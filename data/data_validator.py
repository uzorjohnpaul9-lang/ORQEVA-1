"""
Phase 2: Data Infrastructure - Data Validator
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DataValidator:
    """
    Validate incoming market data.
    """
    
    def __init__(self):
        self.validation_errors = []
        
    def validate_ohlcv(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate OHLCV data integrity.
        
        Returns:
            Dictionary with validation results
        """
        errors = []
        
        # Check required columns
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_columns if col not in data.columns]
        if missing_cols:
            errors.append(f"Missing columns: {missing_cols}")
        
        # Check for null values
        null_counts = data.isnull().sum()
        if null_counts.any():
            errors.append(f"Null values found: {null_counts[null_counts > 0].to_dict()}")
        
        # Check for negative prices
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in data.columns:
                neg_count = (data[col] < 0).sum()
                if neg_count > 0:
                    errors.append(f"Negative values in {col}: {neg_count}")
        
        # Check for negative volume
        if 'volume' in data.columns:
            neg_vol = (data['volume'] < 0).sum()
            if neg_vol > 0:
                errors.append(f"Negative volume: {neg_vol}")
        
        # Check high >= low
        if 'high' in data.columns and 'low' in data.columns:
            invalid_hl = (data['high'] < data['low']).sum()
            if invalid_hl > 0:
                errors.append(f"High < Low violations: {invalid_hl}")
        
        # Check high >= open and high >= close
        if all(col in data.columns for col in ['high', 'open', 'close']):
            invalid_high_open = (data['high'] < data['open']).sum()
            invalid_high_close = (data['high'] < data['close']).sum()
            if invalid_high_open > 0:
                errors.append(f"High < Open violations: {invalid_high_open}")
            if invalid_high_close > 0:
                errors.append(f"High < Close violations: {invalid_high_close}")
        
        # Check low <= open and low <= close
        if all(col in data.columns for col in ['low', 'open', 'close']):
            invalid_low_open = (data['low'] > data['open']).sum()
            invalid_low_close = (data['low'] > data['close']).sum()
            if invalid_low_open > 0:
                errors.append(f"Low > Open violations: {invalid_low_open}")
            if invalid_low_close > 0:
                errors.append(f"Low > Close violations: {invalid_low_close}")
        
        self.validation_errors = errors
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "row_count": len(data),
            "column_count": len(data.columns)
        }
    
    def check_gaps(self, data: pd.DataFrame, timeframe: str = "1h") -> List[Dict[str, Any]]:
        """
        Check for data gaps in time series.
        
        Returns:
            List of gap dictionaries
        """
        gaps = []
        
        if 'timestamp' not in data.columns:
            return gaps
        
        # Convert to datetime if needed
        timestamps = pd.to_datetime(data['timestamp'])
        timestamps = timestamps.sort_values()
        
        # Define expected frequency
        freq_map = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "1h": "1h",
            "1d": "1D"
        }
        freq = freq_map.get(timeframe, "1h")
        
        # Check for gaps
        for i in range(1, len(timestamps)):
            expected_diff = pd.Timedelta(freq)
            actual_diff = timestamps.iloc[i] - timestamps.iloc[i-1]
            
            if actual_diff > expected_diff * 1.5:  # Allow 50% tolerance
                gaps.append({
                    "start": timestamps.iloc[i-1],
                    "end": timestamps.iloc[i],
                    "expected_duration": expected_diff,
                    "actual_duration": actual_diff,
                    "missing_periods": int(actual_diff / expected_diff) - 1
                })
        
        return gaps
    
    def validate_price(self, price: float, symbol: str = "") -> bool:
        """
        Validate price is reasonable.
        
        Returns:
            True if price is valid
        """
        if price is None or np.isnan(price):
            logger.warning(f"Invalid price for {symbol}: {price}")
            return False
        
        if price <= 0:
            logger.warning(f"Non-positive price for {symbol}: {price}")
            return False
        
        if price > 100000:  # Reasonable upper bound
            logger.warning(f"Unusually high price for {symbol}: {price}")
            return False
        
        return True
    
    def validate_volume(self, volume: int, symbol: str = "") -> bool:
        """
        Validate volume is reasonable.
        
        Returns:
            True if volume is valid
        """
        if volume is None or np.isnan(volume):
            logger.warning(f"Invalid volume for {symbol}: {volume}")
            return False
        
        if volume < 0:
            logger.warning(f"Negative volume for {symbol}: {volume}")
            return False
        
        return True
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Validate symbol format.
        
        Returns:
            True if symbol is valid
        """
        if not symbol or not isinstance(symbol, str):
            return False
        
        # Basic symbol validation (1-5 uppercase letters)
        if len(symbol) < 1 or len(symbol) > 5:
            return False
        
        if not symbol.isalpha() or not symbol.isupper():
            return False
        
        return True
