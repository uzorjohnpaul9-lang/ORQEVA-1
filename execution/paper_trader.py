"""
Phase 7: Paper Trading System
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PaperTrader:
    """
    Paper trading system for testing without real money.
    """
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = {}
        self.orders = []
        self.trades = []
        self.is_active = False
        
    def start(self):
        """Start paper trading."""
        self.is_active = True
        logger.info(f"Paper trading started with ${self.initial_capital}")
    
    def stop(self):
        """Stop paper trading."""
        self.is_active = False
        logger.info("Paper trading stopped")
    
    def place_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place a paper order.
        
        Returns:
            Order details
        """
        if not self.is_active:
            return {"error": "Paper trading not active"}
        
        # Simulate order execution
        order = {
            "id": f"paper_{len(self.orders) + 1}",
            "symbol": symbol,
            "quantity": quantity,
            "side": side,
            "type": order_type,
            "status": "filled",
            "filled_price": limit_price or 150.00,  # Placeholder
            "filled_at": datetime.now(),
            "commission": 0.0
        }
        
        self.orders.append(order)
        
        # Update positions
        self._update_position(order)
        
        logger.info(f"Paper order filled: {side} {quantity} {symbol}")
        return order
    
    def _update_position(self, order: Dict[str, Any]):
        """Update position based on order."""
        symbol = order["symbol"]
        quantity = order["quantity"]
        side = order["side"]
        price = order["filled_price"]
        
        if symbol not in self.positions:
            self.positions[symbol] = {
                "symbol": symbol,
                "quantity": 0,
                "avg_price": 0,
                "side": side
            }
        
        pos = self.positions[symbol]
        
        if side == "buy":
            pos["quantity"] += quantity
        else:
            pos["quantity"] -= quantity
        
        # Update average price
        pos["avg_price"] = price
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        value = self.capital
        for pos in self.positions.values():
            value += pos["quantity"] * pos["avg_price"]
        return value
    
    def get_positions(self) -> Dict[str, Any]:
        """Get all positions."""
        return self.positions
    
    def get_trade_history(self) -> list:
        """Get trade history."""
        return self.trades
