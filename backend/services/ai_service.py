"""AI analysis service: runs the trading system's AI models over live bars."""
import asyncio
import logging
from typing import Any

import numpy as np

from backend.services import market_service
from backend.middleware.cache import cache

logger = logging.getLogger(__name__)

# Representative symbols per market for the summary view
SUMMARY_SYMBOLS = {
    "stock": "SPY",
    "crypto": "BTC/USD",
    "forex": "EUR/USD",
}

MODEL_ROSTER = [
    {"name": "Market Regime Detector", "key": "regime", "description": "Classifies bull / bear / sideways / volatile regimes from trend strength and volatility.", "kind": "statistical"},
    {"name": "Momentum Decoder", "key": "momentum", "description": "Multi-horizon momentum (5/20/50 bars) with acceleration scoring.", "kind": "statistical"},
    {"name": "Confidence Scorer", "key": "confidence", "description": "Weighted composite of regime, momentum and volatility into a trade confidence.", "kind": "ensemble"},
]


def _derive_features(prices: list[float]) -> dict[str, Any]:
    """Compute volatility + trend strength from a close-price series."""
    p = np.asarray(prices, dtype=float)
    returns = np.diff(p) / p[:-1]
    volatility = float(np.std(returns)) if len(returns) > 1 else 0.0
    # Trend strength: R^2 of a linear fit on prices (0..1)
    x = np.arange(len(p))
    slope, intercept = np.polyfit(x, p, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((p - fitted) ** 2))
    ss_tot = float(np.sum((p - np.mean(p)) ** 2))
    r2 = 0.0 if ss_tot == 0 else max(0.0, 1.0 - ss_res / ss_tot)
    direction = 1 if slope > 0 else -1
    return {
        "volatility": volatility,
        "trend_strength": float(r2),
        "trend_direction": direction,
        "slope_per_bar": float(slope),
    }


def analyze_sync(market: str, symbol: str) -> dict[str, Any]:
    """Run regime/momentum/confidence models over live OHLC bars (blocking I/O)."""
    cache_key = f"ai:analysis:{market}:{symbol}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    bars_data = market_service.get_bars(market, symbol, interval="1day", outputsize=60)
    if "error" in bars_data or not bars_data.get("bars"):
        return {"error": bars_data.get("error", "bars_unavailable"), "symbol": symbol.upper(), "market": market}

    bars = bars_data["bars"]
    prices = [b["close"] for b in bars]

    # Local imports: the core package lives outside `backend`
    from ai_models.regime_detector import MarketRegimeDetector
    from ai_models.momentum_decoder import MomentumDecoder
    from ai_models.confidence_scorer import ConfidenceScorer

    features = _derive_features(prices)

    regime_result = MarketRegimeDetector().detect_regime({
        "prices": prices,
        "volatility": features["volatility"],
        "trend_strength": features["trend_strength"],
        "timestamp": bars[-1]["time"],
    })
    # Direction-aware regime label (detector itself is direction-agnostic at low strength)
    if features["trend_direction"] < 0 and regime_result["regime"] == "bull":
        regime_result["regime"] = "bear"
        regime_result["description"] = "Downtrend"
        regime_result["recommendation"] = "Favor short positions, defensive strategies"

    momentum = MomentumDecoder().calculate_momentum(np.asarray(prices))

    confidence = ConfidenceScorer().score_trade(
        technical_signals={},
        regime=regime_result["regime"],
        volume_data={},
        momentum=float(momentum.get("short_term", 0.0)) if "error" not in momentum else 0.0,
        volatility=features["volatility"],
    )

    result = {
        "symbol": symbol.upper(),
        "market": market,
        "bars_used": len(prices),
        "current_price": round(prices[-1], 6),
        "regime": {
            "regime": regime_result["regime"],
            "description": regime_result["description"],
            "confidence": round(regime_result["confidence"], 3),
            "recommendation": regime_result["recommendation"],
        },
        "momentum": {
            "overall": momentum.get("overall", "neutral"),
            "short_term_pct": round(float(momentum.get("short_term", 0.0)) * 100, 2),
            "medium_term_pct": round(float(momentum.get("medium_term", 0.0)) * 100, 2),
            "long_term_pct": round(float(momentum.get("long_term", 0.0)) * 100, 2),
            "acceleration_pct": round(float(momentum.get("acceleration", 0.0)) * 100, 2),
            "score": round(float(momentum.get("score", 0.5)), 3),
        },
        "volatility": {
            "daily_pct": round(features["volatility"] * 100, 2),
            "annualized_pct": round(features["volatility"] * 100 * np.sqrt(252), 1),
        },
        "confidence": {
            "score": round(confidence["confidence"], 3),
            "breakdown": {k: round(v, 3) for k, v in confidence["scores"].items()},
            "recommendation": confidence["recommendation"],
        },
    }
    cache.set(cache_key, result, ttl=300)
    return result


async def analyze(market: str, symbol: str) -> dict[str, Any]:
    return await asyncio.to_thread(analyze_sync, market, symbol)


async def market_summary() -> dict[str, Any]:
    """Regime + recommendation for one representative symbol per market."""

    async def one(mkt: str) -> dict[str, Any]:
        try:
            res = await analyze(mkt, SUMMARY_SYMBOLS[mkt])
        except Exception as e:
            logger.error(f"AI summary failed for {mkt}: {e}")
            res = {"error": "analysis_failed"}
        return {"market": mkt, **res}

    entries = await asyncio.gather(*(one(m) for m in SUMMARY_SYMBOLS))
    return {"markets": list(entries), "models": MODEL_ROSTER}
