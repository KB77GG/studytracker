"""Staff-only read endpoints for homework answer timelines (作答过程)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from models import Task, User, db
from services.answer_integrity import latest_logs_by_task, serialize_log, task_logs
from services.answer_timeline_rules import LEVEL_LABELS

answer_integrity_bp = Blueprint("answer_integrity", __name__)

_STAFF_ROLES = {User.ROLE_ADMIN, User.ROLE_ASSISTANT, User.ROLE_TEACHER}
MAX_SUMMARY_TASKS = 200


def _staff_role() -> str | None:
    role = getattr(current_user, "role", None)
    if not getattr(current_user, "is_active", False) or role not in _STAFF_ROLES:
        return None
    return role


def _teacher_owns(task: Task) -> bool:
    """Same scope rule as the existing staff attempt-history endpoint."""
    return int(task.created_by or 0) == int(current_user.id)


_MAX_TASK_ID_DIGITS = 12


def _parse_task_ids(raw: str) -> list[int]:
    """Plain ASCII task ids only; anything else (e.g. '²', huge numbers) is skipped."""
    ids: list[int] = []
    for part in (raw or "").split(",")[: MAX_SUMMARY_TASKS * 2]:
        part = part.strip()
        if part.isascii() and part.isdigit() and len(part) <= _MAX_TASK_ID_DIGITS:
            ids.append(int(part))
    return list(dict.fromkeys(ids))[:MAX_SUMMARY_TASKS]


@answer_integrity_bp.get("/api/staff/answer-integrity/summary")
@login_required
def staff_answer_integrity_summary():
    """Latest flag level per task, for badges on the task list."""
    role = _staff_role()
    if not role:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    task_ids = _parse_task_ids(request.args.get("task_ids", ""))
    if role == User.ROLE_TEACHER and task_ids:
        owned = db.session.query(Task.id).filter(
            Task.id.in_(task_ids), Task.created_by == current_user.id
        )
        task_ids = [row[0] for row in owned]
    items = {
        str(task_id): {
            "level": row.level,
            "level_label": LEVEL_LABELS.get(row.level, row.level),
            "has_timeline": bool(row.has_timeline),
        }
        for task_id, row in latest_logs_by_task(task_ids).items()
    }
    return jsonify({"ok": True, "items": items})


@answer_integrity_bp.get("/api/staff/tasks/<int:task_id>/answer-integrity")
@login_required
def staff_task_answer_integrity(task_id: int):
    """Every retained answering timeline of one task, newest first."""
    role = _staff_role()
    if not role:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"ok": False, "error": "task_not_found"}), 404
    if role == User.ROLE_TEACHER and not _teacher_owns(task):
        return jsonify({"ok": False, "error": "forbidden_task"}), 403
    return jsonify(
        {
            "ok": True,
            "task": {"id": task.id, "student_name": task.student_name, "title": task.detail or ""},
            "logs": [serialize_log(row, include_events=True) for row in task_logs(task.id)],
        }
    )
