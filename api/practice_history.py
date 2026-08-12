"""Student-facing web practice history for the practice dashboard."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import quote

from flask import Blueprint, jsonify, request, session
from flask_login import current_user
from sqlalchemy import func

from models import (
    ListeningSegmentResult,
    ListeningTestSubmission,
    ReadingTestSubmission,
    StudentProfile,
    Task,
    User,
    db,
)

practice_history_bp = Blueprint("practice_history", __name__)

_CAMBRIDGE_TEST_RE = re.compile(r"^ielts(\d+)_test(\d+)$", re.IGNORECASE)
_JFDR_TEST_RE = re.compile(r"^jfdr(\d+)_test(\d+)$", re.IGNORECASE)


def _current_student_profile() -> StudentProfile | None:
    name = (session.get("practice_student_name") or "").strip()
    if name:
        profile = StudentProfile.query.filter_by(
            full_name=name,
            is_deleted=False,
        ).first()
        if profile:
            return profile
        session.pop("practice_student_name", None)

    if (
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None) == User.ROLE_STUDENT
    ):
        return StudentProfile.query.filter_by(
            user_id=current_user.id,
            is_deleted=False,
        ).first()
    return None


def _task_metadata(task: Task) -> dict:
    try:
        payload = json.loads(task.question_ids or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _scope_number(task: Task, kind: str) -> int | None:
    if kind == "reading":
        value = task.reading_passage_number
    else:
        value = _task_metadata(task).get("listening_section_number")
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _display_title(test_id: str, fallback: str | None, kind: str) -> str:
    match = _CAMBRIDGE_TEST_RE.match(test_id)
    if match:
        return f"剑桥雅思 {match.group(1)} · Test {match.group(2)}"
    match = _JFDR_TEST_RE.match(test_id)
    if match:
        return f"9分达人 {match.group(1)} · Test {match.group(2)}"

    title = (fallback or test_id or "练习记录").strip()
    scope_label = "Passage" if kind == "reading" else "(?:Section|Part)"
    title = re.sub(rf"\s+{scope_label}\s+\d+\s*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+(?:Listening|Reading)\s*$", "", title, flags=re.IGNORECASE)
    return title or "练习记录"


def _task_date(task: Task, submitted_at: datetime | None) -> str:
    if submitted_at:
        return (submitted_at + timedelta(hours=8)).date().isoformat()
    return task.date or ""


def _test_review_url(task: Task, test_id: str, kind: str, scope: int | None) -> str:
    safe_id = quote(test_id, safe="")
    if kind == "reading":
        path = f"/reading/test/{safe_id}"
        return f"{path}?passage={scope}" if scope else path

    resource_type = (task.listening_resource_type or "intensive").strip()
    if resource_type == "jijing":
        return f"/listening/jijing/{safe_id}"
    path = f"/listening/test/{safe_id}"
    return f"{path}?section={scope}" if scope else path


def _source_label(task: Task, kind: str) -> str:
    if kind == "reading":
        return (
            "阅读机经" if (task.reading_test_id or "").startswith("reading_jijing_") else "剑雅阅读"
        )
    if (task.listening_resource_type or "").strip() == "jijing":
        return "听力机经"
    return "剑雅听力"


def _serialize_submission_groups(rows: list[tuple], kind: str) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for submission, task in rows:
        test_id = (submission.test_id or "").strip()
        scope = _scope_number(task, kind)
        submitted_at = submission.submitted_at or task.submitted_at
        day = _task_date(task, submitted_at)
        # Section/Passage submissions from the same test and day form one record.
        # Whole-test submissions stay tied to their task to avoid summing retries.
        group_scope = "scoped" if scope else f"full:{task.id}"
        key = (day, kind, test_id, group_scope)
        groups[key].append(
            {
                "submission": submission,
                "task": task,
                "scope": scope,
                "submitted_at": submitted_at,
            }
        )

    records = []
    for (day, row_kind, test_id, group_scope), items in groups.items():
        items.sort(
            key=lambda item: (item["submitted_at"] or datetime.min, item["task"].id or 0),
            reverse=True,
        )
        if group_scope == "scoped":
            latest_by_scope = {}
            for item in items:
                latest_by_scope.setdefault(item["scope"], item)
            items = list(latest_by_scope.values())
        latest = items[0]
        latest_submission = latest["submission"]
        latest_task = latest["task"]
        correct = sum(int(item["submission"].correct_count or 0) for item in items)
        total = sum(int(item["submission"].total_count or 0) for item in items)
        accuracy = (
            round(correct / total * 100, 1)
            if total
            else round(float(latest_submission.accuracy or 0.0), 1)
        )
        is_scoped = group_scope == "scoped"
        scope_total = 3 if row_kind == "reading" else 4
        scope_word = "Passage" if row_kind == "reading" else "Section"
        attempts = []
        for item in sorted(items, key=lambda entry: entry["scope"] or 0):
            submission = item["submission"]
            scope = item["scope"]
            attempts.append(
                {
                    "label": f"{scope_word} {scope}" if scope else "整套",
                    "correct_count": int(submission.correct_count or 0),
                    "total_count": int(submission.total_count or 0),
                    "accuracy": round(float(submission.accuracy or 0.0), 1),
                    "url": _test_review_url(item["task"], test_id, row_kind, scope),
                }
            )
        records.append(
            {
                "kind": row_kind,
                "source_label": _source_label(latest_task, row_kind),
                "title": _display_title(
                    test_id, latest_submission.test_title or latest_task.detail, row_kind
                ),
                "date": day,
                "submitted_at": (
                    latest["submitted_at"].isoformat() if latest["submitted_at"] else None
                ),
                "correct_count": correct,
                "total_count": total,
                "accuracy": accuracy,
                "scope_label": (
                    f"{len(items)}/{scope_total} {scope_word}" if is_scoped else "整套"
                ),
                "url": _test_review_url(latest_task, test_id, row_kind, latest["scope"]),
                "attempts": attempts,
                "_sort_at": latest["submitted_at"] or datetime.min,
            }
        )
    return records


def _serialize_intensive_records(student_name: str) -> list[dict]:
    rows = (
        db.session.query(
            Task,
            func.sum(ListeningSegmentResult.correct_words),
            func.sum(ListeningSegmentResult.total_words),
            func.count(ListeningSegmentResult.id),
            func.max(ListeningSegmentResult.updated_at),
        )
        .join(ListeningSegmentResult, ListeningSegmentResult.task_id == Task.id)
        .filter(
            Task.student_name == student_name,
            Task.listening_exercise_id.isnot(None),
            Task.listening_resource_type == "intensive",
            ListeningSegmentResult.is_completed.is_(True),
        )
        .group_by(Task.id)
        .order_by(func.max(ListeningSegmentResult.updated_at).desc())
        .limit(40)
        .all()
    )
    records = []
    for task, correct_raw, total_raw, completed_count, updated_at in rows:
        correct = int(correct_raw or 0)
        total = int(total_raw or 0)
        accuracy = (
            round(correct / total * 100, 1) if total else round(float(task.accuracy or 0.0), 1)
        )
        token = quote((task.listening_access_token or "").strip(), safe="")
        exercise_id = quote((task.listening_exercise_id or "").strip(), safe="")
        url = f"/listening/{exercise_id}"
        if token:
            url = f"{url}?task_id={task.id}&token={token}"
        records.append(
            {
                "kind": "intensive",
                "source_label": "精听",
                "title": (task.detail or task.listening_exercise_id or "精听练习").strip(),
                "date": _task_date(task, updated_at),
                "submitted_at": updated_at.isoformat() if updated_at else None,
                "correct_count": correct,
                "total_count": total,
                "accuracy": accuracy,
                "scope_label": f"已完成 {int(completed_count or 0)} 句",
                "url": url,
                "attempts": [],
                "_sort_at": updated_at or datetime.min,
            }
        )
    return records


def _recent_practice_records(student_name: str, limit: int) -> list[dict]:
    listening_rows = (
        db.session.query(ListeningTestSubmission, Task)
        .join(Task, Task.id == ListeningTestSubmission.task_id)
        .filter(Task.student_name == student_name)
        .order_by(ListeningTestSubmission.submitted_at.desc())
        .limit(120)
        .all()
    )
    reading_rows = (
        db.session.query(ReadingTestSubmission, Task)
        .join(Task, Task.id == ReadingTestSubmission.task_id)
        .filter(Task.student_name == student_name)
        .order_by(ReadingTestSubmission.submitted_at.desc())
        .limit(120)
        .all()
    )
    records = [
        *_serialize_submission_groups(listening_rows, "listening"),
        *_serialize_submission_groups(reading_rows, "reading"),
        *_serialize_intensive_records(student_name),
    ]
    records.sort(key=lambda item: item["_sort_at"], reverse=True)
    for record in records:
        record.pop("_sort_at", None)
    return records[:limit]


@practice_history_bp.get("/api/practice/history")
def practice_history():
    """Return recent server-owned web practice submissions for one student."""
    profile = _current_student_profile()
    if not profile:
        return jsonify({"ok": False, "error": "not_verified"}), 401
    try:
        limit = min(10, max(1, int(request.args.get("limit") or 4)))
    except (TypeError, ValueError):
        limit = 4
    records = _recent_practice_records(profile.full_name, limit)
    return jsonify(
        {
            "ok": True,
            "name": profile.full_name,
            "records": records,
        }
    )
