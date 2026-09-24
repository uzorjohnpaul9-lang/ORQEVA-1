from typing import Optional
import os

try:
    from pydantic_settings import BaseSettings
    USE_PYDANTIC = True
except ImportError:
    USE_PYDANTIC = False

if USE_PYDANTIC:
    class TradingSettings(BaseSettings):
        trading_enabled: bool = False
        default_risk_profile: str = "conservative"
        max_portfolio_value: float = 100000
        max_risk_per_trade: float = 0.02
        max_daily_loss: float = 0.05
        max_open_positions: int = 10
        max_leverage: float = 1.0
        market_open_hour: int = 9
        market_open_minute: int = 30
        market_close_hour: int = 16
        market_close_minute: int = 0
        default_timeframe: str = "1h"
        lookback_period_days: int = 365

        class Config:
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"

    class DatabaseSettings(BaseSettings):
        database_url: str = "postgresql://user:password@localhost:5432/ai_trading"
        redis_url: str = "redis://localhost:6379/0"

        class Config:
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"

    class SecuritySettings(BaseSettings):
        jwt_secret_key: str = "your_jwt_secret_key"
        encryption_key: str = "your_encryption_key"
        token_expire_minutes: int = 30
        max_login_attempts: int = 5

        class Config:
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"

    class MonitoringSettings(BaseSettings):
        sentry_dsn: Optional[str] = None
        prometheus_port: int = 9090
        log_level: str = "INFO"
        log_file: str = "logs/trading.log"

        class Config:
            env_file = ".env"
            case_sensitive = False
            extra = "ignore"
else:
    class TradingSettings:
        def __init__(self):
            self.trading_enabled = os.getenv("TRADING_ENABLED", "false").lower() == "true"
            self.default_risk_profile = os.getenv("DEFAULT_RISK_PROFILE", "conservative")
            self.max_portfolio_value = float(os.getenv("MAX_PORTFOLIO_VALUE", "100000"))
            self.max_risk_per_trade = 0.02
            self.max_daily_loss = 0.05
            self.max_open_positions = 10
            self.max_leverage = 1.0
            self.market_open_hour = 9
            self.market_open_minute = 30
            self.market_close_hour = 16
            self.market_close_minute = 0
            self.default_timeframe = "1h"
            self.lookback_period_days = 365

    class DatabaseSettings:
        def __init__(self):
            self.database_url = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/ai_trading")
            self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    class SecuritySettings:
        def __init__(self):
            self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "your_jwt_secret_key")
            self.encryption_key = os.getenv("ENCRYPTION_KEY", "your_encryption_key")
            self.token_expire_minutes = 30
            self.max_login_attempts = 5

    class MonitoringSettings:
        def __init__(self):
            self.sentry_dsn = os.getenv("SENTRY_DSN")
            self.prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9090"))
            self.log_level = os.getenv("LOG_LEVEL", "INFO")
            self.log_file = os.getenv("LOG_FILE", "logs/trading.log")

trading_settings = TradingSettings()
database_settings = DatabaseSettings()
security_settings = SecuritySettings()
monitoring_settings = MonitoringSettings()
