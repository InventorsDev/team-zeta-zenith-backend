from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .base import Base
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base):
    """User model for authentication and authorization"""

    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    role = Column(String(10), default=UserRole.USER.value, nullable=False)

    # Organization relationship
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization", back_populates="users")

    # Profile information
    avatar_url = Column(String(512), nullable=True)
    timezone = Column(String(50), default="UTC", nullable=False)
    last_login = Column(DateTime, nullable=True)

    # Preferences
    email_notifications = Column(Boolean, default=True, nullable=False)
    slack_notifications = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<User(email='{self.email}', full_name='{self.full_name}')>"
