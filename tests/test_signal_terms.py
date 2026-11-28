"""Holding-horizon taxonomy, term-aware validity, cooldown and gating."""
from datetime import datetime, timedelta, timezone

from backend.services import (
    engine_service,
    notification_service,
    preferences_service,
    signal_service,
    signal_terms,
    telegram_service,
)


def _ago(minutes: float) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(minutes=minutes)
    ).isoformat().replace("+00:00", "Z")


def test_terms_have_stable_order_and_aliases():
    assert signal_terms.all_terms() == ("very_short", "short", "medium", "long", "very_long")
    assert signal_terms.normalize_term("SCALP") == "very_short"
    assert signal_terms.normalize_term("swing") == "medium"
    assert signal_terms.normalize_term("nonsense") == "very_long"
    assert signal_terms.normalize_terms(["scalp", "bogus", "very_long"]) == ["very_short", "very_long"]


def test_fast_terms_are_vip_and_paper_only():
    for term in signal_terms.FAST_TERMS:
        assert signal_terms.is_fast(term)
        assert signal_terms.min_tier(term) == "vip"
        assert signal_terms.paper_only(term) is True
    assert signal_terms.paper_only("very_long") is False


def test_term_horizon_labels():
    assert signal_terms.horizon_label("very_short") == "5\u201315 min"
    assert signal_terms.horizon_label("short") == "15\u201360 min"
    assert signal_terms.horizon_label("medium") == "1\u20136h"
    assert signal_terms.horizon_label("very_long") == "1\u20135 days"


def test_fast_term_decays_faster_than_swing():
    assert signal_service.is_signal_valid(0.60, _ago(5), term="very_short") is True
    assert signal_service.is_signal_valid(0.60, _ago(20), term="very_short") is False
    assert signal_service.is_signal_valid(0.60, _ago(20), term="very_long") is True


def test_validity_uses_the_term_max_age():
    view = signal_service.signal_validity(
        0.60, _ago(20), status="expired", resolved_at=_ago(10), term="very_short"
    )
    assert view["invalidation_reason"] == "confidence_decay"
    assert view["term"] == "very_short"

    view = signal_service.signal_validity(
        0.60, _ago(60), status="expired", resolved_at=_ago(5), term="very_short"
    )
    assert view["invalidation_reason"] == "time_expiry"


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch_all(self, *args, **kwargs):
        self.calls.append(kwargs)
        return self.rows

    async def insert(self, table, row):
        self.calls.append({"insert": table, "row": row})
        return row


async def test_save_signal_persists_term_deadline():
    db = _FakeDB([])
    row = await signal_service.save_signal(
        db, "BTC/USD", "crypto", "BUY", 0.7, 100, 98, 103, "test",
        tier="vip", term="very_short",
    )
    assert row["term"] == "very_short"
    assert row["timeframe"] == "1min"
    assert row["resolution_interval"] == "1min"
    assert row["expires_at"] is not None
    created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    assert round((expires - created).total_seconds() / 60) == 20


async def test_per_term_cooldown_returns_term_scoped_keys():
    rows = [
        {"symbol": "BTC/USD", "market": "crypto", "direction": "buy",
         "status": "active", "confidence": 0.70, "created_at": _ago(5),
         "term": "very_short"},
        {"symbol": "BTC/USD", "market": "crypto", "direction": "buy",
         "status": "active", "confidence": 0.90, "created_at": _ago(60),
         "term": "very_long"},
        {"symbol": "ETH/USD", "market": "crypto", "direction": "buy",
         "status": "active", "confidence": 0.70, "created_at": _ago(20),
         "term": "very_short"},
    ]
    keys = await engine_service.recent_signal_keys(
        _FakeDB(rows), hours=4, symbols=["BTC/USD", "ETH/USD"],
        term_cooldowns={"very_short": 0.25, "very_long": 4},
        include_term=True,
    )
    assert keys == {
        ("BTC/USD", "crypto", "buy", "very_short"),
        ("BTC/USD", "crypto", "buy", "very_long"),
    }


def test_preferences_can_filter_by_term():
    prefs = {
        "watchlist": ["BTC/USD"], "directions": [], "min_confidence": 0,
        "terms": ["very_short", "short"],
    }
    assert preferences_service.matches_filters(prefs, {"symbol": "BTC/USD", "term": "very_short"})
    assert not preferences_service.matches_filters(prefs, {"symbol": "BTC/USD", "term": "very_long"})


def test_telegram_signal_gate_blocks_free_users_from_fast_signals():
    fast = {"tier_required": "vip"}
    assert telegram_service._can_receive_signal("vip", fast) is True
    assert telegram_service._can_receive_signal("premium", fast) is False
    assert telegram_service._can_receive_signal("free", fast) is False
    assert telegram_service._can_receive_signal("free", {"tier_required": "free"}) is True


async def test_in_app_fanout_respects_signal_tier(monkeypatch):
    users = [{"id": "free-1", "tier": "free"}, {"id": "vip-1", "tier": "vip"}]
    created: list[tuple[str, str]] = []

    async def fake_create(db, user_id, ntype, title, message, **kwargs):
        created.append((user_id, title))

    async def noop(*args, **kwargs):
        return None

    for name in ("queue_channel_signals", "flush_channel_signals", "broadcast_signals"):
        monkeypatch.setattr(telegram_service, name, noop)
    monkeypatch.setattr(notification_service, "create", fake_create)

    await engine_service._fan_out(
        _FakeDB(users),
        {},
        [{"symbol": "BTC/USD", "direction": "buy", "market": "crypto",
          "confidence": 0.7, "strategy": "Fast", "tier_required": "vip"}],
        [],
    )
    assert created == [("vip-1", "buy signal: BTC/USD")]


async def test_non_vip_teasers_never_expose_fast_terms():
    rows = [
        {"symbol": "BTC/USD", "market": "crypto", "direction": "buy",
         "confidence": 0.70, "tier_required": "vip", "created_at": _ago(1),
         "term": "very_short"},
        {"symbol": "ETH/USD", "market": "crypto", "direction": "buy",
         "confidence": 0.70, "tier_required": "premium", "created_at": _ago(10),
         "term": "medium"},
    ]
    db = _FakeDB(rows)
    teasers = await signal_service.locked_teasers(db, tier="free")
    assert [t["term"] for t in teasers] == ["medium"]
    assert set(db.calls[-1]["where"]["term"]) == {"medium", "long", "very_long"}


async def test_non_vip_cannot_request_fast_teasers():
    db = _FakeDB([])
    assert await signal_service.locked_teasers(db, tier="premium", term="short") == []
    assert db.calls == []
