from fastapi import APIRouter, Depends, Query
from backend.auth import get_current_user
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import market_service

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview")
async def market_overview(user: dict = Depends(get_current_user)):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return market_service.get_overview()


@router.get("/quotes")
async def market_quotes(
    symbols: str = Query(..., description="Comma-separated symbols"),
    market: str = Query("crypto", description="stock|forex|crypto|commodity (non-stock shares one market)"),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()][:20]
    quotes = [market_service.get_quote(market, s) for s in sym_list]
    return {"quotes": quotes}


@router.get("/movers")
async def market_movers(user: dict = Depends(get_current_user)):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return market_service.get_movers()


@router.get("/bars")
async def market_bars(
    symbol: str = Query(...),
    market: str = Query("crypto"),
    interval: str = Query("1day", description="5min|15min|30min|1h|1day|1week"),
    outputsize: int = Query(30, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return market_service.get_bars(market, symbol.upper(), interval, outputsize)


@router.get("/discovery")
async def crypto_discovery(
    top_n: int = Query(10, ge=1, le=25),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return market_service.get_discovery(top_n)