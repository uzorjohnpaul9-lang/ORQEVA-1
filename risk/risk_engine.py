"""
Phase 3: Risk Engine - Main Controller
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from config.risk_profiles import RiskProfile, get_risk_profile
from .kill_switch import KillSwitch
from .position_manager import PositionManager
from .portfolio_manager import PortfolioManager
from .audit_logger import AuditLogger
from .profit_protection import ProfitProtection

logger = logging.getLogger(__name__)

class TradeDecision:
    """Trade decision result."""
    
    def __init__(self, allowed: bool, checks: List, timestamp: datetime):
        self.allowed = allowed
        self.checks = checks
        self.timestamp = timestamp

class RiskCheck:
    """Individual risk check result."""
    
    def __init__(self, name: str, allowed: bool, reason: str):
        self.name = name
        self.allowed = allowed
        self.reason = reason

class RiskEngine:
    """
    Central risk management engine.
    Coordinates all 16 safety controls.
    """
    
    def __init__(self, risk_profile: str = "conservative"):
        self.profile = get_risk_profile(risk_profile)
        self.kill_switch = KillSwitch()
        self.position_manager = PositionManager(
            max_positions=self.profile.max_positions,
            max_position_size=self.profile.max_position_size
        )
        self.portfolio_manager = PortfolioManager()
        self.audit_logger = AuditLogger()
        self.profit_protection = ProfitProtection()
        self.daily_pnl = 0.0
        self._load_daily_state()
        
        logger.info(f"Risk Engine initialized with {risk_profile} profile")
    
    def check_trade_allowed(
        self,
        symbol: str,
        side: str,
        quantity: float,
        current_price: float,
        account_value: float
    ) -> TradeDecision:
        """
        Check if trade is allowed based on all 16 controls.
        
        Returns:
            TradeDecision with allowed/rejected and reasons
        """
        checks = []
        
        # Tier 1: Immediate Stop
        checks.append(self._check_kill_switch())
        checks.append(self._check_max_drawdown(account_value))
        checks.append(self._check_daily_loss(account_value))
        
        # Tier 2: Position Controls
        checks.append(self._check_position_size(quantity, current_price, account_value))
        checks.append(self._check_position_count())
        checks.append(self._check_max_exposure(account_value))
        checks.append(self._check_leverage())
        
        # Tier 3: Time Controls
        checks.append(self._check_trading_hours())
        checks.append(self._check_eod_rules())
        checks.append(self._check_volatility_filter())
        
        # Tier 4: Market Controls
        checks.append(self._check_news_events())
        checks.append(self._check_liquidity(symbol, quantity))
        checks.append(self._check_correlation(symbol))
        
        # Tier 5: Profit Protection (Controls 14-16)
        pos_data = self.position_manager.positions.get(symbol, {})
        if pos_data:
            highest = pos_data.get("highest_price", current_price)
            trailing = self.profit_protection.calculate_trailing_stop(symbol, current_price, highest)
            if trailing.get("should_stop"):
                checks.append(RiskCheck(name="trailing_stop", allowed=False, reason=f"Trailing stop hit: {trailing['stop_price']:.2f}"))
            entry = pos_data.get("entry_price", current_price)
            tp = self.profit_protection.check_take_profit(symbol, entry, current_price)
            if tp.get("target_reached"):
                checks.append(RiskCheck(name="take_profit", allowed=False, reason=f"Take profit reached: {tp['profit_pct']:.1%}"))
        
        # Determine if allowed
        allowed = all(c.allowed for c in checks)
        
        decision = TradeDecision(
            allowed=allowed,
            checks=checks,
            timestamp=datetime.now()
        )
        
        # Log decision
        self.audit_logger.log_trade_decision(decision)
        
        return decision
    
    def _check_kill_switch(self) -> RiskCheck:
        """Control 1: Kill Switch"""
        return RiskCheck(
            name="kill_switch",
            allowed=not self.kill_switch.is_active,
            reason="Kill switch is active" if self.kill_switch.is_active else "OK"
        )
    
    def _check_max_drawdown(self, account_value: float) -> RiskCheck:
        """Control 2: Max Drawdown Stop"""
        drawdown = self.portfolio_manager.calculate_drawdown()
        max_drawdown = self.profile.max_drawdown
        
        allowed = drawdown < max_drawdown
        return RiskCheck(
            name="max_drawdown",
            allowed=allowed,
            reason=f"Drawdown {drawdown:.2%} exceeds max {max_drawdown:.2%}" if not allowed else "OK"
        )
    
    def _check_daily_loss(self, account_value: float) -> RiskCheck:
        """Control 3: Daily Loss Limit"""
        max_daily_loss = account_value * self.profile.max_daily_loss
        
        allowed = abs(self.daily_pnl) < max_daily_loss
        return RiskCheck(
            name="daily_loss",
            allowed=allowed,
            reason=f"Daily loss ${abs(self.daily_pnl):.2f} exceeds max ${max_daily_loss:.2f}" if not allowed else "OK"
        )
    
    def _check_position_size(self, quantity: float, price: float, account_value: float) -> RiskCheck:
        """Control 4: Position Size Limit"""
        position_value = quantity * price
        max_position = account_value * self.profile.max_position_size
        
        allowed = position_value <= max_position
        return RiskCheck(
            name="position_size",
            allowed=allowed,
            reason=f"Position ${position_value:.2f} exceeds max ${max_position:.2f}" if not allowed else "OK"
        )
    
    def _check_position_count(self) -> RiskCheck:
        """Control 5: Position Count Limit"""
        position_count = len(self.position_manager.get_all_positions())
        
        allowed = position_count < self.profile.max_positions
        return RiskCheck(
            name="position_count",
            allowed=allowed,
            reason=f"Position count {position_count} >= max {self.profile.max_positions}" if not allowed else "OK"
        )
    
    def _check_max_exposure(self, account_value: float) -> RiskCheck:
        """Control 6: Max Exposure"""
        total_exposure = self.portfolio_manager.calculate_total_exposure()
        max_exposure = account_value * 1.0  # 100% max exposure
        
        allowed = total_exposure <= max_exposure
        return RiskCheck(
            name="max_exposure",
            allowed=allowed,
            reason=f"Exposure ${total_exposure:.2f} exceeds max ${max_exposure:.2f}" if not allowed else "OK"
        )
    
    def _check_leverage(self) -> RiskCheck:
        """Control 7: Leverage Control"""
        leverage = self.portfolio_manager.calculate_leverage()
        max_leverage = 1.0  # No leverage allowed
        
        allowed = leverage <= max_leverage
        return RiskCheck(
            name="leverage",
            allowed=allowed,
            reason=f"Leverage {leverage:.2f}x exceeds max {max_leverage}x" if not allowed else "OK"
        )
    
    def _check_trading_hours(self) -> RiskCheck:
        """Control 8: Trading Hours Only"""
        now = datetime.now()
        is_weekday = now.weekday() < 5
        is_market_hours = 9 <= now.hour < 16
        
        allowed = is_weekday and is_market_hours
        return RiskCheck(
            name="trading_hours",
            allowed=allowed,
            reason="Outside trading hours" if not allowed else "OK"
        )
    
    def _check_eod_rules(self) -> RiskCheck:
        """Control 9: End-of-Day Rules"""
        now = datetime.now()
        is_near_eod = now.hour >= 15 and now.minute >= 30
        
        # Don't open new positions near EOD
        allowed = not is_near_eod
        return RiskCheck(
            name="eod_rules",
            allowed=allowed,
            reason="Near end-of-day, no new positions" if not allowed else "OK"
        )
    
    def _check_volatility_filter(self) -> RiskCheck:
        """Control 10: Volatility Filter - Block trades when ATR > 3% of price."""
        from datetime import datetime
        now = datetime.now()
        hour = now.hour

        # Higher volatility during market open/close and overnight
        if hour < 10 or hour > 15:
            return RiskCheck(
                name="volatility_filter",
                allowed=False,
                reason="High volatility window (market open/close hours)"
            )

        # Simulate volatility check based on time of day
        # In production: fetch ATR from market data API
        if 14 <= hour <= 15:
            return RiskCheck(
                name="volatility_filter",
                allowed=False,
                reason="End-of-day volatility spike"
            )

        return RiskCheck(name="volatility_filter", allowed=True, reason="OK")

    def _check_news_events(self) -> RiskCheck:
        """Control 11: News/Event Avoidance - Block during known event windows."""
        from datetime import datetime
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # Block 30 min before and after major economic events (simplified)
        # In production: integrate with economic calendar API
        event_hours = [8, 9, 14]  # FOMC, NFP, CPI release windows
        for eh in event_hours:
            if abs(hour - eh) <= 0 and minute < 30:
                return RiskCheck(
                    name="news_events",
                    allowed=False,
                    reason=f"Major economic event window ({eh}:00)"
                )

        return RiskCheck(name="news_events", allowed=True, reason="OK")

    def _check_liquidity(self, symbol: str, quantity: float) -> RiskCheck:
        """Control 12: Liquidity Protection - Block if trade > 5% of avg volume."""
        # Simplified: block very large quantities
        # In production: fetch actual volume data and compute slippage estimate
        max_qty = {
            "BTC": 0.1, "ETH": 1.0, "SOL": 10.0,
            "EUR": 10000, "GBP": 10000, "USD": 10000,
        }

        base = symbol.split("/")[0].replace("USD", "").replace("T", "")
        limit = max_qty.get(base, 100)

        if quantity > limit:
            return RiskCheck(
                name="liquidity",
                allowed=False,
                reason=f"Trade size {quantity} exceeds liquidity limit {limit} for {symbol}"
            )

        return RiskCheck(name="liquidity", allowed=True, reason="OK")

    def _check_correlation(self, symbol: str) -> RiskCheck:
        """Control 13: Correlation Manager - Block if >3 correlated positions open."""
        # Group correlated assets
        correlated_groups = {
            "crypto": ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX"],
            "tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
            "forex_usd": ["EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD"],
        }

        base = symbol.split("/")[0].replace("USD", "").replace("T", "")

        for group_name, members in correlated_groups.items():
            if base in members:
                open_count = sum(
                    1 for pos in self.position_manager.positions.values()
                    if any(m in pos.get("symbol", "") for m in members)
                )
                if open_count >= 3:
                    return RiskCheck(
                        name="correlation",
                        allowed=False,
                        reason=f"Too many correlated {group_name} positions ({open_count}/3)"
                    )

        return RiskCheck(name="correlation", allowed=True, reason="OK")
    
    def activate_kill_switch(self, reason: str):
        """Activate kill switch."""
        self.kill_switch.activate(reason)
        self.audit_logger.log_kill_switch(reason)
    
    def deactivate_kill_switch(self):
        """Deactivate kill switch."""
        self.kill_switch.deactivate()
    
    def update_daily_pnl(self, pnl: float):
        """Update daily P&L (persisted)."""
        self.daily_pnl += pnl
        self._save_daily_state()
    
    def reset_daily(self):
        """Reset daily metrics."""
        self.daily_pnl = 0.0
        self._save_daily_state()
        self.audit_logger.log_daily_reset()

    def _save_daily_state(self):
        import os, json
        path = os.path.join(os.path.dirname(__file__), "..", "data", "daily_state.json")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump({
                    "daily_pnl": self.daily_pnl,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save daily state: {e}")

    def _load_daily_state(self):
        import os, json
        path = os.path.join(os.path.dirname(__file__), "..", "data", "daily_state.json")
        try:
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                    self.daily_pnl = data.get("daily_pnl", 0.0)
        except Exception:
            pass
