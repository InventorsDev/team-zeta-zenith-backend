#!/usr/bin/env python3
"""
Simple test to verify the database fix
"""
import requests
import json

def test_ticket_creation():
    """Test ticket creation with the fix"""
    
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJvZ2JvIiwiZXhwIjoxNzU3MTM2NTE0fQ.-AHH9oZ4eO9DPafHD5rIlLSEiQRNwHWO5ix5Rz5QE2I"
    
    ticket_data = {
        "title": "Login Issue Fixed",
        "description": "I cannot login to my account, getting error 500. Please help!",
        "customer_email": "user@example.com",
        "priority": "high",
        "channel": "web"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("TESTING TICKET CREATION WITH DATABASE FIX")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/api/v1/status", timeout=5)
        print(f"[OK] Server running: {response.status_code}")
    except:
        print("[INFO] Server not running. Start with: PYTHONPATH=. python app/main.py")
        print("\nExpected behavior after fix:")
        print("1. Ticket creation should NOT fail with SQLAlchemy errors")
        print("2. Response should include ML fields")
        print("3. Database should only store non-ML fields")
        return
    
    # Test ticket creation
    try:
        print(f"\nCreating ticket...")
        print(f"Title: {ticket_data['title']}")
        print(f"Description: {ticket_data['description'][:50]}...")
        
        response = requests.post(
            "http://localhost:8000/api/v1/tickets",
            headers=headers,
            json=ticket_data,
            timeout=10
        )
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print(f"\n[SUCCESS] Ticket created!")
            print(f"ID: {result.get('id')}")
            
            # Check for ML fields
            ml_fields = {k: v for k, v in result.items() if k.startswith('ml_')}
            print(f"\nML Fields in Response:")
            for field, value in ml_fields.items():
                print(f"  {field}: {value}")
                
            if ml_fields:
                print(f"\n✓ ML enhancement working!")
                print(f"✓ No database errors!")
                print(f"✓ ML fields included in API response!")
            else:
                print(f"\n[ISSUE] No ML fields in response")
                
        elif response.status_code == 500:
            print(f"\n[ERROR] Internal server error - check if database fix worked:")
            print(f"Error: {response.text}")
        else:
            print(f"\n[ERROR] Unexpected status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")

if __name__ == "__main__":
    test_ticket_creation()