"""
Phase 2: Data Infrastructure - Time Series Database
"""
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TimeSeriesDB:
    """
    Time series database for market data storage.
    """
    
    def __init__(self):
        self.data = {}
        
    def insert(
        self,
        symbol: str,
        timestamp: datetime,
        data: Dict[str, Any]
    ):
        """
        Insert time series data point.
        
        Args:
            symbol: Stock symbol
            timestamp: Data timestamp
            data: Data point (open, high, low, close, volume)
        """
        if symbol not in self.data:
            self.data[symbol] = []
        
        self.data[symbol].append({
            "timestamp": timestamp,
            **data
        })
    
    def query(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> pd.DataFrame:
        """
        Query time series data.
        
        Returns:
            DataFrame with time series data
        """
        if symbol not in self.data:
            return pd.DataFrame()
        
        records = [
            r for r in self.data[symbol]
            if start_time <= r["timestamp"] <= end_time
        ]
        
        return pd.DataFrame(records)
    
    def get_latest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get latest data point for symbol.
        
        Returns:
            Latest data point or None
        """
        if symbol not in self.data or not self.data[symbol]:
            return None
        
        return self.data[symbol][-1]
    
    def get_aggregate(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        aggregate: str = "1h"
    ) -> pd.DataFrame:
        """
        Get aggregated data.
        
        Args:
            symbol: Stock symbol
            start_time: Start time
            end_time: End time
            aggregate: Aggregation period (1h, 1d, etc.)
            
        Returns:
            Aggregated DataFrame
        """
        df = self.query(symbol, start_time, end_time)
        
        if df.empty:
            return df
        
        # Set timestamp as index
        df = df.set_index("timestamp")
        
        # Resample and aggregate
        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }
        
        return df.resample(aggregate).agg(agg_dict).dropna()
