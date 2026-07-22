#!/usr/bin/env python3
"""Add mock-exam writing columns (idempotent, SQLite ALTER TABLE).

Adds the writing-section columns to ``mock_exam`` and ``mock_exam_session`` so an
existing StudyTracker database (local or production) picks up the new writing
科目 without a rebuild. Only touches schema; safe to run repeatedly.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text  # noqa: E402

from app import app, db  # noqa: E402


def _add_column(table: str, column: str, ddl: str) -> bool:
    inspector = inspect(db.engine)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        print(f"{table}.{column} already exists")
        return False
    with db.engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    print(f"added {table}.{column}")
    return True


def main() -> int:
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        if "mock_exam" not in tables or "mock_exam_session" not in tables:
            print("mock_exam/mock_exam_session table missing; run base migration first")
            return 1

        _add_column("mock_exam", "writing_test_id", "VARCHAR(120)")
        _add_column("mock_exam", "writing_minutes", "INTEGER NOT NULL DEFAULT 60")

        _add_column("mock_exam_session", "writing_started_at", "DATETIME")
        _add_column("mock_exam_session", "writing_deadline_at", "DATETIME")
        _add_column("mock_exam_session", "writing_submitted_at", "DATETIME")
        _add_column("mock_exam_session", "writing_essay_task1", "TEXT")
        _add_column("mock_exam_session", "writing_essay_task2", "TEXT")
        _add_column("mock_exam_session", "writing_task1_words", "INTEGER")
        _add_column("mock_exam_session", "writing_task2_words", "INTEGER")
        _add_column("mock_exam_session", "writing_duration_seconds", "INTEGER DEFAULT 0")
        _add_column(
            "mock_exam_session",
            "writing_auto_submitted",
            "BOOLEAN NOT NULL DEFAULT 0",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
