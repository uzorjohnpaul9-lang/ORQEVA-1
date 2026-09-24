"""
Crypto Engine - Major crypto pairs via Twelve Data API.
Market hours: 24/7/365.
"""
import os
import requests
from datetime import datetime
from typing import List, Optional
import logging

from .base_engine import BaseEngine, Signal
from .engine_config import CryptoEngineConfig, EngineRiskParams, IndicatorConfig, LARGE_CRYPTO, MID_CRYPTO

logger = logging.getLogger(__name__)


class CryptoEngine(BaseEngine):
    """Crypto engine using Twelve Data API."""

    def __init__(self, config: Optional[CryptoEngineConfig] = None):
        self._config = config or CryptoEngineConfig()
        self._api_key = os.getenv("TWELVE_DATA_API_KEY", "")
        self._base_url = "https://api.twelvedata.com"

    @property
    def market_type(self) -> str:
        return "crypto"

    @property
    def risk_params(self) -> EngineRiskParams:
        return self._config.risk

    @property
    def indicator_config(self) -> IndicatorConfig:
        return self._config.indicators

    def get_symbols(self) -> List[str]:
        return self._config.pairs

    def is_market_hours(self) -> bool:
        """Crypto: 24/7/365, never closed."""
        return True

    def fetch_prices(self, symbol: str, lookback: int = 30) -> List[float]:
        """Fetch daily closing prices from Twelve Data."""
        if not self._api_key:
            return self._simulated_prices(symbol, lookback)

        try:
            url = f"{self._base_url}/time_series"
            params = {
                "symbol": symbol,
                "interval": "1day",
                "outputsize": lookback,
                "apikey": self._api_key,
            }
            r = requests.get(url, params=params, timeout=15)
            data = r.json()

            if "values" in data:
                return [float(v["close"]) for v in reversed(data["values"])]
        except Exception as e:
            logger.error(f"Twelve Data fetch failed for {symbol}: {e}")

        return self._simulated_prices(symbol, lookback)

    def _simulated_prices(self, symbol: str, lookback: int) -> List[float]:
        """Generate simulated prices when API unavailable."""
        import random
        # More realistic base prices for crypto
        base_prices = {
            "BTC/USD": 70000, "ETH/USD": 3500, "SOL/USD": 150,
            "BNB/USD": 600, "XRP/USD": 0.6, "ADA/USD": 0.45,
            "DOGE/USD": 0.12, "AVAX/USD": 35,
        }
        base = base_prices.get(symbol, 100)
        prices = [base]
        for _ in range(lookback - 1):
            change = random.uniform(-0.05, 0.05)
            prices.append(prices[-1] * (1 + change))
        return prices

    def calculate_fees(self, symbol: str, quantity: float, price: float) -> float:
        """Crypto fees: Binance taker fee 0.1%."""
        rp = self.risk_params
        trade_value = quantity * price
        return rp.fee_per_trade + (trade_value * rp.fee_percentage)

    def calculate_slippage(self, symbol: str, quantity: float, price: float) -> float:
        """Estimate slippage based on crypto liquidity tier."""
        trade_value = quantity * price

        if symbol in LARGE_CRYPTO:
            rate = self._config.slippage_btc_eth
        elif symbol in MID_CRYPTO:
            rate = self._config.slippage_large_cap
        else:
            rate = self._config.slippage_small_cap

        return trade_value * rate

    def calculate_position_size(self, symbol: str, price: float, account_value: float) -> float:
        """Position size in units of crypto."""
        rp = self.risk_params
        max_value = account_value * rp.max_position_size
        quantity = max_value / price
        # Round to appropriate precision
        if price > 1000:
            return round(quantity, 6)
        elif price > 1:
            return round(quantity, 4)
        else:
            return round(quantity, 2)
