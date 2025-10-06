from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, QueuePool
from app.core.config import get_settings
from app.models.base import Base
import logging
import time

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
    # PostgreSQL configuration for production with optimized connection pooling
    engine = create_engine(
        settings.database_url_complete,
        # Connection pool settings
        poolclass=QueuePool,
        pool_size=20,              # Core pool size (connections kept alive)
        max_overflow=40,           # Additional connections when pool is full (total=60)
        pool_timeout=30,           # Timeout waiting for connection (seconds)
        pool_recycle=1800,         # Recycle connections after 30 minutes
        pool_pre_ping=True,        # Test connection before using (prevents stale connections)

        # Query optimization settings
        echo=False,                # Disable SQL query logging (use slow query middleware instead)
        echo_pool=False,           # Disable pool logging

        # Performance settings
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",  # 30 second query timeout
        },

        # Execution options for better performance
        execution_options={
            "isolation_level": "READ COMMITTED",  # Balance between consistency and performance
        }
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Query performance monitoring
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query execution time - store start time"""
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query execution time - log slow queries"""
    total_time = time.time() - conn.info["query_start_time"].pop()

    # Log slow queries (over 100ms)
    if total_time > 0.1:
        logger.warning(
            f"Slow query detected ({total_time*1000:.2f}ms): {statement[:200]}..."
        )

    # Log very slow queries with full statement
    if total_time > 1.0:
        logger.error(
            f"Very slow query ({total_time:.2f}s): {statement}\nParameters: {parameters}"
        )


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
