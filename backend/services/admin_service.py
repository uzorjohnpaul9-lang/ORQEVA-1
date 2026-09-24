"""Admin operations + audit logging for the /admin space.

Every mutating admin endpoint calls :func:`log_action`, so the operator has a
"who did what" trail. Config values returned to the UI are booleans only --
never secrets.
"""
import logging
import os

from backend.db.models import (
    AUDIT_LOG,
    SIGNALS,
    SUBSCRIPTIONS,
    USERS,
    gen_uuid,
)
from backend.db.supabase import SupabaseDB, now_iso

log = logging.getLogger(__name__)

SCAN_MODULE = "backend.services.scheduler"


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


async def log_action(
    db: SupabaseDB,
    admin: dict,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Persist an admin mutation to audit_log. Never raises."""
    try:
        await db.insert(
            AUDIT_LOG,
            {
                "id": gen_uuid(),
                "admin_id": admin.get("id"),
                "admin_email": (admin.get("email") or "")[:255],
                "action": action[:100],
                "target_type": target_type[:50],
                "target_id": target_id,
                "details": details or {},
                "created_at": now_iso(),
            },
        )
    except Exception:
        log.exception("audit log write failed")


def user_view(u: dict) -> dict:
    return {
        "id": u.get("id"),
        "email": u.get("email"),
        "username": u.get("username"),
        "tier": u.get("tier"),
        "is_admin": bool(u.get("is_admin")),
        "is_active": bool(u.get("is_active")),
        "telegram_chat_id": u.get("telegram_chat_id"),
        "created_at": u.get("created_at"),
    }


def signal_view(s: dict) -> dict:
    return {
        "id": s.get("id"),
        "symbol": s.get("symbol"),
        "market": s.get("market"),
        "direction": s.get("direction"),
        "confidence": s.get("confidence"),
        "status": s.get("status"),
        "tier_required": s.get("tier_required"),
        "strategy": s.get("strategy"),
        "user_id": s.get("user_id"),
        "created_at": s.get("created_at"),
        "expires_at": s.get("expires_at"),
    }


async def list_users(
    db: SupabaseDB,
    search: str | None = None,
    tier: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    where = {"tier": tier} if tier else None
    # Small platform scale: pull recent users and filter/paginate in Python
    # so we can search across email OR username with one call.
    rows = await db.fetch_all(USERS, where=where, order="created_at.desc", limit=1000)
    if search:
        s = search.strip().lower()
        rows = [
            r for r in rows
            if s in (r.get("email") or "").lower() or s in (r.get("username") or "").lower()
        ]
    return [user_view(r) for r in rows[offset:offset + limit]]


def _integration_flags() -> dict:
    return {
        "trading_enabled": _flag(os.getenv("TRADING_ENABLED", "false")),
        "telegram_free_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN_FREE")),
        "telegram_premium_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN_PREMIUM")),
        "telegram_vip_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN_VIP")),
        "smtp_configured": bool(os.getenv("SMTP_HOST") or os.getenv("SENDER_EMAIL")),
    }


async def system_status(db: SupabaseDB) -> dict:
    from backend.services.scheduler import get_last_scan

    scan = get_last_scan() or {}
    return {
        "scheduler": {
            "enabled": _flag(os.getenv("SCAN_ENABLED", "1")),
            "interval_minutes": float(os.getenv("SCAN_INTERVAL_MINUTES", "15")),
            "cooldown_hours": int(os.getenv("SCAN_COOLDOWN_HOURS", "4")),
        },
        "last_scan": scan,
        "integrations": _integration_flags(),
        "supabase_reachable": await db.ping(),
    }


async def list_subscriptions(
    db: SupabaseDB,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    where = {"status": status} if status else None
    rows = await db.fetch_all(SUBSCRIPTIONS, where=where, order="started_at.desc", limit=min(limit, 200))
    user_ids = {r["user_id"] for r in rows}
    email_map: dict[str, str] = {}
    if user_ids:
        users = await db.fetch_all(USERS, where={"id": list(user_ids)}, columns="id,email")
        email_map = {u["id"]: (u.get("email") or "") for u in users}
    return [
        {
            "id": r.get("id"),
            "user_id": r.get("user_id"),
            "user_email": email_map.get(r.get("user_id")),
            "tier": r.get("tier"),
            "status": r.get("status"),
            "auto_renew": bool(r.get("auto_renew")),
            "started_at": r.get("started_at"),
            "expires_at": r.get("expires_at"),
        }
        for r in rows
    ]


async def list_signals(
    db: SupabaseDB,
    market: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict]:
    where: dict[str, object] = {}
    if market:
        where["market"] = market
    if status:
        where["status"] = status
    rows = await db.fetch_all(SIGNALS, where=where, order="created_at.desc", limit=min(limit, 200))
    return [signal_view(r) for r in rows]


async def invalidate_signal(db: SupabaseDB, signal_id: str) -> dict | None:
    updated = await db.update(SIGNALS, {"status": "cancelled"}, {"id": signal_id})
    return updated[0] if updated else None


async def list_audit(db: SupabaseDB, limit: int = 50) -> list[dict]:
    return await db.fetch_all(AUDIT_LOG, order="created_at.desc", limit=min(limit, 200))