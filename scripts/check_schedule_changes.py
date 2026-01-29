#!/usr/bin/env python3
"""Check schedule changes and send notifications (cron)."""

from app import app
from api.miniprogram import check_schedule_changes_internal


if __name__ == "__main__":
    with app.app_context():
        result = check_schedule_changes_internal()
        print(result)
