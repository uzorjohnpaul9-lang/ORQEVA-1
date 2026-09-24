"""Per-user notification preferences (Phase 13)."""

from backend.db.models import USERS, USER_PREFERENCES, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso

EDITABLE = {
    "telegram_signals", "telegram_tp_sl", "telegram_market_analysis",
    "telegram_risk_alerts", "telegram_system_alerts",
    "email_notifications", "web_notifications",
    "default_market", "risk_tolerance", "theme",
}

_DEFAULTS = {
    "telegram_signals": True,
    "telegram_tp_sl": True,
    "telegram_market_analysis": False,
    "telegram_risk_alerts": True,
    "telegram_system_alerts": True,
    "email_notifications": False,
    "web_notifications": True,
    "default_market": "all",
    "risk_tolerance": "moderate",
    "theme": "dark",
}


async def get_or_create(db: SupabaseDB, user_id: str) -> dict:
    prefs = await db.fetch_one(USER_PREFERENCES, {"user_id": user_id})
    if prefs is None:
        row = {"id": gen_uuid(), "user_id": user_id, **_DEFAULTS}
        try:
            prefs = await db.insert(USER_PREFERENCES, row)
        except Exception:
            prefs = await db.fetch_one(USER_PREFERENCES, {"user_id": user_id}) or row
    for k, v in _DEFAULTS.items():
        prefs.setdefault(k, v)
    return prefs


def view(p: dict) -> dict:
    return {k: p.get(k, v) for k, v in _DEFAULTS.items()}


async def update(db: SupabaseDB, user_id: str, changes: dict) -> dict:
    prefs = await get_or_create(db, user_id)
    allowed = {k: v for k, v in changes.items() if k in EDITABLE and v is not None}
    if prefs.get("id") and allowed:
        await db.update(USER_PREFERENCES, allowed, where={"user_id": user_id})
    prefs.update(allowed)
    return prefs


async def link_telegram(db: SupabaseDB, user: dict, chat_id: str) -> dict:
    await db.update(USERS, {"telegram_chat_id": chat_id.strip()[:50], "updated_at": now_iso()}, where={"id": user["id"]})
    user["telegram_chat_id"] = chat_id.strip()[:50]
    return user


async def unlink_telegram(db: SupabaseDB, user: dict) -> dict:
    await db.update(USERS, {"telegram_chat_id": None, "updated_at": now_iso()}, where={"id": user["id"]})
    user["telegram_chat_id"] = None
    return user