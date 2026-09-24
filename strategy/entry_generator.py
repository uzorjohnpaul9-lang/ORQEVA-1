"""
Phase 4: Strategy Engine - Entry Generator
"""
from typing import Dict, Any, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class EntryGenerator:
    """
    Generate trade entry signals.
    """
    
    def __init__(self):
        self.entry_rules = []
        
    def generate_entry(
        self,
        symbol: str,
        market_data: pd.DataFrame,
        indicators: Dict[str, Any],
        regime: str = "sideways"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate entry signal.
        
        Returns:
            Entry signal or None
        """
        # Get latest values
        latest_close = market_data["close"].iloc[-1]
        latest_rsi = indicators["rsi"].iloc[-1] if "rsi" in indicators else 50
        latest_macd = indicators["macd"]["histogram"].iloc[-1] if "macd" in indicators else 0
        
        # Determine entry conditions
        entry_signal = None
        
        # RSI oversold + MACD crossover = Buy signal
        if latest_rsi < 30 and latest_macd > 0:
            entry_signal = {
                "symbol": symbol,
                "direction": "buy",
                "confidence": 0.7,
                "entry_price": latest_close,
                "reason": "RSI oversold + MACD bullish crossover"
            }
        
        # RSI overbought + MACD crossover = Sell signal
        elif latest_rsi > 70 and latest_macd < 0:
            entry_signal = {
                "symbol": symbol,
                "direction": "sell",
                "confidence": 0.7,
                "entry_price": latest_close,
                "reason": "RSI overbought + MACD bearish crossover"
            }
        
        return entry_signal
