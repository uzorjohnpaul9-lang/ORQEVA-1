"""Phase K: metered signal API keys.

Raw keys are shown exactly once at creation; only a SHA-256 hash is stored.
Each request is metered against a per-tier daily quota so the public `/v1`
signal API can be offered as a paid, rate-limited product.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timezone

from backend.db.models import API_KEYS, USERS, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso

logger = logging.getLogger(__name__)

KEY_PREFIX = "orq_"
FREE_DAILY_QUOTA = 200
PAID_DAILY_QUOTA = 20000

_QUOTA = {"free": FREE_DAILY_QUOTA, "premium": PAID_DAILY_QUOTA, "vip": PAID_DAILY_QUOTA}


def hash_key(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def daily_quota(tier: str | None) -> int:
    return _QUOTA.get((tier or "free").lower(), FREE_DAILY_QUOTA)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _used_today(row: dict) -> int:
    """Daily counter, reset lazily when the stored usage_day rolls over."""
    if row.get("usage_day") != _today():
        return 0
    return int(row.get("requests_today") or 0)


def key_view(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "prefix": row.get("key_prefix"),
        "created_at": row.get("created_at"),
        "last_used_at": row.get("last_used_at"),
        "revoked": bool(row.get("revoked_at")),
        "requests_today": _used_today(row),
        "requests_total": int(row.get("requests_total") or 0),
    }


async def create_key(db: SupabaseDB, user_id: str, name: str | None = None) -> dict:
    raw = KEY_PREFIX + secrets.token_urlsafe(24)
    row = {
        "id": gen_uuid(),
        "user_id": user_id,
        "name": (name or "default").strip()[:60] or "default",
        "key_hash": hash_key(raw),
        "key_prefix": raw[:12],
        "created_at": now_iso(),
        "last_used_at": None,
        "revoked_at": None,
        "usage_day": _today(),
        "requests_today": 0,
        "requests_total": 0,
    }
    created = await db.insert(API_KEYS, row)
    return {"key": raw, **key_view(created)}


async def list_keys(db: SupabaseDB, user_id: str) -> list[dict]:
    rows = await db.fetch_all(API_KEYS, where={"user_id": user_id}, order="created_at.desc")
    return [key_view(r) for r in rows]


async def revoke_key(db: SupabaseDB, user_id: str, key_id: str) -> bool:
    rows = await db.update(
        API_KEYS, {"revoked_at": now_iso()}, where={"id": key_id, "user_id": user_id}
    )
    return bool(rows)


async def authenticate(db: SupabaseDB, raw_key: str | None) -> dict | None:
    """Resolve a raw key to {"user", "key", "used", "quota"}.

    Returns None when the key is unknown, revoked or the owner is inactive, and
    {"error": "quota_exceeded", ...} once the daily quota is spent.
    """
    if not raw_key or not raw_key.startswith(KEY_PREFIX):
        return None
    row = await db.fetch_one(API_KEYS, {"key_hash": hash_key(raw_key)})
    if not row or row.get("revoked_at"):
        return None
    user = await db.fetch_one(USERS, {"id": row.get("user_id")})
    if not user or not user.get("is_active"):
        return None
    quota = daily_quota(user.get("tier"))
    used = _used_today(row)
    if used >= quota:
        return {"error": "quota_exceeded", "user": user, "key": row, "used": used, "quota": quota}
    return {"user": user, "key": row, "used": used, "quota": quota}


async def record_usage(db: SupabaseDB, key: dict) -> None:
    used = _used_today(key)
    await db.update(
        API_KEYS,
        {
            "usage_day": _today(),
            "requests_today": used + 1,
            "requests_total": int(key.get("requests_total") or 0) + 1,
            "last_used_at": now_iso(),
        },
        where={"id": key["id"]},
    )
