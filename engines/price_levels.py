"""Price precision and protective-level sanity checks.

Market data arrives at very different scales (BTC at ~100k, EUR/USD at ~1.08,
PEPE at ~0.000008). Rounding every instrument to four decimals collapses
sub-cent assets to zero and produces entry/SL/TP values that no longer
correspond to each other. These helpers keep the precision the database can
actually store (numeric(18,8)) and reject levels that are impossible to trade.
"""
from __future__ import annotations

import math


def price_decimals(value: float) -> int:
    """Decimals to keep for a price of this magnitude (max 8, DB precision)."""
    p = abs(float(value))
    if p >= 1000:
        return 2
    if p >= 1:
        return 5
    if p >= 0.01:
        return 6
    return 8


def round_price(value: float) -> float:
    """Round a price without destroying sub-cent precision."""
    try:
        return round(float(value), price_decimals(value))
    except (TypeError, ValueError):
        return float("nan")


def valid_levels(direction: str, entry: float, stop_loss: float, take_profit: float) -> bool:
    """True when entry/SL/TP are finite, positive and ordered for the side."""
    try:
        e, s, t = float(entry), float(stop_loss), float(take_profit)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(v) for v in (e, s, t)):
        return False
    if min(e, s, t) <= 0:
        return False
    side = (direction or "").lower()
    if side == "buy":
        return s < e < t
    if side == "sell":
        return t < e < s
    return False
