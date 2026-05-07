#!/usr/bin/env python3
"""Create mock_exam + mock_exam_session tables.

Idempotent: db.create_all() only creates tables that don't yet exist.
"""

from app import app, db
from models import MockExam, MockExamSession  # noqa: F401

with app.app_context():
    print("Creating mock exam tables...")
    db.create_all()
    print("Done!")

    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    for name in ("mock_exam", "mock_exam_session"):
        mark = "✓" if name in tables else "✗"
        print(f"  {mark} {name}")
