"""
Create an invoice for a user.
Usage: python create_invoice.py [tier] [user_id] [method]
Example: python create_invoice.py premium 123456789 crypto
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

if len(sys.argv) < 3:
    print("Usage: python create_invoice.py [tier] [user_id] [method]")
    print("")
    print("Tiers: premium, vip")
    print("Methods: crypto, manual")
    print("")
    print("Example: python create_invoice.py premium 123456789 crypto")
    sys.exit(1)

tier = sys.argv[1].lower()
user_id = sys.argv[2]
method = sys.argv[3] if len(sys.argv) > 3 else "crypto"

invoice = pm.create_invoice(tier, user_id, method)

if "error" in invoice:
    print(f"Error: {invoice['error']}")
    sys.exit(1)

print("=" * 50)
print("INVOICE CREATED")
print("=" * 50)
print(f"Invoice ID: {invoice['invoice_id']}")
print(f"Tier: {invoice['tier'].upper()}")
print(f"User: {invoice['user_id']}")
print(f"Amount: ${invoice['amount_usd']}")
print(f"Method: {invoice['method']}")
print("=" * 50)

# Format message
msg = pm.format_invoice_message(invoice)
print("")
print("Copy this message and send to the user:")
print("-" * 50)
print(msg)
print("-" * 50)
