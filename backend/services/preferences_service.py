"""Per-user notification preferences (Phase 13)."""

from backend.db.models import USERS, USER_PREFERENCES, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso

EDITABLE = {
    "telegram_signals", "telegram_tp_sl", "telegram_market_analysis",
    "telegram_risk_alerts", "telegram_system_alerts",
    "email_notifications", "web_notifications",
    "default_market", "risk_tolerance", "theme",
    # Phase C: signal filters + digest
    "watchlist", "directions", "min_confidence", "telegram_weekly_digest",
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
    "watchlist": [],
    "directions": [],
    "min_confidence": 0.0,
    "telegram_weekly_digest": False,
}

MAX_WATCHLIST = 50
VALID_DIRECTIONS = {"buy", "sell"}


def _norm_watchlist(value) -> list[str]:
    """Uppercase, de-duplicate, drop blanks, cap size. Accepts list or CSV string."""
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple, set)):
        return []
    seen: list[str] = []
    for item in value:
        sym = str(item).strip().upper()[:20]
        if sym and sym not in seen:
            seen.append(sym)
    return seen[:MAX_WATCHLIST]


def _norm_directions(value) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, (list, tuple, set)):
        return []
    out: list[str] = []
    for item in value:
        d = str(item).strip().lower()
        if d in VALID_DIRECTIONS and d not in out:
            out.append(d)
    return out


def _norm_min_confidence(value) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(1.0, max(0.0, conf)), 3)


def _sanitize(changes: dict) -> dict:
    """Coerce filter fields into their canonical storage form."""
    out = dict(changes)
    if "watchlist" in out:
        out["watchlist"] = _norm_watchlist(out["watchlist"])
    if "directions" in out:
        out["directions"] = _norm_directions(out["directions"])
    if "min_confidence" in out:
        out["min_confidence"] = _norm_min_confidence(out["min_confidence"])
    return out


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
    allowed = _sanitize({k: v for k, v in changes.items() if k in EDITABLE and v is not None})
    if prefs.get("id") and allowed:
        await db.update(USER_PREFERENCES, allowed, where={"user_id": user_id})
    prefs.update(allowed)
    return prefs


def matches_filters(prefs: dict, signal: dict) -> bool:
    """True when a signal passes a user's watchlist/direction/confidence filters.

    Empty watchlist or directions means "no restriction". A missing signal
    direction/confidence does not disqualify the signal.
    """
    watchlist = prefs.get("watchlist") or []
    if watchlist:
        allowed = {str(w).upper() for w in watchlist}
        if str(signal.get("symbol") or "").upper() not in allowed:
            return False

    directions = prefs.get("directions") or []
    if directions:
        allowed_dirs = {str(d).lower() for d in directions}
        if str(signal.get("direction") or "").lower() not in allowed_dirs:
            return False

    try:
        min_conf = float(prefs.get("min_confidence") or 0)
    except (TypeError, ValueError):
        min_conf = 0.0
    if min_conf > 0:
        try:
            if float(signal.get("confidence")) < min_conf:
                return False
        except (TypeError, ValueError):
            pass
    return True


async def link_telegram(db: SupabaseDB, user: dict, chat_id: str) -> dict:
    await db.update(USERS, {"telegram_chat_id": chat_id.strip()[:50], "updated_at": now_iso()}, where={"id": user["id"]})
    user["telegram_chat_id"] = chat_id.strip()[:50]
    return user


async def unlink_telegram(db: SupabaseDB, user: dict) -> dict:
    await db.update(USERS, {"telegram_chat_id": None, "updated_at": now_iso()}, where={"id": user["id"]})
    user["telegram_chat_id"] = None
    return user