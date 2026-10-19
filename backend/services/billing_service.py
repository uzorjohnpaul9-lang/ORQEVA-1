"""Billing service - Phase 12: invoices, subscriptions, promos, refunds.

Pricing/wallet config comes from the trading system's payments module so the
Telegram bot and the dashboard share one source of truth.
"""
import asyncio
import logging
import math
import random
from datetime import datetime, timedelta, timezone

from backend.config import settings
from backend.db.models import (
    INVOICES,
    PAYMENT_EVENTS,
    PROMO_CODES,
    SUBSCRIPTIONS,
    USERS,
    gen_uuid,
)
from backend.db.supabase import SupabaseDB, now_iso, parse_dt
from backend.payments.registry import (
    GATEWAY_METHODS,
    configured_gateways,
    get_provider,
    is_gateway,
)
from payments.payment_manager import (
    PAYMENT_CONFIG,
    WALLET_ADDRESSES,
    load_payment_config,
    save_payment_config,
)

logger = logging.getLogger(__name__)

INVOICE_TTL_HOURS = {"crypto": 24, "manual": 48, "gateway": 24}
GRACE_DAYS = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def plans() -> list[dict]:
    out = []
    for tier, cfg in PAYMENT_CONFIG.items():
        if tier == "free":
            continue
        out.append({
            "tier": tier,
            "name": cfg["name"],
            "price_usd": cfg["price"],
            "duration_days": cfg["duration_days"],
        })
    return out


def bank_card_details() -> dict:
    """Admin-configured receiving details for the manual (bank/card) method."""
    return (load_payment_config().get("bank_card") or {})


async def admin_set_bank_card_details(data: dict) -> dict:
    """Persist admin-configured receiving details for the manual method."""
    return save_payment_config({"bank_card": data})


async def validate_promo(db: SupabaseDB, code: str | None) -> tuple[dict | None, float]:
    """Returns (promo_row_or_None, discount_pct)."""
    if not code:
        return None, 0.0
    promo = await db.fetch_one(PROMO_CODES, {"code": code.strip().upper()})
    if not promo or not promo.get("active"):
        return None, 0.0
    expires = parse_dt(promo.get("expires_at"))
    if expires and _utcnow() > expires:
        return None, 0.0
    if int(promo.get("uses_count") or 0) >= int(promo.get("max_uses") or 0):
        return None, 0.0
    return promo, float(promo.get("discount_pct") or 0)


async def _unique_amount(db: SupabaseDB, base: float) -> float:
    """Per-invoice unique amount (base + random cents) so hand-pay transactions
    can be auto-matched to the invoice they belong to."""
    for _ in range(25):
        candidate = round(base + random.randint(1, 99) / 100.0, 2)
        clash = await db.fetch_one(INVOICES, {"unique_amount": candidate, "status": "pending"})
        if not clash:
            return candidate
    return round(base + random.randint(100, 999) / 100.0, 2)


async def create_invoice(db: SupabaseDB, user: dict, tier: str,
                         method: str = "crypto", promo_code: str | None = None) -> dict:
    """Create a payment invoice for a paid tier.

    `method` is a legacy rail (crypto/manual) or a configured gateway
    (nowpayments/stripe/paystack/flutterwave) which returns a hosted checkout.
    """
    cfg = PAYMENT_CONFIG.get(tier)
    if not cfg or tier == "free":
        return {"error": "invalid_tier"}
    if method not in GATEWAY_METHODS and method not in ("crypto", "manual"):
        return {"error": "invalid_method"}

    promo, discount_pct = await validate_promo(db, promo_code)
    amount = float(cfg["price"])
    discount = round(amount * discount_pct / 100.0, 2)
    total = round(max(amount - discount, 0.0), 2)

    network = None
    wallet = None
    if method == "crypto":
        network = "usdt_trc20"
        wallet = WALLET_ADDRESSES.get(network)

    invoice_id = gen_uuid()
    invoice = {
        "id": invoice_id,
        "user_id": user["id"],
        "tier": tier,
        "method": "gateway" if is_gateway(method) else method,
        "network": network,
        "wallet_address": wallet,
        "amount_usd": total,
        "discount_usd": discount,
        "promo_code": promo.get("code") if promo else None,
        "status": "pending",
        "tx_ref": None,
        "note": None,
        "provider": method if is_gateway(method) else ("crypto" if method == "crypto" else "manual"),
        "provider_ref": None,
        "checkout_url": None,
        "unique_amount": None,
        "memo": f"ORQ-{invoice_id[:8].upper()}" if method in ("crypto", "manual") else None,
        "currency": "USD",
        "paid_at": None,
        "created_at": now_iso(),
        "expires_at": _iso(_utcnow() + timedelta(
            hours=INVOICE_TTL_HOURS["gateway" if is_gateway(method) else method])),
        "processed_at": None,
        "processed_by": None,
    }

    if method in ("crypto", "manual"):
        invoice["unique_amount"] = await _unique_amount(db, total)

    created = await db.insert(INVOICES, invoice)

    if is_gateway(method):
        provider = get_provider(method)
        if provider is None:
            await db.update(INVOICES, {"status": "cancelled"}, where={"id": invoice_id})
            return {"error": "invalid_method"}
        checkout_input = dict(created)
        checkout_input["_user_email"] = user.get("email")
        result = await asyncio.to_thread(provider.create_checkout, checkout_input, settings.APP_BASE_URL)
        if not result.get("ok"):
            await db.update(
                INVOICES,
                {"status": "cancelled", "note": f"checkout failed: {str(result.get('detail'))[:200]}"},
                where={"id": invoice_id},
            )
            logger.warning("checkout failed for %s via %s: %s", invoice_id, method, result.get("detail"))
            return {"error": "checkout_unavailable"}
        rows = await db.update(
            INVOICES,
            {"checkout_url": result.get("checkout_url"), "provider_ref": result.get("provider_ref") or None},
            where={"id": invoice_id},
        )
        created = rows[0] if rows else (await db.fetch_one(INVOICES, {"id": invoice_id}) or created)

    logger.info(f"Invoice {created['id']} created: {tier} ${total} via {method} for {user['email']}")
    return created


def invoice_view(inv: dict, email: str | None = None) -> dict:
    d = {
        "id": inv["id"],
        "tier": inv.get("tier"),
        "method": inv.get("method"),
        "network": inv.get("network"),
        "wallet_address": inv.get("wallet_address"),
        "amount_usd": inv.get("amount_usd"),
        "discount_usd": inv.get("discount_usd"),
        "promo_code": inv.get("promo_code"),
        "status": inv.get("status"),
        "tx_ref": inv.get("tx_ref"),
        "provider": inv.get("provider"),
        "provider_ref": inv.get("provider_ref"),
        "checkout_url": inv.get("checkout_url"),
        "unique_amount": inv.get("unique_amount"),
        "memo": inv.get("memo"),
        "paid_at": inv.get("paid_at"),
        "created_at": inv.get("created_at"),
        "expires_at": inv.get("expires_at"),
        "processed_at": inv.get("processed_at"),
    }
    if email is not None:
        d["user_email"] = email
    return d


async def get_owned_invoice(db: SupabaseDB, invoice_id: str, user_id: str | None = None) -> dict | None:
    where: dict = {"id": invoice_id}
    if user_id is not None:
        where["user_id"] = user_id
    return await db.fetch_one(INVOICES, where)


async def submit_tx_ref(db: SupabaseDB, invoice: dict, tx_ref: str) -> dict:
    await db.update(INVOICES, {"tx_ref": tx_ref[:500]}, where={"id": invoice["id"]})
    return await db.fetch_one(INVOICES, {"id": invoice["id"]})


async def cancel_invoice(db: SupabaseDB, invoice: dict) -> dict:
    await db.update(
        INVOICES,
        {"status": "cancelled", "processed_at": now_iso()},
        where={"id": invoice["id"]},
    )
    return await db.fetch_one(INVOICES, {"id": invoice["id"]})


async def _activate_subscription(db: SupabaseDB, invoice: dict) -> None:
    """Upsert/extend the subscription + sync tier + count promo usage.

    Shared by admin approval and gateway (webhook) auto-approval.
    """
    sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": invoice["user_id"]})
    days = PAYMENT_CONFIG[invoice["tier"]]["duration_days"]
    base = _utcnow()
    same_tier = sub and sub.get("status") in ("active", "past_due") and sub.get("tier") == invoice["tier"]
    if same_tier and sub.get("expires_at") and _utcnow() < parse_dt(sub["expires_at"]):
        base = parse_dt(sub["expires_at"])  # stack renewals on top of remaining time
    new_expires = _iso(base + timedelta(days=days))
    provider = invoice.get("provider") or None
    provider_ref = invoice.get("provider_ref") or None
    if sub is None:
        await db.insert(
            SUBSCRIPTIONS,
            {
                "id": gen_uuid(),
                "user_id": invoice["user_id"],
                "tier": invoice["tier"],
                "status": "active",
                "auto_renew": True,
                "cancel_at_period_end": False,
                "grace_until": None,
                "provider": provider,
                "provider_ref": provider_ref,
                "reminder_sent_count": 0,
                "started_at": now_iso(),
                "expires_at": new_expires,
                "last_invoice_id": invoice["id"],
            },
        )
    else:
        # started_at only moves when a new/different tier is purchased;
        # a cancelled-at-period-end renewal reactivates on payment.
        await db.update(
            SUBSCRIPTIONS,
            {
                "tier": invoice["tier"],
                "status": "active",
                "expires_at": new_expires,
                "last_invoice_id": invoice["id"],
                "grace_until": None,
                "cancel_at_period_end": False,
                "provider": provider or sub.get("provider"),
                "provider_ref": provider_ref,
                "reminder_sent_count": 0,
            },
            where={"user_id": invoice["user_id"]},
        )

    # Promo usage count
    if invoice.get("promo_code"):
        promo = await db.fetch_one(PROMO_CODES, {"code": invoice["promo_code"]})
        if promo:
            await db.update(
                PROMO_CODES,
                {"uses_count": int(promo.get("uses_count") or 0) + 1},
                where={"code": invoice["promo_code"]},
            )

    # Tier takes effect immediately
    await db.update(USERS, {"tier": invoice["tier"], "updated_at": now_iso()}, where={"id": invoice["user_id"]})


async def approve_invoice(db: SupabaseDB, invoice: dict, admin: dict) -> dict:
    if invoice.get("status") != "pending":
        return {"error": f"invoice already {invoice.get('status')}"}
    if _utcnow() > parse_dt(invoice.get("expires_at")):
        await db.update(
            INVOICES,
            {
                "status": "rejected",
                "note": "approval attempted after expiry",
                "processed_at": now_iso(),
                "processed_by": admin["id"],
            },
            where={"id": invoice["id"]},
        )
        return {"error": "invoice expired"}

    await db.update(
        INVOICES,
        {
            "status": "approved",
            "processed_at": now_iso(),
            "processed_by": admin["id"],
        },
        where={"id": invoice["id"]},
    )
    await _activate_subscription(db, invoice)

    done = await db.fetch_one(INVOICES, {"id": invoice["id"]})
    logger.info(f"Invoice {done['id']} approved by {admin['email']}: {invoice['tier']}")
    return done


# ---- Gateway webhooks (auto-approve) ---------------------------------------

async def record_payment_event(db: SupabaseDB, provider: str, event_id: str, *,
                               invoice_id: str | None = None, type: str | None = None,
                               status: str = "processed", detail: str | None = None,
                               payload: dict | None = None) -> dict:
    """Idempotent webhook log: unique (provider, event_id) means replayed
    deliveries are recognized and dropped. Returns {duplicate, row}."""
    existing = await db.fetch_one(PAYMENT_EVENTS, {"provider": provider, "event_id": event_id})
    if existing:
        return {"duplicate": True, "row": existing}
    row = {
        "id": gen_uuid(),
        "provider": provider,
        "event_id": event_id[:200],
        "invoice_id": invoice_id,
        "type": type,
        "status": status,
        "detail": (detail or None) and detail[:300],
        "payload": payload,
        "created_at": now_iso(),
    }
    try:
        await db.insert(PAYMENT_EVENTS, row)
        return {"duplicate": False, "row": row}
    except Exception:
        # Concurrent duplicate delivery raced the unique index.
        again = await db.fetch_one(PAYMENT_EVENTS, {"provider": provider, "event_id": event_id})
        if again:
            return {"duplicate": True, "row": again}
        logger.exception("payment_events insert failed")
        return {"duplicate": False, "row": row}


async def approve_from_gateway(db: SupabaseDB, invoice: dict, *,
                               provider: str, provider_ref: str | None,
                               amount_usd: float | None) -> dict:
    """Auto-approve a pending invoice from a verified gateway payment."""
    if invoice.get("status") != "pending":
        return {"error": f"invoice already {invoice.get('status')}"}

    if amount_usd is not None:
        expected = float(invoice.get("unique_amount") or invoice.get("amount_usd") or 0)
        if amount_usd + 0.01 < expected:
            logger.warning("Gateway amount %s < invoice %s; approving anyway",
                           amount_usd, expected)

    await db.update(
        INVOICES,
        {
            "status": "approved",
            "processed_at": now_iso(),
            "processed_by": None,
            "provider": provider,
            "provider_ref": provider_ref or invoice.get("provider_ref"),
            "paid_at": now_iso(),
        },
        where={"id": invoice["id"]},
    )
    await _activate_subscription(db, invoice)

    done = await db.fetch_one(INVOICES, {"id": invoice["id"]})
    logger.info("Invoice %s auto-approved via %s webhook", done["id"], provider)
    return done


async def handle_gateway_webhook(db: SupabaseDB, provider_name: str,
                                 headers: dict, body: bytes, payload: dict) -> dict:
    """Verify signature, dedupe, normalize, auto-approve. Never raises;
    returns {ok, status, detail, ...} so the router can answer correctly."""
    provider = get_provider(provider_name)
    if provider is None:
        return {"ok": False, "status": 404, "detail": "unknown provider"}

    verified = provider.verify_webhook(headers, body, payload)
    if not verified.get("ok"):
        logger.warning("Webhook rejected (%s): %s", provider_name, verified.get("detail"))
        return {"ok": False, "status": 400, "detail": verified.get("detail") or "verification failed"}

    event = verified["event"]
    rec = await record_payment_event(
        db, provider_name, event.event_id,
        invoice_id=event.invoice_id, type=event.type,
        status="processed" if event.paid else "ignored",
        payload=payload if len(str(payload)) < 20000 else {"truncated": True},
    )
    if rec["duplicate"]:
        return {"ok": True, "status": 200, "duplicate": True, "detail": "event already processed"}
    if not event.paid:
        return {"ok": True, "status": 200, "detail": f"event '{event.type}' recorded (not a payment)"}

    invoice = None
    if event.invoice_id:
        invoice = await db.fetch_one(INVOICES, {"id": event.invoice_id})
    if invoice is None and event.provider_ref:
        invoice = await db.fetch_one(INVOICES, {"provider_ref": event.provider_ref})
    if invoice is None:
        await record_payment_event(
            db, provider_name, event.event_id + ":orphan",
            type=event.type, status="ignored", detail="invoice not found",
        )
        return {"ok": True, "status": 200, "detail": "no matching invoice"}

    out = await approve_from_gateway(
        db, invoice, provider=provider_name,
        provider_ref=event.provider_ref, amount_usd=event.amount_usd,
    )
    if out.get("error"):
        return {"ok": True, "status": 200, "detail": out["error"]}
    await _notify_paid(db, out)
    return {"ok": True, "status": 200, "approved": True, "invoice_id": out["id"],
            "tier": out.get("tier")}


async def _notify_paid(db: SupabaseDB, invoice: dict) -> None:
    """In-app + Telegram + email confirmation after a gateway auto-approval."""
    try:
        from backend.services import email_service
        from backend.services import notification_service as notif_service
        from backend.services import telegram_service

        owner = await db.fetch_one(USERS, {"id": invoice["user_id"]})
        if not owner:
            return
        tier = (invoice.get("tier") or "").upper()
        text = f"\U0001f389 <b>Subscription active</b>\nYour {tier} plan was confirmed and is now live. Thank you!"
        await telegram_service.notify_user(db, owner, "system", text)
        await notif_service.create(db, owner["id"], "system", "Subscription activated",
                                   f"Your {tier} plan was confirmed and is now live.",
                                   respect_prefs=True)
        base = settings.APP_BASE_URL.rstrip("/")
        subject, html = email_service.subscription_paid_email(tier, f"{base}/billing")
        await email_service.send_email(owner.get("email") or "", subject, html)
    except Exception:  # pragma: no cover - notify must never fail the webhook
        logger.exception("paid notification failed for invoice %s", invoice.get("id"))


async def reject_invoice(db: SupabaseDB, invoice: dict, admin: dict, reason: str) -> dict:
    if invoice.get("status") != "pending":
        return {"error": f"invoice already {invoice.get('status')}"}
    await db.update(
        INVOICES,
        {
            "status": "rejected",
            "note": (reason[:300] or None),
            "processed_at": now_iso(),
            "processed_by": admin["id"],
        },
        where={"id": invoice["id"]},
    )
    return await db.fetch_one(INVOICES, {"id": invoice["id"]})


async def refund_invoice(db: SupabaseDB, invoice: dict, admin: dict, reason: str) -> dict:
    if invoice.get("status") != "approved":
        return {"error": "only approved invoices can be refunded"}

    await db.update(
        INVOICES,
        {
            "status": "refunded",
            "note": (reason[:300] or None),
            "processed_at": now_iso(),
            "processed_by": admin["id"],
        },
        where={"id": invoice["id"]},
    )
    await db.update(SUBSCRIPTIONS, {"status": "cancelled"}, where={"user_id": invoice["user_id"]})
    await db.update(USERS, {"tier": "free", "updated_at": now_iso()}, where={"id": invoice["user_id"]})

    done = await db.fetch_one(INVOICES, {"id": invoice["id"]})
    logger.warning(f"Invoice {done['id']} refunded by {admin['email']}")

    # Best-effort: tell the gateway so card/charge reversals actually process.
    provider = get_provider(invoice.get("provider") or "")
    if provider is not None:
        try:
            result = await provider.refund(invoice)
            if not result.get("ok"):
                logger.info("Gateway refund skipped for %s: %s", invoice["id"], result.get("detail"))
        except Exception:  # pragma: no cover - defensive
            logger.exception("gateway refund failed")
    return done


async def get_subscription(db: SupabaseDB, user_id: str) -> dict | None:
    """Current subscription state; sweeps expiry lazily.

    Past expiry, auto-renewing subs get a GRACE_DAYS window (status "grace")
    so dunning reminders/renewal invoices have room to land; only after grace
    (or when auto-renew is off) does the tier downgrade.
    """
    sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": user_id})
    if not sub:
        return None
    now = _utcnow()
    expires = parse_dt(sub.get("expires_at"))
    in_grace = False
    if sub.get("status") == "active" and expires and now > expires:
        grace = parse_dt(sub.get("grace_until"))
        if sub.get("auto_renew") and not sub.get("cancel_at_period_end"):
            if not grace:
                grace = expires + timedelta(days=GRACE_DAYS)
                await db.update(SUBSCRIPTIONS, {"grace_until": _iso(grace)}, where={"user_id": user_id})
            in_grace = now <= grace
        if not in_grace:
            await db.update(SUBSCRIPTIONS, {"status": "expired"}, where={"user_id": user_id})
            await db.update(USERS, {"tier": "free", "updated_at": now_iso()}, where={"id": user_id})
            sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": user_id}) or sub

    invoices = await db.fetch_all(INVOICES, where={"user_id": user_id, "status": "approved"}, columns="amount_usd")
    lifetime_spend = sum(float(i.get("amount_usd") or 0) for i in invoices)

    status = sub.get("status")
    if in_grace and status == "active":
        status = "grace"

    return {
        "tier": sub.get("tier"),
        "status": status,
        "auto_renew": bool(sub.get("auto_renew")),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "grace_until": sub.get("grace_until"),
        "started_at": sub.get("started_at"),
        "expires_at": sub.get("expires_at"),
        "days_left": max((expires - now).days, 0) if expires else 0,
        "lifetime_spend_usd": round(lifetime_spend, 2),
    }


async def set_auto_renew(db: SupabaseDB, user_id: str, enabled: bool) -> bool:
    """auto_renew=False is cancel-at-period-end: the plan stays until
    expires_at, then downgrades (no renewal invoice is created)."""
    sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": user_id})
    if not sub:
        return False
    await db.update(
        SUBSCRIPTIONS,
        {"auto_renew": enabled, "cancel_at_period_end": not enabled},
        where={"user_id": user_id},
    )
    return True


# ---- Admin ----

async def admin_promo_create(db: SupabaseDB, code: str, discount_pct: float,
                             max_uses: int, expires_days: int | None) -> dict:
    code = code.strip().upper()
    if not code or len(code) > 40:
        return {"error": "invalid_code"}
    if not (1 <= discount_pct <= 100):
        return {"error": "discount must be 1-100"}
    existing = await db.fetch_one(PROMO_CODES, {"code": code})
    if existing:
        return {"error": "code exists"}
    promo = {
        "code": code,
        "discount_pct": discount_pct,
        "max_uses": max_uses,
        "uses_count": 0,
        "active": True,
        "expires_at": _iso(_utcnow() + timedelta(days=expires_days)) if expires_days else None,
    }
    return await db.insert(PROMO_CODES, promo)


async def admin_promos(db: SupabaseDB) -> list[dict]:
    return await db.fetch_all(PROMO_CODES, order="code")


async def admin_promo_toggle(db: SupabaseDB, code: str) -> dict:
    promo = await db.fetch_one(PROMO_CODES, {"code": code.upper()})
    if not promo:
        return {"error": "not_found"}
    await db.update(PROMO_CODES, {"active": not promo.get("active")}, where={"code": code.upper()})
    return await db.fetch_one(PROMO_CODES, {"code": code.upper()}) or promo


def promo_view(p: dict) -> dict:
    return {
        "code": p.get("code"),
        "discount_pct": p.get("discount_pct"),
        "max_uses": p.get("max_uses"),
        "uses_count": p.get("uses_count"),
        "active": bool(p.get("active")),
        "expires_at": p.get("expires_at"),
    }


async def admin_stats(db: SupabaseDB) -> dict:
    approved = await db.fetch_all(INVOICES, where={"status": "approved"}, columns="tier,amount_usd")
    revenue = sum(float(i.get("amount_usd") or 0) for i in approved)
    refunded_rows = await db.fetch_all(INVOICES, where={"status": "refunded"}, columns="amount_usd")
    refunded = sum(float(i.get("amount_usd") or 0) for i in refunded_rows)
    pending = await db.count(INVOICES, where={"status": "pending"})
    approved_n = len(approved)
    active_subs = await db.count(SUBSCRIPTIONS, where={"status": "active"})

    revenue_by_tier: dict[str, dict] = {}
    for i in approved:
        t = i.get("tier") or "free"
        agg = revenue_by_tier.setdefault(t, {"count": 0, "revenue_usd": 0.0})
        agg["count"] += 1
        agg["revenue_usd"] += float(i.get("amount_usd") or 0)
    for t in revenue_by_tier:
        revenue_by_tier[t]["revenue_usd"] = round(revenue_by_tier[t]["revenue_usd"], 2)

    return {
        "revenue_usd": round(revenue, 2),
        "refunded_usd": round(refunded, 2),
        "net_usd": round(revenue - refunded, 2),
        "pending_invoices": int(pending),
        "approved_invoices": int(approved_n),
        "active_subscriptions": int(active_subs),
        "revenue_by_tier": revenue_by_tier,
    }


async def admin_list_invoices(db: SupabaseDB, status: str | None = None, limit: int = 100) -> list[dict]:
    where = {"status": status} if status else None
    invoices = await db.fetch_all(INVOICES, where=where, order="created_at.desc", limit=limit)
    user_ids = {i["user_id"] for i in invoices}
    email_map: dict[str, str] = {}
    if user_ids:
        users = await db.fetch_all(USERS, where={"id": list(user_ids)}, columns="id,email")
        email_map = {u["id"]: u.get("email") or "" for u in users}
    return [invoice_view(inv, email_map.get(inv["user_id"])) for inv in invoices]


# ---- Revenue dashboard -------------------------------------------------------

async def revenue_dashboard(db: SupabaseDB) -> dict:
    """MRR/ARR, tier mix, revenue over time, expiring-soon, churn, LTV."""
    approved = await db.fetch_all(
        INVOICES, where={"status": "approved"}, columns="tier,amount_usd,created_at,provider,user_id")
    refunded_rows = await db.fetch_all(INVOICES, where={"status": "refunded"}, columns="amount_usd")
    revenue = sum(float(i.get("amount_usd") or 0) for i in approved)
    refunded = sum(float(i.get("amount_usd") or 0) for i in refunded_rows)
    pending = await db.count(INVOICES, where={"status": "pending"})
    subs = await db.fetch_all(SUBSCRIPTIONS, columns="id,tier,status,expires_at,grace_until,cancel_at_period_end")

    active = [s for s in subs if s.get("status") in ("active", "past_due")]
    grace = [s for s in subs if parse_dt(s.get("grace_until")) and _utcnow() <= parse_dt(s.get("grace_until"))]
    # "grace" rows are still status=active in the table; count them once
    active_ids = {s.get("id") for s in active}
    grace = [s for s in grace if s.get("id") in active_ids]

    def _price(tier: str) -> float:
        return float((PAYMENT_CONFIG.get(tier) or {}).get("price") or 0)

    mrr = sum(_price(s.get("tier")) for s in active)

    by_tier = {}
    for s in active:
        t = s.get("tier") or "free"
        agg = by_tier.setdefault(t, {"count": 0, "mrr_usd": 0.0})
        agg["count"] += 1
        agg["mrr_usd"] += _price(t)

    now = _utcnow()
    windows = {"expiring_7d": 7, "expiring_3d": 3, "expiring_1d": 1}
    expiring = {}
    for key, days in windows.items():
        expiring[key] = sum(
            1 for s in active
            if s.get("expires_at")
            and 0 < (parse_dt(s["expires_at"]) - now).days <= days
        )

    cutoff_30 = now - timedelta(days=30)
    churned = sum(
        1 for s in subs
        if s.get("status") in ("expired", "cancelled")
        and parse_dt(s.get("expires_at") or s.get("grace_until"))
        and parse_dt(s.get("expires_at") or s.get("grace_until")) >= cutoff_30
    )
    cancelling = sum(1 for s in active if s.get("cancel_at_period_end"))

    revenue_by_month: list[dict] = []
    buckets: dict[str, float] = {}
    for i in approved:
        dt = parse_dt(i.get("created_at"))
        if not dt:
            continue
        key = dt.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0.0) + float(i.get("amount_usd") or 0)
    for m in range(5, -1, -1):
        key = (now - timedelta(days=30 * m)).strftime("%Y-%m")
        revenue_by_month.append({"month": key, "revenue_usd": round(buckets.get(key, 0.0), 2)})

    by_provider: dict[str, dict] = {}
    for i in approved:
        p = i.get("provider") or "manual"
        agg = by_provider.setdefault(p, {"count": 0, "revenue_usd": 0.0})
        agg["count"] += 1
        agg["revenue_usd"] += float(i.get("amount_usd") or 0)
    for p in by_provider:
        by_provider[p]["revenue_usd"] = round(by_provider[p]["revenue_usd"], 2)

    payers = len({i.get("user_id") for i in approved})
    net = round(revenue - refunded, 2)

    return {
        "revenue_usd": round(revenue, 2),
        "refunded_usd": round(refunded, 2),
        "net_usd": net,
        "mrr_usd": round(mrr, 2),
        "arr_usd": round(mrr * 12, 2),
        "pending_invoices": int(pending),
        "active_subscriptions": len(active),
        "subscriptions_by_tier": by_tier,
        "in_grace": len(grace),
        "cancelling_at_period_end": cancelling,
        **expiring,
        "churned_30d": int(churned),
        "revenue_by_month": revenue_by_month,
        "revenue_by_provider": by_provider,
        "ltv_usd": round(net / payers, 2) if payers else 0.0,
        "paying_users": payers,
        "gateway_providers": configured_gateways(),
    }


# ---- Reminders / dunning (scheduler) ---------------------------------------

async def _warn_subscriber(db: SupabaseDB, user_id: str, tier: str, days_left: int,
                           reason: str) -> None:
    try:
        owner = await db.fetch_one(USERS, {"id": user_id})
        if not owner:
            return
        from backend.services import notification_service as notif_service
        from backend.services import telegram_service
        from backend.services import email_service

        text = (
            f"Your {tier.upper()} subscription expires in {days_left} day"
            f"{'s' if days_left != 1 else ''}. {reason}"
        )
        await notif_service.create(db, user_id, "system", "Subscription expiring", text,
                                   respect_prefs=True)
        await telegram_service.notify_user(db, owner, "system", f"⏰ <b>Subscription expiring</b>\n{text}")
        subject, html = email_service.subscription_expiring_email(tier, days_left, reason)
        await email_service.send_email(owner.get("email") or "", subject, html)
    except Exception:  # pragma: no cover - never fail the sweep on notify
        logger.exception("subscription warning failed for %s", user_id)


async def billing_jobs(db: SupabaseDB) -> dict:
    """Daily billing sweep: expiry reminders (7/3/1d), renewal invoices for
    auto-renew subs, grace-window expiry downgrade, stale invoice cleanup.

    Called from the scheduler; every step is independently failure-tolerant.
    """
    out = {"reminders_sent": 0, "renewal_invoices": 0, "grace_expired": 0, "invoices_expired": 0}
    now = _utcnow()

    # 1) pending invoices past their TTL
    stale = await db.fetch_all(INVOICES, where={"status": "pending"}, columns="id,expires_at")
    for inv in stale:
        exp = parse_dt(inv.get("expires_at"))
        if exp and now > exp:
            await db.update(INVOICES, {"status": "expired", "processed_at": now_iso()},
                            where={"id": inv["id"]})
            out["invoices_expired"] += 1

    # 2) grace windows that ran out -> expire + downgrade (even without a lazy read)
    subs = await db.fetch_all(SUBSCRIPTIONS, where={"status": "active"})
    for sub in subs:
        grace = parse_dt(sub.get("grace_until"))
        expires = parse_dt(sub.get("expires_at"))
        wants_renewal = sub.get("auto_renew") and not sub.get("cancel_at_period_end")
        if not grace and expires and now > expires and wants_renewal:
            grace = expires + timedelta(days=GRACE_DAYS)
            await db.update(SUBSCRIPTIONS, {"grace_until": _iso(grace)}, where={"user_id": sub["user_id"]})
        expired = grace and now > grace
        if not grace and expires and now > expires and not wants_renewal:
            expired = True
        if expired:
            await db.update(SUBSCRIPTIONS, {"status": "expired"}, where={"user_id": sub["user_id"]})
            await db.update(USERS, {"tier": "free", "updated_at": now_iso()}, where={"id": sub["user_id"]})
            out["grace_expired"] += 1
            continue

        if sub.get("cancel_at_period_end") or not sub.get("auto_renew"):
            continue  # cancelled at period end: no reminders, no renewal invoice

        # 3) expiry reminders at the 7/3/1-day marks (pre-expiry only).
        # Ceil-based so a sweep landing exactly on a boundary (or a non-daily
        # cadence) still crosses each threshold exactly once - truncating
        # .days can skip a whole bucket at the 8.0/4.0/2.0-day edges.
        if not expires:
            continue
        remaining = (expires - now).total_seconds()
        in_grace = bool(grace and now > expires)
        if remaining > 0:
            days_left = math.ceil(remaining / 86400)
            sent = int(sub.get("reminder_sent_count") or 0)
            step = None
            if days_left <= 1 and sent <= 2:
                step = 2
            elif days_left <= 3 and sent <= 1:
                step = 1
            elif days_left <= 7 and sent <= 0:
                step = 0
            if step is not None:
                reason = ("Renew now to keep signals, alerts and VIP auto-trade running."
                          if sub.get("auto_renew") else
                          "Cancel or renew before it lapses.")
                await _warn_subscriber(db, sub["user_id"], sub.get("tier") or "premium",
                                       days_left, reason)
                await db.update(SUBSCRIPTIONS, {"reminder_sent_count": step + 1},
                                where={"user_id": sub["user_id"]})
                out["reminders_sent"] += 1

        # 4) auto-renew: open a renewal invoice a few days out (once).
        # Also covers the grace window (already past expiry) so dunning has
        # something to pay against.
        window_end = grace if in_grace else expires
        window_remaining = (window_end - now).total_seconds() if window_end else -1
        win_days = math.ceil(window_remaining / 86400) if window_remaining > -1 else -1
        if 0 <= win_days <= 3:
            days_left = win_days
            recent = await db.fetch_one(
                INVOICES,
                {"user_id": sub["user_id"], "tier": sub.get("tier"), "status": "pending"},
            )
            if not recent:
                owner = await db.fetch_one(USERS, {"id": sub["user_id"]})
                if owner:
                    method = sub.get("provider") or "crypto"
                    if method not in GATEWAY_METHODS and method not in ("crypto", "manual"):
                        method = "crypto"
                    created = await create_invoice(db, owner, sub.get("tier") or "premium", method)
                    if not created.get("error"):
                        out["renewal_invoices"] += 1
                        await _warn_subscriber(
                            db, sub["user_id"], sub.get("tier") or "premium", days_left,
                            "Your renewal invoice is ready — payment renews your plan instantly.")

    return out