"""
Crypto Alt Engine - Memecoins + hot/trending alts via keyless exchange data.

Market type is "crypto" (VIP tier) so it reuses the existing crypto market
value end-to-end; signals are tagged with a category ("Meme Momentum" or
"Alt Momentum") for clarity. Data chain: keyless exchanges -> Twelve Data ->
simulated (last resort). Market hours: 24/7/365.
"""
import os
import requests
from typing import List, Optional
import logging

from .base_engine import BaseEngine, Signal
from .engine_config import (
    CryptoAltEngineConfig, EngineRiskParams, IndicatorConfig,
    MEME_COINS, HOT_COINS,
)

logger = logging.getLogger(__name__)


class CryptoAltEngine(BaseEngine):
    """Memecoin + hot-alt engine using keyless exchange data."""

    def __init__(self, config: Optional[CryptoAltEngineConfig] = None):
        self._config = config or CryptoAltEngineConfig()
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
        return self._config.symbols

    def is_market_hours(self) -> bool:
        """Crypto: 24/7/365, never closed."""
        return True

    @staticmethod
    def category(symbol: str) -> str:
        """Signal strategy tag for a symbol based on its bucket."""
        if symbol in MEME_COINS:
            return "Meme Momentum"
        if symbol in HOT_COINS:
            return "Alt Momentum"
        return "Alt Momentum"

    def fetch_prices(self, symbol: str, lookback: int = 30) -> List[float]:
        """Daily closing prices: keyless exchange data -> Twelve Data -> simulated."""
        from .exchange_data import fetch_prices as exchange_prices

        try:
            prices = exchange_prices(symbol, lookback, "1day")
            if len(prices) >= 2:
                self._last_source = "live"
                return prices
        except Exception as e:
            logger.error(f"Exchange data fetch failed for {symbol}: {e}")

        if self._api_key:
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

    def analyze(self, symbol: str) -> Optional[Signal]:
        """Indicator signal, tagged with the symbol's category."""
        signal = super().analyze(symbol)
        if signal is not None:
            signal.metadata.setdefault("strategy", self.category(symbol))
        return signal

    def analyze_strategy(self, symbol: str) -> Optional[Signal]:
        """Methodology signal, tagged with the symbol's category."""
        signal = super().analyze_strategy(symbol)
        if signal is not None:
            signal.metadata.setdefault("category", self.category(symbol))
        return signal

    def _simulated_prices(self, symbol: str, lookback: int) -> List[float]:
        """Generate simulated prices when no data source is reachable."""
        import random
        base_prices = {
            "DOGE/USD": 0.12, "SHIB/USD": 0.00002, "PEPE/USD": 0.00001,
            "BONK/USD": 0.00002, "FLOKI/USD": 0.0002, "WIF/USD": 2.0,
            "TRUMP/USD": 10.0, "FARTCOIN/USD": 1.0, "PENGU/USD": 0.03,
            "SOL/USD": 150, "AVAX/USD": 35, "LINK/USD": 15, "NEAR/USD": 5,
            "SUI/USD": 3, "SEI/USD": 0.4, "TIA/USD": 6, "INJ/USD": 20,
            "ARB/USD": 1.0, "OP/USD": 2.0, "APT/USD": 8, "TRX/USD": 0.12,
            "LTC/USD": 85, "DOT/USD": 6, "ATOM/USD": 8, "UNI/USD": 8,
            "AAVE/USD": 150,
        }
        base = base_prices.get(symbol, 1.0)
        prices = [base]
        for _ in range(lookback - 1):
            change = random.uniform(-0.08, 0.08)
            prices.append(prices[-1] * (1 + change))
        return prices

    def calculate_fees(self, symbol: str, quantity: float, price: float) -> float:
        """Crypto fees: Binance taker fee 0.1%."""
        rp = self.risk_params
        trade_value = quantity * price
        return rp.fee_per_trade + (trade_value * rp.fee_percentage)

    def calculate_slippage(self, symbol: str, quantity: float, price: float) -> float:
        """Slippage by bucket: memecoins worst, established alts best."""
        trade_value = quantity * price
        if symbol in MEME_COINS:
            rate = self._config.slippage_meme
        elif symbol in HOT_COINS:
            rate = self._config.slippage_hot
        else:
            rate = self._config.slippage_alt
        return trade_value * rate

    def calculate_position_size(self, symbol: str, price: float, account_value: float) -> float:
        """Position size in units of crypto."""
        rp = self.risk_params
        max_value = account_value * rp.max_position_size
        quantity = max_value / price
        if price > 1000:
            return round(quantity, 6)
        elif price > 1:
            return round(quantity, 4)
        elif price > 0.001:
            return round(quantity, 4)
        else:
            return round(quantity, 2)
