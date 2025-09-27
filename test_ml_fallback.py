#!/usr/bin/env python3
"""
Test the improved ML fallback logic
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.ml_service import ml_service

def test_classification_fallback():
    """Test improved classification fallback logic"""
    
    test_cases = [
        {
            "text": "I cannot login to my account, forgot my password",
            "expected_category": "authentication"
        },
        {
            "text": "I was charged twice for my subscription this month, need refund", 
            "expected_category": "billing"
        },
        {
            "text": "The app keeps crashing with error 500, server issue",
            "expected_category": "technical"
        },
        {
            "text": "How do I setup the integration? Need help with configuration",
            "expected_category": "support"
        },
        {
            "text": "Can you add a new feature for dark mode? Would be great improvement",
            "expected_category": "feature_request"
        },
        {
            "text": "Just some general feedback about the service",
            "expected_category": "general"
        }
    ]
    
    print("TESTING IMPROVED ML CLASSIFICATION FALLBACK")
    print("=" * 50)
    
    for i, case in enumerate(test_cases, 1):
        result = ml_service.classify_ticket(case["text"])
        
        print(f"\n{i}. Text: {case['text'][:60]}...")
        print(f"   Expected: {case['expected_category']}")
        print(f"   Got: {result['category']}")
        print(f"   Confidence: {result['confidence']:.2f} ({result['confidence_label']})")
        print(f"   Classifier: {result['classifier_used']}")
        
        if result['category'] == case['expected_category']:
            print("   [CORRECT]")
        else:
            print("   [INCORRECT]")

def test_sentiment_fallback():
    """Test improved sentiment fallback logic"""
    
    test_cases = [
        {
            "text": "I love this service! It's absolutely amazing and fantastic!",
            "expected_sentiment": "positive"
        },
        {
            "text": "This is terrible! Worst experience ever, completely broken and useless!",
            "expected_sentiment": "negative"
        },
        {
            "text": "URGENT! Critical issue, need help immediately! This is broken!",
            "expected_sentiment": "negative"
        },
        {
            "text": "Thank you for the great support, really appreciate your help!",
            "expected_sentiment": "positive"
        },
        {
            "text": "I have a question about the pricing model",
            "expected_sentiment": "neutral"
        },
        {
            "text": "The system crashed again, very frustrating and annoying problem",
            "expected_sentiment": "negative"
        }
    ]
    
    print("\n\nTESTING IMPROVED ML SENTIMENT FALLBACK")
    print("=" * 50)
    
    for i, case in enumerate(test_cases, 1):
        result = ml_service.analyze_sentiment(case["text"])
        
        print(f"\n{i}. Text: {case['text'][:60]}...")
        print(f"   Expected: {case['expected_sentiment']}")
        print(f"   Got: {result['sentiment']}")
        print(f"   Score: {result['sentiment_score']:.2f}")
        print(f"   Confidence: {result['confidence']:.2f} ({result['confidence_label']})")
        
        if result['sentiment'] == case['expected_sentiment']:
            print("   [CORRECT]")
        else:
            print("   [INCORRECT]")

def test_ticket_enhancement():
    """Test complete ticket enhancement"""
    
    print("\n\nTESTING COMPLETE TICKET ENHANCEMENT")
    print("=" * 50)
    
    sample_ticket = {
        "title": "Login Problem - Urgent Help Needed",
        "description": "I cannot login to my account! Keep getting authentication errors. This is very frustrating and I need help immediately. My password reset is not working.",
        "customer_email": "user@example.com",
        "priority": "high"
    }
    
    enhanced = ml_service.enhance_ticket_data(sample_ticket)
    
    print(f"\nOriginal ticket:")
    print(f"  Title: {sample_ticket['title']}")
    print(f"  Description: {sample_ticket['description'][:80]}...")
    
    print(f"\nML Enhancement:")
    print(f"  Category: {enhanced.get('ml_category')} (confidence: {enhanced.get('ml_confidence', 0):.2f})")
    print(f"  Sentiment: {enhanced.get('ml_sentiment')} (score: {enhanced.get('ml_sentiment_score', 0):.2f})")
    print(f"  ML Available: {enhanced.get('ml_available')}")
    print(f"  Processed At: {enhanced.get('ml_processed_at')}")
    
    if enhanced.get('potential_duplicates'):
        print(f"  Potential Duplicates: {enhanced.get('potential_duplicates')}")

if __name__ == "__main__":
    test_classification_fallback()
    test_sentiment_fallback() 
    test_ticket_enhancement()
    
    print("\n" + "=" * 50)
    print("ML FALLBACK TESTING COMPLETE")
    print("The improved fallback logic should now provide")
    print("context-aware results instead of static values!")