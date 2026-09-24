"""
Phase 6: Backtesting Engine
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class Backtester:
    """
    Backtesting engine for validating trading strategies.
    """
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = []
        
    def run_backtest(
        self,
        strategy: Any,
        data: pd.DataFrame,
        risk_profile: str = "conservative"
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data.
        
        Args:
            strategy: Trading strategy to test
            data: Historical price data
            risk_profile: Risk profile to use
            
        Returns:
            Backtest results
        """
        logger.info("Starting backtest...")
        
        self.capital = self.initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = []
        
        for i in range(len(data)):
            current_data = data.iloc[:i+1]
            
            # Generate signal
            signal = strategy.generate_signal(current_data, {})
            
            # Execute trade if signal exists
            if signal and signal.get("direction") != "hold":
                self._execute_trade(signal, data.iloc[i])
            
            # Update equity
            self._update_equity(data.iloc[i])
        
        return self._generate_report()
    
    def _execute_trade(self, signal: Dict[str, Any], bar: pd.Series):
        """Execute a trade based on signal."""
        direction = signal.get("direction")
        confidence = signal.get("confidence", 0.5)
        
        # Calculate position size based on confidence
        position_size = self.capital * 0.1 * confidence
        
        if direction == "buy" and self.capital >= position_size:
            self.positions.append({
                "entry_price": bar["close"],
                "size": position_size,
                "entry_time": bar.name if hasattr(bar, 'name') else datetime.now(),
                "direction": "long"
            })
            self.capital -= position_size
            
        elif direction == "sell" and self.positions:
            # Close position
            position = self.positions.pop(0)
            pnl = (bar["close"] - position["entry_price"]) / position["entry_price"] * position["size"]
            self.capital += position["size"] + pnl
            self.trades.append({
                "entry_price": position["entry_price"],
                "exit_price": bar["close"],
                "pnl": pnl,
                "return_pct": pnl / position["size"]
            })
    
    def _update_equity(self, bar: pd.Series):
        """Update equity curve."""
        equity = self.capital
        for pos in self.positions:
            equity += pos["size"] * (bar["close"] / pos["entry_price"])
        self.equity_curve.append(equity)
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate backtest report."""
        equity_series = pd.Series(self.equity_curve)
        
        returns = equity_series.pct_change().dropna()
        
        total_return = (self.equity_curve[-1] - self.initial_capital) / self.initial_capital
        
        # Calculate metrics
        winning_trades = [t for t in self.trades if t["pnl"] > 0]
        losing_trades = [t for t in self.trades if t["pnl"] <= 0]
        
        win_rate = len(winning_trades) / len(self.trades) if self.trades else 0
        
        avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t["pnl"]) for t in losing_trades]) if losing_trades else 0
        
        profit_factor = avg_win / avg_loss if avg_loss > 0 else float('inf')
        
        # Sharpe ratio
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Max drawdown
        max_drawdown = 0
        peak = self.equity_curve[0]
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.equity_curve[-1] if self.equity_curve else self.initial_capital,
            "total_return": total_return,
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "equity_curve": self.equity_curve
        }
