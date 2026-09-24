"""
Trading System - Core Integration
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import trading_settings
from config.risk_profiles import get_risk_profile, RiskProfile
from data.market_data import MarketDataManager
from data.technical_indicators import TechnicalIndicators
from data.data_validator import DataValidator
from risk.risk_engine import RiskEngine
from risk.kill_switch import KillSwitch
from risk.position_manager import PositionManager
from risk.portfolio_manager import PortfolioManager
from risk.time_controls import TimeControls
from risk.audit_logger import AuditLogger
from strategy.strategy_engine import StrategyEngine
from strategy.technical_indicators import TechnicalIndicators as StrategyIndicators
from strategy.entry_generator import EntryGenerator
from strategy.exit_generator import ExitGenerator
from ai_models.regime_detector import MarketRegimeDetector
from ai_models.confidence_scorer import ConfidenceScorer
from ai_models.momentum_decoder import MomentumDecoder
from execution.paper_trader import PaperTrader
from execution.order_manager import OrderManager
from execution.position_manager import PositionManager as ExecutionPositionManager

logger = logging.getLogger(__name__)

class TradingSystem:
    """
    Main trading system that integrates all components.
    """
    
    def __init__(self, risk_profile: str = "conservative"):
        self.risk_profile = get_risk_profile(risk_profile)
        self.is_running = False
        
        # Initialize components
        self.market_data = MarketDataManager()
        self.indicators = TechnicalIndicators()
        self.validator = DataValidator()
        
        # Risk components
        self.risk_engine = RiskEngine(risk_profile)
        self.kill_switch = KillSwitch()
        self.time_controls = TimeControls()
        self.audit_logger = AuditLogger()
        
        # Strategy components
        self.strategy_engine = StrategyEngine()
        self.entry_generator = EntryGenerator()
        self.exit_generator = ExitGenerator()
        
        # AI components
        self.regime_detector = MarketRegimeDetector()
        self.confidence_scorer = ConfidenceScorer()
        self.momentum_decoder = MomentumDecoder()
        
        # Execution components
        self.paper_trader = PaperTrader()
        self.order_manager = OrderManager()
        self.execution_positions = ExecutionPositionManager()
        
        logger.info(f"Trading System initialized with {risk_profile} profile")
    
    def start(self):
        """Start the trading system."""
        logger.info("Starting Trading System...")
        self.is_running = True
        self.paper_trader.start()
        logger.info("Trading System started successfully")
    
    def stop(self):
        """Stop the trading system."""
        logger.info("Stopping Trading System...")
        self.is_running = False
        self.paper_trader.stop()
        logger.info("Trading System stopped")
    
    def get_market_data(self, symbol: str, timeframe: str = "1h") -> Any:
        """
        Get market data for a symbol.
        
        Returns:
            DataFrame with OHLCV data
        """
        return self.market_data.get_stock_data(symbol, timeframe)
    
    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Analyze a symbol and generate trading signals.
        
        Returns:
            Analysis results
        """
        # Get market data
        market_data = self.get_market_data(symbol)
        
        if market_data is None or market_data.empty:
            return {"error": "No data available"}
        
        # Calculate technical indicators
        indicators = self.indicators.calculate_all_indicators(market_data)
        
        # Detect market regime
        prices = market_data["close"].tolist()
        regime = self.regime_detector.detect_regime({
            "prices": prices,
            "volatility": 0.02,  # Placeholder
            "trend_strength": 0.6  # Placeholder
        })
        
        # Calculate momentum
        momentum = self.momentum_decoder.calculate_momentum(
            market_data["close"].values
        )
        
        # Generate entry signal
        entry_signal = self.entry_generator.generate_entry(
            symbol, market_data, indicators, regime["regime"]
        )
        
        # Score confidence
        confidence = self.confidence_scorer.score_trade(
            technical_signals=indicators,
            regime=regime["regime"],
            volume_data={"volume": market_data["volume"].iloc[-1]},
            momentum=momentum.get("short_term", 0),
            volatility=0.02  # Placeholder
        )
        
        return {
            "symbol": symbol,
            "current_price": market_data["close"].iloc[-1],
            "regime": regime,
            "momentum": momentum,
            "entry_signal": entry_signal,
            "confidence": confidence,
            "indicators": {
                "rsi": indicators["rsi"].iloc[-1] if "rsi" in indicators else None,
                "macd": indicators["macd"]["histogram"].iloc[-1] if "macd" in indicators else None
            }
        }
    
    def check_trade_allowed(
        self,
        symbol: str,
        side: str,
        quantity: float,
        current_price: float,
        account_value: float
    ) -> Dict[str, Any]:
        """
        Check if a trade is allowed.
        
        Returns:
            Trade decision
        """
        decision = self.risk_engine.check_trade_allowed(
            symbol, side, quantity, current_price, account_value
        )
        
        return {
            "allowed": decision.allowed,
            "checks": [
                {
                    "name": check.name,
                    "allowed": check.allowed,
                    "reason": check.reason
                }
                for check in decision.checks
            ],
            "timestamp": decision.timestamp.isoformat()
        }
    
    def execute_paper_trade(
        self,
        symbol: str,
        quantity: int,
        side: str,
        order_type: str = "market"
    ) -> Dict[str, Any]:
        """
        Execute a paper trade.
        
        Returns:
            Order details
        """
        if not self.is_active():
            return {"error": "System not active"}
        
        # Check if trade is allowed
        account_value = self.paper_trader.get_portfolio_value()
        current_price = self.market_data.get_realtime_quote(symbol)["last"]
        
        trade_check = self.check_trade_allowed(
            symbol, side, quantity, current_price, account_value
        )
        
        if not trade_check["allowed"]:
            return {
                "error": "Trade not allowed",
                "reasons": [c["reason"] for c in trade_check["checks"] if not c["allowed"]]
            }
        
        # Execute paper trade
        order = self.paper_trader.place_order(
            symbol, quantity, side, order_type
        )
        
        # Log the trade
        self.audit_logger.log_position_opened(
            symbol, side, quantity, order.get("filled_price", 0)
        )
        
        return order
    
    def get_portfolio_status(self) -> Dict[str, Any]:
        """
        Get current portfolio status.
        
        Returns:
            Portfolio status
        """
        return {
            "is_active": self.is_running,
            "portfolio_value": self.paper_trader.get_portfolio_value(),
            "positions": self.paper_trader.get_positions(),
            "capital": self.paper_trader.capital,
            "risk_profile": self.risk_profile.name,
            "kill_switch_active": self.kill_switch.is_active
        }
    
    def is_active(self) -> bool:
        """Check if system is active."""
        return self.is_running and not self.kill_switch.is_active
    
    def activate_kill_switch(self, reason: str):
        """Activate kill switch."""
        self.kill_switch.activate(reason)
        self.risk_engine.activate_kill_switch(reason)
        self.audit_logger.log_kill_switch(reason)
    
    def deactivate_kill_switch(self):
        """Deactivate kill switch."""
        self.kill_switch.deactivate()
        self.risk_engine.deactivate_kill_switch()
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get complete system status.
        
        Returns:
            System status
        """
        return {
            "is_running": self.is_running,
            "is_active": self.is_active(),
            "risk_profile": self.risk_profile.name,
            "portfolio": self.get_portfolio_status(),
            "market_open": self.market_data.is_market_open(),
            "kill_switch": self.kill_switch.get_status()
        }
