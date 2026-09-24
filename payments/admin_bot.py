"""
Admin Bot - Manage payments and users from Telegram.
Includes input validation and rate limiting.
"""
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from payments.payment_manager import PaymentManager
from notifications.channel_notifier import ChannelNotifier
from security.rate_limiter import rate_limit
from dotenv import load_dotenv
load_dotenv()

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


ADMIN_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_FREE", "")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

payment_mgr = PaymentManager()
notifier = ChannelNotifier()

# Input validation patterns
VALID_TIER = re.compile(r"^(free|premium|vip)$", re.IGNORECASE)
VALID_INVOICE_ID = re.compile(r"^[a-f0-9\-]{8,36}$", re.IGNORECASE)
VALID_COMMAND = re.compile(r"^/[a-z_]+$")


def send_admin(message: str):
    """Send message to admin."""
    if not ADMIN_TOKEN or not ADMIN_CHAT_ID:
        print(f"Admin: {message}")
        return

    url = f"https://api.telegram.org/bot{ADMIN_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }, timeout=10)


def _sanitize(text: str) -> str:
    """Remove HTML special chars to prevent injection in Telegram messages."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@rate_limit(calls=20, period=60.0)
def handle_command(command: str, args: list):
    """Handle admin commands with input validation."""
    if not VALID_COMMAND.match(command):
        send_admin("Invalid command format.")
        return

    if command == "/pending":
        msg = payment_mgr.format_pending_list()
        send_admin(msg)

    elif command == "/approve":
        if not args:
            send_admin("Usage: /approve [invoice_id]")
            return
        invoice_id = args[0]
        if not VALID_INVOICE_ID.match(invoice_id):
            send_admin(f"Invalid invoice ID format: {_sanitize(invoice_id)}")
            return
        result = payment_mgr.approve_payment(invoice_id, "Approved by admin")
        if "error" in result:
            send_admin(f"Error: {_sanitize(result['error'])}")
        else:
            tier = _sanitize(result.get("tier", "").upper())
            user_id = _sanitize(result.get("user_id", ""))
            send_admin(f"✅ Payment approved!\n\nTier: {tier}\nUser: {user_id}")
            send_admin(
                f"🎉 <b>Welcome to {tier}!</b>\n\n"
                f"Your subscription is now active.\n"
                f"Check your channel for signals."
            )

    elif command == "/reject":
        if not args:
            send_admin("Usage: /reject [invoice_id] [reason]")
            return
        invoice_id = args[0]
        if not VALID_INVOICE_ID.match(invoice_id):
            send_admin(f"Invalid invoice ID format: {_sanitize(invoice_id)}")
            return
        reason = " ".join(args[1:]) if len(args) > 1 else "Payment rejected"
        reason = _sanitize(reason)[:200]
        result = payment_mgr.reject_payment(invoice_id, reason)
        if "error" in result:
            send_admin(f"Error: {_sanitize(result['error'])}")
        else:
            send_admin(f"❌ Payment rejected: {_sanitize(invoice_id)}")

    elif command == "/stats":
        stats = payment_mgr.get_stats()
        msg = (
            f"📊 <b>PAYMENT STATS</b>\n\n"
            f"Pending: {stats['pending_payments']}\n"
            f"Active Subscriptions: {stats['active_subscriptions']}\n"
            f"Total Revenue: ${stats['total_revenue']}\n"
            f"Total Payments: {stats['total_payments']}"
        )
        send_admin(msg)

    elif command == "/help":
        msg = (
            "🤖 <b>ADMIN COMMANDS</b>\n\n"
            "/pending - View pending payments\n"
            "/approve [id] - Approve payment\n"
            "/reject [id] [reason] - Reject payment\n"
            "/stats - View statistics\n"
            "/help - Show this menu"
        )
        send_admin(msg)

    else:
        send_admin(f"Unknown command: {_sanitize(command)}\nType /help for commands")


def poll_updates():
    """Poll for admin commands via getUpdates."""
    print("Admin bot started. Waiting for commands...")
    print("Commands: /pending, /approve, /reject, /stats, /help")

    if not ADMIN_TOKEN:
        print("No admin token configured!")
        return

    offset = 0
    url = f"https://api.telegram.org/bot{ADMIN_TOKEN}"

    while True:
        try:
            r = requests.get(f"{url}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=35)
            data = r.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if chat_id != ADMIN_CHAT_ID:
                    continue

                if text.startswith("/"):
                    parts = text.split()
                    command = parts[0].lower()
                    args = parts[1:]
                    handle_command(command, args)

        except KeyboardInterrupt:
            print("\nAdmin bot stopped.")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    poll_updates()
