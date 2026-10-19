"""
Admin Bot - Manage payments and users from Telegram.
Includes input validation and rate limiting.
"""
import os
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from notifications.channel_notifier import ChannelNotifier
from security.rate_limiter import rate_limit
from dotenv import load_dotenv
load_dotenv()

BILLING_NOTE = (
    "Billing moved to the database (Phase I). Invoices are created, approved "
    "and refunded from the ORQEVA admin dashboard (Billing tab) — gateway "
    "webhooks auto-approve paid invoices."
)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def _admin_token() -> str:
    """Dedicated admin bot, falling back to the Free bot for older setups."""
    return os.getenv("TELEGRAM_BOT_TOKEN_ADMIN", "") or os.getenv(
        "TELEGRAM_BOT_TOKEN_FREE", ""
    )


ADMIN_TOKEN = _admin_token()
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

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

    if command in ("/pending", "/approve", "/reject", "/stats"):
        send_admin(BILLING_NOTE)

    elif command == "/help":
        msg = (
            "📊 <b>ADMIN COMMANDS</b>\n\n"
            "/pending, /approve, /reject, /stats - billing moved to the dashboard\n"
            "/help - Show this menu"
        )
        send_admin(msg)

    else:
        send_admin(f"Unknown command: {_sanitize(command)}\nType /help for commands")


def poll_updates():
    """Poll for admin commands via getUpdates."""
    print("Admin bot started. Waiting for commands...")
    print("Billing commands moved to the dashboard. Type /help for commands.")

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
