"""
Saved Search Model - Store user saved searches
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base


class SavedSearch(Base):
    """Model for storing user saved searches"""

    __tablename__ = "saved_searches"

    # Relationships
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User", backref="saved_searches")

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    organization = relationship("Organization", backref="saved_searches")

    # Search details
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    query = Column(String(500), nullable=True)
    conditions = Column(JSON, nullable=True, default=list)  # List of search conditions

    # Settings
    is_default = Column(Boolean, default=False, nullable=False)
    is_shared = Column(Boolean, default=False, nullable=False, index=True)

    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    use_count = Column(Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<SavedSearch(id={self.id}, name='{self.name}', user_id={self.user_id})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "name": self.name,
            "description": self.description,
            "query": self.query,
            "conditions": self.conditions,
            "is_default": self.is_default,
            "is_shared": self.is_shared,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "use_count": self.use_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
