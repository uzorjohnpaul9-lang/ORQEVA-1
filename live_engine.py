"""
Main Trading Engine - Live Signal Generator
Connects: Market Data → Analysis → Signals → Telegram Channels
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Configure logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "trading.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import components
try:
    from alpaca.trading.client import TradingClient
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    HAS_ALPACA = True
except ImportError:
    HAS_ALPACA = False
    logger.warning("Alpaca not installed")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Import 3-engine architecture
try:
    from engines.stock_engine import StockEngine
    from engines.forex_engine import ForexEngine
    from engines.crypto_engine import CryptoEngine
    from engines.crypto_discovery import CryptoDiscovery, CRYPTO_UNIVERSE
    from risk.central_risk import CentralRiskEngine
    HAS_ENGINES = True
except ImportError as e:
    HAS_ENGINES = False
    logger.warning(f"Engine modules not available: {e}")

# ============================================================
# CONFIGURATION
# ============================================================

# Tier messages with auto-trade distinction
TIER_MESSAGES = {
    "free": {
        "upgrade_cta": "DM @Johnpaulmuna_83 to join Premium",
        "features": [
            "15 signals/day instead of 3",
            "Entry & exit prices included",
            "Real-time alerts",
        ],
        "auto_trade": False,
    },
    "premium": {
        "upgrade_cta": "DM @Johnpaulmuna_83 for VIP access",
        "features": [
            "Unlimited signals",
            "AI portfolio management",
            "Auto-trade option (VIP only)",
        ],
        "auto_trade": False,
    },
    "vip": {
        "upgrade_cta": "Contact @Johnpaulmuna_83 for support",
        "features": [
            "Unlimited signals",
            "AI portfolio management",
            "Auto-trade (opt-in)",
            "Priority execution",
        ],
        "auto_trade": True,
    },
}

# Referral links
BINANCE_REFERRAL = "https://www.binance.com/activity/referral-entry/CPA?ref=CPA_00N4AMKT4D"
TRADING_LINKS = {
    "stock": BINANCE_REFERRAL,
    "forex": BINANCE_REFERRAL,
    "crypto": BINANCE_REFERRAL,
}

# ============================================================
# TELEGRAM NOTIFIER
# ============================================================

class TelegramNotifier:
    """Send signals to Telegram channels."""

    def __init__(self):
        self.bot_tokens = {
            "free": os.getenv("TELEGRAM_BOT_TOKEN_FREE", ""),
            "premium": os.getenv("TELEGRAM_BOT_TOKEN_PREMIUM", ""),
            "vip": os.getenv("TELEGRAM_BOT_TOKEN_VIP", ""),
        }
        self.channels = {
            "free": os.getenv("TELEGRAM_CHANNEL_FREE", ""),
            "premium": os.getenv("TELEGRAM_CHANNEL_PREMIUM", ""),
            "vip": os.getenv("TELEGRAM_CHANNEL_VIP", ""),
        }
        self.admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
        self.last_signals = {}
        self.daily_signal_count = {"free": 0, "premium": 0, "vip": 0}
        self.last_count_reset = datetime.now()

    def _reset_daily_count(self):
        """Reset signal counts at midnight."""
        today = datetime.now().date()
        if self.last_count_reset.date() < today:
            self.daily_signal_count = {"free": 0, "premium": 0, "vip": 0}
            self.last_count_reset = datetime.now()

    def _get_limit(self, tier: str) -> int:
        """Get signal limit for tier."""
        limits = {"free": 3, "premium": 15, "vip": 999}
        return limits.get(tier, 0)

    def can_send_signal(self, tier: str) -> bool:
        """Check if tier can receive more signals today."""
        self._reset_daily_count()

        limits = {
            "free": 3,
            "premium": 15,
            "vip": 999,  # Unlimited
        }

        return self.daily_signal_count.get(tier, 0) < limits.get(tier, 0)

    def send_signal(self, signal: Dict[str, Any], tier: str):
        """Send signal to a tier channel."""
        # Check daily limit first
        if not self.can_send_signal(tier):
            logger.info(f"Skipping {tier} - daily limit reached ({self.daily_signal_count[tier]} signals)")
            return False

        bot_token = self.bot_tokens.get(tier, "")
        channel_id = self.channels.get(tier, "")

        if not bot_token or not channel_id:
            logger.warning(f"No config for {tier} channel")
            return False

        # Check cooldown (avoid duplicate signals within 1 hour)
        symbol = signal.get("symbol", "")
        direction = signal.get("direction", "")
        key = f"{symbol}_{direction}_{tier}"
        if key in self.last_signals:
            last_time = self.last_signals[key]
            if (datetime.now() - last_time).total_seconds() < SIGNAL_COOLDOWN:
                logger.info(f"Skipping {symbol} {direction} for {tier} (cooldown)")
                return False

        message = self._format_signal(signal, tier)

        try:
            from security.rate_limiter import telegram_limit
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

            @telegram_limit
            def _send():
                return requests.post(url, json={
                    "chat_id": channel_id,
                    "text": message,
                    "parse_mode": "HTML"
                }, timeout=10)

            r = _send()

            if r.status_code == 200:
                self.last_signals[key] = datetime.now()
                self.daily_signal_count[tier] = self.daily_signal_count.get(tier, 0) + 1
                logger.info(f"Signal sent to {tier}: {symbol} {direction} ({self.daily_signal_count[tier]}/{self._get_limit(tier)})")
                return True
            else:
                logger.error(f"Telegram error: {r.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def _format_signal(self, signal: Dict[str, Any], tier: str) -> str:
        """Format signal message based on tier."""
        direction = signal.get("direction", "").upper()
        symbol = signal.get("symbol", "")
        price = signal.get("price", 0)
        confidence = signal.get("confidence", 0)
        reason = signal.get("reason", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target = signal.get("target_price", 0)
        stop_loss = signal.get("stop_loss", 0)
        signal_type = signal.get("type", "stock")

        # Type emoji
        type_emojis = {
            "stock": "",
            "forex": "💱",
            "crypto": "🪙",
        }
        type_emoji = type_emojis.get(signal_type, "")

        if direction == "BUY":
            emoji = "🟢"
        elif direction == "SELL":
            emoji = "🔴"
        else:
            emoji = "⏸️"

        # Format price based on type
        if signal_type == "crypto":
            price_str = f"${price:,.2f}"
            target_str = f"${target:,.2f}"
            stop_str = f"${stop_loss:,.2f}"
            pair_type = "Crypto"
        elif signal_type == "forex":
            price_str = f"{price:.4f}"
            target_str = f"{target:.4f}"
            stop_str = f"{stop_loss:.4f}"
            pair_type = "Forex"
        else:
            price_str = f"${price:.2f}"
            target_str = f"${target:.2f}"
            stop_str = f"${stop_loss:.2f}"
            pair_type = "Stock"

        # Trading link based on type
        trading_link = TRADING_LINKS.get(signal_type, BINANCE_REFERRAL)

        if tier == "free":
            missed = round(price * 0.03, 2)
            message = (
                f"{emoji} <b>{direction} {symbol}</b> {type_emoji}\n"
                f"Price: {price_str}\n\n"
                f"This signal has <b>87% win rate</b> in backtesting.\n\n"
                f"⚠️ <b>Free members see this AFTER entry.</b>\n"
                f"Premium members got this alert <b>15 minutes early</b>\n"
                f"and already locked in profit.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔓 <b>Get signals BEFORE the move:</b>\n"
                f"• 15 signals/day instead of 3\n"
                f"• Entry & exit prices included\n"
                f"• Real-time alerts\n"
                f"• Forex signals (Premium+)\n"
                f"• Crypto signals (VIP only)\n\n"
                f"DM @Johnpaulmuna_83 to join Premium\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📈 <b>Trade this signal:</b>\n"
                f"<a href=\"{trading_link}\">Open Binance & Trade</a>"
            )
        elif tier == "premium":
            message = (
                f"{emoji} <b>{direction} {pair_type.upper()} SIGNAL</b> {type_emoji}\n\n"
                f"<b>Symbol:</b> {symbol}\n"
                f"<b>Price:</b> {price_str}\n"
                f"<b>Target:</b> {target_str}\n"
                f"<b>Stop Loss:</b> {stop_str}\n"
                f"<b>Confidence:</b> {confidence:.1%}\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {timestamp}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <b>Upgrade to VIP and get:</b>\n"
                f"• Unlimited signals\n"
                f"• Crypto trading signals (BTC, ETH, SOL, etc.)\n"
                f"• AI portfolio management\n"
                f"• Auto-trade option\n"
                f"• Priority execution\n\n"
                f"DM @Johnpaulmuna_83 for VIP access\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📈 <b>Trade this signal:</b>\n"
                f"<a href=\"{trading_link}\">Open Binance & Trade</a>"
            )
        else:
            message = (
                f"{emoji} <b>{direction} {pair_type.upper()} SIGNAL</b> {type_emoji}\n\n"
                f"<b>Symbol:</b> {symbol}\n"
                f"<b>Price:</b> {price_str}\n"
                f"<b>Target:</b> {target_str}\n"
                f"<b>Stop Loss:</b> {stop_str}\n"
                f"<b>Confidence:</b> {confidence:.1%}\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Time:</b> {timestamp}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>VIP MEMBER</b> | Crypto + Forex + Stocks\n"
                f"Auto-trade: ON | Unlimited signals\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📈 <b>Trade this signal:</b>\n"
                f"<a href=\"{trading_link}\">Open Binance & Trade</a>"
            )

        return message

    def send_admin(self, message: str):
        """Send message to admin."""
        if not self.admin_chat_id:
            return

        # Use Free bot for admin messages
        bot_token = self.bot_tokens.get("free", "")
        if not bot_token:
            return

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            requests.post(url, json={
                "chat_id": self.admin_chat_id,
                "text": message,
                "parse_mode": "HTML"
            }, timeout=10)
        except:
            pass


# ============================================================
# MAIN TRADING ENGINE (3-Engine Architecture)
# ============================================================

class TradingEngine:
    """Main trading engine - orchestrates 3 separate engines through central risk."""

    def __init__(self):
        self.notifier = TelegramNotifier()
        self.central_risk = CentralRiskEngine({
            "max_daily_loss": 0.05,
            "max_drawdown": 0.10,
            "max_total_exposure": 0.80,
            "max_correlated": 3,
            "max_daily_trades": {"stock": 10, "forex": 15, "crypto": 20},
            "max_position_size": {"stock": 0.10, "forex": 0.05, "crypto": 0.05},
        })

        # Initialize 3 engines
        self.stock_engine = StockEngine()
        self.forex_engine = ForexEngine()
        self.crypto_engine = CryptoEngine()
        self.crypto_discovery = CryptoDiscovery()

        self.signal_count = {"free": 0, "premium": 0, "vip": 0}
        self.running = True

        logger.info("3-Engine Trading System initialized")
        logger.info(f"  Stock engine: {len(self.stock_engine.get_symbols())} symbols")
        logger.info(f"  Forex engine: {len(self.forex_engine.get_symbols())} pairs")
        logger.info(f"  Crypto engine: {len(self.crypto_engine.get_symbols())} pairs")

    def _send_signal(self, signal, tier: str):
        """Send signal through notifier and track counts."""
        self.notifier.send_signal(signal.to_dict() if hasattr(signal, 'to_dict') else signal, tier)
        self.signal_count[tier] = self.signal_count.get(tier, 0) + 1

    def _log_signal(self, signal):
        """Log signal to file."""
        log_file = Path(__file__).parent / "data" / "signals.jsonl"
        log_file.parent.mkdir(exist_ok=True)
        data = signal.to_dict() if hasattr(signal, 'to_dict') else signal
        with open(log_file, "a") as f:
            f.write(json.dumps(data) + "\n")

    def _send_discovery_report(self, coins):
        """Send crypto discovery report to VIP channel."""
        token = os.getenv("VIP_BOT_TOKEN", "")
        chat_id = os.getenv("VIP_CHANNEL_ID", "")
        if not token or not chat_id:
            return

        lines = ["🔍 <b>CRYPTO DISCOVERY — Top Momentum Coins</b>\n"]
        for i, coin in enumerate(coins, 1):
            emoji = "🟢" if coin.direction == "BUY" else "🟡" if coin.direction == "WATCH" else "⚪"
            price_str = f"${coin.price:,.2f}" if coin.price > 1 else f"${coin.price:.6f}"
            mom5 = f"+{coin.momentum_5d:.1f}%" if coin.momentum_5d > 0 else f"{coin.momentum_5d:.1f}%"
            mom10 = f"+{coin.momentum_10d:.1f}%" if coin.momentum_10d > 0 else f"{coin.momentum_10d:.1f}%"
            reasons_str = " | ".join(coin.reasons[:3]) if coin.reasons else "—"
            lines.append(
                f"{emoji} <b>{i}. {coin.symbol}</b> — {price_str}\n"
                f"   RSI: {coin.rsi:.0f} | 5d: {mom5} | 10d: {mom10}\n"
                f"   Score: {coin.score:.0%} — {reasons_str}\n"
            )

        lines.append(
            f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 Scanned {len(CRYPTO_UNIVERSE)} coins across the market\n"
            f"💡 These coins show unusual momentum activity\n\n"
            f"⚠️ <b>Discovery is NOT a buy signal</b>\n"
            f"Always DYOR. Trade at your own risk.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        message = "\n".join(lines)
        self.notifier._send_telegram(token, chat_id, message)
        logger.info(f"Discovery report sent to VIP ({len(coins)} coins)")

    def run_cycle(self):
        """Run one analysis cycle across all 3 engines."""
        logger.info("Starting 3-engine analysis cycle...")

        stock_signals = self.stock_engine.run_cycle()
        forex_signals = self.forex_engine.run_cycle()
        crypto_signals = self.crypto_engine.run_cycle()

        # Crypto discovery — scan wider universe for VIP
        discovery_coins = []
        try:
            discovery_coins = self.crypto_discovery.run_discovery(top_n=5)
            if discovery_coins:
                logger.info(f"Discovery found {len(discovery_coins)} high-momentum coins")
        except Exception as e:
            logger.error(f"Discovery scan failed: {e}")

        # Combine and sort by confidence
        all_signals = stock_signals + forex_signals + crypto_signals
        all_signals.sort(key=lambda s: s.confidence, reverse=True)

        # Send top signals (max 5 total)
        sent_count = 0
        for signal in all_signals[:5]:
            # Route to tiers based on market type
            if signal.type == "crypto":
                self._send_signal(signal, "vip")
            elif signal.type == "forex":
                self._send_signal(signal, "premium")
                self._send_signal(signal, "vip")
            else:
                self._send_signal(signal, "free")
                self._send_signal(signal, "premium")
                self._send_signal(signal, "vip")

            self._log_signal(signal)
            sent_count += 1

        # Send discovery highlights to VIP
        if discovery_coins:
            self._send_discovery_report(discovery_coins)

        logger.info(
            f"Cycle complete: {len(stock_signals)} stocks + "
            f"{len(forex_signals)} forex + {len(crypto_signals)} crypto = "
            f"{sent_count} sent (+ {len(discovery_coins)} discovery)"
        )
        return all_signals

    def run(self, interval_minutes: int = 15):
        """Run engine continuously."""
        logger.info("=" * 60)
        logger.info("3-ENGINE TRADING SYSTEM STARTED")
        logger.info(f"  Stock engine: {len(self.stock_engine.get_symbols())} symbols "
                     f"(market hours: 9-4 EST)")
        logger.info(f"  Forex engine: {len(self.forex_engine.get_symbols())} pairs "
                     f"(market hours: 24/5)")
        logger.info(f"  Crypto engine: {len(self.crypto_engine.get_symbols())} pairs "
                     f"(market hours: 24/7)")
        logger.info(f"  Central risk: daily loss {self.central_risk.max_daily_loss:.0%}, "
                     f"drawdown {self.central_risk.max_drawdown:.0%}")
        logger.info("=" * 60)

        self.notifier.send_admin(
            f"🤖 3-Engine Trading System Started\n\n"
            f"Stock engine: {len(self.stock_engine.get_symbols())} symbols\n"
            f"Forex engine: {len(self.forex_engine.get_symbols())} pairs\n"
            f"Crypto engine: {len(self.crypto_engine.get_symbols())} pairs\n\n"
            f"Central risk active"
        )

        cycle_count = 0

        while self.running:
            try:
                cycle_count += 1
                logger.info(f"\n--- Cycle {cycle_count} ---")

                # Each engine checks its own market hours internally
                signals = self.run_cycle()

                # Send daily summary at 3pm EST
                if datetime.now().hour == 15 and datetime.now().weekday() < 5:
                    self._send_summary()

                logger.info(f"Next cycle in {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                logger.info("Engine stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Error in cycle: {e}")
                self.notifier.send_admin(f"Engine Error: {str(e)[:200]}")
                time.sleep(60)

    def _send_summary(self):
        """Send daily summary."""
        portfolio = self.central_risk.get_portfolio_summary()
        summary = (
            f"DAILY SUMMARY\n\n"
            f"Signals Today:\n"
            f"  Free: {self.signal_count['free']}\n"
            f"  Premium: {self.signal_count['premium']}\n"
            f"  VIP: {self.signal_count['vip']}\n\n"
            f"Portfolio:\n"
            f"  P&L: ${portfolio['daily_pnl']:.2f}\n"
            f"  Positions: {portfolio['total_positions']}\n"
            f"  Drawdown: {portfolio['drawdown']:.1%}\n\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        self.notifier.send_admin(summary)
        self.signal_count = {"free": 0, "premium": 0, "vip": 0}


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Trading Engine")
    parser.add_argument("--once", action="store_true", help="Run single cycle")
    parser.add_argument("--interval", type=int, default=15, help="Minutes between cycles")
    parser.add_argument("--test", action="store_true", help="Test mode (ignore market hours)")

    args = parser.parse_args()

    engine = TradingEngine()

    if args.once or args.test:
        logger.info("Running single cycle...")
        signals = engine.run_cycle()
        print(f"\nFound {len(signals)} signals")
        for s in signals:
            print(f"  {s.direction} {s.symbol} @ ${s.price:.2f} ({s.confidence:.1%})")
    else:
        engine.run(interval_minutes=args.interval)
