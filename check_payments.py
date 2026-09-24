"""
View pending payments and stats.
Usage: python check_payments.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from payments.payment_manager import PaymentManager
from dotenv import load_dotenv
load_dotenv()

pm = PaymentManager()

print("=" * 50)
print("PAYMENT DASHBOARD")
print("=" * 50)

# Stats
stats = pm.get_stats()
print(f"\n📊 Statistics:")
print(f"  Pending Payments: {stats['pending_payments']}")
print(f"  Active Subscriptions: {stats['active_subscriptions']}")
print(f"  Total Revenue: ${stats['total_revenue']}")
print(f"  Total Payments: {stats['total_payments']}")

# Pending payments
print(f"\n💳 Pending Payments:")
pending = pm.get_pending_payments()
if not pending:
    print("  None.")
else:
    for p in pending:
        created = p.get("created_at", "")[:16]
        print(f"  {p['invoice_id']} | {p['tier'].upper()} | ${p['amount_usd']} | {p.get('method', 'N/A')} | {created}")
    print(f"\n  Approve: python approve_payment.py [invoice_id]")

print("\n" + "=" * 50)
