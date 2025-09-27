#!/usr/bin/env python3
"""
Test ticket creation with ML enhancement
"""
import json
import requests
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_ticket_creation():
    """Test creating a ticket with the provided token"""
    
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiZW1haWwiOiJvZ2JvIiwiZXhwIjoxNzU3MTM2NTE0fQ.-AHH9oZ4eO9DPafHD5rIlLSEiQRNwHWO5ix5Rz5QE2I"
    
    # Test data - using correct schema fields
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
    
    print("TESTING TICKET CREATION WITH ML ENHANCEMENT")
    print("=" * 50)
    
    # First, let's test if the server is running
    try:
        response = requests.get("http://localhost:8000/api/v1/status", timeout=5)
        print(f"[OK] Server is running: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Server not running: {e}")
        print("\nTo start server:")
        print("  PYTHONPATH=. python app/main.py")
        return False
    
    # Test ticket creation
    try:
        print(f"\n1. Creating ticket with data:")
        print(f"   Title: {ticket_data['title']}")
        print(f"   Description: {ticket_data['description'][:50]}...")
        
        response = requests.post(
            "http://localhost:8000/api/v1/tickets",
            headers=headers,
            json=ticket_data,
            timeout=10
        )
        
        print(f"\n2. Response status: {response.status_code}")
        
        if response.status_code == 201:
            ticket_response = response.json()
            print(f"\n3. Created ticket response:")
            print(json.dumps(ticket_response, indent=2))
            
            # Check for ML fields
            ml_fields = [k for k in ticket_response.keys() if k.startswith('ml_')]
            print(f"\n4. ML fields found: {ml_fields}")
            
            # Check specific ML values
            ml_category = ticket_response.get('ml_category')
            ml_sentiment = ticket_response.get('ml_sentiment')
            ml_confidence = ticket_response.get('ml_confidence')
            
            print(f"\n5. ML Analysis Results:")
            print(f"   Category: {ml_category}")
            print(f"   Sentiment: {ml_sentiment}")
            print(f"   Confidence: {ml_confidence}")
            
            if ml_category is None and ml_sentiment is None:
                print(f"\n[ISSUE] ML values are null - ML enhancement not working")
                return False
            else:
                print(f"\n[OK] ML enhancement working correctly")
                return True
                
        else:
            print(f"\n[FAIL] Ticket creation failed: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"[FAIL] Request failed: {e}")
        return False

def debug_ml_service():
    """Debug the ML service directly"""
    print("\n" + "=" * 50)
    print("DEBUGGING ML SERVICE DIRECTLY")
    print("=" * 50)
    
    try:
        from app.services.ml_service import ml_service
        
        test_text = "I keep getting a 500 error when trying to log into my account. This is very frustrating and I need help immediately!"
        
        print(f"1. ML Service Available: {ml_service.is_available}")
        
        # Test classification
        print(f"\n2. Testing classification...")
        classification = ml_service.classify_ticket(test_text)
        print(f"   Result: {classification}")
        
        # Test sentiment
        print(f"\n3. Testing sentiment analysis...")
        sentiment = ml_service.analyze_sentiment(test_text)
        print(f"   Result: {sentiment}")
        
        # Test enhancement
        print(f"\n4. Testing ticket data enhancement...")
        ticket_data = {
            "title": "Cannot login to account", 
            "description": test_text,
            "customer_email": "test@example.com",
            "priority": "high"
        }
        enhanced = ml_service.enhance_ticket_data(ticket_data)
        print(f"   Enhanced fields: {list(enhanced.keys())}")
        print(f"   ML fields: {[k for k in enhanced.keys() if k.startswith('ml_')]}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] ML service debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def debug_ticket_service():
    """Debug the ticket service integration"""
    print("\n" + "=" * 50)
    print("DEBUGGING TICKET SERVICE INTEGRATION")
    print("=" * 50)
    
    try:
        from app.services.ticket_service import TicketService
        from app.services.ml_service import ml_service
        from unittest.mock import Mock
        
        # Mock the database session and repositories
        mock_db = Mock()
        ticket_service = TicketService(mock_db)
        
        # Mock the repository create_ticket method
        mock_ticket = Mock()
        mock_ticket.id = 123
        mock_ticket.title = "Test Ticket"
        mock_ticket.content = "Test content"
        ticket_service.ticket_repo.create_ticket = Mock(return_value=mock_ticket)
        
        # Test data
        from app.schemas.ticket import TicketCreate
        ticket_data = TicketCreate(
            title="Cannot login to account", 
            description="I keep getting a 500 error when trying to log into my account. This is very frustrating and I need help immediately!",
            customer_email="test@example.com",
            priority="high",
            channel="web"
        )
        
        print(f"1. Testing ticket data enhancement in service...")
        
        # Test the enhancement process
        ticket_dict = ticket_data.dict()
        print(f"   Original data: {list(ticket_dict.keys())}")
        
        enhanced_dict = ml_service.enhance_ticket_data(ticket_dict)
        print(f"   Enhanced data: {list(enhanced_dict.keys())}")
        print(f"   ML fields: {[k for k in enhanced_dict.keys() if k.startswith('ml_')]}")
        
        # Check ML field values
        for key, value in enhanced_dict.items():
            if key.startswith('ml_'):
                print(f"   {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Ticket service debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run debugging tests"""
    
    # Test direct ML service
    ml_debug_ok = debug_ml_service()
    
    # Test ticket service integration  
    service_debug_ok = debug_ticket_service()
    
    # Test actual API if server is available
    api_test_ok = test_ticket_creation()
    
    print(f"\n" + "=" * 50)
    print("DEBUGGING SUMMARY")
    print("=" * 50)
    print(f"ML Service Debug: {'✓' if ml_debug_ok else '✗'}")
    print(f"Ticket Service Debug: {'✓' if service_debug_ok else '✗'}")
    print(f"API Test: {'✓' if api_test_ok else '✗'}")
    
    if not ml_debug_ok:
        print(f"\n[ISSUE] ML Service not working properly")
        print(f"- Check ML dependencies are installed")
        print(f"- Check ML models are available")
        
    if not api_test_ok:
        print(f"\n[ISSUE] API integration not working")
        print(f"- Make sure server is running: PYTHONPATH=. python app/main.py")
        print(f"- Check ML enhancement is properly integrated")
    
    return 0 if all([ml_debug_ok, service_debug_ok]) else 1

if __name__ == "__main__":
    sys.exit(main())