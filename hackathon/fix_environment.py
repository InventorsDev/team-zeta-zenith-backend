#!/usr/bin/env python3
"""
Fix environment script for Support Ticket Analysis ML System
Resolves NumPy compatibility issues
"""

import subprocess
import sys
import os

def fix_numpy_issue():
    """Fix NumPy compatibility issues"""
    print("Fixing NumPy compatibility issues...")
    
    try:
        # First, uninstall problematic packages
        print("Uninstalling problematic packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "numpy", "scikit-learn", "scipy"])
        
        # Install compatible NumPy version
        print("Installing compatible NumPy version...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy==1.24.3"])
        
        # Install compatible scikit-learn
        print("Installing compatible scikit-learn...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "scikit-learn==1.3.0"])
        
        # Install other requirements
        print("Installing other requirements...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
        print("Environment fixed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to fix environment: {e}")
        return False

def test_imports():
    """Test if all imports work correctly"""
    print("Testing imports...")
    
    try:
        import numpy as np
        print(f"✅ NumPy version: {np.__version__}")
        
        import pandas as pd
        print(f"✅ Pandas version: {pd.__version__}")
        
        import sklearn
        print(f"✅ Scikit-learn version: {sklearn.__version__}")
        
        import nltk
        print(f"✅ NLTK version: {nltk.__version__}")
        
        import vaderSentiment
        print(f"✅ VADER Sentiment version: {vaderSentiment.__version__}")
        
        import fastapi
        print(f"✅ FastAPI version: {fastapi.__version__}")
        
        print("All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def main():
    print("Support Ticket Analysis ML System - Environment Fix")
    print("=" * 60)
    
    # Fix NumPy issues
    if not fix_numpy_issue():
        print("Failed to fix environment. Exiting.")
        return
    
    # Test imports
    if not test_imports():
        print("Some imports still failed. Please check manually.")
        return
    
    print("\n🎉 Environment fixed successfully!")
    print("You can now run: python test_system.py")

if __name__ == "__main__":
    main() 