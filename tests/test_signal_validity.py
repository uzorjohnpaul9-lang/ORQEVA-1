"""Signal validity rules: decay floor, grace window, and re-issue cooldown."""
from datetime import datetime, timedelta, timezone

from backend.services import engine_service, outcome_service, signal_service


def _ago(hours: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours)
    ).isoformat().replace("+00:00", "Z")


def test_signal_is_invalid_once_decayed_confidence_breaks_floor():
    assert signal_service.is_signal_valid(0.80, _ago(4)) is True
    assert signal_service.is_signal_valid(0.80, _ago(10)) is False


def test_boundary_signal_gets_the_grace_window():
    assert signal_service.is_signal_valid(0.50, _ago(0.5)) is True
    assert signal_service.is_signal_valid(0.50, _ago(2)) is False


def test_validity_view_labels_confidence_expiry():
    view = signal_service.signal_validity(
        0.60, _ago(20), status="expired", resolved_at=_ago(10)
    )
    assert view["valid"] is False
    assert view["invalidation_reason"] == "confidence_decay"


def test_validity_view_labels_time_expiry():
    view = signal_service.signal_validity(
        0.60, _ago(80), status="expired", resolved_at=_ago(1)
    )
    assert view["valid"] is False
    assert view["invalidation_reason"] == "time_expiry"


def test_active_signal_exposes_deadline_and_validity():
    view = signal_service.signal_validity(0.90, _ago(1), status="active")
    assert view["valid"] is True
    assert view["invalidation_reason"] is None
    assert view["valid_until"] is not None


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows

    async def fetch_all(self, *args, **kwargs):
        return self.rows


async def test_cooldown_ignores_expired_and_decayed_signals():
    rows = [
        {"symbol": "EUR/USD", "market": "forex", "direction": "buy",
         "status": "expired", "confidence": 0.80, "created_at": _ago(1)},
        {"symbol": "GBP/USD", "market": "forex", "direction": "buy",
         "status": "active", "confidence": 0.90, "created_at": _ago(1)},
        {"symbol": "XAU/USD", "market": "commodity", "direction": "sell",
         "status": "active", "confidence": 0.60, "created_at": _ago(20)},
        {"symbol": "BTC/USD", "market": "crypto", "direction": "buy",
         "status": "closed", "confidence": 0.80, "created_at": _ago(1)},
    ]
    keys = await engine_service.recent_signal_keys(
        _FakeDB(rows), 4, symbols=["EUR/USD", "GBP/USD", "XAU/USD", "BTC/USD"]
    )
    assert keys == {
        ("GBP/USD", "forex", "buy"),
        ("BTC/USD", "crypto", "buy"),
    }


class _ResolveDB:
    def __init__(self, row):
        self.row = row
        self.updates = []

    async def fetch_all(self, *args, **kwargs):
        return [self.row]

    async def update(self, table, data, where=None):
        self.updates.append(dict(data))
        return []


async def test_resolver_expires_signals_below_the_confidence_floor(monkeypatch):
    row = {
        "id": "sig-1",
        "symbol": "EUR/USD",
        "market": "forex",
        "direction": "buy",
        "confidence": 0.60,
        "entry_price": 1.10,
        "stop_loss": 1.09,
        "take_profit": 1.12,
        "created_at": _ago(20),
    }
    db = _ResolveDB(row)

    async def fake_bars(*args, **kwargs):
        return [], "1h"

    async def fake_close(*args, **kwargs):
        return None

    monkeypatch.setattr(outcome_service, "_fetch_bars_with_fallback", fake_bars)
    monkeypatch.setattr(
        "backend.services.order_executor.close_signal_trades", fake_close
    )

    counts = await outcome_service.resolve_active_signals(db)

    assert counts["expired"] == 1
    assert db.updates[0]["status"] == "expired"
    assert db.updates[0]["outcome"] == "expired"
    assert db.updates[0]["resolution_version"] == outcome_service.RESOLUTION_VERSION
