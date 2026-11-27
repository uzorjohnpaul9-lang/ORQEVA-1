"""Fast-lane engine for 1m/5m scalp signals.

The daily engines answer "what is the multi-day trend?"; this engine answers
"is there a tradable move in the next 5-60 minutes?". It shares the indicator
math and level validation with the other engines, but sizes targets from ATR
and refuses setups whose take-profit would not clear estimated costs.

Signals produced here are tagged very_short/short and are VIP-only by the
term config. Auto-trade treats them as paper-only.
"""
from __future__ import annotations

import logging
import os
from dataclasses import replace
from datetime import datetime
from typing import Any

from .base_engine import BaseEngine, Signal
from .engine_config import (
    CommodityEngineConfig, CryptoEngineConfig, EngineRiskParams,
    ForexEngineConfig, IndicatorConfig,
)
from .indicators import (
    calculate_bollinger, calculate_ema, calculate_macd,
    calculate_rsi, score_signal,
)
from .price_levels import round_price

logger = logging.getLogger(__name__)

_MARKET_CONFIG = {
    "crypto": CryptoEngineConfig,
    "forex": ForexEngineConfig,
    "commodity": CommodityEngineConfig,
}

# Estimated round-trip cost as a fraction of notional. These are deliberately
# conservative: a scalp that cannot clear them is not worth publishing.
_COST_PCT = {"crypto": 0.0007, "forex": 0.00012, "commodity": 0.0002}
_COST_MULTIPLE = float(os.getenv("FAST_COST_MULTIPLE", "1.5"))

# Take-profit / stop-loss distance in ATR units. Short-term bars are noisier,
# so the stop is wider than the target's ATR multiple in risk terms.
_TP_ATR = {"very_short": 1.3, "short": 1.9}
_SL_ATR = {"very_short": 1.0, "short": 1.2}


def _atr_from_bars(bars: list[dict], period: int = 14) -> float:
    if len(bars) < period + 1:
        return 0.0
    ranges = []
    for prev, cur in zip(bars[-period - 1:-1], bars[-period:]):
        high = float(cur.get("high") or 0)
        low = float(cur.get("low") or 0)
        prev_close = float(prev.get("close") or 0)
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(ranges) / len(ranges) if ranges else 0.0


class IntradayEngine(BaseEngine):
    """One engine instance covers one market and one term."""

    def __init__(self, market: str, symbols: list[str], term: str):
        from backend.services import signal_terms

        self._market_type = market if market in _MARKET_CONFIG else "crypto"
        self._symbols = list(symbols)
        self._term = signal_terms.normalize_term(term)
        self._term_cfg = signal_terms.get(self._term)
        self._config = _MARKET_CONFIG[self._market_type]()
        self._last_source: str | None = None

        # Shorter indicator windows suit 1m/5m data; the daily config would
        # barely move inside a ten-minute candle.
        self._indicators = replace(
            self._config.indicators,
            rsi_period=7,
            macd_fast=6,
            macd_slow=13,
            macd_signal=5,
            bollinger_period=20,
            atr_period=14,
            ema_fast=9,
            ema_mid=21,
            ema_slow=50,
            momentum_period=5,
            momentum_threshold=0.001 if self._market_type == "forex" else 0.002,
            min_signal_score=float(os.getenv("FAST_MIN_SCORE", "0.50")),
            bollinger_tolerance_high=1.003 if self._market_type == "forex" else 1.01,
            bollinger_tolerance_low=0.997 if self._market_type == "forex" else 0.99,
        )

    @property
    def market_type(self) -> str:
        return self._market_type

    @property
    def risk_params(self) -> EngineRiskParams:
        return self._config.risk

    @property
    def indicator_config(self) -> IndicatorConfig:
        return self._indicators

    @property
    def term(self) -> str:
        return self._term

    def get_symbols(self) -> list[str]:
        return list(self._symbols)

    def is_market_hours(self) -> bool:
        if self._market_type == "crypto":
            return True
        now = datetime.now()
        if now.weekday() == 5 and now.hour >= 5:
            return False
        if now.weekday() == 6 and now.hour < 5:
            return False
        return True

    def _fetch_bars(self, symbol: str, limit: int) -> list[dict[str, Any]]:
        interval = self._term_cfg.data_interval
        if self._market_type == "crypto":
            from .exchange_data import fetch_klines
            bars, source = fetch_klines(symbol, interval, limit)
            self._last_source = source
            return bars
        from . import tradfi_data
        bars, source = tradfi_data.fetch_bars(
            symbol, interval, limit, self._market_type
        )
        self._last_source = source
        return bars

    def fetch_prices(self, symbol: str, lookback: int) -> list[float]:
        return [float(b["close"]) for b in self._fetch_bars(symbol, lookback)]

    def analyze_symbol(self, symbol: str) -> Signal | None:
        try:
            bars = self._fetch_bars(symbol, max(80, self._indicators.ema_slow + 30))
            if len(bars) < 60:
                return None
            closes = [float(b["close"]) for b in bars]
            current = closes[-1]
            if current <= 0:
                return None

            rsi = calculate_rsi(closes, self._indicators.rsi_period)
            macd = calculate_macd(
                closes, self._indicators.macd_fast,
                self._indicators.macd_slow, self._indicators.macd_signal,
            )
            bollinger = calculate_bollinger(
                closes, self._indicators.bollinger_period,
                self._indicators.bollinger_std,
            )
            ema = {
                "ema9": calculate_ema(closes, self._indicators.ema_fast),
                "ema21": calculate_ema(closes, self._indicators.ema_mid),
                "ema50": calculate_ema(closes, self._indicators.ema_slow),
            }
            result = score_signal(
                rsi, macd, bollinger, closes, current,
                self._indicators, ema=ema,
            )
            if not result["direction"]:
                return None

            atr = _atr_from_bars(bars, self._indicators.atr_period)
            if atr <= 0:
                return None
            atr_pct = atr / current
            cost_pct = _COST_PCT.get(self._market_type, 0.001) * _COST_MULTIPLE

            tp_pct = atr_pct * _TP_ATR.get(self._term, 1.5)
            # A target that cannot clear estimated round-trip costs is not a
            # tradable setup, no matter how pretty the indicator score is.
            if tp_pct < cost_pct:
                return None
            sl_pct = max(atr_pct * _SL_ATR.get(self._term, 1.0), tp_pct / 1.5)

            confidence = float(result["confidence"])
            # Cost headroom is a quality signal, not a guarantee.
            if tp_pct > cost_pct * 2.5:
                confidence = min(0.90, confidence + 0.02)
            else:
                confidence = min(confidence, 0.72)

            if result["direction"] == "BUY":
                target = current * (1 + tp_pct)
                stop = current * (1 - sl_pct)
            else:
                target = current * (1 - tp_pct)
                stop = current * (1 + sl_pct)

            return Signal(
                symbol=symbol,
                direction=result["direction"],
                price=current,
                confidence=round(confidence, 4),
                reason=(
                    f"{' + '.join(result['reasons'])} | "
                    f"{self._term_cfg.horizon_label()} target, "
                    f"cost floor {cost_pct:.2%}"
                ),
                target_price=round_price(target),
                stop_loss=round_price(stop),
                signal_type=self._market_type,
                fees=self.calculate_fees(symbol, 1, current),
                slippage=self.calculate_slippage(symbol, 1, current),
                term=self._term,
                timeframe=self._term_cfg.data_interval,
                metadata={
                    "strategy": f"Fast {self._term_cfg.label}",
                    "term": self._term,
                    "timeframe": self._term_cfg.data_interval,
                    "horizon": self._term_cfg.horizon_label(),
                    "rsi": rsi,
                    "atr": atr,
                    "macd": macd,
                    "cost_pct": round(cost_pct, 6),
                    "tp_pct": round(tp_pct, 6),
                    "sl_pct": round(sl_pct, 6),
                    "data_source": "live" if self._last_source else "simulated",
                    **ema,
                },
            )
        except Exception as e:
            logger.warning("fast analyze failed for %s %s: %s", self._term, symbol, str(e)[:140])
            return None

    def run_cycle(self, account_value: float = 100000) -> list[Signal]:
        if not self.is_market_hours():
            return []
        signals: list[Signal] = []
        for symbol in self.get_symbols():
            signal = self.analyze_symbol(symbol)
            if signal is not None:
                signals.append(signal)
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    def calculate_fees(self, symbol: str, quantity: float, price: float) -> float:
        cost = _COST_PCT.get(self._market_type, 0.001) / 2
        return round(quantity * price * cost, 6)

    def calculate_slippage(self, symbol: str, quantity: float, price: float) -> float:
        cost = _COST_PCT.get(self._market_type, 0.001) / 2
        return round(quantity * price * cost, 6)

    def calculate_position_size(self, symbol: str, price: float, account_value: float) -> float:
        if price <= 0:
            return 0.0
        value = account_value * self._config.risk.max_position_size
        return round(value / price, 6)
