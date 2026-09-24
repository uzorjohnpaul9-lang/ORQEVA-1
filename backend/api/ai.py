from fastapi import APIRouter, Depends, Query

from backend.db.database import get_db
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user
from backend.services import ai_service
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/ai", tags=["ai"])

VALID_MARKETS = {"stock", "forex", "crypto", "commodity"}


@router.get("/models")
async def models(user: dict = Depends(get_current_user)):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return {"models": ai_service.MODEL_ROSTER}


@router.get("/analysis")
async def analysis(
    symbol: str = Query(..., min_length=1, max_length=20),
    market: str = Query("stock"),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    if market not in VALID_MARKETS:
        return {"error": "invalid_market"}
    return await ai_service.analyze(market, symbol)


@router.get("/summary")
async def summary(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await ai_service.market_summary()