"""
Phase 6: Order Manager
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OrderManager:
    """
    Manage order lifecycle.
    """
    
    def __init__(self):
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.order_history: List[Dict[str, Any]] = []
        
    def create_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create a new order.
        
        Returns:
            Order details
        """
        order_id = f"order_{len(self.orders) + 1}"
        
        order = {
            "id": order_id,
            "symbol": symbol,
            "quantity": quantity,
            "side": side,
            "type": order_type,
            "limit_price": limit_price,
            "status": "pending",
            "created_at": datetime.now(),
            "filled_at": None,
            "filled_price": None
        }
        
        self.orders[order_id] = order
        logger.info(f"Order created: {order_id}")
        
        return order
    
    def fill_order(self, order_id: str, fill_price: float):
        """Fill an order."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "filled"
            self.orders[order_id]["filled_price"] = fill_price
            self.orders[order_id]["filled_at"] = datetime.now()
            
            # Move to history
            self.order_history.append(self.orders.pop(order_id))
            logger.info(f"Order filled: {order_id} @ {fill_price}")
    
    def cancel_order(self, order_id: str):
        """Cancel an order."""
        if order_id in self.orders:
            self.orders[order_id]["status"] = "cancelled"
            self.order_history.append(self.orders.pop(order_id))
            logger.info(f"Order cancelled: {order_id}")
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending orders."""
        return [o for o in self.orders.values() if o["status"] == "pending"]
