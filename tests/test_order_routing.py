"""Phase 17b: real order routing through exchange adapters."""
import pytest

from backend.exchanges import get_adapter
from backend.exchanges.kraken_adapter import KrakenAdapter
from backend.exchanges.oanda_adapter import OandaAdapter
from backend.exchanges.coinbase_adapter import CoinbaseAdapter
from tests.conftest import register_and_login


# ---------- symbol mapping ----------

def test_symbol_mappings():
    assert KrakenAdapter.to_kraken_pair("BTCUSD") == "XBTUSD"
    assert KrakenAdapter.to_kraken_pair("ETHUSDT") == "ETHUSDT"
    assert OandaAdapter.to_oanda_instrument("EURUSD") == "EUR_USD"
    assert OandaAdapter.to_oanda_instrument("XAU_USD") == "XAU_USD"
    assert CoinbaseAdapter.to_product_id("BTCUSDT") == "BTC-USDT"
    assert CoinbaseAdapter.to_product_id("ETHUSD") == "ETH-USD"


# ---------- adapter unit behavior (network mocked) ----------

import base64 as _b64
KRAKEN_SECRET = _b64.b64encode(b"krakensecret").decode()


def test_kraken_place_order_success(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"result": {"txid": ["TX-1"], "descr": {"order": "buy 1.0 XBTUSD"}}}
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResp())
    out = get_adapter("kraken").place_order(
        "k", KRAKEN_SECRET, True, symbol="BTCUSD", side="buy",
        quantity=1.0, order_type="market", limit_price=None)
    assert out["ok"] is True and out["broker_order_id"] == "TX-1"


def test_kraken_place_order_broker_error(monkeypatch):
    class FakeResp:
        status_code = 200
        def json(self):
            return {"error": ["EOrder:Insufficient funds"]}
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResp())
    out = get_adapter("kraken").place_order(
        "k", KRAKEN_SECRET, True, symbol="BTCUSD", side="buy",
        quantity=1.0, order_type="market", limit_price=None)
    assert out["ok"] is False and "Insufficient" in out["detail"]


def test_kraken_limit_requires_price():
    out = get_adapter("kraken").place_order(
        "k", KRAKEN_SECRET, True, symbol="BTCUSD", side="buy",
        quantity=1.0, order_type="limit", limit_price=None)
    assert out["ok"] is False and "limit_price" in out["detail"]


def test_oanda_units_sign(monkeypatch):
    captured = {}

    def fake_get(api_key, is_paper, path):
        if path == "/v3/accounts":
            return {"accounts": [{"id": "ACC-1"}]}
        return {"account": {"balance": "100", "currency": "USD"}}

    class FakeResp:
        status_code = 201
        def json(self):
            return {"orderCreateTransaction": {"id": "77"},
                    "orderFillTransaction": {"id": "78", "price": "1.0855"}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["body"] = json
        return FakeResp()

    monkeypatch.setattr(OandaAdapter, "_get", staticmethod(fake_get))
    monkeypatch.setattr("requests.post", fake_post)
    ad = get_adapter("oanda")
    out = ad.place_order("tok", "", True, symbol="EURUSD", side="sell",
                         quantity=2.5, order_type="market", limit_price=None)
    assert out["ok"] and out["broker_order_id"] == "77" and out["filled_price"] == 1.0855
    units = int(captured["body"]["order"]["units"])
    instrument = captured["body"]["order"]["instrument"]
    assert units < 0 and abs(units) == 250 and instrument == "EUR_USD"


def test_coinbase_payload_shape(monkeypatch):
    captured = {}

    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    pem_key = ec.generate_private_key(ec.SECP256R1())
    pem = pem_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    class FakeResp:
        status_code = 200
        def json(self):
            return {"success": True,
                    "success_response": {"order_id": "cb-9", "order_status": "PENDING_OPEN"}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"], captured["json"] = url, json
        return FakeResp()

    monkeypatch.setattr("requests.post", fake_post)
    out = get_adapter("coinbase").place_order(
        "org/key", pem, False, symbol="BTCUSDT", side="buy",
        quantity=0.01, order_type="market", limit_price=None)
    assert out["ok"] and out["broker_order_id"] == "cb-9"
    cfg = captured["json"]["order_configuration"]["market_market"]
    assert cfg["base_size"].startswith("0.01")
    assert captured["json"]["product_id"] == "BTC-USDT"
    assert captured["json"]["side"] == "BUY"


def test_base_adapter_without_routing(monkeypatch):
    from backend.exchanges.base import BaseAdapter

    class Dummy(BaseAdapter):
        name, display_name, markets = "dummy", "Dummy", ["crypto"]
        supports_order_routing = False

        def _validate(self, api_key, api_secret, is_paper):
            return {}

        def _account(self, api_key, api_secret, is_paper):
            return {}

    out = Dummy().place_order("k", "s", True, symbol="BTCUSD", side="buy",
                              quantity=1.0, order_type="market", limit_price=None)
    assert out["ok"] is False and "not supported" in out["detail"]


# ---------- API-level routing ----------

@pytest.fixture
async def kraken_conn(client):
    """Active kraken connection for the current user; returns (headers, email)."""
    H, email = await register_and_login(client)

    from security.security_manager import SecurityManager
    from backend.db.models import EXCHANGE_CONNECTIONS, USERS, gen_uuid
    from backend.db.supabase import SupabaseDB, get_service_client, now_iso

    sec = SecurityManager()
    db = SupabaseDB(await get_service_client())
    u = await db.fetch_one(USERS, {"email": email})
    conn_id = gen_uuid()
    await db.insert(EXCHANGE_CONNECTIONS, {
        "id": conn_id,
        "user_id": u["id"],
        "exchange": "kraken",
        "api_key_encrypted": sec.encrypt_data("KRAKENKEY123456"),
        "api_secret_encrypted": sec.encrypt_data("krakensecret"),
        "is_paper": True,
        "is_active": True,
        "connected_at": now_iso(),
        "last_checked": now_iso(),
    })
    return H, conn_id


async def _open_live(client, H, symbol="BTCUSD", **over):
    payload = {"symbol": symbol, "market": "crypto", "side": "buy",
               "quantity": 0.01, "route": "live"}
    payload.update(over)
    return await client.post("/api/trading/orders", json=payload, headers=H)


@pytest.fixture
def fixed_live_price(monkeypatch):
    """Live route resolves price from a feed (entry_price is rejected there);
    pin it so tests stay offline and deterministic."""
    async def _price(market, symbol):
        return 50000.0

    monkeypatch.setattr("backend.api.trading.live_price", _price)


async def test_live_route_without_connection_403(client):
    H, _ = await register_and_login(client)
    r = await _open_live(client, H)
    assert r.status_code == 403 and "no validated live connection" in r.json()["detail"]


async def test_live_route_happy_path(client, kraken_conn, fixed_live_price, monkeypatch):
    H, _conn_id = kraken_conn

    monkeypatch.setattr(
        KrakenAdapter, "_place_order",
        lambda self, k, s, p, *, symbol, side, quantity, order_type, limit_price, **kw:
        {"ok": True, "broker_order_id": f"TX-{side}", "broker_status": "submitted",
         "filled_price": None},
    )
    r = await _open_live(client, H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["venue"] == "kraken" and body["broker_order_id"] == "TX-buy"
    trade_id = body["trade_id"]

    # close routes opposite side through the same broker
    rc = await client.post(f"/api/trading/close/{trade_id}",
                           json={"exit_price": 51000.0}, headers=H)
    assert rc.status_code == 200, rc.text


async def test_live_route_broker_rejection_leaves_no_trade(client, kraken_conn, fixed_live_price, monkeypatch):
    H, _conn_id = kraken_conn
    monkeypatch.setattr(
        KrakenAdapter, "_place_order",
        lambda self, k, s, p, *, symbol, side, quantity, order_type, limit_price, **kw:
        {"ok": False, "detail": "EOrder:Insufficient funds"},
    )
    r = await _open_live(client, H)
    assert r.status_code == 502 and "Insufficient funds" in r.json()["detail"]

    rh = await client.get("/api/trading/history?outcome=open", headers=H)
    assert all(t["symbol"] != "BTCUSD" or t.get("exchange") != "kraken"
               for t in rh.json().get("trades", []))


async def test_close_live_without_connection_blocked(client, kraken_conn, fixed_live_price, monkeypatch):
    """A live-routed open position must NOT be silently paper-closed."""
    H, conn_id = kraken_conn
    monkeypatch.setattr(
        KrakenAdapter, "_place_order",
        lambda self, k, s, p, *, symbol, side, quantity, order_type, limit_price, **kw:
        {"ok": True, "broker_order_id": "TX-x", "broker_status": "ok", "filled_price": None},
    )
    r = await _open_live(client, H)
    assert r.status_code == 200, r.text
    trade_id = r.json()["trade_id"]

    # disconnect the broker behind the dashboard's back
    from backend.db.models import EXCHANGE_CONNECTIONS
    from backend.db.supabase import SupabaseDB, get_service_client

    db = SupabaseDB(await get_service_client())
    await db.update(EXCHANGE_CONNECTIONS, {"is_active": False}, {"id": conn_id})

    rc = await client.post(f"/api/trading/close/{trade_id}", headers=H)  # no body -> live price path
    assert rc.status_code == 502 and "close manually at broker" in rc.json()["detail"]


async def test_paper_path_regression(client):
    H, _ = await register_and_login(client)
    r = await client.post("/api/trading/orders", json={
        "symbol": "AAPL", "market": "stock", "side": "buy",
        "quantity": 2, "entry_price": 100.0,
    }, headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["venue"] == "paper" and body["route"] == "paper" and body.get("broker_order_id") is None

    rc = await client.post(f"/api/trading/close/{body['trade_id']}",
                           json={"exit_price": 101.0}, headers=H)
    assert rc.status_code == 200 and float(rc.json()["pnl"]) == 2.0
