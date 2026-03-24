#!/usr/bin/env python3
"""Send tomorrow class reminders (cron)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app
from api.miniprogram import send_tomorrow_class_reminders_internal


if __name__ == "__main__":
    with app.app_context():
        result = send_tomorrow_class_reminders_internal()
        print(result)
