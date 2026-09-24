"""
Phase 3: Risk Engine - Profit Protection
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ProfitProtection:
    """
    Profit protection controls (Controls 14-16).
    """
    
    def __init__(self):
        self.trailing_stops: Dict[str, Dict[str, Any]] = {}
        self.take_profit_targets: Dict[str, float] = {}
        
    def calculate_trailing_stop(
        self,
        symbol: str,
        current_price: float,
        highest_price: float,
        trailing_pct: float = 0.02
    ) -> Dict[str, Any]:
        """
        Control 14: Trailing Stop Loss
        
        Calculate dynamic stop loss.
        """
        stop_price = highest_price * (1 - trailing_pct)
        
        # Update trailing stop
        if symbol not in self.trailing_stops:
            self.trailing_stops[symbol] = {
                "highest_price": highest_price,
                "stop_price": stop_price,
                "trailing_pct": trailing_pct
            }
        else:
            if current_price > self.trailing_stops[symbol]["highest_price"]:
                self.trailing_stops[symbol]["highest_price"] = current_price
                self.trailing_stops[symbol]["stop_price"] = current_price * (1 - trailing_pct)
        
        should_stop = current_price <= self.trailing_stops[symbol]["stop_price"]
        
        return {
            "control": "trailing_stop",
            "symbol": symbol,
            "current_price": current_price,
            "stop_price": self.trailing_stops[symbol]["stop_price"],
            "highest_price": self.trailing_stops[symbol]["highest_price"],
            "should_stop": should_stop,
            "trailing_pct": trailing_pct
        }
    
    def check_take_profit(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        take_profit_pct: float = 0.06
    ) -> Dict[str, Any]:
        """
        Control 15: Take Profit Manager
        
        Check if take profit target is reached.
        """
        profit_pct = (current_price - entry_price) / entry_price
        target_reached = profit_pct >= take_profit_pct
        
        return {
            "control": "take_profit",
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "profit_pct": profit_pct,
            "take_profit_pct": take_profit_pct,
            "target_reached": target_reached
        }
    
    def calculate_gradual_deployment(
        self,
        symbol: str,
        intended_quantity: float,
        is_first_trade: bool = True
    ) -> Dict[str, Any]:
        """
        Control 16: Gradual Deployment
        
        Scale into positions gradually.
        """
        if is_first_trade:
            # Only use 50% of intended quantity for first trade
            actual_quantity = intended_quantity * 0.5
            reason = "First trade: using 50% of intended quantity"
        else:
            actual_quantity = intended_quantity
            reason = "Subsequent trade: using full quantity"
        
        return {
            "control": "gradual_deployment",
            "symbol": symbol,
            "intended_quantity": intended_quantity,
            "actual_quantity": actual_quantity,
            "is_first_trade": is_first_trade,
            "reason": reason
        }
