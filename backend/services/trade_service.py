from datetime import datetime, timezone

from backend.db.models import TRADES, USER_PREFERENCES, gen_uuid
from backend.db.supabase import SupabaseDB, now_iso, parse_dt

DEFAULT_STARTING_BALANCE = 100000.0


async def get_starting_balance(db: SupabaseDB, user_id: str, is_demo: bool = False) -> float:
    """Starting balance for a ledger: the per-user demo balance, or the live default.

    Paper/demo accounts carry a virtual balance the user can reset; the live
    ledger keeps the fixed platform baseline.
    """
    if not is_demo:
        return DEFAULT_STARTING_BALANCE
    prefs = await db.fetch_one(
        USER_PREFERENCES, {"user_id": user_id}, columns="demo_starting_balance"
    )
    if prefs and prefs.get("demo_starting_balance") is not None:
        try:
            return float(prefs["demo_starting_balance"])
        except (TypeError, ValueError):
            return DEFAULT_STARTING_BALANCE
    return DEFAULT_STARTING_BALANCE


async def save_trade(db: SupabaseDB, user_id: str, symbol: str, market: str,
                     side: str, quantity: float, entry_price: float,
                     strategy: str | None = None, exchange: str | None = None,
                     broker_order_id: str | None = None,
                     is_demo: bool = False) -> dict:
    trade = {
        "id": gen_uuid(),
        "user_id": user_id,
        "symbol": symbol,
        "market": market,
        "side": side.lower(),
        "quantity": quantity,
        "entry_price": entry_price,
        "exit_price": None,
        "pnl": None,
        "status": "open",
        "strategy": strategy,
        "exchange": exchange,
        "broker_order_id": broker_order_id,
        "stop_loss": None,
        "take_profit": None,
        "is_demo": is_demo,
        "opened_at": now_iso(),
        "closed_at": None,
    }
    return await db.insert(TRADES, trade)


async def close_trade(db: SupabaseDB, trade_id: str, exit_price: float) -> dict | None:
    trade = await db.fetch_one(TRADES, {"id": trade_id})
    if not trade or trade.get("status") != "open":
        return None

    if trade.get("side") == "buy":
        pnl = (exit_price - trade["entry_price"]) * trade["quantity"]
    else:
        pnl = (trade["entry_price"] - exit_price) * trade["quantity"]

    await db.update(
        TRADES,
        {
            "exit_price": exit_price,
            "closed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": "closed",
            "pnl": pnl,
        },
        where={"id": trade_id},
    )
    return await db.fetch_one(TRADES, {"id": trade_id})


async def list_trades(db: SupabaseDB, user_id: str, market: str | None = None,
                      status: str | None = None, limit: int = 50,
                      is_demo: bool | None = None) -> list[dict]:
    where: dict[str, object] = {"user_id": user_id}
    if market:
        where["market"] = market
    if status:
        where["status"] = status
    if is_demo is not None:
        where["is_demo"] = bool(is_demo)
    return await db.fetch_all(TRADES, where=where, order="opened_at.desc", limit=limit)


async def get_portfolio_summary(db: SupabaseDB, user_id: str, is_demo: bool | None = None):
    where: dict[str, object] = {"user_id": user_id}
    if is_demo is not None:
        where["is_demo"] = bool(is_demo)
    total = await db.count(TRADES, where=where)
    open_count = await db.count(TRADES, where={**where, "status": "open"})
    pnl_rows = await db.fetch_all(TRADES, where=where, columns="pnl")
    total_pnl = sum(float(r.get("pnl") or 0) for r in pnl_rows)
    wins = sum(1 for r in pnl_rows if (r.get("pnl") or 0) > 0)

    return {
        "total_trades": total,
        "open_trades": open_count,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round((wins / total * 100) if total > 0 else 0.0, 1),
    }


async def get_holdings(db: SupabaseDB, user_id: str, is_demo: bool | None = None) -> list[dict]:
    """Aggregate open trades into per-symbol holdings (net quantity + avg entry)."""
    where: dict[str, object] = {"user_id": user_id, "status": "open"}
    if is_demo is not None:
        where["is_demo"] = bool(is_demo)
    trades = await db.fetch_all(TRADES, where=where)

    groups: dict[tuple[str, str], dict] = {}
    for tr in trades:
        key = (tr["symbol"], tr["market"])
        g = groups.setdefault(key, {
            "symbol": tr["symbol"], "market": tr["market"],
            "net_qty": 0.0, "cost_basis": 0.0,
            "trade_count": 0, "strategy": tr.get("strategy"),
        })
        qty = float(tr["quantity"])
        g["net_qty"] += qty if tr["side"] == "buy" else -qty
        g["cost_basis"] += float(tr["entry_price"]) * qty
        g["trade_count"] += 1
        if len(g["strategy"] or "") < len(tr.get("strategy") or ""):
            g["strategy"] = tr.get("strategy")

    out = []
    for g in groups.values():
        qty = abs(g["net_qty"])
        avg_entry = (g["cost_basis"] / qty) if qty else 0.0
        out.append({
            "symbol": g["symbol"],
            "market": g["market"],
            "quantity": round(g["net_qty"], 8),
            "avg_entry_price": round(avg_entry, 6),
            "trade_count": g["trade_count"],
            "strategy": g["strategy"],
        })
    out.sort(key=lambda h: -abs(h["quantity"]))
    return out


async def get_performance(db: SupabaseDB, user_id: str, is_demo: bool | None = None) -> dict:
    """Realized performance: equity curve, win/loss stats, allocation by market."""
    where: dict[str, object] = {"user_id": user_id, "status": "closed"}
    if is_demo is not None:
        where["is_demo"] = bool(is_demo)
    trades = await db.fetch_all(TRADES, where=where, order="closed_at.asc")

    START = await get_starting_balance(db, user_id, bool(is_demo))
    equity_curve: list[dict] = []
    allocation: dict[str, float] = {}
    cum = 0.0
    peak = 0.0
    max_dd = 0.0
    wins = losses = 0

    for tr in trades:
        pnl = float(tr.get("pnl") or 0.0)
        cum += pnl
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1
        peak = max(peak, cum)
        max_dd = min(max_dd, cum - peak)

        closed_at = parse_dt(tr.get("closed_at"))
        label = closed_at.strftime("%m-%d %H:%M") if closed_at else ""
        equity_curve.append({"label": label, "value": round(START + cum, 2)})

        mkt = tr.get("market") or "other"
        notional = abs(float(tr.get("exit_price") or tr.get("entry_price") or 0) * float(tr["quantity"]))
        allocation[mkt] = allocation.get(mkt, 0.0) + notional

    closed = len(trades)
    return {
        "starting_value": START,
        "portfolio_value": round(START + cum, 2),
        "total_pnl": round(cum, 2),
        "win_rate": round(wins / closed * 100, 1) if closed else 0.0,
        "wins": wins,
        "losses": losses,
        "max_drawdown": round(max_dd, 2),
        "equity_curve": equity_curve,
        "allocation": [
            {"market": k, "value": round(v, 2)}
            for k, v in sorted(allocation.items(), key=lambda kv: -kv[1])
        ],
    }


async def get_demo_account(db: SupabaseDB, user_id: str) -> dict:
    """Snapshot of the user's virtual (demo) trading account."""
    starting = await get_starting_balance(db, user_id, is_demo=True)
    closed = await db.fetch_all(
        TRADES, where={"user_id": user_id, "is_demo": True, "status": "closed"}, columns="pnl"
    )
    realized = sum(float(r.get("pnl") or 0) for r in closed)
    open_count = await db.count(
        TRADES, where={"user_id": user_id, "is_demo": True, "status": "open"}
    )
    return {
        "starting_balance": round(starting, 2),
        "realized_pnl": round(realized, 2),
        "portfolio_value": round(starting + realized, 2),
        "open_positions": open_count,
        "closed_trades": len(closed),
    }


async def reset_demo(db: SupabaseDB, user_id: str) -> dict:
    """Clear the user's demo trades, restoring the starting balance."""
    deleted = await db.delete(TRADES, {"user_id": user_id, "is_demo": True})
    starting = await get_starting_balance(db, user_id, is_demo=True)
    return {
        "deleted": len(deleted),
        "starting_balance": round(starting, 2),
        "portfolio_value": round(starting, 2),
    }