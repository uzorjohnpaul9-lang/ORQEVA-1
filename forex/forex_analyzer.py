"""
Forex Analysis Module
Uses Twelve Data API for forex signals.
"""
import os
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Major forex pairs
FOREX_PAIRS = [
    "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
    "AUD/USD", "USD/CAD", "NZD/USD"
]

# API key
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")


class ForexAnalyzer:
    """Analyze forex pairs and generate signals."""

    def __init__(self):
        self.api_key = TWELVE_DATA_API_KEY
        self.base_url = "https://api.twelvedata.com"

    def get_forex_data(self, symbol: str, interval: str = "1day", outputsize: int = 30) -> Optional[Dict]:
        """Get forex data from Twelve Data."""
        if not self.api_key:
            return None

        try:
            url = f"{self.base_url}/time_series"
            params = {
                "symbol": symbol,
                "interval": interval,
                "outputsize": outputsize,
                "apikey": self.api_key
            }

            r = requests.get(url, params=params, timeout=15)
            data = r.json()

            if "values" in data:
                values = data["values"]
                prices = [float(v["close"]) for v in reversed(values)]
                volumes = [float(v.get("volume", 0)) for v in reversed(values)]

                return {
                    "symbol": symbol,
                    "prices": prices,
                    "volumes": volumes,
                    "current_price": prices[-1] if prices else 0,
                    "high": max(prices) if prices else 0,
                    "low": min(prices) if prices else 0,
                }
            else:
                return None

        except Exception as e:
            return None

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI."""
        if len(prices) < period + 1:
            return 50.0

        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        """Calculate MACD."""
        if len(prices) < 26:
            return {"macd": 0, "signal": 0, "histogram": 0}

        ema12 = sum(prices[-12:]) / 12
        ema26 = sum(prices[-26:]) / 26

        macd = ema12 - ema26
        signal = sum(prices[-9:]) / 9

        return {
            "macd": macd,
            "signal": signal,
            "histogram": macd - signal
        }

    def calculate_bollinger(self, prices: List[float], period: int = 20) -> Dict[str, float]:
        """Calculate Bollinger Bands."""
        if len(prices) < period:
            return {"upper": 0, "middle": 0, "lower": 0}

        recent = prices[-period:]
        middle = sum(recent) / period

        variance = sum((p - middle) ** 2 for p in recent) / period
        std_dev = variance ** 0.5

        return {
            "upper": middle + (2 * std_dev),
            "middle": middle,
            "lower": middle - (2 * std_dev),
        }

    def analyze_pair(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Analyze a forex pair and return signal if found."""
        data = self.get_forex_data(symbol)

        if not data or len(data["prices"]) < 26:
            return None

        prices = data["prices"]
        current = data["current_price"]

        # Calculate indicators
        rsi = self.calculate_rsi(prices)
        macd = self.calculate_macd(prices)
        bollinger = self.calculate_bollinger(prices)

        # Calculate trend
        sma20 = sum(prices[-20:]) / 20
        sma5 = sum(prices[-5:]) / 5
        trend = "up" if sma5 > sma20 else "down"

        # Count signals
        bullish_score = 0
        bullish_reasons = []
        bearish_score = 0
        bearish_reasons = []

        # RSI signals
        if rsi < 35:
            bullish_score += 0.25
            bullish_reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > 65:
            bearish_score += 0.25
            bearish_reasons.append(f"RSI overbought ({rsi:.0f})")

        # MACD signals
        if macd["histogram"] > 0:
            bullish_score += 0.2
            bullish_reasons.append("MACD bullish")
        elif macd["histogram"] < 0:
            bearish_score += 0.2
            bearish_reasons.append("MACD bearish")

        # Bollinger signals
        if current <= bollinger["lower"] * 1.001:
            bullish_score += 0.2
            bullish_reasons.append("Near lower Bollinger")
        elif current >= bollinger["upper"] * 0.999:
            bearish_score += 0.2
            bearish_reasons.append("Near upper Bollinger")

        # Trend signals
        if trend == "up":
            bullish_score += 0.15
            bullish_reasons.append("Uptrend")
        else:
            bearish_score += 0.15
            bearish_reasons.append("Downtrend")

        # Momentum
        if len(prices) >= 5:
            change_5d = (prices[-1] - prices[-5]) / prices[-5]
            if change_5d > 0.002:
                bullish_score += 0.1
                bullish_reasons.append(f"+{change_5d:.2%} momentum")
            elif change_5d < -0.002:
                bearish_score += 0.1
                bearish_reasons.append(f"{change_5d:.2%} momentum")

        # Generate signal
        min_score = 0.45

        if bullish_score >= min_score and bullish_score > bearish_score:
            confidence = min(bullish_score, 0.95)
            pip_value = 0.0001 if "JPY" not in symbol else 0.01
            target = current + (pip_value * 50)
            stop_loss = current - (pip_value * 25)

            return {
                "symbol": symbol,
                "direction": "BUY",
                "price": current,
                "confidence": confidence,
                "reason": " + ".join(bullish_reasons),
                "target_price": round(target, 4),
                "stop_loss": round(stop_loss, 4),
                "rsi": round(rsi, 2),
                "type": "forex",
                "timestamp": datetime.now().isoformat(),
            }

        elif bearish_score >= min_score and bearish_score > bullish_score:
            confidence = min(bearish_score, 0.95)
            pip_value = 0.0001 if "JPY" not in symbol else 0.01
            target = current - (pip_value * 50)
            stop_loss = current + (pip_value * 25)

            return {
                "symbol": symbol,
                "direction": "SELL",
                "price": current,
                "confidence": confidence,
                "reason": " + ".join(bearish_reasons),
                "target_price": round(target, 4),
                "stop_loss": round(stop_loss, 4),
                "rsi": round(rsi, 2),
                "type": "forex",
                "timestamp": datetime.now().isoformat(),
            }

        return None

    def analyze_all(self) -> List[Dict[str, Any]]:
        """Analyze all forex pairs."""
        signals = []

        for pair in FOREX_PAIRS:
            signal = self.analyze_pair(pair)
            if signal:
                signals.append(signal)

        return signals
