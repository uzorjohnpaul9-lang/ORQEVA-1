from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import broker_spike_capital as capital
import broker_spike_ctrader as ctrader


class FakeCapitalResponse:
    def __init__(self, status_code: int, body: dict, headers: dict | None = None) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self.text = json.dumps(body)

    def json(self) -> dict:
        return self._body


class FakeCapitalClient:
    def __init__(self, *, missing_stops: bool = False) -> None:
        self.session_info = {"accountId": "A1", "isDemo": True}
        self.cst = "cst"
        self.security_token = "token"
        self.missing_stops = missing_stops
        self.positions: dict[str, dict] = {}
        self.pending: dict[str, str] = {}
        self.sequence = 0
        self.login_calls = 0
        self.closed_refs: dict[str, str] = {}

    def login(self) -> None:
        self.login_calls += 1

    def json(self, method: str, path: str, **kwargs) -> dict:
        return self.request(method, path, **kwargs).json()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        allow_404: bool = False,
        timeout: int = 30,
    ) -> FakeCapitalResponse:
        method = method.upper()
        if path == "/api/v1/accounts":
            return FakeCapitalResponse(
                200,
                {
                    "accounts": [
                        {
                            "accountId": "A1",
                            "balance": {
                                "balance": 10000,
                                "profitLoss": 5,
                                "available": 9000,
                            },
                        }
                    ]
                },
            )
        if path == "/api/v1/markets/EURUSD":
            return FakeCapitalResponse(
                200,
                {
                    "instrument": {
                        "epic": "EURUSD",
                        "name": "EUR/USD",
                        "type": "CURRENCIES",
                        "currency": "USD",
                    },
                    "dealingRules": {
                        "minDealSize": {"value": 0.01},
                        "minSizeIncrement": {"value": 0.01},
                    },
                    "snapshot": {
                        "bid": 1.08,
                        "offer": 1.0802,
                        "decimalPlacesFactor": 5,
                        "marketStatus": "TRADEABLE",
                    },
                },
            )
        if method == "POST" and path == "/api/v1/positions":
            self.sequence += 1
            deal_id = f"P{self.sequence}"
            reference = f"D{self.sequence}"
            self.pending[reference] = deal_id
            self.positions[deal_id] = {
                "dealId": deal_id,
                "stopLevel": None if self.missing_stops else json_body["stopLevel"],
                "profitLevel": None if self.missing_stops else json_body["profitLevel"],
            }
            return FakeCapitalResponse(200, {"dealReference": reference})
        if method == "GET" and path.startswith("/api/v1/confirms/"):
            reference = path.rsplit("/", 1)[-1]
            if reference in self.pending:
                return FakeCapitalResponse(
                    200,
                    {
                        "dealStatus": "ACCEPTED",
                        "dealId": self.pending[reference],
                        "level": 1.0802,
                    },
                )
            if reference in self.closed_refs:
                return FakeCapitalResponse(
                    200,
                    {"dealStatus": "ACCEPTED", "dealId": self.closed_refs[reference]},
                )
        if method == "GET" and path.startswith("/api/v1/positions/"):
            deal_id = path.rsplit("/", 1)[-1]
            if deal_id in self.positions:
                return FakeCapitalResponse(200, {"position": self.positions[deal_id]})
            if allow_404:
                return FakeCapitalResponse(404, {"errorCode": "not-found"})
        if method == "PUT" and path.startswith("/api/v1/positions/"):
            deal_id = path.rsplit("/", 1)[-1]
            if deal_id not in self.positions:
                return FakeCapitalResponse(404, {"errorCode": "not-found"})
            self.positions[deal_id]["stopLevel"] = json_body["stopLevel"]
            self.positions[deal_id]["profitLevel"] = json_body["profitLevel"]
            return FakeCapitalResponse(200, {})
        if method == "DELETE" and path.startswith("/api/v1/positions/"):
            deal_id = path.rsplit("/", 1)[-1]
            self.positions.pop(deal_id, None)
            reference = f"C{deal_id}"
            self.closed_refs[reference] = deal_id
            return FakeCapitalResponse(200, {"dealReference": reference})
        raise AssertionError(f"unexpected Capital.com request: {method} {path}")


class CapitalSpikeTests(unittest.TestCase):
    def _credentials(self) -> capital.Credentials:
        return capital.Credentials(
            env="demo",
            api_key="key",
            identifier="user@example.com",
            password="password",
            base_url="http://capital.invalid",
            account_id="A1",
        )

    def _run(self, *, missing_stops: bool = False, round_trips: int = 2) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "capital.json"
            args = capital.build_parser().parse_args(
                [
                    "--execute",
                    "--round-trips",
                    str(round_trips),
                    "--symbols",
                    "EURUSD",
                    "--report",
                    str(report),
                ]
            )
            spike = capital.CapitalSpike(args, self._credentials())
            spike.client = FakeCapitalClient(missing_stops=missing_stops)
            with contextlib.redirect_stdout(io.StringIO()):
                code = spike.run()
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            return payload

    def test_market_detail_without_top_level_epic(self) -> None:
        payload = self._run()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["symbols"][0]["epic"], "EURUSD")
        self.assertEqual(len(payload["orders"]), 2)
        for order in payload["orders"]:
            self.assertTrue(order["ok"])
            self.assertTrue(order["closed"])
            self.assertTrue(order["sl_tp_visible"])

    def test_missing_stops_are_repaired(self) -> None:
        payload = self._run(missing_stops=True, round_trips=1)
        order = payload["orders"][0]
        self.assertTrue(order["ok"])
        self.assertTrue(order["sl_tp_visible"])
        self.assertTrue(order["sl_tp_visible_after_repair"])
        self.assertIn("stop_repair", order)

    def test_market_lookup_does_not_use_first_search_result(self) -> None:
        class WrongSearchClient(FakeCapitalClient):
            def request(self, method, path, **kwargs):
                if path == "/api/v1/markets/EURUSD":
                    return FakeCapitalResponse(404, {"errorCode": "not-found"})
                if path.startswith("/api/v1/markets?searchTerm="):
                    return FakeCapitalResponse(
                        200,
                        {
                            "markets": [
                                {"epic": "GBPEUR", "instrumentName": "GBP/EUR"}
                            ]
                        },
                    )
                return super().request(method, path, **kwargs)

        args = capital.build_parser().parse_args(["--symbols", "EURUSD"])
        spike = capital.CapitalSpike(args, self._credentials())
        spike.client = WrongSearchClient()
        with self.assertRaises(RuntimeError):
            spike._market("EURUSD")


class CtradeFakeResponse:
    pass


class CtradeDeferred:
    def __init__(self, result) -> None:
        self.result = result

    def addCallbacks(self, callback, errback):
        callback(self.result)
        return self


class CtradeReactor:
    def __init__(self) -> None:
        self.running = True

    def callLater(self, delay, fn, *args, **kwargs):
        if delay <= 5:
            fn(*args, **kwargs)
        return CtradeFakeResponse()

    def stop(self) -> None:
        self.running = False


class CtradeFakeClient:
    def __init__(self, state: dict, limit_mode: str) -> None:
        self.state = state
        self.limit_mode = limit_mode
        self.running = False

    def send(self, request, **kwargs):
        from ctrader_open_api.messages import OpenApiCommonMessages_pb2 as CM
        from ctrader_open_api.messages import OpenApiMessages_pb2 as OA
        from ctrader_open_api.messages import OpenApiModelMessages_pb2 as OAM

        def raw(inner):
            message = CM.ProtoMessage()
            message.payloadType = inner.payloadType
            message.payload = inner.SerializeToString()
            return message

        def event(execution_type, order_status, *, position_status=None, with_position=True):
            response = OA.ProtoOAExecutionEvent()
            response.ctidTraderAccountId = 123
            response.executionType = execution_type
            if with_position:
                position = response.position
                position.positionId = 777
                position.positionStatus = (
                    position_status
                    if position_status is not None
                    else OAM.ProtoOAPositionStatus.POSITION_STATUS_OPEN
                )
                position.swap = 0
                position.price = self.state.get("price", 1.08)
                trade = position.tradeData
                trade.symbolId = 1
                trade.volume = self.state.get("volume", 100000)
                trade.tradeSide = OAM.ProtoOATradeSide.BUY
                if self.state["stop"]:
                    position.stopLoss = self.state["stop"]
                if self.state["tp"]:
                    position.takeProfit = self.state["tp"]
            order = response.order
            order.orderId = 555
            order.orderType = OAM.ProtoOAOrderType.MARKET
            order.orderStatus = order_status
            trade = order.tradeData
            trade.symbolId = 1
            trade.volume = self.state.get("volume", 100000)
            trade.tradeSide = OAM.ProtoOATradeSide.BUY
            return response

        name = request.DESCRIPTOR.name
        if name == "ProtoOAApplicationAuthReq":
            return CtradeDeferred(raw(OA.ProtoOAApplicationAuthRes()))
        if name == "ProtoOAGetAccountListByAccessTokenReq":
            response = OA.ProtoOAGetAccountListByAccessTokenRes()
            response.accessToken = "access"
            response.permissionScope = 1
            account = response.ctidTraderAccount.add()
            account.ctidTraderAccountId = 123
            account.isLive = False
            account.traderLogin = 456
            return CtradeDeferred(raw(response))
        if name == "ProtoOAAccountAuthReq":
            response = OA.ProtoOAAccountAuthRes()
            response.ctidTraderAccountId = 123
            return CtradeDeferred(raw(response))
        if name == "ProtoOATraderReq":
            response = OA.ProtoOATraderRes()
            response.ctidTraderAccountId = 123
            trader = response.trader
            trader.ctidTraderAccountId = 123
            trader.balance = 1000000
            trader.moneyDigits = 2
            trader.depositAssetId = 1
            trader.brokerName = "Pepperstone"
            return CtradeDeferred(raw(response))
        if name == "ProtoOASymbolsListReq":
            response = OA.ProtoOASymbolsListRes()
            response.ctidTraderAccountId = 123
            symbol = response.symbol.add()
            symbol.symbolId = 1
            symbol.symbolName = "EURUSD"
            symbol.enabled = True
            return CtradeDeferred(raw(response))
        if name == "ProtoOASymbolByIdReq":
            response = OA.ProtoOASymbolByIdRes()
            response.ctidTraderAccountId = 123
            symbol = response.symbol.add()
            symbol.symbolId = 1
            symbol.digits = 5
            symbol.pipPosition = 4
            symbol.minVolume = 100000
            symbol.stepVolume = 1000
            symbol.lotSize = 10000000
            symbol.maxVolume = 100000000
            return CtradeDeferred(raw(response))
        if name == "ProtoOASubscribeSpotsReq":
            response = OA.ProtoOASubscribeSpotsRes()
            response.ctidTraderAccountId = 123
            return CtradeDeferred(raw(response))
        if name == "ProtoOANewOrderReq":
            if request.orderType == OAM.ProtoOAOrderType.LIMIT:
                self.state["price"] = float(request.limitPrice)
                self.state["stop"] = 0.0
                self.state["tp"] = 0.0
                self.state["closed"] = False
                if self.limit_mode == "filled":
                    return CtradeDeferred(
                        raw(
                            event(
                                OAM.ProtoOAExecutionType.ORDER_FILLED,
                                OAM.ProtoOAOrderStatus.ORDER_STATUS_FILLED,
                            )
                        )
                    )
                return CtradeDeferred(
                    raw(
                        event(
                            OAM.ProtoOAExecutionType.ORDER_ACCEPTED,
                            OAM.ProtoOAOrderStatus.ORDER_STATUS_ACCEPTED,
                            with_position=False,
                        )
                    )
                )
            self.state["closed"] = False
            self.state["stop"] = 0.0
            self.state["tp"] = 0.0
            return CtradeDeferred(
                raw(
                    event(
                        OAM.ProtoOAExecutionType.ORDER_FILLED,
                        OAM.ProtoOAOrderStatus.ORDER_STATUS_FILLED,
                    )
                )
            )
        if name == "ProtoOAAmendPositionSLTPReq":
            self.state["stop"] = float(request.stopLoss)
            self.state["tp"] = float(request.takeProfit)
            return CtradeDeferred(
                raw(
                    event(
                        OAM.ProtoOAExecutionType.ORDER_REPLACED,
                        OAM.ProtoOAOrderStatus.ORDER_STATUS_FILLED,
                    )
                )
            )
        if name == "ProtoOAClosePositionReq":
            self.state["closed"] = True
            return CtradeDeferred(
                raw(
                    event(
                        OAM.ProtoOAExecutionType.ORDER_FILLED,
                        OAM.ProtoOAOrderStatus.ORDER_STATUS_FILLED,
                        position_status=OAM.ProtoOAPositionStatus.POSITION_STATUS_CLOSED,
                    )
                )
            )
        if name == "ProtoOACancelOrderReq":
            return CtradeDeferred(
                raw(
                    event(
                        OAM.ProtoOAExecutionType.ORDER_CANCELLED,
                        OAM.ProtoOAOrderStatus.ORDER_STATUS_CANCELLED,
                        with_position=False,
                    )
                )
            )
        if name == "ProtoOAReconcileReq":
            response = OA.ProtoOAReconcileRes()
            response.ctidTraderAccountId = 123
            if not self.state["closed"]:
                position = response.position.add()
                position.positionId = 777
                position.positionStatus = OAM.ProtoOAPositionStatus.POSITION_STATUS_OPEN
                position.swap = 0
                position.price = self.state.get("price", 1.08)
                trade = position.tradeData
                trade.symbolId = 1
                trade.volume = self.state.get("volume", 100000)
                trade.tradeSide = OAM.ProtoOATradeSide.BUY
                if self.state["stop"]:
                    position.stopLoss = self.state["stop"]
                if self.state["tp"]:
                    position.takeProfit = self.state["tp"]
            return CtradeDeferred(raw(response))
        raise AssertionError(f"unexpected cTrader request: {name}")


class CtradeSpikeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            import ctrader_open_api  # noqa: F401
        except ImportError as exc:
            raise unittest.SkipTest(f"cTrader SDK not installed: {exc}")

    def _run(self, limit_mode: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "ctrader.json"
            args = ctrader.build_parser().parse_args(
                [
                    "--execute",
                    "--round-trips",
                    "1",
                    "--limit-order",
                    "--symbols",
                    "EURUSD",
                    "--spot-wait",
                    "0",
                    "--report",
                    str(report),
                ]
            )
            credentials = ctrader.Credentials(
                env="demo",
                client_id="client",
                client_secret="secret",
                access_token="access",
                refresh_token="",
                account_id=123,
                redirect_uri="http://localhost:8080/callback",
            )
            spike = ctrader.CtraderSpike(args, credentials)
            spike._load_modules()
            state = {"stop": 0.0, "tp": 0.0, "closed": False, "price": 1.08}
            spike._client = CtradeFakeClient(state, limit_mode)
            spike._reactor = CtradeReactor()
            with contextlib.redirect_stdout(io.StringIO()):
                spike._on_connected(spike._client)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(payload["ok"])
            return payload

    def test_market_round_trip_and_limit_cancel(self) -> None:
        payload = self._run("cancel")
        orders = {order["kind"]: order for order in payload["orders"]}
        self.assertTrue(orders["market"]["ok"])
        self.assertTrue(orders["market"]["sl_tp_ok"])
        self.assertTrue(orders["market"]["closed"])
        self.assertTrue(orders["limit"]["ok"])

    def test_limit_fill_is_verified_and_closed(self) -> None:
        payload = self._run("filled")
        orders = {order["kind"]: order for order in payload["orders"]}
        self.assertTrue(orders["market"]["ok"])
        self.assertTrue(orders["limit"]["ok"])
        self.assertTrue(orders["limit"]["sl_tp_ok"])
        self.assertTrue(orders["limit"]["closed"])

    def test_account_id_must_be_integer(self) -> None:
        environment = {
            "CTRADER_ENV": "demo",
            "CTRADER_CLIENT_ID": "client",
            "CTRADER_CLIENT_SECRET": "secret",
            "CTRADER_ACCESS_TOKEN": "access",
            "CTRADER_ACCOUNT_ID": "not-an-int",
        }
        with tempfile.TemporaryDirectory() as tmp:
            args = ctrader.build_parser().parse_args(
                ["--token-file", str(Path(tmp) / "tokens.json")]
            )
            with patch.dict(os.environ, environment, clear=False):
                with self.assertRaises(SystemExit):
                    ctrader._credentials(args)


if __name__ == "__main__":
    unittest.main()
