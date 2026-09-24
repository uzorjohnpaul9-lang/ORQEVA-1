"""
Phase 5: AI Models - Market Regime Detector
"""
from typing import Dict, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)

class MarketRegimeDetector:
    """
    Detect current market regime (bull, bear, sideways, volatile).
    """
    
    REGIMES = {
        "bull": {"description": "Uptrend", "trend": 1},
        "bear": {"description": "Downtrend", "trend": -1},
        "sideways": {"description": "Range-bound", "trend": 0},
        "volatile": {"description": "High volatility", "trend": 0}
    }
    
    def __init__(self):
        self.current_regime = "sideways"
        self.regime_history = []
        
    def detect_regime(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect current market regime.
        
        Args:
            market_data: Dictionary with price and indicator data
            
        Returns:
            Dictionary with regime detection
        """
        # Extract features
        prices = market_data.get("prices", [])
        volatility = market_data.get("volatility", 0.0)
        trend_strength = market_data.get("trend_strength", 0.0)
        
        # Simple regime detection logic
        if volatility > 0.03:
            regime = "volatile"
        elif trend_strength > 0.6:
            if prices[-1] > prices[0]:
                regime = "bull"
            else:
                regime = "bull" if trend_strength > 0.7 else "bear"
        elif trend_strength < 0.3:
            regime = "sideways"
        else:
            regime = "sideways"
        
        self.current_regime = regime
        self.regime_history.append({
            "regime": regime,
            "timestamp": market_data.get("timestamp")
        })
        
        return {
            "regime": regime,
            "description": self.REGIMES[regime]["description"],
            "confidence": min(trend_strength + (1 - volatility), 1.0),
            "recommendation": self._get_regime_recommendation(regime)
        }
    
    def _get_regime_recommendation(self, regime: str) -> str:
        """Get trading recommendation based on regime."""
        recommendations = {
            "bull": "Favor long positions, trend-following strategies",
            "bear": "Favor short positions, defensive strategies",
            "sideways": "Range trading, mean reversion strategies",
            "volatile": "Reduce position sizes, use wider stops"
        }
        return recommendations.get(regime, "No recommendation")
