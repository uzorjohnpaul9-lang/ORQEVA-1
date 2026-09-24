"""
Test the payment system.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from payments.payment_manager import PaymentManager, PAYMENT_CONFIG

print("=" * 60)
print("PAYMENT SYSTEM")
print("=" * 60)

pm = PaymentManager()

print("\n--- Tier Pricing ---")
for tier, config in PAYMENT_CONFIG.items():
    if tier == "free":
        print(f"  {config['name']:10s} | ${config['price']}/mo | FREE")
    else:
        print(f"  {config['name']:10s} | ${config['price']}/mo | {config['duration_days']} days")

print("\n--- Test Invoice ---")
invoice = pm.create_invoice("premium", "test_user_123", "crypto")
print(f"  Invoice ID: {invoice.get('invoice_id', 'N/A')}")
print(f"  Tier: {invoice.get('tier', 'N/A')}")
print(f"  Amount: ${invoice.get('amount_usd', 0)}")
print(f"  Wallet: {invoice.get('wallet_address', 'N/A')[:30]}...")

print("\n--- Invoice Message ---")
msg = pm.format_invoice_message(invoice)
print(msg)

print("\n--- Stats ---")
stats = pm.get_stats()
print(f"  Pending: {stats['pending_payments']}")
print(f"  Active: {stats['active_subscriptions']}")
print(f"  Revenue: ${stats['total_revenue']}")

print("\n" + "=" * 60)
print("Payment system ready!")
print("=" * 60)
