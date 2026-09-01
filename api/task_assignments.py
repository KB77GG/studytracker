"""Staff-safe history checks for the unified task assignment drawer."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from models import User
from services.task_assignment_duplicates import check_duplicate_assignments

task_assignments_bp = Blueprint("task_assignments", __name__)


def _staff() -> bool:
    return bool(
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None)
        in {User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT}
    )


@task_assignments_bp.post("/api/task-assignments/duplicates")
@login_required
def duplicate_check_api():
    if not _staff():
        return jsonify(ok=False, error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    names = data.get("student_names") or []
    payload = dict(data)
    payload.pop("student_names", None)
    result = check_duplicate_assignments(names, payload)
    # This endpoint is deliberately history-only.  In particular, it does not
    # include Task/PlanItem access tokens, answers, or assignment URLs.
    return jsonify(ok=True, **result)
