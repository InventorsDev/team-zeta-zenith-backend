"""
Unit tests for Authentication Service

Tests authentication logic, password hashing, token generation, etc.
"""

import pytest
from fastapi import HTTPException
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserLogin
from app.models.user import User, UserRole
from app.core.security import verify_password


@pytest.mark.unit
@pytest.mark.auth
class TestAuthService:
    """Test suite for AuthService"""

    def test_register_user_success(self, test_db, test_organization):
        """Test successful user registration"""
        auth_service = AuthService(test_db)

        user_data = UserCreate(
            email="newuser@test.com",
            password="SecurePassword123!",
            full_name="New User",
            organization_id=test_organization.id
        )

        result = auth_service.register_user(user_data)

        # Verify response structure
        assert "access_token" in result
        assert "token_type" in result
        assert result["token_type"] == "bearer"

        # Verify user was created in database
        user = test_db.query(User).filter(User.email == user_data.email).first()
        assert user is not None
        assert user.email == user_data.email
        assert user.full_name == user_data.full_name
        assert user.organization_id == test_organization.id
        assert user.role == UserRole.USER.value
        assert verify_password("SecurePassword123!", user.hashed_password)

    def test_register_user_duplicate_email(self, test_db, test_user):
        """Test registration with existing email fails"""
        auth_service = AuthService(test_db)

        user_data = UserCreate(
            email=test_user.email,  # Already exists
            password="SecurePassword123!",
            full_name="Duplicate User",
            organization_id=test_user.organization_id
        )

        with pytest.raises(HTTPException) as exc:
            auth_service.register_user(user_data)

        assert exc.value.status_code == 400
        assert "already registered" in str(exc.value.detail).lower()

    def test_login_success(self, test_db, test_user):
        """Test successful login"""
        auth_service = AuthService(test_db)

        login_data = UserLogin(
            email=test_user.email,
            password="user123"  # Password from fixture
        )

        result = auth_service.login_user(login_data)

        assert "access_token" in result
        assert "token_type" in result
        assert result["token_type"] == "bearer"
        assert result["access_token"] is not None

    def test_login_wrong_password(self, test_db, test_user):
        """Test login with wrong password fails"""
        auth_service = AuthService(test_db)

        login_data = UserLogin(
            email=test_user.email,
            password="wrongpassword"
        )

        with pytest.raises(HTTPException) as exc:
            auth_service.login_user(login_data)

        assert exc.value.status_code == 401
        assert "incorrect" in str(exc.value.detail).lower()

    def test_login_nonexistent_user(self, test_db):
        """Test login with non-existent user fails"""
        auth_service = AuthService(test_db)

        login_data = UserLogin(
            email="nonexistent@test.com",
            password="somepassword"
        )

        with pytest.raises(HTTPException) as exc:
            auth_service.login_user(login_data)

        assert exc.value.status_code == 401
        assert "incorrect" in str(exc.value.detail).lower()

    def test_login_inactive_user(self, test_db, test_user):
        """Test login with inactive user fails"""
        # Make user inactive
        test_user.is_active = False
        test_db.commit()

        auth_service = AuthService(test_db)

        login_data = UserLogin(
            email=test_user.email,
            password="user123"
        )

        with pytest.raises(HTTPException) as exc:
            auth_service.login_user(login_data)

        assert exc.value.status_code == 400
        assert "inactive" in str(exc.value.detail).lower()

    def test_get_current_user(self, test_db, test_user):
        """Test retrieving current user from token payload"""
        auth_service = AuthService(test_db)

        payload = {"sub": str(test_user.id)}
        user = auth_service.get_current_user(payload)

        assert user.id == test_user.id
        assert user.email == test_user.email

    def test_get_current_user_invalid_id(self, test_db):
        """Test invalid user ID in payload"""
        auth_service = AuthService(test_db)

        payload = {"sub": "99999"}  # Non-existent user

        with pytest.raises(HTTPException) as exc:
            auth_service.get_current_user(payload)

        assert exc.value.status_code == 401
