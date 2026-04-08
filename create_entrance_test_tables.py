#!/usr/bin/env python3
"""Create entrance_test_* tables for the entrance test system.

Idempotent: uses db.create_all() which only creates tables that don't exist yet.
Does NOT touch any existing studytracker tables.
"""

import sys

from app import app
from models import (
    db,
    EntranceTestPaper,
    EntranceTestSection,
    EntranceTestQuestion,
    EntranceTestInvitation,
    EntranceTestAttempt,
    EntranceTestAnswer,
)


TABLES = [
    EntranceTestPaper.__tablename__,
    EntranceTestSection.__tablename__,
    EntranceTestQuestion.__tablename__,
    EntranceTestInvitation.__tablename__,
    EntranceTestAttempt.__tablename__,
    EntranceTestAnswer.__tablename__,
]


def main():
    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            print(f"Error creating tables: {exc}")
            sys.exit(1)

        # Verify
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        for t in TABLES:
            mark = "OK" if t in existing else "MISSING"
            print(f"  [{mark}] {t}")

        missing = [t for t in TABLES if t not in existing]
        if missing:
            print(f"Failed to create: {missing}")
            sys.exit(1)

        print("All entrance_test_* tables ready.")


if __name__ == "__main__":
    main()
