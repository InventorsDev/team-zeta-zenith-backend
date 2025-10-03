"""
Alert Model - Stores alerts and notifications for tickets and organizations
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base
from enum import Enum


class AlertType(str, Enum):
    """Alert types"""
    HIGH_URGENCY = "high_urgency"
    SLA_BREACH = "sla_breach"
    SLA_WARNING = "sla_warning"
    ANOMALY = "anomaly"
    SPIKE = "spike"
    CUSTOM = "custom"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(Base):
    """Model for storing alerts and notifications"""

    __tablename__ = "alerts"

    # Relationships
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    ticket = relationship("Ticket", backref="alerts")

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization", backref="alerts")

    # Alert information
    alert_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    message = Column(String(2000), nullable=True)

    # Status
    is_resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Notification status
    is_notified = Column(Boolean, default=False, nullable=False)
    notified_at = Column(DateTime, nullable=True)
    notification_channels = Column(JSON, nullable=True, default=list)  # ["email", "slack", etc.]

    # Additional metadata
    alert_metadata = Column(JSON, nullable=True, default=dict)

    # Timestamps
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.alert_type}', severity='{self.severity}', resolved={self.is_resolved})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "organization_id": self.organization_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "is_resolved": self.is_resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "is_notified": self.is_notified,
            "notified_at": self.notified_at.isoformat() if self.notified_at else None,
            "notification_channels": self.notification_channels,
            "metadata": self.alert_metadata,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @property
    def is_critical(self):
        """Check if alert is critical"""
        return self.severity == AlertSeverity.CRITICAL.value

    @property
    def time_since_triggered(self):
        """Get time since alert was triggered"""
        if self.triggered_at:
            return datetime.utcnow() - self.triggered_at
        return None
