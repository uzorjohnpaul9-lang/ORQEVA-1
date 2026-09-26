"""Billing service - Phase 12: invoices, subscriptions, promos, refunds.

Pricing/wallet config comes from the trading system's payments module so the
Telegram bot and the dashboard share one source of truth.
"""
import logging
from datetime import datetime, timedelta, timezone

from backend.db.models import (
    INVOICES,
    PROMO_CODES,
    SUBSCRIPTIONS,
    USERS,
    gen_uuid,
)
from backend.db.supabase import SupabaseDB, now_iso, parse_dt
from payments.payment_manager import (
    PAYMENT_CONFIG,
    WALLET_ADDRESSES,
    load_payment_config,
    save_payment_config,
)

logger = logging.getLogger(__name__)

INVOICE_TTL_HOURS = {"crypto": 24, "manual": 48}


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


async def create_invoice(db: SupabaseDB, user: dict, tier: str,
                         method: str = "crypto", promo_code: str | None = None) -> dict:
    """Create a payment invoice for a paid tier."""
    cfg = PAYMENT_CONFIG.get(tier)
    if not cfg or tier == "free":
        return {"error": "invalid_tier"}
    if method not in ("crypto", "manual"):
        return {"error": "invalid_method"}

    promo, discount_pct = await validate_promo(db, promo_code)
    amount = float(cfg["price"])
    discount = round(amount * discount_pct / 100.0, 2)
    total = round(max(amount - discount, 0.0), 2)

    network = None
    wallet = None
    if method == "crypto":
        network = "usdt_trc20" if total > 100 else "usdt_trc20"
        wallet = WALLET_ADDRESSES.get(network)

    invoice = {
        "id": gen_uuid(),
        "user_id": user["id"],
        "tier": tier,
        "method": method,
        "network": network,
        "wallet_address": wallet,
        "amount_usd": total,
        "discount_usd": discount,
        "promo_code": promo.get("code") if promo else None,
        "status": "pending",
        "tx_ref": None,
        "note": None,
        "created_at": now_iso(),
        "expires_at": _iso(_utcnow() + timedelta(hours=INVOICE_TTL_HOURS[method])),
        "processed_at": None,
        "processed_by": None,
    }
    created = await db.insert(INVOICES, invoice)
    logger.info(f"Invoice {created['id']} created: {tier} ${total} for {user['email']}")
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

    # Upsert subscription: extend if same tier, replace on tier change
    sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": invoice["user_id"]})
    days = PAYMENT_CONFIG[invoice["tier"]]["duration_days"]
    base = _utcnow()
    same_tier = sub and sub.get("status") == "active" and sub.get("tier") == invoice["tier"]
    if same_tier and sub.get("expires_at") and _utcnow() < parse_dt(sub["expires_at"]):
        base = parse_dt(sub["expires_at"])  # stack renewals on top of remaining time
    new_expires = _iso(base + timedelta(days=days))
    if sub is None:
        await db.insert(
            SUBSCRIPTIONS,
            {
                "id": gen_uuid(),
                "user_id": invoice["user_id"],
                "tier": invoice["tier"],
                "status": "active",
                "auto_renew": True,
                "started_at": now_iso(),
                "expires_at": new_expires,
                "last_invoice_id": invoice["id"],
            },
        )
    else:
        # started_at only moves when a new/different tier is purchased
        await db.update(
            SUBSCRIPTIONS,
            {
                "tier": invoice["tier"],
                "status": "active",
                "expires_at": new_expires,
                "last_invoice_id": invoice["id"],
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

    done = await db.fetch_one(INVOICES, {"id": invoice["id"]})
    logger.info(f"Invoice {done['id']} approved by {admin['email']}: {invoice['tier']} until {new_expires}")
    return done


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
    return done


async def get_subscription(db: SupabaseDB, user_id: str) -> dict | None:
    """Current subscription state; sweeps expiry lazily."""
    sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": user_id})
    if not sub:
        return None
    if sub.get("status") == "active" and sub.get("expires_at") and _utcnow() > parse_dt(sub["expires_at"]):
        await db.update(SUBSCRIPTIONS, {"status": "expired"}, where={"user_id": user_id})
        await db.update(USERS, {"tier": "free", "updated_at": now_iso()}, where={"id": user_id})
        sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": user_id}) or sub

    invoices = await db.fetch_all(INVOICES, where={"user_id": user_id, "status": "approved"}, columns="amount_usd")
    lifetime_spend = sum(float(i.get("amount_usd") or 0) for i in invoices)
    expires = parse_dt(sub.get("expires_at"))

    return {
        "tier": sub.get("tier"),
        "status": sub.get("status"),
        "auto_renew": bool(sub.get("auto_renew")),
        "started_at": sub.get("started_at"),
        "expires_at": sub.get("expires_at"),
        "days_left": max((expires - _utcnow()).days, 0) if expires else 0,
        "lifetime_spend_usd": round(lifetime_spend, 2),
    }


async def set_auto_renew(db: SupabaseDB, user_id: str, enabled: bool) -> bool:
    sub = await db.fetch_one(SUBSCRIPTIONS, {"user_id": user_id})
    if not sub:
        return False
    await db.update(SUBSCRIPTIONS, {"auto_renew": enabled}, where={"user_id": user_id})
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