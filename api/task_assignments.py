"""Staff-safe history checks for the unified task assignment drawer."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from models import User
from services.task_assignment_catalogs import (
    ListeningExerciseNotFound,
    load_intensive_listening_segments,
)
from services.task_assignment_duplicates import check_duplicate_assignments
from services.writing_assignments import catalog_options

task_assignments_bp = Blueprint("task_assignments", __name__)


def _staff() -> bool:
    return bool(
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None)
        in {User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT}
    )


@task_assignments_bp.get("/api/task-assignments/writing-catalog")
@login_required
def writing_catalog_api():
    """Return writing resources that can be assigned from the staff drawer."""

    if not _staff():
        return jsonify(ok=False, error="forbidden"), 403
    options = catalog_options()
    return jsonify(
        ok=True,
        resources=options,
        summary={
            "exercises": sum(row["resource_type"] == "exercise" for row in options),
            "mother_topics": sum(
                row["resource_type"] == "mother_topic" for row in options
            ),
        },
    )


@task_assignments_bp.get("/api/task-assignments/listening-segments")
@login_required
def listening_segments_api():
    """Load one intensive-listening sentence list on demand for staff."""

    if not _staff():
        return jsonify(ok=False, error="forbidden"), 403
    exercise_id = (request.args.get("exercise_id") or "").strip()
    if not exercise_id:
        return jsonify(ok=False, error="missing_exercise_id"), 400
    configured_root = current_app.config.get("LISTENING_ASSIGNMENT_ROOT")
    root = (
        Path(configured_root)
        if configured_root
        else Path(current_app.static_folder) / "listening"
    )
    try:
        segments = load_intensive_listening_segments(root, exercise_id)
    except ListeningExerciseNotFound:
        return jsonify(ok=False, error="not_found"), 404
    return jsonify(ok=True, exercise_id=exercise_id, segments=segments)


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
