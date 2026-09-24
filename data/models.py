"""
Phase 2: Data Infrastructure - Database Models
"""
from datetime import datetime
from typing import Optional

try:
    from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, Index
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

    class MarketData(Base):
        __tablename__ = "market_data"
        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(10), nullable=False, index=True)
        timestamp = Column(DateTime, nullable=False, index=True)
        open = Column(Float, nullable=False)
        high = Column(Float, nullable=False)
        low = Column(Float, nullable=False)
        close = Column(Float, nullable=False)
        volume = Column(Integer, nullable=False)
        timeframe = Column(String(5), nullable=False)
        vwap = Column(Float, nullable=True)
        __table_args__ = (Index('idx_symbol_timestamp', 'symbol', 'timestamp', 'timeframe'),)

    class TechnicalIndicator(Base):
        __tablename__ = "technical_indicators"
        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(10), nullable=False, index=True)
        timestamp = Column(DateTime, nullable=False, index=True)
        indicator_name = Column(String(50), nullable=False)
        value = Column(Float, nullable=True)
        parameters = Column(JSON, nullable=True)
        __table_args__ = (Index('idx_symbol_indicator', 'symbol', 'timestamp', 'indicator_name'),)

    class Trade(Base):
        __tablename__ = "trades"
        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(10), nullable=False, index=True)
        timestamp = Column(DateTime, nullable=False, index=True)
        side = Column(String(4), nullable=False)
        quantity = Column(Float, nullable=False)
        price = Column(Float, nullable=False)
        order_id = Column(String(50), nullable=True)
        status = Column(String(20), nullable=False)
        commission = Column(Float, default=0.0)

    class Position(Base):
        __tablename__ = "positions"
        id = Column(Integer, primary_key=True, autoincrement=True)
        symbol = Column(String(10), nullable=False, index=True)
        side = Column(String(4), nullable=False)
        quantity = Column(Float, nullable=False)
        entry_price = Column(Float, nullable=False)
        entry_time = Column(DateTime, nullable=False)
        current_price = Column(Float, nullable=True)
        unrealized_pnl = Column(Float, default=0.0)
        status = Column(String(20), nullable=False)
        exit_price = Column(Float, nullable=True)
        exit_time = Column(DateTime, nullable=True)
        realized_pnl = Column(Float, nullable=True)

    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True, autoincrement=True)
        username = Column(String(50), nullable=False, unique=True)
        email = Column(String(100), nullable=False, unique=True)
        password_hash = Column(String(255), nullable=False)
        tier = Column(String(20), nullable=False, default="free")
        created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
        is_active = Column(Boolean, default=True)
        api_key = Column(String(100), nullable=True, unique=True)

except ImportError:
    pass
