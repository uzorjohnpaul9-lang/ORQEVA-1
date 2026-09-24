"""
Base Engine - Abstract class for all market engines.
"""
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any

from .engine_config import EngineRiskParams, IndicatorConfig
from .indicators import (
    calculate_rsi, calculate_macd, calculate_bollinger,
    calculate_atr, calculate_sma, score_signal,
)

logger = logging.getLogger(__name__)


class Signal:
    """Trading signal produced by an engine."""
    def __init__(self, symbol: str, direction: str, price: float,
                 confidence: float, reason: str, target_price: float,
                 stop_loss: float, signal_type: str,
                 fees: float = 0.0, slippage: float = 0.0,
                 metadata: Optional[Dict] = None):
        self.symbol = symbol
        self.direction = direction
        self.price = price
        self.confidence = confidence
        self.reason = reason
        self.target_price = target_price
        self.stop_loss = stop_loss
        self.type = signal_type
        self.fees = fees
        self.slippage = slippage
        self.timestamp = datetime.now().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "price": self.price,
            "confidence": self.confidence,
            "reason": self.reason,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "type": self.type,
            "timestamp": self.timestamp,
            "fees": self.fees,
            "slippage": self.slippage,
        }


class BaseEngine(ABC):
    """Abstract base class for all 3 market engines."""

    @property
    @abstractmethod
    def market_type(self) -> str:
        """Return 'stock', 'forex', or 'crypto'."""

    @property
    @abstractmethod
    def risk_params(self) -> EngineRiskParams:
        """Return market-specific risk parameters."""

    @property
    @abstractmethod
    def indicator_config(self) -> IndicatorConfig:
        """Return market-specific indicator configuration."""

    @abstractmethod
    def fetch_prices(self, symbol: str, lookback: int) -> List[float]:
        """Fetch historical closing prices for a symbol."""

    @abstractmethod
    def get_symbols(self) -> List[str]:
        """Return list of symbols to scan."""

    @abstractmethod
    def is_market_hours(self) -> bool:
        """Check if this market is currently open."""

    @abstractmethod
    def calculate_fees(self, symbol: str, quantity: float, price: float) -> float:
        """Calculate trading fees for a given trade."""

    @abstractmethod
    def calculate_slippage(self, symbol: str, quantity: float, price: float) -> float:
        """Estimate slippage cost for a given trade."""

    @abstractmethod
    def calculate_position_size(self, symbol: str, price: float, account_value: float) -> float:
        """Calculate appropriate position size based on risk params."""

    def analyze(self, symbol: str) -> Optional[Signal]:
        """
        Analyze a symbol and produce a signal if criteria are met.
        Uses shared scoring logic from indicators.py.
        """
        if not self.is_market_hours():
            return None

        try:
            prices = self.fetch_prices(symbol, self.indicator_config.macd_slow + 10)
            if not prices or len(prices) < 26:
                return None

            current_price = prices[-1]
            config = self.indicator_config

            rsi = calculate_rsi(prices, config.rsi_period)
            macd = calculate_macd(prices, config.macd_fast, config.macd_slow, config.macd_signal)
            bollinger = calculate_bollinger(prices, config.bollinger_period, config.bollinger_std)
            atr = calculate_atr(prices, config.atr_period)

            result = score_signal(rsi, macd, bollinger, prices, current_price, config)

            if not result["direction"]:
                return None

            direction = result["direction"]
            confidence = result["confidence"]
            reason = " + ".join(result["reasons"])

            # Calculate target and stop loss using risk params
            rp = self.risk_params
            if direction == "BUY":
                target_price = current_price * (1 + rp.take_profit_pct)
                stop_loss = current_price * (1 - rp.stop_loss_pct)
            else:
                target_price = current_price * (1 - rp.take_profit_pct)
                stop_loss = current_price * (1 + rp.stop_loss_pct)

            # Calculate fees and slippage
            quantity = self.calculate_position_size(symbol, current_price, 100000)
            fees = self.calculate_fees(symbol, quantity, current_price)
            slippage = self.calculate_slippage(symbol, quantity, current_price)

            return Signal(
                symbol=symbol,
                direction=direction,
                price=current_price,
                confidence=confidence,
                reason=reason,
                target_price=round(target_price, 4),
                stop_loss=round(stop_loss, 4),
                signal_type=self.market_type,
                fees=fees,
                slippage=slippage,
                metadata={"rsi": rsi, "atr": atr, "macd": macd},
            )

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            return None

    def run_cycle(self, account_value: float = 100000) -> List[Signal]:
        """Run a full analysis cycle across all symbols for this engine."""
        if not self.is_market_hours():
            logger.info(f"{self.market_type} market closed, skipping cycle")
            return []

        signals = []
        for symbol in self.get_symbols():
            signal = self.analyze(symbol)
            if signal and signal.confidence >= self.indicator_config.min_signal_score:
                signals.append(signal)
                logger.info(
                    f"{self.market_type.upper()}: {signal.direction} {symbol} "
                    f"({signal.confidence:.1%}) - {signal.reason}"
                )

        signals.sort(key=lambda s: s.confidence, reverse=True)
        logger.info(f"{self.market_type} cycle: {len(signals)} signals found")
        return signals

    def calculate_net_pnl(self, signal: Signal, exit_price: float, quantity: float) -> float:
        """Calculate net P&L after fees and slippage."""
        if signal.direction == "BUY":
            gross = (exit_price - signal.price) * quantity
        else:
            gross = (signal.price - exit_price) * quantity

        total_cost = signal.fees + signal.slippage
        return gross - total_cost
