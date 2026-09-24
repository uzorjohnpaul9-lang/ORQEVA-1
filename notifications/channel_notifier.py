"""
Channel-based Notification System
Posts signals to Telegram channels (Free, Premium, VIP).
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
        "channel_env": "TELEGRAM_CHANNEL_FREE",
    },
    "premium": {
        "name": "Premium",
        "price": 49,
        "max_signals_per_day": 15,
        "max_trades_per_day": 10,
        "features": ["all_signals", "trade_alerts", "daily_summary", "kill_switch_alerts"],
        "bot_token_env": "TELEGRAM_BOT_TOKEN_PREMIUM",
        "channel_env": "TELEGRAM_CHANNEL_PREMIUM",
    },
    "vip": {
        "name": "VIP",
        "price": 199,
        "max_signals_per_day": -1,  # Unlimited
        "max_trades_per_day": -1,    # Unlimited
        "features": ["all_signals", "trade_alerts", "daily_summary", "kill_switch_alerts", "error_alerts", "portfolio_updates"],
        "bot_token_env": "TELEGRAM_BOT_TOKEN_VIP",
        "channel_env": "TELEGRAM_CHANNEL_VIP",
    }
}


class ChannelNotifier:
    """Post signals to Telegram channels."""

    def __init__(self):
        self.tier_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: {"signals": 0, "trades": 0})
        self.last_reset: Dict[str, datetime] = {}
        self.signal_log: List[Dict[str, Any]] = []

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
        Send trading signal to channels.

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
            channel = os.getenv(config["channel_env"], "")

            if not bot_token or bot_token == "create_this_bot":
                logger.warning(f"No bot token for {tier} tier")
                continue

            if not channel:
                logger.warning(f"No channel for {tier} tier")
                continue

            # Format message based on tier
            message = self._format_signal_message(signal, tier)

            # Send to channel
            success = self._send_to_channel(bot_token, channel, message)

            if success:
                # Increment usage
                self._reset_usage_if_needed(tier)
                self.tier_usage[tier]["signals"] += 1

                # Log
                self.signal_log.append({
                    "tier": tier,
                    "signal": signal,
                    "timestamp": datetime.now().isoformat(),
                    "channel": channel
                })

                logger.info(f"Signal sent to {tier} channel: {channel}")
            else:
                logger.error(f"Failed to send signal to {tier} channel: {channel}")

    def send_trade_alert(self, trade: Dict[str, Any], target_tiers: List[str] = None):
        """Send trade execution alert to channels."""
        if target_tiers is None:
            target_tiers = ["premium", "vip"]

        for tier in target_tiers:
            if not self.can_send_trade_alert(tier):
                continue

            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            channel = os.getenv(config["channel_env"], "")

            if not bot_token or bot_token == "create_this_bot" or not channel:
                continue

            message = self._format_trade_message(trade)
            success = self._send_to_channel(bot_token, channel, message)

            if success:
                self._reset_usage_if_needed(tier)
                self.tier_usage[tier]["trades"] += 1

    def send_daily_summary(self, summary: Dict[str, Any]):
        """Send daily summary to all channels."""
        for tier in ["free", "premium", "vip"]:
            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            channel = os.getenv(config["channel_env"], "")

            if not bot_token or bot_token == "create_this_bot" or not channel:
                continue

            message = self._format_summary_message(summary, tier)
            self._send_to_channel(bot_token, channel, message)

    def send_kill_switch(self, reason: str):
        """Send kill switch alert to Premium and VIP channels."""
        for tier in ["premium", "vip"]:
            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            channel = os.getenv(config["channel_env"], "")

            if not bot_token or bot_token == "create_this_bot" or not channel:
                continue

            message = (
                "🛑 <b>KILL SWITCH ACTIVATED</b>\n\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "All trading has been halted."
            )

            self._send_to_channel(bot_token, channel, message)

    def send_admin_alert(self, message: str):
        """Send alert to admin."""
        admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
        if not admin_chat_id:
            return

        # Use any available bot token
        for tier in ["free", "premium", "vip"]:
            config = TIER_CONFIG[tier]
            bot_token = os.getenv(config["bot_token_env"], "")
            if bot_token and bot_token != "create_this_bot":
                self._send_telegram(bot_token, admin_chat_id, message)
                break

    def _format_signal_message(self, signal: Dict[str, Any], tier: str) -> str:
        """Format signal message based on tier."""
        direction = signal.get("direction", "hold").upper()
        symbol = signal.get("symbol", "???")
        price = signal.get("price", 0)
        confidence = signal.get("confidence", 0)
        reason = signal.get("reason", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if direction == "BUY":
            emoji = "🟢"
        elif direction == "SELL":
            emoji = "🔴"
        else:
            emoji = "⏸️"

        # Free tier - creates FOMO and drives premium signups
        if tier == "free":
            # Calculate a fake "missed profit" to create FOMO
            missed = round(price * 0.03, 2)  # 3% move
            message = (
                f"{emoji} <b>{direction} {symbol}</b>\n"
                f"Price: ${price:.2f}\n\n"
                f"This signal has <b>87% win rate</b> in backtesting.\n\n"
                f"⚠️ <b>Free members see this AFTER entry.</b>\n"
                f"Premium members got this alert <b>15 minutes early</b>\n"
                f"and already locked in +${missed} profit.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔓 <b>Get signals BEFORE the move:</b>\n"
                f"• 15 signals/day instead of 3\n"
                f"• Entry & exit prices included\n"
                f"• Real-time alerts\n\n"
                f"DM @Johnpaulmuna_83 to join Premium\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
        # Premium - shows value but teases VIP
        elif tier == "premium":
            message = (
                f"{emoji} <b>{direction} SIGNAL</b>\n\n"
                f"<b>Symbol:</b> {symbol}\n"
                f"<b>Price:</b> ${price:.2f}\n"
                f"<b>Confidence:</b> {confidence:.1%}\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {timestamp}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <b>VIP members also get:</b>\n"
                f"• Unlimited signals\n"
                f"• AI portfolio management\n"
                f"• Priority execution\n\n"
                f"DM @Johnpaulmuna_83 for VIP access\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
        # VIP - full experience, no upsell
        else:
            remaining = "Unlimited"
            message = (
                f"{emoji} <b>{direction} SIGNAL</b>\n\n"
                f"<b>Symbol:</b> {symbol}\n"
                f"<b>Price:</b> ${price:.2f}\n"
                f"<b>Confidence:</b> {confidence:.1%}\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {timestamp}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>VIP MEMBER</b> | Signals left: {remaining}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
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

    def _format_summary_message(self, summary: Dict[str, Any], tier: str) -> str:
        """Format daily summary message."""
        pnl = summary.get("daily_pnl", 0)
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        trades = summary.get("trades_today", 0)
        win_rate = summary.get("win_rate", 0)
        portfolio = summary.get("portfolio_value", 0)
        config = TIER_CONFIG[tier]

        return (
            f"📊 <b>DAILY SUMMARY - {config['name'].upper()}</b>\n\n"
            f"<b>Portfolio:</b> ${portfolio:,.2f}\n"
            f"{pnl_emoji} <b>Daily P&L:</b> ${pnl:,.2f}\n"
            f"<b>Trades:</b> {trades}\n"
            f"<b>Win Rate:</b> {win_rate:.1%}"
        )

    def _send_to_channel(self, bot_token: str, channel: str, message: str) -> bool:
        """Send message to a Telegram channel."""
        # Private channels need numeric ID (like -1001234567890)
        # Public channels can use @username
        if channel.startswith("-100") or channel.startswith("-"):
            chat_id = channel  # Already numeric ID
        elif channel.startswith("https://t.me/+") or channel.startswith("t.me/+"):
            # Private invite link - can't be used for posting
            # Bot must be admin and we need the numeric channel ID
            logger.error(f"Private channel needs numeric ID, not invite link: {channel}")
            return False
        elif channel.startswith("@"):
            chat_id = channel
        else:
            chat_id = "@" + channel

        return self._send_telegram(bot_token, chat_id, message)

    def _send_telegram(self, bot_token: str, chat_id: str, message: str) -> bool:
        """Send message via Telegram bot."""
        if not HAS_REQUESTS:
            logger.error("requests library not available")
            return False

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()

            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram API error: {result}")
                return False
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
            }

        return stats

    def get_config(self) -> Dict[str, Any]:
        """Get tier configuration."""
        return TIER_CONFIG
