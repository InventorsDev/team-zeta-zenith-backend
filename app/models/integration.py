from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Text,
    JSON,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from .base import Base
from enum import Enum
import sqlalchemy as sa


class IntegrationType(str, Enum):
    SLACK = "slack"
    ZENDESK = "zendesk"
    EMAIL = "email"
    DISCORD = "discord"
    TEAMS = "teams"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class Integration(Base):
    """Integration model for external platform connections"""

    __tablename__ = "integrations"

    # Basic integration info
    name = Column(String(255), nullable=False)
    type = Column(sa.Enum(IntegrationType), nullable=False)
    status = Column(
        sa.Enum(IntegrationStatus), default=IntegrationStatus.PENDING, nullable=False
    )

    # Organization relationship
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="integrations")

    # Configuration (encrypted sensitive data)
    config = Column(JSON, nullable=True, default=dict)  # API keys, tokens, etc.
    settings = Column(JSON, nullable=True, default=dict)  # Non-sensitive settings

    # Connection details
    webhook_url = Column(String(512), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    webhook_token = Column(String(255), nullable=True, unique=True)  # Unique token for webhook URLs
    api_endpoint = Column(String(512), nullable=True)

    # Sync information
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    sync_frequency = Column(Integer, default=300, nullable=False)  # seconds

    # Features enabled
    sync_tickets = Column(Boolean, default=True, nullable=False)
    receive_webhooks = Column(Boolean, default=True, nullable=False)
    send_notifications = Column(Boolean, default=True, nullable=False)

    # Rate limiting
    rate_limit_per_hour = Column(Integer, default=1000, nullable=False)
    current_hour_requests = Column(Integer, default=0, nullable=False)
    rate_limit_reset_at = Column(DateTime, nullable=True)

    # Statistics
    total_tickets_synced = Column(Integer, default=0, nullable=False)
    total_webhooks_received = Column(Integer, default=0, nullable=False)

    # Relationships
    tickets = relationship("Ticket", back_populates="integration")

    def __repr__(self):
        return f"<Integration(name='{self.name}', type='{self.type}', status='{self.status}')>"
