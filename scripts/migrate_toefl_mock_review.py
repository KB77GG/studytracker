#!/usr/bin/env python3
"""Add the TOEFL v2 review fields to an existing SQLite database.

This migration deliberately uses only the standard library.  It can be run
before deploying the application code and is idempotent.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "app.db"
PACKAGE_ROOT = ROOT / "data" / "toefl_practice_v2"

ATTEMPT_COLUMNS = {
    "review_status": "VARCHAR(24) NOT NULL DEFAULT 'not_started'",
    "review_version": "INTEGER NOT NULL DEFAULT 1",
    "review_reviewer_id": "INTEGER",
    "review_updated_at": "DATETIME",
    "review_published_at": "DATETIME",
    "review_reopened_at": "DATETIME",
}

RESPONSE_COLUMNS = {
    "review_status": "VARCHAR(24) NOT NULL DEFAULT 'pending'",
    "teacher_score": "FLOAT",
    "score_max": "FLOAT DEFAULT 5.0",
    "rubric_code": "VARCHAR(64)",
    "rubric_version": "VARCHAR(24)",
    "teacher_feedback": "TEXT",
    "reviewed_by": "INTEGER",
    "reviewed_at": "DATETIME",
}

RUBRIC_VERSION = "2026-01"
RUBRIC_CODES = {
    "listen_and_repeat": "toefl_2026_speaking_listen_and_repeat",
    "take_an_interview": "toefl_2026_speaking_take_an_interview",
    "write_email": "toefl_2026_writing_write_an_email",
    "academic_discussion": "toefl_2026_writing_academic_discussion",
}


def quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1] for row in conn.execute(f"PRAGMA table_info({quote(table)})")
    }


def add_columns(conn: sqlite3.Connection, table: str, definitions: dict[str, str]) -> int:
    existing = columns(conn, table)
    added = 0
    for name, ddl in definitions.items():
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE {quote(table)} ADD COLUMN {quote(name)} {ddl}")
        added += 1
    return added


def add_indexes(conn: sqlite3.Connection) -> None:
    indexes = (
        ("toefl_mock_attempt", "review_status", "ix_toefl_mock_attempt_review_status"),
        (
            "toefl_mock_attempt",
            "review_reviewer_id",
            "ix_toefl_mock_attempt_review_reviewer_id",
        ),
        ("toefl_mock_response", "review_status", "ix_toefl_mock_response_review_status"),
        ("toefl_mock_response", "reviewed_by", "ix_toefl_mock_response_reviewed_by"),
    )
    for table, column, index in indexes:
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS {quote(index)} "
            f"ON {quote(table)} ({quote(column)})"
        )


def manual_question_rubrics(
    package_root: Path,
) -> dict[str, dict[str, tuple[str, str] | None]]:
    result: dict[str, dict[str, tuple[str, str] | None]] = {}
    if not package_root.is_dir():
        return result
    for content_path in sorted(package_root.glob("*/content.json")):
        try:
            content = json.loads(content_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        exam = content.get("exam", {})
        exam_id = str(exam.get("id") or content_path.parent.name)
        groups = {
            str(item.get("id")): item.get("task_type")
            for item in content.get("groups", [])
            if item.get("id")
        }
        result[exam_id] = {
            str(item["id"]): (
                (RUBRIC_CODES[groups.get(str(item.get("group_id")))], RUBRIC_VERSION)
                if groups.get(str(item.get("group_id"))) in RUBRIC_CODES
                else None
            )
            for item in content.get("questions", [])
            if item.get("grading_status") == "manual"
            and item.get("id")
        }
    return result


def backfill(
    conn: sqlite3.Connection,
    package_root: Path,
) -> tuple[int, int]:
    package_manual = manual_question_rubrics(package_root)
    attempts_changed = 0
    responses_changed = 0
    attempts = conn.execute(
        "SELECT id, exam_id, status, review_status FROM toefl_mock_attempt"
    ).fetchall()
    for attempt_id, exam_id, status, review_status in attempts:
        manual_ids = package_manual.get(str(exam_id))
        # If the package is no longer present, keep the newly-added conservative
        # defaults instead of guessing whether legacy responses were manual.
        if manual_ids is None:
            continue
        if status == "completed" and review_status == "not_started":
            new_status = "pending" if manual_ids else "not_required"
            conn.execute(
                "UPDATE toefl_mock_attempt SET review_status = ? WHERE id = ?",
                (new_status, attempt_id),
            )
            attempts_changed += 1
        rows = conn.execute(
            "SELECT id, question_id, review_status, rubric_code, rubric_version "
            "FROM toefl_mock_response WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchall()
        for response_id, question_id, current_status, current_code, current_version in rows:
            is_manual = str(question_id) in manual_ids
            rubric = manual_ids.get(str(question_id))
            new_status = "pending" if is_manual else "not_required"
            # The added column defaults every legacy row to ``pending``.  Only
            # rows with a legacy/default status need correcting.  Never overwrite
            # draft/reviewed state when an operator reruns this idempotent script
            # after teachers have started grading.
            should_update = (
                is_manual
                and current_status in (None, "", "not_started", "not_required")
            ) or (
                not is_manual
                and current_status in (None, "", "not_started", "pending")
            )
            if not should_update or current_status == new_status:
                status_needs_update = False
            else:
                status_needs_update = True
            rubric_needs_update = bool(
                rubric
                and (current_code != rubric[0] or current_version != rubric[1])
            )
            if not status_needs_update and not rubric_needs_update:
                continue
            if status_needs_update and rubric:
                conn.execute(
                    "UPDATE toefl_mock_response SET review_status = ?, rubric_code = ?, rubric_version = ? WHERE id = ?",
                    (new_status, rubric[0], rubric[1], response_id),
                )
            elif status_needs_update:
                conn.execute(
                    "UPDATE toefl_mock_response SET review_status = ? WHERE id = ?",
                    (new_status, response_id),
                )
            else:
                conn.execute(
                    "UPDATE toefl_mock_response SET rubric_code = ?, rubric_version = ? WHERE id = ?",
                    (rubric[0], rubric[1], response_id),
                )
            responses_changed += 1
    return attempts_changed, responses_changed


def migrate(database: Path, package_root: Path | None = None) -> int:
    package_root = package_root or database.resolve().parent / "data" / "toefl_practice_v2"
    if not package_root.is_dir():
        print(f"TOEFL v2 package root missing: {package_root}", file=sys.stderr)
        return 1
    try:
        conn = sqlite3.connect(database)
    except sqlite3.Error as exc:
        print(f"cannot open database: {exc}", file=sys.stderr)
        return 1
    try:
        missing = [
            table
            for table in ("toefl_mock_attempt", "toefl_mock_response")
            if not table_exists(conn, table)
        ]
        if missing:
            print(
                "TOEFL v2 tables missing; run the base schema first: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            return 1
        attempt_added = add_columns(conn, "toefl_mock_attempt", ATTEMPT_COLUMNS)
        response_added = add_columns(conn, "toefl_mock_response", RESPONSE_COLUMNS)
        add_indexes(conn)
        attempts_changed, responses_changed = backfill(conn, package_root)
        conn.commit()
        print(
            "migration complete: "
            f"database={database}; attempt_columns_added={attempt_added}; "
            f"response_columns_added={response_added}; "
            f"attempts_backfilled={attempts_changed}; "
            f"responses_backfilled={responses_changed}"
        )
        return 0
    except sqlite3.Error as exc:
        conn.rollback()
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    result.add_argument(
        "--package-root",
        type=Path,
        help="TOEFL v2 package directory; defaults beside the selected database",
    )
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    raise SystemExit(migrate(args.database, args.package_root))
