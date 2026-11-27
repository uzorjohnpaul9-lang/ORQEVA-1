"""Fast-lane engine: ATR targets, cost gate and term tagging."""
from engines import intraday_engine


def _bars(n: int = 90, start: float = 100.0, step: float = 0.2, rng: float = 1.0):
    out = []
    price = start
    for _ in range(n):
        open_ = price
        close = price + step
        high = max(open_, close) + rng
        low = min(open_, close) - rng
        out.append({
            "time": "2026-01-01T00:00:00Z",
            "open": open_, "high": high, "low": low, "close": close,
        })
        price = close
    return out


def _patch_score(monkeypatch):
    def fake_score(*args, **kwargs):
        return {"direction": "BUY", "confidence": 0.80, "reasons": ["test"]}

    monkeypatch.setattr(intraday_engine, "score_signal", fake_score)


def _engine(monkeypatch, bars, term="very_short"):
    _patch_score(monkeypatch)
    engine = intraday_engine.IntradayEngine("crypto", ["BTC/USD"], term)
    monkeypatch.setattr(engine, "_fetch_bars", lambda symbol, limit: bars)
    return engine


def test_fast_signal_is_term_tagged_and_cost_aware(monkeypatch):
    engine = _engine(monkeypatch, _bars())
    signal = engine.analyze_symbol("BTC/USD")

    assert signal is not None
    assert signal.term == "very_short"
    assert signal.timeframe == "1min"
    assert signal.target_price > signal.price
    assert signal.stop_loss < signal.price
    assert signal.metadata["term"] == "very_short"
    assert signal.metadata["horizon"] == "5\u201315 min"
    assert signal.metadata["cost_pct"] > 0


def test_fast_signal_rejects_setups_that_cannot_clear_costs(monkeypatch):
    engine = _engine(monkeypatch, _bars(rng=0.00001, step=0.00001))
    assert engine.analyze_symbol("BTC/USD") is None


def test_fast_engine_maps_to_vip_term_row(monkeypatch):
    from backend.services import engine_service

    engine = _engine(monkeypatch, _bars())
    signal = engine.analyze_symbol("BTC/USD")
    row = engine_service._engine_signal_to_db(
        signal, "crypto", "Fast Very short", "vip",
        term="very_short", timeframe="1min",
    )
    assert row["term"] == "very_short"
    assert row["timeframe"] == "1min"
    assert row["resolution_interval"] == "1min"
    assert row["tier"] == "vip"
