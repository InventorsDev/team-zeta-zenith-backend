#!/usr/bin/env python3
"""
Script to schedule daily ML training via cron job
Can be run manually or scheduled via system cron
"""

import os
import sys
import logging
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

def run_daily_ml_training():
    """Execute daily ML training"""
    print(f"[{datetime.now()}] Starting daily ML training job...")
    
    try:
        # Import after path setup
        from tasks.ml_training_tasks import daily_ml_training
        
        # Execute the training task
        result = daily_ml_training()
        
        print(f"[{datetime.now()}] ML training job result: {result}")
        return True
        
    except Exception as e:
        print(f"[{datetime.now()}] ML training job failed: {e}")
        return False

def setup_logging():
    """Setup basic logging for the cron job"""
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'ml_training_cron.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

if __name__ == "__main__":
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("Daily ML training cron job started")
    
    success = run_daily_ml_training()
    
    if success:
        logger.info("Daily ML training cron job completed successfully")
        sys.exit(0)
    else:
        logger.error("Daily ML training cron job failed")
        sys.exit(1)