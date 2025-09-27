#!/usr/bin/env python3
"""
Celery worker startup script.
This script can be used to start Celery workers with different configurations.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings

def start_worker(worker_type="general", concurrency=None, loglevel="info"):
    """Start a Celery worker with specific configuration."""
    settings = get_settings()

    # Base command
    cmd = [
        "celery",
        "-A", "app.tasks.celery_app",
        "worker",
        "--loglevel", loglevel
    ]

    # Configure based on worker type
    if worker_type == "ml":
        # ML worker configuration - lower concurrency, specific queues
        cmd.extend([
            "--concurrency", str(concurrency) if concurrency else "1",
            "--queues", "ml_tasks",
            "--hostname", "ml_worker@%h"
        ])
    elif worker_type == "sync":
        # Sync worker configuration - for integration tasks
        cmd.extend([
            "--concurrency", str(concurrency) if concurrency else "2",
            "--queues", "sync_tasks",
            "--hostname", "sync_worker@%h"
        ])
    else:
        # General worker configuration
        cmd.extend([
            "--concurrency", str(concurrency) if concurrency else "2",
            "--hostname", "general_worker@%h"
        ])

    # Add additional options
    cmd.extend([
        "--prefetch-multiplier", "1",
        "--max-tasks-per-child", "1000"
    ])

    print(f"Starting {worker_type} Celery worker...")
    print(f"Command: {' '.join(cmd)}")
    print(f"Broker URL: {settings.celery_broker_url}")
    print(f"Result Backend: {settings.celery_result_backend}")

    try:
        # Start the worker
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down worker...")
    except subprocess.CalledProcessError as e:
        print(f"Error starting worker: {e}")
        sys.exit(1)

def start_beat():
    """Start Celery Beat scheduler."""
    settings = get_settings()

    cmd = [
        "celery",
        "-A", "app.tasks.celery_app",
        "beat",
        "--loglevel", "info"
    ]

    print("Starting Celery Beat scheduler...")
    print(f"Command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down beat scheduler...")
    except subprocess.CalledProcessError as e:
        print(f"Error starting beat scheduler: {e}")
        sys.exit(1)

def start_flower(port=5555):
    """Start Flower monitoring."""
    cmd = [
        "celery",
        "-A", "app.tasks.celery_app",
        "flower",
        "--port", str(port)
    ]

    print(f"Starting Flower monitoring on port {port}...")
    print(f"Command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down Flower...")
    except subprocess.CalledProcessError as e:
        print(f"Error starting Flower: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Start Celery components")
    parser.add_argument(
        "component",
        choices=["worker", "beat", "flower"],
        help="Component to start"
    )
    parser.add_argument(
        "--worker-type",
        choices=["general", "ml", "sync"],
        default="general",
        help="Type of worker (only for worker component)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        help="Number of concurrent worker processes"
    )
    parser.add_argument(
        "--loglevel",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Log level"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5555,
        help="Port for Flower (only for flower component)"
    )

    args = parser.parse_args()

    if args.component == "worker":
        start_worker(args.worker_type, args.concurrency, args.loglevel)
    elif args.component == "beat":
        start_beat()
    elif args.component == "flower":
        start_flower(args.port)

if __name__ == "__main__":
    main()