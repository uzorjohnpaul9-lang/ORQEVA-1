"""
Pricing/wallet config - single source of truth for the app, Telegram bot and
billing service.

Phase I retired the legacy JSON payment store (`PaymentManager` +
data/payments/{pending,subscriptions,history}.json): invoice and subscription
state live in the database (`invoices` / `subscriptions`) via
`backend/services/billing_service.py`. Only `payment_config.json` (admin-set
bank/card receiving details) remains file-backed.
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

PAYMENTS_DIR = Path(__file__).parent.parent / "data" / "payments"
PAYMENTS_DIR.mkdir(parents=True, exist_ok=True)

# Payment Configuration
PAYMENT_CONFIG = {
    "free": {
        "name": "Free",
        "price": 0,
        "currency": "USD",
        "duration_days": 9999,  # Unlimited
    },
    "premium": {
        "name": "Premium",
        "price": 49,
        "annual_price": 490,
        "annual_days": 365,
        "currency": "USD",
        "duration_days": 30,
        "crypto": {
            "usdt_trc20": 49,
            "usdt_erc20": 49,
        },
    },
    "vip": {
        "name": "VIP",
        "price": 199,
        "annual_price": 1990,
        "annual_days": 365,
        "currency": "USD",
        "duration_days": 30,
        "crypto": {
            "usdt_trc20": 199,
            "usdt_erc20": 199,
        },
    }
}

# Receiving wallet for hand-pay crypto invoices
WALLET_ADDRESSES = {
    "usdt_trc20": "TVTd5E174wygdqAUBYddFWgViLTQJRKytf",
    "usdt_erc20": "YOUR_ERC20_WALLET_ADDRESS",
}

# Admin config
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

PAYMENT_CONFIG_FILE = PAYMENTS_DIR / "payment_config.json"

DEFAULT_PAYMENT_CONFIG = {
    "bank_card": {
        "bank_name": "",
        "account_name": "",
        "account_number": "",
        "branch": "",
        "instructions": "",
    }
}


def load_payment_config() -> dict:
    """Load admin-configurable payment config (bank/card receiving details)."""
    if PAYMENT_CONFIG_FILE.exists():
        try:
            with open(PAYMENT_CONFIG_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            logger.warning("payment_config.json unreadable; resetting to defaults")
    return {k: dict(v) for k, v in DEFAULT_PAYMENT_CONFIG.items()}


def save_payment_config(data: dict) -> dict:
    """Persist admin-configurable payment config."""
    cleaned = {
        "bank_card": {
            "bank_name": str((data.get("bank_card") or {}).get("bank_name") or "").strip()[:120],
            "account_name": str((data.get("bank_card") or {}).get("account_name") or "").strip()[:120],
            "account_number": str((data.get("bank_card") or {}).get("account_number") or "").strip()[:60],
            "branch": str((data.get("bank_card") or {}).get("branch") or "").strip()[:120],
            "instructions": str((data.get("bank_card") or {}).get("instructions") or "").strip()[:500],
        }
    }
    PAYMENT_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PAYMENT_CONFIG_FILE, "w") as f:
        json.dump(cleaned, f, indent=2)
    return cleaned
