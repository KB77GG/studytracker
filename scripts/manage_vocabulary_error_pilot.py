#!/usr/bin/env python3
"""Preview pilot enrollment without importing app/config or exporting identities.

Default: SQLite mode=ro, no enrollment or historical queue import. Applying
requires explicit student IDs, the reviewed start time and preview digest.
It only enrolls students; it never changes the global runtime switch.
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

TABLES = (
    "vocabulary_review_policy_enrollment",
    "vocabulary_error_queue",
    "vocabulary_policy_checkpoint",
    "vocabulary_policy_allocation",
    "vocabulary_policy_event",
)
POLICY_DEFAULTS = {
    "DAILY_LIMIT": 20,
    "SAMPLE_LIMIT": 4,
    "MAINTENANCE_LIMIT": 10,
    "SUCCESS_INTERVAL_DAYS": 2,
    "FAILURE_LIMIT": 3,
    "PAUSE_DAYS": 7,
    "OVERDUE_DAYS": 7,
}
READ_COLUMNS = {
    "sqlite_master": {"name", "type"},
    "user": {"id", "role", "is_active"},
    "vocabulary_learning_flow": {"student_id", "started_at"},
    "vocabulary_review_attempt": {"student_id", "submitted_at"},
    "vocabulary_review_session": {"student_id", "status"},
    **{name: {"student_id", "enabled", "starts_at"} for name in TABLES},
}


class ManagementError(ValueError):
    pass


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)  # noqa: UP017


def parse_start(value):
    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return at.astimezone(timezone.utc).replace(tzinfo=None) if at.tzinfo else at  # noqa: UP017


@contextmanager
def readonly(database):
    path = Path(database).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.25)
    try:
        connection.execute("PRAGMA query_only=ON")
        deadline = time.monotonic() + 10
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 5000)

        def authorize(action, table, column, _database, _source):
            permitted = action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE)
            if action == sqlite3.SQLITE_READ:
                permitted = table in READ_COLUMNS and (
                    column in READ_COLUMNS[table] or column == ""
                )
            elif action == sqlite3.SQLITE_FUNCTION:
                permitted = (column or "").lower() in {"count", "coalesce"}
            elif action == sqlite3.SQLITE_PRAGMA:
                permitted = table == "database_list" and column is None
            return sqlite3.SQLITE_OK if permitted else sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        yield connection
        assert connection.total_changes == 0
    finally:
        connection.close()


def _ids(values):
    selected = sorted({int(value) for value in values})
    if any(value <= 0 for value in selected) or len(selected) > 500:
        raise ManagementError("invalid_selection")
    return selected


def effective_policy_parameters(database):
    """Read only the seven public knobs, with Config's environment precedence.

    The first .env occurrence wins, quotes follow Config's simple loader, and
    process environment overrides the file. Never import config/app, mutate
    os.environ, or copy unrelated values into the preview.
    """
    keys = {f"VOCABULARY_ERROR_REVIEW_{name}": name for name in POLICY_DEFAULTS}
    raw = {}
    env_file = Path(database).resolve(strict=True).parent / ".env"
    if env_file.exists():
        try:
            with env_file.open(encoding="utf-8") as source:
                for raw_line in source:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    if key in keys and key not in raw:
                        raw[key] = value.strip().strip("'").strip('"')
        except (OSError, UnicodeError) as error:
            raise ManagementError("policy_environment_unreadable") from error
    raw.update({key: os.environ[key] for key in keys if key in os.environ})
    parameters = {}
    for key, name in keys.items():
        value = raw.get(key, POLICY_DEFAULTS[name])
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError(f"invalid_policy_config:{key}")
        try:
            parsed = int(value)
        except (ValueError, TypeError) as error:
            raise ValueError(f"invalid_policy_config:{key}") from error
        if parsed < (0 if name == "SAMPLE_LIMIT" else 1):
            raise ValueError(f"invalid_policy_config:{key}")
        parameters[name.lower()] = parsed
    if parameters["sample_limit"] > parameters["daily_limit"]:
        raise ValueError("policy_sample_limit_exceeds_daily_limit")
    return parameters


def _database_identity(connection):
    row = next(
        (row for row in connection.execute("PRAGMA database_list") if row[1] == "main"),
        None,
    )
    if row is None or not row[2]:
        raise ManagementError("file_database_required")
    database = Path(row[2]).resolve(strict=True)
    stat = database.stat()
    descriptor = {"path": str(database), "device": stat.st_dev, "inode": stat.st_ino}
    identity = hashlib.sha256(
        json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return database, identity


def preview(connection, *, student_ids=(), starts_at=None, now=None):
    now = now or utc_now()
    starts_at = starts_at or now
    database, identity = _database_identity(connection)
    parameters = effective_policy_parameters(database)
    selected = _ids(student_ids)
    explicit = bool(selected)
    if not selected:
        cutoff = (now - timedelta(days=28)).isoformat(" ")
        selected = _ids(
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT student_id FROM ("
                "SELECT student_id FROM vocabulary_learning_flow WHERE started_at>=? "
                "UNION SELECT student_id FROM vocabulary_review_attempt WHERE submitted_at>=?"
                ") LIMIT 501",
                (cutoff, cutoff),
            )
        )
    existing_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?,?,?,?,?)", TABLES
        )
    }
    active = set()
    pending = set()
    enrolled = set()
    counts = {name: 0 for name in TABLES}
    if selected:
        placeholders = ",".join("?" for _ in selected)
        active = {
            row[0]
            for row in connection.execute(
                f"SELECT id FROM user WHERE id IN ({placeholders}) AND role='student' AND is_active=1",
                selected,
            )
        }
        pending = {
            row[0]
            for row in connection.execute(
                f"SELECT DISTINCT student_id FROM vocabulary_review_session WHERE student_id IN ({placeholders}) AND status='active'",
                selected,
            )
        }
        if TABLES[0] in existing_tables:
            enrolled = {
                row[0]
                for row in connection.execute(
                    f"SELECT student_id FROM {TABLES[0]} WHERE student_id IN ({placeholders})",
                    selected,
                )
            }
        for name in existing_tables:
            counts[name] = connection.execute(
                f"SELECT COUNT(*) FROM {name} WHERE student_id IN ({placeholders})", selected
            ).fetchone()[0]
    result = {
        "read_only_preview": True,
        "selection": "explicit" if explicit else "recent_28d_activity_preview_only",
        "selected_count": len(selected),
        "active_student_count": len(active),
        "invalid_or_inactive_count": len(set(selected) - active),
        "unfinished_review_count": len(pending),
        "already_enrolled_count": len(enrolled),
        "eligible_new_enrollment_count": len(active - pending - enrolled),
        "schema_ready": len(existing_tables) == len(TABLES),
        "missing_table_count": len(TABLES) - len(existing_tables),
        "existing_policy_rows": counts,
        "starts_at_utc": starts_at.isoformat() + "Z",
        "database_identity": identity,
        "policy_parameters": parameters,
        "historical_error_rows_to_import": 0,
        "initial_mandatory_rows_to_create": 0,
        "global_switch_unchanged": True,
        "identity_rows_exported": False,
    }
    digest_input = {"selection_ids": selected, "preview": result}
    result["preview_digest"] = hashlib.sha256(
        json.dumps(digest_input, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return result


def apply_enrollment(database, *, student_ids, starts_at, expected_digest, now=None):
    selected = _ids(student_ids)
    now = now or utc_now()
    if not selected or len(selected) > 50 or not expected_digest:
        raise ManagementError("explicit_reviewed_selection_required")
    if starts_at < now - timedelta(minutes=10):
        raise ManagementError("start_time_expired_repreview_required")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from flask import Flask
    from sqlalchemy.orm import load_only

    from models import User, db
    from services.vocabulary_error_queue import enroll_student, policy_settings

    app = Flask("vocabulary-pilot-management")
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///" + str(Path(database).resolve(strict=True)),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"timeout": 1}},
        VOCABULARY_ERROR_REVIEW_ENABLED=False,
    )
    db.init_app(app)
    with app.app_context():
        try:
            db.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            raw = db.session.connection().connection.driver_connection
            checked = preview(raw, student_ids=selected, starts_at=starts_at, now=now)
            if checked["preview_digest"] != expected_digest:
                raise ManagementError("preview_changed_repreview_required")
            app.config.update(
                {
                    f"VOCABULARY_ERROR_REVIEW_{name.upper()}": value
                    for name, value in checked["policy_parameters"].items()
                }
            )
            if policy_settings() != checked["policy_parameters"]:
                raise ManagementError("policy_parameters_changed_repreview_required")
            if not checked["schema_ready"] or checked["eligible_new_enrollment_count"] != len(
                selected
            ):
                raise ManagementError("selected_students_not_ready")
            users = (
                User.query.options(load_only(User.id, User.role, User.is_active))
                .filter(User.id.in_(selected))
                .all()
            )
            for user in users:
                enroll_student(user, starts_at=starts_at, now=now)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        finally:
            db.session.remove()
    return {
        "applied": True,
        "enrolled_count": len(selected),
        "starts_at_utc": starts_at.isoformat() + "Z",
        "initial_mandatory_rows_created": 0,
        "historical_error_rows_imported": 0,
        "global_switch_unchanged": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--student-id", type=int, action="append", default=[])
    parser.add_argument("--starts-at")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-preview-digest")
    args = parser.parse_args()
    try:
        starts_at = parse_start(args.starts_at) if args.starts_at else utc_now()
        if args.apply:
            if not args.starts_at:
                raise ManagementError("reviewed_start_time_required")
            result = apply_enrollment(
                args.database,
                student_ids=args.student_id,
                starts_at=starts_at,
                expected_digest=args.expected_preview_digest,
            )
        else:
            with readonly(args.database) as connection:
                result = preview(connection, student_ids=args.student_id, starts_at=starts_at)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ManagementError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        return 1
    except Exception:
        # SQL, selected identities and secrets must never appear in stderr.
        print(json.dumps({"ok": False, "error": "pilot_management_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
