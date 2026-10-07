"""Endpoint coverage: dashboard, signals, portfolio, ai, market, admin."""
import uuid

import httpx

from tests.conftest import register_and_login


# ── Dashboard ────────────────────────────────────────────────────────────────

async def test_dashboard_overview_and_notifications(client: httpx.AsyncClient):
    assert (await client.get("/api/dashboard/overview")).status_code == 401

    H, _ = await register_and_login(client)
    r = await client.get("/api/dashboard/overview", headers=H)
    assert r.status_code == 200
    body = r.json()
    for key in ("total_signals", "active_signals", "open_trades",
                "total_pnl", "win_rate", "portfolio_value"):
        assert key in body
    assert body["open_trades"] == 0
    assert body["total_pnl"] == 0.0
    assert body["win_rate"] == 0.0

    r = await client.get("/api/dashboard/notifications", headers=H)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Signals ──────────────────────────────────────────────────────────────────

async def test_signals_list_stats_accuracy(client: httpx.AsyncClient):
    assert (await client.get("/api/signals/")).status_code == 401

    H, _ = await register_and_login(client)
    r = await client.get("/api/signals/", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    if body:
        assert "effective_confidence" in body[0]
        assert "age_hours" in body[0]

    r = await client.get("/api/signals/stats", headers=H)
    assert r.status_code == 200 and isinstance(r.json(), dict)

    r = await client.get("/api/signals/accuracy", headers=H)
    assert r.status_code == 200 and isinstance(r.json(), dict)


async def test_signal_detail_404_and_tier_gate(client: httpx.AsyncClient):
    H, _ = await register_and_login(client)
    Ha, _ = await register_and_login(client, admin=True)

    r = await client.get(f"/api/signals/{uuid.uuid4()}", headers=H)
    assert r.status_code == 404

    from backend.db.models import SIGNALS
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import signal_service

    db = SupabaseDB(await get_service_client())
    sig = await signal_service.save_signal(
        db, "TIERGATE", "stock", "buy", 75.0, 100.0, 97.0, 105.0,
        "tier-gate-test", tier="vip",
    )
    try:
        r = await client.get(f"/api/signals/{sig['id']}", headers=H)
        assert r.status_code == 403

        r = await client.get(f"/api/signals/{sig['id']}", headers=Ha)
        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == "TIERGATE"
        assert body["tier_required"] == "vip"
        assert "effective_confidence" in body
    finally:
        await db.delete(SIGNALS, {"id": sig["id"]})


# ── Portfolio ────────────────────────────────────────────────────────────────

async def test_portfolio_empty_state(client: httpx.AsyncClient):
    assert (await client.get("/api/portfolio/trades")).status_code == 401

    H, _ = await register_and_login(client)
    r = await client.get("/api/portfolio/trades", headers=H)
    assert r.status_code == 200 and r.json() == []

    r = await client.get("/api/portfolio/summary", headers=H)
    assert r.status_code == 200
    s = r.json()
    assert s["total_trades"] == 0
    assert s["open_trades"] == 0
    assert s["total_pnl"] == 0.0

    # No open trades -> no live-quote fan-out, both endpoints stay local
    for path in ("/api/portfolio/positions", "/api/portfolio/holdings"):
        r = await client.get(path, headers=H)
        assert r.status_code == 200 and r.json() == []

    r = await client.get("/api/portfolio/performance", headers=H)
    assert r.status_code == 200
    p = r.json()
    assert p["starting_value"] == 100000.0
    assert p["total_pnl"] == 0.0
    assert p["win_rate"] == 0.0

    # validation: limit out of range
    r = await client.get("/api/portfolio/trades", headers=H, params={"limit": 500})
    assert r.status_code == 422


# ── AI ───────────────────────────────────────────────────────────────────────

async def test_ai_models_and_validation(client: httpx.AsyncClient):
    assert (await client.get("/api/ai/models")).status_code == 401

    H, _ = await register_and_login(client)
    r = await client.get("/api/ai/models", headers=H)
    assert r.status_code == 200
    assert isinstance(r.json()["models"], list) and r.json()["models"]

    # invalid market short-circuits before any market-data fetch
    r = await client.get("/api/ai/analysis", headers=H,
                         params={"symbol": "AAPL", "market": "bogus"})
    assert r.status_code == 200
    assert r.json() == {"error": "invalid_market"}

    # missing symbol -> request validation error
    r = await client.get("/api/ai/analysis", headers=H, params={"market": "stock"})
    assert r.status_code == 422


async def test_ai_analysis_and_summary_mocked(client: httpx.AsyncClient, monkeypatch):
    from backend.services import ai_service

    async def fake_analyze(market: str, symbol: str):
        return {"market": market, "symbol": symbol.upper(), "confidence": 0.42}

    # patch the data-fetching primitive; market_summary composes on top of it
    monkeypatch.setattr(ai_service, "analyze", fake_analyze)

    H, _ = await register_and_login(client)
    r = await client.get("/api/ai/analysis", headers=H,
                         params={"symbol": "aapl", "market": "stock"})
    assert r.status_code == 200
    assert r.json()["symbol"] == "AAPL"
    assert r.json()["confidence"] == 0.42

    r = await client.get("/api/ai/summary", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["models"] == ai_service.MODEL_ROSTER
    assert {m["market"] for m in body["markets"]}  # one entry per market


# ── Market (providers monkeypatched; no live network) ───────────────────────

async def test_market_endpoints_mocked(client: httpx.AsyncClient, monkeypatch):
    from backend.services import market_service

    monkeypatch.setattr(market_service, "get_overview",
                        lambda: {"indices": [{"name": "S&P 500", "price": 5000.0}]})
    monkeypatch.setattr(market_service, "get_quote",
                        lambda market, symbol: {"market": market, "symbol": symbol, "price": 1.23})
    monkeypatch.setattr(market_service, "get_movers",
                        lambda: {"gainers": [], "losers": []})
    monkeypatch.setattr(market_service, "get_bars",
                        lambda market, symbol, interval, n:
                        {"symbol": symbol, "interval": interval, "bars": []})
    monkeypatch.setattr(market_service, "get_discovery",
                        lambda top_n: {"top": [], "count": top_n})

    assert (await client.get("/api/market/overview")).status_code == 401

    H, _ = await register_and_login(client)

    r = await client.get("/api/market/overview", headers=H)
    assert r.status_code == 200 and r.json()["indices"]

    r = await client.get("/api/market/quotes", headers=H,
                         params={"symbols": "btc, eth", "market": "crypto"})
    assert r.status_code == 200
    quotes = r.json()["quotes"]
    assert len(quotes) == 2
    assert {q["symbol"] for q in quotes} == {"BTC", "ETH"}

    r = await client.get("/api/market/movers", headers=H)
    assert r.status_code == 200

    r = await client.get("/api/market/bars", headers=H,
                         params={"symbol": "btc", "market": "crypto", "outputsize": 5})
    assert r.status_code == 200
    assert r.json()["symbol"] == "BTC"

    r = await client.get("/api/market/discovery", headers=H, params={"top_n": 3})
    assert r.status_code == 200 and r.json()["count"] == 3

    # validation
    r = await client.get("/api/market/quotes", headers=H)
    assert r.status_code == 422
    r = await client.get("/api/market/bars", headers=H,
                         params={"symbol": "btc", "outputsize": 500})
    assert r.status_code == 422


# ── Admin ────────────────────────────────────────────────────────────────────

async def test_admin_requires_admin_role(client: httpx.AsyncClient):
    assert (await client.get("/api/admin/users")).status_code == 401

    H, _ = await register_and_login(client)
    r = await client.get("/api/admin/users", headers=H)
    assert r.status_code == 403

    r = await client.get("/api/admin/system", headers=H)
    assert r.status_code == 403


async def test_admin_user_management_and_status(client: httpx.AsyncClient):
    Ha, email = await register_and_login(client, admin=True)

    r = await client.get("/api/admin/users", headers=Ha)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    me = next(u for u in users if u["email"] == email)
    assert me["is_admin"] is True

    # tier change on self (allowed; only admin/active revocation is guarded)
    r = await client.patch(f"/api/admin/users/{me['id']}", headers=Ha,
                           json={"tier": "premium"})
    assert r.status_code == 200
    assert r.json()["tier"] == "premium"

    # self-guards
    r = await client.patch(f"/api/admin/users/{me['id']}", headers=Ha,
                           json={"is_admin": False})
    assert r.status_code == 400
    r = await client.patch(f"/api/admin/users/{me['id']}", headers=Ha,
                           json={"is_active": False})
    assert r.status_code == 400

    # unknown user
    r = await client.patch(f"/api/admin/users/{uuid.uuid4()}", headers=Ha,
                           json={"tier": "vip"})
    assert r.status_code == 404

    # reset-password on unknown user fails before touching auth
    r = await client.post(f"/api/admin/users/{uuid.uuid4()}/reset-password",
                          headers=Ha, json={})
    assert r.status_code == 404


async def test_admin_system_audit_subscriptions_signals(client: httpx.AsyncClient):
    Ha, _ = await register_and_login(client, admin=True)

    r = await client.get("/api/admin/system", headers=Ha)
    assert r.status_code == 200
    sys_body = r.json()
    assert "scheduler" in sys_body
    assert "integrations" in sys_body
    assert sys_body["supabase_reachable"] is True

    r = await client.get("/api/admin/audit", headers=Ha)
    assert r.status_code == 200 and isinstance(r.json(), list)

    r = await client.get("/api/admin/subscriptions", headers=Ha)
    assert r.status_code == 200 and isinstance(r.json(), list)

    r = await client.get("/api/admin/signals", headers=Ha)
    assert r.status_code == 200 and isinstance(r.json(), list)
