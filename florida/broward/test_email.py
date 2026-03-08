#!/usr/bin/env python3
"""
Test email notifications
"""
import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Add parent directories to path to find lib package
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.notifications import NotificationManager, ScraperMetrics

# Setup logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s | %(name)s | %(message)s'
)

# Load environment variables
load_dotenv()

# Create test metrics
metrics = ScraperMetrics(
    start_time=datetime.now(),
    end_time=datetime.now(),
    success=True,
    data_type="daily",
    date_or_year="2026-03-07",
    mortgages_count=204,
    mortgages_over_1m=18,
    total_volume=15234567.89,
    files_downloaded=5,
    s3_uploaded=True
)

# Send test notification
print("Testing email notification...")
print(f"From: {os.getenv('EMAIL_FROM')}")
print(f"To: {os.getenv('EMAIL_TO')}")
print(f"Email enabled: {os.getenv('EMAIL_NOTIFICATIONS')}")
print()

manager = NotificationManager()
print(f"Email configured: {manager.email_enabled}")
print(f"Email to list: {manager.email_to}")
print()

manager.send_success_notification(metrics)

print("\nIf email configured correctly, you should receive a notification email!")
print("Check your inbox (and spam folder)")
