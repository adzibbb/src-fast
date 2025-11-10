# database.py
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Production database configuration
engine = create_engine(
    settings.DATABASE_URL,
    # Connection pooling for production
    pool_size=20,  # Increased from default 5
    max_overflow=30,  # Allow temporary connection bursts
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600,  # Recycle connections every hour (not 5 minutes)
    pool_timeout=30,  # Wait 30 seconds for connection
    echo=settings.SQL_ECHO,  # Control SQL logging
    # For SQLite in production, use more robust settings
    connect_args=(
        {"check_same_thread": False}
        if "sqlite" in settings.DATABASE_URL
        else {}
    )
)

# Add connection logging for debugging
@event.listens_for(engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    logger.debug("Database connection established")

@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug("Database connection checked out")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Important for performance
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()