#!/usr/bin/env python3
"""
Quick test runner for the Support Ticket Analysis ML System
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    print("Installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Requirements installed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install requirements: {e}")
        return False
    return True

def run_tests():
    """Run the test suite"""
    print("Running tests...")
    try:
        subprocess.check_call([sys.executable, "test_system.py"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Tests failed: {e}")
        return False

def main():
    print("Support Ticket Analysis ML System - Test Runner")
    print("=" * 50)
    
    # Install requirements
    if not install_requirements():
        print("Failed to install requirements. Exiting.")
        return
    
    # Run tests
    if run_tests():
        print("\n🎉 All tests passed! Sprint 1 is complete!")
    else:
        print("\n❌ Some tests failed. Please check the output above.")

if __name__ == "__main__":
    main() 