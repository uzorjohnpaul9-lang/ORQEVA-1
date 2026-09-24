"""Hardening sprint stage 4: broker-side SL/TP protective orders."""
import base64 as _b64

from backend.exchanges.alpaca_adapter import AlpacaAdapter
from backend.exchanges.kraken_adapter import KrakenAdapter
from backend.exchanges.oanda_adapter import OandaAdapter
from backend.exchanges.coinbase_adapter import CoinbaseAdapter


def test_alpaca_bracket_request_built(monkeypatch):
    """Bracket params must reach submit_order when SL+TP given."""
    captured = {}

    class FakeResp:
        id = "alp-1"
        status = "pending_new"
        filled_avg_price = None

    def fake_submit(order_req):
        captured["req"] = order_req
        return FakeResp()

    class FakeClient:
        def __init__(self, *a, **k): ...
        def submit_order(self, r):
            return fake_submit(r)

    monkeypatch.setattr(AlpacaAdapter, "_client", lambda self, k, s, p: FakeClient())
    out = AlpacaAdapter().place_order(
        "k", "s", True, symbol="AAPL", side="buy", quantity=1,
        order_type="market", limit_price=None, stop_loss=95.0, take_profit=110.0)
    assert out["ok"] and out["protective"] == "bracket"
    req = captured["req"]
    assert float(req.take_profit.limit_price) == 110.0
    assert float(req.stop_loss.stop_price) == 95.0


def test_kraken_stop_only_uses_close_params(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200
        def json(self):
            return {"result": {"txid": ["K1"]}}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["params"] = data
        return FakeResp()

    import base64 as _b64
    secret = _b64.b64encode(b"krakensecret").decode()
    monkeypatch.setattr("requests.post", fake_post)
    out = KrakenAdapter().place_order(
        "k", secret, True, symbol="BTCUSD", side="buy", quantity=0.5,
        order_type="market", limit_price=None, stop_loss=40000.0)
    assert out["ok"] and out["protective"] == "stop-loss"
    p = captured["params"]
    assert p["close[ordertype]"] == "stop-loss"
    assert p["close[price]"].startswith("40000")


def test_oanda_sl_tp_on_fill(monkeypatch):
    captured = {}

    def fake_get(api_key, is_paper, path):
        if path == "/v3/accounts":
            return {"accounts": [{"id": "A1"}]}
        return {"account": {}}

    class FakeResp:
        status_code = 201
        def json(self):
            return {"orderCreateTransaction": {"id": "9"}}

    monkeypatch.setattr(OandaAdapter, "_get", staticmethod(fake_get))
    monkeypatch.setattr("requests.post",
                        lambda url, headers=None, json=None, timeout=None:
                        (captured.update(body=json), FakeResp())[1])
    out = OandaAdapter().place_order(
        "tok", "", True, symbol="EURUSD", side="buy", quantity=1.0,
        order_type="market", limit_price=None, stop_loss=1.07, take_profit=1.12)
    o = captured["body"]["order"]
    assert out["protective"] == "stop-loss+take-profit"
    assert float(o["stopLossOnFill"]["price"]) == 1.07
    assert float(o["takeProfitOnFill"]["price"]) == 1.12


def test_coinbase_bracket_config(monkeypatch):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()

    calls = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"success": True, "success_response": {"order_id": "cb-b"}}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return FakeResp()

    import requests as _rq
    orig_post = _rq.post
    _rq.post = fake_post
    try:
        out = CoinbaseAdapter().place_order(
            "org/key", pem, False, symbol="BTCUSDT", side="buy", quantity=0.01,
            order_type="market", limit_price=None, stop_loss=45000.0, take_profit=60000.0)
    finally:
        _rq.post = orig_post

    assert out["ok"] and out["protective"] == "bracket"
    cfg = list(calls[-1]["order_configuration"].values())[0]
    assert any("45000" in str(v) for v in cfg.values())
    assert any("60000" in str(v) for v in cfg.values())


async def test_paper_route_accepts_sl_tp(client):
    """Paper route accepts SL/TP fields without erroring; nothing is routed to a broker."""
    from tests.conftest import register_and_login

    H, _ = await register_and_login(client)
    r = await client.post("/api/trading/orders", headers=H, json={
        "symbol": "BTCUSDT", "market": "crypto", "side": "buy",
        "quantity": 0.01, "route": "paper", "entry_price": 45000.0,
        "stop_loss": 40000.0, "take_profit": 50000.0,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "filled" and body["route"] == "paper"
    assert body["venue"] == "paper"


async def test_paper_trade_does_not_persist_sl_tp(client):
    """SL/TP are broker-side only for live venues — paper trades stay clean."""
    from sqlalchemy import select
    from backend.db.database import async_session
    from backend.db.models import Trade
    from tests.conftest import register_and_login

    H, _ = await register_and_login(client)
    r = await client.post("/api/trading/orders", headers=H, json={
        "symbol": "ETHUSDT", "market": "crypto", "side": "buy",
        "quantity": 0.5, "route": "paper", "entry_price": 3000.0,
        "stop_loss": 1000.0,
    })
    assert r.status_code == 200
    trade_id = r.json()["trade_id"]
    async with async_session() as db:
        t = (await db.execute(select(Trade).where(Trade.id == trade_id))).scalar_one()
        assert t.stop_loss is None and t.take_profit is None


# --- Coinbase partial-failure handling --------------------------------------

def _ec_pem() -> str:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    return ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()).decode()


def test_coinbase_stop_failure_keeps_entry_result(monkeypatch):
    """Entry fills, sibling stop fails -> ok=True + protective_error, not ok=False."""
    calls = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"success": True, "success_response": {"order_id": "cb-e"}}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json)
        return FakeResp()

    monkeypatch.setattr(CoinbaseAdapter, "_submit_stop",
                        lambda self, *a, **k: (_ for _ in ()).throw(RuntimeError("insufficient balance")))

    import requests as _rq
    orig = _rq.post
    _rq.post = fake_post
    try:
        out = CoinbaseAdapter().place_order(
            "org/key", _ec_pem(), False, symbol="BTCUSDT", side="buy", quantity=0.01,
            order_type="market", limit_price=None, stop_loss=45000.0)
    finally:
        _rq.post = orig

    assert out["ok"] is True
    assert out["protective"] is None
    assert "insufficient balance" in out["protective_error"]
    # exactly one real order POSTed to the broker (entry), stop raised locally
    assert len(calls) == 1


def test_coinbase_entry_failure_never_places_stop(monkeypatch):
    """If the entry is rejected no trigger order may be left behind (no orphans)."""
    stop_called = []

    class FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"success": False,
                    "error_response": {"message": "order rejected"}}

    monkeypatch.setattr(CoinbaseAdapter, "_submit_stop",
                        lambda self, *a, **k: stop_called.append(1))
    monkeypatch.setattr("requests.post", lambda *a, **k: FakeResp())

    out = CoinbaseAdapter().place_order(
        "org/key", _ec_pem(), False, symbol="BTCUSDT", side="buy", quantity=0.01,
        order_type="market", limit_price=None, stop_loss=45000.0)
    assert out["ok"] is False and "order rejected" in out["detail"]
    assert stop_called == []  # stop attempted only after a confirmed entry


async def test_live_route_surfaces_warning_and_notifies(client, monkeypatch):
    """protective_error from an adapter -> 200 + warning in payload + notification."""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from backend.db.database import async_session
    from backend.db.models import ExchangeConnection, Notification, User
    from backend.api.exchanges import security as sec
    from tests.conftest import register_and_login

    H, email = await register_and_login(client)
    async with async_session() as db:
        u = (await db.execute(
            select(User).where(User.email == email))).scalar_one()
        db.add(ExchangeConnection(
            user_id=u.id, exchange="coinbase",
            api_key_encrypted=sec.encrypt_data("org/key"),
            api_secret_encrypted=sec.encrypt_data(_ec_pem()),
            is_paper=True, is_active=True,
            connected_at=datetime.now(timezone.utc),
        ))
        await db.commit()

    monkeypatch.setattr(
        CoinbaseAdapter, "_place_order",
        lambda self, k, s, p, *, symbol, side, quantity, order_type, limit_price, **kw:
        {"ok": True, "broker_order_id": "CB-1", "broker_status": "filled",
         "filled_price": None, "protective": None,
         "protective_error": "stop rejected: invalid price"},
    )

    r = await client.post("/api/trading/orders", headers=H, json={
        "symbol": "BTCUSDT", "market": "crypto", "side": "buy",
        "quantity": 0.01, "route": "live", "entry_price": 50000.0,
        "stop_loss": 45000.0,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["venue"] == "coinbase"
    assert "stop-loss could not be placed" in body.get("warning", "")

    async with async_session() as db:
        u = (await db.execute(select(User).where(User.email == email))).scalar_one()
        notes = (await db.execute(
            select(Notification).where(Notification.user_id == u.id))).scalars().all()
    assert any(n.type == "trade_warning" for n in notes)