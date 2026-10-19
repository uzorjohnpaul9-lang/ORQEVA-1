"""Stripe adapter (Checkout Sessions + signed webhooks)."""
import hashlib
import hmac
import os

from backend.payments.base import GatewayEvent, PaymentProvider

API_BASE = "https://api.stripe.com/v1"


class StripeProvider(PaymentProvider):
    name = "stripe"
    display_name = "Card (Stripe)"

    @property
    def api_key(self) -> str:
        return os.getenv("STRIPE_SECRET_KEY", "")

    @property
    def _webhook_secret(self) -> str:
        return os.getenv("STRIPE_WEBHOOK_SECRET", "")

    def _create_checkout(self, invoice: dict, base_url: str, frontend_base: str) -> dict:
        body = [
            ("mode", "payment"),
            ("client_reference_id", invoice["id"]),
            ("metadata[invoice_id]", invoice["id"]),
            ("metadata[tier]", str(invoice.get("tier") or "")),
            ("line_items[0][quantity]", "1"),
            ("line_items[0][price_data][currency]", "usd"),
            ("line_items[0][price_data][unit_amount]", str(int(float(invoice["amount_usd"]) * 100))),
            ("line_items[0][price_data][product_data][name]", f"ORQEVA {invoice.get('tier', '').upper()}"),
            ("success_url", f"{frontend_base}/billing?status=paid"),
            ("cancel_url", f"{frontend_base}/billing"),
        ]
        resp = self._post_form(f"{API_BASE}/checkout/sessions", body)
        if not resp.get("url"):
            return {"ok": False, "detail": f"no session url: {str(resp)[:150]}"}
        return {"ok": True, "checkout_url": resp["url"], "provider_ref": str(resp.get("id") or "")}

    @staticmethod
    def _post_form(url: str, form: list[tuple[str, str]]) -> dict:
        import httpx
        resp = httpx.post(url, data=form, headers={
            "Authorization": f"Bearer {os.getenv('STRIPE_SECRET_KEY', '')}",
        }, timeout=20.0)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _verify_webhook(self, headers: dict, body: bytes, payload: dict) -> dict:
        header = headers.get("stripe-signature") or headers.get("Stripe-Signature") or ""
        secret = self._webhook_secret
        if not header or not secret:
            return {"ok": False, "detail": "missing signature or secret"}

        timestamp = None
        signatures = []
        for part in header.split(","):
            k, _, v = part.partition("=")
            if k.strip() == "t":
                timestamp = v.strip()
            elif k.strip() == "v1":
                signatures.append(v.strip())
        if not timestamp or not signatures:
            return {"ok": False, "detail": "malformed stripe-signature"}

        signed = f"{timestamp}.".encode() + body
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, s) for s in signatures):
            return {"ok": False, "detail": "bad signature"}

        evt_type = str(payload.get("type") or "")
        obj = payload.get("data") or {}
        obj = obj.get("object") or obj
        if evt_type.startswith("checkout.session."):
            invoice_id = obj.get("metadata", {}).get("invoice_id") or obj.get("client_reference_id")
            paid = bool(obj.get("payment_status") == "paid" or obj.get("status") == "complete")
        elif evt_type.startswith("invoice."):
            invoice_id = (obj.get("metadata") or {}).get("invoice_id")
            paid = bool(obj.get("paid") or evt_type == "invoice.paid")
        else:
            invoice_id, paid = None, False

        event = GatewayEvent(
            event_id=str(payload.get("id") or ""),
            type=evt_type or "unknown",
            invoice_id=str(invoice_id) if invoice_id else None,
            provider_ref=str(obj.get("id") or "") or None,
            amount_usd=(float(obj.get("amount_total") or 0) / 100.0) or None,
            currency=str(obj.get("currency") or "usd"),
            paid=paid,
            raw=payload,
        )
        return {"ok": True, "event": event}

    async def _refund(self, invoice: dict) -> dict:
        import httpx
        session_ref = invoice.get("provider_ref") or ""
        if not session_ref:
            return {"ok": False, "detail": "no provider_ref"}
        if invoice.get("provider") == "stripe" and session_ref.startswith("cs_"):
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(
                    f"{API_BASE}/checkout/sessions/{session_ref}/line_items",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if r.status_code == 200:
                    items = r.json().get("data") or []
                    if items and items[0].get("id"):
                        session_ref = items[0]["id"]
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                f"{API_BASE}/refunds",
                data={"charge": session_ref, "amount": str(int(float(invoice.get("amount_usd") or 0) * 100))},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        if r.status_code >= 400:
            return {"ok": False, "detail": r.text[:150]}
        return {"ok": True, "detail": "refund submitted"}
