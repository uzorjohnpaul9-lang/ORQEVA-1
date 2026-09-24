from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user
from backend.services import notification_service as notif_service
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    type: str | None = None,
    limit: int = 50,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    rows = await notif_service.list_for(db, user["id"], unread_only=unread_only, ntype=type, limit=limit)
    return {
        "notifications": [notif_service.view(n) for n in rows],
        "unread_count": await notif_service.unread_count(db, user["id"]),
    }


@router.get("/unread-count")
async def unread(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return {"count": await notif_service.unread_count(db, user["id"])}


class MarkReadBody(BaseModel):
    notification_id: str = Field(min_length=8)


@router.post("/read")
async def mark_read(
    body: MarkReadBody,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    ok = await notif_service.mark_read(db, user["id"], body.notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="notification not found")
    return {"status": "read"}


@router.post("/read-all")
async def mark_all_read(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return {"marked": await notif_service.mark_all_read(db, user["id"])}


@router.delete("/read")
async def clear_read(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return {"cleared": await notif_service.clear_read(db, user["id"])}