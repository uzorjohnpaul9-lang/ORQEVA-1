"""
Phase 3: Risk Engine - Market Controls
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class MarketControls:
    """
    Market condition controls (Controls 11-13).
    """
    
    def __init__(self):
        self.news_events = []
        self.correlation_threshold = 0.7
        
    def check_news_events(self, symbol: str = None) -> Dict[str, Any]:
        """
        Control 11: News/Event Awareness

        Look up imminent high-impact economic events from the calendar service.
        Annotate-only: never blocks by default (see RiskEngine._check_news_events).
        """
        try:
            from backend.services import calendar_service
            window = calendar_service.alert_window_minutes()
            pending_events = calendar_service.high_impact_soon(window)
            affected = sorted({m for e in pending_events for m in e.get("affected_markets", [])})
        except Exception:
            window = 0
            pending_events = []
            affected = []

        allowed = len(pending_events) == 0

        return {
            "control": "news_events",
            "allowed": allowed,
            "reason": (
                f"High-impact event soon: {', '.join(e.get('name', 'event') for e in pending_events[:3])}"
                if pending_events else "OK"
            ),
            "window_minutes": window,
            "pending_events": pending_events,
            "affected_markets": affected,
        }
    
    def check_liquidity(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """
        Control 12: Liquidity Protection
        
        Check if there's adequate liquidity.
        """
        # Placeholder - would check actual order book
        min_liquidity = 10000  # Minimum liquidity threshold
        
        return {
            "control": "liquidity",
            "allowed": True,  # Placeholder
            "reason": "OK",
            "min_liquidity": min_liquidity
        }
    
    def check_correlation(
        self,
        symbol: str,
        existing_positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Control 13: Correlation Manager
        
        Check if new position is too correlated with existing positions.
        """
        if not existing_positions:
            return {
                "control": "correlation",
                "allowed": True,
                "reason": "No existing positions"
            }
        
        # Placeholder - would calculate actual correlation
        # For now, allow all trades
        
        return {
            "control": "correlation",
            "allowed": True,
            "reason": "OK",
            "correlation_threshold": self.correlation_threshold
        }
