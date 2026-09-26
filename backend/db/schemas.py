from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ── Auth ──
class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    tier: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Signals ──
class SignalResponse(BaseModel):
    id: str
    symbol: str
    market: str
    direction: str
    confidence: float
    effective_confidence: float | None = None
    age_hours: float | None = None
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    strategy: str | None
    status: str
    tier_required: str
    indicators: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Trades ──
class TradeResponse(BaseModel):
    id: str
    symbol: str
    market: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float | None
    pnl: float | None
    status: str
    strategy: str | None
    exchange: str | None
    opened_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True


# ── Notifications ──
class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    is_read: bool
    channel: str
    created_at: datetime

    class Config:
        from_attributes = True


class MarkNotificationRead(BaseModel):
    notification_id: str


# ── User Preferences ──
class PreferencesResponse(BaseModel):
    telegram_signals: bool
    telegram_tp_sl: bool
    telegram_market_analysis: bool
    telegram_risk_alerts: bool
    telegram_system_alerts: bool
    email_notifications: bool
    web_notifications: bool
    default_market: str
    risk_tolerance: str
    theme: str

    class Config:
        from_attributes = True


class PreferencesUpdate(BaseModel):
    telegram_signals: bool | None = None
    telegram_tp_sl: bool | None = None
    telegram_market_analysis: bool | None = None
    telegram_risk_alerts: bool | None = None
    telegram_system_alerts: bool | None = None
    email_notifications: bool | None = None
    web_notifications: bool | None = None
    default_market: str | None = Field(None, pattern="^(all|stock|forex|crypto)$")
    risk_tolerance: str | None = Field(None, pattern="^(conservative|moderate|aggressive)$")
    theme: str | None = Field(None, pattern="^(dark|light)$")


# ── Exchange Connections ──
class ExchangeConnect(BaseModel):
    exchange: str = Field(..., min_length=3, max_length=20)
    api_key: str = Field(..., min_length=10)
    api_secret: str | None = Field(None, max_length=5000)
    is_paper: bool = True


class ExchangeResponse(BaseModel):
    id: str
    exchange: str
    is_paper: bool
    is_active: bool
    connected_at: datetime
    last_checked: datetime | None

    class Config:
        from_attributes = True


# ── Auto-Trade ──
class AutoTradeSettings(BaseModel):
    enabled: bool = False
    route: str = Field("paper", pattern="^(paper|live)$")
    markets: list[str] = Field(default_factory=lambda: ["forex", "crypto", "stock"])
    per_trade_risk_pct: float = Field(1.0, ge=0.1, le=10.0)
    min_confidence: float = Field(0.0, ge=0.0, le=1.0)


class AutoTradeLogResponse(BaseModel):
    id: str
    symbol: str
    market: str
    direction: str
    confidence: float | None
    quantity: float | None
    entry_price: float | None
    route: str
    status: str
    reason: str | None
    trade_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Dashboard Overview ──
class DashboardOverview(BaseModel):
    total_signals: int
    active_signals: int
    open_trades: int
    total_pnl: float
    win_rate: float
    portfolio_value: float
