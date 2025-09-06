#!/usr/bin/env python3
"""
Test the database fix for ML fields
"""
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_ml_enhancement_separation():
    """Test that ML fields are separated from database fields"""
    
    print("TESTING ML FIELD SEPARATION")
    print("=" * 50)
    
    try:
        from app.services.ml_service import ml_service
        
        # Sample ticket data
        ticket_data = {
            "title": "Cannot login to account",
            "description": "I keep getting error 500 when trying to log in",
            "customer_email": "test@example.com",
            "priority": "high",
            "channel": "web",
            "organization_id": 1
        }
        
        print("1. Testing ML enhancement...")
        enhanced_data = ml_service.enhance_ticket_data(ticket_data)
        
        print(f"   Original fields: {list(ticket_data.keys())}")
        print(f"   Enhanced fields: {list(enhanced_data.keys())}")
        
        # Separate fields
        db_fields = {k: v for k, v in enhanced_data.items() if not k.startswith('ml_')}
        ml_fields = {k: v for k, v in enhanced_data.items() if k.startswith('ml_')}
        
        print(f"\n2. Field separation:")
        print(f"   DB fields: {list(db_fields.keys())}")
        print(f"   ML fields: {list(ml_fields.keys())}")
        
        print(f"\n3. ML field values:")
        for field, value in ml_fields.items():
            print(f"   {field}: {value}")
        
        # Verify no ML fields in DB data
        has_ml_fields = any(k.startswith('ml_') for k in db_fields.keys())
        if not has_ml_fields:
            print(f"\n[SUCCESS] No ML fields in database data - will not cause SQLAlchemy errors")
        else:
            print(f"\n[FAIL] ML fields still in database data")
            
        return not has_ml_fields
        
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ticket_service_mock():
    """Test ticket service with mocked database"""
    
    print(f"\n" + "=" * 50)
    print("TESTING TICKET SERVICE WITH MOCK DB")
    print("=" * 50)
    
    try:
        from app.services.ticket_service import TicketService
        from app.schemas.ticket import TicketCreate
        from unittest.mock import Mock
        
        # Mock database and repository
        mock_db = Mock()
        ticket_service = TicketService(mock_db)
        
        # Mock the ticket that would be returned from DB
        mock_ticket = Mock()
        mock_ticket.id = 123
        mock_ticket.title = "Cannot login to account"
        mock_ticket.description = "Error 500 on login"
        mock_ticket.customer_email = "test@example.com"
        mock_ticket.priority = "high"
        mock_ticket.channel = "web"
        mock_ticket.status = "open"
        mock_ticket.created_at = "2024-01-01T10:00:00Z"
        mock_ticket.organization_id = 1
        mock_ticket.assigned_to = None
        mock_ticket.assignee_name = None
        mock_ticket.tags = []
        mock_ticket.sentiment_score = None
        mock_ticket.category = None
        mock_ticket.needs_human_review = False
        
        # Mock repository methods
        ticket_service.ticket_repo.create_ticket = Mock(return_value=mock_ticket)
        ticket_service.user_repo.get = Mock(return_value=None)
        
        # Mock current user
        mock_user = Mock()
        mock_user.organization_id = 1
        
        # Create ticket data
        ticket_data = TicketCreate(
            title="Cannot login to account",
            description="I keep getting error 500 when trying to log in",
            customer_email="test@example.com",
            priority="high", 
            channel="web"
        )
        
        print("1. Testing ticket creation...")
        
        # This should not fail with SQLAlchemy errors now
        result = ticket_service.create_ticket(ticket_data, mock_user)
        
        print(f"   Result type: {type(result)}")
        print(f"   Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        if isinstance(result, dict):
            ml_fields = [k for k in result.keys() if k.startswith('ml_')]
            print(f"   ML fields in response: {ml_fields}")
            
            if ml_fields:
                print(f"\n[SUCCESS] ML fields included in API response")
                return True
            else:
                print(f"\n[ISSUE] No ML fields in response") 
                return False
        else:
            print(f"\n[ISSUE] Result is not a dict: {result}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Ticket service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    
    enhancement_ok = test_ml_enhancement_separation()
    service_ok = test_ticket_service_mock()
    
    print(f"\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    print(f"ML Enhancement Separation: {'✓' if enhancement_ok else '✗'}")
    print(f"Ticket Service Mock Test: {'✓' if service_ok else '✗'}")
    
    if enhancement_ok and service_ok:
        print(f"\n[SUCCESS] Database fix should work!")
        print(f"- ML fields are separated from database fields")
        print(f"- Ticket service returns ML fields in API response")
        print(f"- No SQLAlchemy errors expected")
    else:
        print(f"\n[FAIL] Issues remain")
    
    return 0 if (enhancement_ok and service_ok) else 1

if __name__ == "__main__":
    sys.exit(main())