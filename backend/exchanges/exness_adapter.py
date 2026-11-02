"""Exness (forex + metals) adapter - routes through a self-hosted MT5 bridge.

Exness exposes no public REST/FIX API: orders have to go through a running
MetaTrader 5 terminal. ``bridge/mt5_bridge.py`` runs next to that terminal on a
Windows VPS and this adapter speaks to it over HTTPS.

Credentials are stored like every other venue:
  api_key    -> "ACCOUNT|SERVER" (e.g. "12345678|Exness-MT5Real8")
  api_secret -> MT5 password

The account itself decides demo vs live; ``is_paper`` is only used to refuse
connecting a REAL account while the dashboard is in paper mode.
"""
from typing import Any

import requests

from backend.config import settings
from backend.exchanges.base import BaseAdapter

_TIMEOUT = 45


class ExnessAdapter(BaseAdapter):
    name = "exness"
    display_name = "Exness"
    markets = ["forex", "commodity"]
    needs_secret = True
    supports_order_routing = True
    supports_position_close = True

    key_label = "MT5 account"
    key_hint = "Your Exness MT5 account number, e.g. 12345678"
    secret_label = "MT5 password"
    needs_server = True
    server_label = "MT5 server"
    server_hint = "From the MT5 login window, e.g. Exness-MT5Real8"

    # ----------------------------------------------------------- credentials

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """EUR/USD, XAU-USD -> EURUSD, XAUUSD. Case and dots are preserved."""
        return "".join(ch for ch in (symbol or "") if ch not in "/- ").strip()

    @staticmethod
    def split_credentials(api_key: str, server: str = "") -> tuple[str, str]:
        """Accept "ACCOUNT|SERVER" (what the dashboard sends) or a bare login."""
        raw = (api_key or "").strip()
        login, _sep, embedded = raw.partition("|")
        resolved = ((server or "").strip() or embedded.strip()
                    or (settings.EXNESS_MT5_SERVER or "").strip())
        if not login.strip():
            raise RuntimeError("Exness account number is required")
        if not resolved:
            raise RuntimeError(
                "Exness MT5 server is required (for example Exness-MT5Real8)"
            )
        return login.strip(), resolved

    def _endpoint(self) -> tuple[str, dict[str, str]]:
        url = (settings.EXNESS_BRIDGE_URL or "").strip().rstrip("/")
        token = (settings.EXNESS_BRIDGE_TOKEN or "").strip()
        if not url:
            raise RuntimeError("EXNESS_BRIDGE_URL is not configured on the backend")
        if not token:
            raise RuntimeError("EXNESS_BRIDGE_TOKEN is not configured on the backend")
        return url, {"X-Bridge-Token": token}

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url, headers = self._endpoint()
        r = requests.post(f"{url}{path}", json=payload, headers=headers, timeout=_TIMEOUT)
        try:
            body = r.json()
        except ValueError:
            raise RuntimeError(f"bridge HTTP {r.status_code}: {r.text[:120]}")
        if r.status_code >= 400:
            detail = body.get("detail") if isinstance(body, dict) else body
            raise RuntimeError(f"bridge HTTP {r.status_code}: {str(detail)[:150]}")
        return body

    def _session(self, api_key: str, api_secret: str) -> dict[str, Any]:
        login, server = self.split_credentials(api_key)
        if not api_secret:
            raise RuntimeError("Exness MT5 password is required")
        return {"login": login, "password": api_secret, "server": server}

    # ---------------------------------------------------------------- adapter

    def _validate(self, api_key: str, api_secret: str, is_paper: bool) -> dict:
        try:
            body = self._post("/validate", self._session(api_key, api_secret))
            if not body.get("ok"):
                return {"ok": False, "detail": body.get("detail") or "MT5 login failed"}
            acct = body.get("account") or {}
            mode = str(acct.get("trade_mode") or "unknown").lower()
            label = f"{acct.get('company') or 'Exness'} account {acct.get('login')} ({mode})"
            if is_paper and mode == "real":
                return {
                    "ok": False,
                    "detail": ("this is a REAL-money account - turn off Paper trading "
                               "mode to connect it"),
                }
            if not is_paper and mode != "real":
                return {"ok": True, "detail": f"{label} - orders will stay on {mode}"}
            return {"ok": True, "detail": label}
        except Exception as e:
            return self._net_unavailable(e)

    def _account(self, api_key: str, api_secret: str, is_paper: bool) -> dict[str, Any]:
        body = self._post("/account", self._session(api_key, api_secret))
        if not body.get("ok"):
            raise RuntimeError(body.get("detail") or "MT5 account unavailable")
        acct = body.get("account") or {}
        equity = float(acct.get("equity") or 0)
        balance = float(acct.get("balance") or 0)
        return {
            "account_id": str(acct.get("login") or ""),
            "account_number": str(acct.get("login") or ""),
            "server": acct.get("server"),
            "currency": acct.get("currency", "USD"),
            "environment": acct.get("trade_mode"),
            "balance": balance,
            "equity": equity,
            "unrealized_pl": round(equity - balance, 2),
            "margin_free": float(acct.get("margin_free") or 0),
            "leverage": acct.get("leverage"),
            "open_trade_count": int(acct.get("open_positions") or 0),
        }

    def _place_order(self, api_key: str, api_secret: str, is_paper: bool, *,
                     symbol: str, side: str, quantity: float,
                     order_type: str, limit_price: float | None,
                     stop_loss: float | None = None,
                     take_profit: float | None = None) -> dict:
        payload = {
            **self._session(api_key, api_secret),
            "symbol": self.normalize_symbol(symbol),
            "side": side.lower(),
            "quantity_units": float(quantity),
            "order_type": order_type,
            "limit_price": limit_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "comment": "ORQEVA",
        }
        body = self._post("/order", payload)
        if not body.get("ok"):
            return {"ok": False,
                    "detail": body.get("detail") or "Exness bridge rejected the order"}
        return body

    def close_positions(self, api_key: str, api_secret: str, is_paper: bool, *,
                        symbol: str, side: str, quantity: float) -> dict:
        """Close the MT5 position(s) instead of opening an offsetting hedge."""
        payload = {
            **self._session(api_key, api_secret),
            "symbol": self.normalize_symbol(symbol),
            "side": side.lower(),
            "quantity_units": float(quantity),
        }
        body = self._post("/close", payload)
        if not body.get("ok"):
            return {"ok": False,
                    "detail": body.get("detail") or "Exness bridge could not close the position"}
        return body
