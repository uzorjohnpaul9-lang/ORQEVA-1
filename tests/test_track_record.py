"""Public track-record rules: no look-ahead, live-only, net R, safe CSV."""
import json

import pytest

from backend.db import supabase as supabase_db
from backend.services import outcome_service, track_record_service


def test_apply_filters_uses_is_method_for_null():
    calls = {}

    class Query:
        def is_(self, col, value):
            calls["is"] = (col, value)
            return self

    supabase_db._apply_filters(Query(), {"user_id": {"op": "is", "value": "null"}})
    assert calls["is"] == ("user_id", "null")


def _bar(time, o, h, l, c):
    return {"time": time, "open": o, "high": h, "low": l, "close": c}


def test_evaluate_ignores_bar_containing_creation():
    created = "2026-01-01T12:00:00Z"
    bars = [
        _bar("2026-01-01T10:00:00Z", 100, 200, 90, 190),  # pre-signal: TP + SL
        _bar("2026-01-01T13:00:00Z", 100, 110, 95, 96),   # after: only SL
    ]
    assert outcome_service.evaluate("buy", 100, 95, 200, bars, created) == ("sl", 95)


def test_evaluate_same_bar_both_levels_is_stop_first():
    bars = [_bar("2026-01-01T13:00:00Z", 100, 200, 90, 150)]
    assert outcome_service.evaluate(
        "buy", 100, 95, 200, bars, "2026-01-01T12:00:00Z"
    ) == ("sl", 95)


def test_evaluate_sell_direction():
    bars = [_bar("2026-01-01T13:00:00Z", 100, 102, 80, 82)]
    assert outcome_service.evaluate(
        "sell", 100, 105, 90, bars, "2026-01-01T12:00:00Z"
    ) == ("tp", 90)


def test_evaluate_no_bars_after_creation_returns_none():
    bars = [_bar("2026-01-01T10:00:00Z", 100, 200, 90, 150)]
    assert outcome_service.evaluate(
        "buy", 100, 95, 200, bars, "2026-01-01T12:00:00Z"
    ) is None


class _FakeDB:
    def __init__(self):
        self.calls = []

    async def update(self, table, data, where=None):
        self.calls.append(dict(data))
        if any(k in data for k in ("resolution_basis", "resolution_version")):
            raise RuntimeError("column does not exist")
        return []


async def test_persist_outcome_falls_back_without_provenance():
    db = _FakeDB()
    await outcome_service._persist_outcome(
        db,
        {"status": "closed", "outcome": "tp", "resolution_basis": "1h",
         "resolution_version": "v1"},
        "sig-1",
    )
    assert len(db.calls) == 2
    assert "resolution_basis" not in db.calls[1]
    assert db.calls[1]["outcome"] == "tp"


def _row(outcome, r, source="live", market="crypto", strategy="trend"):
    return {
        "id": f"{outcome}-{r}-{source}",
        "symbol": "BTCUSDT",
        "market": market,
        "direction": "buy",
        "outcome": outcome,
        "r_multiple": r,
        "data_source": source,
        "strategy": strategy,
        "created_at": "2026-01-01T00:00:00Z",
        "resolved_at": "2026-01-02T00:00:00Z",
    }


def test_aggregate_live_only_gross_and_net():
    rows = [
        _row("tp", 2.0),
        _row("sl", -1.0),
        _row("expired", 0.5),
        _row("breakeven", 0.0),
        _row("tp", 5.0, source="simulated"),
        _row("tp", 5.0, source=None),
    ]
    out = track_record_service.aggregate(rows, cost=0.05, gate=3)

    assert out["resolved"] == 4
    assert out["tp"] == 1 and out["sl"] == 1
    assert out["expired"] == 1 and out["breakeven"] == 1
    assert out["win_rate"] == 25.0
    assert out["win_rate_tp_sl"] == 50.0
    assert out["avg_r_gross"] == 0.375
    assert out["avg_r_net"] == 0.325
    assert out["excluded"] == {"simulated": 1, "unknown": 1}
    assert out["status"] == "live"
    assert out["live_only"] is True
    assert out["by_market"][0]["market"] == "crypto"


def test_aggregate_collecting_below_gate():
    out = track_record_service.aggregate([_row("tp", 1.0)], cost=0.05, gate=30)
    assert out["status"] == "collecting"
    assert out["sample"] == {
        "resolved": 1, "needed": 30, "remaining": 29, "progress_pct": 3.3
    }


def test_csv_has_header_and_guards_formulas():
    row = track_record_service._public_row(
        {
            **_row("tp", 2.0),
            "symbol": "=cmd|' /C calc'!A0",
            "entry_price": 100,
            "stop_loss": 95,
            "take_profit": 110,
            "exit_price": 110,
        },
        cost=0.05,
    )
    text = track_record_service.rows_to_csv([row])
    lines = text.split("\r\n")
    assert lines[0].startswith("signal_id,opened_at,closed_at,symbol")
    assert "r_multiple_gross" in lines[0] and "r_multiple_net" in lines[0]
    assert "'=cmd" in text
    assert ",1.95," in text  # 2.0 gross - 0.05 cost


async def test_public_endpoint_is_unauthenticated_and_cached(client, monkeypatch):
    payload = track_record_service.aggregate(
        [_row("tp", 1.5), _row("sl", -1.0)], cost=0.05, gate=2
    )
    payload.update(
        generated_at="2026-01-02T00:00:00Z",
        resolution_version="test",
        methodology={"version": "test"},
        recent=[track_record_service._public_row(_row("tp", 1.5), 0.05)],
    )

    async def fake_snapshot(*, recent_limit=50):
        return payload

    monkeypatch.setattr("backend.api.track_record._snapshot", fake_snapshot)

    r = await client.get(
        "/api/track-record",
        headers={"Origin": "https://preview.orqeva.pages.dev"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["cache-control"].startswith("public")
    assert r.headers["x-track-record-version"] == "test"
    assert r.headers["access-control-allow-origin"] == "https://preview.orqeva.pages.dev"

    body = r.json()
    assert body["live_only"] is True
    assert "user_id" not in json.dumps(body)
    assert body["recent"][0]["r_multiple_net"] == 1.45

    r2 = await client.get(
        "/api/track-record", headers={"If-None-Match": r.headers["etag"]}
    )
    assert r2.status_code == 304

    csv_r = await client.get("/api/track-record.csv")
    assert csv_r.status_code == 200
    assert csv_r.headers["content-type"].startswith("text/csv")
    assert "signal_id,opened_at" in csv_r.text
