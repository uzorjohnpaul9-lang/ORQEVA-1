"""Pepperstone cTrader Open API demo spike.

This is deliberately standalone. It does not import the backend, touch the
database, or change the live Exness connection.

Run with the dedicated spike venv:
    scripts\\broker_spikes\\.venv\\Scripts\\python.exe scripts\\broker_spike_ctrader.py

Read-only checks (default):
    ... scripts\\broker_spike_ctrader.py

Demo order checks (explicit opt-in):
    ... scripts\\broker_spike_ctrader.py --execute --round-trips 5

The report is written to temp/broker_spike_ctrader.json by default. Credentials
are read from environment variables (or temp/ctrader_tokens.json) and are never
included in the report.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "temp" / "broker_spike_ctrader.json"
DEFAULT_TOKEN_FILE = ROOT / "temp" / "ctrader_tokens.json"
DEFAULT_SYMBOLS = ["EURUSD", "GBPUSD", "USDCHF", "NZDUSD", "USDCAD", "XAUUSD"]
AUTH_URI = "https://openapi.ctrader.com/apps/auth"
TOKEN_URI = "https://openapi.ctrader.com/apps/token"
PRICE_SCALE = 100_000.0


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


def _normalize_symbol(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _resolve_report_path(raw: str | None) -> Path:
    path = Path(raw) if raw else DEFAULT_REPORT
    if not path.is_absolute():
        path = ROOT / path
    return path


def _resolve_token_path(raw: str | None) -> Path:
    path = Path(raw) if raw else DEFAULT_TOKEN_FILE
    if not path.is_absolute():
        path = ROOT / path
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _load_tokens(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _auth_url(client_id: str, redirect_uri: str) -> str:
    return f"{AUTH_URI}?{urlencode({'client_id': client_id, 'redirect_uri': redirect_uri, 'scope': 'trading'})}"


def _exchange_auth_code(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    auth_code: str,
    token_out: Path,
) -> int:
    import requests

    response = requests.get(
        TOKEN_URI,
        params={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        print(f"Token exchange failed: HTTP {response.status_code} non-JSON response")
        return 1
    if response.status_code != 200 or not payload.get("accessToken"):
        print(f"Token exchange failed: HTTP {response.status_code}: {payload}")
        return 1
    _write_json(token_out, payload)
    try:
        os.chmod(token_out, 0o600)
    except OSError:
        pass
    print(f"Token exchange succeeded. Tokens written to: {token_out}")
    print("Set CTRADER_ACCESS_TOKEN and CTRADER_REFRESH_TOKEN from that file.")
    return 0


@dataclass
class Credentials:
    env: str
    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    account_id: int | None
    redirect_uri: str


def _credentials(args: argparse.Namespace) -> Credentials:
    env = (args.env or _env("CTRADER_ENV", "demo") or "demo").lower()
    if env not in {"demo", "live"}:
        raise SystemExit("CTRADER_ENV must be demo or live")
    if env == "live" and not args.allow_live:
        raise SystemExit("Refusing live cTrader: pass --allow-live to override")

    client_id = _env("CTRADER_CLIENT_ID")
    client_secret = _env("CTRADER_CLIENT_SECRET")
    token_path = _resolve_token_path(args.token_file)
    tokens = _load_tokens(token_path)
    access_token = _env("CTRADER_ACCESS_TOKEN") or str(tokens.get("accessToken") or "")
    refresh_token = _env("CTRADER_REFRESH_TOKEN") or str(tokens.get("refreshToken") or "")
    account_raw = args.account_id or _env("CTRADER_ACCOUNT_ID")
    try:
        account_id = int(account_raw) if account_raw else None
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"CTRADER_ACCOUNT_ID must be an integer: {account_raw}") from exc

    missing = []
    if not client_id:
        missing.append("CTRADER_CLIENT_ID")
    if not client_secret:
        missing.append("CTRADER_CLIENT_SECRET")
    if not access_token and not refresh_token:
        missing.append("CTRADER_ACCESS_TOKEN or CTRADER_REFRESH_TOKEN")
    if missing:
        raise SystemExit(
            "Missing cTrader credentials: "
            + ", ".join(missing)
            + "\n\nPowerShell example:\n"
            + '  $env:CTRADER_CLIENT_ID="..."\n'
            + '  $env:CTRADER_CLIENT_SECRET="..."\n'
            + '  $env:CTRADER_ACCESS_TOKEN="..."\n'
            + '  $env:CTRADER_REFRESH_TOKEN="..."\n'
            + '  $env:CTRADER_ACCOUNT_ID="..."\n'
            + "\nOr create an auth URL with:\n"
            + "  python scripts/broker_spike_ctrader.py --auth-url\n"
        )

    return Credentials(
        env=env,
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        refresh_token=refresh_token,
        account_id=account_id,
        redirect_uri=args.redirect_uri,
    )


def _refresh_access_token(
    creds: Credentials, token_out: Path | None = None
) -> str | None:
    if not creds.refresh_token:
        return None
    try:
        import requests

        response = requests.get(
            TOKEN_URI,
            params={
                "grant_type": "refresh_token",
                "refresh_token": creds.refresh_token,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
            },
            timeout=30,
        )
        payload = response.json()
        if response.status_code == 200 and payload.get("accessToken"):
            creds.access_token = str(payload["accessToken"])
            if payload.get("refreshToken"):
                creds.refresh_token = str(payload["refreshToken"])
            if token_out is not None:
                try:
                    _write_json(token_out, payload)
                    os.chmod(token_out, 0o600)
                except OSError as exc:
                    print(f"Warning: could not persist refreshed cTrader tokens: {exc}")
            return None
        return f"HTTP {response.status_code}: {payload}"
    except Exception as exc:  # pragma: no cover - network dependent
        return str(exc)


class CtraderSpike:
    def __init__(self, args: argparse.Namespace, creds: Credentials) -> None:
        self.args = args
        self.creds = creds
        self.report: dict[str, Any] = {
            "broker": "ctrader",
            "broker_variant": args.broker,
            "environment": creds.env,
            "started_at": _iso_now(),
            "checks": {},
            "accounts": [],
            "symbols": [],
            "spot": None,
            "orders": [],
            "execution_events": [],
            "errors": [],
        }
        self._finished = False
        self._exit_code = 1
        self._client: Any = None
        self._reactor: Any = None
        self._OA: Any = None
        self._OAM: Any = None
        self._Protobuf: Any = None
        self._timeout_call: Any = None
        self._wanted_ids: dict[str, int] = {}
        self._symbol_details: dict[str, dict[str, Any]] = {}
        self._spot_symbol: dict[str, Any] | None = None
        self._after_spot_done = False
        self._round_trip_index = 0
        self._last_price: float | None = None
        self._limit_done = False

    def run(self) -> int:
        self._load_modules()
        host = (
            self._EndPoints.PROTOBUF_LIVE_HOST
            if self.creds.env == "live"
            else self._EndPoints.PROTOBUF_DEMO_HOST
        )
        self.report["host"] = host
        self._client = self._Client(
            host,
            self._EndPoints.PROTOBUF_PORT,
            self._TcpProtocol,
            numberOfMessagesToSendPerSecond=20,
        )
        self._client.setConnectedCallback(self._on_connected)
        self._client.setDisconnectedCallback(self._on_disconnected)
        self._client.setMessageReceivedCallback(self._on_message)
        self._timeout_call = self._reactor.callLater(
            self.args.timeout, self._on_timeout
        )
        self._client.startService()
        self._reactor.run()
        return self._exit_code

    def _load_modules(self) -> None:
        try:
            from ctrader_open_api import Client, EndPoints, Protobuf, TcpProtocol
            from ctrader_open_api.messages import OpenApiMessages_pb2 as OA
            from ctrader_open_api.messages import OpenApiModelMessages_pb2 as OAM
            from twisted.internet import reactor
        except ImportError as exc:  # pragma: no cover - dependency dependent
            raise SystemExit(
                "Missing cTrader Open API dependency.\n"
                "Install it in the dedicated spike venv:\n"
                "  python -m venv scripts\\broker_spikes\\.venv\n"
                "  scripts\\broker_spikes\\.venv\\Scripts\\python.exe "
                "-m pip install -r scripts\\broker_spikes\\requirements.txt\n"
                f"Original error: {exc}"
            ) from exc
        self._Client = Client
        self._EndPoints = EndPoints
        self._Protobuf = Protobuf
        self._TcpProtocol = TcpProtocol
        self._OA = OA
        self._OAM = OAM
        self._reactor = reactor

    def _send(self, request: Any, callback: Any, timeout: int = 10) -> None:
        def safe_callback(message: Any) -> None:
            try:
                callback(message)
            except Exception as exc:  # pragma: no cover - defensive
                self._on_error(exc)

        try:
            deferred = self._client.send(
                request, responseTimeoutInSeconds=timeout
            )
        except Exception as exc:  # pragma: no cover - defensive
            self._on_error(exc)
            return
        deferred.addCallbacks(safe_callback, self._on_error)

    def _extract(self, message: Any) -> Any:
        if message.payloadType == self._OA.ProtoOAErrorRes().payloadType:
            error = self._Protobuf.extract(message)
            detail = (
                getattr(error, "description", "")
                or getattr(error, "errorCode", "")
                or "unknown cTrader error"
            )
            raise RuntimeError(f"cTrader error: {detail}")
        return self._Protobuf.extract(message)

    def _check(self, name: str, ok: bool, detail: str = "") -> None:
        self.report["checks"][name] = {"ok": bool(ok), "detail": detail}

    def _add_error(self, message: str) -> None:
        self.report["errors"].append(message)
        print(f"ERROR: {message}")

    def _on_error(self, failure: Any) -> None:
        if hasattr(failure, "getErrorMessage"):
            message = failure.getErrorMessage()
        else:
            message = str(failure)
        self._add_error(message)
        self._finish(1)

    def _on_timeout(self) -> None:
        self._add_error(f"spike timed out after {self.args.timeout}s")
        self._finish(1)

    def _on_disconnected(self, client: Any, reason: Any) -> None:
        if not self._finished:
            self._add_error(f"disconnected: {reason}")
            self._finish(1)

    def _on_connected(self, client: Any) -> None:
        self._check("connected", True)
        request = self._OA.ProtoOAApplicationAuthReq()
        request.clientId = self.creds.client_id
        request.clientSecret = self.creds.client_secret
        self._send(request, self._on_application_auth, timeout=15)

    def _on_application_auth(self, message: Any) -> None:
        self._extract(message)
        self._check("application_auth", True)
        request = self._OA.ProtoOAGetAccountListByAccessTokenReq()
        request.accessToken = self.creds.access_token
        self._send(request, self._on_accounts, timeout=20)

    def _on_accounts(self, message: Any) -> None:
        response = self._extract(message)
        accounts = []
        for account in response.ctidTraderAccount:
            accounts.append(
                {
                    "account_id": int(account.ctidTraderAccountId),
                    "is_live": bool(account.isLive),
                    "trader_login": int(account.traderLogin),
                }
            )
        self.report["accounts"] = accounts
        self.report["permission_scope"] = int(
            getattr(response, "permissionScope", 0)
        )
        self._check("account_list", bool(accounts), f"{len(accounts)} account(s)")
        if not accounts:
            raise RuntimeError("access token returned no cTrader accounts")

        account = self._choose_account(accounts)
        self.report["account"] = account
        is_live = bool(account["is_live"])
        if self.creds.env == "demo" and is_live:
            raise RuntimeError("selected account is live; demo was requested")
        if self.creds.env == "live" and not is_live:
            raise RuntimeError("selected account is demo; live was requested")
        self._check("account_environment", True, self.creds.env)

        request = self._OA.ProtoOAAccountAuthReq()
        request.ctidTraderAccountId = account["account_id"]
        request.accessToken = self.creds.access_token
        self._send(request, self._on_account_auth, timeout=15)

    def _choose_account(self, accounts: list[dict[str, Any]]) -> dict[str, Any]:
        if self.creds.account_id is not None:
            for account in accounts:
                if account["account_id"] == self.creds.account_id:
                    return account
            raise RuntimeError(
                f"CTRADER_ACCOUNT_ID {self.creds.account_id} not found"
            )
        want_live = self.creds.env == "live"
        for account in accounts:
            if bool(account["is_live"]) is want_live:
                return account
        return accounts[0]

    def _on_account_auth(self, message: Any) -> None:
        response = self._extract(message)
        account_id = int(response.ctidTraderAccountId)
        self._check("account_auth", True, str(account_id))
        request = self._OA.ProtoOATraderReq()
        request.ctidTraderAccountId = account_id
        self._send(request, self._on_trader, timeout=15)

    def _on_trader(self, message: Any) -> None:
        response = self._extract(message)
        trader = response.trader
        money_digits = int(getattr(trader, "moneyDigits", 0) or 0)
        divisor = 10 ** money_digits if money_digits else 1
        balance = float(trader.balance) / divisor
        self.report["trader"] = {
            "account_id": int(trader.ctidTraderAccountId),
            "balance": balance,
            "money_digits": money_digits,
            "leverage_in_cents": int(getattr(trader, "leverageInCents", 0) or 0),
            "max_leverage": int(getattr(trader, "maxLeverage", 0) or 0),
            "broker_name": getattr(trader, "brokerName", "") or "",
            "account_type": int(getattr(trader, "accountType", 0) or 0),
            "deposit_asset_id": int(getattr(trader, "depositAssetId", 0) or 0),
        }
        self._check("trader", True, f"balance={balance}")
        request = self._OA.ProtoOASymbolsListReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.includeArchivedSymbols = False
        self._send(request, self._on_symbols, timeout=20)

    def _on_symbols(self, message: Any) -> None:
        response = self._extract(message)
        available: list[dict[str, Any]] = []
        for symbol in response.symbol:
            if not bool(getattr(symbol, "enabled", True)):
                continue
            available.append(
                {
                    "symbol_id": int(symbol.symbolId),
                    "name": str(symbol.symbolName),
                }
            )
        by_name = {_normalize_symbol(item["name"]): item for item in available}
        wanted_ids: dict[str, int] = {}
        for target in self.args.symbols:
            match = by_name.get(_normalize_symbol(target))
            if match:
                wanted_ids[target] = match["symbol_id"]
        self.report["available_symbol_count"] = len(available)
        self._wanted_ids = wanted_ids
        missing = [symbol for symbol in self.args.symbols if symbol not in wanted_ids]
        self._check(
            "symbol_lookup",
            len(wanted_ids) == len(self.args.symbols),
            f"missing={missing}" if missing else "all requested symbols found",
        )
        if not wanted_ids:
            raise RuntimeError("none of the requested symbols are available")

        request = self._OA.ProtoOASymbolByIdReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.symbolId.extend(wanted_ids.values())
        self._send(request, self._on_symbol_details, timeout=20)

    def _on_symbol_details(self, message: Any) -> None:
        response = self._extract(message)
        details_by_id: dict[int, dict[str, Any]] = {}
        for symbol in response.symbol:
            details_by_id[int(symbol.symbolId)] = {
                "symbol_id": int(symbol.symbolId),
                "digits": int(getattr(symbol, "digits", 0) or 0),
                "pip_position": int(getattr(symbol, "pipPosition", 0) or 0),
                "min_volume": int(getattr(symbol, "minVolume", 0) or 0),
                "max_volume": int(getattr(symbol, "maxVolume", 0) or 0),
                "step_volume": int(getattr(symbol, "stepVolume", 0) or 0),
                "lot_size": int(getattr(symbol, "lotSize", 0) or 0),
                "commission": int(getattr(symbol, "commission", 0) or 0),
            }
        self._symbol_details = {}
        for name, symbol_id in self._wanted_ids.items():
            detail = details_by_id.get(symbol_id)
            if detail:
                detail["name"] = name
                self._symbol_details[name] = detail
        self.report["symbols"] = list(self._symbol_details.values())
        self._check(
            "symbol_details",
            len(self._symbol_details) == len(self._wanted_ids),
            f"{len(self._symbol_details)} resolved",
        )

        first = next(iter(self._symbol_details.values()))
        self._spot_symbol = first
        request = self._OA.ProtoOASubscribeSpotsReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.symbolId.append(first["symbol_id"])
        request.subscribeToSpotTimestamp = True
        self._send(request, self._on_spot_subscribed, timeout=10)

    def _on_spot_subscribed(self, message: Any) -> None:
        self._extract(message)
        self._reactor.callLater(self.args.spot_wait, self._after_spot)

    def _on_message(self, client: Any, message: Any) -> None:
        try:
            if message.payloadType == self._OA.ProtoOASpotEvent().payloadType:
                event = self._Protobuf.extract(message)
                if self._spot_symbol and int(event.symbolId) == self._spot_symbol["symbol_id"]:
                    bid_raw = int(event.bid)
                    ask_raw = int(event.ask)
                    self.report["spot"] = {
                        "symbol": self._spot_symbol["name"],
                        "symbol_id": self._spot_symbol["symbol_id"],
                        "bid_raw": bid_raw,
                        "ask_raw": ask_raw,
                        "bid": bid_raw / PRICE_SCALE,
                        "ask": ask_raw / PRICE_SCALE,
                        "timestamp": int(getattr(event, "timestamp", 0) or 0),
                    }
                    self._check("spot_quote", True)
                    self._reactor.callLater(0, self._after_spot)
            elif message.payloadType == self._OA.ProtoOAExecutionEvent().payloadType:
                event = self._Protobuf.extract(message)
                self.report["execution_events"].append(self._exec_info(event))
        except Exception as exc:  # pragma: no cover - defensive
            self._add_error(f"message handling failed: {exc}")

    def _exec_info(self, event: Any) -> dict[str, Any]:
        info: dict[str, Any] = {
            "execution_type": int(getattr(event, "executionType", 0) or 0),
            "error_code": getattr(event, "errorCode", "") or "",
        }
        try:
            if event.HasField("position"):
                position = event.position
                info["position_id"] = int(position.positionId)
                info["position_status"] = int(
                    getattr(position, "positionStatus", 0) or 0
                )
                if position.HasField("tradeData"):
                    info["symbol_id"] = int(position.tradeData.symbolId)
                    info["volume"] = int(position.tradeData.volume)
                    info["side"] = int(position.tradeData.tradeSide)
                if position.HasField("price"):
                    info["price"] = float(position.price)
                if position.HasField("stopLoss"):
                    info["stop_loss"] = float(position.stopLoss)
                if position.HasField("takeProfit"):
                    info["take_profit"] = float(position.takeProfit)
        except Exception:
            pass
        try:
            if event.HasField("order"):
                order = event.order
                info["order_id"] = int(order.orderId)
                info["order_status"] = int(
                    getattr(order, "orderStatus", 0) or 0
                )
                info["executed_volume"] = int(
                    getattr(order, "executedVolume", 0) or 0
                )
                if order.HasField("executionPrice"):
                    info["execution_price"] = float(order.executionPrice)
        except Exception:
            pass
        try:
            if event.HasField("deal"):
                deal = event.deal
                info["deal_id"] = int(deal.dealId)
                info["deal_position_id"] = int(deal.positionId)
                if deal.HasField("executionPrice"):
                    info["deal_price"] = float(deal.executionPrice)
        except Exception:
            pass
        return info

    def _after_spot(self) -> None:
        if self._after_spot_done:
            return
        self._after_spot_done = True
        read_checks = [
            "connected",
            "application_auth",
            "account_list",
            "account_environment",
            "account_auth",
            "trader",
            "symbol_lookup",
            "symbol_details",
        ]
        read_ok = all(self.report["checks"].get(name, {}).get("ok") for name in read_checks)
        if not self.args.execute:
            self._finish(0 if read_ok else 1)
            return
        if not read_ok:
            self._finish(1)
            return
        scope = int(self.report.get("permission_scope", 0) or 0)
        if scope == 0:
            self._add_error("access token has view-only scope; cannot trade")
            self._finish(1)
            return
        self._start_round_trips()

    def _start_round_trips(self) -> None:
        if self._round_trip_index >= self.args.round_trips:
            if self.args.limit_order and not self._limit_done:
                self._place_limit_order()
            else:
                self._finish_after_orders()
            return
        index = self._round_trip_index
        self._round_trip_index += 1
        names = list(self._symbol_details)
        symbol = names[index % len(names)]
        side = self._side_for_index(index)
        self._place_market_order(symbol, side, index + 1)

    def _side_for_index(self, index: int) -> str:
        if self.args.side == "ALTERNATE":
            return "BUY" if index % 2 == 0 else "SELL"
        return self.args.side

    def _volume_for(self, detail: dict[str, Any]) -> int:
        lot_size = int(detail.get("lot_size") or 0) or 10_000_000
        min_volume = int(detail.get("min_volume") or 0)
        max_volume = int(detail.get("max_volume") or 0)
        step_volume = int(detail.get("step_volume") or 0)
        volume = int(round(self.args.lots * lot_size))
        if step_volume > 0:
            volume = ((volume + step_volume - 1) // step_volume) * step_volume
        if min_volume > 0 and volume < min_volume:
            volume = min_volume
        if step_volume > 0:
            volume = ((volume + step_volume - 1) // step_volume) * step_volume
        if max_volume > 0:
            volume = min(volume, max_volume)
        return max(volume, 1)

    def _place_market_order(self, symbol: str, side: str, number: int) -> None:
        detail = self._symbol_details[symbol]
        volume = self._volume_for(detail)
        request = self._OA.ProtoOANewOrderReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.symbolId = detail["symbol_id"]
        request.orderType = self._OAM.ProtoOAOrderType.MARKET
        request.tradeSide = (
            self._OAM.ProtoOATradeSide.BUY
            if side == "BUY"
            else self._OAM.ProtoOATradeSide.SELL
        )
        request.volume = volume
        request.comment = f"broker spike #{number}"
        print(f"[order {number}] {side} {symbol} volume={volume} (demo)")
        self._send(
            request,
            lambda message: self._on_market_order(
                message, symbol, side, volume, number
            ),
            timeout=20,
        )

    def _on_market_order(
        self,
        message: Any,
        symbol: str,
        side: str,
        volume: int,
        number: int,
    ) -> None:
        event = self._extract(message)
        info = self._exec_info(event)
        record = {
            "kind": "market",
            "number": number,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "response": info,
            "ok": False,
        }
        self.report["orders"].append(record)
        rejected_types = {
            int(self._OAM.ProtoOAExecutionType.ORDER_REJECTED),
            int(self._OAM.ProtoOAExecutionType.ORDER_CANCEL_REJECTED),
            int(self._OAM.ProtoOAExecutionType.ORDER_EXPIRED),
        }
        if info.get("error_code") or info.get("execution_type") in rejected_types:
            self._add_error(
                f"market order rejected: "
                f"{info.get('error_code') or info.get('execution_type')}"
            )
            self._next_round_trip()
            return
        filled = info.get("execution_type") == int(
            self._OAM.ProtoOAExecutionType.ORDER_FILLED
        )
        position_id = info.get("position_id")
        if filled and position_id:
            record["position_id"] = position_id
            self._after_fill(record, symbol, side, info)
            return
        if position_id:
            record["position_id"] = position_id
            self._wait_position(record, symbol, side, position_id, 6)
            return
        self._add_error("market order returned no position id")
        self._next_round_trip()

    def _wait_position(
        self,
        record: dict[str, Any],
        symbol: str,
        side: str,
        position_id: int,
        attempts: int,
    ) -> None:
        request = self._OA.ProtoOAReconcileReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        self._send(
            request,
            lambda message: self._on_reconcile(
                message, record, symbol, side, position_id, attempts
            ),
            timeout=15,
        )

    def _on_reconcile(
        self,
        message: Any,
        record: dict[str, Any],
        symbol: str,
        side: str,
        position_id: int,
        attempts: int,
    ) -> None:
        response = self._extract(message)
        position = next(
            (
                item
                for item in response.position
                if int(item.positionId) == int(position_id)
            ),
            None,
        )
        open_statuses = {
            int(self._OAM.ProtoOAPositionStatus.POSITION_STATUS_OPEN),
            int(self._OAM.ProtoOAPositionStatus.POSITION_STATUS_CREATED),
        }
        if (
            position
            and int(getattr(position, "positionStatus", 0) or 0) in open_statuses
            and int(getattr(position.tradeData, "volume", 0) or 0) > 0
        ):
            info = {
                "position_id": int(position.positionId),
                "price": float(getattr(position, "price", 0) or 0),
                "volume": int(position.tradeData.volume),
                "symbol_id": int(position.tradeData.symbolId),
                "side": int(position.tradeData.tradeSide),
            }
            record["position"] = info
            self._after_fill(record, symbol, side, info)
            return
        if attempts > 1:
            self._reactor.callLater(
                1, self._wait_position, record, symbol, side, position_id, attempts - 1
            )
            return
        self._add_error(f"position {position_id} did not appear after fill")
        self._next_round_trip()

    def _after_fill(
        self,
        record: dict[str, Any],
        symbol: str,
        side: str,
        info: dict[str, Any],
    ) -> None:
        detail = self._symbol_details[symbol]
        entry = float(info.get("price") or 0)
        if entry <= 0 and self.report.get("spot"):
            spot = self.report["spot"]
            entry = float(spot["ask"] if side == "BUY" else spot["bid"])
        if entry <= 0:
            entry = float(self._last_price or 0)
        if entry <= 0:
            record["sl_tp_ok"] = False
            self._add_error(f"no usable price for {symbol}; closing without SL/TP")
            self._close_position(record, symbol, side, info)
            return
        self._last_price = entry
        stop_pct = self.args.stop_pct or (0.01 if "XAU" in symbol else 0.002)
        if side == "BUY":
            stop_loss = entry * (1 - stop_pct)
            take_profit = entry * (1 + stop_pct * self.args.profit_multiple)
        else:
            stop_loss = entry * (1 + stop_pct)
            take_profit = entry * (1 - stop_pct * self.args.profit_multiple)
        digits = int(detail.get("digits") or 5)
        stop_loss = round(stop_loss, digits)
        take_profit = round(take_profit, digits)
        record["stop_loss"] = stop_loss
        record["take_profit"] = take_profit

        request = self._OA.ProtoOAAmendPositionSLTPReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.positionId = int(info["position_id"])
        request.stopLoss = stop_loss
        request.takeProfit = take_profit
        self._send(
            request,
            lambda message: self._on_amend(
                message, record, symbol, side, info, stop_loss, take_profit
            ),
            timeout=15,
        )

    def _on_amend(
        self,
        message: Any,
        record: dict[str, Any],
        symbol: str,
        side: str,
        info: dict[str, Any],
        stop_loss: float,
        take_profit: float,
    ) -> None:
        event = self._extract(message)
        amend_info = self._exec_info(event)
        record["amend_response"] = amend_info
        rejected_types = {
            int(self._OAM.ProtoOAExecutionType.ORDER_REJECTED),
            int(self._OAM.ProtoOAExecutionType.ORDER_CANCEL_REJECTED),
            int(self._OAM.ProtoOAExecutionType.ORDER_EXPIRED),
        }
        if amend_info.get("error_code") or amend_info.get(
            "execution_type"
        ) in rejected_types:
            record["sl_tp_ok"] = False
            self._add_error(
                f"SL/TP amend rejected: "
                f"{amend_info.get('error_code') or amend_info.get('execution_type')}"
            )
            self._close_position(record, symbol, side, info)
            return
        self._verify_sl_tp(
            record,
            symbol,
            side,
            info,
            stop_loss,
            take_profit,
            4,
        )

    def _verify_sl_tp(
        self,
        record: dict[str, Any],
        symbol: str,
        side: str,
        info: dict[str, Any],
        stop_loss: float,
        take_profit: float,
        attempts: int,
    ) -> None:
        request = self._OA.ProtoOAReconcileReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        self._send(
            request,
            lambda message: self._on_verify_sl_tp(
                message,
                record,
                symbol,
                side,
                info,
                stop_loss,
                take_profit,
                attempts,
            ),
            timeout=15,
        )

    def _on_verify_sl_tp(
        self,
        message: Any,
        record: dict[str, Any],
        symbol: str,
        side: str,
        info: dict[str, Any],
        stop_loss: float,
        take_profit: float,
        attempts: int,
    ) -> None:
        response = self._extract(message)
        position = next(
            (
                item
                for item in response.position
                if int(item.positionId) == int(info["position_id"])
            ),
            None,
        )
        if position is not None:
            actual_stop = (
                float(position.stopLoss) if position.HasField("stopLoss") else 0.0
            )
            actual_profit = (
                float(position.takeProfit)
                if position.HasField("takeProfit")
                else 0.0
            )
            detail = self._symbol_details[symbol]
            digits = int(detail.get("digits") or 5)
            tolerance = (10 ** -digits) * 1.5
            stop_ok = actual_stop > 0 and abs(actual_stop - stop_loss) <= tolerance
            profit_ok = (
                actual_profit > 0
                and abs(actual_profit - take_profit) <= tolerance
            )
            record["applied_stop_loss"] = actual_stop
            record["applied_take_profit"] = actual_profit
            if stop_ok and profit_ok:
                record["sl_tp_ok"] = True
                self._close_position(record, symbol, side, info)
                return
            record["sl_tp_ok"] = False
            self._add_error(
                f"SL/TP not applied on position {info['position_id']}: "
                f"stop={actual_stop} target={stop_loss}, "
                f"profit={actual_profit} target={take_profit}"
            )
            self._close_position(record, symbol, side, info)
            return
        if attempts > 1:
            self._reactor.callLater(
                1,
                self._verify_sl_tp,
                record,
                symbol,
                side,
                info,
                stop_loss,
                take_profit,
                attempts - 1,
            )
            return
        record["sl_tp_ok"] = False
        self._add_error(
            f"position {info['position_id']} disappeared before SL/TP verification"
        )
        self._next_round_trip()

    def _close_position(
        self,
        record: dict[str, Any],
        symbol: str,
        side: str,
        info: dict[str, Any],
    ) -> None:
        volume = int(info.get("volume") or record.get("volume") or 0)
        if volume <= 0:
            self._add_error("cannot close: volume is zero")
            self._next_round_trip()
            return
        request = self._OA.ProtoOAClosePositionReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.positionId = int(info["position_id"])
        request.volume = volume
        self._send(
            request,
            lambda message: self._on_close(
                message, record, symbol, side, int(info["position_id"])
            ),
            timeout=20,
        )

    def _on_close(
        self,
        message: Any,
        record: dict[str, Any],
        symbol: str,
        side: str,
        position_id: int,
    ) -> None:
        event = self._extract(message)
        record["close_response"] = self._exec_info(event)
        self._verify_closed(record, position_id, 6)

    def _verify_closed(
        self,
        record: dict[str, Any],
        position_id: int,
        attempts: int,
    ) -> None:
        request = self._OA.ProtoOAReconcileReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        self._send(
            request,
            lambda message: self._on_verify_closed(
                message, record, position_id, attempts
            ),
            timeout=15,
        )

    def _on_verify_closed(
        self,
        message: Any,
        record: dict[str, Any],
        position_id: int,
        attempts: int,
    ) -> None:
        response = self._extract(message)
        open_statuses = {
            int(self._OAM.ProtoOAPositionStatus.POSITION_STATUS_OPEN),
            int(self._OAM.ProtoOAPositionStatus.POSITION_STATUS_CREATED),
        }
        still_open = any(
            int(item.positionId) == int(position_id)
            and int(getattr(item, "positionStatus", 0) or 0) in open_statuses
            for item in response.position
        )
        if not still_open:
            record["ok"] = True
            record["closed"] = True
            self._check("market_order_round_trip", True)
            self._next_round_trip()
            return
        if attempts > 1:
            self._reactor.callLater(
                1, self._verify_closed, record, position_id, attempts - 1
            )
            return
        self._add_error(f"position {position_id} still open after close")
        self._next_round_trip()

    def _next_round_trip(self) -> None:
        self._reactor.callLater(0.2, self._start_round_trips)

    def _place_limit_order(self) -> None:
        self._limit_done = True
        if not self._symbol_details:
            self._finish_after_orders()
            return
        symbol = next(iter(self._symbol_details))
        detail = self._symbol_details[symbol]
        price = self._last_price
        if not price and self.report.get("spot"):
            spot = self.report["spot"]
            price = (float(spot["bid"]) + float(spot["ask"])) / 2
        if not price:
            record = {
                "kind": "limit",
                "symbol": symbol,
                "ok": False,
                "detail": "no price available for limit order",
            }
            self.report["orders"].append(record)
            self._add_error(record["detail"])
            self._finish_after_orders()
            return
        side = "BUY"
        volume = self._volume_for(detail)
        limit_price = round(price * 0.95, int(detail.get("digits") or 5))
        request = self._OA.ProtoOANewOrderReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.symbolId = detail["symbol_id"]
        request.orderType = self._OAM.ProtoOAOrderType.LIMIT
        request.tradeSide = self._OAM.ProtoOATradeSide.BUY
        request.volume = volume
        request.limitPrice = limit_price
        request.comment = "broker spike limit"
        print(f"[limit] BUY {symbol} volume={volume} price={limit_price}")
        self._send(
            request,
            lambda message: self._on_limit_order(
                message, symbol, volume, limit_price
            ),
            timeout=20,
        )

    def _on_limit_order(
        self,
        message: Any,
        symbol: str,
        volume: int,
        limit_price: float,
    ) -> None:
        event = self._extract(message)
        info = self._exec_info(event)
        record = {
            "kind": "limit",
            "symbol": symbol,
            "side": "BUY",
            "volume": volume,
            "limit_price": limit_price,
            "response": info,
            "ok": False,
        }
        self.report["orders"].append(record)
        rejected_types = {
            int(self._OAM.ProtoOAExecutionType.ORDER_REJECTED),
            int(self._OAM.ProtoOAExecutionType.ORDER_CANCEL_REJECTED),
            int(self._OAM.ProtoOAExecutionType.ORDER_EXPIRED),
        }
        if info.get("error_code") or info.get("execution_type") in rejected_types:
            self._add_error(
                f"limit order rejected: "
                f"{info.get('error_code') or info.get('execution_type')}"
            )
            self._finish_after_orders()
            return
        if info.get("execution_type") == int(
            self._OAM.ProtoOAExecutionType.ORDER_FILLED
        ) and info.get("position_id"):
            record["position_id"] = info["position_id"]
            self._after_fill(record, symbol, "BUY", info)
            return
        order_id = info.get("order_id")
        if not order_id:
            self._add_error("limit order returned no order id")
            self._finish_after_orders()
            return
        request = self._OA.ProtoOACancelOrderReq()
        request.ctidTraderAccountId = self.report["account"]["account_id"]
        request.orderId = int(order_id)
        self._send(
            request,
            lambda cancel_message: self._on_limit_cancel(
                cancel_message, record
            ),
            timeout=15,
        )

    def _on_limit_cancel(
        self, message: Any, record: dict[str, Any]
    ) -> None:
        event = self._extract(message)
        info = self._exec_info(event)
        record["cancel_response"] = info
        cancelled = info.get("execution_type") == int(
            self._OAM.ProtoOAExecutionType.ORDER_CANCELLED
        ) or info.get("order_status") == int(
            self._OAM.ProtoOAOrderStatus.ORDER_STATUS_CANCELLED
        )
        if info.get("error_code") or not cancelled:
            record["ok"] = False
            self._add_error(
                f"limit order cancel failed: "
                f"{info.get('error_code') or info.get('execution_type')}"
            )
            self._finish_after_orders()
            return
        record["ok"] = True
        self._check("limit_order_accept_cancel", True)
        self._finish_after_orders()

    def _finish_after_orders(self) -> None:
        order_records = self.report["orders"]
        if not order_records:
            self._check("order_execution", False, "no orders were placed")
            self._finish(1)
            return
        passed = 0
        for item in order_records:
            item_ok = bool(item.get("ok"))
            if item.get("kind") == "market":
                item_ok = item_ok and bool(item.get("sl_tp_ok"))
            if item_ok:
                passed += 1
        ok = passed == len(order_records)
        self._check(
            "order_execution",
            ok,
            f"{passed}/{len(order_records)} passed",
        )
        self._finish(0 if ok else 1)

    def _finish(self, exit_code: int) -> None:
        if self._finished:
            return
        self._finished = True
        self._exit_code = exit_code
        self.report["finished_at"] = _iso_now()
        self.report["ok"] = bool(exit_code == 0)
        if self._timeout_call is not None:
            try:
                if self._timeout_call.active():
                    self._timeout_call.cancel()
            except Exception:
                pass
        report_path = _resolve_report_path(self.args.report)
        try:
            _write_json(report_path, self.report)
        except OSError as exc:
            print(f"Could not write report {report_path}: {exc}")
        checks = self.report["checks"]
        failed = [name for name, item in checks.items() if not item.get("ok")]
        print(
            f"\nctrader spike {'PASSED' if exit_code == 0 else 'FAILED'} "
            f"(env={self.creds.env}, broker={self.args.broker})"
        )
        print(f"Report: {report_path}")
        if failed:
            print(f"Failed checks: {', '.join(failed)}")
        if self.report["errors"]:
            print(f"Errors: {len(self.report['errors'])}")
        try:
            if self._client is not None and getattr(self._client, "running", False):
                self._client.stopService()
        except Exception:
            pass
        try:
            if self._reactor is not None and self._reactor.running:
                self._reactor.callLater(0.2, self._reactor.stop)
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pepperstone cTrader demo spike (standalone; no backend changes)."
    )
    parser.add_argument("--env", choices=["demo", "live"], default=None)
    parser.add_argument("--broker", default="Pepperstone")
    parser.add_argument("--account-id", default=None)
    parser.add_argument("--token-file", default=None)
    parser.add_argument("--redirect-uri", default="http://localhost:8080/callback")
    parser.add_argument("--auth-url", action="store_true")
    parser.add_argument("--auth-code", default=None)
    parser.add_argument("--token-out", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--round-trips", type=int, default=1)
    parser.add_argument("--lots", type=float, default=0.01)
    parser.add_argument("--symbols", type=_parse_symbols, default=DEFAULT_SYMBOLS)
    parser.add_argument("--side", choices=["BUY", "SELL", "ALTERNATE"], default="ALTERNATE")
    parser.add_argument("--stop-pct", type=float, default=None)
    parser.add_argument("--profit-multiple", type=float, default=2.0)
    parser.add_argument("--limit-order", action="store_true")
    parser.add_argument("--spot-wait", type=float, default=3.0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--report", default=None)
    parser.add_argument("--allow-live", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.auth_url:
        client_id = _env("CTRADER_CLIENT_ID")
        if not client_id:
            print("Set CTRADER_CLIENT_ID before requesting an auth URL.")
            return 2
        print(_auth_url(client_id, args.redirect_uri))
        return 0
    if args.auth_code:
        client_id = _env("CTRADER_CLIENT_ID")
        client_secret = _env("CTRADER_CLIENT_SECRET")
        if not client_id or not client_secret:
            print("Set CTRADER_CLIENT_ID and CTRADER_CLIENT_SECRET first.")
            return 2
        return _exchange_auth_code(
            client_id,
            client_secret,
            args.redirect_uri,
            args.auth_code,
            _resolve_token_path(args.token_out),
        )

    creds = _credentials(args)
    refresh_error = _refresh_access_token(
        creds, _resolve_token_path(args.token_file)
    )
    if refresh_error:
        if creds.access_token:
            print(f"Token refresh failed; using existing access token ({refresh_error})")
        else:
            print(f"Token refresh failed and no access token is available: {refresh_error}")
            return 2
    spike = CtraderSpike(args, creds)
    return spike.run()


if __name__ == "__main__":
    raise SystemExit(main())
