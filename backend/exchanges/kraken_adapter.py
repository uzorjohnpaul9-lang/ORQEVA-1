"""Kraken (crypto) adapter - pure stdlib HMAC-SHA512 signing."""
import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any

import requests

from backend.exchanges.base import BaseAdapter

_API = "https://api.kraken.com"
_TIMEOUT = 10


class KrakenAdapter(BaseAdapter):
    name = "kraken"
    display_name = "Kraken"
    markets = ["crypto"]
    needs_secret = True
    supports_order_routing = True

    # Kraken uses XBT for BTC
    SYMBOL_MAP = {"BTC": "XBT"}

    @classmethod
    def to_kraken_pair(cls, symbol: str) -> str:
        s = symbol.upper().replace("/", "").replace("-", "")
        for src, dst in cls.SYMBOL_MAP.items():
            if s.startswith(src):
                s = dst + s[len(src):]
                break
        return s

    @staticmethod
    def _sign(secret_b64: str, path: str, nonce: str, postdata: str) -> str:
        encoded = (nonce + postdata).encode()
        msg = path.encode() + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(secret_b64), msg, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode()

    def _private(self, api_key: str, api_secret: str, endpoint: str) -> dict:
        path = f"/0/private/{endpoint}"
        nonce = str(int(time.time() * 1000))
        postdata = urllib.parse.urlencode({"nonce": nonce})
        headers = {
            "API-Key": api_key,
            "API-Sign": self._sign(api_secret, path, nonce, postdata),
        }
        r = requests.post(f"{_API}{path}", data={"nonce": nonce}, headers=headers, timeout=_TIMEOUT)
        body = r.json()
        if body.get("error"):
            raise RuntimeError("; ".join(body["error"])[:150])
        return body["result"]

    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        try:
            self._private(api_key, api_secret, "Balance")
            return {"ok": True, "detail": "balance endpoint reachable"}
        except Exception as e:
            return self._net_unavailable(e)

    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        balances = self._private(api_key, api_secret, "Balance")
        # trim to non-dust entries for a compact snapshot
        filtered = {k: float(v) for k, v in balances.items() if float(v) > 0}
        return {"type": "spot", "balances": dict(sorted(filtered.items(), key=lambda kv: -kv[1])[:20])}

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        path = "/0/private/AddOrder"
        nonce = str(int(time.time() * 1000))
        params = {
            "nonce": nonce,
            "pair": self.to_kraken_pair(symbol),
            "type": side.lower(),
            "ordertype": "limit" if order_type == "limit" else "market",
            "volume": f"{quantity:.8f}",
        }
        if order_type == "limit":
            if not limit_price or limit_price <= 0:
                raise RuntimeError("limit orders require limit_price")
            params["price"] = f"{limit_price:.8f}".rstrip("0").rstrip(".")

        # Protective orders attached to the entry (Kraken close[...] syntax).
        protective = []
        if stop_loss and stop_loss > 0:
            params["close[ordertype]"] = "stop-loss"
            params["close[price]"] = f"{float(stop_loss):.8f}".rstrip("0").rstrip(".")
            protective.append("stop-loss")
        if take_profit and take_profit > 0:
            params["close[ordertype]"] = "take-profit" if not protective else "stop-loss-loss"
            params["close[price]"] = f"{float(take_profit):.8f}".rstrip("0").rstrip(".")
            if not protective:
                protective.append("take-profit")
            else:
                # stop-loss-loss = stop loss + take profit combo
                params["close[price]"] = (
                    f"{float(stop_loss):.8f},{float(take_profit):.8f}")
                protective[-1] = "stop+tp"

        postdata = urllib.parse.urlencode(params)
        headers = {
            "API-Key": api_key,
            "API-Sign": self._sign(api_secret, path, nonce, postdata),
        }
        r = requests.post(f"{_API}{path}", data=params, headers=headers, timeout=_TIMEOUT)
        body = r.json()
        if body.get("error"):
            raise RuntimeError("; ".join(body["error"])[:150])
        result = body.get("result", {})
        return {
            "ok": True,
            "broker_order_id": (result.get("txid") or [""])[0],
            "broker_status": result.get("descr", {}).get("order", "")[:40],
            "filled_price": None,
            "protective": "+".join(protective) or None,
        }


def kraken_signature_for_tests(secret_b64: str, path: str, nonce: str, postdata: str) -> str:
    """Exposed for unit tests."""
    return KrakenAdapter._sign(secret_b64, path, nonce, postdata)
