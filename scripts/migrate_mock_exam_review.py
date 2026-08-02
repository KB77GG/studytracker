#!/usr/bin/env python3
"""Create the web mock-exam review schema without importing the application.

This script is intentionally self-contained so it can be copied to a server
and run against the existing SQLite database before the new application code is
deployed.  It only uses the Python standard library, accepts an explicit
``--database`` path, and is safe to run repeatedly.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "app.db"

REVIEW_COLUMNS = {
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

EDITOR_SESSION_COLUMNS = {
    "review_id": "INTEGER",
    "token_hash": "VARCHAR(64)",
    "link_version": "INTEGER NOT NULL DEFAULT 1",
    "expires_at": "DATETIME",
    "last_seen_at": "DATETIME",
    "revoked_at": "DATETIME",
    "created_at": "DATETIME",
    "updated_at": "DATETIME",
}


def _quote_identifier(value: str) -> str:
    """Quote one of this script's fixed schema identifiers."""
    return '"' + value.replace('"', '""') + '"'


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table)})")
    }


def _add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> bool:
    if column in _columns(conn, table):
        return False
    conn.execute(
        f"ALTER TABLE {_quote_identifier(table)} ADD COLUMN {_quote_identifier(column)} {ddl}"
    )
    return True


def _add_index(conn: sqlite3.Connection, table: str, column: str, index_name: str) -> None:
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS {_quote_identifier(index_name)} "
        f"ON {_quote_identifier(table)} ({_quote_identifier(column)})"
    )


def _add_unique_index(
    conn: sqlite3.Connection, table: str, column: str, index_name: str
) -> None:
    conn.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {_quote_identifier(index_name)} "
        f"ON {_quote_identifier(table)} ({_quote_identifier(column)})"
    )


def _create_review_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mock_exam_review (
            id INTEGER PRIMARY KEY,
            session_id INTEGER NOT NULL UNIQUE,
            status VARCHAR(16) NOT NULL DEFAULT 'draft',
            listening_feedback TEXT,
            reading_feedback TEXT,
            overall_feedback TEXT,
            next_stage_advice TEXT,
            task1_ta VARCHAR(16),
            task1_cc VARCHAR(16),
            task1_lr VARCHAR(16),
            task1_gra VARCHAR(16),
            task2_tr VARCHAR(16),
            task2_cc VARCHAR(16),
            task2_lr VARCHAR(16),
            task2_gra VARCHAR(16),
            task1_band FLOAT,
            task2_band FLOAT,
            task1_band_state VARCHAR(20) NOT NULL DEFAULT 'pending',
            task2_band_state VARCHAR(20) NOT NULL DEFAULT 'pending',
            writing_raw FLOAT,
            writing_band FLOAT,
            writing_band_state VARCHAR(20) NOT NULL DEFAULT 'pending',
            task1_band_override FLOAT,
            task2_band_override FLOAT,
            writing_band_override FLOAT,
            override_reason TEXT,
            question_feedback_json TEXT,
            task1_teacher_draft TEXT,
            task2_teacher_draft TEXT,
            annotations_json TEXT,
            reviewer_name VARCHAR(64),
            version INTEGER NOT NULL DEFAULT 1,
            auto_saved_at DATETIME,
            published_at DATETIME,
            link_version INTEGER NOT NULL DEFAULT 1,
            link_expires_at DATETIME,
            link_revoked_at DATETIME,
            last_saved_by INTEGER,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES mock_exam_session(id)
        )
        """
    )
    for column, ddl in REVIEW_COLUMNS.items():
        _add_column(conn, "mock_exam_review", column, ddl)


def _create_editor_session_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mock_exam_review_edit_session (
            id INTEGER PRIMARY KEY,
            review_id INTEGER NOT NULL,
            token_hash VARCHAR(64) NOT NULL UNIQUE,
            link_version INTEGER NOT NULL,
            expires_at DATETIME NOT NULL,
            last_seen_at DATETIME,
            revoked_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES mock_exam_review(id)
        )
        """
    )
    for column, ddl in EDITOR_SESSION_COLUMNS.items():
        _add_column(conn, "mock_exam_review_edit_session", column, ddl)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    _add_column(conn, "mock_exam_session", "student_profile_id", "INTEGER")
    _create_review_table(conn)
    _create_editor_session_table(conn)
    _add_index(
        conn,
        "mock_exam_session",
        "student_profile_id",
        "ix_mock_exam_session_student_profile_id",
    )
    _add_index(conn, "mock_exam_review", "session_id", "ix_mock_exam_review_session_id")
    _add_unique_index(
        conn,
        "mock_exam_review",
        "session_id",
        "uq_mock_exam_review_session_id",
    )
    _add_unique_index(
        conn,
        "mock_exam_review_edit_session",
        "token_hash",
        "uq_mock_exam_review_edit_session_token_hash",
    )
    _add_index(
        conn,
        "mock_exam_review_edit_session",
        "review_id",
        "ix_mock_review_edit_session_review_id",
    )
    _add_index(
        conn,
        "mock_exam_review_edit_session",
        "expires_at",
        "ix_mock_review_edit_session_expires_at",
    )


def _backfill_profile_ids(conn: sqlite3.Connection) -> tuple[int, int, int]:
    names = [
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT student_name
            FROM mock_exam_session
            WHERE student_profile_id IS NULL
              AND student_name IS NOT NULL
              AND TRIM(student_name) <> ''
            """
        )
    ]
    updated = 0
    ambiguous_active_names = 0
    missing_active_profiles = 0
    for name in names:
        profiles = conn.execute(
            """
            SELECT id
            FROM student_profile
            WHERE full_name = ? AND is_deleted = 0
            ORDER BY id
            """,
            (name,),
        ).fetchall()
        if len(profiles) == 0:
            missing_active_profiles += 1
            continue
        if len(profiles) != 1:
            ambiguous_active_names += 1
            continue
        result = conn.execute(
            """
            UPDATE mock_exam_session
            SET student_profile_id = ?
            WHERE student_profile_id IS NULL AND student_name = ?
            """,
            (profiles[0][0], name),
        )
        updated += result.rowcount
    return updated, ambiguous_active_names, missing_active_profiles


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE),
        help="SQLite database path (default: repository app.db)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    database = args.database
    try:
        conn = sqlite3.connect(database)
    except sqlite3.Error as exc:
        print(f"cannot open database: {exc}", file=sys.stderr)
        return 1

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if not _table_exists(conn, "mock_exam_session") or not _table_exists(
            conn, "student_profile"
        ):
            print("mock_exam_session/student_profile table missing; run base migration first")
            return 1
        _ensure_schema(conn)
        updated, ambiguous, missing = _backfill_profile_ids(conn)
        conn.commit()
        print(
            "migration complete: "
            f"database={database}; "
            f"backfilled={updated}; "
            f"ambiguous_active_names={ambiguous}; "
            f"missing_active_profiles={missing}"
        )
        return 0
    except sqlite3.Error as exc:
        conn.rollback()
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
