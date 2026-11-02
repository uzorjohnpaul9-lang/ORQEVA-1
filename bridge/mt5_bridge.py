"""ORQEVA - Exness (MetaTrader 5) bridge.

The Railway backend cannot reach MetaTrader 5 directly: the MetaTrader5 Python
package only runs on Windows next to a running MT5 terminal. This service is the
small HTTP shim that runs on that Windows VPS. The backend's ``exness`` adapter
calls it for credential checks, account snapshots, orders and position closes.

Security:
  * every route except ``/health`` requires ``X-Bridge-Token`` matching
    ``MT5_BRIDGE_TOKEN``;
  * the bridge binds to 127.0.0.1 and is exposed through a Cloudflare tunnel,
    never directly to the internet;
  * the MT5 credentials travel per request and are never stored here.

Run:
  python -m uvicorn bridge.mt5_bridge:app --host 127.0.0.1 --port 8100
"""
import hmac
import logging
import math
import os
import threading
from contextlib import contextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

try:  # Windows-only package; keep the module importable for tests/CI on Linux.
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - exercised only on non-Windows hosts
    mt5 = None

log = logging.getLogger("orqeva.mt5")

app = FastAPI(title="ORQEVA MT5 Bridge", version="1.0.0")

# MT5's Python API is one global terminal session per process - serialize it.
_LOCK = threading.Lock()

_SUCCESS_RETCODES = {10008, 10009, 10010}  # PLACED, DONE, DONE_PARTIAL
_INVALID_FILL = 10030
_INIT_TIMEOUT_MS = int(os.getenv("MT5_INIT_TIMEOUT_MS", "30000"))


class BridgeError(RuntimeError):
    pass


# ---------------------------------------------------------------- pure helpers

def normalize_symbol(symbol: str) -> str:
    """EUR/USD, eur-usd -> EURUSD. Case and dots are kept (MT5 names are cased)."""
    return "".join(ch for ch in (symbol or "") if ch not in "/- ").strip()


def units_to_lots(units: float, contract_size: float, volume_min: float,
                  volume_max: float, volume_step: float) -> float:
    """Convert base-asset units (what ORQEVA's ledger stores) into MT5 lots."""
    if contract_size <= 0:
        raise BridgeError("broker did not report a contract size for this symbol")
    if units <= 0:
        raise BridgeError("quantity must be positive")
    raw = float(units) / float(contract_size)
    step = float(volume_step or 0.01)
    if step <= 0:
        step = 0.01
    lots = math.floor(raw / step + 1e-6) * step
    lots = round(lots, 8)
    if lots <= 0:
        raise BridgeError(f"{units:g} units is below the broker's minimum trade size")
    if volume_min and lots < float(volume_min):
        raise BridgeError(
            f"calculated volume {lots:g} lots is below the broker minimum "
            f"{float(volume_min):g} - raise risk per trade or the stop distance"
        )
    if volume_max and lots > float(volume_max):
        lots = round(float(volume_max), 8)
    return lots


def _contract_size(info: Any) -> float:
    return float(getattr(info, "trade_contract_size", 0) or 0)


def _digits(info: Any) -> int:
    return int(getattr(info, "digits", 5) or 5)


def _round(value: float, info: Any) -> float:
    return round(float(value), _digits(info))


def _stops_distance(info: Any) -> float:
    return float(getattr(info, "trade_stops_level", 0) or 0) * float(
        getattr(info, "point", 0.0) or 0.0
    )


def _filling_modes(info: Any) -> list[int]:
    """Ordered filling modes the symbol accepts, IOC first for market orders."""
    mask = int(getattr(info, "filling_mode", 0) or 0)
    modes: list[int] = []
    if mask & 2:
        modes.append(mt5.ORDER_FILLING_IOC)
    if mask & 1:
        modes.append(mt5.ORDER_FILLING_FOK)
    modes.append(mt5.ORDER_FILLING_RETURN)
    return modes


def _validate_stops(side: str, price: float, stop_loss: float | None,
                    take_profit: float | None, info: Any) -> None:
    is_buy = side == "buy"
    min_distance = _stops_distance(info)
    if stop_loss:
        if is_buy and stop_loss >= price:
            raise BridgeError("stop-loss must be below the entry price for a buy")
        if not is_buy and stop_loss <= price:
            raise BridgeError("stop-loss must be above the entry price for a sell")
        if min_distance and abs(price - stop_loss) < min_distance:
            raise BridgeError(
                f"stop-loss is inside the broker's minimum stop distance "
                f"({min_distance:g}) for this symbol"
            )
    if take_profit:
        if is_buy and take_profit <= price:
            raise BridgeError("take-profit must be above the entry price for a buy")
        if not is_buy and take_profit >= price:
            raise BridgeError("take-profit must be below the entry price for a sell")
        if min_distance and abs(take_profit - price) < min_distance:
            raise BridgeError(
                f"take-profit is inside the broker's minimum stop distance "
                f"({min_distance:g}) for this symbol"
            )


def _protective_kind(stop_loss: float | None, take_profit: float | None) -> str:
    if stop_loss and take_profit:
        return "bracket"
    if stop_loss:
        return "stop_loss"
    if take_profit:
        return "take_profit"
    return "none"


def resolve_symbol(mt: Any, symbol: str, suffix: str) -> tuple[str, Any]:
    """Resolve an ORQEVA symbol (EURUSD, XAU/USD) to the broker's exact name."""
    base = normalize_symbol(symbol)
    if not base:
        raise BridgeError("symbol is required")

    # MT5 symbol names are case-sensitive and brokers suffix them inconsistently
    # (EURUSDm, XAUUSDm, EURUSD.a), so probe the plausible spellings in order.
    candidates: list[str] = []
    seen: set[str] = set()
    for spelling in (base, base.upper(), base.lower()):
        for name in (spelling, f"{spelling}{suffix}", f"{spelling}{suffix.upper()}",
                     f"{spelling}{suffix.lower()}"):
            if name and name not in seen:
                seen.add(name)
                candidates.append(name)

    for name in candidates:
        info = mt.symbol_info(name)
        if info is None:
            continue
        if not getattr(info, "visible", True):
            mt.symbol_select(name, True)
            info = mt.symbol_info(name) or info
        return name, info

    matches = mt.symbols_get(f"*{base}*") or []
    for item in matches:
        name = getattr(item, "name", "")
        if not name:
            continue
        info = mt.symbol_info(name)
        if info is not None:
            if not getattr(info, "visible", True):
                mt.symbol_select(name, True)
                info = mt.symbol_info(name) or info
            return name, info

    raise BridgeError(
        f"{base} is not available on this account (tried {', '.join(candidates)})"
    )


# ------------------------------------------------------------- MT5 session

def _load_mt5() -> Any:
    if mt5 is None:
        raise BridgeError(
            "MetaTrader5 is not installed - run pip install -r bridge/requirements.txt "
            "on the Windows host"
        )
    return mt5


@contextmanager
def terminal_session(login: str, password: str, server: str):
    mt = _load_mt5()
    try:
        login_int = int(str(login).strip())
    except (TypeError, ValueError):
        raise BridgeError("MT5 login must be the numeric account number")
    if not password or not server:
        raise BridgeError("MT5 password and server are required")

    kwargs: dict[str, Any] = {
        "login": login_int,
        "password": password,
        "server": server,
        "timeout": _INIT_TIMEOUT_MS,
        "portable": False,
    }
    path = os.getenv("MT5_TERMINAL_PATH", "").strip()
    if path:
        kwargs["path"] = path

    with _LOCK:
        if not mt.initialize(**kwargs):
            code, message = mt.last_error()
            raise BridgeError(
                f"MT5 login failed [{code}]: {message}. Start the Exness terminal, "
                "log in once, and enable Tools > Options > Expert Advisors > "
                "Allow algorithmic trading."
            )
        try:
            yield mt
        finally:
            mt.shutdown()


def _account_payload(mt: Any) -> dict[str, Any]:
    info = mt.account_info()
    if info is None:
        raise BridgeError("MT5 could not read account information")
    mode = getattr(info, "trade_mode", None)
    return {
        "login": str(getattr(info, "login", "") or ""),
        "server": getattr(info, "server", "") or "",
        "company": getattr(info, "company", "") or "",
        "currency": getattr(info, "currency", "USD") or "USD",
        "balance": float(getattr(info, "balance", 0) or 0),
        "equity": float(getattr(info, "equity", 0) or 0),
        "margin_free": float(getattr(info, "margin_free", 0) or 0),
        "leverage": int(getattr(info, "leverage", 0) or 0),
        "trade_mode": {0: "demo", 1: "contest", 2: "real"}.get(mode, "unknown"),
        "open_positions": int(mt.positions_total() or 0),
    }


# ------------------------------------------------------------------- models

class Credentials(BaseModel):
    login: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=1, max_length=256)
    server: str = Field(default="", max_length=128)

    def resolved_server(self) -> str:
        return (self.server or os.getenv("MT5_DEFAULT_SERVER", "")).strip()


class OrderBody(Credentials):
    symbol: str = Field(..., min_length=1, max_length=32)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity_units: float = Field(..., gt=0)
    order_type: str = Field(default="market", pattern="^(market|limit)$")
    limit_price: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    take_profit: float | None = Field(default=None, gt=0)
    comment: str = Field(default="ORQEVA", max_length=31)


class CloseBody(Credentials):
    symbol: str = Field(..., min_length=1, max_length=32)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity_units: float = Field(..., gt=0)


# --------------------------------------------------------------- auth guard

def require_token(x_bridge_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("MT5_BRIDGE_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503,
                            detail="MT5_BRIDGE_TOKEN is not configured on the bridge")
    if not x_bridge_token or not hmac.compare_digest(x_bridge_token, expected):
        raise HTTPException(status_code=401, detail="invalid bridge token")


# -------------------------------------------------------------------- routes

@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness probe - deliberately exposes nothing account-specific."""
    return {"status": "ok", "mt5_available": mt5 is not None}


@app.post("/validate", dependencies=[Depends(require_token)])
def validate(body: Credentials) -> dict[str, Any]:
    try:
        with terminal_session(body.login, body.password, body.resolved_server()) as mt:
            account = _account_payload(mt)
        return {"ok": True, "detail": "account reachable", "account": account}
    except BridgeError as e:
        return {"ok": False, "detail": str(e)}
    except Exception as e:  # noqa: BLE001 - never 500 with a stack trace
        return {"ok": False, "detail": f"bridge error: {str(e)[:200]}"}


@app.post("/account", dependencies=[Depends(require_token)])
def account(body: Credentials) -> dict[str, Any]:
    try:
        with terminal_session(body.login, body.password, body.resolved_server()) as mt:
            return {"ok": True, "account": _account_payload(mt)}
    except BridgeError as e:
        return {"ok": False, "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"bridge error: {str(e)[:200]}"}


@app.post("/order", dependencies=[Depends(require_token)])
def order(body: OrderBody) -> dict[str, Any]:
    try:
        with terminal_session(body.login, body.password, body.resolved_server()) as mt:
            return _send_order(mt, body)
    except BridgeError as e:
        return {"ok": False, "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"bridge error: {str(e)[:200]}"}


@app.post("/close", dependencies=[Depends(require_token)])
def close(body: CloseBody) -> dict[str, Any]:
    try:
        with terminal_session(body.login, body.password, body.resolved_server()) as mt:
            return _close_positions(mt, body)
    except BridgeError as e:
        return {"ok": False, "detail": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"bridge error: {str(e)[:200]}"}


# ------------------------------------------------------------ order helpers

def _send_order(mt: Any, body: OrderBody) -> dict[str, Any]:
    suffix = os.getenv("MT5_SYMBOL_SUFFIX", "m")
    magic = int(os.getenv("MT5_MAGIC", "20261021"))
    deviation = int(os.getenv("MT5_DEVIATION", "20"))
    symbol, info = resolve_symbol(mt, body.symbol, suffix)

    lots = units_to_lots(
        body.quantity_units, _contract_size(info),
        float(getattr(info, "volume_min", 0.01) or 0.01),
        float(getattr(info, "volume_max", 100.0) or 100.0),
        float(getattr(info, "volume_step", 0.01) or 0.01),
    )

    tick = mt.symbol_info_tick(symbol)
    if tick is None:
        raise BridgeError(f"no live quote for {symbol} - is the market open?")

    pending = body.order_type == "limit"
    if pending:
        if not body.limit_price:
            raise BridgeError("limit orders require limit_price")
        price = _round(body.limit_price, info)
    else:
        price = float(tick.ask if body.side == "buy" else tick.bid)

    stop_loss = _round(body.stop_loss, info) if body.stop_loss else None
    take_profit = _round(body.take_profit, info) if body.take_profit else None
    _validate_stops(body.side, price, stop_loss, take_profit, info)

    if pending:
        action = mt.TRADE_ACTION_PENDING
        order_type = (mt.ORDER_TYPE_BUY_LIMIT if body.side == "buy"
                      else mt.ORDER_TYPE_SELL_LIMIT)
    else:
        action = mt.TRADE_ACTION_DEAL
        order_type = mt.ORDER_TYPE_BUY if body.side == "buy" else mt.ORDER_TYPE_SELL

    request: dict[str, Any] = {
        "action": action,
        "symbol": symbol,
        "volume": lots,
        "type": order_type,
        "price": price,
        "sl": stop_loss or 0.0,
        "tp": take_profit or 0.0,
        "deviation": deviation,
        "magic": magic,
        "comment": body.comment or "ORQEVA",
        "type_time": mt.ORDER_TIME_GTC,
    }

    result = None
    for filling in _filling_modes(info):
        request["type_filling"] = filling
        result = mt.order_send(request)
        if result is None:
            code, message = mt.last_error()
            raise BridgeError(f"MT5 order_send failed [{code}]: {message}")
        if result.retcode != _INVALID_FILL:
            break

    if result is None:
        raise BridgeError("MT5 returned no order result")
    if result.retcode not in _SUCCESS_RETCODES:
        raise BridgeError(
            f"MT5 rejected order [{result.retcode}]: {result.comment or 'no reason given'}"
        )

    ticket = getattr(result, "order", 0) or getattr(result, "deal", 0)
    return {
        "ok": True,
        "broker_order_id": str(ticket or ""),
        "broker_status": "PENDING" if pending else "FILLED",
        "filled_price": None if pending else float(getattr(result, "price", 0) or price),
        "protective": _protective_kind(stop_loss, take_profit),
        "detail": getattr(result, "comment", "") or "",
        "symbol": symbol,
        "volume": lots,
    }


def _close_positions(mt: Any, body: CloseBody) -> dict[str, Any]:
    suffix = os.getenv("MT5_SYMBOL_SUFFIX", "m")
    magic = int(os.getenv("MT5_MAGIC", "20261021"))
    deviation = int(os.getenv("MT5_DEVIATION", "20"))
    symbol, info = resolve_symbol(mt, body.symbol, suffix)

    contract = _contract_size(info)
    step = float(getattr(info, "volume_step", 0.01) or 0.01)
    vol_min = float(getattr(info, "volume_min", 0.01) or 0.01)
    want_lots = units_to_lots(
        body.quantity_units, contract, vol_min,
        float(getattr(info, "volume_max", 100.0) or 100.0), step,
    )

    position_type = mt.POSITION_TYPE_BUY if body.side == "buy" else mt.POSITION_TYPE_SELL
    positions = [
        p for p in (mt.positions_get(symbol=symbol) or [])
        if p.type == position_type and int(getattr(p, "magic", 0) or 0) == magic
    ]
    if not positions:
        raise BridgeError(
            f"no open ORQEVA position on {symbol} to close - close it manually in MT5"
        )
    positions.sort(key=lambda p: getattr(p, "time", 0))

    remaining = want_lots
    closed_lots = 0.0
    tickets: list[str] = []
    for position in positions:
        if remaining <= 1e-9:
            break
        volume = min(remaining, float(getattr(position, "volume", 0) or 0))
        volume = math.floor(volume / step + 1e-6) * step
        volume = round(volume, 8)
        if volume < vol_min:
            volume = float(getattr(position, "volume", 0) or 0)
            if volume < vol_min:
                continue
        tick = mt.symbol_info_tick(symbol)
        if tick is None:
            raise BridgeError(f"no live quote for {symbol} - cannot close")
        close_type = (mt.ORDER_TYPE_SELL if position.type == mt.POSITION_TYPE_BUY
                      else mt.ORDER_TYPE_BUY)
        price = float(tick.bid if position.type == mt.POSITION_TYPE_BUY else tick.ask)
        request = {
            "action": mt.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "position": position.ticket,
            "volume": volume,
            "type": close_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": "ORQEVA close",
            "type_time": mt.ORDER_TIME_GTC,
        }
        result = None
        for filling in _filling_modes(info):
            request["type_filling"] = filling
            result = mt.order_send(request)
            if result is None:
                code, message = mt.last_error()
                raise BridgeError(f"MT5 close failed [{code}]: {message}")
            if result.retcode != _INVALID_FILL:
                break
        if result is None or result.retcode not in _SUCCESS_RETCODES:
            reason = getattr(result, "comment", "") if result else "no result"
            code = getattr(result, "retcode", "?") if result else "?"
            raise BridgeError(f"MT5 rejected close [{code}]: {reason}")
        closed_lots += volume
        remaining -= volume
        tickets.append(str(getattr(result, "order", 0) or getattr(result, "deal", 0) or ""))

    if closed_lots <= 0:
        raise BridgeError("no closable volume was found on the broker position")

    return {
        "ok": True,
        "broker_order_id": tickets[-1] if tickets else "",
        "broker_status": "FILLED",
        "filled_price": None,
        "protective": "none",
        "closed_volume_units": round(closed_lots * contract, 8),
        "tickets": tickets,
        "detail": f"closed {closed_lots:g} lots on {symbol}",
    }
