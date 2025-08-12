from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Float,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship
from .base import Base
from enum import Enum
import sqlalchemy as sa


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    PENDING = "pending"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    ZENDESK = "zendesk"
    API = "api"
    WEB = "web"


class Ticket(Base):
    """Ticket model for customer support requests"""

    __tablename__ = "tickets"

    # Basic ticket information
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    external_id = Column(
        String(255), nullable=True, index=True
    )  # ID from external system

    # Status and priority
    status = Column(sa.Enum(TicketStatus), default=TicketStatus.OPEN, nullable=False)
    priority = Column(
        sa.Enum(TicketPriority), default=TicketPriority.MEDIUM, nullable=False
    )
    channel = Column(sa.Enum(TicketChannel), nullable=False)

    # Customer information
    customer_email = Column(String(255), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)

    # Assignment
    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    assignee = relationship("User", foreign_keys=[assigned_to])

    # Organization relationship
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="tickets")

    # Integration relationship
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=True)
    integration = relationship("Integration", back_populates="tickets")

    # Timestamps
    first_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    last_activity_at = Column(DateTime, nullable=True)

    # AI Analysis
    sentiment_score = Column(Float, nullable=True)  # -1 to 1 (negative to positive)
    category = Column(String(100), nullable=True)  # AI-classified category
    urgency_score = Column(Float, nullable=True)  # 0 to 1 (low to high urgency)
    confidence_score = Column(Float, nullable=True)  # 0 to 1 (AI confidence)

    # Tags and metadata
    tags = Column(JSON, nullable=True, default=list)  # List of string tags
    ticket_metadata = Column(JSON, nullable=True, default=dict)  # Additional metadata

    # Processing flags
    is_processed = Column(Boolean, default=False, nullable=False)
    needs_human_review = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<Ticket(title='{self.title[:50]}...', status='{self.status}')>"
