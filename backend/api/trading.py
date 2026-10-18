import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.db.database import get_db
from backend.db.models import IDEMPOTENCY_RECORDS, TRADES, gen_uuid
from backend.db.supabase import SupabaseDB
from backend.auth import get_current_user
from backend.services import trade_service, analytics_service, risk_service, telegram_service
from backend.exchanges import get_adapter
from backend.services import notification_service as notif_service
from backend.services.order_executor import active_connection, creds, live_price, place_and_record
from backend.api.risk import central
from backend.middleware.rate_limiter import check_rate_limit

router = APIRouter(prefix="/api/trading", tags=["trading"])


class OrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    market: str = Field(pattern="^(stock|forex|crypto|commodity)$")
    side: str = Field(pattern="^(buy|sell)$")
    quantity: float = Field(gt=0)
    # Advisory only: when present it seeds the paper fill and the risk maths. It is
    # NEVER trusted on the live route (see place_order) because the broker fills
    # at the real market price and a client-chosen price would corrupt exposure,
    # position-size and daily-loss accounting.
    entry_price: float | None = Field(default=None, gt=0)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    limit_price: float | None = Field(default=None, gt=0)
    route: str = Field(default="paper", pattern="^(paper|live)$")
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    idempotency_key: str | None = Field(default=None, max_length=64)


class CloseRequest(BaseModel):
    exit_price: float | None = Field(default=None, gt=0)


async def _idempotency_replay(db: SupabaseDB, user_id: str, key: str) -> dict | None:
    rec = await db.fetch_one(
        IDEMPOTENCY_RECORDS,
        {"user_id": user_id, "endpoint": "orders", "key": key},
    )
    if not rec:
        return None
    # response_json is a jsonb column; postgrest returns it already decoded.
    stored = rec.get("response_json")
    if isinstance(stored, dict):
        return stored
    try:
        return json.loads(stored) if stored else None
    except (TypeError, ValueError):
        return None


async def _idempotency_claim(db: SupabaseDB, user_id: str, key: str) -> bool:
    """Insert a placeholder row to win the key. False = someone else holds it."""
    try:
        await db.insert(IDEMPOTENCY_RECORDS, {
            "id": gen_uuid(),
            "user_id": user_id,
            "endpoint": "orders",
            "key": key,
            "response_json": {},
        })
        return True
    except Exception:
        return False


async def _idempotency_release(db: SupabaseDB, user_id: str, key: str) -> None:
    """Drop an unfulfilled claim so the caller may retry."""
    try:
        await db.delete(IDEMPOTENCY_RECORDS,
                        {"user_id": user_id, "endpoint": "orders", "key": key})
    except Exception:
        pass


async def _idempotency_store(db: SupabaseDB, user_id: str, key: str, response: dict) -> None:
    try:
        await db.update(
            IDEMPOTENCY_RECORDS,
            {"response_json": response},
            where={"user_id": user_id, "endpoint": "orders", "key": key},
        )
    except Exception:
        pass


def _validate_protective_levels(side: str, entry: float,
                                stop_loss: float | None, take_profit: float | None) -> None:
    """A buy needs stop_loss < entry < take_profit; a sell is the mirror.

    Getting this wrong makes the broker fill the protective leg instantly at the
    worst available price, so it is rejected outright rather than clamped.
    """
    is_buy = (side or "").lower() == "buy"
    if stop_loss is not None:
        if is_buy and stop_loss >= entry:
            raise HTTPException(
                status_code=422,
                detail=f"stop_loss {stop_loss} must be below the entry price {entry} for a buy",
            )
        if not is_buy and stop_loss <= entry:
            raise HTTPException(
                status_code=422,
                detail=f"stop_loss {stop_loss} must be above the entry price {entry} for a sell",
            )
    if take_profit is not None:
        if is_buy and take_profit <= entry:
            raise HTTPException(
                status_code=422,
                detail=f"take_profit {take_profit} must be above the entry price {entry} for a buy",
            )
        if not is_buy and take_profit >= entry:
            raise HTTPException(
                status_code=422,
                detail=f"take_profit {take_profit} must be below the entry price {entry} for a sell",
            )


async def _route_close(db: SupabaseDB, user: dict, trade: dict) -> str | None:
    """Close a live-routed position at its broker. Returns error detail or None."""
    if trade.get("exchange") in (None, "", "paper"):
        return None
    conn = await active_connection(db, user["id"], trade.get("market"))
    if not conn:
        return f"live trade but no active {trade.get('exchange')} connection - close manually at broker"
    adapter = get_adapter(conn.get("exchange"))
    opposite = "sell" if (trade.get("side") or "").lower() == "buy" else "buy"
    api_key, api_secret = creds(conn)
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

    # Claim the key BEFORE the order reaches the broker. The unique index
    # (user_id, endpoint, key) then serialises concurrent retries, so two racing
    # requests can never both place an order. A duplicate while the first is still
    # in flight replays a pending marker instead of placing again.
    claimed = False
    if body.idempotency_key:
        claimed = await _idempotency_claim(db, user["id"], body.idempotency_key)
        if not claimed:
            replay = await _idempotency_replay(db, user["id"], body.idempotency_key)
            return replay or {
                "status": "pending",
                "detail": "identical request already in flight",
                "idempotency_key": body.idempotency_key,
            }

    try:
        return await _place_order_inner(db, user, body)
    except HTTPException:
        # Failed orders must not burn the key, or a retry of a transient
        # broker/feed failure would be permanently replayed as an error.
        if body.idempotency_key and claimed:
            await _idempotency_release(db, user["id"], body.idempotency_key)
        raise


async def _place_order_inner(db: SupabaseDB, user: dict, body: OrderRequest) -> dict:
    # Route check first: fail fast before touching price feeds or risk counters.
    conn = None
    if body.route == "live":
        if body.entry_price is not None:
            raise HTTPException(
                status_code=422,
                detail="entry_price is not accepted on the live route - the broker fill price is used",
            )
        conn = await active_connection(db, user["id"], body.market)
        if not conn:
            raise HTTPException(
                status_code=403,
                detail=f"no validated live connection for {body.market} - connect one under /api/exchanges or use route=paper",
            )
    if body.order_type == "limit" and body.limit_price is None:
        raise HTTPException(status_code=422, detail="limit orders require limit_price")

    # Resolve the price BEFORE the risk gate. pre_trade_check multiplies by this
    # value, so a missing/zero price would make every size and exposure cap pass.
    price = body.entry_price if body.entry_price is not None else await live_price(body.market, body.symbol)
    if not price or price <= 0:
        raise HTTPException(status_code=503, detail="price unavailable - provide entry_price or retry later")
    price = float(price)

    # Stop/target must sit on the correct side of the entry, otherwise the broker
    # fills the protective leg immediately at the worst possible price.
    _validate_protective_levels(body.side, price, body.stop_loss, body.take_profit)

    # Risk gate: kill switch, max positions, daily loss, position size, exposure.
    # Paper orders are the demo ledger and are gated on the demo balance.
    risk_status = await risk_service.get_risk_status(db, user["id"], is_demo=(body.route != "live"))
    allowed, reason = await risk_service.pre_trade_check(
        db, user["id"], body.market, body.quantity, price, status=risk_status,
        is_demo=(body.route != "live"),
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    # Central cross-market engine: global kill switch, drawdown auto-trip, per-market
    # daily cap, correlation limits. Applies to manual AND live orders.
    approval = await asyncio.to_thread(
        central.approve_trade, body.market, body.symbol.upper(), body.side.upper(),
        body.quantity, price, risk_status["account_value"],
    )
    if not getattr(approval, "allowed", False):
        raise HTTPException(
            status_code=403,
            detail=getattr(approval, "reason", "blocked by the central risk engine"),
        )

    result = await place_and_record(
        db, user=user, symbol=body.symbol.upper(), market=body.market,
        side=body.side, quantity=body.quantity, entry_price=float(price),
        route=body.route, conn=conn, order_type=body.order_type,
        limit_price=body.limit_price,
        stop_loss=body.stop_loss, take_profit=body.take_profit,
        strategy="manual",
    )
    if result.get("status") != "filled":
        raise HTTPException(status_code=502, detail=result.get("detail", "broker rejected order"))
    response = {k: result.get(k) for k in ("status", "trade_id", "symbol", "side",
                                           "quantity", "entry_price", "route", "venue",
                                           "broker_order_id", "warning") if result.get(k) is not None}
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
        exit_price = await live_price(trade.get("market"), trade.get("symbol"))
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
    is_demo: bool | None = Query(None),
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
    if is_demo is not None:
        where["is_demo"] = bool(is_demo)
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
                "is_demo": t.get("is_demo"),
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
    is_demo: bool | None = Query(None),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    s, e = analytics_service.parse_range(start, end, days)
    trades = await analytics_service.get_closed_trades(db, user["id"], start=s, end=e, is_demo=is_demo)

    wins = sum(1 for t in trades if (t.get("pnl") or 0) > 0)
    losses = sum(1 for t in trades if (t.get("pnl") or 0) < 0)
    total_pnl = round(sum(float(t.get("pnl") or 0) for t in trades), 2)
    starting_value = await trade_service.get_starting_balance(db, user["id"], bool(is_demo))

    return {
        "range": {"start": s.isoformat() if s else None, "end": e.isoformat() if e else None},
        "closed_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(trades) * 100, 1) if trades else 0.0,
        "total_pnl": total_pnl,
        "pnl_series": analytics_service.pnl_series(trades),
        "drawdown_series": analytics_service.drawdown_series(trades, starting_value),
        "by_strategy": analytics_service.win_loss_by_strategy(trades),
        "correlation": analytics_service.correlation_matrix(trades),
    }


@router.get("/export")
async def export_trades(
    format: str = Query("csv", pattern="^(csv)$"),
    days: int | None = Query(None, ge=1, le=365),
    start: str | None = Query(None),
    end: str | None = Query(None),
    is_demo: bool | None = Query(None),
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    s, e = analytics_service.parse_range(start, end, days)
    trades = await analytics_service.get_closed_trades(db, user["id"], start=s, end=e, is_demo=is_demo)

    csv_text = analytics_service.trades_to_csv(trades)
    filename = f"trades_{(s.date() if s else 'all')}_{(e.date() if e else 'all')}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/demo")
async def demo_account(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Virtual (demo) account snapshot: balance, realized P&L, open positions."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    return await trade_service.get_demo_account(db, user["id"])


@router.post("/demo/reset")
async def demo_reset(
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Clear all demo trades and restore the demo starting balance."""
    check_rate_limit(user["id"], user.get("tier", "free"))
    result = await trade_service.reset_demo(db, user["id"])
    try:
        await notif_service.create(
            db, user["id"], "trade", "Demo account reset",
            f"Cleared {result['deleted']} demo trade(s). Balance restored to "
            f"${result['starting_balance']:,.2f}.",
        )
    except Exception:
        pass
    return result