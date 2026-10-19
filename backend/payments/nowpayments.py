"""NOWPayments adapter (crypto-first gateway; invoice + IPN webhook)."""
import hashlib
import hmac
import json
import os

from backend.payments.base import GatewayEvent, PaymentProvider

API_BASE = "https://api.nowpayments.io/v1"


class NowPaymentsProvider(PaymentProvider):
    name = "nowpayments"
    display_name = "NOWPayments (crypto)"

    @property
    def api_key(self) -> str:
        return os.getenv("NOWPAYMENTS_API_KEY", "")

    @property
    def _ipn_secret(self) -> str:
        return os.getenv("NOWPAYMENTS_IPN_SECRET", "")

    @property
    def _wallet(self) -> str:
        return os.getenv("NOWPAYMENTS_PAYOUT_ADDRESS", "")

    @property
    def _pay_currency(self) -> str:
        return os.getenv("NOWPAYMENTS_PAY_CURRENCY", "usdttrc20")

    def _create_checkout(self, invoice: dict, base_url: str, frontend_base: str) -> dict:
        body = {
            "price_amount": float(invoice["amount_usd"]),
            "price_currency": "usd",
            "pay_currency": self._pay_currency,
            "order_id": invoice["id"],
            "order_description": f"ORQEVA {invoice.get('tier', '').upper()}",
            # gateway callbacks hit the backend; the browser lands on the frontend
            "ipn_callback_url": f"{base_url}/api/billing/webhooks/nowpayments",
            "success_url": f"{frontend_base}/billing?status=paid",
            "cancel_url": f"{frontend_base}/billing",
        }
        if self._wallet:
            body["payout_address"] = self._wallet
        data = self._post_json(
            f"{API_BASE}/invoice",
            headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
            json_body=body,
        )
        url = data.get("invoice_url")
        if not url:
            return {"ok": False, "detail": f"no invoice_url: {str(data)[:150]}"}
        return {"ok": True, "checkout_url": url, "provider_ref": str(data.get("id") or "")}

    def _verify_webhook(self, headers: dict, body: bytes, payload: dict) -> dict:
        sig = (headers.get("x-nowpayments-sig") or headers.get("X-NOWPayments-Sig") or "").strip().lower()
        if not sig or not self._ipn_secret:
            return {"ok": False, "detail": "missing signature or secret"}
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        expected = hmac.new(self._ipn_secret.encode(), canonical.encode(), hashlib.sha512).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return {"ok": False, "detail": "bad signature"}

        status = str(payload.get("payment_status") or "").lower()
        paid = status in ("finished", "partially_paid", "confirmed")
        event = GatewayEvent(
            event_id=f"{payload.get('payment_id') or payload.get('order_id')}-{status}",
            type=status or "ipn",
            invoice_id=str(payload.get("order_id") or "") or None,
            provider_ref=str(payload.get("payment_id") or "") or None,
            amount_usd=float(payload.get("price_amount") or 0) or None,
            currency=str(payload.get("price_currency") or "usd"),
            paid=paid,
            raw=payload,
        )
        return {"ok": True, "event": event}

    async def _refund(self, invoice: dict) -> dict:
        return {"ok": False, "detail": "NOWPayments refunds are manual (crypto sends)"}
