"""
VIP Auto-Trade System
Only VIP users who agree get auto-trading.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

DATA_DIR = Path(__file__).parent.parent / "data" / "auto_trade"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class VIPAutoTrade:
    """Manage VIP auto-trade opt-ins and execution."""

    def __init__(self):
        self.vip_users = self._load_json("vip_users.json", {})
        self.trade_history = self._load_json("trade_history.json", [])
        self.portfolio = self._load_json("portfolio.json", {})

    def _load_json(self, filename: str, default):
        filepath = DATA_DIR / filename
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
        return default

    def _save_json(self, filename: str, data):
        filepath = DATA_DIR / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def add_vip_user(self, user_id: str, auto_trade: bool = False):
        """Add a VIP user."""
        self.vip_users[user_id] = {
            "user_id": user_id,
            "tier": "vip",
            "auto_trade": auto_trade,
            "added_at": datetime.now().isoformat(),
            "risk_profile": "moderate",  # default
            "max_position_size": 1000,  # max $1000 per trade
            "daily_loss_limit": 500,  # max $500 loss per day
        }
        self._save_json("vip_users.json", self.vip_users)

    def opt_in_auto_trade(self, user_id: str, risk_profile: str = "moderate") -> bool:
        """VIP user opts into auto-trading."""
        if user_id not in self.vip_users:
            return False

        self.vip_users[user_id]["auto_trade"] = True
        self.vip_users[user_id]["risk_profile"] = risk_profile

        # Set risk limits based on profile
        if risk_profile == "conservative":
            self.vip_users[user_id]["max_position_size"] = 500
            self.vip_users[user_id]["daily_loss_limit"] = 250
        elif risk_profile == "moderate":
            self.vip_users[user_id]["max_position_size"] = 1000
            self.vip_users[user_id]["daily_loss_limit"] = 500
        elif risk_profile == "aggressive":
            self.vip_users[user_id]["max_position_size"] = 2000
            self.vip_users[user_id]["daily_loss_limit"] = 1000

        self._save_json("vip_users.json", self.vip_users)
        return True

    def opt_out_auto_trade(self, user_id: str) -> bool:
        """VIP user opts out of auto-trading."""
        if user_id not in self.vip_users:
            return False

        self.vip_users[user_id]["auto_trade"] = False
        self._save_json("vip_users.json", self.vip_users)
        return True

    def get_auto_trade_users(self) -> List[Dict]:
        """Get all VIP users with auto-trade enabled."""
        return [u for u in self.vip_users.values() if u.get("auto_trade")]

    def can_auto_trade(self, user_id: str) -> bool:
        """Check if user can auto-trade."""
        user = self.vip_users.get(user_id)
        if not user:
            return False
        return user.get("auto_trade", False)

    def record_trade(self, user_id: str, trade: Dict[str, Any]):
        """Record a trade for a user."""
        trade_record = {
            "user_id": user_id,
            "symbol": trade.get("symbol"),
            "direction": trade.get("direction"),
            "quantity": trade.get("quantity"),
            "price": trade.get("price"),
            "timestamp": datetime.now().isoformat(),
            "status": "executed",
        }

        self.trade_history.append(trade_record)
        self._save_json("trade_history.json", self.trade_history)

    def get_user_trades(self, user_id: str) -> List[Dict]:
        """Get trade history for a user."""
        return [t for t in self.trade_history if t.get("user_id") == user_id]

    def format_opt_in_message(self) -> str:
        """Format opt-in message for VIP users."""
        return (
            "🤖 <b>VIP AUTO-TRADE</b>\n\n"
            "Let the AI trade automatically for you.\n\n"
            "<b>How it works:</b>\n"
            "• AI analyzes market 24/7\n"
            "• Automatically executes trades\n"
            "• You keep the profits\n\n"
            "<b>Risk Profiles:</b>\n"
            "• Conservative: $500/trade, $250/day max loss\n"
            "• Moderate: $1000/trade, $500/day max loss\n"
            "• Aggressive: $2000/trade, $1000/day max loss\n\n"
            "<b>Commands:</b>\n"
            "/auto_trade_on conservative - Enable auto-trade\n"
            "/auto_trade_on moderate - Enable auto-trade\n"
            "/auto_trade_on aggressive - Enable auto-trade\n"
            "/auto_trade_off - Disable auto-trade\n"
            "/auto_status - Check your status"
        )

    def format_status(self, user_id: str) -> str:
        """Format user status."""
        user = self.vip_users.get(user_id)
        if not user:
            return "You are not a VIP user."

        auto_trade = "ON" if user.get("auto_trade") else "OFF"
        risk = user.get("risk_profile", "N/A")
        max_pos = user.get("max_position_size", 0)
        daily_limit = user.get("daily_loss_limit", 0)

        trades = self.get_user_trades(user_id)

        msg = (
            f"📊 <b>YOUR VIP STATUS</b>\n\n"
            f"<b>Auto-Trade:</b> {auto_trade}\n"
            f"<b>Risk Profile:</b> {risk}\n"
            f"<b>Max Position:</b> ${max_pos}\n"
            f"<b>Daily Loss Limit:</b> ${daily_limit}\n"
            f"<b>Total Trades:</b> {len(trades)}\n"
        )

        return msg

    def get_stats(self) -> Dict[str, Any]:
        """Get auto-trade statistics."""
        total_users = len(self.vip_users)
        auto_trade_users = len(self.get_auto_trade_users())
        total_trades = len(self.trade_history)

        return {
            "total_vip_users": total_users,
            "auto_trade_enabled": auto_trade_users,
            "total_trades": total_trades,
        }


# Global instance
vip_auto = VIPAutoTrade()
