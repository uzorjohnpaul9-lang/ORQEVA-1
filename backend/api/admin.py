"""Admin space endpoints (all require_admin). See frontend /admin."""
import asyncio
import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import require_admin
from backend.db.database import get_db
from backend.db.models import USERS
from backend.db.supabase import SupabaseDB, get_service_client, now_iso
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import admin_service, notification_service, telegram_service, support_service, sentinel_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    tier: str | None = Field(None, pattern="^(free|premium|vip)$")
    is_admin: bool | None = None
    is_active: bool | None = None
    telegram_chat_id: str | None = None


class ResetPassword(BaseModel):
    notify: bool = True


class DeactivateBody(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)
    anonymize: bool = False


class DeleteBody(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)
    # Typed confirmation: must equal the target's current email (case-insensitive).
    confirm: str = Field(..., min_length=1, max_length=255)


async def _auth_metadata(client, user_id: str) -> dict:
    """Existing Supabase Auth user_metadata (defensive; never raises)."""
    try:
        resp = await client.auth.admin.get_user_by_id(user_id)
        return dict((resp.user.user_metadata or {}))
    except Exception:
        return {}


@router.get("/users")
async def users(
    search: str | None = Query(None, max_length=100),
    tier: str | None = Query(None, pattern="^(free|premium|vip)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await admin_service.list_users(db, search=search, tier=tier, limit=limit, offset=offset)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    target = await db.fetch_one(USERS, {"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    updates: dict = {"updated_at": now_iso()}
    meta_updates: dict = {}
    if body.tier is not None:
        updates["tier"] = body.tier
        meta_updates["tier"] = body.tier
    if body.is_admin is not None:
        updates["is_admin"] = body.is_admin
        meta_updates["is_admin"] = body.is_admin
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if body.telegram_chat_id is not None:
        updates["telegram_chat_id"] = body.telegram_chat_id

    if not updates:
        return admin_service.user_view(target)

    # Never allow removing the last admin or disabling yourself.
    if user_id == admin["id"]:
        if updates.get("is_admin") is False:
            raise HTTPException(status_code=400, detail="You cannot revoke your own admin role")
        if updates.get("is_active") is False:
            raise HTTPException(status_code=400, detail="You cannot disable your own account")

    updated = await db.update(USERS, updates, {"id": user_id})
    row = updated[0] if updated else target

    if meta_updates:
        try:
            client = await get_service_client()
            meta = await _auth_metadata(client, user_id)
            meta.update(meta_updates)
            await client.auth.admin.update_user_by_id(user_id, {"user_metadata": meta})
        except Exception as e:
            logger.warning("auth metadata sync failed for %s: %s", user_id, e)

    await admin_service.log_action(
        db, admin, "user.update", "user", user_id,
        {"changes": {k: v for k, v in updates.items() if k != "updated_at"}},
    )
    return admin_service.user_view(row)


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    body: DeactivateBody,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Soft-terminate an account. Optionally anonymize PII (restorable via reactivate)."""
    check_rate_limit(admin["id"], "admin")
    target = await db.fetch_one(USERS, {"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    if await admin_service.is_last_admin(db, target):
        raise HTTPException(status_code=400, detail="Cannot deactivate the last admin")

    updates: dict = {"is_active": False, "updated_at": now_iso()}
    original: dict | None = None
    if body.anonymize:
        original = {"email": target.get("email"), "username": target.get("username")}
        updates.update(admin_service.anonymized_identity(user_id))

    updated = await db.update(USERS, updates, {"id": user_id})
    row = updated[0] if updated else target

    # Persist the original identity in auth metadata so reactivate can restore it.
    if original:
        try:
            client = await get_service_client()
            meta = await _auth_metadata(client, user_id)
            meta["_deactivated_original"] = original
            await client.auth.admin.update_user_by_id(user_id, {"user_metadata": meta})
        except Exception as e:
            logger.warning("auth metadata sync failed for %s: %s", user_id, e)

    await admin_service.log_action(
        db, admin, "user.deactivate", "user", user_id,
        {"reason": body.reason, "anonymized": bool(body.anonymize)},
    )
    return admin_service.user_view(row)


@router.post("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: str,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Reverse a deactivation, restoring anonymized identity when present."""
    check_rate_limit(admin["id"], "admin")
    target = await db.fetch_one(USERS, {"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    updates: dict = {"is_active": True, "updated_at": now_iso()}
    restored = False
    try:
        client = await get_service_client()
        meta = await _auth_metadata(client, user_id)
        original = meta.pop("_deactivated_original", None)
        if isinstance(original, dict):
            if original.get("email"):
                updates["email"] = original["email"]
                restored = True
            if original.get("username"):
                updates["username"] = original["username"]
            await client.auth.admin.update_user_by_id(user_id, {"user_metadata": meta})
    except Exception as e:
        logger.warning("auth metadata restore failed for %s: %s", user_id, e)

    updated = await db.update(USERS, updates, {"id": user_id})
    row = updated[0] if updated else target

    await admin_service.log_action(
        db, admin, "user.reactivate", "user", user_id, {"identity_restored": restored},
    )
    return admin_service.user_view(row)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    body: DeleteBody,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Hard-delete an account: Supabase Auth user + profile (FK cascades children)."""
    check_rate_limit(admin["id"], "admin")
    target = await db.fetch_one(USERS, {"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if await admin_service.is_last_admin(db, target):
        raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    expected = (target.get("email") or "").strip().lower()
    if body.confirm.strip().lower() != expected:
        raise HTTPException(status_code=400, detail="Confirmation does not match the user's email")

    # Remove the auth identity first; if that fails, keep the profile intact so
    # the account is not left half-deleted.
    try:
        client = await get_service_client()
        await client.auth.admin.delete_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Auth deletion failed: {getattr(e, 'message', e)}")

    await db.delete(USERS, {"id": user_id})
    await admin_service.log_action(
        db, admin, "user.delete", "user", user_id,
        {"reason": body.reason, "email": target.get("email")},
    )
    return {"deleted": True, "id": user_id}


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    body: ResetPassword | None = None,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    target = await db.fetch_one(USERS, {"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    alphabet = string.ascii_letters + string.digits
    temp = "".join(secrets.choice(alphabet) for _ in range(14))
    try:
        client = await get_service_client()
        await client.auth.admin.update_user_by_id(user_id, {"password": temp})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Password update failed: {getattr(e, 'message', e)}")

    await admin_service.log_action(
        db, admin, "user.reset_password", "user", user_id, {"temp_issued": True},
    )

    if body is None or body.notify:
        await notification_service.create(
            db, user_id, "system", "Password reset",
            f"Your password was reset by support. Temporary password: {temp}", respect_prefs=False,
        )
        try:
            if target.get("telegram_chat_id"):
                await telegram_service.notify_user(
                    db, target, "system",
                    f"<b>Password reset</b>\nSupport reset your password. Temporary password: {temp}",
                )
        except Exception:
            pass

    return {"reset": True, "temporary_password": temp}


@router.get("/system")
async def system(
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await admin_service.system_status(db)


@router.post("/outcomes/resolve")
async def resolve_outcomes(
    budget_seconds: int = Query(240, ge=10, le=600),
    limit: int = Query(5000, ge=1, le=20000),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Run one bounded outcome-resolution pass on demand (ops + verification)."""
    check_rate_limit(admin["id"], "admin")
    from backend.services import outcome_service

    counts = await outcome_service.resolve_active_signals(
        db, limit=limit, budget_seconds=budget_seconds
    )
    await admin_service.log_action(
        db, admin, "outcomes.resolve", "signal", "batch",
        {"limit": limit, "budget_seconds": budget_seconds, **counts},
    )
    return counts


@router.post("/forward-test")
async def forward_test(
    resolve: bool = Query(False, description="Run an outcome-resolution pass first"),
    budget_seconds: int = Query(120, ge=10, le=600),
    limit: int = Query(2000, ge=1, le=20000),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Live-only forward test: per-market/strategy hit-rate excluding simulated data.

    Optionally runs one bounded outcome-resolution pass first (``resolve=true``)
    so a freshly-resolved batch is reflected immediately.
    """
    check_rate_limit(admin["id"], "admin")
    from backend.services import outcome_service

    resolved: dict | None = None
    if resolve:
        resolved = await outcome_service.resolve_active_signals(
            db, limit=limit, budget_seconds=budget_seconds
        )
        await admin_service.log_action(
            db, admin, "forward_test.run", "signal", "batch",
            {"limit": limit, "budget_seconds": budget_seconds, **resolved},
        )

    stats = await outcome_service.forward_test_stats(db)
    if resolved is not None:
        stats["resolved_now"] = resolved
    return stats


@router.get("/market/providers")
async def market_providers(
    symbol: str = Query("BTC/USD"),
    interval: str = Query("1day"),
    admin: dict = Depends(require_admin),
):
    """Diagnostic: probe each keyless crypto data provider from this host."""
    check_rate_limit(admin["id"], "admin")
    from engines.exchange_data import probe

    providers = await asyncio.to_thread(probe, symbol, interval)
    return {"symbol": symbol, "interval": interval, "providers": providers}


@router.get("/market/sentiment")
async def market_sentiment_probe(
    symbol: str = Query("BTC/USD"),
    admin: dict = Depends(require_admin),
):
    """Diagnostic: probe each keyless sentiment feed from this host (Phase H)."""
    check_rate_limit(admin["id"], "admin")
    from engines import market_sentiment as ms

    rows = await asyncio.to_thread(ms.probe, symbol)
    return {"symbol": symbol, "feeds": rows}


@router.post("/telegram/test-channel")
async def telegram_test_channel(
    tier: str = Query(..., pattern="^(free|premium|vip)$"),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await telegram_service.test_channel(tier)


@router.get("/audit")
async def audit(
    limit: int = Query(50, ge=1, le=200),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await admin_service.list_audit(db, limit)


@router.get("/subscriptions")
async def subscriptions(
    status: str | None = Query(None, pattern="^(active|expired|cancelled)$"),
    limit: int = Query(100, ge=1, le=200),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await admin_service.list_subscriptions(db, status, limit)


@router.get("/signals")
async def signals(
    market: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await admin_service.list_signals(db, market=market, status=status, limit=limit)


@router.post("/signals/{signal_id}/invalidate")
async def invalidate_signal(
    signal_id: str,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    sig = await admin_service.invalidate_signal(db, signal_id)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    await admin_service.log_action(
        db, admin, "signal.invalidate", "signal", signal_id,
        {"symbol": sig.get("symbol"), "market": sig.get("market")},
    )
    return admin_service.signal_view(sig)


# ---- Support queue (Phase F) --------------------------------------------

class SupportReply(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    status: str | None = Field(default=None, pattern="^(open|in_progress|resolved|closed)$")
    priority: str | None = Field(default=None, pattern="^(low|normal|high)$")


class SupportUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|in_progress|resolved|closed)$")
    priority: str | None = Field(default=None, pattern="^(low|normal|high)$")


@router.get("/support")
async def support_list(
    status: str | None = Query(None, pattern="^(open|in_progress|resolved|closed)$"),
    limit: int = Query(100, ge=1, le=200),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await support_service.list_all(db, status=status, limit=limit)


@router.get("/support/stats")
async def support_stats(
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await support_service.stats(db)


@router.get("/support/{ticket_id}")
async def support_get(
    ticket_id: str,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    ticket = await support_service.get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.post("/support/{ticket_id}/reply")
async def support_reply(
    ticket_id: str,
    body: SupportReply,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    ticket = await support_service.reply(
        db, admin, ticket_id, body.message, status=body.status, priority=body.priority
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await admin_service.log_action(
        db, admin, "support.reply", "support_ticket", ticket_id,
        {"status": ticket.get("status")},
    )
    if ticket.get("user_id"):
        await notification_service.create(
            db, ticket["user_id"], "system", "Support replied",
            f"Re: {ticket.get('subject')} - {body.message[:400]}",
        )
    return ticket


@router.patch("/support/{ticket_id}")
async def support_update(
    ticket_id: str,
    body: SupportUpdate,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    ticket = await support_service.set_status(
        db, admin, ticket_id, body.status, priority=body.priority
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await admin_service.log_action(
        db, admin, "support.update", "support_ticket", ticket_id,
        {"status": ticket.get("status"), "priority": ticket.get("priority")},
    )
    return ticket


@router.get("/users/{user_id}/context")
async def user_context(
    user_id: str,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Read-only support context: profile, prefs, activity, connections."""
    check_rate_limit(admin["id"], "admin")
    ctx = await admin_service.user_context(db, user_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="User not found")
    return ctx


@router.get("/sentinel")
async def sentinel_list(
    limit: int = Query(100, ge=1, le=200),
    kind: str | None = Query(None),
    severity: str | None = Query(None),
    resolved: bool | None = Query(None),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    return await sentinel_service.list_events(
        db, limit=limit, kind=kind, severity=severity, resolved=resolved
    )


@router.post("/sentinel/{event_id}/resolve")
async def sentinel_resolve(
    event_id: str,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    ev = await sentinel_service.resolve_event(db, event_id, admin["id"])
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    await admin_service.log_action(
        db, admin, "sentinel.resolve", "security_event", event_id, {"resolved": True}
    )
    return ev


@router.get("/sentinel/blocks")
async def sentinel_blocks(
    active_only: bool = Query(True),
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Auto-block list (active = not yet expired/cleared)."""
    check_rate_limit(admin["id"], "admin")
    return await sentinel_service.list_blocks(db, active_only=active_only)


@router.post("/sentinel/blocks/{ip}/unblock")
async def sentinel_unblock(
    ip: str,
    db: SupabaseDB = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    check_rate_limit(admin["id"], "admin")
    row = await sentinel_service.unblock(db, ip, admin)
    if not row:
        raise HTTPException(status_code=404, detail="IP not blocked")
    return row