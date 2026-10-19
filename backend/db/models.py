"""Table/column name constants for the Supabase (PostgREST) data layer.

The backend no longer uses SQLAlchemy models; rows are plain dicts returned
by :mod:`backend.db.supabase`. Keep the imports in the rest of the codebase
readable by pointing at the same table names.
"""
import uuid


def gen_uuid() -> str:
    return str(uuid.uuid4())


USERS = "users"
PASSWORD_RESET_TOKENS = "password_reset_tokens"
SIGNALS = "signals"
TRADES = "trades"
NOTIFICATIONS = "notifications"
USER_PREFERENCES = "user_preferences"
SUPPORT_TICKETS = "support_tickets"
SECURITY_EVENTS = "security_events"
BLOCKED_IPS = "blocked_ips"
EXCHANGE_CONNECTIONS = "exchange_connections"
IDEMPOTENCY_RECORDS = "idempotency_records"
RISK_SETTINGS = "risk_settings"
INVOICES = "invoices"
PAYMENT_EVENTS = "payment_events"
SUBSCRIPTIONS = "subscriptions"
PROMO_CODES = "promo_codes"
AUDIT_LOG = "audit_log"
AUTO_TRADE_SETTINGS = "auto_trade_settings"
AUTO_TRADE_LOG = "auto_trade_log"
AFFILIATE_PARTNERS = "affiliate_partners"
AFFILIATE_CLICKS = "affiliate_clicks"
AFFILIATE_CONVERSIONS = "affiliate_conversions"
API_KEYS = "api_keys"