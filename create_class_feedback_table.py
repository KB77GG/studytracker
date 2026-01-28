#!/usr/bin/env python3
"""Create class feedback table in the database."""

from app import app, db
from models import ClassFeedback

with app.app_context():
    print("Creating class feedback table...")
    db.create_all()
    print("Done!")

    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    if "class_feedback" in tables:
        print("  ✓ class_feedback exists")
    else:
        print("  ✗ class_feedback NOT FOUND")
