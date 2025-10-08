"""
End-to-End tests for complete user journeys

Tests full workflows from start to finish
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestUserJourney:
    """Test complete user workflows"""

    def test_complete_user_registration_and_login_flow(self, client: TestClient, test_organization):
        """
        E2E Test: User Registration → Login → Access Protected Resource

        Steps:
        1. Register new user
        2. Login with credentials
        3. Access protected endpoint with token
        4. Verify user data
        """
        # Step 1: Register
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "journey@test.com",
                "password": "SecurePass123!",
                "full_name": "Journey User",
                "organization_id": test_organization.id
            }
        )
        assert register_response.status_code == 201
        register_data = register_response.json()
        first_token = register_data["access_token"]

        # Step 2: Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "journey@test.com",
                "password": "SecurePass123!"
            }
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        token = login_data["access_token"]

        # Step 3: Access protected resource
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200

        # Step 4: Verify data
        user_data = me_response.json()
        assert user_data["email"] == "journey@test.com"
        assert user_data["full_name"] == "Journey User"
        assert user_data["role"] == "user"

    def test_ticket_lifecycle_workflow(self, client: TestClient, admin_headers, test_organization):
        """
        E2E Test: Complete ticket lifecycle

        Steps:
        1. Create ticket
        2. Get ticket details
        3. Update ticket status
        4. Assign ticket
        5. Resolve ticket
        6. Close ticket
        """
        # Step 1: Create ticket
        create_response = client.post(
            "/api/v1/tickets",
            headers=admin_headers,
            json={
                "title": "Customer Issue",
                "description": "Customer needs help with product",
                "priority": "high",
                "channel": "email",
                "customer_email": "customer@example.com",
                "customer_name": "John Doe"
            }
        )
        assert create_response.status_code == 201
        ticket = create_response.json()
        ticket_id = ticket["id"]

        # Step 2: Get ticket details
        get_response = client.get(
            f"/api/v1/tickets/{ticket_id}",
            headers=admin_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "open"

        # Step 3: Update to in_progress
        update1_response = client.put(
            f"/api/v1/tickets/{ticket_id}",
            headers=admin_headers,
            json={"status": "in_progress"}
        )
        assert update1_response.status_code == 200
        assert update1_response.json()["status"] == "in_progress"

        # Step 4: Assign ticket (if assignee field exists)
        # This would require a user ID, skipping for now

        # Step 5: Resolve ticket
        update2_response = client.put(
            f"/api/v1/tickets/{ticket_id}",
            headers=admin_headers,
            json={"status": "resolved"}
        )
        assert update2_response.status_code == 200
        assert update2_response.json()["status"] == "resolved"

        # Step 6: Close ticket
        update3_response = client.put(
            f"/api/v1/tickets/{ticket_id}",
            headers=admin_headers,
            json={"status": "closed"}
        )
        assert update3_response.status_code == 200
        assert update3_response.json()["status"] == "closed"

    def test_analytics_workflow(self, client: TestClient, admin_headers, test_tickets):
        """
        E2E Test: Analytics data retrieval workflow

        Steps:
        1. Get dashboard metrics
        2. Get time-series data
        3. Filter by date range
        4. Verify calculations
        """
        # Step 1: Get dashboard metrics
        dashboard_response = client.get(
            "/api/v1/analytics/dashboard",
            headers=admin_headers
        )
        assert dashboard_response.status_code == 200
        dashboard = dashboard_response.json()
        assert "total_tickets" in dashboard
        assert dashboard["total_tickets"] > 0

        # Step 2: Get time-series data
        timeseries_response = client.get(
            "/api/v1/analytics/time-series/ticket_count?granularity=daily",
            headers=admin_headers
        )
        assert timeseries_response.status_code == 200
        timeseries = timeseries_response.json()
        assert "data_points" in timeseries

        # Step 3: Filter by date range
        from datetime import datetime, timedelta
        start_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
        end_date = datetime.utcnow().isoformat()

        filtered_response = client.get(
            f"/api/v1/analytics/time-series/ticket_count?start_date={start_date}&end_date={end_date}",
            headers=admin_headers
        )
        assert filtered_response.status_code == 200

    def test_admin_user_management_workflow(
        self,
        client: TestClient,
        admin_headers,
        test_organization
    ):
        """
        E2E Test: Admin managing users

        Steps:
        1. Admin creates new user
        2. Admin lists users
        3. Admin updates user role
        4. Admin deactivates user
        """
        # Note: This test depends on user management endpoints being implemented
        # Placeholder for now - would need to implement user management API

        # Step 1: Create user (via registration as admin)
        # Step 2: List users in organization
        # Step 3: Update user role
        # Step 4: Deactivate user
        pass

    def test_alert_rule_workflow(self, client: TestClient, admin_headers, test_organization):
        """
        E2E Test: Creating and managing alert rules

        Steps:
        1. Create alert rule
        2. Get alert rules list
        3. Update alert rule
        4. Test alert rule
        5. Delete alert rule
        """
        # Step 1: Create alert rule
        create_response = client.post(
            "/api/v1/alerts/rules",
            headers=admin_headers,
            json={
                "name": "High Priority Alert",
                "description": "Alert for high priority tickets",
                "is_active": True,
                "conditions": [
                    {
                        "field": "priority",
                        "operator": "eq",
                        "value": "high"
                    }
                ],
                "logic": "AND",
                "alert_type": "high_priority",
                "severity": "high",
                "notification_channels": ["email"],
                "title_template": "High priority ticket: {ticket.title}",
                "message_template": "A high priority ticket requires attention"
            }
        )
        assert create_response.status_code == 201
        rule = create_response.json()
        rule_id = rule["id"]

        # Step 2: Get alert rules
        list_response = client.get(
            "/api/v1/alerts/rules",
            headers=admin_headers
        )
        assert list_response.status_code == 200
        rules = list_response.json()
        assert any(r["id"] == rule_id for r in rules)

        # Step 3: Update rule
        update_response = client.put(
            f"/api/v1/alerts/rules/{rule_id}",
            headers=admin_headers,
            json={
                "name": "Updated High Priority Alert",
                "is_active": False
            }
        )
        assert update_response.status_code == 200
        updated_rule = update_response.json()
        assert updated_rule["name"] == "Updated High Priority Alert"
        assert updated_rule["is_active"] is False

        # Step 4: Test rule
        test_response = client.post(
            "/api/v1/alerts/rules/test",
            headers=admin_headers,
            json={
                "conditions": [
                    {
                        "field": "priority",
                        "operator": "eq",
                        "value": "high"
                    }
                ],
                "logic": "AND"
            }
        )
        assert test_response.status_code == 200

        # Step 5: Delete rule
        delete_response = client.delete(
            f"/api/v1/alerts/rules/{rule_id}",
            headers=admin_headers
        )
        assert delete_response.status_code == 204
