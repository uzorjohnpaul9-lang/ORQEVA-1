"""Phase 20 groundwork: /metrics, /readyz, engine scheduler + scan service."""
import sys
import types
from types import SimpleNamespace

import pytest

from tests.conftest import register_and_login


def _fake_engine_module(class_name: str, signals):
    mod = types.ModuleType(f"engines.{class_name.lower()}")
    cls = type(class_name, (), {
        "is_market_hours": lambda self: True,
        "run_cycle": lambda self: list(signals),
        "__init__": lambda self: None,
    })
    setattr(mod, class_name, cls)
    return mod


def _sig(symbol, direction="buy"):
    return SimpleNamespace(
        symbol=symbol, direction=direction, confidence=0.7,
        price=100.0, stop_loss=95.0, target_price=110.0, metadata={"src": "test"},
    )


# ---------- HTTP endpoints ----------

async def test_metrics_scrape(client):
    await client.get("/api/health")  # generate traffic for counters
    r = await client.get("/metrics")
    assert r.status_code == 200
    body = r.content
    assert b"http_requests_total" in body
    assert b"http_request_duration_seconds" in body


async def test_readyz_ok(client):
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["database"] == "up"


# ---------- record_scan instrumentation ----------

def test_record_scan_updates_metrics():
    from backend.monitoring.metrics import record_scan, render

    before = render()[0]
    record_scan(3, False)
    after = render()[0]
    assert b"engine_scans_total" in after
    # scans counter must have increased by one series value
    def total(buf: bytes) -> float:
        for line in buf.decode().splitlines():
            if line.startswith("engine_scans_total "):
                return float(line.split()[1])
        return 0.0

    assert total(after) == pytest.approx(total(before) + 1)


# ---------- scheduler config ----------

def test_scheduler_env_config(monkeypatch):
    from backend.services import scheduler

    monkeypatch.setenv("SCAN_INTERVAL_MINUTES", "0.5")
    assert scheduler._interval_seconds() == 60  # clamped to >= 60s
    monkeypatch.setenv("SCAN_COOLDOWN_HOURS", "-2")
    assert scheduler._cooldown_hours() == 0
    monkeypatch.setenv("SCAN_ENABLED", "no")
    assert scheduler._enabled() is False


# ---------- run_scan with injected engines ----------

@pytest.fixture
def fake_engines(monkeypatch):
    """Factory: inject_engines(stock_syms, forex_syms, crypto_syms) -> call counter.

    Every engine listed in engine_service._ENGINE_SPECS is replaced, so a scan
    never reaches a live market feed (the alt/commodity engines otherwise pull
    real klines from Binance/Bybit/Coinbase/OKX/Twelve Data and inject signals
    the test never asked for).

    Symbols are keyed by engine *bucket*, not by db_market: crypto_alt shares
    the "crypto" market with the crypto engine but stays silent unless a test
    asks for it.
    """
    from backend.services import engine_service

    calls = {"n": 0}

    def emit(syms):
        def inner(self):
            calls["n"] += 1
            return [_sig(s) for s in syms]
        return inner

    def inject(stock_syms, forex_syms, crypto_syms):
        by_bucket = {"stock": stock_syms, "forex": forex_syms, "crypto": crypto_syms}
        for bucket, mod_name, cls_name, _strategy, _tier, _db_market in engine_service._ENGINE_SPECS:
            syms = by_bucket.get(bucket, [])
            mod = types.ModuleType(mod_name)
            cls = type(cls_name, (), {
                "is_market_hours": lambda self: True,
                "run_cycle": emit(syms),
                "__init__": lambda self: None,
            })
            setattr(mod, cls_name, cls)
            monkeypatch.setitem(sys.modules, mod_name, mod)

    inject.calls = calls
    return inject


@pytest.fixture
def quiet_fanout(monkeypatch):
    """Isolate run_scan from fan-out side effects.

    Telegram broadcasts (dead/revoked test tokens) and per-user notification
    inserts (130+ accumulated test users) are not what these tests assert on;
    they add minutes of network round-trips and can pollute `errors`.

    Outcome resolution and billing jobs are stubbed for the same reason: the
    first fetches live prices against a 240s budget, the second can create
    real gateway invoices in the sandbox.
    """
    async def _noop(*args, **kwargs):
        return None

    async def _empty_dict(*args, **kwargs):
        return {}

    monkeypatch.setattr("backend.services.telegram_service.broadcast", _noop)
    monkeypatch.setattr("backend.services.notification_service.create", _noop)
    monkeypatch.setattr("backend.services.auto_trade_service.run_for_scan", _noop)
    monkeypatch.setattr("backend.services.outcome_service.resolve_active_signals", _empty_dict)
    monkeypatch.setattr("backend.services.billing_service.billing_jobs", _empty_dict)


async def test_run_scan_saves_and_fanout_shape(fake_engines, quiet_fanout, client):
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    fake_engines(["AAPL"], [], ["BTCUSDT"])
    db = SupabaseDB(await get_service_client())
    out = await engine_service.run_scan(db, cooldown_hours=0)
    assert out["errors"] == []
    assert out["signals_generated"] == 2
    assert out["by_market"] == {
        "stock": 1, "forex": 0, "crypto": 1, "crypto_alt": 0, "commodity": 0,
    }
    keys = {(s["symbol"], s["market"]) for s in out["saved"]}
    assert ("AAPL", "stock") in keys and ("BTCUSDT", "crypto") in keys


async def test_run_scan_cooldown_suppresses_duplicates(fake_engines, quiet_fanout, client):
    """Second identical scan within the cooldown window must save nothing."""
    from backend.db.models import SIGNALS
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    fake_engines(["MSFT"], ["EURUSD"], ["ETHUSDT"])

    db = SupabaseDB(await get_service_client())
    # prior suite runs may have saved these within 24h -> clear them first
    for sym in ("MSFT", "EURUSD", "ETHUSDT"):
        await db.delete(SIGNALS, {"symbol": sym})

    first = await engine_service.run_scan(db, cooldown_hours=24)
    assert first["signals_generated"] == 3

    second = await engine_service.run_scan(db, cooldown_hours=24)
    assert second["signals_generated"] == 0
    assert second["by_market"] == {
        "stock": 0, "forex": 0, "crypto": 0, "crypto_alt": 0, "commodity": 0,
    }


async def test_cooldown_key_matches_stored_direction(monkeypatch, quiet_fanout, client):
    """The cooldown key must match the direction that is actually stored.

    Engines emit "BUY"/"SELL" while rows are stored lowercased. If the key
    is not normalised the same way, every real signal bypasses the cooldown
    and gets published over and over.
    """
    from backend.db.models import SIGNALS
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    def _upper(sym):
        return SimpleNamespace(
            symbol=sym, direction="BUY", confidence=0.7, price=100.0,
            stop_loss=95.0, target_price=110.0, metadata={"src": "test"},
        )

    _patch_all_engines(monkeypatch, {"StockEngine": lambda self: [_upper("UPPERCOOLDOWN")]})

    db = SupabaseDB(await get_service_client())
    await db.delete(SIGNALS, {"symbol": "UPPERCOOLDOWN"})

    first = await engine_service.run_scan(db, cooldown_hours=24)
    assert first["signals_generated"] == 1
    rows = await db.fetch_all(
        SIGNALS, where={"symbol": "UPPERCOOLDOWN"}, columns="symbol,market,direction"
    )
    assert rows and rows[0]["direction"] == "buy"

    second = await engine_service.run_scan(db, cooldown_hours=24)
    assert second["signals_generated"] == 0


async def test_run_scan_without_cooldown_allows_repeats(fake_engines, quiet_fanout, client):
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    fake_engines(["TSLA"], [], ["SOLUSDT"])
    db = SupabaseDB(await get_service_client())
    a = await engine_service.run_scan(db, cooldown_hours=0)
    b = await engine_service.run_scan(db, cooldown_hours=0)
    assert a["signals_generated"] == b["signals_generated"] == 2


def _patch_all_engines(monkeypatch, run_cycle_by_engine=None, market_hours=True):
    """Replace every engine in engine_service._ENGINE_SPECS.

    Tests that patch only the three original engines leave crypto_alt and
    commodity running against live feeds: the suite turns into a network
    benchmark and real signals/errors leak into the assertions.
    """
    from backend.services import engine_service

    run_cycle_by_engine = run_cycle_by_engine or {}
    for _bucket, mod_name, cls_name, _strategy, _tier, _db_market in engine_service._ENGINE_SPECS:
        mod = types.ModuleType(mod_name)
        cls = type(cls_name, (), {
            "is_market_hours": lambda self: market_hours,
            "run_cycle": run_cycle_by_engine.get(cls_name, lambda self: []),
            "__init__": lambda self: None,
        })
        setattr(mod, cls_name, cls)
        monkeypatch.setitem(sys.modules, mod_name, mod)


async def test_run_scan_engine_error_captured(monkeypatch, quiet_fanout):
    def boom(self):
        raise RuntimeError("feed down")

    _patch_all_engines(monkeypatch, {
        "StockEngine": boom,
        "ForexEngine": lambda self: [],
        "CryptoEngine": lambda self: [],
    })

    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    db = SupabaseDB(await get_service_client())
    out = await engine_service.run_scan(db)
    assert len(out["errors"]) == 1 and "feed down" in out["errors"][0]
    assert out["signals_generated"] == 0


async def test_scheduled_scan_tick_never_raises(monkeypatch, quiet_fanout):
    """run_scheduled_scan swallows DB/engine failures."""
    monkeypatch.setenv("SCAN_COOLDOWN_HOURS", "4")
    # empty fake engines: this asserts the tick's error handling, not live feeds
    _patch_all_engines(monkeypatch, market_hours=False)
    from backend.services import scheduler
    out = await scheduler.run_scheduled_scan()
    assert {"signals_generated", "by_market", "errors"} <= set(out.keys())
