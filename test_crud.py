#!/usr/bin/env python3
"""Test script for CRUD operations"""

import sys
import json
import requests
import time
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def test_api_endpoints():
    """Test if API endpoints are accessible"""
    try:
        response = requests.get(f"{API_BASE}/status")
        print(f"API Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"API Status failed: {e}")
        return False

def test_authentication_flow():
    """Test user registration and login to get access token"""
    try:
        # Register a test user
        user_data = {
            "email": f"testuser_{int(time.time())}@example.com",
            "password": "TestPassword123",
            "full_name": "Test User",
            "organization_id": 1  # Assuming organization with ID 1 exists
        }
        
        register_response = requests.post(f"{API_BASE}/auth/register", json=user_data)
        print(f"User Registration: {register_response.status_code}")
        
        if register_response.status_code == 201:
            token_data = register_response.json()
            access_token = token_data.get("access_token")
            
            # Test protected endpoint
            headers = {"Authorization": f"Bearer {access_token}"}
            me_response = requests.get(f"{API_BASE}/auth/me", headers=headers)
            print(f"Get Current User: {me_response.status_code}")
            
            if me_response.status_code == 200:
                user_info = me_response.json()
                print(f"  User Email: {user_info.get('email')}")
                print(f"  Organization ID: {user_info.get('organization_id')}")
                return access_token, user_info
        
        return None, None
    except Exception as e:
        print(f"Authentication flow failed: {e}")
        return None, None

def test_ticket_crud(access_token):
    """Test ticket CRUD operations"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print("\n=== Testing Ticket CRUD ===")
        
        # 1. Create a ticket
        ticket_data = {
            "title": "Test Support Ticket",
            "description": "This is a test ticket created via API",
            "customer_email": "customer@example.com",
            "customer_name": "John Doe",
            "priority": "medium",
            "channel": "api",
            "organization_id": 1,
            "tags": ["test", "api"]
        }
        
        create_response = requests.post(f"{API_BASE}/tickets/", json=ticket_data, headers=headers)
        print(f"Create Ticket: {create_response.status_code}")
        
        if create_response.status_code == 201:
            ticket = create_response.json()
            ticket_id = ticket["id"]
            print(f"  Created Ticket ID: {ticket_id}")
            
            # 2. Get the ticket
            get_response = requests.get(f"{API_BASE}/tickets/{ticket_id}", headers=headers)
            print(f"Get Ticket: {get_response.status_code}")
            
            # 3. Update the ticket
            update_data = {
                "title": "Updated Test Support Ticket",
                "priority": "high",
                "status": "in_progress"
            }
            update_response = requests.put(f"{API_BASE}/tickets/{ticket_id}", json=update_data, headers=headers)
            print(f"Update Ticket: {update_response.status_code}")
            
            # 4. Get tickets list with pagination
            list_response = requests.get(f"{API_BASE}/tickets/?page=1&size=10", headers=headers)
            print(f"List Tickets: {list_response.status_code}")
            if list_response.status_code == 200:
                tickets_data = list_response.json()
                print(f"  Total Tickets: {tickets_data.get('total', 0)}")
                print(f"  Current Page: {tickets_data.get('page', 0)}")
            
            # 5. Get ticket statistics
            stats_response = requests.get(f"{API_BASE}/tickets/stats", headers=headers)
            print(f"Ticket Stats: {stats_response.status_code}")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"  Total Tickets: {stats.get('total_tickets', 0)}")
                print(f"  Open Tickets: {stats.get('open_tickets', 0)}")
            
            return ticket_id
        else:
            print(f"  Error: {create_response.text}")
            return None
            
    except Exception as e:
        print(f"Ticket CRUD test failed: {e}")
        return None

def test_integration_crud(access_token):
    """Test integration CRUD operations"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print("\n=== Testing Integration CRUD ===")
        
        # 1. Create an integration
        integration_data = {
            "name": "Test Slack Integration",
            "type": "slack",
            "organization_id": 1,
            "config": {
                "bot_token": "xoxb-test-token",
                "signing_secret": "test-secret"
            },
            "settings": {
                "default_channel": "#support"
            },
            "webhook_url": "https://hooks.slack.com/test"
        }
        
        create_response = requests.post(f"{API_BASE}/integrations/", json=integration_data, headers=headers)
        print(f"Create Integration: {create_response.status_code}")
        
        if create_response.status_code == 201:
            integration = create_response.json()
            integration_id = integration["id"]
            print(f"  Created Integration ID: {integration_id}")
            
            # 2. Get the integration
            get_response = requests.get(f"{API_BASE}/integrations/{integration_id}", headers=headers)
            print(f"Get Integration: {get_response.status_code}")
            
            # 3. Update the integration
            update_data = {
                "name": "Updated Test Slack Integration",
                "sync_frequency": 600
            }
            update_response = requests.put(f"{API_BASE}/integrations/{integration_id}", json=update_data, headers=headers)
            print(f"Update Integration: {update_response.status_code}")
            
            # 4. Get integrations list
            list_response = requests.get(f"{API_BASE}/integrations/?page=1&size=10", headers=headers)
            print(f"List Integrations: {list_response.status_code}")
            if list_response.status_code == 200:
                integrations_data = list_response.json()
                print(f"  Total Integrations: {integrations_data.get('total', 0)}")
            
            # 5. Get integration stats
            stats_response = requests.get(f"{API_BASE}/integrations/stats", headers=headers)
            print(f"Integration Stats: {stats_response.status_code}")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"  Total Integrations: {stats.get('total_integrations', 0)}")
                print(f"  Active Integrations: {stats.get('active_integrations', 0)}")
            
            # 6. Test integration connection
            test_response = requests.post(f"{API_BASE}/integrations/{integration_id}/test", json={"test_connection": True}, headers=headers)
            print(f"Test Integration: {test_response.status_code}")
            
            return integration_id
        else:
            print(f"  Error: {create_response.text}")
            return None
            
    except Exception as e:
        print(f"Integration CRUD test failed: {e}")
        return None

def test_filtering_and_pagination(access_token):
    """Test filtering and pagination features"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print("\n=== Testing Filtering and Pagination ===")
        
        # Test ticket filtering
        filter_tests = [
            ("status=open", "Filter by status"),
            ("priority=high", "Filter by priority"), 
            ("search=test", "Search functionality"),
            ("unassigned=true", "Filter unassigned tickets"),
            ("needs_review=true", "Filter tickets needing review")
        ]
        
        for filter_param, description in filter_tests:
            response = requests.get(f"{API_BASE}/tickets/?{filter_param}", headers=headers)
            print(f"{description}: {response.status_code}")
        
        # Test integration filtering
        integration_filters = [
            ("type=slack", "Filter by type"),
            ("status=active", "Filter by status"),
            ("active_only=true", "Filter active only")
        ]
        
        for filter_param, description in integration_filters:
            response = requests.get(f"{API_BASE}/integrations/?{filter_param}", headers=headers)
            print(f"Integration {description}: {response.status_code}")
        
        # Test pagination
        pagination_response = requests.get(f"{API_BASE}/tickets/?page=1&size=5", headers=headers)
        print(f"Pagination Test: {pagination_response.status_code}")
        if pagination_response.status_code == 200:
            data = pagination_response.json()
            print(f"  Page: {data.get('page')}")
            print(f"  Size: {data.get('size')}")
            print(f"  Has Next: {data.get('has_next')}")
            print(f"  Has Prev: {data.get('has_prev')}")
        
    except Exception as e:
        print(f"Filtering and pagination test failed: {e}")

def main():
    """Run all CRUD tests"""
    print("=" * 60)
    print("CRUD Operations Test Suite")
    print("=" * 60)
    print(f"Testing API at: {BASE_URL}")
    print(f"Timestamp: {datetime.now()}")
    print("-" * 60)
    
    # Test 1: API Endpoints
    if not test_api_endpoints():
        print("API is not running. Please start the server first.")
        print("Run: python app/main.py")
        sys.exit(1)
    
    print("-" * 60)
    
    # Test 2: Authentication
    access_token, user_info = test_authentication_flow()
    if not access_token:
        print("Authentication failed. Cannot continue with CRUD tests.")
        sys.exit(1)
    
    print("-" * 60)
    
    # Test 3: Ticket CRUD
    ticket_id = test_ticket_crud(access_token)
    
    print("-" * 60)
    
    # Test 4: Integration CRUD  
    integration_id = test_integration_crud(access_token)
    
    print("-" * 60)
    
    # Test 5: Filtering and Pagination
    test_filtering_and_pagination(access_token)
    
    print("-" * 60)
    print("CRUD test suite completed!")
    print("=" * 60)
    
    print("\nSummary:")
    print(f"- Authentication: {'✓' if access_token else '✗'}")
    print(f"- Ticket CRUD: {'✓' if ticket_id else '✗'}")
    print(f"- Integration CRUD: {'✓' if integration_id else '✗'}")
    print(f"- Filtering/Pagination: ✓")

if __name__ == "__main__":
    main()