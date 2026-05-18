#!/usr/bin/env python3
"""Create student_word_mastery table for spaced-repetition review."""

from app import app, db
from models import StudentWordMastery

with app.app_context():
    print("Creating student_word_mastery table...")
    db.create_all()

    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    if "student_word_mastery" in inspector.get_table_names():
        print("  ✓ student_word_mastery exists")
    else:
        print("  ✗ student_word_mastery NOT FOUND")
