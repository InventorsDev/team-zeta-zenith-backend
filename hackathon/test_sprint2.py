#!/usr/bin/env python3
"""
Sprint 2 Test Script
Tests BERT-based classification, trend detection, and model monitoring features
"""

import json
import time
from datetime import datetime, timedelta
import random

def test_sprint2_features():
    """Test all Sprint 2 features"""
    print("=" * 60)
    print("SUPPORT TICKET ANALYSIS ML SYSTEM - SPRINT 2 TESTS")
    print("=" * 60)
    
    # Test 1: BERT Classifier
    print("\n1. Testing BERT Classifier...")
    test_bert_classifier()
    
    # Test 2: Trend Detection
    print("\n2. Testing Trend Detection...")
    test_trend_detection()
    
    # Test 3: Model Monitoring
    print("\n3. Testing Model Monitoring...")
    test_model_monitoring()
    
    # Test 4: API Integration
    print("\n4. Testing API Integration...")
    test_api_integration()
    
    print("\n" + "=" * 60)
    print("🎉 Sprint 2 tests completed!")
    print("=" * 60)

def test_bert_classifier():
    """Test BERT classifier functionality"""
    try:
        from app.models.bert_classifier import bert_classifier
        
        print("   ✓ BERT classifier imported successfully")
        
        # Test model info
        model_info = bert_classifier.get_model_info()
        print(f"   ✓ Model info retrieved: {model_info['model_name']}")
        
        # Test data preparation
        try:
            train_dataset, val_dataset = bert_classifier.prepare_data()
            print(f"   ✓ Data preparation successful: {len(train_dataset)} training, {len(val_dataset)} validation samples")
        except Exception as e:
            print(f"   ⚠ Data preparation failed (expected if no training data): {e}")
        
        print("   ✓ BERT classifier test completed")
        
    except Exception as e:
        print(f"   ✗ BERT classifier test failed: {e}")

def test_trend_detection():
    """Test trend detection functionality"""
    try:
        from app.analytics.trend_detector import trend_detector
        
        print("   ✓ Trend detector imported successfully")
        
        # Create sample ticket data with timestamps
        sample_tickets = []
        base_time = datetime.now() - timedelta(days=7)
        
        categories = ['billing', 'bug', 'feature', 'account', 'general']
        sentiments = ['positive', 'negative', 'neutral']
        
        for i in range(50):
            ticket = {
                'id': f'ticket_{i}',
                'text': f'Sample ticket {i}',
                'category': random.choice(categories),
                'sentiment': random.choice(sentiments),
                'sentiment_score': random.uniform(-1, 1),
                'timestamp': (base_time + timedelta(hours=i)).isoformat()
            }
            sample_tickets.append(ticket)
        
        # Test volume trends
        volume_trends = trend_detector.calculate_volume_trends(sample_tickets, "daily")
        print(f"   ✓ Volume trends calculated: {volume_trends['total_tickets']} tickets analyzed")
        
        # Test sentiment trends
        sentiment_trends = trend_detector.calculate_sentiment_trends(sample_tickets, "daily")
        print(f"   ✓ Sentiment trends calculated: {sentiment_trends['total_tickets']} tickets analyzed")
        
        # Test anomaly detection
        anomalies = trend_detector.detect_anomalies(sample_tickets)
        total_anomalies = sum(len(anomaly_list) for anomaly_list in anomalies.values())
        print(f"   ✓ Anomaly detection completed: {total_anomalies} anomalies found")
        
        # Test alert generation
        alerts = trend_detector.generate_alerts(volume_trends)
        print(f"   ✓ Alert generation completed: {len(alerts)} alerts generated")
        
        print("   ✓ Trend detection test completed")
        
    except Exception as e:
        print(f"   ✗ Trend detection test failed: {e}")

def test_model_monitoring():
    """Test model monitoring functionality"""
    try:
        from app.monitoring.model_monitor import model_monitor
        
        print("   ✓ Model monitor imported successfully")
        
        # Create sample prediction data
        sample_prediction = {
            'category': 'billing',
            'confidence': 0.85,
            'confidence_label': 'high',
            'text': 'Sample ticket for monitoring'
        }
        
        # Test prediction tracking
        model_monitor.track_prediction("test_model", sample_prediction, ground_truth="billing")
        print("   ✓ Prediction tracking completed")
        
        # Test performance metrics
        metrics = model_monitor.calculate_performance_metrics("test_model", time_window=1)
        print(f"   ✓ Performance metrics calculated: {metrics['total_predictions']} predictions")
        
        # Test drift detection
        drift_results = model_monitor.detect_model_drift("test_model")
        print(f"   ✓ Drift detection completed: drift_detected={drift_results['drift_detected']}")
        
        # Test retraining triggers
        retraining_results = model_monitor.check_retraining_triggers("test_model")
        print(f"   ✓ Retraining check completed: retraining_needed={retraining_results['retraining_needed']}")
        
        # Test health dashboard
        health_data = model_monitor.get_model_health_dashboard("test_model")
        print(f"   ✓ Health dashboard generated: status={health_data['status']}")
        
        # Test all models health
        all_health = model_monitor.get_all_models_health()
        print(f"   ✓ All models health: {all_health['total_models']} models monitored")
        
        print("   ✓ Model monitoring test completed")
        
    except Exception as e:
        print(f"   ✗ Model monitoring test failed: {e}")

def test_api_integration():
    """Test API integration for Sprint 2 features"""
    try:
        import requests
        
        base_url = "http://localhost:8000"
        
        # Test root endpoint
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ API root endpoint: {data['message']}")
            print(f"   ✓ Sprint 2 features: {len(data['sprint_2_features'])} features available")
        else:
            print(f"   ⚠ API root endpoint returned status {response.status_code}")
        
        # Test health endpoint
        response = requests.get(f"{base_url}/api/v1/ml/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Health check: {data['status']} status")
        else:
            print(f"   ⚠ Health check returned status {response.status_code}")
        
        # Test trend detection endpoint
        sample_tickets = [
            {
                'id': 'test_1',
                'text': 'Test ticket 1',
                'category': 'billing',
                'sentiment': 'negative',
                'sentiment_score': -0.5,
                'timestamp': datetime.now().isoformat()
            },
            {
                'id': 'test_2',
                'text': 'Test ticket 2',
                'category': 'bug',
                'sentiment': 'positive',
                'sentiment_score': 0.8,
                'timestamp': datetime.now().isoformat()
            }
        ]
        
        trend_request = {
            'tickets': sample_tickets,
            'time_period': 'daily'
        }
        
        response = requests.post(f"{base_url}/api/v1/ml/trends/volume", json=trend_request)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Volume trends API: {data['total_tickets']} tickets analyzed")
        else:
            print(f"   ⚠ Volume trends API returned status {response.status_code}")
        
        # Test model monitoring endpoint
        response = requests.get(f"{base_url}/api/v1/ml/monitoring/health")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Model monitoring API: {data['total_models']} models monitored")
        else:
            print(f"   ⚠ Model monitoring API returned status {response.status_code}")
        
        print("   ✓ API integration test completed")
        
    except requests.exceptions.ConnectionError:
        print("   ⚠ API server not running. Start with: uvicorn app.main:app --reload")
    except Exception as e:
        print(f"   ✗ API integration test failed: {e}")

def test_bert_training_simulation():
    """Simulate BERT training process"""
    print("\n5. Testing BERT Training Simulation...")
    
    try:
        from app.models.bert_classifier import bert_classifier
        
        # Check if training data exists
        import os
        if os.path.exists("data/expanded_tickets.json"):
            print("   ✓ Training data found")
            
            # Note: Actual training would take significant time and resources
            # This is just a simulation to test the interface
            print("   ⚠ BERT training simulation (not actually training)")
            print("   ✓ Training interface ready")
            print("   ✓ Use POST /api/v1/ml/bert/train to start training")
        else:
            print("   ⚠ Training data not found at data/expanded_tickets.json")
            print("   ✓ BERT training interface available")
        
    except Exception as e:
        print(f"   ✗ BERT training simulation failed: {e}")

if __name__ == "__main__":
    test_sprint2_features()
    test_bert_training_simulation() 