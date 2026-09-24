"""
Crypto Analysis Module
Uses Twelve Data API for crypto signals.
"""
import os
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Top crypto pairs
CRYPTO_PAIRS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD",
    "XRP/USD", "ADA/USD", "DOGE/USD", "AVAX/USD"
]

TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")


class CryptoAnalyzer:
    """Analyze crypto pairs and generate signals."""

    def __init__(self):
        self.api_key = TWELVE_DATA_API_KEY
        self.base_url = "https://api.twelvedata.com"

    def get_crypto_data(self, symbol: str, interval: str = "1day", outputsize: int = 30) -> Optional[Dict]:
        """Get crypto data from Twelve Data."""
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

                return {
                    "symbol": symbol,
                    "prices": prices,
                    "current_price": prices[-1] if prices else 0,
                    "high": max(prices) if prices else 0,
                    "low": min(prices) if prices else 0,
                }
            return None

        except Exception as e:
            return None

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
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
        return 100 - (100 / (1 + rs))

    def calculate_macd(self, prices: List[float]) -> Dict[str, float]:
        if len(prices) < 26:
            return {"macd": 0, "signal": 0, "histogram": 0}
        ema12 = sum(prices[-12:]) / 12
        ema26 = sum(prices[-26:]) / 26
        macd = ema12 - ema26
        signal = sum(prices[-9:]) / 9
        return {"macd": macd, "signal": signal, "histogram": macd - signal}

    def calculate_bollinger(self, prices: List[float], period: int = 20) -> Dict[str, float]:
        if len(prices) < period:
            return {"upper": 0, "middle": 0, "lower": 0}
        recent = prices[-period:]
        middle = sum(recent) / period
        variance = sum((p - middle) ** 2 for p in recent) / period
        std_dev = variance ** 0.5
        return {"upper": middle + (2 * std_dev), "middle": middle, "lower": middle - (2 * std_dev)}

    def analyze_pair(self, symbol: str) -> Optional[Dict[str, Any]]:
        data = self.get_crypto_data(symbol)
        if not data or len(data["prices"]) < 26:
            return None

        prices = data["prices"]
        current = data["current_price"]

        rsi = self.calculate_rsi(prices)
        macd = self.calculate_macd(prices)
        bollinger = self.calculate_bollinger(prices)

        sma20 = sum(prices[-20:]) / 20
        sma5 = sum(prices[-5:]) / 5
        trend = "up" if sma5 > sma20 else "down"

        bullish_score = 0
        bullish_reasons = []
        bearish_score = 0
        bearish_reasons = []

        if rsi < 35:
            bullish_score += 0.25
            bullish_reasons.append(f"RSI oversold ({rsi:.0f})")
        elif rsi > 65:
            bearish_score += 0.25
            bearish_reasons.append(f"RSI overbought ({rsi:.0f})")

        if macd["histogram"] > 0:
            bullish_score += 0.2
            bullish_reasons.append("MACD bullish")
        elif macd["histogram"] < 0:
            bearish_score += 0.2
            bearish_reasons.append("MACD bearish")

        if current <= bollinger["lower"] * 1.02:
            bullish_score += 0.2
            bullish_reasons.append("Near lower Bollinger")
        elif current >= bollinger["upper"] * 0.98:
            bearish_score += 0.2
            bearish_reasons.append("Near upper Bollinger")

        if trend == "up":
            bullish_score += 0.15
            bullish_reasons.append("Uptrend")
        else:
            bearish_score += 0.15
            bearish_reasons.append("Downtrend")

        if len(prices) >= 5:
            change_5d = (prices[-1] - prices[-5]) / prices[-5]
            if change_5d > 0.03:
                bullish_score += 0.1
                bullish_reasons.append(f"+{change_5d:.1%} momentum")
            elif change_5d < -0.03:
                bearish_score += 0.1
                bearish_reasons.append(f"{change_5d:.1%} momentum")

        min_score = 0.45

        if bullish_score >= min_score and bullish_score > bearish_score:
            confidence = min(bullish_score, 0.95)
            target = current * 1.05
            stop_loss = current * 0.97
            return {
                "symbol": symbol, "direction": "BUY", "price": current,
                "confidence": confidence, "reason": " + ".join(bullish_reasons),
                "target_price": round(target, 4), "stop_loss": round(stop_loss, 4),
                "type": "crypto", "timestamp": datetime.now().isoformat(),
            }
        elif bearish_score >= min_score and bearish_score > bullish_score:
            confidence = min(bearish_score, 0.95)
            target = current * 0.95
            stop_loss = current * 1.03
            return {
                "symbol": symbol, "direction": "SELL", "price": current,
                "confidence": confidence, "reason": " + ".join(bearish_reasons),
                "target_price": round(target, 4), "stop_loss": round(stop_loss, 4),
                "type": "crypto", "timestamp": datetime.now().isoformat(),
            }

        return None

    def analyze_all(self) -> List[Dict[str, Any]]:
        signals = []
        for pair in CRYPTO_PAIRS:
            signal = self.analyze_pair(pair)
            if signal:
                signals.append(signal)
        return signals
