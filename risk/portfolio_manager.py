"""
Phase 3: Risk Engine - Portfolio Manager
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class PortfolioManager:
    """
    Manage portfolio-level risk.
    """
    
    def __init__(self):
        self.initial_capital = 100000
        self.current_capital = 100000
        self.peak_capital = 100000
        self.positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        
    def calculate_total_exposure(self) -> float:
        """
        Calculate total market exposure.
        
        Returns:
            Total exposure in dollars
        """
        return sum(
            pos.get("current_price", 0) * pos.get("quantity", 0)
            for pos in self.positions
        )
    
    def calculate_drawdown(self) -> float:
        """
        Calculate current drawdown.
        
        Returns:
            Drawdown as decimal (0.0 to 1.0)
        """
        if self.peak_capital == 0:
            return 0.0
        
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        return max(0.0, drawdown)
    
    def calculate_daily_pnl(self) -> float:
        """
        Calculate today's P&L.
        
        Returns:
            Daily P&L in dollars
        """
        today = datetime.now().date()
        daily_trades = [
            t for t in self.trade_history
            if t.get("exit_time") and t["exit_time"].date() == today
        ]
        
        return sum(t.get("pnl", 0) for t in daily_trades)
    
    def calculate_leverage(self) -> float:
        """
        Calculate current leverage.
        
        Returns:
            Leverage ratio (1.0 = no leverage)
        """
        exposure = self.calculate_total_exposure()
        
        if self.current_capital == 0:
            return 0.0
        
        return exposure / self.current_capital
    
    def calculate_var(self, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            confidence: Confidence level (0.0 to 1.0)
            
        Returns:
            VaR in dollars
        """
        # Simple VaR calculation based on historical returns
        if len(self.trade_history) < 10:
            return 0.0
        
        returns = [t.get("return_pct", 0) for t in self.trade_history]
        returns.sort()
        
        index = int(len(returns) * (1 - confidence))
        var_pct = returns[index] if index < len(returns) else 0.0
        
        return self.current_capital * abs(var_pct)
    
    def update_capital(self, new_capital: float):
        """Update current capital and peak."""
        self.current_capital = new_capital
        if new_capital > self.peak_capital:
            self.peak_capital = new_capital
    
    def add_position(self, position: Dict[str, Any]):
        """Add position to portfolio."""
        self.positions.append(position)
    
    def remove_position(self, symbol: str):
        """Remove position from portfolio."""
        self.positions = [p for p in self.positions if p.get("symbol") != symbol]
    
    def add_trade(self, trade: Dict[str, Any]):
        """Add completed trade to history."""
        self.trade_history.append(trade)
