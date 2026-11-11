"""Capital.com REST API demo spike.

Standalone: no backend imports, no database writes, no changes to the live
Exness connection.

Run with the dedicated spike venv:
    scripts\\broker_spikes\\.venv\\Scripts\\python.exe scripts\\broker_spike_capital.py

Read-only checks (default):
    ... scripts\\broker_spike_capital.py

Demo order checks (explicit opt-in):
    ... scripts\\broker_spike_capital.py --execute --round-trips 5

The report is written to temp/broker_spike_capital.json by default. Credentials
are read from environment variables and are never included in the report.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "temp" / "broker_spike_capital.json"
DEMO_BASE = "https://demo-api-capital.backend-capital.com"
LIVE_BASE = "https://api-capital.backend-capital.com"
DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "USDCHF", "NZDUSD", "USDCAD", "XAUUSD"]
SYMBOL_ALIASES = {
    "XAUUSD": ["XAUUSD", "GOLD"],
    "XAGUSD": ["XAGUSD", "SILVER"],
    "USOIL": ["USOIL", "OIL_CRUDE"],
    "UKOIL": ["UKOIL", "OIL_BRENT"],
    "NAS100": ["NAS100", "US100"],
    "SPX500": ["SPX500", "US500"],
    "GER40": ["GER40", "DE40"],
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def _parse_symbols(raw: str) -> list[str]:
    symbols = [item.strip().upper() for item in raw.split(",") if item.strip()]
    if not symbols:
        raise argparse.ArgumentTypeError("at least one symbol is required")
    return symbols


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _resolve_report_path(raw: str | None) -> Path:
    path = Path(raw) if raw else DEFAULT_REPORT
    if not path.is_absolute():
        path = ROOT / path
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rule_value(rule: Any) -> float | None:
    value = rule.get("value") if isinstance(rule, dict) else rule
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _price_digits(instrument: dict[str, Any], snapshot: dict[str, Any]) -> int:
    for source, key in (
        (instrument, "precision"),
        (snapshot, "decimalPlacesFactor"),
        (instrument, "decimalPlacesFactor"),
    ):
        value = source.get(key)
        if value is None:
            continue
        try:
            return max(0, min(8, int(value)))
        except (TypeError, ValueError):
            continue
    return 5


def _round_price(value: float, digits: int) -> float:
    quant = Decimal(1).scaleb(-digits)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def _round_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    decimal_value = Decimal(str(value))
    decimal_step = Decimal(str(step))
    units = (decimal_value / decimal_step).to_integral_value(rounding=ROUND_CEILING)
    return float(units * decimal_step)


def _sanitize_session(info: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "accountId",
        "accountType",
        "currency",
        "currentAccountId",
        "hasActiveAccount",
        "isDemo",
    )
    return {key: info[key] for key in keys if key in info}


def _deal_id(confirm: dict[str, Any]) -> str:
    if confirm.get("dealId"):
        return str(confirm["dealId"])
    for deal in confirm.get("affectedDeals") or []:
        if isinstance(deal, dict) and deal.get("dealId"):
            return str(deal["dealId"])
    return ""


@dataclass
class Credentials:
    env: str
    api_key: str
    identifier: str
    password: str
    base_url: str
    account_id: str


def _credentials(args: argparse.Namespace) -> Credentials:
    env = (args.env or _env("CAPITAL_ENV", "demo") or "demo").lower()
    if env not in {"demo", "live"}:
        raise SystemExit("CAPITAL_ENV must be demo or live")
    if env == "live" and not args.allow_live:
        raise SystemExit("Refusing live Capital.com: pass --allow-live to override")
    base_url = (
        args.base_url
        or _env("CAPITAL_BASE_URL")
        or (LIVE_BASE if env == "live" else DEMO_BASE)
    ).rstrip("/")
    api_key = _env("CAPITAL_API_KEY")
    identifier = _env("CAPITAL_IDENTIFIER")
    password = _env("CAPITAL_PASSWORD")
    account_id = args.account_id or _env("CAPITAL_ACCOUNT_ID")
    missing = []
    if not api_key:
        missing.append("CAPITAL_API_KEY")
    if not identifier:
        missing.append("CAPITAL_IDENTIFIER")
    if not password:
        missing.append("CAPITAL_PASSWORD")
    if missing:
        raise SystemExit(
            "Missing Capital.com credentials: "
            + ", ".join(missing)
            + "\n\nPowerShell example:\n"
            + '  $env:CAPITAL_API_KEY="..."\n'
            + '  $env:CAPITAL_IDENTIFIER="you@example.com"\n'
            + '  $env:CAPITAL_PASSWORD="..."  # API key custom password\n'
            + '  $env:CAPITAL_ACCOUNT_ID="..."  # optional\n'
        )
    return Credentials(
        env=env,
        api_key=api_key,
        identifier=identifier,
        password=password,
        base_url=base_url,
        account_id=account_id,
    )


class CapitalClient:
    def __init__(self, creds: Credentials) -> None:
        self.creds = creds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "orqeva-broker-spike/1.0"})
        self.cst: str | None = None
        self.security_token: str | None = None
        self.session_info: dict[str, Any] = {}

    def login(self) -> None:
        url = f"{self.creds.base_url}/api/v1/session"
        headers = {
            "X-CAP-API-KEY": self.creds.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "identifier": self.creds.identifier,
            "password": self.creds.password,
            "encryptedPassword": False,
        }
        response: requests.Response | None = None
        for attempt in range(3):
            response = self.session.post(
                url, headers=headers, json=payload, timeout=30
            )
            if response.status_code != 429:
                break
            time.sleep(1 + attempt)
        if response is None or response.status_code != 200:
            body = response.text[:500] if response is not None else "no response"
            code = response.status_code if response is not None else "n/a"
            raise RuntimeError(f"Capital.com login failed: HTTP {code}: {body}")
        cst = response.headers.get("CST")
        security_token = response.headers.get("X-SECURITY-TOKEN")
        if not cst or not security_token:
            raise RuntimeError(
                "Capital.com login succeeded but did not return CST/"
                "X-SECURITY-TOKEN"
            )
        self.cst = cst
        self.security_token = security_token
        try:
            self.session_info = response.json()
        except ValueError:
            self.session_info = {}

    def _headers(self) -> dict[str, str]:
        headers = {
            "X-CAP-API-KEY": self.creds.api_key,
            "Content-Type": "application/json",
        }
        if self.cst:
            headers["CST"] = self.cst
        if self.security_token:
            headers["X-SECURITY-TOKEN"] = self.security_token
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        allow_404: bool = False,
        timeout: int = 30,
    ) -> requests.Response:
        method = method.upper()
        url = f"{self.creds.base_url}{path}"
        last_error = ""
        for attempt in range(3):
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_body,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                if method == "GET" and attempt < 2:
                    time.sleep(1)
                    continue
                raise RuntimeError(f"{method} {path} network error: {exc}") from exc

            if response.status_code == 401 and attempt == 0:
                self.login()
                continue
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else 1.0
                except ValueError:
                    delay = 1.0
                time.sleep(max(delay, 0.5))
                continue
            if response.status_code >= 500 and method == "GET" and attempt < 2:
                time.sleep(1)
                continue
            if allow_404 and response.status_code == 404:
                return response
            if not 200 <= response.status_code < 300:
                raise RuntimeError(
                    f"{method} {path} -> HTTP {response.status_code}: "
                    f"{response.text[:500]}"
                )
            return response
        raise RuntimeError(f"{method} {path} failed after retries: {last_error}")

    def json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any]:
        response = self.request(
            method, path, json_body=json_body, allow_404=allow_404
        )
        if response.status_code == 404:
            return {"_http_status": 404}
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {"data": data}


class CapitalSpike:
    def __init__(self, args: argparse.Namespace, creds: Credentials) -> None:
        self.args = args
        self.creds = creds
        self.client = CapitalClient(creds)
        self.report: dict[str, Any] = {
            "broker": "capital.com",
            "environment": creds.env,
            "base_url": creds.base_url,
            "started_at": _iso_now(),
            "checks": {},
            "accounts": [],
            "symbols": [],
            "orders": [],
            "errors": [],
        }
        self.markets: dict[str, dict[str, Any]] = {}
        self._exit_code = 1

    def run(self) -> int:
        try:
            self.client.login()
            self._check("session", True)
            self.report["session"] = _sanitize_session(self.client.session_info)
            print(f"Authenticated to Capital.com ({self.creds.env})")
            if self.args.test_session_refresh:
                self._test_session_refresh()
            self._load_accounts()
            self._resolve_symbols()
            if self.args.execute:
                self._execute_orders()
            self.report["ok"] = all(
                item.get("ok") for item in self.report["checks"].values()
            )
            self._exit_code = 0 if self.report["ok"] else 1
        except Exception as exc:  # noqa: BLE001 - spike must report failures
            self._add_error(str(exc))
            self.report["ok"] = False
            self._exit_code = 1
        self._write_report()
        self._print_summary()
        return self._exit_code

    def _check(self, name: str, ok: bool, detail: str = "") -> None:
        self.report["checks"][name] = {"ok": bool(ok), "detail": detail}

    def _add_error(self, message: str) -> None:
        self.report["errors"].append(message)
        print(f"ERROR: {message}")

    def _write_report(self) -> None:
        self.report["finished_at"] = _iso_now()
        path = _resolve_report_path(self.args.report)
        try:
            _write_json(path, self.report)
        except OSError as exc:
            print(f"Could not write report {path}: {exc}")

    def _print_summary(self) -> None:
        checks = self.report["checks"]
        failed = [name for name, item in checks.items() if not item.get("ok")]
        print(
            f"\nCapital.com spike "
            f"{'PASSED' if self.report.get('ok') else 'FAILED'} "
            f"(env={self.creds.env})"
        )
        print(f"Report: {_resolve_report_path(self.args.report)}")
        if failed:
            print(f"Failed checks: {', '.join(failed)}")
        if self.report["errors"]:
            print(f"Errors: {len(self.report['errors'])}")

    def _test_session_refresh(self) -> None:
        self.client.cst = None
        self.client.security_token = None
        data = self.client.json("GET", "/api/v1/accounts")
        ok = bool(data.get("accounts"))
        self._check("session_refresh", ok, "forced 401 re-login")

    def _load_accounts(self) -> None:
        data = self.client.json("GET", "/api/v1/accounts")
        accounts = data.get("accounts") or []
        self.report["accounts"] = accounts
        if not accounts:
            raise RuntimeError("Capital.com returned no accounts")
        active_id = (
            self.creds.account_id
            or str(self.client.session_info.get("accountId") or "")
            or str((accounts[0] or {}).get("accountId") or "")
        )
        account = next(
            (
                item
                for item in accounts
                if str(item.get("accountId")) == str(active_id)
            ),
            accounts[0],
        )
        self.report["account"] = account
        balance = account.get("balance") or {}
        if isinstance(balance, dict):
            self.report["balance"] = {
                "balance": _number(balance.get("balance")),
                "deposit": _number(balance.get("deposit")),
                "profit_loss": _number(balance.get("profitLoss")),
                "available": _number(balance.get("available")),
                "equity_estimate": _number(balance.get("balance"))
                + _number(balance.get("profitLoss")),
            }
        self._check(
            "accounts",
            True,
            f"{len(accounts)} account(s), active={account.get('accountId')}",
        )

    def _resolve_symbols(self) -> None:
        symbol_errors: list[dict[str, str]] = []
        for target in self.args.symbols:
            try:
                market = self._market(target)
                detail = self._market_detail(target, market)
            except Exception as exc:  # noqa: BLE001 - report, keep other symbols
                symbol_errors.append({"symbol": target, "error": str(exc)})
                self._add_error(f"market lookup failed for {target}: {exc}")
                continue
            self.markets[target] = detail
            print(
                f"[market] {target} epic={detail['epic']} "
                f"min={detail['min_deal_size']} step={detail['size_step']}"
            )
        if symbol_errors:
            self.report["symbol_errors"] = symbol_errors
        self.report["symbols"] = list(self.markets.values())
        resolved = len(self.markets)
        self._check(
            "symbol_lookup",
            resolved == len(self.args.symbols),
            f"{resolved}/{len(self.args.symbols)} resolved",
        )
        rules_ok = bool(self.markets) and all(
            item.get("min_deal_size") is not None
            and item.get("size_step") is not None
            for item in self.markets.values()
        )
        self._check("market_rules", rules_ok, "min size and step captured")

    def _market(self, symbol: str) -> dict[str, Any]:
        candidates = SYMBOL_ALIASES.get(symbol.upper(), [symbol])
        for candidate in candidates:
            response = self.client.request(
                "GET", f"/api/v1/markets/{quote(candidate)}", allow_404=True
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and (
                    data.get("epic")
                    or (data.get("instrument") or {}).get("epic")
                ):
                    return data
            search = self.client.json(
                "GET", f"/api/v1/markets?searchTerm={quote(candidate)}"
            )
            markets = search.get("markets") or []
            target = _normalize(candidate)
            for market in markets:
                names = {
                    _normalize(str(market.get("epic") or "")),
                    _normalize(str(market.get("instrumentName") or "")),
                    _normalize(str(market.get("symbol") or "")),
                    _normalize(
                        str((market.get("instrument") or {}).get("name") or "")
                    ),
                    _normalize(
                        str((market.get("instrument") or {}).get("epic") or "")
                    ),
                }
                if target in names:
                    return market
        raise RuntimeError(f"Capital.com market not found: {symbol}")

    def _market_detail(
        self, target: str, market: dict[str, Any]
    ) -> dict[str, Any]:
        instrument = market.get("instrument") or {}
        dealing = market.get("dealingRules") or {}
        snapshot = market.get("snapshot") or {}
        digits = _price_digits(instrument, snapshot)
        return {
            "requested": target,
            "epic": market.get("epic") or instrument.get("epic") or target,
            "name": instrument.get("name")
            or market.get("instrumentName")
            or target,
            "instrument_type": instrument.get("type")
            or market.get("instrumentType")
            or "",
            "currency": instrument.get("currency") or "",
            "digits": digits,
            "min_deal_size": _rule_value(dealing.get("minDealSize")),
            "max_deal_size": _rule_value(dealing.get("maxDealSize")),
            "size_step": _rule_value(dealing.get("minSizeIncrement")),
            "min_stop_distance": _rule_value(dealing.get("minStepDistance")),
            "bid": _number(snapshot.get("bid") or snapshot.get("lastTraded")),
            "offer": _number(snapshot.get("offer") or snapshot.get("lastTraded")),
            "market_status": snapshot.get("marketStatus") or "",
            "snapshot_time": snapshot.get("updateTime"),
            "dealing_rules": dealing,
        }

    def _size_for(self, market: dict[str, Any]) -> float:
        if self.args.size is not None:
            size = float(self.args.size)
        else:
            minimum = market.get("min_deal_size") or 0.0
            step = market.get("size_step") or 0.0
            size = max(minimum, step, 0.01)
        step = float(market.get("size_step") or 0.0)
        return _round_to_step(size, step) if step > 0 else size

    def _side_for(self, index: int) -> str:
        if self.args.side == "ALTERNATE":
            return "BUY" if index % 2 == 0 else "SELL"
        return self.args.side

    def _execute_orders(self) -> None:
        if not self.markets:
            self._check("order_execution", False, "no markets resolved")
            return
        names = list(self.markets)
        for index in range(self.args.round_trips):
            symbol = names[index % len(names)]
            side = self._side_for(index)
            self._round_trip(index + 1, symbol, side)
        passed = sum(1 for order in self.report["orders"] if order.get("ok"))
        total = len(self.report["orders"])
        self._check(
            "order_execution",
            total > 0 and passed == total,
            f"{passed}/{total} passed",
        )

    def _round_trip(self, number: int, symbol: str, side: str) -> None:
        market = self.markets[symbol]
        record: dict[str, Any] = {
            "kind": "market",
            "number": number,
            "symbol": symbol,
            "epic": market.get("epic"),
            "side": side,
            "ok": False,
            "closed": False,
        }
        self.report["orders"].append(record)
        try:
            self._round_trip_inner(number, symbol, side, record)
        except Exception as exc:  # noqa: BLE001 - keep remaining trips running
            record["ok"] = False
            self._add_error(f"{symbol} round trip failed: {exc}")
            deal_id = str(record.get("deal_id") or "")
            if deal_id and not record.get("closed"):
                try:
                    cleanup = self._close(deal_id)
                    record["cleanup_close"] = cleanup
                    record["closed"] = bool(cleanup.get("closed"))
                except Exception as close_exc:  # noqa: BLE001
                    self._add_error(
                        f"cleanup close failed for {deal_id}: {close_exc}"
                    )

    def _round_trip_inner(
        self,
        number: int,
        symbol: str,
        side: str,
        record: dict[str, Any],
    ) -> None:
        market = self.markets[symbol]
        bid = float(market.get("bid") or 0)
        offer = float(market.get("offer") or 0)
        if bid <= 0 or offer <= 0:
            raise RuntimeError(f"{symbol} has no bid/offer snapshot")
        entry = offer if side == "BUY" else bid
        stop_pct = self.args.stop_pct or (0.01 if "XAU" in symbol else 0.002)
        digits = int(market.get("digits") or 5)
        if side == "BUY":
            stop = entry * (1 - stop_pct)
            profit = entry * (1 + stop_pct * self.args.profit_multiple)
        else:
            stop = entry * (1 + stop_pct)
            profit = entry * (1 - stop_pct * self.args.profit_multiple)
        stop = _round_price(stop, digits)
        profit = _round_price(profit, digits)
        size = self._size_for(market)
        record.update(
            {
                "size": size,
                "stop_level": stop,
                "profit_level": profit,
            }
        )
        payload: dict[str, Any] = {
            "epic": market["epic"],
            "direction": side,
            "size": size,
            "stopLevel": stop,
            "profitLevel": profit,
            "guaranteedStop": False,
            "forceOpen": True,
        }
        print(
            f"[order {number}] {side} {symbol} size={size} "
            f"SL={stop} TP={profit} (demo)"
        )
        created = self.client.json(
            "POST", "/api/v1/positions", json_body=payload
        )
        deal_reference = str(created.get("dealReference") or "")
        if not deal_reference:
            raise RuntimeError(f"create position returned no dealReference: {created}")
        record["deal_reference"] = deal_reference
        confirm = self._confirm(deal_reference)
        record["confirm"] = confirm
        status = str(confirm.get("dealStatus") or "").upper()
        if status in {"REJECTED", "REJECT"}:
            raise RuntimeError(
                f"Capital.com rejected {symbol}: {confirm.get('reason') or status}"
            )
        deal_id = _deal_id(confirm)
        if not deal_id:
            raise RuntimeError(f"no dealId in confirmation: {confirm}")
        record["deal_id"] = deal_id
        record["fill_level"] = _number(confirm.get("level"))

        position = self._position(deal_id)
        record["position"] = position
        sl_tp_state = self._sl_tp_state(position)
        sl_tp_visible = self._has_sl_tp(position)
        record["sl_tp_state"] = sl_tp_state
        record["sl_tp_visible"] = sl_tp_visible
        if not sl_tp_visible and self.args.repair_stops:
            repair = self.client.json(
                "PUT",
                f"/api/v1/positions/{quote(deal_id)}",
                json_body={"stopLevel": stop, "profitLevel": profit},
                allow_404=True,
            )
            record["stop_repair"] = repair
            position = self._position(deal_id)
            record["position_after_repair"] = position
            sl_tp_state = self._sl_tp_state(position)
            sl_tp_visible = self._has_sl_tp(position)
            record["sl_tp_state"] = sl_tp_state
            record["sl_tp_visible"] = sl_tp_visible
            record["sl_tp_state_after_repair"] = sl_tp_state
            record["sl_tp_visible_after_repair"] = sl_tp_visible

        close = self._close(deal_id)
        record["close"] = close
        record["closed"] = bool(close.get("closed"))
        record["ok"] = bool(record["closed"] and sl_tp_visible)
        if not sl_tp_visible:
            self._add_error(
                f"{symbol}: SL/TP not visible on demo position {deal_id}"
            )
        if not record["closed"]:
            self._add_error(f"{symbol}: position {deal_id} did not close")

    def _confirm(self, deal_reference: str) -> dict[str, Any]:
        path = f"/api/v1/confirms/{quote(deal_reference)}"
        last: dict[str, Any] = {}
        for attempt in range(12):
            response = self.client.request("GET", path, allow_404=True)
            if response.status_code == 200:
                try:
                    last = response.json()
                except ValueError:
                    last = {}
                status = str(last.get("dealStatus") or "").upper()
                if _deal_id(last) and status not in {"", "PENDING"}:
                    return last
                if status in {"REJECTED", "REJECT"}:
                    return last
            time.sleep(0.5 + attempt * 0.1)
        raise RuntimeError(f"deal confirmation timed out: {last}")

    def _position(self, deal_id: str) -> dict[str, Any] | None:
        path = f"/api/v1/positions/{quote(deal_id)}"
        response = self.client.request("GET", path, allow_404=True)
        if response.status_code == 404:
            return None
        try:
            data = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        position = data.get("position")
        return position if isinstance(position, dict) else data

    def _sl_tp_state(self, position: dict[str, Any] | None) -> dict[str, float]:
        if not position:
            return {"stop": 0.0, "profit": 0.0}
        stop = _number(position.get("stopLevel"))
        if stop == 0:
            stop = _number(position.get("stopLoss"))
        profit = _number(position.get("profitLevel"))
        if profit == 0:
            profit = _number(position.get("takeProfit"))
        return {"stop": stop, "profit": profit}

    def _has_sl_tp(self, position: dict[str, Any] | None) -> bool:
        state = self._sl_tp_state(position)
        return state["stop"] > 0 and state["profit"] > 0

    def _close(self, deal_id: str) -> dict[str, Any]:
        path = f"/api/v1/positions/{quote(deal_id)}"
        response = self.client.request("DELETE", path, allow_404=True)
        if response.status_code == 404:
            return {"http_status": 404, "already_closed": True, "closed": True}
        try:
            body = response.json()
        except ValueError:
            body = {}
        result: dict[str, Any] = {
            "http_status": response.status_code,
            "body": body,
            "closed": False,
        }
        deal_reference = str(body.get("dealReference") or "")
        if deal_reference:
            try:
                result["confirm"] = self._confirm(deal_reference)
            except Exception as exc:  # noqa: BLE001 - verify via position
                result["confirm_error"] = str(exc)
        for _ in range(10):
            if self._position(deal_id) is None:
                result["closed"] = True
                break
            time.sleep(0.5)
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capital.com REST demo spike (standalone; no backend changes)."
    )
    parser.add_argument("--env", choices=["demo", "live"], default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--round-trips", type=int, default=1)
    parser.add_argument("--symbols", type=_parse_symbols, default=DEFAULT_SYMBOLS)
    parser.add_argument("--side", choices=["BUY", "SELL", "ALTERNATE"], default="ALTERNATE")
    parser.add_argument("--size", type=float, default=None)
    parser.add_argument("--stop-pct", type=float, default=None)
    parser.add_argument("--profit-multiple", type=float, default=2.0)
    parser.add_argument(
        "--no-repair-stops",
        action="store_false",
        dest="repair_stops",
        help="do not attempt PUT /positions/{dealId} when SL/TP are missing",
    )
    parser.set_defaults(repair_stops=True)
    parser.add_argument("--test-session-refresh", action="store_true")
    parser.add_argument("--report", default=None)
    parser.add_argument("--allow-live", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    creds = _credentials(args)
    return CapitalSpike(args, creds).run()


if __name__ == "__main__":
    raise SystemExit(main())
