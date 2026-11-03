"""Shared order execution used by both the manual Trading API and the AI Auto-Trade runner.

Keeps the risk -> broker -> save-trade -> central-engine sequence in one place so the
auto-trader and a hand-placed order can never drift apart.
"""
import asyncio
import os
import time

from backend.db.models import EXCHANGE_CONNECTIONS, SIGNALS, TRADES
from backend.db.supabase import SupabaseDB
from backend.exchanges import get_adapter
from backend.services import trade_service
from backend.services import telegram_service
from backend.services import notification_service as notif_service
from backend.api.risk import central


def protection_placed_requested(protective: str | None, stop_loss: float | None,
                                take_profit: float | None) -> bool:
    """True when the adapter confirmed protection matching what was requested."""
    kind = (protective or "").lower()
    if stop_loss and take_profit:
        return kind in ("bracket", "oto", "oco")
    if stop_loss:
        return kind in ("bracket", "oto", "oco", "stop_loss", "stop")
    if take_profit:
        return kind in ("bracket", "oto", "oco", "take_profit")
    return True


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


_ACCOUNT_CACHE_TTL = float(os.getenv("BROKER_ACCOUNT_CACHE_SECONDS", "30"))
_account_cache: dict[str, tuple[float, float]] = {}


def _account_cache_key(conn: dict) -> str:
    return f"{conn.get('id') or ''}:{conn.get('exchange') or ''}"


async def broker_account_value(conn: dict | None, ttl: float | None = None) -> float | None:
    """The venue's account equity/balance, or None when it cannot be read.

    Live size caps must use the real account value: the platform baseline is a
    fixed number and would size a $1k account as if it held $100k. A short TTL
    cache stops an auto-trade scan from hitting the bridge once per signal.
    """
    if conn is None:
        return None
    ttl = _ACCOUNT_CACHE_TTL if ttl is None else ttl
    cache_key = _account_cache_key(conn)
    now = time.monotonic()
    cached = _account_cache.get(cache_key)
    if cached and now - cached[0] < ttl:
        return cached[1]
    adapter = get_adapter(conn.get("exchange"))
    if adapter is None:
        return None
    api_key, api_secret = creds(conn)

    def fetch() -> dict | None:
        try:
            return adapter.account(api_key, api_secret, conn.get("is_paper"))
        except Exception:
            return None

    snapshot = await asyncio.to_thread(fetch)
    if not snapshot:
        return None
    for field in ("equity", "balance"):
        try:
            value = float(snapshot.get(field) or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            _account_cache[cache_key] = (now, value)
            return value
    return None


async def _broker_close(conn: dict, trade: dict) -> dict:
    adapter = get_adapter(conn.get("exchange"))
    api_key, api_secret = creds(conn)
    # MT5 hedging accounts would just open an offsetting position if we sent the
    # opposite market order, leaving both legs live at the broker. Venues that
    # support it close the actual position by ticket instead.
    if getattr(adapter, "supports_position_close", False):
        return await asyncio.to_thread(
            adapter.close_positions, api_key, api_secret, conn.get("is_paper"),
            symbol=trade.get("symbol"), side=(trade.get("side") or "").lower(),
            quantity=float(trade.get("quantity")),
        )
    opposite = "sell" if (trade.get("side") or "").lower() == "buy" else "buy"
    return await asyncio.to_thread(
        adapter.place_order, api_key, api_secret, conn.get("is_paper"),
        symbol=trade.get("symbol"), side=opposite,
        quantity=float(trade.get("quantity")), order_type="market", limit_price=None,
    )


async def route_close(db: SupabaseDB, user: dict, trade: dict) -> str | None:
    """Close a live-routed position at its broker. Returns error detail or None."""
    if trade.get("exchange") in (None, "", "paper"):
        return None
    conn = await active_connection(db, user["id"], trade.get("market"))
    if not conn:
        return f"live trade but no active {trade.get('exchange')} connection - close manually at broker"
    result = await _broker_close(conn, trade)
    if not result.get("ok"):
        return f"broker rejected close order: {result.get('detail')}"
    return None


def _already_closed(detail: str | None) -> bool:
    text = (detail or "").lower()
    return "no open" in text or "no closable volume" in text


def is_demo_ledger(route: str, conn: dict | None) -> bool:
    """True for the virtual/demo ledger: paper route or a demo broker connection."""
    return route != "live" or bool(conn and conn.get("is_paper"))


async def close_signal_trades(db: SupabaseDB, signal_id: str, exit_price: float | None,
                              outcome: str) -> dict:
    """Close open auto-trade positions whose signal has resolved.

    A broker TP/SL usually closes the position first; the bridge then reports no
    open position, which is treated as already closed. Signals that expire have
    no broker-side trigger, so their positions must be closed here. Failures are
    collected and the trade stays open rather than being paper-closed while the
    broker position is still live.
    """
    trades = await db.fetch_all(
        TRADES, where={"signal_id": signal_id, "status": "open"},
    )
    closed, failed = 0, []
    for trade in trades:
        user_id = trade.get("user_id")
        is_live = trade.get("exchange") not in (None, "", "paper")
        if is_live:
            conn = await active_connection(db, user_id, trade.get("market"))
            if not conn:
                failed.append(f"{trade.get('symbol')}: no active connection")
                continue
            result = await _broker_close(conn, trade)
            if not result.get("ok"):
                detail = result.get("detail")
                if not _already_closed(detail):
                    failed.append(f"{trade.get('symbol')}: {detail}")
                    continue

        price = None
        if outcome != "expired" and exit_price:
            price = float(exit_price)
        if price is None:
            price = await live_price(trade.get("market"), trade.get("symbol"))
        if price is None and exit_price:
            price = float(exit_price)
        if not price or price <= 0:
            failed.append(f"{trade.get('symbol')}: exit price unavailable")
            continue

        closed_trade = await trade_service.close_trade(db, trade["id"], float(price))
        if not closed_trade:
            continue
        closed += 1
        if not closed_trade.get("is_demo"):
            try:
                await asyncio.to_thread(
                    central.close_position, closed_trade.get("market"),
                    closed_trade.get("symbol"), float(price),
                )
            except Exception:
                pass

    return {"closed": closed, "failed": failed[:10]}


async def reconcile_resolved_trades(db: SupabaseDB, limit: int = 200) -> dict:
    """Retry closing auto-trade trades whose signal resolved earlier.

    The outcome pass closes positions as it resolves each signal, but a broker
    outage at that moment would otherwise leave the trade open forever because
    the signal is already resolved. This sweep runs every scheduler tick and is
    idempotent: trades already closed are skipped.
    """
    rows = await db.fetch_all(
        TRADES, where={"status": "open"}, columns="id,signal_id", limit=limit,
    )
    by_signal: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("signal_id"):
            by_signal.setdefault(row["signal_id"], []).append(row)
    if not by_signal:
        return {"closed": 0, "failed": []}

    signals = await db.fetch_all(
        SIGNALS, where={"id": list(by_signal)}, columns="id,status,outcome,exit_price",
    )
    closed, failed = 0, []
    for signal in signals:
        if signal.get("status") not in ("closed", "expired"):
            continue
        try:
            result = await close_signal_trades(
                db, signal["id"], signal.get("exit_price"), signal.get("outcome") or "expired",
            )
            closed += int(result.get("closed") or 0)
            failed.extend(result.get("failed") or [])
        except Exception as e:  # pragma: no cover - defensive
            failed.append(f"{signal.get('id')}: {str(e)[:100]}")
    return {"closed": closed, "failed": failed[:10]}


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
    protective = None

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
        protective = result.get("protective")
        protective_error = result.get("protective_error")
        # An adapter that silently omits protection while the caller asked for it
        # must not leave the position naked.
        if (stop_loss or take_profit) and not protection_placed_requested(protective, stop_loss, take_profit):
            protective_error = protective_error or (
                f"broker accepted the order but reported no {protective or 'protective'} order"
            )

    fill_price = filled_price or float(price)
    is_demo = is_demo_ledger(route, conn)
    trade = await trade_service.save_trade(
        db, user_id=user["id"], symbol=symbol.upper(), market=market,
        side=side, quantity=quantity, entry_price=float(fill_price),
        strategy=strategy, exchange=venue, broker_order_id=broker_order_id,
        is_demo=is_demo,
    )
    # Only claim protection the broker actually accepted. Recording an SL/TP that
    # was never placed shows a stop in the dashboard that does not exist.
    protection_placed = bool(protective) and protective != "none"
    if venue != "paper":
        fields = {"stop_loss": stop_loss, "take_profit": take_profit} if protection_placed else {}
        if fields:
            await db.update(TRADES, fields, where={"id": trade["id"]})
    if signal_id:
        await db.update(TRADES, {"signal_id": signal_id}, where={"id": trade["id"]})
    if not is_demo:
        await asyncio.to_thread(
            central.open_position, market, trade.get("symbol"),
            side.upper(), quantity, float(fill_price),
        )

    response = {"status": "filled", "trade_id": trade["id"], "symbol": trade.get("symbol"),
                "side": trade.get("side"), "quantity": trade.get("quantity"),
                "entry_price": trade.get("entry_price"), "is_demo": is_demo,
                "route": route, "venue": venue, "broker_order_id": broker_order_id}
    if protective_error:
        warning = (f"Position opened on {venue} but the stop-loss could not be placed: "
                   f"{protective_error}. Protect it manually at the broker.")
        response["warning"] = warning
        await notif_service.create(db, user["id"], "trade_warning",
                                   "Stop-loss not placed", warning)
        await telegram_service.notify_user(db, user, "trade_warning", warning)
    return response