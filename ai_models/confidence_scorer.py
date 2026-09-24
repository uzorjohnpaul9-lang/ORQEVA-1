"""
Phase 5: AI Models - Confidence Scorer
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ConfidenceScorer:
    """
    Score trade confidence based on multiple factors.
    """
    
    def __init__(self):
        self.scoring_weights = {
            "technical": 0.3,
            "regime": 0.2,
            "volume": 0.2,
            "momentum": 0.15,
            "volatility": 0.15
        }
        
    def score_trade(
        self,
        technical_signals: Dict[str, Any],
        regime: str,
        volume_data: Dict[str, Any],
        momentum: float,
        volatility: float
    ) -> Dict[str, Any]:
        """
        Score a potential trade.
        
        Returns:
            Confidence score and breakdown
        """
        scores = {}
        
        # Technical score (0-1)
        scores["technical"] = self._score_technical(technical_signals)
        
        # Regime score (0-1)
        scores["regime"] = self._score_regime(regime)
        
        # Volume score (0-1)
        scores["volume"] = self._score_volume(volume_data)
        
        # Momentum score (0-1)
        scores["momentum"] = self._score_momentum(momentum)
        
        # Volatility score (0-1) - lower is better for entry
        scores["volatility"] = self._score_volatility(volatility)
        
        # Weighted average
        total_score = sum(
            scores[k] * self.scoring_weights[k]
            for k in scores
        )
        
        return {
            "confidence": total_score,
            "scores": scores,
            "recommendation": self._get_recommendation(total_score)
        }
    
    def _score_technical(self, signals: Dict[str, Any]) -> float:
        """Score technical signals."""
        # Placeholder scoring logic
        return 0.5
    
    def _score_regime(self, regime: str) -> float:
        """Score market regime."""
        regime_scores = {
            "bull": 0.8,
            "sideways": 0.5,
            "bear": 0.3,
            "volatile": 0.4
        }
        return regime_scores.get(regime, 0.5)
    
    def _score_volume(self, volume_data: Dict[str, Any]) -> float:
        """Score volume conditions."""
        # Placeholder scoring logic
        return 0.5
    
    def _score_momentum(self, momentum: float) -> float:
        """Score momentum."""
        # Normalize momentum to 0-1
        return min(max((momentum + 1) / 2, 0), 1)
    
    def _score_volatility(self, volatility: float) -> float:
        """Score volatility (lower is better)."""
        # Inverse relationship - lower volatility = higher score
        return max(0, 1 - volatility)
    
    def _get_recommendation(self, score: float) -> str:
        """Get recommendation based on score."""
        if score >= 0.7:
            return "Strong buy signal"
        elif score >= 0.5:
            return "Moderate buy signal"
        elif score >= 0.3:
            return "Weak signal - consider waiting"
        else:
            return "No trade recommended"
