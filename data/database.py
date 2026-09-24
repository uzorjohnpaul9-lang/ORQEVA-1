"""
Phase 2: Data Infrastructure - Database Connection
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session
    from sqlalchemy.pool import QueuePool
    from .models import Base
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    logger.warning("SQLAlchemy not installed. Database features disabled.")

class Database:
    """Database connection manager."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.SessionLocal = None

    def connect(self) -> bool:
        if not HAS_SQLALCHEMY:
            logger.warning("SQLAlchemy not available")
            return False
        try:
            self.engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=1800
            )
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            logger.info("Database connected successfully")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def create_tables(self):
        if not HAS_SQLALCHEMY:
            return
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")

    def get_session(self):
        if self.SessionLocal is None:
            raise Exception("Database not connected")
        return self.SessionLocal()

    def close(self):
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
