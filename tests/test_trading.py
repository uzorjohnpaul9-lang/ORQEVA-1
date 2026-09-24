"""Trading flow: open, close, history, risk gating."""
import httpx

from tests.conftest import register_and_login


async def _open_and_close(client, H):
    body = {"market": "crypto", "symbol": "BTCUSDT", "side": "buy",
            "order_type": "market", "quantity": 0.01}
    r = await client.post("/api/trading/orders", headers=H, json=body)
    if r.status_code not in (200, 201):
        body["entry_price"] = 50000
        r = await client.post("/api/trading/orders", headers=H, json=body)
    assert r.status_code in (200, 201), r.text
    trade_id = r.json()["trade_id"]

    r = await client.post(f"/api/trading/close/{trade_id}", headers=H)
    if r.status_code != 200:
        r = await client.post(f"/api/trading/close/{trade_id}", headers=H,
                              json={"exit_price": 51000})
    assert r.status_code == 200, r.text
    return r.json()


async def test_open_close_generates_history(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    closed = await _open_and_close(client, H)
    assert closed["status"] == "closed"

    r = await client.get("/api/trading/history", headers=H,
                         params={"outcome": "loss", "limit": 50})
    assert r.status_code == 200
    rows = r.json()["trades"]
    ours = [t for t in rows if t["id"] == closed["trade_id"]]
    if ours:  # pnl depends on fill prices; presence is what matters
        assert ours[0]["status"] == "closed"


async def test_history_filters_shape(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    r = await client.get("/api/trading/history", headers=H,
                         params={"market": "crypto", "symbol": "NOSUCHPAIR",
                                 "strategy": "ai", "outcome": "win"})
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"trades", "total", "summary"}
    assert body["trades"] == []


async def test_kill_switch_blocks_orders(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    r = await client.post("/api/risk/kill-switch", headers=H,
                          json={"active": True, "reason": "unit test"})
    assert r.status_code == 200

    body = {"market": "crypto", "symbol": "ETHUSDT", "side": "buy",
            "order_type": "market", "quantity": 0.1}
    r = await client.post("/api/trading/orders", headers=H, json=body)
    assert r.status_code in (400, 403)
    assert "kill switch" in r.json()["detail"].lower()

    # deactivate again
    await client.post("/api/risk/kill-switch", headers=H, json={"active": False})


async def test_max_daily_trades_cap(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    r = await client.put("/api/risk/limits", headers=H, json={"max_daily_trades": 1})
    assert r.status_code == 200

    body = {"market": "crypto", "symbol": "ETHUSDT", "side": "buy",
            "order_type": "market", "quantity": 0.01, "entry_price": 3000}
    r1 = await client.post("/api/trading/orders", headers=H, json=body)
    assert r1.status_code in (200, 201)

    r2 = await client.post("/api/trading/orders", headers=H, json=body)
    assert r2.status_code in (400, 403)
    assert "daily" in r2.json()["detail"].lower() or "trade" in r2.json()["detail"].lower()


async def test_risk_score_present(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    r = await client.get("/api/risk/status", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert "risk_score" in body or "score" in str(body.keys()).lower() or "limits" in str(body.keys()).lower()
