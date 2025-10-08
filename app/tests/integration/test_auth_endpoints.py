"""
Integration tests for Authentication API endpoints

Tests complete authentication workflows through the API
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.auth
@pytest.mark.api
class TestAuthEndpoints:
    """Test suite for auth API endpoints"""

    def test_register_success(self, client: TestClient, test_organization):
        """Test successful user registration via API"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "SecurePass123!",
                "full_name": "New Test User",
                "organization_id": test_organization.id
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client: TestClient, test_user):
        """Test registration with existing email"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "Password123!",
                "full_name": "Duplicate User",
                "organization_id": test_user.organization_id
            }
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient, test_organization):
        """Test registration with invalid email format"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invalid-email",
                "password": "Password123!",
                "full_name": "Test User",
                "organization_id": test_organization.id
            }
        )

        assert response.status_code == 422  # Validation error

    def test_login_success(self, client: TestClient, test_user):
        """Test successful login"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "user123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data

    def test_login_wrong_password(self, client: TestClient, test_user):
        """Test login with wrong password"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword"
            }
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user"""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "somepassword"
            }
        )

        assert response.status_code == 401

    def test_get_current_user(self, client: TestClient, test_user, user_headers):
        """Test getting current user info"""
        response = client.get(
            "/api/v1/auth/me",
            headers=user_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert data["id"] == test_user.id

    def test_get_current_user_without_token(self, client: TestClient):
        """Test accessing protected endpoint without token"""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 403  # Forbidden

    def test_get_current_user_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with invalid token"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401

    def test_refresh_token(self, client: TestClient, user_headers):
        """Test token refresh"""
        response = client.post(
            "/api/v1/auth/refresh",
            headers=user_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
