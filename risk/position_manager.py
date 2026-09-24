"""
Phase 3: Risk Engine - Position Manager
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PositionManager:
    """
    Manage and monitor open positions.
    """
    
    def __init__(self, max_positions: int = 5, max_position_size: float = 0.10):
        self.max_positions = max_positions
        self.max_position_size = max_position_size
        self.positions: Dict[str, Dict[str, Any]] = {}
        
    def can_open_position(self, symbol: str, size_pct: float) -> bool:
        """
        Check if a new position can be opened.
        
        Returns:
            True if position can be opened
        """
        # Check position count
        if len(self.positions) >= self.max_positions:
            logger.warning(f"Max positions reached: {len(self.positions)}/{self.max_positions}")
            return False
        
        # Check if already have position in this symbol
        if symbol in self.positions:
            logger.warning(f"Already have position in {symbol}")
            return False
        
        # Check position size
        if size_pct > self.max_position_size:
            logger.warning(f"Position size {size_pct:.2%} exceeds max {self.max_position_size:.2%}")
            return False
        
        return True
    
    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float
    ) -> Dict[str, Any]:
        """
        Record a new position.
        """
        position = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "entry_time": datetime.now(),
            "current_price": entry_price,
            "unrealized_pnl": 0.0,
            "status": "open"
        }
        
        self.positions[symbol] = position
        logger.info(f"Position opened: {side} {quantity} {symbol} @ {entry_price}")
        
        return position
    
    def close_position(self, symbol: str, exit_price: float) -> Dict[str, Any]:
        """
        Close an existing position.
        """
        if symbol not in self.positions:
            logger.error(f"No position found for {symbol}")
            return {}
        
        position = self.positions.pop(symbol)
        
        # Calculate P&L
        if position["side"] == "buy":
            pnl = (exit_price - position["entry_price"]) * position["quantity"]
        else:
            pnl = (position["entry_price"] - exit_price) * position["quantity"]
        
        position["exit_price"] = exit_price
        position["exit_time"] = datetime.now()
        position["pnl"] = pnl
        position["status"] = "closed"
        
        logger.info(f"Position closed: {symbol} P&L: ${pnl:.2f}")
        
        return position
    
    def update_position(self, symbol: str, current_price: float):
        """Update position with current price."""
        if symbol in self.positions:
            position = self.positions[symbol]
            position["current_price"] = current_price
            
            # Update unrealized P&L
            if position["side"] == "buy":
                position["unrealized_pnl"] = (
                    (current_price - position["entry_price"]) * position["quantity"]
                )
            else:
                position["unrealized_pnl"] = (
                    (position["entry_price"] - current_price) * position["quantity"]
                )
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for a symbol."""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        return list(self.positions.values())
    
    def get_total_value(self) -> float:
        """Get total value of all positions."""
        return sum(
            pos["current_price"] * pos["quantity"]
            for pos in self.positions.values()
        )
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L."""
        return sum(
            pos["unrealized_pnl"]
            for pos in self.positions.values()
        )
