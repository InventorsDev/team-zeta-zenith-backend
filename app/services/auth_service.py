from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User
from app.database.repositories.user_repository import UserRepository
from app.core.security import verify_password, get_password_hash, create_token_response
from app.schemas.user import UserCreate, UserLogin


class AuthService:
    """Authentication service for user registration and login"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def register_user(self, user_data: UserCreate) -> dict:
        """Register a new user"""
        # Check if user already exists
        existing_user = self.user_repo.get_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Hash password and create user
        hashed_password = get_password_hash(user_data.password)
        user = self.user_repo.create_user(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            organization_id=user_data.organization_id
        )

        # Generate token response
        return create_token_response(user.id, user.email)

    def login_user(self, login_data: UserLogin) -> dict:
        """Authenticate user and return token"""
        # Get user by email
        user = self.user_repo.get_by_email(login_data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Verify password
        if not verify_password(login_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated"
            )

        # Update last login and generate token
        self.user_repo.update_last_login(user)
        return create_token_response(user.id, user.email)

    def get_current_user(self, token_payload: dict) -> User:
        """Get current user from token payload"""
        user_id = token_payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        user = self.user_repo.get(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated"
            )

        return user
