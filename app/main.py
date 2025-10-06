import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from contextlib import asynccontextmanager

from app.core.config import get_settings
from app.database.connection import get_db, create_tables
from app.api.v1.router import api_router
from app.api.middleware.rate_limitting import AuthRateLimitMiddleware
from app.api.middleware.security_headers import SecurityHeadersMiddleware
from app.api.middleware.audit_middleware import AuditMiddleware
from app.api.middleware.global_rate_limit import GlobalRateLimitMiddleware
from app.api.middleware.performance_monitoring import (
    PerformanceMonitoringMiddleware,
    set_performance_monitor,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable SQLAlchemy query logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting up the application...")
    try:
        create_tables()
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down the application...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-Powered Customer Support Analyzer Backend API",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,  # Use orjson for 5-10x faster JSON serialization
)

# Add performance monitoring middleware (first to measure total response time)
perf_monitor = PerformanceMonitoringMiddleware(
    app,
    slow_threshold_ms=200,      # Log warning for endpoints >200ms
    very_slow_threshold_ms=1000,  # Log error for endpoints >1000ms
)
app.add_middleware(lambda app: perf_monitor)
set_performance_monitor(perf_monitor)

# Add security headers middleware (applies to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# Add audit logging middleware
app.add_middleware(AuditMiddleware)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add global rate limiting middleware (applies to all API endpoints)
app.add_middleware(
    GlobalRateLimitMiddleware,
    ip_calls=60,         # 60 requests/min for anonymous users
    user_calls=300,      # 300 requests/min for authenticated users
    org_calls=5000,      # 5000 requests/min per organization
)


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "database": "connected",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "database": "disconnected",
            "error": str(e),
        }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to AI-Powered Customer Support Analyzer API",
        "version": settings.app_version,
        "docs": "/docs",
    }


# Include API routes
app.include_router(api_router, prefix=settings.api_v1_prefix)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )
