#!/usr/bin/env python3
"""
Test ML integration with server
"""
import requests
import json
import time

def test_with_server():
    """Test ticket creation with running server"""
    
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJvZ2JvIiwiZXhwIjoxNzU3MTM2NTE0fQ.-AHH9oZ4eO9DPafHD5rIlLSEiQRNwHWO5ix5Rz5QE2I"
    
    ticket_data = {
        "title": "Cannot login to account",
        "description": "I keep getting a 500 error when trying to log into my account. This is very frustrating and I need help immediately!",
        "customer_email": "test@example.com",
        "priority": "high", 
        "channel": "web"
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print("TESTING ML INTEGRATION WITH SERVER")
    print("=" * 50)
    
    # Check server status
    try:
        status_response = requests.get("http://localhost:8000/api/v1/status", timeout=5)
        print(f"[OK] Server running: {status_response.status_code}")
    except:
        print("[INFO] Start server first: PYTHONPATH=. python app/main.py")
        return
    
    # Test ticket creation
    try:
        print(f"\n1. Creating ticket...")
        print(f"   Title: {ticket_data['title']}")
        print(f"   Description: {ticket_data['description'][:50]}...")
        
        response = requests.post(
            "http://localhost:8000/api/v1/tickets",
            headers=headers,
            json=ticket_data,
            timeout=10
        )
        
        print(f"\n2. Response Status: {response.status_code}")
        
        if response.status_code == 201:
            ticket_response = response.json()
            print(f"\n3. Ticket Created Successfully!")
            print(f"   ID: {ticket_response.get('id')}")
            print(f"   Title: {ticket_response.get('title')}")
            
            # Check ML fields
            ml_fields = {k: v for k, v in ticket_response.items() if k.startswith('ml_')}
            print(f"\n4. ML Enhancement Results:")
            for field, value in ml_fields.items():
                print(f"   {field}: {value}")
            
            if ml_fields:
                print(f"\n[SUCCESS] ML integration working! ML fields populated.")
                
                # Test getting analysis for this ticket
                if ticket_response.get('id'):
                    print(f"\n5. Testing ML analysis endpoint...")
                    analysis_response = requests.get(
                        f"http://localhost:8000/api/v1/tickets/{ticket_response['id']}/analysis",
                        headers=headers,
                        timeout=10
                    )
                    
                    if analysis_response.status_code == 200:
                        analysis = analysis_response.json()
                        print(f"   Analysis: {json.dumps(analysis, indent=2)}")
                    else:
                        print(f"   Analysis failed: {analysis_response.status_code}")
                        
            else:
                print(f"\n[ISSUE] No ML fields found in response")
                
        else:
            print(f"\n[FAIL] Ticket creation failed: {response.status_code}")
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"[FAIL] Request failed: {e}")

if __name__ == "__main__":
    test_with_server()