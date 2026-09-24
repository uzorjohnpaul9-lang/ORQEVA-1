"""Admin space endpoints (all require_admin). See frontend /admin."""
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
from backend.services import admin_service, notification_service, telegram_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdate(BaseModel):
    tier: str | None = Field(None, pattern="^(free|premium|vip)$")
    is_admin: bool | None = None
    is_active: bool | None = None
    telegram_chat_id: str | None = None


class ResetPassword(BaseModel):
    notify: bool = True


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