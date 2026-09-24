"""
Signal Notifier - Telegram & Email Alerts
"""
import os
import json
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class TelegramNotifier:
    """Send trading signals via Telegram bot."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id and HAS_REQUESTS)

    def send_message(self, message: str) -> bool:
        if not self.enabled:
            logger.warning("Telegram not configured")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def send_signal(self, signal: Dict[str, Any]) -> bool:
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

        message = (
            f"{emoji} <b>{direction} SIGNAL</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Price:</b> ${price:.2f}\n"
            f"<b>Confidence:</b> {confidence:.1%}\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Time:</b> {timestamp}"
        )

        return self.send_message(message)

    def send_trade_alert(self, trade: Dict[str, Any]) -> bool:
        side = trade.get("side", "").upper()
        symbol = trade.get("symbol", "???")
        qty = trade.get("quantity", 0)
        price = trade.get("price", 0)
        status = trade.get("status", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if side == "BUY":
            emoji = "🟢"
        else:
            emoji = "🔴"

        message = (
            f"{emoji} <b>TRADE EXECUTED</b>\n\n"
            f"<b>Action:</b> {side}\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Quantity:</b> {qty}\n"
            f"<b>Price:</b> ${price:.2f}\n"
            f"<b>Status:</b> {status}\n"
            f"<b>Time:</b> {timestamp}"
        )

        return self.send_message(message)

    def send_daily_summary(self, summary: Dict[str, Any]) -> bool:
        pnl = summary.get("daily_pnl", 0)
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        trades = summary.get("trades_today", 0)
        win_rate = summary.get("win_rate", 0)
        portfolio = summary.get("portfolio_value", 0)

        message = (
            f"📊 <b>DAILY SUMMARY</b>\n\n"
            f"<b>Portfolio:</b> ${portfolio:,.2f}\n"
            f"{pnl_emoji} <b>Daily P&L:</b> ${pnl:,.2f}\n"
            f"<b>Trades:</b> {trades}\n"
            f"<b>Win Rate:</b> {win_rate:.1%}"
        )

        return self.send_message(message)

    def send_error_alert(self, error: str) -> bool:
        message = (
            f"🚨 <b>SYSTEM ERROR</b>\n\n"
            f"<b>Error:</b> {error}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return self.send_message(message)

    def send_kill_switch_alert(self, reason: str) -> bool:
        message = (
            f"🛑 <b>KILL SWITCH ACTIVATED</b>\n\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"All trading has been halted."
        )
        return self.send_message(message)


class EmailNotifier:
    """Send trading signals via email."""

    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = 587,
        sender_email: str = None,
        sender_password: str = None,
        recipient_email: str = None
    ):
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = sender_email or os.getenv("SENDER_EMAIL", "")
        self.sender_password = sender_password or os.getenv("SENDER_PASSWORD", "")
        self.recipient_email = recipient_email or os.getenv("RECIPIENT_EMAIL", "")
        self.enabled = bool(self.sender_email and self.sender_password and self.recipient_email)

    def send_email(self, subject: str, body: str) -> bool:
        if not self.enabled:
            logger.warning("Email not configured")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self.sender_email
            msg["To"] = self.recipient_email
            msg["Subject"] = subject

            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; padding: 20px;">
                    {body}
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Email sent: {subject}")
            return True

        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def send_signal(self, signal: Dict[str, Any]) -> bool:
        direction = signal.get("direction", "hold").upper()
        symbol = signal.get("symbol", "???")
        price = signal.get("price", 0)
        confidence = signal.get("confidence", 0)
        reason = signal.get("reason", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if direction == "BUY":
            color = "#27ae60"
        elif direction == "SELL":
            color = "#e74c3c"
        else:
            color = "#f39c12"

        body = f"""
            <h2 style="color: {color};">Trading Signal: {direction}</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Symbol</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{symbol}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Price</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">${price:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Confidence</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{confidence:.1%}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Reason</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{reason}</td></tr>
                <tr><td style="padding: 8px;"><b>Time</b></td><td style="padding: 8px;">{timestamp}</td></tr>
            </table>
        """

        return self.send_email(f"Trading Signal: {direction} {symbol}", body)

    def send_trade_alert(self, trade: Dict[str, Any]) -> bool:
        side = trade.get("side", "").upper()
        symbol = trade.get("symbol", "???")
        qty = trade.get("quantity", 0)
        price = trade.get("price", 0)
        status = trade.get("status", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        color = "#27ae60" if side == "BUY" else "#e74c3c"

        body = f"""
            <h2 style="color: {color};">Trade Executed: {side}</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Action</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{side}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Symbol</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{symbol}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Quantity</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{qty}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Price</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">${price:.2f}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #eee;"><b>Status</b></td><td style="padding: 8px; border-bottom: 1px solid #eee;">{status}</td></tr>
                <tr><td style="padding: 8px;"><b>Time</b></td><td style="padding: 8px;">{timestamp}</td></tr>
            </table>
        """

        return self.send_email(f"Trade Executed: {side} {qty} {symbol}", body)


class SignalNotifier:
    """Unified notifier that sends via all configured channels."""

    def __init__(self):
        self.telegram = TelegramNotifier()
        self.email = EmailNotifier()

    def send_signal(self, signal: Dict[str, Any]):
        self.telegram.send_signal(signal)
        self.email.send_signal(signal)

    def send_trade_alert(self, trade: Dict[str, Any]):
        self.telegram.send_trade_alert(trade)
        self.email.send_trade_alert(trade)

    def send_daily_summary(self, summary: Dict[str, Any]):
        self.telegram.send_daily_summary(summary)

    def send_error(self, error: str):
        self.telegram.send_error_alert(error)
        self.email.send_email("System Error", f"<h2>Error</h2><p>{error}</p>")

    def send_kill_switch(self, reason: str):
        self.telegram.send_kill_switch_alert(reason)
        self.email.send_email("Kill Switch Activated", f"<h2>Kill Switch</h2><p>Reason: {reason}</p>")

    def get_status(self) -> Dict[str, bool]:
        return {
            "telegram": self.telegram.enabled,
            "email": self.email.enabled
        }
