"""Alpaca (stocks) adapter - paper & live."""
from typing import Any

from backend.exchanges.base import BaseAdapter


class AlpacaAdapter(BaseAdapter):
    name = "alpaca"
    display_name = "Alpaca"
    markets = ["stock"]
    needs_secret = True
    supports_order_routing = True

    def _client(self, api_key: str, api_secret: str, is_paper: bool):
        from alpaca.trading.client import TradingClient

        return TradingClient(api_key, api_secret, paper=is_paper)

    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        try:
            account = self._client(api_key, api_secret, is_paper).get_account()
            ok = account is not None and getattr(account, "account_number", None) is not None
            return {"ok": bool(ok), "detail": "account reachable" if ok else "no account data"}
        except Exception as e:
            return self._net_unavailable(e)

    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        a = self._client(api_key, api_secret, is_paper).get_account()
        return {
            "account_number": getattr(a, "account_number", None),
            "status": getattr(a, "status", None),
            "currency": getattr(a, "currency", "USD"),
            "cash": float(getattr(a, "cash", 0) or 0),
            "equity": float(getattr(a, "equity", 0) or 0),
            "buying_power": float(getattr(a, "buying_power", 0) or 0),
        }

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        from alpaca.trading.requests import (
            MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, StopLossRequest,
        )
        from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

        client = self._client(api_key, api_secret, is_paper)
        order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        bracket = bool(stop_loss and take_profit)

        common = {}
        if bracket:
            common = {
                "order_class": OrderClass.BRACKET,
                "take_profit": TakeProfitRequest(limit_price=round(float(take_profit), 2)),
                "stop_loss": StopLossRequest(stop_price=round(float(stop_loss), 2)),
            }

        if order_type == "limit":
            if not limit_price or limit_price <= 0:
                raise RuntimeError("limit orders require limit_price")
            req = LimitOrderRequest(
                symbol=symbol.upper(), qty=quantity, side=order_side,
                time_in_force=TimeInForce.GTC, limit_price=round(limit_price, 2), **common,
            )
        else:
            req = MarketOrderRequest(
                symbol=symbol.upper(), qty=quantity, side=order_side,
                time_in_force=TimeInForce.GTC, **common,
            )
        resp = client.submit_order(req)
        filled = getattr(resp, "filled_avg_price", None)
        return {
            "ok": True,
            "broker_order_id": str(resp.id),
            "broker_status": str(getattr(resp, "status", "")),
            "filled_price": float(filled) if filled else None,
            "protective": "bracket" if bracket else None,
        }
