from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from .base import Base


class AlertRule(Base):
    """Alert rule model for automated alert triggering"""

    __tablename__ = "alert_rules"

    # Basic Information
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Organization relationship
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="alert_rules")

    # Rule Configuration
    conditions = Column(JSON, nullable=False)  # List of AlertCondition objects
    logic = Column(String(10), default="AND", nullable=False)  # AND or OR

    # Alert Configuration
    alert_type = Column(String(50), nullable=False)  # sla_breach, high_priority, negative_sentiment, etc.
    severity = Column(String(20), nullable=False)  # low, medium, high, critical

    # Actions/Notifications
    notification_channels = Column(JSON, nullable=False)  # ["email", "slack", "webhook"]
    notification_config = Column(JSON, nullable=True)  # Additional config like webhook URLs

    # Thresholds and Limits
    cooldown_minutes = Column(Integer, default=60, nullable=False)  # Min time between same alerts
    max_triggers_per_day = Column(Integer, default=100, nullable=True)  # Rate limiting

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_triggered_at = Column(JSON, nullable=True)  # Timestamp of last trigger
    trigger_count = Column(Integer, default=0, nullable=False)  # Total times triggered

    # Custom message templates
    title_template = Column(String(500), nullable=True)  # e.g., "High priority ticket: {ticket.title}"
    message_template = Column(String(2000), nullable=True)

    def __repr__(self):
        return f"<AlertRule(name='{self.name}', org_id={self.organization_id}, active={self.is_active})>"
