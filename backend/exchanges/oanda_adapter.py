"""OANDA v20 (forex) adapter - bearer token REST."""
from typing import Any

import requests

from backend.exchanges.base import BaseAdapter

_TIMEOUT = 10


class OandaAdapter(BaseAdapter):
    name = "oanda"
    display_name = "OANDA"
    markets = ["forex"]
    needs_secret = False  # single API token; stored in api_key field
    supports_order_routing = True

    def _base(self, is_paper: bool) -> str:
        return "https://api-fxpractice.oanda.com" if is_paper else "https://api-fxtrade.oanda.com"

    def _get(self, api_key: str, is_paper: bool, path: str) -> dict:
        r = requests.get(
            f"{self._base(is_paper)}{path}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
        return r.json()

    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        try:
            accounts = self._get(api_key, is_paper, "/v3/accounts").get("accounts", [])
            ok = len(accounts) > 0
            return {"ok": ok, "detail": f"{len(accounts)} account(s)" if ok else "no linked accounts"}
        except Exception as e:
            return self._net_unavailable(e)

    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        accounts = self._get(api_key, is_paper, "/v3/accounts")["accounts"]
        if not accounts:
            raise RuntimeError("no linked OANDA accounts")
        acct_id = accounts[0]["id"]
        details = self._get(api_key, is_paper, f"/v3/accounts/{acct_id}")["account"]
        balance = float(details.get("balance", 0))
        unrealized = float(details.get("unrealizedPL", 0))
        return {
            "account_id": acct_id,
            "currency": details.get("currency", "USD"),
            "environment": "practice" if is_paper else "live",
            "balance": balance,
            "unrealized_pl": unrealized,
            "open_trade_count": int(details.get("openTradeCount", 0)),
        }

    @staticmethod
    def to_oanda_instrument(symbol: str) -> str:
        """EURUSD -> EUR_USD"""
        s = symbol.upper().replace("/", "").replace("-", "")
        return f"{s[:3]}_{s[3:]}" if len(s) == 6 else s

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        accounts = self._get(api_key, is_paper, "/v3/accounts")["accounts"]
        if not accounts:
            raise RuntimeError("no linked OANDA accounts")
        acct_id = accounts[0]["id"]

        units = int(quantity * (1 if side.lower() == "buy" else -1) * 100)  # base units
        order_body: dict[str, Any] = {
            "order": {
                "instrument": self.to_oanda_instrument(symbol),
                "units": f"{units:+d}",
                "type": "MARKET" if order_type != "limit" else "LIMIT",
                "timeInForce": "FOK" if order_type != "limit" else "GTC",
                "positionFill": "DEFAULT",
            }
        }
        if order_type == "limit":
            if not limit_price or limit_price <= 0:
                raise RuntimeError("limit orders require limit_price")
            order_body["order"]["price"] = f"{limit_price:.5f}"

        protective = []
        if stop_loss and stop_loss > 0:
            order_body["order"]["stopLossOnFill"] = {
                "price": f"{float(stop_loss):.5f}", "timeInForce": "GTC"}
            protective.append("stop-loss")
        if take_profit and take_profit > 0:
            order_body["order"]["takeProfitOnFill"] = {
                "price": f"{float(take_profit):.5f}", "timeInForce": "GTC"}
            protective.append("take-profit")

        r = requests.post(
            f"{self._base(is_paper)}/v3/accounts/{acct_id}/orders",
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json=order_body, timeout=_TIMEOUT,
        )
        body = r.json()
        if r.status_code != 201:
            raise RuntimeError(body.get("errorMessage", f"HTTP {r.status_code}"))
        created = body.get("orderCreateTransaction", {})
        return {
            "ok": True,
            "broker_order_id": str(created.get("id") or body.get("orderFillTransaction", {}).get("id", "")),
            "broker_status": "FILLED" if body.get("orderFillTransaction") else "PENDING",
            "filled_price": float(body["orderFillTransaction"]["price"])
            if body.get("orderFillTransaction") else None,
            "protective": "+".join(protective) or None,
        }
