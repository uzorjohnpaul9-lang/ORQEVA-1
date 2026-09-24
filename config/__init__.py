"""Configuration module."""
from .settings import trading_settings, database_settings, security_settings, monitoring_settings
from .risk_profiles import get_risk_profile, RISK_PROFILES

try:
    from .api_keys import credentials
except Exception:
    credentials = None
