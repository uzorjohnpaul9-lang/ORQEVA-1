"""
Phase 5: AI Models - Momentum Decoder
"""
from typing import Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)

class MomentumDecoder:
    """
    Decode momentum signals from price data.
    """
    
    def __init__(self):
        self.lookback_periods = [5, 10, 20, 50]
        
    def calculate_momentum(self, prices: np.ndarray) -> Dict[str, Any]:
        """
        Calculate momentum indicators.
        
        Returns:
            Dictionary with momentum metrics
        """
        if len(prices) < 50:
            return {"error": "Insufficient data"}
        
        # Short-term momentum (5-day)
        short_momentum = (prices[-1] - prices[-5]) / prices[-5]
        
        # Medium-term momentum (20-day)
        medium_momentum = (prices[-1] - prices[-20]) / prices[-20]
        
        # Long-term momentum (50-day)
        long_momentum = (prices[-1] - prices[-50]) / prices[-50]
        
        # Momentum acceleration
        recent_momentum = (prices[-1] - prices[-5]) / prices[-5]
        prior_momentum = (prices[-5] - prices[-10]) / prices[-10]
        acceleration = recent_momentum - prior_momentum
        
        # Determine overall momentum
        if short_momentum > 0 and medium_momentum > 0 and long_momentum > 0:
            overall = "strong_bullish"
        elif short_momentum > 0 and medium_momentum > 0:
            overall = "bullish"
        elif short_momentum < 0 and medium_momentum < 0 and long_momentum < 0:
            overall = "strong_bearish"
        elif short_momentum < 0 and medium_momentum < 0:
            overall = "bearish"
        else:
            overall = "neutral"
        
        return {
            "short_term": short_momentum,
            "medium_term": medium_momentum,
            "long_term": long_momentum,
            "acceleration": acceleration,
            "overall": overall,
            "score": self._momentum_score(short_momentum, medium_momentum, long_momentum)
        }
    
    def _momentum_score(
        self,
        short: float,
        medium: float,
        long: float
    ) -> float:
        """Calculate momentum score (0-1)."""
        # Weighted average
        score = (short * 0.5 + medium * 0.3 + long * 0.2)
        
        # Normalize to 0-1
        return min(max((score + 1) / 2, 0), 1)
