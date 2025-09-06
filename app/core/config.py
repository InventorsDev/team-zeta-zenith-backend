from typing import Optional, List
from pydantic import validator
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment-based configuration"""

    # Application
    app_name: str = "AI-Powered Customer Support Analyzer"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # API
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 30

    # Database
    database_url: Optional[str] = None

    # SQLite for development
    sqlite_db_name: str = "zenith.db"

    # PostgreSQL for production
    postgres_server: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_db: Optional[str] = None
    postgres_port: int = 5432

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # External APIs
    openai_api_key: Optional[str] = None
    slack_bot_token: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    zendesk_subdomain: Optional[str] = None
    zendesk_email: Optional[str] = None
    zendesk_token: Optional[str] = None

    # CORS
    backend_cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Logging
    log_level: str = "INFO"

    # ML Configuration
    ml_model_path: str = "models/"
    ml_data_path: str = "data/"
    ml_enable_bert: bool = True
    ml_enable_monitoring: bool = True
    ml_confidence_threshold: float = 0.7
    ml_batch_size: int = 32

    # ML Model Settings
    bert_model_name: str = "bert-base-uncased"
    max_sequence_length: int = 512
    
    # Slack Integration for ML Alerts
    slack_webhook_url: Optional[str] = None

    @validator("backend_cors_origins", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @property
    def database_url_complete(self) -> str:
        """Get complete database URL based on environment"""
        if self.database_url:
            return self.database_url

        if self.environment == "production" and all(
            [
                self.postgres_server,
                self.postgres_user,
                self.postgres_password,
                self.postgres_db,
            ]
        ):
            return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"

        # Default to SQLite for development
        return f"sqlite:///./{self.sqlite_db_name}"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
