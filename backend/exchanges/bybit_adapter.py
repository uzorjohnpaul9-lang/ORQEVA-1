"""Bybit (crypto) adapter - v5 REST, Demo Trading and live.

``is_paper=True`` uses https://api-demo.bybit.com (a Demo Trading account and
demo API key); ``False`` uses https://api.bybit.com. Crypto signals execute on
USDT linear perpetuals so long and short signals both work and TP/SL are
attached at the venue.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from typing import Any

import requests

from backend.exchanges.base import BaseAdapter

_DEMO_API = "https://api-demo.bybit.com"
_LIVE_API = "https://api.bybit.com"
_TIMEOUT = 10
_RECV_WINDOW = "20000"
_CATEGORY = "linear"
_INSTRUMENT_TTL = 3600


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class BybitAdapter(BaseAdapter):
    name = "bybit"
    display_name = "Bybit"
    markets = ["crypto"]
    needs_secret = True
    supports_order_routing = True
    supports_position_close = True
    key_label = "API Key"
    key_hint = ("Bybit API key - use a Demo Trading key with Contract Trade "
                "permission when Paper mode is on")
    secret_label = "API Secret"

    def __init__(self):
        self._instruments: dict[str, tuple[float, dict]] = {}

    @staticmethod
    def _base(is_paper: bool) -> str:
        env = "BYBIT_DEMO_BASE_URL" if is_paper else "BYBIT_LIVE_BASE_URL"
        default = _DEMO_API if is_paper else _LIVE_API
        return (os.getenv(env) or default).rstrip("/")

    # Bybit lists these as 1000-unit contracts, so qty/prices are scaled.
    SCALED_SYMBOLS = {
        "PEPE": ("1000PEPEUSDT", 1000.0),
        "SHIB": ("SHIB1000USDT", 1000.0),
        "BONK": ("1000BONKUSDT", 1000.0),
        "FLOKI": ("1000FLOKIUSDT", 1000.0),
    }

    @classmethod
    def to_symbol(cls, symbol: str) -> str:
        """BTC/USD -> BTCUSDT; ETHUSDT -> ETHUSDT; SOL-USDC -> SOLUSDC."""
        s = "".join(ch for ch in (symbol or "").upper() if ch.isalnum())
        base = ""
        if s.endswith("USDT"):
            base = s[:-4]
        elif s.endswith("USDC"):
            base = s[:-4]
        elif s.endswith("USD"):
            base = s[:-3]
        if base in cls.SCALED_SYMBOLS:
            return cls.SCALED_SYMBOLS[base][0]
        if s.endswith("USDT") or s.endswith("USDC"):
            return s
        if s.endswith("USD"):
            return f"{s}T"
        return s

    @classmethod
    def _scale(cls, symbol: str) -> float:
        mapped = cls.to_symbol(symbol)
        for bybit_symbol, scale in cls.SCALED_SYMBOLS.values():
            if bybit_symbol == mapped:
                return scale
        return 1.0

    @staticmethod
    def _sign(secret: str, timestamp: str, api_key: str, recv_window: str,
              payload: str) -> str:
        message = f"{timestamp}{api_key}{recv_window}{payload}"
        return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def _request(self, api_key: str, api_secret: str, is_paper: bool,
                 method: str, path: str, params: dict[str, Any] | None = None,
                 signed: bool = True) -> dict:
        params = dict(params or {})
        base = self._base(is_paper)
        method = method.upper()
        headers = {"Content-Type": "application/json"}
        query = urllib.parse.urlencode(params)
        body = json.dumps(params, separators=(",", ":")) if params else ""

        if signed:
            timestamp = str(int(time.time() * 1000))
            payload = query if method == "GET" else body
            headers.update({
                "X-BAPI-API-KEY": api_key,
                "X-BAPI-TIMESTAMP": timestamp,
                "X-BAPI-RECV-WINDOW": _RECV_WINDOW,
                "X-BAPI-SIGN": self._sign(api_secret, timestamp, api_key,
                                          _RECV_WINDOW, payload),
                "X-BAPI-SIGN-TYPE": "2",
            })

        url = f"{base}{path}"
        if method == "GET":
            if query:
                url = f"{url}?{query}"
            response = requests.get(url, headers=headers, timeout=_TIMEOUT)
        else:
            response = requests.request(method, url, headers=headers,
                                        data=body, timeout=_TIMEOUT)

        try:
            payload = response.json()
        except ValueError:
            raise RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")

        code = payload.get("retCode") if isinstance(payload, dict) else None
        if code not in (0, "0", None):
            message = payload.get("retMsg") if isinstance(payload, dict) else payload
            raise RuntimeError(f"{code}: {message}"[:200])
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}: {str(payload)[:150]}")
        return payload.get("result", {}) if isinstance(payload, dict) else {}

    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        try:
            info = self._request(api_key, api_secret, is_paper, "GET", "/v5/user/query-api")
            if info.get("readOnly"):
                return {"ok": False, "detail": "Bybit API key is read-only; enable trade permission"}
            mode = "demo" if is_paper else "live"
            return {"ok": True, "detail": f"Bybit {mode} API key reachable"}
        except Exception as e:
            return self._net_unavailable(e)

    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        result = self._request(api_key, api_secret, is_paper, "GET",
                               "/v5/account/wallet-balance", {"accountType": "UNIFIED"})
        accounts = result.get("list") or []
        if not accounts:
            raise RuntimeError("Bybit returned no account data")
        account = accounts[0]
        equity = (_to_float(account.get("totalEquity"))
                  or _to_float(account.get("totalMarginBalance"))
                  or _to_float(account.get("totalWalletBalance")))
        balance = _to_float(account.get("totalWalletBalance")) or equity
        balances = {}
        for coin in account.get("coin") or []:
            value = _to_float(coin.get("usdValue")) or _to_float(coin.get("walletBalance"))
            if value > 0:
                balances[coin.get("coin") or "?"] = value
        return {
            "type": account.get("accountType") or "UNIFIED",
            "currency": "USD",
            "equity": equity,
            "balance": balance,
            "buying_power": _to_float(account.get("totalAvailableBalance")),
            "balances": dict(sorted(balances.items(), key=lambda kv: -kv[1])[:20]),
        }

    def _instrument(self, is_paper: bool, symbol: str) -> dict:
        now = time.monotonic()
        cached = self._instruments.get(symbol)
        if cached and now - cached[0] < _INSTRUMENT_TTL:
            return cached[1]
        result = self._request("", "", is_paper, "GET", "/v5/market/instruments-info",
                               {"category": _CATEGORY, "symbol": symbol}, signed=False)
        items = result.get("list") or []
        if not items:
            raise RuntimeError(f"Bybit has no {_CATEGORY} instrument for {symbol}")
        info = items[0]
        if str(info.get("status") or "").lower() != "trading":
            raise RuntimeError(f"Bybit {symbol} is not trading ({info.get('status')})")
        self._instruments[symbol] = (now, info)
        return info

    @staticmethod
    def _round_qty(quantity: float, step: str) -> Decimal:
        return Decimal(str(quantity)).quantize(Decimal(str(step or "0.001")),
                                               rounding=ROUND_DOWN)

    @staticmethod
    def _format_qty(quantity: Decimal, step: str) -> str:
        decimals = max(0, -Decimal(str(step or "0.001")).as_tuple().exponent)
        return f"{quantity:.{decimals}f}"

    @staticmethod
    def _format_price(price: float, tick: str) -> str:
        tick_size = Decimal(str(tick or "0.01"))
        value = Decimal(str(price)).quantize(tick_size, rounding=ROUND_HALF_UP)
        decimals = max(0, -tick_size.as_tuple().exponent)
        return f"{value:.{decimals}f}"

    def _filled_price(self, api_key: str, api_secret: str, is_paper: bool,
                      symbol: str, order_id: str) -> float | None:
        if not order_id:
            return None
        for _ in range(3):
            try:
                result = self._request(api_key, api_secret, is_paper, "GET",
                                       "/v5/order/realtime",
                                       {"category": _CATEGORY, "symbol": symbol,
                                        "orderId": order_id})
                orders = result.get("list") or []
                if orders:
                    order = orders[0]
                    avg = _to_float(order.get("avgPrice"))
                    if avg > 0:
                        return avg
                    value = _to_float(order.get("cumExecValue"))
                    qty = _to_float(order.get("cumExecQty"))
                    if value > 0 and qty > 0:
                        return value / qty
            except Exception:
                pass
            time.sleep(0.25)
        return None

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        bybit_symbol = self.to_symbol(symbol)
        scale = self._scale(symbol)
        info = self._instrument(is_paper, bybit_symbol)
        lot = info.get("lotSizeFilter") or {}
        step = lot.get("qtyStep") or "0.001"
        qty = self._round_qty(quantity / scale, step)
        min_qty = _to_float(lot.get("minOrderQty"))
        max_qty = _to_float(lot.get("maxOrderQty"))
        if qty <= 0 or (min_qty and float(qty) < min_qty):
            raise RuntimeError(
                f"quantity {quantity} is below Bybit minimum {min_qty * scale:g} "
                f"for {bybit_symbol}")
        if max_qty and float(qty) > max_qty:
            raise RuntimeError(
                f"quantity {quantity} exceeds Bybit maximum {max_qty * scale:g} "
                f"for {bybit_symbol}")

        tick = (info.get("priceFilter") or {}).get("tickSize") or "0.01"
        payload: dict[str, Any] = {
            "category": _CATEGORY,
            "symbol": bybit_symbol,
            "side": "Buy" if side.lower() == "buy" else "Sell",
            "orderType": "Limit" if order_type == "limit" else "Market",
            "qty": self._format_qty(qty, step),
            "positionIdx": 0,
        }
        if order_type == "limit":
            if not limit_price or limit_price <= 0:
                raise RuntimeError("limit orders require limit_price")
            scaled_limit = float(limit_price) * scale
            payload["price"] = self._format_price(scaled_limit, tick)
            payload["timeInForce"] = "GTC"
            min_notional = _to_float(lot.get("minNotionalValue"))
            if min_notional and float(qty) * scaled_limit < min_notional:
                raise RuntimeError(
                    f"order notional is below Bybit minimum {min_notional} USDT")
        else:
            payload["timeInForce"] = "IOC"

        protective = None
        if stop_loss and stop_loss > 0:
            payload["stopLoss"] = self._format_price(float(stop_loss) * scale, tick)
        if take_profit and take_profit > 0:
            payload["takeProfit"] = self._format_price(float(take_profit) * scale, tick)
        if stop_loss and stop_loss > 0 and take_profit and take_profit > 0:
            protective = "bracket"
        elif stop_loss and stop_loss > 0:
            protective = "stop_loss"
        elif take_profit and take_profit > 0:
            protective = "take_profit"
        if protective:
            payload["tpslMode"] = "Full"
            payload["tpTriggerBy"] = "LastPrice"
            payload["slTriggerBy"] = "LastPrice"
            if take_profit and take_profit > 0:
                payload["tpOrderType"] = "Market"
            if stop_loss and stop_loss > 0:
                payload["slOrderType"] = "Market"

        result = self._request(api_key, api_secret, is_paper, "POST",
                               "/v5/order/create", payload)
        order_id = str(result.get("orderId") or "")
        filled = self._filled_price(api_key, api_secret, is_paper,
                                    bybit_symbol, order_id)
        return {
            "ok": True,
            "broker_order_id": order_id,
            "broker_status": "submitted",
            "filled_price": (filled / scale) if filled else None,
            "protective": protective,
        }

    def close_positions(self, api_key: str, api_secret: str, is_paper: bool, *,
                        symbol: str, side: str, quantity: float) -> dict:
        bybit_symbol = self.to_symbol(symbol)
        result = self._request(api_key, api_secret, is_paper, "GET",
                               "/v5/position/list",
                               {"category": _CATEGORY, "symbol": bybit_symbol})
        target_side = "Buy" if (side or "").lower() == "buy" else "Sell"
        position = next(
            (p for p in (result.get("list") or [])
             if str(p.get("side")) == target_side and _to_float(p.get("size")) > 0),
            None,
        )
        if position is None:
            return {"ok": False, "detail": "no open position"}

        info = self._instrument(is_paper, bybit_symbol)
        step = (info.get("lotSizeFilter") or {}).get("qtyStep") or "0.001"
        close_qty = self._round_qty(_to_float(position.get("size")) or quantity, step)
        payload = {
            "category": _CATEGORY,
            "symbol": bybit_symbol,
            "side": "Sell" if target_side == "Buy" else "Buy",
            "orderType": "Market",
            "qty": self._format_qty(close_qty, step),
            "positionIdx": int(position.get("positionIdx") or 0),
            "reduceOnly": True,
        }
        created = self._request(api_key, api_secret, is_paper, "POST",
                                "/v5/order/create", payload)
        order_id = str(created.get("orderId") or "")
        filled = self._filled_price(api_key, api_secret, is_paper,
                                    bybit_symbol, order_id)
        return {
            "ok": True,
            "broker_order_id": order_id,
            "broker_status": "submitted",
            "filled_price": (filled / self._scale(symbol)) if filled else None,
        }


def bybit_signature_for_tests(secret: str, timestamp: str, api_key: str,
                              recv_window: str, payload: str) -> str:
    return BybitAdapter._sign(secret, timestamp, api_key, recv_window, payload)
