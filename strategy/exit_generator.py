"""
Phase 4: Strategy Engine - Exit Generator
"""
from typing import Dict, Any, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class ExitGenerator:
    """
    Generate trade exit signals.
    """
    
    def __init__(self):
        self.exit_rules = []
        
    def generate_exit(
        self,
        symbol: str,
        position: Dict[str, Any],
        market_data: pd.DataFrame,
        indicators: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate exit signal.
        
        Returns:
            Exit signal or None
        """
        # Get position details
        entry_price = position.get("entry_price", 0)
        current_price = market_data["close"].iloc[-1]
        side = position.get("side", "buy")
        
        # Calculate profit/loss
        if side == "buy":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        exit_signal = None
        
        # Take profit at 6%
        if pnl_pct >= 0.06:
            exit_signal = {
                "symbol": symbol,
                "reason": "take_profit",
                "confidence": 1.0,
                "exit_price": current_price,
                "pnl_pct": pnl_pct
            }
        
        # Stop loss at -2%
        elif pnl_pct <= -0.02:
            exit_signal = {
                "symbol": symbol,
                "reason": "stop_loss",
                "confidence": 1.0,
                "exit_price": current_price,
                "pnl_pct": pnl_pct
            }
        
        return exit_signal
