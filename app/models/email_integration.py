"""
Email Integration Database Model
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, JSON, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class EmailIntegration(Base):
    """Email integration configuration model"""
    
    __tablename__ = "email_integrations"
    
    # Foreign key to organization
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Email configuration
    provider = Column(String(50), nullable=False)  # gmail, outlook, yahoo, icloud, custom
    email = Column(String(255), nullable=False)
    password = Column(Text, nullable=False)  # Should be encrypted in production
    server = Column(String(255), nullable=True)  # For custom providers
    port = Column(Integer, default=993, nullable=False)
    ssl = Column(Boolean, default=True, nullable=False)
    
    # Mailbox configuration (stored as JSON)
    mailboxes = Column(JSON, nullable=False, default=lambda: {
        "INBOX": {"enabled": True, "process_all": True}
    })
    
    # Processing settings
    sync_frequency = Column(Integer, default=300, nullable=False)  # seconds
    auto_create_tickets = Column(Boolean, default=True, nullable=False)
    auto_reply = Column(Boolean, default=False, nullable=False)
    batch_size = Column(Integer, default=50, nullable=False)
    days_back = Column(Integer, default=7, nullable=False)
    
    # Status and activity
    is_active = Column(Boolean, default=True, nullable=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Processing statistics
    total_emails_processed = Column(Integer, default=0, nullable=False)
    total_tickets_created = Column(Integer, default=0, nullable=False)
    total_duplicates_filtered = Column(Integer, default=0, nullable=False)
    avg_processing_time = Column(Float, default=0.0, nullable=False)
    
    # Auto-reply template
    auto_reply_template = Column(Text, nullable=True)
    
    # Relationships
    organization = relationship("Organization", back_populates="email_integrations")
    processing_logs = relationship("EmailProcessingLog", back_populates="integration", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<EmailIntegration(org={self.organization_id}, provider='{self.provider}', email='{self.email}')>"

class EmailProcessingLog(Base):
    """Log of email processing activities"""
    
    __tablename__ = "email_processing_logs"
    
    # Foreign key to integration
    integration_id = Column(Integer, ForeignKey("email_integrations.id"), nullable=False, index=True)
    
    # Processing details
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=False)  # success, error, partial
    
    # Processing statistics
    emails_processed = Column(Integer, default=0, nullable=False)
    emails_new = Column(Integer, default=0, nullable=False)
    emails_duplicate = Column(Integer, default=0, nullable=False)
    tickets_created = Column(Integer, default=0, nullable=False)
    processing_time = Column(Float, default=0.0, nullable=False)
    
    # Mailbox-specific results (stored as JSON)
    mailbox_results = Column(JSON, nullable=True)
    
    # Error information
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Relationships
    integration = relationship("EmailIntegration", back_populates="processing_logs")
    
    def __repr__(self):
        return f"<EmailProcessingLog(integration={self.integration_id}, status='{self.status}')>"