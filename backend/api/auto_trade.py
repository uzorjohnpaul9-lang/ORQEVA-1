from fastapi import APIRouter, Depends, Query

from backend.db.database import get_db
from backend.db.models import AUTO_TRADE_LOG
from backend.db.supabase import SupabaseDB
from backend.db.schemas import AutoTradeSettings, AutoTradeLogResponse
from backend.auth import get_current_user
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import auto_trade_service

router = APIRouter(prefix="/api/auto-trade", tags=["auto-trade"])


@router.get("/settings")
async def get_settings(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    settings = await auto_trade_service.get_or_create_settings(db, user["id"])
    return auto_trade_service._view_settings(settings)


@router.put("/settings", response_model=AutoTradeSettings)
async def put_settings(
    body: AutoTradeSettings,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    updated = await auto_trade_service.update_settings(db, user["id"], body)
    return auto_trade_service._view_settings(updated)


@router.get("/log")
async def get_log(
    limit: int = Query(50, ge=1, le=200),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    rows = await db.fetch_all(
        AUTO_TRADE_LOG,
        where={"user_id": user["id"]},
        order="created_at.desc",
        limit=limit,
    )
    return {"entries": [AutoTradeLogResponse(**row).model_dump() for row in rows]} if rows else {"entries": []}