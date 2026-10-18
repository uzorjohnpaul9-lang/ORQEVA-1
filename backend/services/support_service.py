"""Support tickets (Phase F).

A support ticket can be opened by a signed-in user or from the login page
(no account). Admins work the queue and reply; the submitter sees the reply
on their own ticket. Nothing here mutates user data -- the admin "context"
view (see :mod:`backend.services.admin_service`) is strictly read-only.
"""
import logging

from backend.db.models import SUPPORT_TICKETS, USERS, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso

log = logging.getLogger(__name__)

CATEGORIES = ("general", "billing", "technical", "account", "other")
STATUSES = ("open", "in_progress", "resolved", "closed")
PRIORITIES = ("low", "normal", "high")
OPEN_STATUSES = ("open", "in_progress")

SUBJECT_MAX = 200
MESSAGE_MAX = 4000


def _clean(value: str | None, allowed: tuple[str, ...], default: str) -> str:
    v = (value or "").strip().lower()
    return v if v in allowed else default


def view(t: dict) -> dict:
    """Submitter-facing shape (no internal/admin fields)."""
    return {
        "id": t.get("id"),
        "subject": t.get("subject"),
        "message": t.get("message"),
        "category": t.get("category"),
        "status": t.get("status"),
        "reply": t.get("reply"),
        "replied_at": t.get("replied_at"),
        "created_at": t.get("created_at"),
        "updated_at": t.get("updated_at"),
    }


def admin_view(t: dict, user_email: str | None = None) -> dict:
    return {
        **view(t),
        "user_id": t.get("user_id"),
        "email": t.get("email"),
        "user_email": user_email,
        "priority": t.get("priority"),
        "source": t.get("source"),
        "assigned_to": t.get("assigned_to"),
        "replied_by": t.get("replied_by"),
    }


async def create_ticket(
    db: SupabaseDB,
    *,
    subject: str,
    message: str,
    email: str,
    category: str = "general",
    user_id: str | None = None,
    source: str = "app",
) -> dict:
    row = {
        "id": gen_uuid(),
        "user_id": user_id,
        "email": (email or "").strip().lower()[:255],
        "subject": subject.strip()[:SUBJECT_MAX],
        "message": message.strip()[:MESSAGE_MAX],
        "category": _clean(category, CATEGORIES, "general"),
        "status": "open",
        "priority": "normal",
        "source": source if source in ("app", "login") else "app",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    created = await db.insert(SUPPORT_TICKETS, row)
    return view(created or row)


async def list_for_user(db: SupabaseDB, user_id: str, limit: int = 50) -> list[dict]:
    rows = await db.fetch_all(
        SUPPORT_TICKETS, where={"user_id": user_id}, order="created_at.desc", limit=min(limit, 200)
    )
    return [view(r) for r in rows]


async def get_for_user(db: SupabaseDB, ticket_id: str, user_id: str) -> dict | None:
    row = await db.fetch_one(SUPPORT_TICKETS, {"id": ticket_id, "user_id": user_id})
    return view(row) if row else None


async def list_all(db: SupabaseDB, status: str | None = None, limit: int = 100) -> list[dict]:
    where = {"status": status} if status in STATUSES else None
    rows = await db.fetch_all(
        SUPPORT_TICKETS, where=where, order="created_at.desc", limit=min(limit, 200)
    )
    # Resolve the account email where the ticket's contact email is missing.
    missing = {r["user_id"] for r in rows if r.get("user_id") and not r.get("email")}
    email_map: dict[str, str] = {}
    if missing:
        users = await db.fetch_all(USERS, where={"id": list(missing)}, columns="id,email")
        email_map = {u["id"]: (u.get("email") or "") for u in users}
    return [
        admin_view(r, user_email=r.get("email") or email_map.get(r.get("user_id")))
        for r in rows
    ]


async def get_ticket(db: SupabaseDB, ticket_id: str) -> dict | None:
    row = await db.fetch_one(SUPPORT_TICKETS, {"id": ticket_id})
    return admin_view(row) if row else None


async def reply(
    db: SupabaseDB,
    admin: dict,
    ticket_id: str,
    message: str,
    status: str | None = None,
    priority: str | None = None,
) -> dict | None:
    updates: dict = {
        "reply": message.strip()[:MESSAGE_MAX],
        "replied_by": admin.get("id"),
        "replied_at": now_iso(),
        "updated_at": now_iso(),
        "status": _clean(status, STATUSES, "in_progress"),
    }
    if priority in PRIORITIES:
        updates["priority"] = priority
    rows = await db.update(SUPPORT_TICKETS, updates, {"id": ticket_id})
    return admin_view(rows[0]) if rows else None


async def set_status(
    db: SupabaseDB,
    admin: dict,
    ticket_id: str,
    status: str,
    priority: str | None = None,
) -> dict | None:
    updates: dict = {"updated_at": now_iso()}
    if status in STATUSES:
        updates["status"] = status
    if priority in PRIORITIES:
        updates["priority"] = priority
    rows = await db.update(SUPPORT_TICKETS, updates, {"id": ticket_id})
    return admin_view(rows[0]) if rows else None


async def stats(db: SupabaseDB) -> dict:
    return {
        "open": await db.count(SUPPORT_TICKETS, where={"status": "open"}),
        "in_progress": await db.count(SUPPORT_TICKETS, where={"status": "in_progress"}),
        "total": await db.count(SUPPORT_TICKETS),
    }
