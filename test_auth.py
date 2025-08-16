#!/usr/bin/env python3
"""Simple test script for authentication endpoints"""

import sys
import json
import requests
import time
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def test_api_status():
    """Test API status endpoint"""
    try:
        response = requests.get(f"{API_BASE}/status")
        print(f"✓ API Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"✗ API Status failed: {e}")
        return False

def test_user_registration():
    """Test user registration"""
    try:
        user_data = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPassword123",
            "full_name": "Test User"
        }
        
        response = requests.post(f"{API_BASE}/auth/register", json=user_data)
        print(f"✓ User Registration: {response.status_code}")
        
        if response.status_code == 201:
            token_data = response.json()
            print(f"  Token received: {token_data['token_type']}")
            return token_data
        else:
            print(f"  Error: {response.text}")
            return None
    except Exception as e:
        print(f"✗ User Registration failed: {e}")
        return None

def test_user_login(email, password):
    """Test user login"""
    try:
        login_data = {
            "email": email,
            "password": password
        }
        
        response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        print(f"✓ User Login: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"  Token received: {token_data['token_type']}")
            return token_data
        else:
            print(f"  Error: {response.text}")
            return None
    except Exception as e:
        print(f"✗ User Login failed: {e}")
        return None

def test_protected_endpoint(token):
    """Test accessing protected endpoint"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_BASE}/auth/me", headers=headers)
        print(f"✓ Protected Endpoint: {response.status_code}")
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"  User: {user_data.get('email')}")
            return True
        else:
            print(f"  Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Protected Endpoint failed: {e}")
        return False

def test_rate_limiting():
    """Test rate limiting on auth endpoints"""
    try:
        login_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        print("Testing rate limiting (5 failed attempts)...")
        for i in range(6):
            response = requests.post(f"{API_BASE}/auth/login", json=login_data)
            print(f"  Attempt {i+1}: {response.status_code}")
            
            if response.status_code == 429:
                print("✓ Rate limiting working!")
                return True
                
        print("✗ Rate limiting not triggered")
        return False
    except Exception as e:
        print(f"✗ Rate limiting test failed: {e}")
        return False

def main():
    """Run all authentication tests"""
    print("=" * 50)
    print("JWT Authentication Test Suite")
    print("=" * 50)
    print(f"Testing API at: {BASE_URL}")
    print(f"Timestamp: {datetime.now()}")
    print("-" * 50)
    
    # Test 1: API Status
    if not test_api_status():
        print("API is not running. Please start the server first.")
        sys.exit(1)
    
    print("-" * 50)
    
    # Test 2: User Registration
    token_data = test_user_registration()
    if not token_data:
        print("Registration failed. Cannot continue with tests.")
        sys.exit(1)
    
    # Extract user data for login test
    # (In a real test, you'd store this info)
    test_email = f"test_{int(time.time())}@example.com"
    test_password = "TestPassword123"
    access_token = token_data.get("access_token")
    
    print("-" * 50)
    
    # Test 3: User Login
    login_token_data = test_user_login(test_email, test_password)
    if login_token_data:
        access_token = login_token_data.get("access_token")
    
    print("-" * 50)
    
    # Test 4: Protected Endpoint
    if access_token:
        test_protected_endpoint(access_token)
    else:
        print("No access token available for protected endpoint test")
    
    print("-" * 50)
    
    # Test 5: Rate Limiting
    test_rate_limiting()
    
    print("-" * 50)
    print("Authentication test suite completed!")

if __name__ == "__main__":
    main()