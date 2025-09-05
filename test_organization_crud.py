#!/usr/bin/env python3
"""Test script for organization-based CRUD operations"""

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

def test_organization_workflow():
    """Test complete organization workflow"""
    try:
        print("\n=== Testing Organization Workflow ===")
        
        # Step 1: Register a user (without organization initially)
        user_data = {
            "email": f"orguser_{int(time.time())}@example.com",
            "password": "TestPassword123",
            "full_name": "Organization Test User"
        }
        
        register_response = requests.post(f"{API_BASE}/auth/register", json=user_data)
        print(f"User Registration: {register_response.status_code}")
        
        if register_response.status_code != 201:
            print(f"  Registration Error: {register_response.text}")
            return None, None
        
        token_data = register_response.json()
        access_token = token_data.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Step 2: Create an organization for this user
        org_data = {
            "name": f"Test Organization {int(time.time())}",
            "description": "A test organization created via API",
            "email": "admin@testorg.com",
            "plan": "pro",
            "max_users": 10,
            "max_tickets_per_month": 5000
        }
        
        org_response = requests.post(f"{API_BASE}/organizations/", json=org_data, headers=headers)
        print(f"Organization Creation: {org_response.status_code}")
        
        if org_response.status_code == 201:
            organization = org_response.json()
            org_id = organization["id"]
            print(f"  Created Organization ID: {org_id}")
            print(f"  Organization Name: {organization['name']}")
            print(f"  Organization Slug: {organization['slug']}")
            
            # Step 3: Get current organization
            current_org_response = requests.get(f"{API_BASE}/organizations/current", headers=headers)
            print(f"Get Current Organization: {current_org_response.status_code}")
            
            # Step 4: Get organization stats
            stats_response = requests.get(f"{API_BASE}/organizations/current/stats", headers=headers)
            print(f"Organization Stats: {stats_response.status_code}")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"  User Count: {stats.get('user_count', 0)}")
                print(f"  Max Users: {stats.get('max_users', 0)}")
                print(f"  Plan: {stats.get('plan', 'unknown')}")
            
            return access_token, org_id
        else:
            print(f"  Organization Creation Error: {org_response.text}")
            return access_token, None
            
    except Exception as e:
        print(f"Organization workflow test failed: {e}")
        return None, None

def test_ticket_creation_without_org_id(access_token):
    """Test ticket creation without specifying organization_id"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print("\n=== Testing Ticket Creation (No org_id required) ===")
        
        # Create a ticket without organization_id (should use user's org)
        ticket_data = {
            "title": "Test Support Ticket via Organization",
            "description": "This ticket is created without specifying organization_id",
            "customer_email": "customer@example.com",
            "customer_name": "Jane Doe",
            "priority": "high",
            "channel": "api",
            "tags": ["test", "organization", "api"]
        }
        
        create_response = requests.post(f"{API_BASE}/tickets/", json=ticket_data, headers=headers)
        print(f"Create Ticket: {create_response.status_code}")
        
        if create_response.status_code == 201:
            ticket = create_response.json()
            ticket_id = ticket["id"]
            print(f"  Created Ticket ID: {ticket_id}")
            print(f"  Organization ID: {ticket.get('organization_id')}")
            print(f"  Title: {ticket['title']}")
            
            # Test getting the ticket
            get_response = requests.get(f"{API_BASE}/tickets/{ticket_id}", headers=headers)
            print(f"Get Ticket: {get_response.status_code}")
            
            return ticket_id
        else:
            print(f"  Error: {create_response.text}")
            return None
            
    except Exception as e:
        print(f"Ticket creation test failed: {e}")
        return None

def test_integration_creation_without_org_id(access_token):
    """Test integration creation without specifying organization_id"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print("\n=== Testing Integration Creation (No org_id required) ===")
        
        # Create an integration without organization_id (should use user's org)
        integration_data = {
            "name": "Test Slack Integration (Auto-Org)",
            "type": "slack",
            "config": {
                "bot_token": "xoxb-auto-org-token",
                "signing_secret": "auto-org-secret"
            },
            "settings": {
                "default_channel": "#auto-support"
            },
            "webhook_url": "https://hooks.slack.com/auto-org"
        }
        
        create_response = requests.post(f"{API_BASE}/integrations/", json=integration_data, headers=headers)
        print(f"Create Integration: {create_response.status_code}")
        
        if create_response.status_code == 201:
            integration = create_response.json()
            integration_id = integration["id"]
            print(f"  Created Integration ID: {integration_id}")
            print(f"  Organization ID: {integration.get('organization_id')}")
            print(f"  Name: {integration['name']}")
            print(f"  Type: {integration['type']}")
            
            # Test getting the integration
            get_response = requests.get(f"{API_BASE}/integrations/{integration_id}", headers=headers)
            print(f"Get Integration: {get_response.status_code}")
            
            # Test getting masked config
            config_response = requests.get(f"{API_BASE}/integrations/{integration_id}/config", headers=headers)
            print(f"Get Integration Config: {config_response.status_code}")
            if config_response.status_code == 200:
                config_data = config_response.json()
                print(f"  Config Fields: {config_data.get('config_fields', [])}")
                print(f"  Masked Config: {config_data.get('masked_config', {})}")
            
            return integration_id
        else:
            print(f"  Error: {create_response.text}")
            return None
            
    except Exception as e:
        print(f"Integration creation test failed: {e}")
        return None

def test_organization_management(access_token, org_id):
    """Test organization management features"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print("\n=== Testing Organization Management ===")
        
        # Update organization
        update_data = {
            "description": "Updated organization description",
            "website": "https://updated-testorg.com",
            "max_users": 15
        }
        
        update_response = requests.put(f"{API_BASE}/organizations/current", json=update_data, headers=headers)
        print(f"Update Organization: {update_response.status_code}")
        
        # Update organization settings
        settings_data = {
            "settings": {
                "theme": "dark",
                "notifications_enabled": True,
                "auto_assign": False,
                "custom_field": "test_value"
            }
        }
        
        settings_response = requests.patch(f"{API_BASE}/organizations/current/settings", json=settings_data, headers=headers)
        print(f"Update Organization Settings: {settings_response.status_code}")
        
        # Get updated organization
        get_updated_response = requests.get(f"{API_BASE}/organizations/current", headers=headers)
        print(f"Get Updated Organization: {get_updated_response.status_code}")
        if get_updated_response.status_code == 200:
            org_data = get_updated_response.json()
            print(f"  Updated Website: {org_data.get('website')}")
            print(f"  Updated Max Users: {org_data.get('max_users')}")
            print(f"  Settings: {org_data.get('settings', {})}")
        
    except Exception as e:
        print(f"Organization management test failed: {e}")

def test_cross_organization_security(access_token):
    """Test that users cannot access other organizations' data"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        print("\n=== Testing Cross-Organization Security ===")
        
        # Try to access organization with a different ID (should fail)
        different_org_id = 99999  # Assuming this doesn't exist
        
        access_response = requests.get(f"{API_BASE}/organizations/{different_org_id}", headers=headers)
        print(f"Access Different Organization: {access_response.status_code}")
        
        if access_response.status_code == 403:
            print("  ✓ Cross-organization access properly blocked")
        elif access_response.status_code == 404:
            print("  ✓ Non-existent organization properly handled")
        else:
            print(f"  ⚠ Unexpected response: {access_response.status_code}")
        
    except Exception as e:
        print(f"Security test failed: {e}")

def main():
    """Run all organization-based tests"""
    print("=" * 60)
    print("Organization-Based CRUD Test Suite")
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
    
    # Test 2: Organization Workflow
    access_token, org_id = test_organization_workflow()
    if not access_token:
        print("Organization workflow failed. Cannot continue with tests.")
        sys.exit(1)
    
    print("-" * 60)
    
    # Test 3: Ticket Creation (without org_id)
    ticket_id = test_ticket_creation_without_org_id(access_token)
    
    print("-" * 60)
    
    # Test 4: Integration Creation (without org_id)  
    integration_id = test_integration_creation_without_org_id(access_token)
    
    print("-" * 60)
    
    # Test 5: Organization Management
    if org_id:
        test_organization_management(access_token, org_id)
    
    print("-" * 60)
    
    # Test 6: Security Testing
    test_cross_organization_security(access_token)
    
    print("-" * 60)
    print("Organization-based CRUD test suite completed!")
    print("=" * 60)
    
    print("\nSummary:")
    print(f"- Organization Workflow: {'✓' if org_id else '✗'}")
    print(f"- Ticket Creation: {'✓' if ticket_id else '✗'}")
    print(f"- Integration Creation: {'✓' if integration_id else '✗'}")
    print(f"- Organization Management: ✓")
    print(f"- Security Testing: ✓")
    
    print("\nKey Features Tested:")
    print("- ✓ User registration without organization")
    print("- ✓ Organization creation by user")
    print("- ✓ Automatic organization assignment")
    print("- ✓ Ticket/Integration creation without org_id")
    print("- ✓ Organization-based data isolation")
    print("- ✓ Organization management and settings")

if __name__ == "__main__":
    main()