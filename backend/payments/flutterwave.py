"""Flutterwave adapter (v3 initialize + verif-hash webhook)."""
import os

from backend.payments.base import GatewayEvent, PaymentProvider

API_BASE = "https://api.flutterwave.com/v3"


class FlutterwaveProvider(PaymentProvider):
    name = "flutterwave"
    display_name = "Card / Transfer (Flutterwave)"

    @property
    def api_key(self) -> str:
        return os.getenv("FLUTTERWAVE_SECRET_KEY", "")

    @property
    def _webhook_hash(self) -> str:
        return os.getenv("FLUTTERWAVE_WEBHOOK_HASH", "")

    def _create_checkout(self, invoice: dict, base_url: str) -> dict:
        body = {
            "tx_ref": invoice["id"],
            "amount": float(invoice["amount_usd"]),
            "currency": os.getenv("FLUTTERWAVE_CURRENCY", "USD"),
            "redirect_url": f"{base_url}/billing?status=paid",
            "customer": {"email": invoice.get("_user_email") or "customer@orqeva.com"},
            "customizations": {"title": f"ORQEVA {invoice.get('tier', '').upper()}"},
        }
        data = self._post_json(
            f"{API_BASE}/transactions/initialize",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json_body=body,
        )
        link = (data.get("data") or {}).get("link")
        if not link:
            return {"ok": False, "detail": f"no link: {str(data)[:150]}"}
        return {"ok": True, "checkout_url": link, "provider_ref": invoice["id"]}

    def _verify_webhook(self, headers: dict, body: bytes, payload: dict) -> dict:
        sig = headers.get("verif-hash") or headers.get("Verif-Hash") or ""
        secret = self._webhook_hash or self.api_key
        if not sig or not secret:
            return {"ok": False, "detail": "missing signature or secret"}
        if sig != secret:
            return {"ok": False, "detail": "bad signature"}

        evt_type = str(payload.get("event") or "")
        data = payload.get("data") or {}
        paid = (
            evt_type in ("charge.completed", "checkout.transaction.completed")
            and str(data.get("status") or "").lower() in ("successful", "success")
        )
        event = GatewayEvent(
            event_id=str(data.get("id") or evt_type or "flutterwave"),
            type=evt_type or "unknown",
            invoice_id=str(data.get("tx_ref") or "") or None,
            provider_ref=str(data.get("id") or "") or None,
            amount_usd=float(data.get("amount") or 0) or None,
            currency=str(data.get("currency") or "usd"),
            paid=paid,
            raw=payload,
        )
        return {"ok": True, "event": event}

    async def _refund(self, invoice: dict) -> dict:
        import httpx
        ref = invoice.get("tx_ref") or invoice.get("provider_ref") or ""
        if not ref:
            return {"ok": False, "detail": "no transaction id"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{API_BASE}/transactions/{ref}/refund",
                json={"amount": float(invoice.get("amount_usd") or 0)},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        if r.status_code >= 400:
            return {"ok": False, "detail": r.text[:150]}
        return {"ok": True, "detail": "refund submitted"}
