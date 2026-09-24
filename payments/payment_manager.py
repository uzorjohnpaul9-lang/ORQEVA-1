"""
Payment System - Crypto (USDT) + Manual (Card/Bank)
"""
import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
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
        "currency": "USD",
        "duration_days": 30,
        "crypto": {
            "usdt_trc20": 199,
            "usdt_erc20": 199,
        },
    }
}

# Your wallet addresses
WALLET_ADDRESSES = {
    "usdt_trc20": "TVTd5E174wygdqAUBYddFWgViLTQJRKytf",
    "usdt_erc20": "YOUR_ERC20_WALLET_ADDRESS",
}

# Admin config
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")


class PaymentManager:
    """Handle crypto and manual payments."""

    def __init__(self):
        self.pending_payments = self._load_json("pending.json", {})
        self.active_subscriptions = self._load_json("subscriptions.json", {})
        self.payment_history = self._load_json("history.json", [])

    def _load_json(self, filename: str, default):
        filepath = PAYMENTS_DIR / filename
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
        return default

    def _save_json(self, filename: str, data):
        filepath = PAYMENTS_DIR / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def create_invoice(self, tier: str, user_id: str, method: str = "crypto") -> Dict[str, Any]:
        """Create a payment invoice."""
        config = PAYMENT_CONFIG.get(tier)
        if not config or tier == "free":
            return {"error": "Invalid tier"}

        invoice_id = str(uuid.uuid4())[:8]
        amount = config["price"]

        if method == "crypto":
            if amount > 100:
                network = "usdt_trc20"
            else:
                network = "usdt_trc20"

            wallet = WALLET_ADDRESSES.get(network, "UNKNOWN")
            crypto_amount = amount  # 1 USDT = 1 USD

            invoice = {
                "invoice_id": invoice_id,
                "tier": tier,
                "user_id": user_id,
                "method": "crypto",
                "network": network,
                "amount_usd": amount,
                "crypto_amount": crypto_amount,
                "wallet_address": wallet,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            }
        else:
            # Manual payment (bank/card)
            invoice = {
                "invoice_id": invoice_id,
                "tier": tier,
                "user_id": user_id,
                "method": "manual",
                "amount_usd": amount,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=48)).isoformat(),
            }

        self.pending_payments[invoice_id] = invoice
        self._save_json("pending.json", self.pending_payments)

        logger.info(f"Invoice created: {invoice_id} for {tier} ({method})")
        return invoice

    def format_invoice_message(self, invoice: Dict[str, Any]) -> str:
        """Format invoice as Telegram message."""
        tier = invoice.get("tier", "").upper()
        amount = invoice.get("amount_usd", 0)
        method = invoice.get("method", "")
        invoice_id = invoice.get("invoice_id", "")
        status = invoice.get("status", "")

        if method == "crypto":
            network = invoice.get("network", "").upper()
            wallet = invoice.get("wallet_address", "")
            crypto_amount = invoice.get("crypto_amount", 0)

            message = (
                f"💳 <b>INVOICE - {tier}</b>\n\n"
                f"<b>Amount:</b> {crypto_amount} USDT\n"
                f"<b>Network:</b> {network}\n"
                f"<b>Wallet:</b>\n<code>{wallet}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>IMPORTANT:</b>\n"
                f"• Send EXACTLY {crypto_amount} USDT\n"
                f"• Wrong network = lost funds\n"
                f"• Send from YOUR wallet\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>Invoice ID:</b> <code>{invoice_id}</code>\n"
                f"<b>Expires:</b> 24 hours\n\n"
                f"Send payment then DM @Johnpaulmuna_83\n"
                f"with your payment screenshot."
            )
        else:
            message = (
                f"💳 <b>INVOICE - {tier}</b>\n\n"
                f"<b>Amount:</b> ${amount} USD\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>Payment Methods:</b>\n"
                f"• Bank Transfer\n"
                f"• Card Payment\n\n"
                f"DM @Johnpaulmuna_83 for payment details.\n\n"
                f"<b>Invoice ID:</b> <code>{invoice_id}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Send payment proof to @Johnpaulmuna_83"
            )

        return message

    def verify_crypto_payment(self, invoice_id: str, tx_hash: str = None) -> bool:
        """
        Verify crypto payment received.
        In production, check blockchain API.
        """
        invoice = self.pending_payments.get(invoice_id)
        if not invoice:
            return False

        # TODO: Integrate with blockchain API
        # For now, manual verification by admin
        logger.info(f"Crypto payment verification requested for {invoice_id}")
        return False

    def approve_payment(self, invoice_id: str, admin_note: str = "") -> Dict[str, Any]:
        """Admin approves a payment."""
        invoice = self.pending_payments.get(invoice_id)
        if not invoice:
            return {"error": "Invoice not found"}

        if invoice["status"] != "pending":
            return {"error": "Invoice already processed"}

        # Update status
        invoice["status"] = "approved"
        invoice["approved_at"] = datetime.now().isoformat()
        invoice["admin_note"] = admin_note

        # Create subscription
        tier = invoice["tier"]
        user_id = invoice["user_id"]
        config = PAYMENT_CONFIG[tier]

        subscription = {
            "user_id": user_id,
            "tier": tier,
            "invoice_id": invoice_id,
            "activated_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=config["duration_days"])).isoformat(),
            "payment_method": invoice.get("method", "unknown"),
            "amount_paid": invoice.get("amount_usd", 0),
        }

        self.active_subscriptions[user_id] = subscription
        self.payment_history.append(invoice)

        # Save
        self._save_json("pending.json", self.pending_payments)
        self._save_json("subscriptions.json", self.active_subscriptions)
        self._save_json("history.json", self.payment_history)

        # Remove from pending
        del self.pending_payments[invoice_id]
        self._save_json("pending.json", self.pending_payments)

        logger.info(f"Payment approved: {invoice_id} → {tier} subscription for {user_id}")
        return subscription

    def reject_payment(self, invoice_id: str, reason: str = "") -> Dict[str, Any]:
        """Admin rejects a payment."""
        invoice = self.pending_payments.get(invoice_id)
        if not invoice:
            return {"error": "Invoice not found"}

        invoice["status"] = "rejected"
        invoice["rejected_at"] = datetime.now().isoformat()
        invoice["rejection_reason"] = reason

        self.payment_history.append(invoice)
        del self.pending_payments[invoice_id]

        self._save_json("pending.json", self.pending_payments)
        self._save_json("history.json", self.payment_history)

        return {"status": "rejected"}

    def check_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Check if user has active subscription."""
        sub = self.active_subscriptions.get(user_id)
        if not sub:
            return None

        # Check expiry
        expires = datetime.fromisoformat(sub["expires_at"])
        if datetime.now() > expires:
            sub["status"] = "expired"
            self._save_json("subscriptions.json", self.active_subscriptions)
            return None

        sub["status"] = "active"
        return sub

    def get_pending_count(self) -> int:
        """Get number of pending payments."""
        return len(self.pending_payments)

    def get_pending_payments(self) -> list:
        """Get all pending payments."""
        return list(self.pending_payments.values())

    def get_stats(self) -> Dict[str, Any]:
        """Get payment statistics."""
        active = sum(1 for s in self.active_subscriptions.values()
                    if datetime.fromisoformat(s["expires_at"]) > datetime.now())
        total_revenue = sum(p.get("amount_usd", 0) for p in self.payment_history)

        return {
            "pending_payments": len(self.pending_payments),
            "active_subscriptions": active,
            "total_revenue": total_revenue,
            "total_payments": len(self.payment_history),
        }

    def format_pending_list(self) -> str:
        """Format pending payments for admin."""
        pending = self.get_pending_payments()
        if not pending:
            return "No pending payments."

        message = "💳 <b>PENDING PAYMENTS</b>\n\n"
        for p in pending:
            created = p.get("created_at", "")[:16]
            message += (
                f"• <b>{p['tier'].upper()}</b> - ${p['amount_usd']}\n"
                f"  ID: <code>{p['invoice_id']}</code>\n"
                f"  User: {p.get('user_id', 'unknown')}\n"
                f"  Method: {p.get('method', 'unknown')}\n"
                f"  Created: {created}\n\n"
            )

        message += "Approve: /approve [invoice_id]"
        return message
