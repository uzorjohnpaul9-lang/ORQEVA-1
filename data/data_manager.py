"""
Phase 2: Data Infrastructure - Data Manager
"""
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

from .market_data import MarketDataManager
from .technical_indicators import TechnicalIndicators
from .data_validator import DataValidator

logger = logging.getLogger(__name__)

class DataManager:
    """Central data management system."""
    
    def __init__(self):
        self.market_data = MarketDataManager()
        self.indicators = TechnicalIndicators()
        self.validator = DataValidator()
        self.data_cache = {}
        
    def get_historical_data(
        self,
        symbols: List[str],
        timeframe: str = "1h",
        days_back: int = 30
    ) -> Dict[str, pd.DataFrame]:
        """
        Get historical data for multiple symbols.
        
        Returns:
            Dictionary mapping symbols to DataFrames
        """
        result = {}
        
        for symbol in symbols:
            df = self.market_data.get_stock_data(
                symbol=symbol,
                timeframe=timeframe
            )
            
            # Validate data
            validation = self.validator.validate_ohlcv(df)
            if validation["valid"]:
                result[symbol] = df
            else:
                logger.warning(f"Invalid data for {symbol}: {validation['errors']}")
        
        return result
    
    def get_current_prices(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get current prices for multiple symbols.
        
        Returns:
            Dictionary mapping symbols to current prices
        """
        result = {}
        
        for symbol in symbols:
            quote = self.market_data.get_realtime_quote(symbol)
            result[symbol] = {
                "price": quote["last"],
                "bid": quote["bid"],
                "ask": quote["ask"],
                "timestamp": quote["timestamp"]
            }
        
        return result
    
    def get_indicators(
        self,
        symbol: str,
        timeframe: str = "1h"
    ) -> Dict[str, Any]:
        """
        Get technical indicators for a symbol.
        
        Returns:
            Dictionary with all indicators
        """
        df = self.get_historical_data([symbol], timeframe)[symbol]
        return self.indicators.calculate_all_indicators(df)
    
    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        return self.market_data.is_market_open()
    
    def get_market_status(self) -> Dict[str, Any]:
        """
        Get current market status.
        
        Returns:
            Dictionary with market status
        """
        calendar = self.market_data.get_market_calendar()
        
        return {
            "is_open": calendar["is_open"],
            "next_open": calendar["open_time"],
            "next_close": calendar["close_time"],
            "extended_hours": calendar["extended_hours"]
        }
