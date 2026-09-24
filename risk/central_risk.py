"""
Central Risk Engine - Cross-market master controller.
Sits above all 3 engines and enforces portfolio-level risk.
"""
import os
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

DAILY_STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "central_risk_state.json")


class TradeDecision:
    """Result of a risk check."""
    def __init__(self, allowed: bool, reason: str = "OK", checks: Optional[List[Dict]] = None):
        self.allowed = allowed
        self.reason = reason
        self.checks = checks or []
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "checks": self.checks,
            "timestamp": self.timestamp,
        }


class CentralRiskEngine:
    """
    Master risk controller sitting above all 3 market engines.
    Enforces: global kill switch, daily loss, max drawdown, cross-market correlation,
    total portfolio exposure.
    """

    def __init__(self, config: Optional[Dict] = None):
        self._config = config or {}
        self._lock = threading.Lock()

        # Global limits
        self.max_daily_loss = self._config.get("max_daily_loss", 0.05)     # 5%
        self.max_drawdown = self._config.get("max_drawdown", 0.10)         # 10%
        self.max_total_exposure = self._config.get("max_total_exposure", 0.80)  # 80%
        self.max_correlated_positions = self._config.get("max_correlated", 3)

        # State (persisted)
        self.daily_pnl = 0.0
        self.initial_capital = 100000.0
        self.current_capital = 100000.0
        self.peak_capital = 100000.0
        self.kill_switch_active = False
        self.kill_switch_reason = ""
        self.trade_count = 0

        # Per-market position tracking
        self.positions: Dict[str, Dict] = {}  # key = "market:symbol"
        self.daily_trade_count: Dict[str, int] = {"stock": 0, "forex": 0, "crypto": 0}

        # Cross-market correlation groups
        self.correlation_groups = {
            "tech_stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
            "crypto_all": ["BTC/USD", "ETH/USD", "SOL/USD", "BNB/USD", "XRP/USD", "ADA/USD", "DOGE/USD", "AVAX/USD"],
            "forex_usd": ["EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD"],
            "risk_assets": ["TSLA", "NVDA", "BTC/USD", "ETH/USD", "SOL/USD"],  # Cross-market risk
        }

        self._load_state()

    # ---- Core Risk Gate ----

    def approve_trade(self, market: str, symbol: str, direction: str,
                      quantity: float, price: float, account_value: float) -> TradeDecision:
        """
        Central gatekeeper: every trade from every engine must pass through here.
        Returns TradeDecision with allowed=True/False.
        """
        with self._lock:
            checks = []

            # 1. Kill switch
            if self.kill_switch_active:
                return TradeDecision(False, f"Kill switch active: {self.kill_switch_reason}")

            # 2. Daily loss limit
            daily_loss_limit = account_value * self.max_daily_loss
            if abs(self.daily_pnl) >= daily_loss_limit and self.daily_pnl < 0:
                checks.append({"name": "daily_loss", "allowed": False,
                               "reason": f"Daily loss limit reached: ${self.daily_pnl:.2f}"})
                return self._decision_from_checks(checks)

            # 3. Max drawdown
            if self.peak_capital > 0:
                drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
                if drawdown >= self.max_drawdown:
                    checks.append({"name": "max_drawdown", "allowed": False,
                                   "reason": f"Drawdown {drawdown:.1%} exceeds limit {self.max_drawdown:.0%}"})
                    return self._decision_from_checks(checks)

            # 4. Market-specific daily trade limit
            max_trades = self._config.get("max_daily_trades", {}).get(market, 20)
            if self.daily_trade_count.get(market, 0) >= max_trades:
                checks.append({"name": "daily_trade_limit", "allowed": False,
                               "reason": f"{market} daily trade limit reached ({max_trades})"})
                return self._decision_from_checks(checks)

            # 5. Total portfolio exposure
            total_exposure = sum(
                pos.get("quantity", 0) * pos.get("price", 0)
                for pos in self.positions.values()
            )
            new_exposure = total_exposure + (quantity * price)
            exposure_pct = new_exposure / account_value
            if exposure_pct > self.max_total_exposure:
                checks.append({"name": "total_exposure", "allowed": False,
                               "reason": f"Total exposure {exposure_pct:.1%} exceeds {self.max_total_exposure:.0%}"})
                return self._decision_from_checks(checks)

            # 6. Cross-market correlation check
            corr_issue = self._check_correlation(market, symbol)
            if corr_issue:
                checks.append({"name": "correlation", "allowed": False, "reason": corr_issue})
                return self._decision_from_checks(checks)

            # 7. Position size check (per-market)
            pos_size_pct = (quantity * price) / account_value
            max_pos = self._config.get("max_position_size", {}).get(market, 0.10)
            if pos_size_pct > max_pos:
                checks.append({"name": "position_size", "allowed": False,
                               "reason": f"Position size {pos_size_pct:.1%} exceeds {max_pos:.0%} limit"})
                return self._decision_from_checks(checks)

            # All checks passed
            return TradeDecision(True, "All risk checks passed", checks)

    def _decision_from_checks(self, checks: List[Dict]) -> TradeDecision:
        failed = [c for c in checks if not c.get("allowed", True)]
        if failed:
            return TradeDecision(False, "; ".join(c["reason"] for c in failed), checks)
        return TradeDecision(True, "All checks passed", checks)

    # ---- Position Management ----

    def open_position(self, market: str, symbol: str, direction: str,
                      quantity: float, price: float):
        """Record a new position."""
        key = f"{market}:{symbol}"
        self.positions[key] = {
            "market": market,
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "entry_price": price,
            "entry_time": datetime.now().isoformat(),
            "highest_price": price,
        }
        self.daily_trade_count[market] = self.daily_trade_count.get(market, 0) + 1
        self.trade_count += 1
        self._save_state()

    def close_position(self, market: str, symbol: str, exit_price: float) -> float:
        """Close a position and return realized P&L."""
        key = f"{market}:{symbol}"
        pos = self.positions.pop(key, None)
        if not pos:
            return 0.0

        entry = pos["entry_price"]
        quantity = pos["quantity"]
        direction = pos["direction"]

        if direction == "BUY":
            pnl = (exit_price - entry) * quantity
        else:
            pnl = (entry - exit_price) * quantity

        self.daily_pnl += pnl
        self.current_capital += pnl
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

        # Auto-kill switch on drawdown
        if self.peak_capital > 0:
            drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
            if drawdown >= self.max_drawdown:
                self.activate_kill_switch(f"Auto-activated: Drawdown {drawdown:.1%}")

        self._save_state()
        return pnl

    def update_position_price(self, market: str, symbol: str, current_price: float):
        """Update highest price for trailing stop tracking."""
        key = f"{market}:{symbol}"
        pos = self.positions.get(key)
        if pos and current_price > pos.get("highest_price", 0):
            pos["highest_price"] = current_price

    # ---- Kill Switch ----

    def activate_kill_switch(self, reason: str):
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        self._save_state()
        logger.critical(f"CENTRAL RISK: Kill switch activated - {reason}")

    def deactivate_kill_switch(self):
        self.kill_switch_active = False
        self.kill_switch_reason = ""
        self._save_state()
        logger.info("Central risk: Kill switch deactivated")

    # ---- Correlation Check ----

    def _check_correlation(self, market: str, symbol: str) -> Optional[str]:
        """Check if adding this position creates excessive correlation."""
        for group_name, members in self.correlation_groups.items():
            if any(m in symbol for m in members):
                count = sum(
                    1 for key, pos in self.positions.items()
                    if any(m in pos["symbol"] for m in members)
                )
                if count >= self.max_correlated_positions:
                    return f"Too many correlated positions in {group_name} ({count}/{self.max_correlated_positions})"
        return None

    # ---- Summary ----

    def get_portfolio_summary(self) -> Dict:
        """Aggregated view across all 3 markets."""
        market_positions = {"stock": 0, "forex": 0, "crypto": 0}
        for key, pos in self.positions.items():
            market = pos.get("market", "unknown")
            market_positions[market] = market_positions.get(market, 0) + 1

        total_exposure = sum(
            pos.get("quantity", 0) * pos.get("price", 0)
            for pos in self.positions.values()
        )

        drawdown = 0.0
        if self.peak_capital > 0:
            drawdown = (self.peak_capital - self.current_capital) / self.peak_capital

        return {
            "daily_pnl": self.daily_pnl,
            "current_capital": self.current_capital,
            "total_exposure": total_exposure,
            "exposure_pct": total_exposure / self.current_capital if self.current_capital else 0,
            "drawdown": drawdown,
            "positions": market_positions,
            "total_positions": len(self.positions),
            "trade_count": self.trade_count,
            "kill_switch": self.kill_switch_active,
            "daily_trades": self.daily_trade_count.copy(),
        }

    # ---- Persistence ----

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(DAILY_STATE_FILE), exist_ok=True)
            with open(DAILY_STATE_FILE, "w") as f:
                json.dump({
                    "daily_pnl": self.daily_pnl,
                    "initial_capital": self.initial_capital,
                    "current_capital": self.current_capital,
                    "peak_capital": self.peak_capital,
                    "kill_switch_active": self.kill_switch_active,
                    "kill_switch_reason": self.kill_switch_reason,
                    "trade_count": self.trade_count,
                    "daily_trade_count": self.daily_trade_count,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "positions": self.positions,
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save central risk state: {e}")

    def _load_state(self):
        try:
            if os.path.exists(DAILY_STATE_FILE):
                with open(DAILY_STATE_FILE) as f:
                    data = json.load(f)
                if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                    self.daily_pnl = data.get("daily_pnl", 0.0)
                    self.initial_capital = data.get("initial_capital", 100000.0)
                    self.current_capital = data.get("current_capital", 100000.0)
                    self.peak_capital = data.get("peak_capital", 100000.0)
                    self.kill_switch_active = data.get("kill_switch_active", False)
                    self.kill_switch_reason = data.get("kill_switch_reason", "")
                    self.trade_count = data.get("trade_count", 0)
                    self.daily_trade_count = data.get("daily_trade_count", {"stock": 0, "forex": 0, "crypto": 0})
                    self.positions = data.get("positions", {})
                    if self.kill_switch_active:
                        logger.warning(f"Kill switch restored: {self.kill_switch_reason}")
        except Exception:
            pass

    def reset_daily(self):
        """Reset daily counters (call at midnight)."""
        self.daily_pnl = 0.0
        self.daily_trade_count = {"stock": 0, "forex": 0, "crypto": 0}
        self._save_state()
