"""Exness (MT5 bridge) adapter + bridge helper tests.

The MetaTrader5 package is Windows-only, so every test here runs against the
bridge's pure helpers and a fake terminal - no MT5 install or Windows host.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import bridge.mt5_bridge as bridge
from backend.config import settings
from backend.exchanges import get_adapter, supported
from backend.exchanges.exness_adapter import ExnessAdapter


# --------------------------------------------------------------- registry

def test_exness_is_registered_for_forex_and_metals():
    adapter = get_adapter("exness")
    assert isinstance(adapter, ExnessAdapter)
    assert {"forex", "commodity"} <= set(adapter.markets)
    assert adapter.supports_order_routing and adapter.supports_position_close
    assert "exness" in {a.name for a in supported()}


# ------------------------------------------------------------- credentials

def test_symbol_normalization():
    assert ExnessAdapter.normalize_symbol("eur/usd") == "eurusd"
    assert ExnessAdapter.normalize_symbol("XAU/USD") == "XAUUSD"
    assert ExnessAdapter.normalize_symbol("EURUSD.a") == "EURUSD.a"


def test_split_credentials_accepts_account_and_server():
    assert ExnessAdapter.split_credentials("12345678|Exness-MT5Real8") == (
        "12345678", "Exness-MT5Real8")
    assert ExnessAdapter.split_credentials("12345678", "Exness-MT5Demo") == (
        "12345678", "Exness-MT5Demo")


def test_split_credentials_uses_env_fallback(monkeypatch):
    monkeypatch.setattr(settings, "EXNESS_MT5_SERVER", "Exness-MT5Real1")
    assert ExnessAdapter.split_credentials("12345678") == (
        "12345678", "Exness-MT5Real1")


def test_split_credentials_requires_server(monkeypatch):
    monkeypatch.setattr(settings, "EXNESS_MT5_SERVER", "")
    with pytest.raises(RuntimeError, match="server is required"):
        ExnessAdapter.split_credentials("12345678")


# ------------------------------------------------------------ adapter calls

def test_validate_refuses_real_account_in_paper_mode(monkeypatch):
    monkeypatch.setattr(
        ExnessAdapter, "_post",
        lambda self, path, payload: {
            "ok": True,
            "account": {"login": "12345678", "company": "Exness",
                        "trade_mode": "real", "balance": 100},
        },
    )
    out = get_adapter("exness").validate("12345678|Exness-MT5Real8", "pw", True)
    assert out["ok"] is False and "REAL" in out["detail"]


def test_validate_demo_account_in_paper_mode(monkeypatch):
    monkeypatch.setattr(
        ExnessAdapter, "_post",
        lambda self, path, payload: {
            "ok": True,
            "account": {"login": "12345678", "company": "Exness",
                        "trade_mode": "demo", "balance": 100},
        },
    )
    out = get_adapter("exness").validate("12345678|Exness-MT5Demo", "pw", True)
    assert out["ok"] is True and "demo" in out["detail"]


def test_validate_bridge_failure_is_reported(monkeypatch):
    monkeypatch.setattr(
        ExnessAdapter, "_post",
        lambda self, path, payload: {"ok": False, "detail": "MT5 login failed [10004]"},
    )
    out = get_adapter("exness").validate("12345678|Exness-MT5Real8", "pw", False)
    assert out["ok"] is False and "10004" in out["detail"]


def test_place_order_payload_and_response(monkeypatch):
    captured = {}

    def fake_post(self, path, payload):
        captured["path"], captured["payload"] = path, payload
        return {"ok": True, "broker_order_id": "42", "broker_status": "FILLED",
                "filled_price": 2000.5, "protective": "bracket"}

    monkeypatch.setattr(ExnessAdapter, "_post", fake_post)
    out = get_adapter("exness").place_order(
        "12345678|Exness-MT5Real8", "pw", False,
        symbol="XAU/USD", side="buy", quantity=20,
        order_type="market", limit_price=None,
        stop_loss=1900, take_profit=2100,
    )
    assert out["ok"] and out["broker_order_id"] == "42"
    assert captured["path"] == "/order"
    p = captured["payload"]
    assert p["login"] == "12345678" and p["server"] == "Exness-MT5Real8"
    assert p["symbol"] == "XAUUSD" and p["quantity_units"] == 20
    assert p["stop_loss"] == 1900 and p["take_profit"] == 2100


def test_close_positions_payload(monkeypatch):
    captured = {}

    def fake_post(self, path, payload):
        captured["path"], captured["payload"] = path, payload
        return {"ok": True, "closed_volume_units": 20000.0}

    monkeypatch.setattr(ExnessAdapter, "_post", fake_post)
    out = get_adapter("exness").close_positions(
        "12345678|Exness-MT5Real8", "pw", False,
        symbol="EUR/USD", side="buy", quantity=20000,
    )
    assert out["ok"] is True
    assert captured["path"] == "/close"
    assert captured["payload"]["symbol"] == "EURUSD"
    assert captured["payload"]["side"] == "buy"


def test_bridge_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "EXNESS_BRIDGE_URL", "")
    out = get_adapter("exness").validate("12345678|Exness-MT5Real8", "pw", False)
    assert out["ok"] is False and "EXNESS_BRIDGE_URL" in out["detail"]


def test_health_reports_bridge_and_mt5(monkeypatch):
    monkeypatch.setattr(settings, "EXNESS_BRIDGE_URL", "https://bridge.test")
    monkeypatch.setattr(settings, "EXNESS_BRIDGE_TOKEN", "tok")
    monkeypatch.setattr(
        "backend.exchanges.exness_adapter.requests.get",
        lambda *a, **k: SimpleNamespace(
            status_code=200,
            json=lambda: {"status": "ok", "mt5_available": True},
        ),
    )
    out = get_adapter("exness").health()
    assert out["ok"] is True and out["reachable"] is True
    assert out["mt5_available"] is True


def test_health_reports_unreachable_bridge(monkeypatch):
    monkeypatch.setattr(settings, "EXNESS_BRIDGE_URL", "https://bridge.test")
    monkeypatch.setattr(settings, "EXNESS_BRIDGE_TOKEN", "tok")

    def boom(*a, **k):
        raise ConnectionError("dns name does not exist")

    monkeypatch.setattr("backend.exchanges.exness_adapter.requests.get", boom)
    out = get_adapter("exness").health()
    assert out["ok"] is False and out["reachable"] is False
    assert "dns" in out["detail"]


def test_health_reports_bridge_without_mt5(monkeypatch):
    monkeypatch.setattr(settings, "EXNESS_BRIDGE_URL", "https://bridge.test")
    monkeypatch.setattr(settings, "EXNESS_BRIDGE_TOKEN", "tok")
    monkeypatch.setattr(
        "backend.exchanges.exness_adapter.requests.get",
        lambda *a, **k: SimpleNamespace(
            status_code=200,
            json=lambda: {"status": "ok", "mt5_available": False},
        ),
    )
    out = get_adapter("exness").health()
    assert out["reachable"] is True and out["ok"] is False
    assert out["mt5_available"] is False


# --------------------------------------------------------- bridge helpers

def test_units_to_lots_uses_contract_size_and_step():
    assert bridge.units_to_lots(20000, 100000, 0.01, 100, 0.01) == 0.2
    assert bridge.units_to_lots(20500, 100000, 0.01, 100, 0.01) == 0.2
    assert bridge.units_to_lots(20, 100, 0.01, 100, 0.01) == 0.2


def test_units_to_lots_rejects_below_minimum():
    with pytest.raises(bridge.BridgeError, match="below the broker minimum"):
        bridge.units_to_lots(1000, 100000, 0.1, 100, 0.01)


def test_units_to_lots_clamps_to_maximum():
    assert bridge.units_to_lots(50_000_000, 100000, 0.01, 5, 0.01) == 5


def test_protective_kind():
    assert bridge._protective_kind(1, 2) == "bracket"
    assert bridge._protective_kind(1, None) == "stop_loss"
    assert bridge._protective_kind(None, 2) == "take_profit"
    assert bridge._protective_kind(None, None) == "none"


def _info(**over):
    base = dict(trade_contract_size=100000, volume_min=0.01, volume_max=100,
                volume_step=0.01, digits=5, point=0.00001,
                trade_stops_level=0, filling_mode=2, visible=True)
    base.update(over)
    return SimpleNamespace(**base)


class FakeMT5:
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    TRADE_ACTION_DEAL = 0
    TRADE_ACTION_PENDING = 5
    ORDER_TIME_GTC = 0

    def __init__(self, positions=None, order_result=None):
        self._positions = positions or []
        self._result = order_result
        self.requests: list[dict] = []

    def symbol_info(self, name):
        return _info()

    def symbol_select(self, name, enable):
        return True

    def symbols_get(self, pattern):
        return []

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(bid=1.0999, ask=1.1000)

    def positions_get(self, symbol=None):
        return self._positions

    def order_send(self, request):
        self.requests.append(dict(request))
        return self._result


def test_bridge_send_order_maps_units_to_lots(monkeypatch):
    fake = FakeMT5(order_result=SimpleNamespace(
        retcode=10009, order=777, deal=778, price=1.1, comment="done"))
    monkeypatch.setattr(bridge, "mt5", fake)

    body = bridge.OrderBody(login="12345678", password="pw",
                            server="Exness-MT5Real8", symbol="EURUSD",
                            side="buy", quantity_units=20000)
    out = bridge._send_order(fake, body)

    assert out["ok"] is True and out["broker_order_id"] == "777"
    assert out["protective"] == "none"
    request = fake.requests[0]
    assert request["volume"] == 0.2 and request["symbol"] == "EURUSD"
    assert request["type"] == fake.ORDER_TYPE_BUY


def test_bridge_rejects_stop_on_wrong_side(monkeypatch):
    fake = FakeMT5(order_result=SimpleNamespace(
        retcode=10009, order=1, deal=1, price=1.1, comment=""))
    monkeypatch.setattr(bridge, "mt5", fake)
    body = bridge.OrderBody(login="12345678", password="pw",
                            server="Exness-MT5Real8", symbol="EURUSD",
                            side="buy", quantity_units=20000, stop_loss=1.2)
    with pytest.raises(bridge.BridgeError, match="below the entry"):
        bridge._send_order(fake, body)


def test_bridge_closes_matching_magic_position(monkeypatch):
    position = SimpleNamespace(ticket=555, type=0, magic=20261021,
                               volume=0.2, time=1)
    fake = FakeMT5(positions=[position],
                   order_result=SimpleNamespace(
                       retcode=10009, order=556, deal=556, price=1.0999, comment=""))
    monkeypatch.setattr(bridge, "mt5", fake)

    body = bridge.CloseBody(login="12345678", password="pw",
                            server="Exness-MT5Real8", symbol="EURUSD",
                            side="buy", quantity_units=20000)
    out = bridge._close_positions(fake, body)

    assert out["ok"] is True and out["closed_volume_units"] == pytest.approx(20000)
    assert out["close_price"] == pytest.approx(1.0999)
    assert out["filled_price"] == pytest.approx(1.0999)
    request = fake.requests[0]
    assert request["position"] == 555
    assert request["type"] == fake.ORDER_TYPE_SELL
    assert request["volume"] == 0.2


def test_bridge_refuses_to_close_unmanaged_position(monkeypatch):
    position = SimpleNamespace(ticket=555, type=0, magic=999,
                               volume=0.2, time=1)
    fake = FakeMT5(positions=[position])
    monkeypatch.setattr(bridge, "mt5", fake)
    body = bridge.CloseBody(login="12345678", password="pw",
                            server="Exness-MT5Real8", symbol="EURUSD",
                            side="buy", quantity_units=20000)
    with pytest.raises(bridge.BridgeError, match="no open ORQEVA position"):
        bridge._close_positions(fake, body)


# --------------------------------------------------------------- bridge auth

def test_bridge_requires_configured_token(monkeypatch):
    monkeypatch.setenv("MT5_BRIDGE_TOKEN", "")
    with pytest.raises(HTTPException) as exc:
        bridge.require_token("anything")
    assert exc.value.status_code == 503


def test_bridge_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("MT5_BRIDGE_TOKEN", "secret")
    with pytest.raises(HTTPException) as exc:
        bridge.require_token("wrong")
    assert exc.value.status_code == 401
    assert bridge.require_token("secret") is None
