"""
Tiered Notification System
Different Telegram bots for different subscription tiers.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Tier Configuration
TIER_CONFIG = {
    "free": {
        "name": "Free",
        "price": 0,
        "max_signals_per_day": 3,
        "max_trades_per_day": 2,
        "features": ["basic_signals", "daily_summary"],
        "bot_token_env": "TELEGRAM_BOT_TOKEN_FREE",
        "chat_ids_env": "TELEGRAM_CHAT_IDS_FREE",
    },
    "premium": {
        "name": "Premium",
        "price": 49,
        "max_signals_per_day": 15,
        "max_trades_per_day": 10,
        "features": ["all_signals", "trade_alerts", "daily_summary", "kill_switch_alerts"],
        "bot_token_env": "TELEGRAM_BOT_TOKEN_PREMIUM",
        "chat_ids_env": "TELEGRAM_CHAT_IDS_PREMIUM",
    },
    "vip": {
        "name": "VIP",
        "price": 199,
        "max_signals_per_day": -1,  # Unlimited
        "max_trades_per_day": -1,    # Unlimited
        "features": ["all_signals", "trade_alerts", "daily_summary", "kill_switch_alerts", "error_alerts", "portfolio_updates"],
        "bot_token_env": "TELEGRAM_BOT_TOKEN_VIP",
        "chat_ids_env": "TELEGRAM_CHAT_IDS_VIP",
    }
}


class TieredNotifier:
    """Manage notifications for different subscription tiers."""

    def __init__(self):
        self.tier_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: {"signals": 0, "trades": 0})
        self.last_reset: Dict[str, datetime] = {}
        self.subscribers: Dict[str, List[str]] = {}  # tier -> list of chat_ids
        self.signal_log: List[Dict[str, Any]] = []

        self._load_subscribers()

    def _load_subscribers(self):
        """Load subscribers from .env or config file."""
        for tier, config in TIER_CONFIG.items():
            bot_token = os.getenv(config["bot_token_env"], "")
            chat_ids_str = os.getenv(config["chat_ids_env"], "")

            if bot_token and chat_ids_str:
                chat_ids = [cid.strip() for cid in chat_ids_str.split(",") if cid.strip()]
                self.subscribers[tier] = chat_ids
                logger.info(f"Loaded {len(chat_ids)} subscribers for {tier} tier")
            else:
                self.subscribers[tier] = []

    def _reset_usage_if_needed(self, tier: str):
        """Reset daily usage counters at midnight."""
        today = datetime.now().date()
        if tier not in self.last_reset or self.last_reset[tier].date() < today:
            self.tier_usage[tier] = {"signals": 0, "trades": 0}
            self.last_reset[tier] = datetime.now()

    def can_send_signal(self, tier: str) -> bool:
        """Check if tier can receive more signals today."""
        self._reset_usage_if_needed(tier)
        config = TIER_CONFIG.get(tier, TIER_CONFIG["free"])
        max_signals = config["max_signals_per_day"]

        if max_signals == -1:  # Unlimited
            return True

        return self.tier_usage[tier]["signals"] < max_signals

    def can_send_trade_alert(self, tier: str) -> bool:
        """Check if tier can receive more trade alerts today."""
        self._reset_usage_if_needed(tier)
        config = TIER_CONFIG.get(tier, TIER_CONFIG["free"])
        max_trades = config["max_trades_per_day"]

        if max_trades == -1:  # Unlimited
            return True

        return self.tier_usage[tier]["trades"] < max_trades

    def send_signal(self, signal: Dict[str, Any], target_tiers: List[str] = None):
        """
        Send trading signal to all eligible subscribers.

        Args:
            signal: Signal data
            target_tiers: List of tiers to notify (default: all)
        """
        if target_tiers is None:
            target_tiers = ["free", "premium", "vip"]

        for tier in target_tiers:
            if not self.can_send_signal(tier):
                logger.info(f"Skipping {tier} tier - daily signal limit reached")
                continue

            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            chat_ids = self.subscribers.get(tier, [])

            if not bot_token or not chat_ids:
                continue

            # Format message based on tier
            message = self._format_signal_message(signal, tier)

            # Send to all subscribers of this tier
            for chat_id in chat_ids:
                self._send_telegram(bot_token, chat_id, message)

            # Increment usage
            self._reset_usage_if_needed(tier)
            self.tier_usage[tier]["signals"] += 1

            # Log
            self.signal_log.append({
                "tier": tier,
                "signal": signal,
                "timestamp": datetime.now().isoformat(),
                "recipients": len(chat_ids)
            })

            logger.info(f"Signal sent to {tier} tier ({len(chat_ids)} recipients)")

    def send_trade_alert(self, trade: Dict[str, Any], target_tiers: List[str] = None):
        """Send trade execution alert."""
        if target_tiers is None:
            target_tiers = ["premium", "vip"]

        for tier in target_tiers:
            if not self.can_send_trade_alert(tier):
                continue

            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            chat_ids = self.subscribers.get(tier, [])

            if not bot_token or not chat_ids:
                continue

            message = self._format_trade_message(trade)

            for chat_id in chat_ids:
                self._send_telegram(bot_token, chat_id, message)

            self._reset_usage_if_needed(tier)
            self.tier_usage[tier]["trades"] += 1

    def send_daily_summary(self, summary: Dict[str, Any]):
        """Send daily summary to all tiers."""
        for tier in ["free", "premium", "vip"]:
            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            chat_ids = self.subscribers.get(tier, [])

            if not bot_token or not chat_ids:
                continue

            message = self._format_summary_message(summary)

            for chat_id in chat_ids:
                self._send_telegram(bot_token, chat_id, message)

    def send_kill_switch(self, reason: str):
        """Send kill switch alert to all tiers."""
        for tier in ["premium", "vip"]:
            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            chat_ids = self.subscribers.get(tier, [])

            if not bot_token or not chat_ids:
                continue

            message = (
                f"🛑 <b>KILL SWITCH ACTIVATED</b>\n\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"All trading has been halted."
            )

            for chat_id in chat_ids:
                self._send_telegram(bot_token, chat_id, message)

    def _format_signal_message(self, signal: Dict[str, Any], tier: str) -> str:
        """Format signal message based on tier."""
        direction = signal.get("direction", "hold").upper()
        symbol = signal.get("symbol", "???")
        price = signal.get("price", 0)
        confidence = signal.get("confidence", 0)
        reason = signal.get("reason", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if direction == "BUY":
            emoji = "📈"
        elif direction == "SELL":
            emoji = "📉"
        else:
            emoji = "⏸️"

        # Free tier gets basic info
        if tier == "free":
            message = (
                f"{emoji} <b>{direction} {symbol}</b>\n"
                f"Price: ${price:.2f}\n"
                f"Confidence: {confidence:.0%}\n"
                f"Time: {timestamp}\n\n"
                f"<i>Upgrade for full analysis</i>"
            )
        # Premium gets more detail
        elif tier == "premium":
            message = (
                f"{emoji} <b>{direction} SIGNAL</b>\n\n"
                f"<b>Symbol:</b> {symbol}\n"
                f"<b>Price:</b> ${price:.2f}\n"
                f"<b>Confidence:</b> {confidence:.1%}\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {timestamp}\n\n"
                f"<i>Signals left today: {TIER_CONFIG['premium']['max_signals_per_day'] - self.tier_usage['premium']['signals']}</i>"
            )
        # VIP gets everything
        else:
            message = (
                f"{emoji} <b>{direction} SIGNAL</b>\n\n"
                f"<b>Symbol:</b> {symbol}\n"
                f"<b>Price:</b> ${price:.2f}\n"
                f"<b>Confidence:</b> {confidence:.1%}\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {timestamp}\n\n"
                f"🎯 <i>Unlimited signals</i>"
            )

        return message

    def _format_trade_message(self, trade: Dict[str, Any]) -> str:
        """Format trade alert message."""
        side = trade.get("side", "").upper()
        symbol = trade.get("symbol", "???")
        qty = trade.get("quantity", 0)
        price = trade.get("price", 0)
        status = trade.get("status", "")

        emoji = "🟢" if side == "BUY" else "🔴"

        return (
            f"{emoji} <b>TRADE EXECUTED</b>\n\n"
            f"<b>Action:</b> {side}\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Quantity:</b> {qty}\n"
            f"<b>Price:</b> ${price:.2f}\n"
            f"<b>Status:</b> {status}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def _format_summary_message(self, summary: Dict[str, Any]) -> str:
        """Format daily summary message."""
        pnl = summary.get("daily_pnl", 0)
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        trades = summary.get("trades_today", 0)
        win_rate = summary.get("win_rate", 0)
        portfolio = summary.get("portfolio_value", 0)

        return (
            f"📊 <b>DAILY SUMMARY</b>\n\n"
            f"<b>Portfolio:</b> ${portfolio:,.2f}\n"
            f"{pnl_emoji} <b>Daily P&L:</b> ${pnl:,.2f}\n"
            f"<b>Trades:</b> {trades}\n"
            f"<b>Win Rate:</b> {win_rate:.1%}"
        )

    def _send_telegram(self, bot_token: str, chat_id: str, message: str) -> bool:
        """Send message via Telegram bot."""
        if not HAS_REQUESTS:
            return False

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed for {chat_id}: {e}")
            return False

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics."""
        stats = {}
        for tier in TIER_CONFIG:
            self._reset_usage_if_needed(tier)
            config = TIER_CONFIG[tier]
            usage = self.tier_usage[tier]

            stats[tier] = {
                "signals_today": usage["signals"],
                "max_signals": config["max_signals_per_day"],
                "trades_today": usage["trades"],
                "max_trades": config["max_trades_per_day"],
                "subscribers": len(self.subscribers.get(tier, []))
            }

        return stats

    def get_config(self) -> Dict[str, Any]:
        """Get tier configuration."""
        return TIER_CONFIG
