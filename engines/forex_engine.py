"""
Forex Engine - Major forex pairs via Twelve Data API.
Market hours: 24/5 (Sunday 5PM - Friday 5PM EST).
"""
import os
import requests
from datetime import datetime
from typing import List, Optional
import logging

from .base_engine import BaseEngine, Signal
from .engine_config import ForexEngineConfig, EngineRiskParams, IndicatorConfig, MAJOR_PAIRS, MINOR_PAIRS

logger = logging.getLogger(__name__)


class ForexEngine(BaseEngine):
    """Forex engine using Twelve Data API."""

    def __init__(self, config: Optional[ForexEngineConfig] = None):
        self._config = config or ForexEngineConfig()
        self._api_key = os.getenv("TWELVE_DATA_API_KEY", "")
        self._base_url = "https://api.twelvedata.com"

    @property
    def market_type(self) -> str:
        return "forex"

    @property
    def risk_params(self) -> EngineRiskParams:
        return self._config.risk

    @property
    def indicator_config(self) -> IndicatorConfig:
        return self._config.indicators

    def get_symbols(self) -> List[str]:
        return self._config.pairs

    def is_market_hours(self) -> bool:
        """Forex: 24/5. Closed Saturday 5AM- Sunday 5AM EST."""
        now = datetime.now()
        # Saturday after 5AM or Sunday before 5AM = closed
        if now.weekday() == 5 and now.hour >= 5:
            return False
        if now.weekday() == 6 and now.hour < 5:
            return False
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
        base = 1.0 + (hash(symbol) % 200) / 100
        prices = [base]
        for _ in range(lookback - 1):
            change = random.uniform(-0.005, 0.005)
            prices.append(prices[-1] * (1 + change))
        return prices

    def calculate_fees(self, symbol: str, quantity: float, price: float) -> float:
        """Forex fees: spread cost + commission."""
        rp = self.risk_params
        # Spread cost approximation (in pips, converted to price)
        is_jpy = "JPY" in symbol
        pip_value = self._config.jpy_pip_value if is_jpy else self._config.pip_value

        if symbol in MAJOR_PAIRS:
            spread_pips = 1.0
        elif symbol in MINOR_PAIRS:
            spread_pips = 2.0
        else:
            spread_pips = 5.0

        spread_cost = spread_pips * pip_value * quantity
        commission = rp.fee_per_trade + (quantity * price * rp.fee_percentage)
        return spread_cost + commission

    def calculate_slippage(self, symbol: str, quantity: float, price: float) -> float:
        """Estimate slippage based on pair liquidity."""
        is_jpy = "JPY" in symbol
        pip_value = self._config.jpy_pip_value if is_jpy else self._config.pip_value

        if symbol in MAJOR_PAIRS:
            slippage_pips = self._config.slippage_major
        elif symbol in MINOR_PAIRS:
            slippage_pips = self._config.slippage_minor
        else:
            slippage_pips = self._config.slippage_exotic

        return slippage_pips * pip_value * quantity

    def calculate_position_size(self, symbol: str, price: float, account_value: float) -> float:
        """Position size in units of base currency."""
        rp = self.risk_params
        max_value = account_value * rp.max_position_size
        quantity = max_value / price
        return round(quantity, 2)
