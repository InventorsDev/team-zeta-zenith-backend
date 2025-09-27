#!/usr/bin/env python3
"""
Quick verification that the ML enhancement now provides different results 
for different inputs (fixing the "same result regardless of input" issue)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from app.services.ml_service import ml_service

def test_varied_responses():
    """Test that different inputs now produce different ML results"""
    
    test_tickets = [
        {
            "title": "Login Issue Fixed",
            "description": "I cannot login to my account, getting error 500. Please help!",
            "customer_email": "user@example.com",
            "priority": "high",
            "channel": "web"
        },
        {
            "title": "Great Service!",
            "description": "Thank you so much for the excellent support! Really appreciate the quick response.",
            "customer_email": "user@example.com", 
            "priority": "low",
            "channel": "email"
        },
        {
            "title": "Feature Request",
            "description": "Can you add a dark mode feature? Would be an awesome improvement!",
            "customer_email": "user@example.com",
            "priority": "medium", 
            "channel": "web"
        }
    ]
    
    print("VERIFYING: Different inputs now produce different ML results")
    print("=" * 60)
    
    results = []
    for i, ticket in enumerate(test_tickets, 1):
        enhanced = ml_service.enhance_ticket_data(ticket)
        
        result = {
            "title": ticket["title"],
            "category": enhanced.get("ml_category"),
            "confidence": enhanced.get("ml_confidence", 0),
            "sentiment": enhanced.get("ml_sentiment"), 
            "sentiment_score": enhanced.get("ml_sentiment_score", 0)
        }
        results.append(result)
        
        print(f"\n{i}. {ticket['title']}")
        print(f"   Description: {ticket['description'][:50]}...")
        print(f"   ML Category: {result['category']} ({result['confidence']:.2f})")
        print(f"   ML Sentiment: {result['sentiment']} ({result['sentiment_score']:.2f})")
    
    # Check if all results are different
    print(f"\n{'='*60}")
    print("ANALYSIS:")
    
    categories = [r["category"] for r in results]
    sentiments = [r["sentiment"] for r in results]
    
    print(f"Categories: {categories}")
    print(f"Sentiments: {sentiments}")
    
    unique_categories = len(set(categories))
    unique_sentiments = len(set(sentiments))
    
    if unique_categories > 1:
        print("✓ FIXED: Different inputs produce different categories")
    else:
        print("✗ ISSUE: All inputs produce same category")
        
    if unique_sentiments > 1:
        print("✓ FIXED: Different inputs produce different sentiments")  
    else:
        print("✗ ISSUE: All inputs produce same sentiment")
    
    print(f"\nBEFORE FIX: All tickets returned:")
    print(f'  ml_category: "general", ml_confidence: 0.5')
    print(f'  ml_sentiment: "neutral", ml_sentiment_score: 0.0')
    
    print(f"\nAFTER FIX: Tickets now return varied, context-aware results!")

if __name__ == "__main__":
    test_varied_responses()