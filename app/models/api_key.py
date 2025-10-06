"""
API Key Model - For programmatic access to the API
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import secrets

from app.models.base import Base


class APIKey(Base):
    """
    API Key model for programmatic API access

    Provides alternative authentication method to JWT tokens for
    server-to-server integrations, webhooks, and automated systems
    """

    __tablename__ = "api_keys"

    # Key identification
    name = Column(String(255), nullable=False)  # Human-readable name
    key_prefix = Column(String(10), nullable=False, index=True)  # First 8 chars for identification
    key_hash = Column(String(255), nullable=False, unique=True)  # bcrypt hash of full key

    # Ownership
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization", backref="api_keys")

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator = relationship("User", backref="api_keys_created")

    # Status and lifecycle
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)  # Null = never expires
    last_used_at = Column(DateTime, nullable=True)

    # Permissions and scopes
    scopes = Column(JSON, nullable=False, default=list)  # List of permitted scopes/permissions
    ip_whitelist = Column(JSON, nullable=True)  # Optional IP whitelist

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    rate_limit = Column(Integer, nullable=True)  # Optional custom rate limit (requests per minute)

    # Metadata
    description = Column(String(1000), nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional key metadata

    # Indexes for common queries
    __table_args__ = (
        Index("ix_api_keys_org_active", "organization_id", "is_active"),
        Index("ix_api_keys_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<APIKey(id={self.id}, name={self.name}, prefix={self.key_prefix}, org={self.organization_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if API key has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if API key is valid (active and not expired)"""
        return self.is_active and not self.is_expired

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key"""
        # Format: zz_live_<48 char random string>
        # Total length: 56 characters
        random_part = secrets.token_urlsafe(36)  # ~48 chars base64
        return f"zz_live_{random_part}"

    @staticmethod
    def generate_test_key() -> str:
        """Generate a test/sandbox API key"""
        random_part = secrets.token_urlsafe(36)
        return f"zz_test_{random_part}"

    @staticmethod
    def extract_prefix(key: str) -> str:
        """Extract the prefix from an API key for identification"""
        # Return first 12 characters (e.g., "zz_live_abcd")
        return key[:12] if len(key) >= 12 else key
