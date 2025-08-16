from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with authentication-specific methods"""

    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, email: str, hashed_password: str, full_name: str, **kwargs) -> User:
        """Create a new user with required fields"""
        user_data = {
            "email": email,
            "hashed_password": hashed_password,
            "full_name": full_name,
            **kwargs
        }
        return self.create(user_data)

    def update_last_login(self, user: User) -> User:
        """Update user's last login timestamp"""
        from datetime import datetime
        return self.update(user, {"last_login": datetime.utcnow()})

    def activate_user(self, user: User) -> User:
        """Activate a user account"""
        return self.update(user, {"is_active": True})

    def deactivate_user(self, user: User) -> User:
        """Deactivate a user account"""
        return self.update(user, {"is_active": False})

    def verify_user(self, user: User) -> User:
        """Mark user as verified"""
        return self.update(user, {"is_verified": True})

    def get_active_users(self, skip: int = 0, limit: int = 100):
        """Get all active users"""
        return (
            self.db.query(User)
            .filter(User.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )
