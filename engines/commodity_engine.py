"""
Commodity Engine - Metals (gold, silver) + energy (crude, nat gas) via Twelve Data.
Market hours: 24/5 (same schedule as forex).
"""
import os
import requests
from datetime import datetime
from typing import List, Optional
import logging

from .base_engine import BaseEngine, Signal
from .engine_config import CommodityEngineConfig, EngineRiskParams, IndicatorConfig, METALS, ENERGY

logger = logging.getLogger(__name__)


class CommodityEngine(BaseEngine):
    """Commodity engine using Twelve Data API."""

    def __init__(self, config: Optional[CommodityEngineConfig] = None):
        self._config = config or CommodityEngineConfig()
        self._api_key = os.getenv("TWELVE_DATA_API_KEY", "")
        self._base_url = "https://api.twelvedata.com"

    @property
    def market_type(self) -> str:
        return "commodity"

    @property
    def risk_params(self) -> EngineRiskParams:
        return self._config.risk

    @property
    def indicator_config(self) -> IndicatorConfig:
        return self._config.indicators

    def get_symbols(self) -> List[str]:
        return self._config.symbols

    def is_market_hours(self) -> bool:
        """Commodities: 24/5. Closed Saturday 5AM - Sunday 5AM (approx EST)."""
        now = datetime.now()
        if now.weekday() == 5 and now.hour >= 5:
            return False
        if now.weekday() == 6 and now.hour < 5:
            return False
        return True

    def fetch_prices(self, symbol: str, lookback: int = 30) -> List[float]:
        """Fetch daily closing prices from Twelve Data."""
        if not self._api_key:
            self._last_source = "simulated"
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
                self._last_source = "live"
                return [float(v["close"]) for v in reversed(data["values"])]
        except Exception as e:
            logger.error(f"Twelve Data fetch failed for {symbol}: {e}")

        self._last_source = "simulated"
        return self._simulated_prices(symbol, lookback)

    def _simulated_prices(self, symbol: str, lookback: int) -> List[float]:
        """Generate simulated prices when API unavailable."""
        import random
        base_prices = {
            "XAU/USD": 2400, "XAG/USD": 30, "WTI/USD": 78,
            "BRENT/USD": 82, "NATGAS/USD": 2.8,
        }
        base = base_prices.get(symbol, 100)
        prices = [base]
        for _ in range(lookback - 1):
            change = random.uniform(-0.02, 0.02)
            prices.append(prices[-1] * (1 + change))
        return prices

    def calculate_fees(self, symbol: str, quantity: float, price: float) -> float:
        """Commodity fees: spread cost + percentage."""
        rp = self.risk_params
        trade_value = quantity * price
        return rp.fee_per_trade + (trade_value * rp.fee_percentage)

    def calculate_slippage(self, symbol: str, quantity: float, price: float) -> float:
        """Slippage by bucket: metals (deep) vs energy."""
        trade_value = quantity * price
        if symbol in METALS:
            rate = self._config.slippage_metal
        else:
            rate = self._config.slippage_energy
        return trade_value * rate

    def calculate_position_size(self, symbol: str, price: float, account_value: float) -> float:
        """Position size in units of the commodity."""
        rp = self.risk_params
        max_value = account_value * rp.max_position_size
        quantity = max_value / price
        return round(quantity, 4)
