from sqlalchemy import Column, Integer, String, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from .base import Base


class Organization(Base):
    """Organization model for multi-tenant support"""

    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)

    # Contact information
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)

    # Settings
    is_active = Column(Boolean, default=True, nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)
    logo_url = Column(String(512), nullable=True)

    # Configuration settings stored as JSON
    settings = Column(JSON, nullable=True, default=dict)

    # Subscription info
    plan = Column(String(50), default="free", nullable=False)  # free, pro, enterprise
    max_users = Column(Integer, default=5, nullable=False)
    max_tickets_per_month = Column(Integer, default=1000, nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization")
    tickets = relationship("Ticket", back_populates="organization")
    integrations = relationship("Integration", back_populates="organization")
    email_integrations = relationship("EmailIntegration", back_populates="organization")

    def __repr__(self):
        return f"<Organization(name='{self.name}', slug='{self.slug}')>"
