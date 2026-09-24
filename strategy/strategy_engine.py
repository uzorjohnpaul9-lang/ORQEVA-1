"""
Phase 4: Strategy Engine - Main Controller
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class StrategyEngine:
    """
    Central strategy engine that combines multiple signals
    and generates trading decisions.
    """
    
    def __init__(self):
        self.strategies = []
        self.signal_weights = {}
        self.active_signals = []
        
    def add_strategy(self, strategy: Any, weight: float = 1.0):
        """Add a trading strategy."""
        self.strategies.append(strategy)
        self.signal_weights[id(strategy)] = weight
        logger.info(f"Added strategy: {strategy.__class__.__name__}")
    
    def generate_signals(
        self,
        market_data: pd.DataFrame,
        technical_indicators: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate trading signals from all strategies.
        
        Returns:
            List of signal dictionaries
        """
        signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(market_data, technical_indicators)
                if signal:
                    signal["strategy"] = strategy.__class__.__name__
                    signal["weight"] = self.signal_weights.get(id(strategy), 1.0)
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Error in strategy {strategy.__class__.__name__}: {e}")
        
        self.active_signals = signals
        return signals
    
    def combine_signals(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine multiple signals into a final decision.
        
        Returns:
            Combined signal with direction and confidence
        """
        if not signals:
            return {"direction": "hold", "confidence": 0.0}
        
        # Weighted average of signals
        total_weight = sum(s.get("weight", 1.0) for s in signals)
        weighted_direction = 0
        
        for signal in signals:
            direction_value = 1 if signal.get("direction") == "buy" else -1
            weighted_direction += direction_value * signal.get("confidence", 0.5) * signal.get("weight", 1.0)
        
        avg_direction = weighted_direction / total_weight
        
        # Determine final direction
        if avg_direction > 0.3:
            direction = "buy"
        elif avg_direction < -0.3:
            direction = "sell"
        else:
            direction = "hold"
        
        # Average confidence
        avg_confidence = np.mean([s.get("confidence", 0.5) for s in signals])
        
        return {
            "direction": direction,
            "confidence": avg_confidence,
            "signal_count": len(signals),
            "timestamp": datetime.now()
        }
