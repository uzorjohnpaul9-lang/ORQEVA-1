"""Methodology-based signal detectors for the ORQEVA engines.

Each detector reads a close-price series and, when its public-methodology
pattern is present, returns a candidate with a direction, a confidence (0-1)
and a human-readable reason. `scan()` returns the single best candidate.

These are deliberately transparent — the same rules the Academy teaches — so
every strategy-tagged signal can be explained to a learner.
"""
from __future__ import annotations

from typing import Any, Optional

MIN_BARS = 30


def _sma(vals: list[float], n: int) -> Optional[float]:
    if len(vals) < n or n <= 0:
        return None
    return sum(vals[-n:]) / n


def _slope(vals: list[float], n: int = 6) -> float:
    """Normalised least-squares slope over the last n bars."""
    if len(vals) < n or n < 2:
        return 0.0
    y = vals[-n:]
    x = list(range(n))
    mx = sum(x) / n
    my = sum(y) / n
    denom = sum((xi - mx) ** 2 for xi in x) or 1.0
    slope = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / denom
    return slope / (abs(my) or 1.0)


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def detect_trend_following(prices: list[float]) -> Optional[dict[str, Any]]:
    if len(prices) < 50:
        return None
    fast = _sma(prices, 20)
    slow = _sma(prices, 50)
    if fast is None or slow is None:
        return None
    price = prices[-1]
    slope = _slope(prices, 10)
    sep = (fast - slow) / (abs(slow) or 1.0)
    if fast > slow and price > fast and slope > 0:
        conf = _clamp(0.45 + abs(sep) * 8 + abs(slope) * 4)
        return {"strategy": "Trend Following", "direction": "BUY", "confidence": conf,
                "reason": "fast MA above slow MA, price above both, rising trend"}
    if fast < slow and price < fast and slope < 0:
        conf = _clamp(0.45 + abs(sep) * 8 + abs(slope) * 4)
        return {"strategy": "Trend Following", "direction": "SELL", "confidence": conf,
                "reason": "fast MA below slow MA, price below both, falling trend"}
    return None


def detect_momentum_surge(prices: list[float]) -> Optional[dict[str, Any]]:
    if len(prices) < 21:
        return None
    roc5 = (prices[-1] / prices[-6] - 1) if prices[-6] else 0.0
    roc20 = (prices[-1] / prices[-21] - 1) if prices[-21] else 0.0
    if roc5 > 0.02 and roc20 > 0:
        return {"strategy": "Momentum Surge", "direction": "BUY", "confidence": _clamp(0.45 + roc5 * 5),
                "reason": f"short ({roc5:.1%}) and medium ({roc20:.1%}) momentum positive"}
    if roc5 < -0.02 and roc20 < 0:
        return {"strategy": "Momentum Surge", "direction": "SELL", "confidence": _clamp(0.45 + abs(roc5) * 5),
                "reason": f"short ({roc5:.1%}) and medium ({roc20:.1%}) momentum negative"}
    return None


def detect_breakout(prices: list[float]) -> Optional[dict[str, Any]]:
    if len(prices) < 22:
        return None
    window = prices[-21:-1]
    hi, lo = max(window), min(window)
    price = prices[-1]
    if hi <= 0:
        return None
    if price > hi * 1.001:
        return {"strategy": "Breakout & Retest", "direction": "BUY", "confidence": _clamp(0.44 + (price / hi - 1) * 20),
                "reason": "price broke above the prior 20-bar range high"}
    if price < lo * 0.999:
        return {"strategy": "Breakout & Retest", "direction": "SELL", "confidence": _clamp(0.44 + (1 - price / lo) * 20),
                "reason": "price broke below the prior 20-bar range low"}
    return None


def detect_market_structure(prices: list[float]) -> Optional[dict[str, Any]]:
    if len(prices) < MIN_BARS:
        return None
    prior_high = max(prices[-20:-1])
    prior_low = min(prices[-20:-1])
    price = prices[-1]
    if price > prior_high:
        return {"strategy": "Market Structure (BOS)", "direction": "BUY", "confidence": 0.55,
                "reason": "break of structure above the last swing high"}
    if price < prior_low:
        return {"strategy": "Market Structure (BOS)", "direction": "SELL", "confidence": 0.55,
                "reason": "break of structure below the last swing low"}
    return None


def detect_liquidity_sweep(prices: list[float]) -> Optional[dict[str, Any]]:
    if len(prices) < 15:
        return None
    ref_high = max(prices[-15:-3])
    ref_low = min(prices[-15:-3])
    spike_up = max(prices[-3:-1])
    spike_dn = min(prices[-3:-1])
    price = prices[-1]
    if spike_up > ref_high and price < ref_high:
        return {"strategy": "Liquidity Sweep", "direction": "SELL", "confidence": 0.58,
                "reason": "failed break above swing high (stop-hunt reversal)"}
    if spike_dn < ref_low and price > ref_low:
        return {"strategy": "Liquidity Sweep", "direction": "BUY", "confidence": 0.58,
                "reason": "failed break below swing low (stop-hunt reversal)"}
    return None


def detect_mean_reversion(prices: list[float]) -> Optional[dict[str, Any]]:
    if len(prices) < 25:
        return None
    window = prices[-20:]
    mean = sum(window) / len(window)
    sd = _std(window)
    if not sd or not mean:
        return None
    drift = abs(_slope(window, 10))
    if drift > 0.01:  # trending, not a range — don't fade
        return None
    z = (prices[-1] - mean) / sd
    if z >= 1.8:
        return {"strategy": "Mean Reversion", "direction": "SELL", "confidence": _clamp(0.42 + (z - 1.8) * 0.2),
                "reason": f"price {z:.1f}stdev above range mean"}
    if z <= -1.8:
        return {"strategy": "Mean Reversion", "direction": "BUY", "confidence": _clamp(0.42 + (abs(z) - 1.8) * 0.2),
                "reason": f"price {abs(z):.1f}stdev below range mean"}
    return None


def detect_support_resistance(prices: list[float]) -> Optional[dict[str, Any]]:
    if len(prices) < 30:
        return None
    window = prices[-30:]
    lo, hi = min(window), max(window)
    price = prices[-1]
    span = (hi - lo) or 1.0
    pos = (price - lo) / span
    momentum_up = prices[-1] >= prices[-2]
    if pos <= 0.08 and momentum_up:
        return {"strategy": "Support Reaction", "direction": "BUY", "confidence": 0.5,
                "reason": "price at the low of its 30-bar range with an up-move"}
    if pos >= 0.92 and not momentum_up:
        return {"strategy": "Resistance Reaction", "direction": "SELL", "confidence": 0.5,
                "reason": "price at the high of its 30-bar range with a down-move"}
    return None


DETECTORS = (
    detect_trend_following,
    detect_momentum_surge,
    detect_breakout,
    detect_market_structure,
    detect_liquidity_sweep,
    detect_mean_reversion,
    detect_support_resistance,
)


def scan(prices: list[float], min_conf: float = 0.45) -> Optional[dict[str, Any]]:
    """Return the strongest methodology candidate above `min_conf`, or None."""
    if not prices or len(prices) < MIN_BARS:
        return None
    best: Optional[dict[str, Any]] = None
    for detect in DETECTORS:
        try:
            cand = detect(prices)
        except Exception:
            cand = None
        if not cand or cand["confidence"] < min_conf:
            continue
        if best is None or cand["confidence"] > best["confidence"]:
            best = cand
    return best
