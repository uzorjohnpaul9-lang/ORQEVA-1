from backend.exchanges import supported
from backend.exchanges.bybit_adapter import BybitAdapter, bybit_signature_for_tests
from backend.services.order_executor import is_demo_ledger


def test_bybit_is_registered():
    assert "bybit" in {adapter.name for adapter in supported()}


def test_bybit_signature_is_deterministic_and_payload_sensitive():
    first = bybit_signature_for_tests("secret", "1700000000000", "key", "20000", '{"a":1}')
    same = bybit_signature_for_tests("secret", "1700000000000", "key", "20000", '{"a":1}')
    other = bybit_signature_for_tests("secret", "1700000000000", "key", "20000", '{"a":2}')
    assert first == same
    assert first != other
    assert len(first) == 64


def test_bybit_demo_and_live_hosts(monkeypatch):
    monkeypatch.delenv("BYBIT_DEMO_BASE_URL", raising=False)
    monkeypatch.delenv("BYBIT_LIVE_BASE_URL", raising=False)
    adapter = BybitAdapter()
    assert adapter._base(True) == "https://api-demo.bybit.com"
    assert adapter._base(False) == "https://api.bybit.com"


def test_bybit_symbol_mapping():
    assert BybitAdapter.to_symbol("BTC/USD") == "BTCUSDT"
    assert BybitAdapter.to_symbol("ETH-USDT") == "ETHUSDT"
    assert BybitAdapter.to_symbol("SOL/USDC") == "SOLUSDC"
    assert BybitAdapter.to_symbol("PEPE/USD") == "1000PEPEUSDT"
    assert BybitAdapter.to_symbol("SHIB/USD") == "SHIB1000USDT"
    assert BybitAdapter._scale("PEPE/USD") == 1000.0
    assert BybitAdapter._scale("BTC/USD") == 1.0


def test_bybit_quantity_and_price_formatting():
    assert BybitAdapter._format_qty(BybitAdapter._round_qty(0.001234, "0.001"), "0.001") == "0.001"
    assert BybitAdapter._format_qty(BybitAdapter._round_qty(1.239, "0.01"), "0.01") == "1.23"
    assert BybitAdapter._format_price(95.0, "0.10") == "95.00"
    assert BybitAdapter._format_price(0.123456, "0.0001") == "0.1235"


def test_demo_ledger_includes_demo_broker_connections():
    assert is_demo_ledger("paper", None)
    assert is_demo_ledger("live", {"is_paper": True})
    assert not is_demo_ledger("live", {"is_paper": False})
    assert not is_demo_ledger("live", None)


def test_bybit_market_order_attaches_bracket_protection(monkeypatch):
    adapter = BybitAdapter()
    captured = {}

    def fake_request(api_key, api_secret, is_paper, method, path, params=None,
                     signed=True):
        if path == "/v5/market/instruments-info":
            return {"list": [{
                "symbol": "BTCUSDT",
                "status": "Trading",
                "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001",
                                  "maxOrderQty": "100"},
                "priceFilter": {"tickSize": "0.10"},
            }]}
        if path == "/v5/order/create":
            captured["payload"] = params
            captured["is_paper"] = is_paper
            return {"orderId": "order-1"}
        if path == "/v5/order/realtime":
            return {"list": [{"avgPrice": "100.5", "orderStatus": "Filled"}]}
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_request", fake_request)
    result = adapter._place_order(
        "key", "secret", True, symbol="BTC/USD", side="buy", quantity=0.001234,
        order_type="market", limit_price=None, stop_loss=95.0, take_profit=110.0,
    )

    assert result["ok"] is True
    assert result["protective"] == "bracket"
    assert result["filled_price"] == 100.5
    assert captured["is_paper"] is True
    payload = captured["payload"]
    assert payload["category"] == "linear"
    assert payload["symbol"] == "BTCUSDT"
    assert payload["side"] == "Buy"
    assert payload["orderType"] == "Market"
    assert payload["qty"] == "0.001"
    assert payload["stopLoss"] == "95.00"
    assert payload["takeProfit"] == "110.00"
    assert payload["tpslMode"] == "Full"
    assert payload["positionIdx"] == 0


def test_bybit_scaled_memecoin_converts_qty_and_prices(monkeypatch):
    adapter = BybitAdapter()
    captured = {}

    def fake_request(api_key, api_secret, is_paper, method, path, params=None,
                     signed=True):
        if path == "/v5/market/instruments-info":
            return {"list": [{
                "symbol": "1000PEPEUSDT",
                "status": "Trading",
                "lotSizeFilter": {"qtyStep": "100", "minOrderQty": "100",
                                  "maxOrderQty": "1000000"},
                "priceFilter": {"tickSize": "0.0000010"},
            }]}
        if path == "/v5/order/create":
            captured["payload"] = params
            return {"orderId": "pepe-1"}
        if path == "/v5/order/realtime":
            return {"list": [{"avgPrice": "0.010", "orderStatus": "Filled"}]}
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_request", fake_request)
    result = adapter._place_order(
        "key", "secret", True, symbol="PEPE/USD", side="buy", quantity=1_000_000,
        order_type="market", limit_price=None, stop_loss=0.000009,
        take_profit=0.000012,
    )

    payload = captured["payload"]
    assert payload["symbol"] == "1000PEPEUSDT"
    assert payload["qty"] == "1000"
    assert payload["stopLoss"] == "0.0090000"
    assert payload["takeProfit"] == "0.0120000"
    assert result["filled_price"] == 0.00001


def test_bybit_close_uses_the_open_position_size(monkeypatch):
    adapter = BybitAdapter()
    captured = {}

    def fake_request(api_key, api_secret, is_paper, method, path, params=None,
                     signed=True):
        if path == "/v5/position/list":
            return {"list": [{"side": "Buy", "size": "0.005", "positionIdx": 0}]}
        if path == "/v5/market/instruments-info":
            return {"list": [{
                "symbol": "BTCUSDT",
                "status": "Trading",
                "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001"},
                "priceFilter": {"tickSize": "0.10"},
            }]}
        if path == "/v5/order/create":
            captured["payload"] = params
            return {"orderId": "close-1"}
        if path == "/v5/order/realtime":
            return {"list": [{"avgPrice": "101.0", "orderStatus": "Filled"}]}
        raise AssertionError(path)

    monkeypatch.setattr(adapter, "_request", fake_request)
    result = adapter.close_positions(
        "key", "secret", True, symbol="BTC/USD", side="buy", quantity=0.001,
    )

    assert result["ok"] is True
    payload = captured["payload"]
    assert payload["side"] == "Sell"
    assert payload["qty"] == "0.005"
    assert payload["reduceOnly"] is True
    assert payload["positionIdx"] == 0
