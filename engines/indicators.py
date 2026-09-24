"""
Shared Technical Indicators - Single implementation used by all 3 engines.
Replaces the copy-pasted RSI/MACD/Bollinger in live_engine, forex_analyzer, crypto_analyzer.
"""
from typing import List, Dict, Optional
from .engine_config import IndicatorConfig


def calculate_rsi(prices: List[float], period: int = 14) -> float:
    """Relative Strength Index. Returns 0-100."""
    if len(prices) < period + 1:
        return 50.0
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
    """MACD line, signal line, histogram. SMA-based for simplicity."""
    if len(prices) < slow:
        return {"macd": 0, "signal": 0, "histogram": 0}
    ema_fast = sum(prices[-fast:]) / fast
    ema_slow = sum(prices[-slow:]) / slow
    macd_line = ema_fast - ema_slow
    signal_line = sum(prices[-signal:]) / signal if len(prices) >= signal else macd_line
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": macd_line - signal_line,
    }


def calculate_bollinger(prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, float]:
    """Bollinger Bands: upper, middle, lower."""
    if len(prices) < period:
        return {"upper": 0, "middle": 0, "lower": 0}
    recent = prices[-period:]
    middle = sum(recent) / period
    variance = sum((p - middle) ** 2 for p in recent) / period
    std = variance ** 0.5
    return {
        "upper": middle + (std_dev * std),
        "middle": middle,
        "lower": middle - (std_dev * std),
    }


def calculate_atr(prices: List[float], period: int = 14) -> float:
    """Average True Range (simplified: high-low range)."""
    if len(prices) < period + 1:
        return 0.0
    ranges = [abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))]
    return sum(ranges[-period:]) / period


def calculate_sma(prices: List[float], period: int) -> float:
    """Simple Moving Average."""
    if len(prices) < period:
        return sum(prices) / len(prices) if prices else 0.0
    return sum(prices[-period:]) / period


def score_signal(
    rsi: float,
    macd: Dict[str, float],
    bollinger: Dict[str, float],
    prices: List[float],
    current_price: float,
    config: IndicatorConfig,
) -> Dict[str, float]:
    """
    Score a signal as bullish or bearish using configurable weights.
    Returns {direction, bullish_score, bearish_score, confidence, reasons}.
    """
    bullish_score = 0.0
    bullish_reasons = []
    bearish_score = 0.0
    bearish_reasons = []

    # RSI
    if rsi < config.rsi_oversold:
        bullish_score += config.rsi_weight
        bullish_reasons.append(f"RSI oversold ({rsi:.0f})")
    elif rsi > config.rsi_overbought:
        bearish_score += config.rsi_weight
        bearish_reasons.append(f"RSI overbought ({rsi:.0f})")

    # MACD
    if macd["histogram"] > 0:
        bullish_score += config.macd_weight
        bullish_reasons.append("MACD bullish")
    elif macd["histogram"] < 0:
        bearish_score += config.macd_weight
        bearish_reasons.append("MACD bearish")

    # Bollinger Bands
    tol_high = getattr(config, "bollinger_tolerance_high", 1.03)
    tol_low = getattr(config, "bollinger_tolerance_low", 0.97)
    if bollinger["lower"] > 0 and current_price <= bollinger["lower"] * tol_high:
        bullish_score += config.bollinger_weight
        bullish_reasons.append("Near lower Bollinger")
    elif bollinger["upper"] > 0 and current_price >= bollinger["upper"] * tol_low:
        bearish_score += config.bollinger_weight
        bearish_reasons.append("Near upper Bollinger")

    # Trend (SMA crossover)
    if len(prices) >= 20:
        sma5 = calculate_sma(prices, 5)
        sma20 = calculate_sma(prices, 20)
        if sma5 > sma20:
            bullish_score += config.trend_weight
            bullish_reasons.append("Uptrend (SMA5 > SMA20)")
        else:
            bearish_score += config.trend_weight
            bearish_reasons.append("Downtrend (SMA5 < SMA20)")

    # Momentum
    momentum_threshold = getattr(config, "momentum_threshold", 0.02)
    if len(prices) >= config.momentum_period + 1:
        change = (prices[-1] - prices[-(config.momentum_period + 1)]) / prices[-(config.momentum_period + 1)]
        if change > momentum_threshold:
            bullish_score += config.momentum_weight
            bullish_reasons.append(f"+{change:.1%} momentum")
        elif change < -momentum_threshold:
            bearish_score += config.momentum_weight
            bearish_reasons.append(f"{change:.1%} momentum")

    # Determine direction
    if bullish_score > bearish_score and bullish_score >= config.min_signal_score:
        return {
            "direction": "BUY",
            "confidence": min(bullish_score, 0.95),
            "reasons": bullish_reasons,
        }
    elif bearish_score > bullish_score and bearish_score >= config.min_signal_score:
        return {
            "direction": "SELL",
            "confidence": min(bearish_score, 0.95),
            "reasons": bearish_reasons,
        }

    return {"direction": None, "confidence": 0.0, "reasons": []}
