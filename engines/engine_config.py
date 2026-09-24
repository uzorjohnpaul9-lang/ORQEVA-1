"""
Engine Configuration - Per-market risk parameters, fee models, and strategy configs.
"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class EngineRiskParams:
    """Risk parameters for a single market engine."""
    max_position_size: float       # Max % of capital per single trade
    max_daily_trades: int          # Max trades per day for this market
    max_positions: int             # Max concurrent open positions in this market
    stop_loss_pct: float           # Default stop loss %
    take_profit_pct: float         # Default take profit %
    trailing_stop_pct: float       # Trailing stop %
    max_spread_pct: float          # Max allowed spread before rejecting (slippage filter)
    fee_per_trade: float           # Flat fee per trade ($)
    fee_percentage: float          # Percentage fee per trade (e.g., 0.001 = 0.1%)


@dataclass
class IndicatorConfig:
    """Technical indicator parameters - tuned per market."""
    rsi_period: int = 14
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    atr_period: int = 14
    momentum_period: int = 5
    # Scoring weights
    rsi_weight: float = 0.25
    macd_weight: float = 0.20
    bollinger_weight: float = 0.20
    trend_weight: float = 0.15
    momentum_weight: float = 0.10
    # Min score to emit signal
    min_signal_score: float = 0.40
    # Market-specific tolerances (overridden per engine)
    bollinger_tolerance_high: float = 1.03
    bollinger_tolerance_low: float = 0.97
    momentum_threshold: float = 0.02


@dataclass
class StockEngineConfig:
    """Configuration for the stock engine."""
    symbols: List[str] = field(default_factory=lambda: [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
        "TSLA", "META", "JPM", "V", "UNH",
        "XOM", "JNJ", "WMT", "PG", "MA",
        "HD", "CVX", "MRK", "ABBV", "LLY",
    ])
    market_open_hour: int = 9       # EST
    market_close_hour: int = 16     # EST
    min_confidence: float = 0.50
    lookback_days: int = 40
    indicators: IndicatorConfig = field(default_factory=lambda: IndicatorConfig(
        rsi_period=14, rsi_oversold=35, rsi_overbought=65,
        macd_fast=12, macd_slow=26, macd_signal=9,
        bollinger_period=20, bollinger_std=2.0,
        momentum_period=5, min_signal_score=0.45,
    ))
    risk: EngineRiskParams = field(default_factory=lambda: EngineRiskParams(
        max_position_size=0.10,     # 10% per stock
        max_daily_trades=10,
        max_positions=5,
        stop_loss_pct=0.03,         # 3%
        take_profit_pct=0.05,       # 5%
        trailing_stop_pct=0.02,     # 2%
        max_spread_pct=0.001,       # 0.1%
        fee_per_trade=0.0,          # Alpaca: $0 commission
        fee_percentage=0.0005,      # SEC fee estimate
    ))
    # Slippage model
    slippage_large_cap: float = 0.0001    # 0.01%
    slippage_mid_cap: float = 0.0005      # 0.05%
    slippage_small_cap: float = 0.001     # 0.1%


@dataclass
class ForexEngineConfig:
    """Configuration for the forex engine."""
    pairs: List[str] = field(default_factory=lambda: [
        "EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF",
        "AUD/USD", "USD/CAD", "NZD/USD",
    ])
    market_open_hour: int = 0       # 24/5
    market_close_hour: int = 24
    min_confidence: float = 0.50
    lookback_days: int = 30
    pip_value: float = 0.0001       # Standard pip (0.0001 for most, 0.01 for JPY)
    jpy_pip_value: float = 0.01
    indicators: IndicatorConfig = field(default_factory=lambda: IndicatorConfig(
        rsi_period=14, rsi_oversold=35, rsi_overbought=65,
        macd_fast=12, macd_slow=26, macd_signal=9,
        bollinger_period=20, bollinger_std=2.0,
        momentum_period=5, min_signal_score=0.40,
        # Forex uses tighter Bollinger tolerance
        bollinger_tolerance_high=1.001,   # 0.1%
        bollinger_tolerance_low=0.999,
        momentum_threshold=0.002,         # 0.2%
    ))
    risk: EngineRiskParams = field(default_factory=lambda: EngineRiskParams(
        max_position_size=0.05,     # 5% per forex position
        max_daily_trades=15,
        max_positions=3,
        stop_loss_pct=0.005,        # 0.5% (tight)
        take_profit_pct=0.01,       # 1%
        trailing_stop_pct=0.003,    # 0.3%
        max_spread_pct=0.002,       # 0.2%
        fee_per_trade=0.0,
        fee_percentage=0.0001,      # Spread cost estimate
    ))
    # Slippage model (in pips)
    slippage_major: float = 0.5     # EUR/USD, GBP/USD
    slippage_minor: float = 2.0     # USD/CAD, AUD/USD
    slippage_exotic: float = 5.0    # Exotic pairs


@dataclass
class CryptoEngineConfig:
    """Configuration for the crypto engine."""
    pairs: List[str] = field(default_factory=lambda: [
        "BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD",
        "XRP/USD", "ADA/USD", "DOGE/USD", "AVAX/USD",
    ])
    market_open_hour: int = 0       # 24/7
    market_close_hour: int = 24
    min_confidence: float = 0.50
    lookback_days: int = 30
    indicators: IndicatorConfig = field(default_factory=lambda: IndicatorConfig(
        rsi_period=14, rsi_oversold=35, rsi_overbought=65,
        macd_fast=12, macd_slow=26, macd_signal=9,
        bollinger_period=20, bollinger_std=2.0,
        momentum_period=5, min_signal_score=0.40,
        # Crypto uses wider tolerance (volatile market)
        bollinger_tolerance_high=1.02,    # 2%
        bollinger_tolerance_low=0.98,
        momentum_threshold=0.03,          # 3%
    ))
    risk: EngineRiskParams = field(default_factory=lambda: EngineRiskParams(
        max_position_size=0.05,     # 5% per crypto position
        max_daily_trades=20,
        max_positions=4,
        stop_loss_pct=0.05,         # 5% (wider for volatility)
        take_profit_pct=0.10,       # 10%
        trailing_stop_pct=0.04,     # 4%
        max_spread_pct=0.01,        # 1%
        fee_per_trade=0.0,
        fee_percentage=0.001,       # Binance taker fee 0.1%
    ))
    # Slippage model
    slippage_btc_eth: float = 0.0001     # 0.01%
    slippage_large_cap: float = 0.001    # 0.1% (SOL, BNB)
    slippage_small_cap: float = 0.005    # 0.5% (low-volume alts)


# Major pair groupings for slippage
MAJOR_PAIRS = {"EUR/USD", "GBP/USD", "USD/JPY"}
MINOR_PAIRS = {"USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD"}
LARGE_CRYPTO = {"BTC/USD", "ETH/USD"}
MID_CRYPTO = {"SOL/USD", "BNB/USD", "XRP/USD"}
# Everything else = small cap crypto
