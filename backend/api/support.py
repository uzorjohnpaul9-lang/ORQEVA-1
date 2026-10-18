"""Support channel (Phase F).

Public: anyone (signed in or from the login page) can open a ticket.
Signed in: users can also read their own tickets and replies.
"""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.auth import get_current_user, get_optional_user
from backend.config import settings
from backend.db.supabase import SupabaseDB
from backend.db.database import get_db
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import notification_service, support_service

log = logging.getLogger("support")

router = APIRouter(prefix="/api/support", tags=["support"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=support_service.SUBJECT_MAX)
    message: str = Field(min_length=5, max_length=support_service.MESSAGE_MAX)
    category: str = Field(default="general", max_length=20)
    # Required only for the login-page (anonymous) channel.
    email: str | None = Field(default=None, max_length=255)


async def _announce(db: SupabaseDB, ticket: dict, user: dict | None) -> None:
    """Best-effort: notify the submitter in-app and ping the support inbox."""
    try:
        if user:
            await notification_service.create(
                db, user["id"], "system", "Support request received",
                f"We got your request \"{ticket['subject']}\" and will reply soon.",
            )
    except Exception:
        log.exception("support: in-app notify failed")

    if settings.SUPPORT_EMAIL:
        try:
            from backend.services import email_service

            html = (
                f"<p><b>{ticket['subject']}</b> ({ticket['category']})</p>"
                f"<p>From: {ticket['email']}</p>"
                f"<p>{ticket['message']}</p>"
            )
            await email_service.send_email(settings.SUPPORT_EMAIL, f"[Support] {ticket['subject']}", html)
        except Exception:
            log.error("support email notify failed", exc_info=True)


@router.post("", status_code=201)
async def create_ticket(
    body: TicketCreate,
    request: Request,
    db: SupabaseDB = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    if user:
        check_rate_limit(user["id"], user.get("tier", "free"))
        email = user.get("email") or ""
        source = "app"
    else:
        ip = request.client.host if request.client else "unknown"
        check_rate_limit(f"anon:{ip}", "free")
        email = (body.email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            raise HTTPException(status_code=400, detail="A valid email is required")
        source = "login"

    ticket = await support_service.create_ticket(
        db,
        subject=body.subject,
        message=body.message,
        email=email,
        category=body.category,
        user_id=user["id"] if user else None,
        source=source,
    )
    await _announce(db, ticket, user)
    return ticket


@router.get("")
async def my_tickets(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return {"tickets": await support_service.list_for_user(db, user["id"])}


@router.get("/{ticket_id}")
async def get_my_ticket(
    ticket_id: str,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    ticket = await support_service.get_for_user(db, ticket_id, user["id"])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket
