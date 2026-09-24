"""In-app notification center (Phase 15)."""

from backend.db.models import NOTIFICATIONS, USER_PREFERENCES, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso


async def _web_enabled(db: SupabaseDB, user_id: str) -> bool:
    row = await db.fetch_one(USER_PREFERENCES, {"user_id": user_id}, columns="web_notifications")
    if row is None:
        return True
    return bool(row.get("web_notifications", True))


async def create(db: SupabaseDB, user_id: str, ntype: str, title: str, message: str,
                 respect_prefs: bool = True) -> dict | None:
    """Create an in-app notification. Never raises."""
    try:
        if respect_prefs and not await _web_enabled(db, user_id):
            return None
        row = {
            "id": gen_uuid(),
            "user_id": user_id,
            "type": ntype[:30],
            "title": title[:200],
            "message": message,
            "is_read": False,
            "channel": "in_app",
            "created_at": now_iso(),
        }
        return await db.insert(NOTIFICATIONS, row)
    except Exception:
        return None


def view(n: dict) -> dict:
    return {
        "id": n["id"],
        "type": n.get("type"),
        "title": n.get("title"),
        "message": n.get("message"),
        "is_read": bool(n.get("is_read")),
        "created_at": n.get("created_at"),
    }


async def list_for(db: SupabaseDB, user_id: str, unread_only: bool = False,
                   ntype: str | None = None, limit: int = 50) -> list[dict]:
    where: dict[str, object] = {"user_id": user_id}
    if unread_only:
        where["is_read"] = False
    if ntype:
        where["type"] = ntype[:30]
    return await db.fetch_all(NOTIFICATIONS, where=where, order="created_at.desc", limit=min(limit, 200))


async def unread_count(db: SupabaseDB, user_id: str) -> int:
    return await db.count(NOTIFICATIONS, where={"user_id": user_id, "is_read": False})


async def mark_read(db: SupabaseDB, user_id: str, notification_id: str) -> bool:
    rows = await db.update(
        NOTIFICATIONS,
        {"is_read": True},
        where={"id": notification_id, "user_id": user_id},
    )
    return len(rows) > 0


async def mark_all_read(db: SupabaseDB, user_id: str) -> int:
    rows = await db.fetch_all(NOTIFICATIONS, where={"user_id": user_id, "is_read": False}, columns="id")
    if not rows:
        return 0
    await db.update(NOTIFICATIONS, {"is_read": True}, where={"user_id": user_id, "is_read": False})
    return len(rows)


async def clear_read(db: SupabaseDB, user_id: str) -> int:
    rows = await db.fetch_all(NOTIFICATIONS, where={"user_id": user_id, "is_read": True}, columns="id")
    count = len(rows)
    if count:
        await db.delete(NOTIFICATIONS, where={"user_id": user_id, "is_read": True})
    return count