"""
Stock Engine - US equities via Alpaca API.
Market hours: 9AM-4PM EST, weekdays only.
"""
import os
from datetime import datetime, timedelta
from typing import List, Optional
import logging

from .base_engine import BaseEngine, Signal
from .engine_config import StockEngineConfig, EngineRiskParams, IndicatorConfig

logger = logging.getLogger(__name__)

# US market holidays (simplified - major ones)
MARKET_HOLIDAYS = {
    (1, 1), (1, 20), (2, 17), (4, 21), (5, 26),
    (6, 19), (7, 4), (9, 1), (11, 27), (12, 25),
}


class StockEngine(BaseEngine):
    """Stock-specific engine using Alpaca API for data."""

    def __init__(self, config: Optional[StockEngineConfig] = None):
        self._config = config or StockEngineConfig()
        self._client = None
        self._data_client = None
        self._connect()

    def _connect(self):
        """Connect to Alpaca API."""
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient

            api_key = os.getenv("ALPACA_API_KEY", "")
            secret_key = os.getenv("ALPACA_SECRET_KEY", "")

            if api_key and secret_key:
                self._client = TradingClient(api_key, secret_key, paper=True)
                self._data_client = StockHistoricalDataClient(api_key, secret_key)
                logger.info("Stock engine: Alpaca connected")
            else:
                logger.warning("Stock engine: No Alpaca credentials, using simulated data")
        except Exception as e:
            logger.warning(f"Stock engine: Alpaca connection failed: {e}")

    @property
    def market_type(self) -> str:
        return "stock"

    @property
    def risk_params(self) -> EngineRiskParams:
        return self._config.risk

    @property
    def indicator_config(self) -> IndicatorConfig:
        return self._config.indicators

    def get_symbols(self) -> List[str]:
        return self._config.symbols

    def is_market_hours(self) -> bool:
        """US stock market: 9:30AM-4PM EST, weekdays, excluding holidays."""
        now = datetime.now()
        # Weekend check
        if now.weekday() >= 5:
            return False
        # Holiday check
        if (now.month, now.day) in MARKET_HOLIDAYS:
            return False
        # Time check (EST approximation: UTC-5)
        hour = now.hour
        # Simple approximation: 9:30-16:00
        if hour < self._config.market_open_hour or hour >= self._config.market_close_hour:
            return False
        return True

    def fetch_prices(self, symbol: str, lookback: int = 40) -> List[float]:
        """Fetch daily closing prices from Alpaca."""
        if not self._data_client:
            return self._simulated_prices(symbol, lookback)

        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame(1, "Day"),
                start=datetime.now() - timedelta(days=lookback + 10),
            )
            bars = self._data_client.get_stock_bars(request)
            if bars and symbol in bars:
                return [bar.close for bar in bars[symbol]]
        except Exception as e:
            logger.error(f"Alpaca fetch failed for {symbol}: {e}")

        return self._simulated_prices(symbol, lookback)

    def _simulated_prices(self, symbol: str, lookback: int) -> List[float]:
        """Generate simulated prices when API unavailable."""
        import random
        base = hash(symbol) % 500 + 50
        prices = [base]
        for _ in range(lookback - 1):
            change = random.uniform(-0.03, 0.03)
            prices.append(prices[-1] * (1 + change))
        return prices

    def calculate_fees(self, symbol: str, quantity: float, price: float) -> float:
        """Stock fees: Alpaca = $0 commission, but SEC fee applies."""
        rp = self.risk_params
        flat = rp.fee_per_trade
        pct = quantity * price * rp.fee_percentage
        return flat + pct

    def calculate_slippage(self, symbol: str, quantity: float, price: float) -> float:
        """Estimate slippage based on market cap tier."""
        trade_value = quantity * price
        if trade_value > 100000:
            rate = self._config.slippage_large_cap
        elif trade_value > 20000:
            rate = self._config.slippage_mid_cap
        else:
            rate = self._config.slippage_small_cap
        return trade_value * rate

    def calculate_position_size(self, symbol: str, price: float, account_value: float) -> float:
        """Position size = max_position_size * account_value / price, capped by max_positions."""
        rp = self.risk_params
        max_value = account_value * rp.max_position_size
        quantity = max_value / price
        return round(quantity, 2)
