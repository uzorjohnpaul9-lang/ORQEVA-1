"""Shared order execution used by both the manual Trading API and the AI Auto-Trade runner.

Keeps the risk -> broker -> save-trade -> central-engine sequence in one place so the
auto-trader and a hand-placed order can never drift apart.
"""
import asyncio

from backend.db.models import EXCHANGE_CONNECTIONS, TRADES
from backend.db.supabase import SupabaseDB
from backend.exchanges import get_adapter
from backend.services import trade_service
from backend.services import telegram_service
from backend.services import notification_service as notif_service
from backend.api.risk import central


async def live_price(market: str, symbol: str) -> float | None:
    """Fetch live price off the event loop; None on failure/timeout."""
    from backend.services import market_service

    def fetch(m: str, s: str) -> float | None:
        q = market_service.get_quote(m, s)
        return q.get("price") if isinstance(q, dict) else None

    try:
        return await asyncio.wait_for(asyncio.to_thread(fetch, market, symbol), timeout=10.0)
    except Exception:
        return None


async def active_connection(db: SupabaseDB, user_id: str, market: str) -> dict | None:
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


def creds(conn: dict) -> tuple[str, str]:
    from backend.api.exchanges import security
    api_key = security.decrypt_data(conn["api_key_encrypted"])
    api_secret = security.decrypt_data(conn["api_secret_encrypted"]) if conn.get("api_secret_encrypted") else ""
    return api_key, api_secret


async def place_and_record(db: SupabaseDB, *, user: dict, symbol: str, market: str, side: str,
                           quantity: float, entry_price: float, route: str,
                           conn: dict | None = None, order_type: str = "market",
                           limit_price: float | None = None,
                           stop_loss: float | None = None, take_profit: float | None = None,
                           strategy: str = "manual", signal_id: str | None = None) -> dict:
    """Route, place, and persist one order. Mirrors the manual orders endpoint.

    Returns a dict with ``status`` ('filled' | 'rejected') plus a human-readable
    ``detail`` (set on rejection) - never raises on broker/network failures.
    """
    price = float(entry_price)
    venue, broker_order_id, filled_price = "paper", None, None
    protective_error = None

    if conn is not None:
        adapter = get_adapter(conn.get("exchange"))
        api_key, api_secret = creds(conn)
        result = await asyncio.to_thread(
            adapter.place_order, api_key, api_secret, conn.get("is_paper"),
            symbol=symbol.upper(), side=side,
            quantity=quantity, order_type=order_type,
            limit_price=limit_price,
            stop_loss=stop_loss, take_profit=take_profit,
        )
        if not result.get("ok"):
            return {"status": "rejected", "detail": f"broker rejected order: {result.get('detail')}"}
        venue = conn.get("exchange")
        broker_order_id = result.get("broker_order_id")
        filled_price = result.get("filled_price")
        protective_error = result.get("protective_error")

    fill_price = filled_price or float(price)
    trade = await trade_service.save_trade(
        db, user_id=user["id"], symbol=symbol.upper(), market=market,
        side=side, quantity=quantity, entry_price=float(fill_price),
        strategy=strategy, exchange=venue, broker_order_id=broker_order_id,
    )
    if venue != "paper":
        await db.update(TRADES, {"stop_loss": stop_loss, "take_profit": take_profit}, where={"id": trade["id"]})
    if signal_id:
        await db.update(TRADES, {"signal_id": signal_id}, where={"id": trade["id"]})
    await asyncio.to_thread(
        central.open_position, market, trade.get("symbol"),
        side.upper(), quantity, float(fill_price),
    )

    response = {"status": "filled", "trade_id": trade["id"], "symbol": trade.get("symbol"),
                "side": trade.get("side"), "quantity": trade.get("quantity"),
                "entry_price": trade.get("entry_price"),
                "route": route, "venue": venue, "broker_order_id": broker_order_id}
    if protective_error:
        warning = (f"Position opened on {venue} but the stop-loss could not be placed: "
                   f"{protective_error}. Protect it manually at the broker.")
        response["warning"] = warning
        await notif_service.create(db, user["id"], "trade_warning",
                                   "Stop-loss not placed", warning)
        await telegram_service.notify_user(db, user, "trade_warning", warning)
    return response