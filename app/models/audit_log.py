"""
Audit Log Model - Tracks security-relevant actions
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class AuditLog(Base):
    """
    Audit log model for tracking security-relevant actions

    Tracks: Authentication attempts, data modifications, permission changes,
    configuration updates, API access, etc.
    """

    __tablename__ = "audit_logs"

    # User who performed the action (nullable for anonymous actions)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user = relationship("User", backref="audit_logs")

    # Organization context (nullable for system-level actions)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=True, index=True
    )
    organization = relationship("Organization", backref="audit_logs")

    # Action details
    action = Column(String(100), nullable=False, index=True)  # e.g., "user.login", "ticket.create"
    resource_type = Column(String(50), nullable=True, index=True)  # e.g., "ticket", "user", "organization"
    resource_id = Column(String(100), nullable=True, index=True)  # ID of affected resource
    status = Column(String(20), nullable=False, index=True)  # "success", "failure", "unauthorized"

    # Request context
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(255), nullable=True)
    http_method = Column(String(10), nullable=True)  # GET, POST, PUT, DELETE, etc.

    # Additional details
    details = Column(JSON, nullable=True)  # Additional context (changes made, error details, etc.)
    severity = Column(String(20), default="info", nullable=False)  # "info", "warning", "critical"

    # Timestamp (automatically set by Base model)
    # created_at field is inherited from Base

    # Indexes for common query patterns
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_action_status", "action", "status"),
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_org_created", "organization_id", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id}, status={self.status})>"
