from fastapi import APIRouter, Depends, Query

from backend.db.database import get_db
from backend.db.models import NOTIFICATIONS, SIGNALS, TRADES
from backend.db.schemas import DashboardOverview
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user
from backend.middleware.rate_limiter import check_rate_limit
from backend.middleware.cache import cache
from backend.services import trade_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview(
    is_demo: bool | None = Query(None),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))

    cache_key = f"dashboard:{user['id']}:{is_demo}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    trade_where: dict = {"user_id": user["id"]}
    if is_demo is not None:
        trade_where["is_demo"] = bool(is_demo)

    total_signals = await db.count(SIGNALS)
    active_signals = await db.count(SIGNALS, where={"status": "active"})
    open_trades = await db.count(TRADES, where={**trade_where, "status": "open"})
    pnl_rows = await db.fetch_all(TRADES, where=trade_where, columns="pnl")
    total_pnl = sum(float(r.get("pnl") or 0) for r in pnl_rows)
    total_trades = len(pnl_rows)
    wins = sum(1 for r in pnl_rows if (r.get("pnl") or 0) > 0)
    starting = await trade_service.get_starting_balance(db, user["id"], bool(is_demo))

    result = DashboardOverview(
        total_signals=total_signals,
        active_signals=active_signals,
        open_trades=open_trades,
        total_pnl=round(total_pnl, 2),
        win_rate=round((wins / total_trades * 100) if total_trades > 0 else 0.0, 1),
        portfolio_value=round(starting + total_pnl, 2),
    )
    cache.set(cache_key, result, ttl=15)
    return result


@router.get("/notifications")
async def list_notifications(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    rows = await db.fetch_all(
        NOTIFICATIONS,
        where={"user_id": user["id"]},
        order="created_at.desc",
        limit=20,
    )
    return [
        {
            "id": n.get("id"),
            "type": n.get("type"),
            "title": n.get("title"),
            "message": n.get("message"),
            "is_read": n.get("is_read"),
            "created_at": n.get("created_at"),
        }
        for n in rows
    ]