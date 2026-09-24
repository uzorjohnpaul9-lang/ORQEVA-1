"""Coinbase Advanced Trade (crypto) adapter - ES256 JWT, no extra deps."""
import base64
import json
import time
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from backend.exchanges.base import BaseAdapter

_API = "https://api.coinbase.com/api/v3/brokerage"
_TIMEOUT = 10


class CoinbaseAdapter(BaseAdapter):
    name = "coinbase"
    display_name = "Coinbase Advanced"
    markets = ["crypto"]
    needs_secret = True  # api_key = key name, api_secret = EC PEM (may arrive b64-wrapped)
    supports_order_routing = True

    @staticmethod
    def to_product_id(symbol: str) -> str:
        """BTCUSDT -> BTC-USDT; BTCUSD -> BTC-USD"""
        s = symbol.upper().replace("/", "").replace("-", "")
        for quote in ("USDT", "USD", "USDC"):
            if s.endswith(quote):
                return f"{s[:-len(quote)]}-{quote}"
        return s

    @staticmethod
    def _pem_bytes(secret: str) -> bytes:
        s = secret.strip()
        if "BEGIN" not in s:
            s = base64.b64decode(s).decode()
        if "\n" not in s:
            s = s.replace("\\n", "\n")
        return s.encode()

    def _jwt(self, api_key: str, api_secret: str, method: str = "GET",
             path: str = "/api/v3/brokerage/accounts") -> tuple[str, int]:
        now = int(time.time())
        private_key = serialization.load_pem_private_key(self._pem_bytes(api_secret), password=None)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise RuntimeError("api_secret is not an EC private key")
        header = {"alg": "ES256", "kid": api_key, "nonce": secrets_token_hex()}
        payload = {
            "sub": api_key,
            "iss": "cdp",
            "nbf": now,
            "exp": now + 120,
            "uri": f"{method.upper()} api.coinbase.com{path}",
        }
        signing_input = (
            base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
            + b"."
            + base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
        )
        der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        # DER -> raw r||s (70 bytes typical)
        r, s = _der_to_rs(der_sig)
        sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return (
            signing_input.decode() + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode(),
            now,
        )

    def _headers(self, api_key: str, api_secret: str, method: str = "GET",
                 path: str = "/api/v3/brokerage/accounts") -> dict[str, str]:
        token, _ = self._jwt(api_key, api_secret, method, path)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        try:
            r = requests.get(f"{_API}/accounts?limit=5", headers=self._headers(api_key, api_secret), timeout=_TIMEOUT)
            body = r.json()
            if r.status_code != 200:
                raise RuntimeError(body.get("message", f"HTTP {r.status_code}"))
            return {"ok": True, "detail": "accounts endpoint reachable"}
        except Exception as e:
            return self._net_unavailable(e)

    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        r = requests.get(f"{_API}/accounts?limit=50", headers=self._headers(api_key, api_secret), timeout=_TIMEOUT)
        if r.status_code != 200:
            raise RuntimeError(r.text[:150])
        balances = {}
        for a in r.json().get("accounts", []):
            val = float(a.get("total_balance", {}).get("value", 0) or 0)
            if val > 0:
                balances[a["currency"]] = val
        return {"type": "spot", "balances": dict(sorted(balances.items(), key=lambda kv: -kv[1])[:20])}

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        path = "/api/v3/brokerage/orders"
        payload: dict[str, Any] = {
            "product_id": self.to_product_id(symbol),
            "side": side.upper(),
        }
        protective = []
        protective_error: str | None = None
        if order_type == "limit":
            if not limit_price or limit_price <= 0:
                raise RuntimeError("limit orders require limit_price")
            payload["order_configuration"] = {
                "limit_limit_gtc": {"base_size": f"{quantity:.8f}",
                                    "limit_price": f"{limit_price:.2f}"},
            }
        else:
            config: dict[str, Any] = {"base_size": f"{quantity:.8f}"}
            if stop_loss and take_profit and stop_loss > 0 and take_profit > 0:
                # native bracket: exit config rides on the entry order
                payload["order_configuration"] = {
                    "bracket_bracket_gtc": {
                        "base_size": f"{quantity:.8f}",
                        "limit_price": "",  # market entry leg
                        "stop_limit_price": f"{float(stop_loss):.2f}",
                        "stop_limit_price_pct": "",
                        "stop_trigger_price": f"{float(stop_loss):.2f}",
                        "take_profit_limit_price": f"{float(take_profit):.2f}",
                    },
                }
                protective.append("bracket")
            else:
                payload["order_configuration"] = {"market_market": config}

        r = requests.post(f"{_API}/orders", headers=self._headers(api_key, api_secret, "POST", path),
                          json=payload, timeout=_TIMEOUT)
        body = r.json()
        if not body.get("success"):
            raise RuntimeError(body.get("error_response", {}).get("message", r.text[:150]))
        order = body.get("success_response", {})

        # Standalone stop-loss AFTER a confirmed entry: if it fails we must NOT
        # report the whole order as failed (the position already exists at the
        # broker). Surface protective_error instead so the caller warns the user.
        if order_type != "limit" and not protective and stop_loss and stop_loss > 0:
            try:
                self._submit_stop(api_key, api_secret, symbol, side,
                                  quantity, float(stop_loss))
                protective.append("stop-loss")
            except Exception as e:  # noqa: BLE001 - keep entry result usable
                protective_error = str(e)[:150]

        return {
            "ok": True,
            "broker_order_id": str(order.get("order_id", "")),
            "broker_status": str(order.get("order_status", ""))[:40],
            "filled_price": None,
            "protective": "+".join(protective) or None,
            "protective_error": protective_error,
        }

    def _submit_stop(self, api_key: str, api_secret: str, symbol: str, side: str,
                     quantity: float, stop_price: float) -> None:
        """Standalone stop-loss for the opposite direction. Raises on failure."""
        opposite = "sell" if side.lower() == "buy" else "buy"
        payload = {
            "product_id": self.to_product_id(symbol),
            "side": opposite.upper(),
            "order_configuration": {
                "stop_limit_stop_limit_gtc": {
                    "base_size": f"{quantity:.8f}",
                    "limit_price": f"{stop_price * 0.995:.2f}",   # slight slippage guard
                    "stop_direction": "STOP_DIRECTION_STOP_DOWN"
                    if opposite == "sell" else "STOP_DIRECTION_STOP_UP",
                },
            },
        }
        r = requests.post(f"{_API}/orders",
                          headers=self._headers(api_key, api_secret, "POST", "/api/v3/brokerage/orders"),
                          json=payload, timeout=_TIMEOUT)
        body = r.json()
        if not body.get("success"):
            raise RuntimeError(body.get("error_response", {}).get("message", r.text[:150]))


def secrets_token_hex(n: int = 16) -> str:
    import secrets

    return secrets.token_hex(n)


def _der_to_rs(der: bytes) -> tuple[int, int]:
    # minimal ASN.1 SEQUENCE / INTEGER parse for ECDSA signatures
    assert der[0] == 0x30
    i = 2
    assert der[i] == 0x02
    rlen = der[i + 1]
    r = int.from_bytes(der[i + 2 : i + 2 + rlen], "big")
    j = i + 2 + rlen
    assert der[j] == 0x02
    slen = der[j + 1]
    s = int.from_bytes(der[j + 2 : j + 2 + slen], "big")
    return r, s


def coinbase_sign_for_tests(pem: str, kid: str) -> str:
    """Exposed for unit tests - returns a signed JWT."""
    token, _ = CoinbaseAdapter()._jwt(kid, pem)
    return token
