"""Bachs adapter (hosted checkout sessions + HMAC-signed webhooks).

Bachs is the only hosted-checkout gateway. The billing page lets the
customer pick a payment corridor (card / bank transfer / mobile money /
crypto) and we forward it as ``payment_method_types``; Bachs then converts
the USD price into the buyer's local currency at checkout.

Webhook signatures are HMAC-SHA256 over ``"{timestamp}.{raw_body}"``, sent
in ``X-Bachs-Signature`` (v1) and ``X-Bachs-Signature-V2``
(``t=<ts>,v1=<sig>``). V2 is preferred: it carries the timestamp inline
and can hold more than one signature while a signing secret rotates.

Money is always a decimal string ("49.00") paired with an ISO 4217
currency; never minor units.
"""
import hashlib
import hmac
import os
import time

from backend.payments.base import GatewayEvent, PaymentProvider

SANDBOX_BASE = "https://sandbox-api.bachs.io"
LIVE_BASE = "https://api.bachs.io"

# Every corridor Bachs exposes: id -> (label, currency, kind). A given
# account only has some of them enabled, so `enabled_corridors()` asks
# Bachs which ones it can actually offer before the UI offers them.
CORRIDORS: dict[str, tuple[str, str, str]] = {
    "USD_CARD": ("Debit or credit card", "USD", "card"),
    "NGN_CARD": ("Nigerian card", "NGN", "card"),
    "NGN_BANK_TRANSFER": ("Nigerian bank transfer", "NGN", "bank"),
    "MOMO_GHS": ("Mobile money - Ghana", "GHS", "momo"),
    "MOMO_KES": ("Mobile money - Kenya", "KES", "momo"),
    "MOMO_TZS": ("Mobile money - Tanzania", "TZS", "momo"),
    "MOMO_UGX": ("Mobile money - Uganda", "UGX", "momo"),
    "MOMO_XAF": ("Mobile money - Cameroon", "XAF", "momo"),
    "MOMO_XOF": ("Mobile money - Senegal & Cote d'Ivoire", "XOF", "momo"),
    "MOMO_RWF": ("Mobile money - Rwanda", "RWF", "momo"),
    "MOMO_MWK": ("Mobile money - Malawi", "MWK", "momo"),
    "MOMO_ZMW": ("Mobile money - Zambia", "ZMW", "momo"),
    "CRYPTO": ("Crypto - USDT, USDC, ETH, SOL, BNB", "CRYPTO", "crypto"),
}

# Deliveries older than this are rejected as replays.
SIGNATURE_TOLERANCE_SECONDS = 300

# Account checkout settings rarely change; cache them briefly.
CORRIDOR_CACHE_TTL = 300
_CORRIDOR_CACHE: dict = {"at": 0.0, "value": None}


def _error_detail(status: int, data: dict) -> str:
    detail = str((data or {}).get("detail") or "")
    code = str((data or {}).get("error_code") or "")
    if code and detail:
        return f"{status} {code}: {detail}"[:200]
    if code:
        return f"{status} {code}"[:200]
    if detail:
        return f"{status} {detail}"[:200]
    return f"http {status}"


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class BachsProvider(PaymentProvider):
    name = "bachs"
    display_name = "Bachs (card, bank, mobile money, crypto)"

    @property
    def api_key(self) -> str:
        return os.getenv("BACHS_API_KEY", "").strip()

    @property
    def _webhook_secret(self) -> str:
        return os.getenv("BACHS_WEBHOOK_SECRET", "").strip()

    @property
    def api_base(self) -> str:
        """Sandbox unless the key is explicitly live.

        BACHS_API_URL overrides both, which is what a self-hosted proxy or
        a staged environment needs.
        """
        base = os.getenv("BACHS_API_URL", "").strip().rstrip("/")
        if base:
            return base
        return LIVE_BASE if self.api_key.startswith("sk_live_") else SANDBOX_BASE

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, json_body: dict | None = None) -> tuple[int, dict]:
        import httpx
        resp = httpx.request(
            method, f"{self.api_base}{path}",
            headers=self._headers(), json=json_body, timeout=20.0,
        )
        try:
            data = resp.json() if resp.content else {}
        except Exception:
            data = {"detail": resp.text[:200]}
        if not isinstance(data, dict):
            data = {"detail": str(data)[:200]}
        return resp.status_code, data

    # -- corridors ---------------------------------------------------------

    def corridor_ids(self) -> set[str]:
        """Every corridor Bachs knows about (not just the enabled ones)."""
        return set(CORRIDORS)

    def enabled_corridors(self) -> list[str]:
        """Corridors this Bachs account can actually accept.

        Bachs rejects a checkout whose restriction leaves nothing payable,
        and silently omits a corridor the account cannot use, so the UI must
        only offer what the account has enabled. Cached briefly: the answer
        only changes when the account's checkout settings are edited.
        """
        if not self.is_configured():
            return []
        now = time.time()
        cached = _CORRIDOR_CACHE.get("at", 0.0)
        if _CORRIDOR_CACHE.get("value") is not None and now - cached < CORRIDOR_CACHE_TTL:
            return list(_CORRIDOR_CACHE["value"])
        try:
            status, data = self._request("GET", "/v1/accounts/checkout/settings")
        except Exception:
            return []
        if status >= 400:
            return []
        enabled = data.get("enabled_payment_methods") or {}
        out: list[str] = []
        for name, cfg in enabled.items():
            if name not in CORRIDORS:
                continue
            if not isinstance(cfg, dict) or not cfg.get("enabled"):
                continue
            if name == "CRYPTO":
                # CRYPTO additionally needs at least one asset turned on.
                assets = cfg.get("currencies") or {}
                if not any(bool(v) for v in assets.values()):
                    continue
            out.append(name)
        _CORRIDOR_CACHE["at"] = now
        _CORRIDOR_CACHE["value"] = out
        return list(out)

    def corridor_catalogue(self) -> list[dict]:
        """Corridor list for the billing page, limited to what we can take."""
        allowed = set(self.enabled_corridors())
        if not allowed:
            # Bachs is not configured (or the settings call failed): offer the
            # card and crypto rails we know work so the page still renders.
            allowed = {"USD_CARD", "CRYPTO"}
        out = []
        for name, (label, currency, kind) in CORRIDORS.items():
            if name not in allowed:
                continue
            out.append({
                "id": name,
                "label": label,
                "currency": currency,
                "kind": kind,
            })
        return out

    # -- checkout ----------------------------------------------------------

    def _create_checkout(self, invoice: dict, base_url: str, frontend_base: str) -> dict:
        corridor = str(invoice.get("payment_method") or "").strip()
        if corridor and corridor not in CORRIDORS:
            return {"ok": False, "detail": f"unsupported corridor {corridor}"}

        amount = f"{float(invoice['amount_usd']):.2f}"
        currency = str(invoice.get("currency") or "USD").upper()
        invoice_id = str(invoice["id"])

        body: dict = {
            # Exactly one pricing source: a raw amount, no catalog product.
            "pricing": {"currency": currency, "amount": amount},
            "reference": invoice_id[:128],
            "success_url": f"{frontend_base}/billing?status=paid",
            "cancel_url": f"{frontend_base}/billing?status=cancelled",
            "metadata": {"invoice_id": invoice_id, "tier": str(invoice.get("tier") or "")},
            "expires_in_minutes": 60,
        }
        email = str(invoice.get("_user_email") or "").strip()
        if email:
            body["customer"] = {"email": email}
        if corridor:
            body["payment_method_types"] = [corridor]

        try:
            status, data = self._request("POST", "/v1/checkout-sessions", body)
        except Exception as e:
            return {"ok": False, "detail": f"network: {str(e)[:170]}"}
        if status >= 400:
            return {"ok": False, "detail": _error_detail(status, data)}

        url = data.get("checkout_url")
        if not url:
            return {"ok": False, "detail": f"no checkout_url: {str(data)[:170]}"}
        return {
            "ok": True,
            "checkout_url": str(url),
            "provider_ref": str(data.get("checkout_id") or "") or None,
        }

    # -- webhooks ----------------------------------------------------------

    def _verify_webhook(self, headers: dict, body: bytes, payload: dict) -> dict:
        secret = self._webhook_secret
        if not secret:
            return {"ok": False, "detail": "missing webhook secret"}

        lowered = {str(k).lower(): v for k, v in (headers or {}).items()}
        v2 = str(lowered.get("x-bachs-signature-v2") or "")
        v1 = str(lowered.get("x-bachs-signature") or "")
        ts_header = str(lowered.get("x-bachs-timestamp") or "")

        raw_ts = ""
        signatures: list[str] = []
        for part in v2.split(","):
            key, _, value = part.partition("=")
            key = key.strip()
            if key == "t" and value.strip() and not raw_ts:
                raw_ts = value.strip()
            elif key == "v1" and value.strip():
                signatures.append(value.strip())
        if not raw_ts and ts_header.strip():
            raw_ts = ts_header.strip()
        if not signatures and v1.strip():
            signatures = [v1.strip()]
        if not raw_ts or not signatures:
            return {"ok": False, "detail": "missing bachs signature headers"}

        try:
            ts = int(raw_ts)
        except ValueError:
            return {"ok": False, "detail": "malformed bachs timestamp"}
        if abs(time.time() - ts) > SIGNATURE_TOLERANCE_SECONDS:
            return {"ok": False, "detail": "stale bachs signature"}

        # The signed message uses the timestamp exactly as sent.
        expected = hmac.new(
            secret.encode(), raw_ts.encode() + b"." + body, hashlib.sha256
        ).hexdigest()
        if not any(hmac.compare_digest(expected, s) for s in signatures):
            return {"ok": False, "detail": "bad bachs signature"}

        evt_type = str(payload.get("type") or "")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            data = {}
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        invoice_id = metadata.get("invoice_id") or data.get("reference") or None
        checkout_id = data.get("checkout_id") or None
        charge = data.get("charge") or {}
        charge_id = data.get("charge_id") or (
            charge.get("id") if isinstance(charge, dict) else None
        )

        amount = _to_float(data.get("amount"))
        currency = str(data.get("currency") or "") or None

        paid = False
        amount_usd: float | None = None
        if evt_type == "checkout.completed":
            # data.amount is the session amount in the session currency (USD).
            paid = str(data.get("payment_status") or "") == "paid"
            amount_usd = amount
        elif evt_type == "collection.succeeded":
            # data.amount here is the *customer's* local-currency charge
            # (e.g. NGN 75000.00), not the USD invoice total, so it must not
            # be compared against the invoice. resolve_amount() fetches the
            # session total instead.
            paid = str(data.get("status") or "").upper() in (
                "SUCCEEDED", "OVERPAID", "ACCEPTED",
            )
            amount_usd = None
        # collection.failed / collection.underpaid / checkout.expired and
        # everything else are recorded but never fulfil an order.

        event = GatewayEvent(
            event_id=str(payload.get("id") or ""),
            type=evt_type or "unknown",
            invoice_id=str(invoice_id) if invoice_id else None,
            provider_ref=str(charge_id or checkout_id or "") or None,
            amount_usd=amount_usd,
            currency=currency,
            paid=paid,
            raw=payload,
        )
        return {"ok": True, "event": event}

    async def resolve_amount(self, event: GatewayEvent) -> float | None:
        """The invoice-currency amount for a paid event.

        collection.succeeded reports the amount the customer was charged in
        their own currency. The checkout session holds the USD total we
        priced, so read it from there when the event does not carry it.
        """
        data = (event.raw or {}).get("data") or {}
        checkout_id = data.get("checkout_id") if isinstance(data, dict) else None
        if not checkout_id:
            return None
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{self.api_base}/v1/checkout-sessions/{checkout_id}",
                    headers=self._headers(),
                )
                if r.status_code >= 400:
                    return None
                session = r.json()
        except Exception:
            return None
        if not isinstance(session, dict):
            return None
        for key in ("amount", "total_amount"):
            value = _to_float(session.get(key))
            if value is not None:
                return value
        pricing = session.get("pricing") or {}
        if isinstance(pricing, dict):
            return _to_float(pricing.get("amount"))
        return None

    # -- refunds -----------------------------------------------------------

    async def _refund(self, invoice: dict) -> dict:
        import httpx
        charge_id = str(invoice.get("provider_ref") or "").strip()
        if not charge_id:
            return {"ok": False, "detail": "no charge id on invoice"}
        invoice_id = str(invoice.get("id") or "")
        body = {
            "charge_id": charge_id,
            "reference": f"orqeva-refund-{invoice_id[:32]}",
            "reason": "ORQEVA billing refund",
            "idempotency_key": f"orqeva-refund-{invoice_id}",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.post(
                    f"{self.api_base}/v1/refunds",
                    headers=self._headers(), json=body,
                )
        except Exception as e:
            return {"ok": False, "detail": f"network: {str(e)[:170]}"}
        if r.status_code >= 400:
            try:
                data = r.json()
            except Exception:
                data = {"detail": r.text[:200]}
            if not isinstance(data, dict):
                data = {"detail": str(data)[:200]}
            return {"ok": False, "detail": _error_detail(r.status_code, data)}
        return {"ok": True, "detail": "refund submitted"}
