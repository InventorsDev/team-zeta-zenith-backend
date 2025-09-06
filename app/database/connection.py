from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from app.core.config import get_settings
from app.models.base import Base
import logging

logger = logging.getLogger(__name__)

settings = get_settings()

# Create engine with appropriate configuration
if "sqlite" in settings.database_url_complete:
    # SQLite configuration for development
    engine = create_engine(
        settings.database_url_complete,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Disable SQL query logging
    )
else:
    # PostgreSQL configuration for production
    engine = create_engine(
        settings.database_url_complete,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False,  # Disable SQL query logging
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables in the database"""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def drop_tables():
    """Drop all tables in the database"""
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("Database tables dropped")
