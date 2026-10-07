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
    """Factory: inject_engines(stock_syms, forex_syms, crypto_syms) -> call counter."""
    calls = {"n": 0}

    def emit(syms):
        def inner(self):
            calls["n"] += 1
            return [_sig(s) for s in syms]
        return inner

    def inject(stock_syms, forex_syms, crypto_syms):
        specs = [
            ("stock_engine", "StockEngine", stock_syms),
            ("forex_engine", "ForexEngine", forex_syms),
            ("crypto_engine", "CryptoEngine", crypto_syms),
        ]
        for mod_suffix, cls_name, syms in specs:
            mod = types.ModuleType(f"engines.{mod_suffix}")
            cls = type(cls_name, (), {
                "is_market_hours": lambda self: True,
                "run_cycle": emit(syms),
                "__init__": lambda self: None,
            })
            setattr(mod, cls_name, cls)
            monkeypatch.setitem(sys.modules, f"engines.{mod_suffix}", mod)

    inject.calls = calls
    return inject


@pytest.fixture
def quiet_fanout(monkeypatch):
    """Isolate run_scan from fan-out side effects.

    Telegram broadcasts (dead/revoked test tokens) and per-user notification
    inserts (130+ accumulated test users) are not what these tests assert on;
    they add minutes of network round-trips and can pollute `errors`.
    """
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.services.telegram_service.broadcast", _noop)
    monkeypatch.setattr("backend.services.notification_service.create", _noop)
    monkeypatch.setattr("backend.services.auto_trade_service.run_for_scan", _noop)


async def test_run_scan_saves_and_fanout_shape(fake_engines, quiet_fanout, client):
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    fake_engines(["AAPL"], [], ["BTCUSDT"])
    db = SupabaseDB(await get_service_client())
    out = await engine_service.run_scan(db, cooldown_hours=0)
    assert out["errors"] == []
    assert out["signals_generated"] == 2
    assert out["by_market"] == {"stock": 1, "forex": 0, "crypto": 1}
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
    assert second["by_market"] == {"stock": 0, "forex": 0, "crypto": 0}


async def test_run_scan_without_cooldown_allows_repeats(fake_engines, quiet_fanout, client):
    from backend.db.supabase import SupabaseDB, get_service_client
    from backend.services import engine_service

    fake_engines(["TSLA"], [], ["SOLUSDT"])
    db = SupabaseDB(await get_service_client())
    a = await engine_service.run_scan(db, cooldown_hours=0)
    b = await engine_service.run_scan(db, cooldown_hours=0)
    assert a["signals_generated"] == b["signals_generated"] == 2


async def test_run_scan_engine_error_captured(monkeypatch, quiet_fanout):
    bad = types.ModuleType("engines.stock_engine")

    def boom(self):
        raise RuntimeError("feed down")

    bad.StockEngine = type("StockEngine", (), {
        "is_market_hours": lambda self: True,
        "run_cycle": boom,
        "__init__": lambda self: None,
    })
    good = types.ModuleType("engines.forex_engine")
    good.ForexEngine = type("ForexEngine", (), {
        "is_market_hours": lambda self: True,
        "run_cycle": lambda self: [],
        "__init__": lambda self: None,
    })
    crypto = types.ModuleType("engines.crypto_engine")
    crypto.CryptoEngine = type("CryptoEngine", (), {
        "is_market_hours": lambda self: False,   # market closed -> skipped silently
        "run_cycle": lambda self: [],
        "__init__": lambda self: None,
    })
    monkeypatch.setitem(sys.modules, "engines.stock_engine", bad)
    monkeypatch.setitem(sys.modules, "engines.forex_engine", good)
    monkeypatch.setitem(sys.modules, "engines.crypto_engine", crypto)

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
    for suffix, cls in (("stock_engine", "StockEngine"),
                        ("forex_engine", "ForexEngine"),
                        ("crypto_engine", "CryptoEngine")):
        mod = types.ModuleType(f"engines.{suffix}")
        setattr(mod, cls, type(cls, (), {
            "is_market_hours": lambda self: False,
            "run_cycle": lambda self: [],
            "__init__": lambda self: None,
        }))
        monkeypatch.setitem(sys.modules, f"engines.{suffix}", mod)
    from backend.services import scheduler
    out = await scheduler.run_scheduled_scan()
    assert {"signals_generated", "by_market", "errors"} <= set(out.keys())
