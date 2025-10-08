"""
Integration tests for Ticket API endpoints

Tests ticket CRUD operations and filtering
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
@pytest.mark.api
class TestTicketEndpoints:
    """Test suite for ticket API endpoints"""

    def test_create_ticket(self, client: TestClient, admin_headers, test_organization):
        """Test creating a new ticket"""
        response = client.post(
            "/api/v1/tickets",
            headers=admin_headers,
            json={
                "title": "Test Ticket",
                "description": "This is a test ticket",
                "priority": "high",
                "channel": "api",
                "customer_email": "customer@test.com",
                "customer_name": "Test Customer"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Ticket"
        assert data["priority"] == "high"
        assert data["status"] == "open"
        assert "id" in data

    def test_get_tickets_list(self, client: TestClient, admin_headers, test_tickets):
        """Test getting list of tickets"""
        response = client.get(
            "/api/v1/tickets",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) > 0

    def test_get_ticket_by_id(self, client: TestClient, admin_headers, test_ticket):
        """Test getting a specific ticket"""
        response = client.get(
            f"/api/v1/tickets/{test_ticket.id}",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_ticket.id
        assert data["title"] == test_ticket.title

    def test_get_nonexistent_ticket(self, client: TestClient, admin_headers):
        """Test getting a non-existent ticket"""
        response = client.get(
            "/api/v1/tickets/99999",
            headers=admin_headers
        )

        assert response.status_code == 404

    def test_update_ticket(self, client: TestClient, admin_headers, test_ticket):
        """Test updating a ticket"""
        response = client.put(
            f"/api/v1/tickets/{test_ticket.id}",
            headers=admin_headers,
            json={
                "title": "Updated Title",
                "priority": "urgent",
                "status": "in_progress"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["priority"] == "urgent"
        assert data["status"] == "in_progress"

    def test_delete_ticket(self, client: TestClient, admin_headers, test_ticket):
        """Test deleting a ticket"""
        response = client.delete(
            f"/api/v1/tickets/{test_ticket.id}",
            headers=admin_headers
        )

        assert response.status_code == 204

        # Verify ticket is deleted
        get_response = client.get(
            f"/api/v1/tickets/{test_ticket.id}",
            headers=admin_headers
        )
        assert get_response.status_code == 404

    def test_filter_tickets_by_status(self, client: TestClient, admin_headers, test_tickets):
        """Test filtering tickets by status"""
        response = client.get(
            "/api/v1/tickets?status=open",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert all(ticket["status"] == "open" for ticket in data["items"])

    def test_filter_tickets_by_priority(self, client: TestClient, admin_headers, test_tickets):
        """Test filtering tickets by priority"""
        response = client.get(
            "/api/v1/tickets?priority=high",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert all(ticket["priority"] == "high" for ticket in data["items"])

    def test_pagination(self, client: TestClient, admin_headers, test_tickets):
        """Test ticket pagination"""
        response = client.get(
            "/api/v1/tickets?page=1&size=5",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 5
        assert data["page"] == 1
        assert data["size"] == 5

    def test_unauthorized_access(self, client: TestClient, test_ticket):
        """Test accessing tickets without authentication"""
        response = client.get("/api/v1/tickets")
        assert response.status_code == 403

    def test_agent_can_read_tickets(self, client: TestClient, agent_headers, test_ticket):
        """Test agent can read tickets"""
        response = client.get(
            f"/api/v1/tickets/{test_ticket.id}",
            headers=agent_headers
        )

        assert response.status_code == 200

    def test_user_cannot_delete_tickets(self, client: TestClient, user_headers, test_ticket):
        """Test regular user cannot delete tickets"""
        response = client.delete(
            f"/api/v1/tickets/{test_ticket.id}",
            headers=user_headers
        )

        assert response.status_code == 403
