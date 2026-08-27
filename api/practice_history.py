"""Student-facing web practice history for the practice dashboard."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required
from sqlalchemy import func

from models import (
    ListeningSegmentResult,
    ListeningTestSubmission,
    PracticeSubmissionAttempt,
    ReadingTestSubmission,
    StudentProfile,
    Task,
    User,
    db,
)
from services.practice_attempt_reporting import (
    build_detailed_attempt_history,
    load_attempts_by_task,
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


def _test_review_url(
    task: Task,
    test_id: str,
    kind: str,
    scope: int | None,
    attempt_id: int | None = None,
) -> str:
    safe_id = quote(test_id, safe="")
    params = {}
    if attempt_id:
        params["history_attempt"] = int(attempt_id)
    if kind == "reading":
        path = f"/reading/test/{safe_id}"
        if scope:
            params["passage"] = int(scope)
        return f"{path}?{urlencode(params)}" if params else path

    resource_type = (task.listening_resource_type or "intensive").strip()
    if resource_type == "jijing":
        return f"/listening/jijing/{safe_id}"
    path = f"/listening/test/{safe_id}"
    if scope:
        params["section"] = int(scope)
    return f"{path}?{urlencode(params)}" if params else path


def _source_label(task: Task, kind: str) -> str:
    if kind == "reading":
        return (
            "阅读机经" if (task.reading_test_id or "").startswith("reading_jijing_") else "剑雅阅读"
        )
    if (task.listening_resource_type or "").strip() == "jijing":
        return "听力机经"
    return "剑雅听力"


def _json_object(value: str | None) -> dict:
    try:
        decoded = json.loads(value or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _json_list(value: str | None) -> list:
    try:
        decoded = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []


def _json_rows(value: str | None) -> list[dict]:
    return [row for row in _json_list(value) if isinstance(row, dict)]


def _score_attempt(
    item: dict,
    *,
    kind: str,
    scope: int | None,
    correct: int,
    total: int,
) -> dict:
    scope_word = "Passage" if kind == "reading" else "Section"
    submitted_at = item["submitted_at"]
    return {
        "label": f"{scope_word} {scope}" if scope else "整套",
        "scope": scope,
        "correct_count": int(correct or 0),
        "total_count": int(total or 0),
        "accuracy": round(correct / total * 100, 1) if total else 0.0,
        "url": _test_review_url(
            item["task"],
            item["test_id"],
            kind,
            scope,
            item.get("attempt_id"),
        ),
        "attempt_number": int(item.get("attempt_number") or 1),
        "submitted_at": submitted_at.isoformat() if submitted_at else None,
        "_submitted_at": submitted_at or datetime.min,
        "_task_id": int(item["task"].id or 0),
    }


def _submission_scope_attempts(item: dict, kind: str) -> list[dict]:
    submission = item["submission"]
    explicit_scope = item.get("scope")
    if explicit_scope:
        return [
            _score_attempt(
                item,
                kind=kind,
                scope=explicit_scope,
                correct=int(submission.correct_count or 0),
                total=int(submission.total_count or 0),
            )
        ]

    scope_key = "passage" if kind == "reading" else "section"
    answers = _json_object(submission.answers_json)
    result_groups: dict[int, list[dict]] = defaultdict(list)
    for row in _json_rows(submission.results_json):
        raw_scope = row.get(scope_key)
        try:
            scope = int(raw_scope) + 1
        except (TypeError, ValueError):
            continue
        if scope <= 0:
            continue
        result_groups[scope].append(row)

    attempts = []
    for scope, rows in sorted(result_groups.items()):
        attempted = False
        for row in rows:
            ids = [str(value) for value in (row.get("ids") or [])]
            if any(str(answers.get(question_id, "")).strip() for question_id in ids):
                attempted = True
                break
            if str(row.get("value") or "").strip():
                attempted = True
                break
        if not attempted:
            continue
        correct = sum(int(row.get("awarded") or 0) for row in rows)
        total = sum(max(1, int(row.get("marks") or 1)) for row in rows)
        attempts.append(
            _score_attempt(
                item,
                kind=kind,
                scope=scope,
                correct=correct,
                total=total,
            )
        )
    if attempts:
        return attempts
    return [
        _score_attempt(
            item,
            kind=kind,
            scope=None,
            correct=int(submission.correct_count or 0),
            total=int(submission.total_count or 0),
        )
    ]


def _serialize_submission_groups(items: list[dict], kind: str) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for item in items:
        test_id = item["test_id"]
        day = _task_date(item["task"], item["submitted_at"])
        groups[(day, kind, test_id)].append(item)

    records = []
    for (day, row_kind, test_id), group_items in groups.items():
        group_items.sort(
            key=lambda item: (
                item["submitted_at"] or datetime.min,
                item["task"].id or 0,
            ),
            reverse=True,
        )
        latest = group_items[0]
        latest_submission = latest["submission"]
        latest_task = latest["task"]
        all_attempts = [
            attempt
            for item in group_items
            for attempt in _submission_scope_attempts(item, row_kind)
        ]
        all_attempts.sort(
            key=lambda attempt: (
                attempt["scope"] or 0,
                attempt["_submitted_at"],
                attempt["_task_id"],
            )
        )
        latest_by_scope = {}
        for attempt in reversed(all_attempts):
            latest_by_scope.setdefault(attempt["scope"], attempt)
        current_attempts = sorted(
            latest_by_scope.values(), key=lambda attempt: attempt["scope"] or 0
        )
        correct = sum(attempt["correct_count"] for attempt in current_attempts)
        total = sum(attempt["total_count"] for attempt in current_attempts)
        accuracy = (
            round(correct / total * 100, 1)
            if total
            else round(float(latest_submission.accuracy or 0.0), 1)
        )
        scope_total = 3 if row_kind == "reading" else 4
        scope_word = "Passage" if row_kind == "reading" else "Section"
        scoped = bool(current_attempts) and all(
            attempt["scope"] for attempt in current_attempts
        )
        legacy_missing = sum(
            int(item.get("legacy_missing_attempts") or 0) for item in group_items
        )
        latest_item_attempts = _submission_scope_attempts(latest, row_kind)
        for attempt in all_attempts:
            attempt.pop("_submitted_at", None)
            attempt.pop("_task_id", None)
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
                    f"{len(current_attempts)}/{scope_total} {scope_word}" if scoped else "整套"
                ),
                "url": latest_item_attempts[-1]["url"] if latest_item_attempts else "#",
                "attempts": all_attempts,
                "legacy_missing_attempts": legacy_missing,
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


def _submission_items(
    current_rows: list[tuple],
    snapshot_rows: list[tuple],
    kind: str,
) -> list[dict]:
    items = []
    snapshots_by_task: dict[int, list[dict]] = defaultdict(list)
    for snapshot, task in snapshot_rows:
        if snapshot.kind != kind:
            continue
        item = {
            "submission": snapshot,
            "task": task,
            "test_id": (snapshot.test_id or "").strip(),
            "scope": snapshot.scope_number or _scope_number(task, kind),
            "submitted_at": snapshot.submitted_at or task.submitted_at,
            "attempt_id": snapshot.id,
            "attempt_number": int(snapshot.attempt_number or 1),
            "legacy_missing_attempts": 0,
        }
        items.append(item)
        snapshots_by_task[task.id].append(item)

    for submission, task in current_rows:
        task_snapshots = snapshots_by_task.get(task.id, [])
        current_number = max(1, int(submission.attempt_count or 1))
        current_item = next(
            (
                item
                for item in task_snapshots
                if item["attempt_number"] == current_number
            ),
            None,
        )
        if not current_item:
            current_item = {
                "submission": submission,
                "task": task,
                "test_id": (submission.test_id or "").strip(),
                "scope": _scope_number(task, kind),
                "submitted_at": submission.submitted_at or task.submitted_at,
                "attempt_id": None,
                "attempt_number": current_number,
                "legacy_missing_attempts": 0,
            }
            items.append(current_item)
        retained_numbers = {
            item["attempt_number"] for item in task_snapshots
        } | {current_number}
        current_item["legacy_missing_attempts"] = max(
            0, current_number - len(retained_numbers)
        )
    return items


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
    snapshot_rows = (
        db.session.query(PracticeSubmissionAttempt, Task)
        .join(Task, Task.id == PracticeSubmissionAttempt.task_id)
        .filter(Task.student_name == student_name)
        .order_by(PracticeSubmissionAttempt.submitted_at.desc())
        .limit(240)
        .all()
    )
    records = [
        *_serialize_submission_groups(
            _submission_items(listening_rows, snapshot_rows, "listening"),
            "listening",
        ),
        *_serialize_submission_groups(
            _submission_items(reading_rows, snapshot_rows, "reading"),
            "reading",
        ),
        *_serialize_intensive_records(student_name),
    ]
    records.sort(key=lambda item: item["_sort_at"], reverse=True)
    for record in records:
        record.pop("_sort_at", None)
    return records[:limit]


def _serialize_attempt_submission(attempt: PracticeSubmissionAttempt) -> dict:
    return {
        "task_id": attempt.task_id,
        "student_name": attempt.student_name,
        "test_id": attempt.test_id,
        "test_title": attempt.test_title,
        "correct_count": int(attempt.correct_count or 0),
        "total_count": int(attempt.total_count or 0),
        "accuracy": round(float(attempt.accuracy or 0.0), 1),
        "ielts_score": attempt.ielts_score,
        "completion_rate": round(float(attempt.completion_rate or 0.0), 1),
        "duration_seconds": int(attempt.duration_seconds or 0),
        "attempt_count": int(attempt.attempt_number or 1),
        "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        "answers": _json_object(attempt.answers_json),
        "results": _json_rows(attempt.results_json),
        "wrong_numbers": _json_list(attempt.wrong_numbers_json),
    }


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


@practice_history_bp.get("/api/practice/history/attempt/<int:attempt_id>")
def practice_history_attempt(attempt_id: int):
    """Return one immutable attempt owned by the verified student."""
    profile = _current_student_profile()
    if not profile:
        return jsonify({"ok": False, "error": "not_verified"}), 401
    attempt = PracticeSubmissionAttempt.query.filter_by(
        id=attempt_id,
        student_name=profile.full_name,
    ).first()
    if not attempt:
        return jsonify({"ok": False, "error": "attempt_not_found"}), 404
    return jsonify(
        {
            "ok": True,
            "kind": attempt.kind,
            "submission": _serialize_attempt_submission(attempt),
        }
    )


@practice_history_bp.get("/api/staff/tasks/<int:task_id>/attempt-history")
@login_required
def staff_task_attempt_history(task_id: int):
    """Return one IELTS task's retained history to authorized web staff."""
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"ok": False, "error": "task_not_found"}), 404

    role = getattr(current_user, "role", None)
    if not getattr(current_user, "is_active", False) or role not in {
        User.ROLE_ADMIN,
        User.ROLE_ASSISTANT,
        User.ROLE_TEACHER,
    }:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if role == User.ROLE_TEACHER and int(task.created_by or 0) != int(current_user.id):
        return jsonify({"ok": False, "error": "forbidden_task"}), 403

    submission = ListeningTestSubmission.query.filter_by(task_id=task.id).first()
    kind = "listening"
    if not submission:
        submission = ReadingTestSubmission.query.filter_by(task_id=task.id).first()
        kind = "reading"
    if not submission:
        return jsonify({"ok": False, "error": "attempt_history_not_found"}), 404

    snapshots = load_attempts_by_task([task.id]).get(task.id, [])
    return jsonify(
        {
            "ok": True,
            "task": {
                "id": task.id,
                "student_name": task.student_name,
                "title": submission.test_title or task.detail or "练习记录",
                "kind": kind,
                "kind_label": "听力" if kind == "listening" else "阅读",
            },
            "attempt_overview": build_detailed_attempt_history(
                submission,
                snapshots,
                kind=kind,
            ),
        }
    )
