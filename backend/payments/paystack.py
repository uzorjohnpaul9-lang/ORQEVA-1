"""Paystack adapter (transaction initialize + HMAC-SHA512 webhook)."""
import hashlib
import hmac
import os

from backend.payments.base import GatewayEvent, PaymentProvider

API_BASE = "https://api.paystack.co"


class PaystackProvider(PaymentProvider):
    name = "paystack"
    display_name = "Card / Transfer (Paystack)"

    @property
    def api_key(self) -> str:
        return os.getenv("PAYSTACK_SECRET_KEY", "")

    def _create_checkout(self, invoice: dict, base_url: str) -> dict:
        body = {
            "email": invoice.get("_user_email") or "customer@orqeva.com",
            "amount": int(float(invoice["amount_usd"]) * 100),  # kobo
            "currency": os.getenv("PAYSTACK_CURRENCY", "USD"),
            "reference": invoice["id"],
            "callback_url": f"{base_url}/billing?status=paid",
        }
        data = self._post_json(
            f"{API_BASE}/transaction/initialize",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json_body=body,
        )
        url = (data.get("data") or {}).get("authorization_url")
        if not url:
            return {"ok": False, "detail": f"no authorization_url: {str(data)[:150]}"}
        return {"ok": True, "checkout_url": url, "provider_ref": invoice["id"]}

    def _verify_webhook(self, headers: dict, body: bytes, payload: dict) -> dict:
        sig = headers.get("x-paystack-signature") or headers.get("X-Paystack-Signature") or ""
        if not sig or not self.api_key:
            return {"ok": False, "detail": "missing signature or secret"}
        expected = hmac.new(self.api_key.encode(), body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return {"ok": False, "detail": "bad signature"}

        evt_type = str(payload.get("event") or "")
        data = payload.get("data") or {}
        paid = evt_type == "charge.success" and str(data.get("status") or "") == "success"
        event = GatewayEvent(
            event_id=str(data.get("id") or evt_type or "paystack"),
            type=evt_type or "unknown",
            invoice_id=str(data.get("reference") or "") or None,
            provider_ref=str(data.get("id") or "") or None,
            amount_usd=(float(data.get("amount") or 0) / 100.0) or None,
            currency=str(data.get("currency") or "usd"),
            paid=paid,
            raw=payload,
        )
        return {"ok": True, "event": event}

    async def _refund(self, invoice: dict) -> dict:
        import httpx
        ref = invoice.get("tx_ref") or invoice.get("provider_ref") or ""
        if not ref:
            return {"ok": False, "detail": "no transaction reference"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{API_BASE}/refund",
                json={"transaction": ref},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        if r.status_code >= 400:
            return {"ok": False, "detail": r.text[:150]}
        return {"ok": True, "detail": "refund submitted"}
