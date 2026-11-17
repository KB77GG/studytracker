#!/usr/bin/env python3
"""Choose a small balanced pilot from read-only learning metadata.

No identities leave stdout. --save-private writes only a mode-0600 manifest,
never learning data. Enrollment is a separate reviewed operation.
"""

import argparse
import json
import os
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

COLUMNS = {
    "user": {"id", "role", "is_active"},
    "student_profile": {"id", "user_id", "is_deleted", "primary_teacher_id"},
    "teacher_student_link": {"teacher_id", "student_id"},
    "vocabulary_learning_question": {
        "student_id",
        "task_id",
        "sense_id",
        "dimension",
        "first_attempt_id",
        "score_eligible",
        "remediation_kind",
        "first_is_correct",
    },
    "dictation_record": {
        "student_id",
        "task_id",
        "attempt_id",
        "created_at",
        "is_first_attempt",
        "is_correct",
        "response_kind",
    },
    "vocabulary_review_session": {"student_id", "status"},
    "vocabulary_review_policy_enrollment": {"student_id"},
}


def connect_readonly(path):
    conn = sqlite3.connect(
        Path(path).resolve(strict=True).as_uri() + "?mode=ro", uri=True, timeout=0.25
    )
    conn.execute("PRAGMA query_only=ON")
    deadline = time.monotonic() + 15
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 5000)

    def authorize(action, table, column, *_):
        allowed = action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE)
        if action == sqlite3.SQLITE_READ:
            allowed = table in COLUMNS and (column in COLUMNS[table] or column == "")
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY

    conn.set_authorizer(authorize)
    return conn


def choose(candidates, size=6):
    """Equal lower/upper halves, stable error-ratio extremes within each half."""
    if size not in (4, 6) or len(candidates) < size:
        raise ValueError("insufficient_eligible_students")
    ordered = sorted(
        candidates, key=lambda row: (row["errors"] / row["answers"], row["student_id"])
    )
    half = len(ordered) // 2
    low = ordered[:half][: size // 2]
    high = list(reversed(ordered[half:]))[: size // 2]
    return {"lower_error": low, "higher_error": high}


def select(conn, now, size=6):
    cutoff = (now - timedelta(days=28)).isoformat(" ")
    recent = (now - timedelta(days=7)).isoformat(" ")
    bounds = (cutoff, now.isoformat(" "))
    rows = conn.execute(
        """
        SELECT q.student_id,q.task_id,q.sense_id,q.dimension,r.created_at,
               r.is_correct,r.response_kind
        FROM vocabulary_learning_question q CROSS JOIN dictation_record r
        WHERE q.student_id=r.student_id AND q.task_id=r.task_id
          AND q.first_attempt_id=r.attempt_id
          AND r.created_at>=? AND r.created_at<? AND r.is_first_attempt=1
          AND q.first_is_correct IS NOT NULL AND q.score_eligible=1
          AND q.remediation_kind IS NULL
    """,
        bounds,
    ).fetchmany(500001)
    if len(rows) > 500000:
        raise ValueError("row_limit_exceeded")
    grouped = defaultdict(
        lambda: {"answers": 0, "errors": 0, "tasks": set(), "last": "", "error_items": set()}
    )
    for student, task, sense, dimension, at, correct, response in rows:
        if correct not in (0, 1) or response not in (None, "answer", "forgot"):
            continue
        row = grouped[student]
        row["answers"] += 1
        wrong = not correct or response == "forgot"
        row["errors"] += int(wrong)
        if wrong:
            row["error_items"].add((task, sense, dimension))
        row["tasks"].add(task)
        row["last"] = max(row["last"], at)
    active = {
        row[0] for row in conn.execute("SELECT id FROM user WHERE role='student' AND is_active=1")
    }
    teachers = {
        row[0]
        for row in conn.execute(
            "SELECT id FROM user WHERE role IN ('teacher','admin','assistant') AND is_active=1"
        )
    }
    profiles = {
        row[0]: (row[1], row[2])
        for row in conn.execute(
            "SELECT id,user_id,primary_teacher_id FROM student_profile WHERE is_deleted=0 AND user_id IS NOT NULL"
        )
    }
    assigned = defaultdict(set)
    for _, (student, teacher) in profiles.items():
        if teacher in teachers:
            assigned[student].add(teacher)
    for teacher, profile in conn.execute("SELECT teacher_id,student_id FROM teacher_student_link"):
        if teacher in teachers and profile in profiles:
            assigned[profiles[profile][0]].add(teacher)
    pending = {
        row[0]
        for row in conn.execute(
            "SELECT student_id FROM vocabulary_review_session WHERE status='active'"
        )
    }
    enrolled = {
        row[0] for row in conn.execute("SELECT student_id FROM vocabulary_review_policy_enrollment")
    }
    recent_sufficient = {
        student
        for student, row in grouped.items()
        if row["last"] >= recent and len(row["tasks"]) >= 3 and row["answers"] >= 20
    }
    eligible = recent_sufficient & active & set(assigned) - pending - enrolled
    candidates = [{"student_id": student, **grouped[student]} for student in eligible]
    groups = choose(candidates, size=size) if len(candidates) >= size else {}
    selected = [row["student_id"] for values in groups.values() for row in values]
    output = {
        "at_utc": now.isoformat() + "Z",
        "read_only": True,
        "criteria": {
            "lookback_days": 28,
            "recent_days": 7,
            "minimum_tasks": 3,
            "minimum_formal_first_answers": 20,
            "active_teacher_assignment_required": True,
            "unfinished_review_excluded": True,
        },
        "observed_students": len(grouped),
        "recent_sufficient_students": len(recent_sufficient),
        "recent_active_students": len(recent_sufficient & active),
        "recent_assigned_students": len(recent_sufficient & set(assigned)),
        "already_enrolled_exclusions": len(recent_sufficient & enrolled),
        "eligible_students": len(eligible),
        "unfinished_review_exclusions": len(recent_sufficient & pending),
        "selected_count": len(selected),
        "selection_ready": len(selected) == size,
        "selected_teacher_count": len(set().union(*(assigned[student] for student in selected))),
        "groups": {},
        "historical_error_rows_to_import": 0,
        "student_identity_rows_exported": False,
        "database_changes": conn.total_changes,
        "teacher_willingness_verified": False,
    }
    for label, values in groups.items():
        rates = [row["errors"] / row["answers"] for row in values]
        output["groups"][label] = {
            "students": len(values),
            "formal_first_answers": sum(row["answers"] for row in values),
            "errors": sum(row["errors"] for row in values),
            "error_rate_range": [round(min(rates), 4), round(max(rates), 4)],
            "observed_task_count": sum(len(row["tasks"]) for row in values),
        }
    private = {
        "version": 1,
        "selected_at_utc": output["at_utc"],
        "student_ids": sorted(selected),
        "groups": {
            label: [row["student_id"] for row in values] for label, values in groups.items()
        },
        "selection_summary": output,
    }
    return output, private


def save_private(path, manifest):
    target = Path(path)
    if target.is_symlink() or not target.parent.is_dir():
        raise ValueError("private_destination_invalid")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--size", type=int, choices=(4, 6), default=6)
    parser.add_argument("--save-private")
    args = parser.parse_args()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)  # noqa: UP017 - Python 3.10
        with connect_readonly(args.database) as conn:
            output, private = select(conn, now, args.size)
        if args.save_private:
            if not output["selection_ready"]:
                raise ValueError("insufficient_eligible_students")
            save_private(args.save_private, private)
            output["private_manifest_saved"] = True
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        code = (
            str(error)
            if isinstance(error, ValueError)
            and str(error)
            in {
                "insufficient_eligible_students",
                "row_limit_exceeded",
                "private_destination_invalid",
            }
            else "pilot_selection_failed_no_identities_exported"
        )
        print(json.dumps({"ok": False, "error": code, "exception_type": type(error).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
