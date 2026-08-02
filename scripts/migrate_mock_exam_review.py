#!/usr/bin/env python3
"""Safely add the web mock-exam review schema and profile binding.

The migration is deliberately idempotent.  Existing sessions are backfilled
only when their historical ``student_name`` matches exactly one profile; an
ambiguous name is reported and left NULL for manual resolution.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text  # noqa: E402

from app import app, db  # noqa: E402
from models import (  # noqa: E402
    MockExamReview,
    MockExamReviewEditSession,
    MockExamSession,
    StudentProfile,
)


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


def _add_index(table: str, column: str, index_name: str) -> None:
    inspector = inspect(db.engine)
    indexes = {idx["name"] for idx in inspector.get_indexes(table)}
    if index_name in indexes:
        print(f"{index_name} already exists")
        return
    with db.engine.begin() as conn:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"))
    print(f"added {index_name}")


def _ensure_review_columns() -> None:
    columns = {
        "session_id": "INTEGER",
        "status": "VARCHAR(16) NOT NULL DEFAULT 'draft'",
        "listening_feedback": "TEXT",
        "reading_feedback": "TEXT",
        "overall_feedback": "TEXT",
        "next_stage_advice": "TEXT",
        "task1_ta": "VARCHAR(16)",
        "task1_cc": "VARCHAR(16)",
        "task1_lr": "VARCHAR(16)",
        "task1_gra": "VARCHAR(16)",
        "task2_tr": "VARCHAR(16)",
        "task2_cc": "VARCHAR(16)",
        "task2_lr": "VARCHAR(16)",
        "task2_gra": "VARCHAR(16)",
        "task1_band": "FLOAT",
        "task2_band": "FLOAT",
        "task1_band_state": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "task2_band_state": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "writing_raw": "FLOAT",
        "writing_band": "FLOAT",
        "writing_band_state": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "task1_band_override": "FLOAT",
        "task2_band_override": "FLOAT",
        "writing_band_override": "FLOAT",
        "override_reason": "TEXT",
        "question_feedback_json": "TEXT",
        "task1_teacher_draft": "TEXT",
        "task2_teacher_draft": "TEXT",
        "annotations_json": "TEXT",
        "reviewer_name": "VARCHAR(64)",
        "version": "INTEGER NOT NULL DEFAULT 1",
        "auto_saved_at": "DATETIME",
        "published_at": "DATETIME",
        "link_version": "INTEGER NOT NULL DEFAULT 1",
        "link_expires_at": "DATETIME",
        "link_revoked_at": "DATETIME",
        "last_saved_by": "INTEGER",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    }
    for column, ddl in columns.items():
        _add_column("mock_exam_review", column, ddl)


def _ensure_editor_session_columns() -> None:
    columns = {
        "review_id": "INTEGER NOT NULL",
        "token_hash": "VARCHAR(64) NOT NULL",
        "link_version": "INTEGER NOT NULL",
        "expires_at": "DATETIME NOT NULL",
        "last_seen_at": "DATETIME",
        "revoked_at": "DATETIME",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    }
    for column, ddl in columns.items():
        _add_column("mock_exam_review_edit_session", column, ddl)


def _backfill_profile_ids() -> tuple[int, list[str]]:
    names = {
        name
        for (name,) in db.session.query(MockExamSession.student_name)
        .filter(MockExamSession.student_profile_id.is_(None))
        .distinct()
        .all()
        if name
    }
    updated = 0
    ambiguous = []
    for name in sorted(names):
        profiles = StudentProfile.query.filter_by(full_name=name).all()
        if len(profiles) != 1:
            ambiguous.append(name)
            continue
        count = (
            MockExamSession.query.filter(
                MockExamSession.student_profile_id.is_(None),
                MockExamSession.student_name == name,
            ).update({"student_profile_id": profiles[0].id}, synchronize_session=False)
        )
        updated += count
    db.session.commit()
    return updated, ambiguous


def main() -> int:
    with app.app_context():
        tables = set(inspect(db.engine).get_table_names())
        if "mock_exam_session" not in tables or "student_profile" not in tables:
            print("mock_exam_session/student_profile table missing; run base migration first")
            return 1

        _add_column("mock_exam_session", "student_profile_id", "INTEGER")
        _add_index(
            "mock_exam_session",
            "student_profile_id",
            "ix_mock_exam_session_student_profile_id",
        )

        MockExamReview.__table__.create(bind=db.engine, checkfirst=True)
        MockExamReviewEditSession.__table__.create(bind=db.engine, checkfirst=True)
        _ensure_review_columns()
        _ensure_editor_session_columns()
        _add_index("mock_exam_review", "session_id", "ix_mock_exam_review_session_id")
        _add_index("mock_exam_review_edit_session", "review_id", "ix_mock_review_edit_session_review_id")
        _add_index("mock_exam_review_edit_session", "expires_at", "ix_mock_review_edit_session_expires_at")

        updated, ambiguous = _backfill_profile_ids()
        print(f"backfilled {updated} session profile ids")
        if ambiguous:
            print("skipped ambiguous or missing names:")
            for name in ambiguous:
                print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
