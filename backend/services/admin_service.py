"""Admin operations + audit logging for the /admin space.

Every mutating admin endpoint calls :func:`log_action`, so the operator has a
"who did what" trail. Config values returned to the UI are booleans only --
never secrets.
"""
import logging
import os

from backend.db.models import (
    AUDIT_LOG,
    EXCHANGE_CONNECTIONS,
    NOTIFICATIONS,
    RISK_SETTINGS,
    SIGNALS,
    SUBSCRIPTIONS,
    SUPPORT_TICKETS,
    TRADES,
    USER_PREFERENCES,
    USERS,
    gen_uuid,
)
from backend.db.supabase import SupabaseDB, now_iso

log = logging.getLogger(__name__)

SCAN_MODULE = "backend.services.scheduler"


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _mask(value: str | None) -> str:
    """Last 4 chars only (enough to verify config without leaking the value)."""
    v = (value or "").strip()
    return f"...{v[-4:]}" if len(v) >= 4 else ("set" if v else "")


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
        "telegram_channel_free": _mask(os.getenv("TELEGRAM_CHANNEL_FREE")),
        "telegram_channel_premium": _mask(os.getenv("TELEGRAM_CHANNEL_PREMIUM")),
        "telegram_channel_vip": _mask(os.getenv("TELEGRAM_CHANNEL_VIP")),
        "smtp_configured": bool(os.getenv("SMTP_HOST") or os.getenv("SENDER_EMAIL")),
    }


async def system_status(db: SupabaseDB) -> dict:
    from backend.services.scheduler import get_last_scan

    from backend.services import telegram_service

    scan = get_last_scan() or {}
    return {
        "commit": (os.getenv("RAILWAY_GIT_COMMIT_SHA") or "")[:7],
        "last_channel_fanout": telegram_service.last_channel_fanout(),
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


# ---- Account termination ------------------------------------------------

def anonymized_identity(user_id: str) -> dict:
    """Replacement email/username for a deactivated+anonymized account."""
    short = (user_id or "").replace("-", "")[:12] or "user"
    return {"email": f"deleted+{short}@orqeva.invalid", "username": f"deleted_{short}"}


async def is_last_admin(db: SupabaseDB, target: dict) -> bool:
    """True when deactivating/deleting ``target`` would remove the last admin."""
    if not target.get("is_admin"):
        return False
    return await db.count(USERS, where={"is_admin": True}) <= 1


# ---- Read-only user context (Phase F) -----------------------------------

_PREF_FIELDS = (
    "risk_tolerance",
    "max_drawdown_pct",
    "auto_manage",
    "notifications_enabled",
    "email_alerts",
    "push_alerts",
    "telegram_linked",
    "watchlist",
    "directions",
    "min_confidence",
    "telegram_weekly_digest",
    "demo_starting_balance",
)


def _trade_view(t: dict) -> dict:
    return {
        "id": t.get("id"),
        "symbol": t.get("symbol"),
        "market": t.get("market"),
        "side": t.get("side"),
        "quantity": t.get("quantity"),
        "entry_price": t.get("entry_price"),
        "exit_price": t.get("exit_price"),
        "status": t.get("status"),
        "pnl": t.get("pnl"),
        "is_demo": bool(t.get("is_demo")),
        "opened_at": t.get("opened_at"),
        "closed_at": t.get("closed_at"),
    }


async def user_context(db: SupabaseDB, user_id: str) -> dict | None:
    """A strictly read-only snapshot for admin support work.

    Never returns credentials: exchange connections are reduced to metadata
    (the encrypted key columns are dropped), and no mutating path exists here.
    """
    user = await db.fetch_one(USERS, {"id": user_id})
    if not user:
        return None

    prefs = await db.fetch_one(USER_PREFERENCES, {"user_id": user_id})
    risk = await db.fetch_one(RISK_SETTINGS, {"user_id": user_id})
    recent = await db.fetch_all(
        TRADES, where={"user_id": user_id}, order="opened_at.desc", limit=25
    )
    closed = await db.fetch_all(
        TRADES, where={"user_id": user_id, "status": "closed"}, columns="pnl", limit=1000
    )
    connections = await db.fetch_all(
        EXCHANGE_CONNECTIONS,
        where={"user_id": user_id},
        order="created_at.desc",
        columns="id,exchange,status,permissions,created_at",
        limit=20,
    )
    subs = await db.fetch_all(
        SUBSCRIPTIONS, where={"user_id": user_id}, order="started_at.desc", limit=5
    )
    tickets = await db.fetch_all(
        SUPPORT_TICKETS, where={"user_id": user_id}, order="created_at.desc", limit=5
    )
    unread = await db.count(NOTIFICATIONS, where={"user_id": user_id, "is_read": False})

    realized = round(sum(float(t.get("pnl") or 0) for t in closed), 2)
    return {
        "profile": user_view(user),
        "preferences": {f: (prefs or {}).get(f) for f in _PREF_FIELDS} if prefs else None,
        "risk": {
            "daily_loss_limit": (risk or {}).get("daily_loss_limit"),
            "daily_trade_limit": (risk or {}).get("daily_trade_limit"),
            "max_position_pct": (risk or {}).get("max_position_pct"),
            "kill_switch_break_only": (risk or {}).get("kill_switch_break_only"),
        } if risk else None,
        "activity": {
            "open_positions": await db.count(TRADES, where={"user_id": user_id, "status": "open"}),
            "closed_positions": len(closed),
            "realized_pnl": realized,
            "recent_trades": [_trade_view(t) for t in recent],
        },
        "exchanges": [
            {
                "id": c.get("id"),
                "exchange": c.get("exchange"),
                "status": c.get("status"),
                "permissions": c.get("permissions"),
                "created_at": c.get("created_at"),
            }
            for c in connections
        ],
        "subscriptions": [
            {
                "tier": s.get("tier"),
                "status": s.get("status"),
                "auto_renew": bool(s.get("auto_renew")),
                "started_at": s.get("started_at"),
                "expires_at": s.get("expires_at"),
            }
            for s in subs
        ],
        "support_tickets": [
            {
                "id": t.get("id"),
                "subject": t.get("subject"),
                "status": t.get("status"),
                "category": t.get("category"),
                "created_at": t.get("created_at"),
                "replied_at": t.get("replied_at"),
            }
            for t in tickets
        ],
        "notifications_unread": unread,
    }