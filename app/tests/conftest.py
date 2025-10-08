"""
Pytest configuration and shared fixtures

This file contains common fixtures and configuration used across all tests.
Fixtures are automatically discovered by pytest.
"""

import pytest
import os
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.connection import get_db
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.ticket import Ticket, TicketStatus, TicketPriority, TicketChannel
from app.core.security import get_password_hash, create_access_token


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Create a fresh test database for each test function

    Uses SQLite in-memory database for speed
    Each test gets a clean database state
    """
    # Create in-memory SQLite database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with the test database

    Overrides the get_db dependency to use the test database
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def test_organization(test_db: Session) -> Organization:
    """Create a test organization"""
    org = Organization(
        name="Test Organization",
        email="test@example.com",
        is_active=True
    )
    test_db.add(org)
    test_db.commit()
    test_db.refresh(org)
    return org


@pytest.fixture
def test_admin_user(test_db: Session, test_organization: Organization) -> User:
    """Create a test admin user"""
    user = User(
        email="admin@test.com",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin User",
        role=UserRole.ADMIN.value,
        organization_id=test_organization.id,
        is_active=True,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_manager_user(test_db: Session, test_organization: Organization) -> User:
    """Create a test manager user"""
    user = User(
        email="manager@test.com",
        hashed_password=get_password_hash("manager123"),
        full_name="Manager User",
        role=UserRole.MANAGER.value,
        organization_id=test_organization.id,
        is_active=True,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_agent_user(test_db: Session, test_organization: Organization) -> User:
    """Create a test agent user"""
    user = User(
        email="agent@test.com",
        hashed_password=get_password_hash("agent123"),
        full_name="Agent User",
        role=UserRole.AGENT.value,
        organization_id=test_organization.id,
        is_active=True,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_user(test_db: Session, test_organization: Organization) -> User:
    """Create a test regular user"""
    user = User(
        email="user@test.com",
        hashed_password=get_password_hash("user123"),
        full_name="Regular User",
        role=UserRole.USER.value,
        organization_id=test_organization.id,
        is_active=True,
        is_verified=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# ============================================================================
# Authentication Fixtures
# ============================================================================

@pytest.fixture
def admin_token(test_admin_user: User) -> str:
    """Create a JWT token for admin user"""
    return create_access_token(test_admin_user.id, test_admin_user.email)


@pytest.fixture
def manager_token(test_manager_user: User) -> str:
    """Create a JWT token for manager user"""
    return create_access_token(test_manager_user.id, test_manager_user.email)


@pytest.fixture
def agent_token(test_agent_user: User) -> str:
    """Create a JWT token for agent user"""
    return create_access_token(test_agent_user.id, test_agent_user.email)


@pytest.fixture
def user_token(test_user: User) -> str:
    """Create a JWT token for regular user"""
    return create_access_token(test_user.id, test_user.email)


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    """Create authorization headers for admin user"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def manager_headers(manager_token: str) -> dict:
    """Create authorization headers for manager user"""
    return {"Authorization": f"Bearer {manager_token}"}


@pytest.fixture
def agent_headers(agent_token: str) -> dict:
    """Create authorization headers for agent user"""
    return {"Authorization": f"Bearer {agent_token}"}


@pytest.fixture
def user_headers(user_token: str) -> dict:
    """Create authorization headers for regular user"""
    return {"Authorization": f"Bearer {user_token}"}


# ============================================================================
# Ticket Fixtures
# ============================================================================

@pytest.fixture
def test_ticket(test_db: Session, test_organization: Organization) -> Ticket:
    """Create a test ticket"""
    ticket = Ticket(
        title="Test Ticket",
        description="This is a test ticket description",
        status=TicketStatus.OPEN,
        priority=TicketPriority.MEDIUM,
        channel=TicketChannel.API,
        customer_email="customer@example.com",
        customer_name="Test Customer",
        organization_id=test_organization.id,
        sentiment_score=0.5,
        category="General",
        urgency_score=0.6,
        confidence_score=0.9,
        is_processed=True
    )
    test_db.add(ticket)
    test_db.commit()
    test_db.refresh(ticket)
    return ticket


@pytest.fixture
def test_tickets(test_db: Session, test_organization: Organization) -> list[Ticket]:
    """Create multiple test tickets"""
    tickets = []
    for i in range(10):
        ticket = Ticket(
            title=f"Test Ticket {i+1}",
            description=f"Description for test ticket {i+1}",
            status=TicketStatus.OPEN if i % 2 == 0 else TicketStatus.RESOLVED,
            priority=TicketPriority.HIGH if i < 3 else TicketPriority.MEDIUM,
            channel=TicketChannel.API,
            customer_email=f"customer{i+1}@example.com",
            customer_name=f"Customer {i+1}",
            organization_id=test_organization.id,
            sentiment_score=0.5 + (i * 0.05),
            category="General" if i % 2 == 0 else "Technical",
            is_processed=True
        )
        tickets.append(ticket)
        test_db.add(ticket)

    test_db.commit()
    for ticket in tickets:
        test_db.refresh(ticket)

    return tickets


# ============================================================================
# Environment Fixtures
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    """Set test environment variables"""
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
    yield
    # Cleanup
    os.environ.pop("TESTING", None)


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client"""
    mock_client = mocker.Mock()
    mock_client.get.return_value = None
    mock_client.set.return_value = True
    mock_client.delete.return_value = 1
    mock_client.exists.return_value = 0
    mocker.patch("app.cache.redis_client.get_redis_client", return_value=mock_client)
    return mock_client


@pytest.fixture
def mock_celery(mocker):
    """Mock Celery tasks"""
    mock_task = mocker.Mock()
    mock_task.delay.return_value = mocker.Mock(id="test-task-id")
    return mock_task


# ============================================================================
# Utility Functions
# ============================================================================

@pytest.fixture
def assert_valid_response():
    """Helper function to assert valid API responses"""
    def _assert(response, expected_status=200):
        assert response.status_code == expected_status, f"Expected {expected_status}, got {response.status_code}: {response.text}"
        return response.json()
    return _assert
