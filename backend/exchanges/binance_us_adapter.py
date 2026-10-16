"""Binance.US (crypto) adapter - HMAC-SHA256 signed REST, stdlib only.

api.binance.us is the US-reachable venue (api.binance.com blocks US cloud
IPs), so this is the Binance flavour offered as a brokerage option.
"""
import hashlib
import hmac
import time
import urllib.parse
from typing import Any

import requests

from backend.exchanges.base import BaseAdapter

_API = "https://api.binance.us"
_TIMEOUT = 10


class BinanceUSAdapter(BaseAdapter):
    name = "binance_us"
    display_name = "Binance.US"
    markets = ["crypto"]
    needs_secret = True
    supports_order_routing = True

    @staticmethod
    def to_symbol(symbol: str) -> str:
        """BTC/USD -> BTCUSD; DOGE/USDT -> DOGEUSDT."""
        s = symbol.upper().replace("/", "").replace("-", "")
        if s.endswith("USDT") or s.endswith("USDC") or s.endswith("USD"):
            return s
        return f"{s}USD"

    @staticmethod
    def _sign(secret: str, query: str) -> str:
        return hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    def _request(self, api_key: str, api_secret: str, method: str, path: str,
                 params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        query = urllib.parse.urlencode(params)
        params["signature"] = self._sign(api_secret, query)
        headers = {"X-MBX-APIKEY": api_key}
        r = requests.request(method, f"{_API}{path}", params=params, headers=headers, timeout=_TIMEOUT)
        try:
            body = r.json()
        except ValueError:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
        if isinstance(body, dict) and body.get("code") not in (None, 0):
            raise RuntimeError(str(body.get("msg", body))[:150])
        if r.status_code >= 400:
            raise RuntimeError(str(body)[:150])
        return body

    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        try:
            self._request(api_key, api_secret, "GET", "/api/v3/account")
            return {"ok": True, "detail": "account endpoint reachable"}
        except Exception as e:
            return self._net_unavailable(e)

    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        data = self._request(api_key, api_secret, "GET", "/api/v3/account")
        balances: dict[str, float] = {}
        for b in data.get("balances", []):
            try:
                free = float(b.get("free", 0) or 0)
            except (TypeError, ValueError):
                continue
            if free > 0:
                balances[b.get("asset", "?")] = free
        return {"type": "spot", "balances": dict(sorted(balances.items(), key=lambda kv: -kv[1])[:20])}

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        params: dict[str, Any] = {
            "symbol": self.to_symbol(symbol),
            "side": side.upper(),
            "quantity": f"{quantity:.8f}",
        }
        if order_type == "limit":
            if not limit_price or limit_price <= 0:
                raise RuntimeError("limit orders require limit_price")
            params["type"] = "LIMIT"
            params["timeInForce"] = "GTC"
            params["price"] = f"{limit_price:.8f}".rstrip("0").rstrip(".")
        else:
            params["type"] = "MARKET"

        result = self._request(api_key, api_secret, "POST", "/api/v3/order", params)

        protective = []
        protective_error: str | None = None
        if stop_loss and stop_loss > 0:
            try:
                self._submit_stop(api_key, api_secret, symbol, side, quantity, float(stop_loss))
                protective.append("stop-loss")
            except Exception as e:  # keep the confirmed entry usable
                protective_error = str(e)[:150]

        return {
            "ok": True,
            "broker_order_id": str(result.get("orderId", "")),
            "broker_status": str(result.get("status", ""))[:40],
            "filled_price": None,
            "protective": "+".join(protective) or None,
            "protective_error": protective_error,
        }

    def _submit_stop(self, api_key: str, api_secret: str, symbol: str, side: str,
                     quantity: float, stop_price: float) -> None:
        """Standalone STOP_LOSS (market) order for the opposite direction."""
        opposite = "SELL" if side.lower() == "buy" else "BUY"
        params = {
            "symbol": self.to_symbol(symbol),
            "side": opposite,
            "type": "STOP_LOSS",
            "quantity": f"{quantity:.8f}",
            "stopPrice": f"{stop_price:.8f}".rstrip("0").rstrip("."),
        }
        self._request(api_key, api_secret, "POST", "/api/v3/order", params)
