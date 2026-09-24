import asyncio

from fastapi import APIRouter, Depends, Query

from backend.db.database import get_db
from backend.db.schemas import TradeResponse
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user
from backend.services import trade_service, market_service
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

QUOTE_TIMEOUT_S = 10.0


async def _quote_price(market: str, symbol: str) -> float | None:
    """Live price via market_service; degrades to None on slow/failed providers."""
    try:
        q = await asyncio.wait_for(
            asyncio.to_thread(market_service.get_quote, market, symbol),
            timeout=QUOTE_TIMEOUT_S,
        )
        return q.get("price") if isinstance(q, dict) else None
    except Exception:
        return None


@router.get("/trades", response_model=list[TradeResponse])
async def list_trades(
    status: str | None = Query(None),
    market: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    trades = await trade_service.list_trades(db, user["id"], market=market, status=status, limit=limit)
    return [TradeResponse.model_validate(t) for t in trades]


@router.get("/summary")
async def portfolio_summary(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await trade_service.get_portfolio_summary(db, user["id"])


@router.get("/positions")
async def open_positions(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Open trades enriched with live price + unrealized P&L."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    trades = await trade_service.list_trades(db, user["id"], status="open", limit=200)

    # Live quotes for unique (market, symbol) pairs
    unique = sorted({(t["market"], t["symbol"]) for t in trades})
    prices: dict[tuple[str, str], float | None] = {}
    if unique:
        values = await asyncio.gather(*[_quote_price(m, s) for m, s in unique])
        prices = dict(zip(unique, values))

    out = []
    for t in trades:
        d = TradeResponse.model_validate(t).model_dump(mode="json")
        p = prices.get((t["market"], t["symbol"]))
        d["current_price"] = p
        if p is not None:
            direction = 1 if t["side"] == "buy" else -1
            d["unrealized_pnl"] = round((p - t["entry_price"]) * t["quantity"] * direction, 2)
        else:
            d["unrealized_pnl"] = None
        out.append(d)
    return out


@router.get("/holdings")
async def holdings(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Per-symbol aggregation of open positions with live valuation."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    rows = await trade_service.get_holdings(db, user["id"])

    unique = sorted({(h["market"], h["symbol"]) for h in rows})
    prices: dict[tuple[str, str], float | None] = {}
    if unique:
        values = await asyncio.gather(*[_quote_price(m, s) for m, s in unique])
        prices = dict(zip(unique, values))

    out = []
    for h in rows:
        p = prices.get((h["market"], h["symbol"]))
        h["current_price"] = p
        if p is not None:
            direction = 1 if h["quantity"] >= 0 else -1
            qty = abs(h["quantity"])
            h["market_value"] = round(p * qty, 2)
            h["unrealized_pnl"] = round((p - h["avg_entry_price"]) * qty * direction, 2)
        else:
            h["market_value"] = None
            h["unrealized_pnl"] = None
        out.append(h)
    return out


@router.get("/performance")
async def performance(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await trade_service.get_performance(db, user["id"])