"""
Approve a payment.
Usage: python approve_payment.py [invoice_id]
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

if len(sys.argv) < 2:
    print("Usage: python approve_payment.py [invoice_id]")
    print("")
    print("Pending payments:")
    pending = pm.get_pending_payments()
    if not pending:
        print("  No pending payments.")
    else:
        for p in pending:
            print(f"  {p['invoice_id']} | {p['tier'].upper()} | ${p['amount_usd']} | User: {p.get('user_id', 'N/A')}")
    sys.exit(1)

invoice_id = sys.argv[1]

result = pm.approve_payment(invoice_id, "Approved - payment verified")

if "error" in result:
    print(f"Error: {result['error']}")
    sys.exit(1)

print("=" * 50)
print("PAYMENT APPROVED!")
print("=" * 50)
print(f"User: {result.get('user_id', 'N/A')}")
print(f"Tier: {result.get('tier', '').upper()}")
print(f"Activated: {result.get('activated_at', 'N/A')[:19]}")
print(f"Expires: {result.get('expires_at', 'N/A')[:19]}")
print("=" * 50)
print("")
print("Send this message to the user:")
print("-" * 50)
print(f"Welcome to {result.get('tier', '').upper()}!")
print(f"Your subscription is active.")
print(f"Check your channel for signals.")
print("-" * 50)
