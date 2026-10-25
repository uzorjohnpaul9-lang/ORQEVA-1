"""Price precision + protective-level checks for generated signals."""
from types import SimpleNamespace

import pytest

from engines.price_levels import price_decimals, round_price, valid_levels


def test_sub_cent_assets_keep_precision():
    # PEPE/SHIB/FLOKI prices must not collapse to 0.0000.
    assert round_price(0.00000785) == 0.00000785
    assert round_price(0.000012345678) == 0.00001235
    assert round_price(0.0) == 0.0


def test_major_prices_keep_market_conventions():
    assert price_decimals(1.3374) == 5
    assert round_price(1.337456) == 1.33746
    assert round_price(156.81449) == 156.81449
    assert round_price(100000.123) == 100000.12


def test_valid_levels_order_by_side():
    assert valid_levels("buy", 1.33, 1.327, 1.34)
    assert valid_levels("sell", 1.33, 1.333, 1.32)
    assert not valid_levels("buy", 1.33, 1.34, 1.32)
    assert not valid_levels("sell", 1.33, 1.32, 1.34)
    assert not valid_levels("buy", 0.0, 0.0, 0.0)
    assert not valid_levels("buy", 1.33, float("nan"), 1.34)


def test_engine_row_uses_full_precision():
    from backend.services.engine_service import _engine_signal_to_db

    sig = SimpleNamespace(
        symbol="PEPE/USD",
        direction="BUY",
        confidence=0.71,
        price=0.00000785,
        stop_loss=0.00000746,
        target_price=0.00000864,
        metadata={"data_source": "live"},
    )
    row = _engine_signal_to_db(sig, "crypto", "Meme Momentum", "vip")
    assert row["direction"] == "buy"
    assert row["entry_price"] == 0.00000785
    assert row["stop_loss"] == 0.00000746
    assert row["take_profit"] == 0.00000864


def test_engine_row_rejects_broken_levels():
    from backend.services.engine_service import _engine_signal_to_db

    sig = SimpleNamespace(
        symbol="EUR/USD",
        direction="BUY",
        confidence=0.7,
        price=1.08,
        stop_loss=0.0,
        target_price=1.09,
        metadata={"data_source": "live"},
    )
    with pytest.raises(ValueError):
        _engine_signal_to_db(sig, "forex", "Twelve Data Trend", "free")
