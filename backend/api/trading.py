import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.db.database import get_db
from backend.db.models import EXCHANGE_CONNECTIONS, IDEMPOTENCY_RECORDS, TRADES, gen_uuid
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user
from backend.services import trade_service, market_service, analytics_service, risk_service, telegram_service
from backend.exchanges import get_adapter
from backend.services import notification_service as notif_service
from backend.api.risk import central
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/trading", tags=["trading"])


class OrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    market: str = Field(pattern="^(stock|forex|crypto|commodity)$")
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    entry_price: float | None = Field(default=None, gt=0)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    limit_price: float | None = Field(default=None, gt=0)
    route: str = Field(default="paper", pattern="^(paper|live)$")
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, max_length=64)


class CloseRequest(BaseModel):
    exit_price: float | None = Field(default=None, gt=0)


async def _live_price(market: str, symbol: str) -> float | None:
    """Fetch live price off the event loop; None on failure/timeout."""
    def fetch(m: str, s: str) -> float | None:
        q = market_service.get_quote(m, s)
        return q.get("price") if isinstance(q, dict) else None

    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch, market, symbol), timeout=10.0)
    except Exception:
        return None


async def _active_connection(db: SupabaseDB, user_id: str, market: str) -> dict | None:
    """Newest active connection whose adapter serves this market, or None."""
    conns = await db.fetch_all(
        EXCHANGE_CONNECTIONS,
        where={"user_id": user_id, "is_active": True},
        order="connected_at.desc",
    )
    for conn in conns:
        adapter = get_adapter(conn.get("exchange"))
        if adapter and market in adapter.markets:
            return conn
    return None


def _creds(conn: dict) -> tuple[str, str]:
    from backend.api.exchanges import security
    api_key = security.decrypt_data(conn["api_key_encrypted"])
    api_secret = security.decrypt_data(conn["api_secret_encrypted"]) if conn.get("api_secret_encrypted") else ""
    return api_key, api_secret


async def _idempotency_replay(db: SupabaseDB, user_id: str, key: str) -> dict | None:
    rec = await db.fetch_one(
        IDEMPOTENCY_RECORDS,
        {"user_id": user_id, "endpoint": "orders", "key": key},
    )
    return json.loads(rec.get("response_json")) if rec else None


async def _idempotency_store(db: SupabaseDB, user_id: str, key: str, response: dict) -> None:
    try:
        await db.insert(IDEMPOTENCY_RECORDS, {
            "id": gen_uuid(),
            "user_id": user_id,
            "endpoint": "orders",
            "key": key,
            "response_json": json.dumps(response),
        })
    except Exception:
        # concurrent duplicate insert - the first writer already stored it
        pass


async def _route_close(db: SupabaseDB, user: dict, trade: dict) -> str | None:
    """Close a live-routed position at its broker. Returns error detail or None."""
    if trade.get("exchange") in (None, "", "paper"):
        return None
    conn = await _active_connection(db, user["id"], trade.get("market"))
    if not conn:
        return f"live trade but no active {trade.get('exchange')} connection - close manually at broker"
    adapter = get_adapter(conn.get("exchange"))
    opposite = "sell" if (trade.get("side") or "").lower() == "buy" else "buy"
    api_key, api_secret = _creds(conn)
    result = await asyncio.to_thread(
        adapter.place_order, api_key, api_secret, conn.get("is_paper"),
        symbol=trade.get("symbol"), side=opposite,
        quantity=float(trade.get("quantity")), order_type="market", limit_price=None,
    )
    if not result.get("ok"):
        return f"broker rejected close order: {result.get('detail')}"
    return None


@router.post("/orders")
async def place_order(
    body: OrderRequest,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))

    # Idempotency: a retried submission with the same key returns the original result.
    if body.idempotency_key:
        replay = await _idempotency_replay(db, user["id"], body.idempotency_key)
        if replay is not None:
            return replay

    # Risk gate: kill switch, max positions, daily loss, position size, exposure
    allowed, reason = await risk_service.pre_trade_check(
        db, user["id"], body.market, body.quantity, body.entry_price or 0
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    # Route check first: fail fast before touching price feeds or risk counters.
    conn = None
    if body.route == "live":
        conn = await _active_connection(db, user["id"], body.market)
        if not conn:
            raise HTTPException(
                status_code=403,
                detail=f"no validated live connection for {body.market} - connect one under /api/exchanges or use route=paper",
            )
    elif body.order_type == "limit" and body.limit_price is None:
        raise HTTPException(status_code=422, detail="limit orders require limit_price")

    price = body.entry_price if body.entry_price is not None else await _live_price(body.market, body.symbol)
    if not price or price <= 0:
        raise HTTPException(status_code=503, detail="price unavailable - provide entry_price or retry later")

    venue, broker_order_id, filled_price = "paper", None, None
    protective_error = None
    if conn is not None:
        adapter = get_adapter(conn.get("exchange"))
        api_key, api_secret = _creds(conn)
        result = await asyncio.to_thread(
            adapter.place_order, api_key, api_secret, conn.get("is_paper"),
            symbol=body.symbol.upper(), side=body.side,
            quantity=body.quantity, order_type=body.order_type,
            limit_price=body.limit_price,
            stop_loss=body.stop_loss, take_profit=body.take_profit,
        )
        if not result.get("ok"):
            raise HTTPException(status_code=502, detail=f"broker rejected order: {result.get('detail')}")
        venue = conn.get("exchange")
        broker_order_id = result.get("broker_order_id")
        filled_price = result.get("filled_price")
        protective_error = result.get("protective_error")

    fill_price = filled_price or float(price)
    trade = await trade_service.save_trade(
        db, user_id=user["id"], symbol=body.symbol.upper(), market=body.market,
        side=body.side, quantity=body.quantity, entry_price=float(fill_price),
        strategy="manual", exchange=venue, broker_order_id=broker_order_id,
    )
    if venue != "paper" and (body.stop_loss or body.take_profit):
        await db.update(TRADES, {"stop_loss": body.stop_loss, "take_profit": body.take_profit}, where={"id": trade["id"]})
    await asyncio.to_thread(
        central.open_position, body.market, trade.get("symbol"),
        body.side.upper(), body.quantity, float(fill_price),
    )
    response = {"status": "filled", "trade_id": trade["id"], "symbol": trade.get("symbol"),
                "side": trade.get("side"), "quantity": trade.get("quantity"), "entry_price": trade.get("entry_price"),
                "route": body.route, "venue": venue, "broker_order_id": broker_order_id}
    if protective_error:
        warning = (f"Position opened on {venue} but the stop-loss could not be placed: "
                   f"{protective_error}. Protect it manually at the broker.")
        response["warning"] = warning
        await notif_service.create(db, user["id"], "trade_warning",
                                   "Stop-loss not placed", warning)
        await telegram_service.notify_user(db, user, "trade_warning", warning)
    if body.idempotency_key:
        await _idempotency_store(db, user["id"], body.idempotency_key, response)
    return response


@router.post("/close/{trade_id}")
async def close_position(
    trade_id: str,
    body: CloseRequest | None = None,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))

    trade = await db.fetch_one(TRADES, {"id": trade_id})
    if not trade or trade.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="trade not found")
    if trade.get("status") != "open":
        raise HTTPException(status_code=400, detail="trade already closed")

    # Live-routed positions must be closed at the broker first; never silently paper-close them.
    # Runs before price resolution - if the broker is unreachable, a price is pointless.
    close_err = await _route_close(db, user, trade)
    if close_err:
        raise HTTPException(status_code=502, detail=close_err)

    exit_price = body.exit_price if body else None
    if exit_price is None:
        exit_price = await _live_price(trade.get("market"), trade.get("symbol"))
    if not exit_price or exit_price <= 0:
        raise HTTPException(status_code=503, detail="exit price unavailable - provide exit_price or retry later")

    closed = await trade_service.close_trade(db, trade_id, float(exit_price))
    if not closed:
        raise HTTPException(status_code=400, detail="close failed")
    await asyncio.to_thread(
        central.close_position, closed.get("market"), closed.get("symbol"), float(exit_price)
    )
    try:
        await telegram_service.notify_user(db, user, "tp_sl", telegram_service.format_trade_closed(closed))
    except Exception:
        pass
    await notif_service.create(
        db, user["id"], "trade",
        f"Position closed: {closed.get('symbol')}",
        f"P&L: {'+' if (closed.get('pnl') or 0) >= 0 else ''}{float(closed.get('pnl') or 0):.2f} USD at {closed.get('exit_price')}",
    )
    return {"status": "closed", "trade_id": closed["id"], "pnl": closed.get("pnl"),
            "exit_price": closed.get("exit_price"), "closed_at": closed.get("closed_at")}


@router.get("/history")
async def history(
    market: str | None = Query(None, pattern="^(stock|forex|crypto|commodity)$"),
    symbol: str | None = Query(None, max_length=20),
    strategy: str | None = Query(None, max_length=50),
    outcome: str | None = Query(None, pattern="^(win|loss|open)$"),
    start: str | None = Query(None),
    end: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Completed + open trade history with filters and pagination."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    s, e = analytics_service.parse_range(start, end, None)

    where: dict = {"user_id": user["id"]}
    if market:
        where["market"] = market
    if symbol:
        where["symbol"] = symbol.upper()
    if strategy:
        where["strategy"] = strategy
    if outcome == "open":
        where["status"] = "open"
    elif outcome == "win":
        where["status"] = "closed"
        where["pnl"] = {"op": "gt", "value": 0}
    elif outcome == "loss":
        where["status"] = "closed"
        where["pnl"] = {"op": "lt", "value": 0}
    if s:
        where["opened_at"] = {"op": "gte", "value": s.isoformat().replace("+00:00", "Z")}
    if e:
        where["opened_at"] = {"op": "lte", "value": e.isoformat().replace("+00:00", "Z")}

    total = await db.count(TRADES, where=where)
    trades = await db.fetch_all(TRADES, where=where, order="opened_at.desc", limit=limit, offset=offset)

    closed = [t for t in trades if t.get("status") == "closed"]
    wins = sum(1 for t in closed if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in closed if (t.get("pnl") or 0) < 0)

    return {
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "trades": [
            {
                "id": t.get("id"),
                "symbol": t.get("symbol"),
                "market": t.get("market"),
                "side": t.get("side"),
                "quantity": t.get("quantity"),
                "entry_price": t.get("entry_price"),
                "exit_price": t.get("exit_price"),
                "pnl": t.get("pnl"),
                "strategy": t.get("strategy"),
                "status": t.get("status"),
                "opened_at": t.get("opened_at"),
                "closed_at": t.get("closed_at"),
            }
            for t in trades
        ],
        "summary": {
            "in_page": len(trades),
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wins / len(closed) * 100, 1) if closed else 0.0,
            "total_pnl": round(sum(float(t.get("pnl") or 0.0) for t in closed), 2),
        },
    }


@router.get("/analytics")
async def analytics(
    days: int | None = Query(None, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    s, e = analytics_service.parse_range(start, end, days)
    trades = await analytics_service.get_closed_trades(db, user["id"], start=s, end=e)

    wins = sum(1 for t in trades if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in trades if (t.get("pnl") or 0) < 0)
    total_pnl = round(sum(float(t.get("pnl") or 0) for t in trades), 2)

    return {
        "range": {"start": s.isoformat() if s else None, "end": e.isoformat() if e else None},
        "closed_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(trades) * 100, 1) if trades else 0.0,
        "total_pnl": total_pnl,
        "pnl_series": analytics_service.pnl_series(trades),
        "drawdown_series": analytics_service.drawdown_series(trades),
        "by_strategy": analytics_service.win_loss_by_strategy(trades),
        "correlation": analytics_service.correlation_matrix(trades),
    }


@router.get("/export")
async def export_trades(
    format: str = Query("csv", pattern="^(csv)$"),
    days: int | None = Query(None, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    s, e = analytics_service.parse_range(start, end, days)
    trades = await analytics_service.get_closed_trades(db, user["id"], start=s, end=e)

    csv_text = analytics_service.trades_to_csv(trades)
    filename = f"trades_{(s.date() if s else 'all')}_{(e.date() if e else 'all')}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )