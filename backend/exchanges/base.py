"""Base exchange adapter contract."""
from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    name: str = ""
    display_name: str = ""
    markets: list[str] = []
    needs_secret: bool = True
    supports_order_routing: bool = False

    def validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        """Credential check. Returns {ok: bool, detail: str}."""
        if self.needs_secret and not api_secret:
            return {"ok": False, "detail": "api_secret required"}
        try:
            return self._validate(api_key, api_secret, is_paper)
        except Exception as e:
            return {"ok": False, "detail": str(e)[:200]}

    def account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        """Account snapshot. Raises on failure; caller handles."""
        return self._account(api_key, api_secret, is_paper)

    def place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                    symbol: str, side: str, quantity: float,
                    order_type: str = "market", limit_price: float | None = None,
                    stop_loss: float | None = None,
                    take_profit: float | None = None) -> dict:
        """Submit an order. Returns {ok, broker_order_id?, filled_price?, detail}.

        When stop_loss/take_profit are provided the adapter attaches protective
        orders at the broker so positions stay protected even if ORQEVA is down.
        """
        if not self.supports_order_routing:
            return {"ok": False, "detail": "order routing not supported for this adapter"}
        try:
            return self._place_order(api_key, api_secret, is_paper, symbol=symbol,
                                     side=side, quantity=quantity,
                                     order_type=order_type, limit_price=limit_price,
                                     stop_loss=stop_loss, take_profit=take_profit)
        except Exception as e:
            return {"ok": False, "detail": str(e)[:200]}

    @abstractmethod
    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict: ...

    @abstractmethod
    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]: ...

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        raise NotImplementedError

    @staticmethod
    def _net_unavailable(e: Exception) -> dict:
        msg = str(e)[:120]
        return {"ok": False, "detail": f"network/blocked or bad credentials: {msg}"}
