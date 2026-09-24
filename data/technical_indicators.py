"""
Phase 2: Data Infrastructure - Technical Indicators
"""
import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """Calculate technical indicators for market data."""
    
    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).
        
        Args:
            prices: Series of closing prices
            period: RSI period (default: 14)
            
        Returns:
            Series of RSI values
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def calculate_macd(
        prices: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Dict[str, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            prices: Series of closing prices
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line period (default: 9)
            
        Returns:
            Dictionary with macd, signal, histogram
        """
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: pd.Series,
        period: int = 20,
        std_dev: int = 2
    ) -> Dict[str, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: Series of closing prices
            period: SMA period (default: 20)
            std_dev: Standard deviation multiplier (default: 2)
            
        Returns:
            Dictionary with upper, middle, lower bands
        """
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return {
            "upper": upper_band,
            "middle": sma,
            "lower": lower_band
        }
    
    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average.
        
        Args:
            prices: Series of closing prices
            period: EMA period
            
        Returns:
            Series of EMA values
        """
        return prices.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Simple Moving Average.
        
        Args:
            prices: Series of closing prices
            period: SMA period
            
        Returns:
            Series of SMA values
        """
        return prices.rolling(window=period).mean()
    
    @staticmethod
    def calculate_atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of closing prices
            period: ATR period (default: 14)
            
        Returns:
            Series of ATR values
        """
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    @staticmethod
    def calculate_stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3
    ) -> Dict[str, pd.Series]:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of closing prices
            k_period: %K period (default: 14)
            d_period: %D period (default: 3)
            
        Returns:
            Dictionary with %K and %D
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()
        
        return {
            "k": k,
            "d": d
        }
    
    @staticmethod
    def calculate_adx(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average Directional Index.
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of closing prices
            period: ADX period (default: 14)
            
        Returns:
            Series of ADX values
        """
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    @staticmethod
    def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume.
        
        Args:
            close: Series of closing prices
            volume: Series of volume
            
        Returns:
            Series of OBV values
        """
        obv = pd.Series(index=close.index, dtype=float)
        obv.iloc[0] = 0
        
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate all technical indicators for a DataFrame.
        
        Args:
            df: DataFrame with columns: open, high, low, close, volume
            
        Returns:
            Dictionary with all indicators
        """
        indicators = {}
        
        # RSI
        indicators["rsi"] = self.calculate_rsi(df["close"])
        
        # MACD
        indicators["macd"] = self.calculate_macd(df["close"])
        
        # Bollinger Bands
        indicators["bollinger"] = self.calculate_bollinger_bands(df["close"])
        
        # EMAs
        indicators["ema_9"] = self.calculate_ema(df["close"], 9)
        indicators["ema_21"] = self.calculate_ema(df["close"], 21)
        indicators["ema_50"] = self.calculate_ema(df["close"], 50)
        
        # SMA
        indicators["sma_200"] = self.calculate_sma(df["close"], 200)
        
        # ATR
        indicators["atr"] = self.calculate_atr(df["high"], df["low"], df["close"])
        
        # Stochastic
        indicators["stochastic"] = self.calculate_stochastic(
            df["high"], df["low"], df["close"]
        )
        
        # ADX
        indicators["adx"] = self.calculate_adx(df["high"], df["low"], df["close"])
        
        # OBV
        indicators["obv"] = self.calculate_obv(df["close"], df["volume"])
        
        return indicators
