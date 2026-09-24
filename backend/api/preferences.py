from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user
from backend.db.schemas import PreferencesUpdate
from backend.services import preferences_service as prefs_service
from backend.services import telegram_service as telegram
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("")
async def get_preferences(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    prefs = await prefs_service.get_or_create(db, user["id"])
    return {
        **prefs_service.view(prefs),
        "telegram_chat_id": user.get("telegram_chat_id"),
        "telegram_linked": bool(user.get("telegram_chat_id")),
    }


@router.put("")
async def update_preferences(
    body: PreferencesUpdate,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    prefs = await prefs_service.update(db, user["id"], changes)
    return prefs_service.view(prefs)


# ---- Telegram linking ----

class TelegramLinkRequest(BaseModel):
    chat_id: str = Field(min_length=4, max_length=50)


@router.post("/telegram/link")
async def link_telegram(
    body: TelegramLinkRequest,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    user = await prefs_service.link_telegram(db, user, body.chat_id)
    # send a confirmation message right away so the user sees it works
    result = await telegram.send_test(user)
    return {"telegram_chat_id": user.get("telegram_chat_id"), "test": result}


@router.post("/telegram/test")
async def test_telegram(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await telegram.send_test(user)


@router.delete("/telegram/link")
async def unlink_telegram(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    user = await prefs_service.unlink_telegram(db, user)
    return {"telegram_chat_id": None, "telegram_linked": False}