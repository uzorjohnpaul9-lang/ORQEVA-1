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
EXCHANGE_CONNECTIONS = "exchange_connections"
IDEMPOTENCY_RECORDS = "idempotency_records"
RISK_SETTINGS = "risk_settings"
INVOICES = "invoices"
SUBSCRIPTIONS = "subscriptions"
PROMO_CODES = "promo_codes"
AUDIT_LOG = "audit_log"