"""User presence: last-seen tracking and the online window.

"Online" is intentionally not the same thing as ``is_active`` (account
enabled/disabled). Any authenticated request refreshes ``users.last_seen_at``,
throttled per process so a chatty client cannot turn presence into a write
storm. Presence failures are swallowed: they must never break authentication.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from backend.db.models import USERS
from backend.db.supabase import SupabaseDB, now_iso, parse_dt

log = logging.getLogger(__name__)

ONLINE_WINDOW_SECONDS = int(os.getenv("PRESENCE_ONLINE_WINDOW_SECONDS", "120"))
TOUCH_INTERVAL_SECONDS = int(os.getenv("PRESENCE_TOUCH_INTERVAL_SECONDS", "60"))

_last_touch: dict[str, float] = {}


def online_cutoff(now: datetime | None = None) -> datetime:
    """Earliest last_seen_at that still counts as online."""
    base = now or datetime.now(timezone.utc)
    return base - timedelta(seconds=ONLINE_WINDOW_SECONDS)


def online_cutoff_iso(now: datetime | None = None) -> str:
    return online_cutoff(now).isoformat().replace("+00:00", "Z")


def is_online(last_seen_at, now: datetime | None = None) -> bool:
    seen = parse_dt(last_seen_at)
    if seen is None:
        return False
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return seen >= online_cutoff(now)


def _prune(mono_now: float) -> None:
    expired = [uid for uid, ts in _last_touch.items() if mono_now - ts >= TOUCH_INTERVAL_SECONDS]
    for uid in expired:
        _last_touch.pop(uid, None)


async def touch(db: SupabaseDB, user_id: str) -> bool:
    """Refresh last_seen_at, at most once per TOUCH_INTERVAL_SECONDS/user.

    Returns True when a write was attempted. Never raises.
    """
    if not user_id:
        return False
    mono_now = time.monotonic()
    previous = _last_touch.get(user_id)
    if previous is not None and mono_now - previous < TOUCH_INTERVAL_SECONDS:
        return False
    _last_touch[user_id] = mono_now
    if len(_last_touch) > 10_000:
        _prune(mono_now)
    try:
        await db.update(USERS, {"last_seen_at": now_iso()}, {"id": user_id})
        return True
    except Exception as e:  # presence must never break authentication
        log.debug("presence touch failed for %s: %s", user_id, e)
        return False
