#!/usr/bin/env python3
"""Send tomorrow class reminders (cron)."""

from app import app
from api.miniprogram import send_tomorrow_class_reminders_internal


if __name__ == "__main__":
    with app.app_context():
        result = send_tomorrow_class_reminders_internal()
        print(result)
