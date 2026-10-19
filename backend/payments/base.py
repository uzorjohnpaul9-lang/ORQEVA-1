"""Base payment gateway contract (mirrors backend/exchanges/base.py)."""
from abc import ABC, abstractmethod
from typing import Any

import httpx


class GatewayEvent:
    """Normalized webhook payload from any gateway."""

    __slots__ = ("event_id", "type", "invoice_id", "provider_ref",
                 "amount_usd", "currency", "paid", "raw")

    def __init__(self, *, event_id: str, type: str, invoice_id: str | None,
                 provider_ref: str | None, amount_usd: float | None,
                 currency: str | None, paid: bool, raw: dict):
        self.event_id = event_id
        self.type = type
        self.invoice_id = invoice_id
        self.provider_ref = provider_ref
        self.amount_usd = amount_usd
        self.currency = currency
        self.paid = paid
        self.raw = raw


class PaymentProvider(ABC):
    name: str = ""
    display_name: str = ""

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def api_key(self) -> str:
        return ""

    def create_checkout(self, invoice: dict, base_url: str, frontend_base: str | None = None) -> dict:
        """Hosted checkout. Returns {ok, checkout_url?, detail?}; never raises.

        ``base_url`` is the backend origin a gateway calls back on (webhooks);
        ``frontend_base`` is the public app origin the user's browser is sent
        to after payment. They fall back to the same value when only one is
        configured (see config.frontend_base).
        """
        if not self.is_configured():
            return {"ok": False, "detail": "gateway not configured"}
        try:
            return self._create_checkout(invoice, base_url, frontend_base or base_url)
        except httpx.HTTPError as e:
            return {"ok": False, "detail": f"network: {str(e)[:120]}"}
        except Exception as e:
            return {"ok": False, "detail": str(e)[:200]}

    def verify_webhook(self, headers: dict, body: bytes, payload: dict) -> dict:
        """Verify signature + normalize. Returns {ok, event|detail}; never raises."""
        if not self.is_configured():
            return {"ok": False, "detail": "gateway not configured"}
        try:
            return self._verify_webhook(headers, body, payload)
        except Exception as e:
            return {"ok": False, "detail": str(e)[:200]}

    async def refund(self, invoice: dict) -> dict:
        """Best-effort refund call. Returns {ok, detail}; never raises.

        Admin-triggered refunds stay authoritative in the DB; this just pokes
        the gateway so card/charge reversals actually process.
        """
        if not self.is_configured():
            return {"ok": False, "detail": "gateway not configured"}
        try:
            return await self._refund(invoice)
        except Exception as e:
            return {"ok": False, "detail": str(e)[:200]}

    @abstractmethod
    def _create_checkout(self, invoice: dict, base_url: str, frontend_base: str) -> dict: ...

    @abstractmethod
    def _verify_webhook(self, headers: dict, body: bytes, payload: dict) -> dict: ...

    async def _refund(self, invoice: dict) -> dict:
        return {"ok": False, "detail": "refunds not supported"}

    @staticmethod
    def _post_json(url: str, *, headers: dict, json_body: dict, timeout: float = 20.0) -> dict:
        resp = httpx.post(url, headers=headers, json=json_body, timeout=timeout)
        resp.raise_for_status()
        return resp.json() if resp.content else {}
