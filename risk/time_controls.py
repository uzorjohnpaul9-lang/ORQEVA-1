"""
Phase 3: Risk Engine - Time Controls
"""
from datetime import datetime, time
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class TimeControls:
    """
    Time-based risk controls (Controls 8-10).
    """
    
    def __init__(self):
        self.market_open = time(9, 30)
        self.market_close = time(16, 0)
        self.eod_buffer_minutes = 30
        
    def check_trading_hours(self) -> Dict[str, Any]:
        """
        Control 8: Trading Hours Only
        
        Check if current time is within trading hours.
        """
        now = datetime.now()
        current_time = now.time()
        is_weekday = now.weekday() < 5
        
        is_market_hours = self.market_open <= current_time <= self.market_close
        allowed = is_weekday and is_market_hours
        
        return {
            "control": "trading_hours",
            "allowed": allowed,
            "reason": "Outside trading hours" if not allowed else "OK",
            "current_time": now.isoformat(),
            "market_open": self.market_open.isoformat(),
            "market_close": self.market_close.isoformat()
        }
    
    def check_eod_rules(self) -> Dict[str, Any]:
        """
        Control 9: End-of-Day Rules
        
        Check if we're near end-of-day.
        """
        now = datetime.now()
        current_time = now.time()
        
        # Calculate EOD time
        eod_time = time(
            self.market_close.hour,
            max(0, self.market_close.minute - self.eod_buffer_minutes)
        )
        
        is_near_eod = current_time >= eod_time
        
        return {
            "control": "eod_rules",
            "allowed": not is_near_eod,
            "reason": "Near end-of-day, no new positions" if is_near_eod else "OK",
            "eod_time": eod_time.isoformat(),
            "buffer_minutes": self.eod_buffer_minutes
        }
    
    def check_volatility_filter(self, volatility: float = 0.0) -> Dict[str, Any]:
        """
        Control 10: Volatility Filter
        
        Check if volatility is within acceptable range.
        """
        max_volatility = 0.03  # 3% daily volatility threshold
        
        allowed = volatility <= max_volatility
        
        return {
            "control": "volatility_filter",
            "allowed": allowed,
            "reason": f"Volatility {volatility:.2%} exceeds max {max_volatility:.2%}" if not allowed else "OK",
            "current_volatility": volatility,
            "max_volatility": max_volatility
        }
