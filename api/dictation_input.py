"""Teacher-authorized native input policy for English spelling practice."""

from datetime import datetime

from flask import Blueprint, jsonify, request

from api.auth_utils import require_api_user
from models import DictationInputGrant, StudentProfile, Task, User, db
from services.dictation_input_policy import (
    AUTHORIZED_GRANT_DAYS,
    create_input_grant,
    grant_payload,
    input_policy,
    teacher_can_manage_student,
)

dictation_input_bp = Blueprint("dictation_input", __name__, url_prefix="/api/dictation")


def _int_arg(value, error_name: str):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return error_name


def _student_task_for_user(user: User, task_id: int | None):
    if task_id is None:
        return None, None
    task = db.session.get(Task, task_id)
    if not task:
        return None, ("task_not_found", 404)
    profile = getattr(user, "student_profile", None)
    if user.role != User.ROLE_STUDENT or not profile or task.student_name != profile.full_name:
        return None, ("forbidden", 403)
    if not task.dictation_book_id:
        return None, ("task_not_dictation", 409)
    return task, None


@dictation_input_bp.get("/input-policy")
@require_api_user()
def get_input_policy():
    """Return strict-by-default policy for the current student."""

    user = request.current_api_user
    if user.role != User.ROLE_STUDENT:
        return jsonify({"ok": True, "policy": input_policy(user, "en_to_zh")})

    task_id = _int_arg(request.args.get("task_id"), "invalid_task_id")
    if isinstance(task_id, str):
        return jsonify({"ok": False, "error": task_id}), 400
    task, error = _student_task_for_user(user, task_id)
    if error:
        return jsonify({"ok": False, "error": error[0]}), error[1]

    mode = request.args.get("mode") or (task.dictation_mode if task else "spelling_drill")
    return jsonify({
        "ok": True,
        "policy": input_policy(user, mode, task_id=task.id if task else None),
    })


def _teacher_profile(user: User, student_profile_id: int | None):
    if not student_profile_id:
        return None, ("missing_student_profile_id", 400)
    profile = db.session.get(StudentProfile, student_profile_id)
    if not profile or profile.is_deleted:
        return None, ("student_not_found", 404)
    if not teacher_can_manage_student(user, profile):
        return None, ("forbidden_student", 403)
    return profile, None


@dictation_input_bp.get("/input-grants")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def list_input_grants():
    user = request.current_api_user
    student_profile_id = _int_arg(request.args.get("student_profile_id"), "invalid_student_profile_id")
    if isinstance(student_profile_id, str):
        return jsonify({"ok": False, "error": student_profile_id}), 400
    profile, error = _teacher_profile(user, student_profile_id)
    if error:
        return jsonify({"ok": False, "error": error[0]}), error[1]
    rows = (
        DictationInputGrant.query
        .filter_by(student_profile_id=profile.id)
        .order_by(DictationInputGrant.created_at.desc(), DictationInputGrant.id.desc())
        .limit(50)
        .all()
    )
    return jsonify({
        "ok": True,
        "student_profile_id": profile.id,
        "grants": [grant_payload(row) | {
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            "teacher_id": row.teacher_id,
        } for row in rows],
    })


@dictation_input_bp.post("/input-grants")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def create_teacher_input_grant():
    user = request.current_api_user
    data = request.get_json(silent=True) or {}
    student_profile_id = _int_arg(data.get("student_profile_id"), "invalid_student_profile_id")
    if isinstance(student_profile_id, str):
        return jsonify({"ok": False, "error": student_profile_id}), 400
    profile, error = _teacher_profile(user, student_profile_id)
    if error:
        return jsonify({"ok": False, "error": error[0]}), error[1]

    try:
        duration_days = int(data.get("duration_days"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_duration_days"}), 400
    if duration_days not in AUTHORIZED_GRANT_DAYS:
        return jsonify({"ok": False, "error": "invalid_duration_days", "allowed": sorted(AUTHORIZED_GRANT_DAYS)}), 400

    task_id = _int_arg(data.get("task_id"), "invalid_task_id")
    if isinstance(task_id, str):
        return jsonify({"ok": False, "error": task_id}), 400
    task = None
    if task_id is not None:
        task = db.session.get(Task, task_id)
        if (
            not task
            or (task.created_by != user.id and user.role != User.ROLE_ADMIN)
            or task.student_name != profile.full_name
        ):
            return jsonify({"ok": False, "error": "forbidden_task"}), 403
        if not task.dictation_book_id:
            return jsonify({"ok": False, "error": "task_not_dictation"}), 409

    try:
        grant = create_input_grant(
            user,
            profile,
            duration_days=duration_days,
            task=task,
            reason=data.get("reason"),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    db.session.add(grant)
    db.session.commit()
    return jsonify({"ok": True, "grant": grant_payload(grant)}), 201


@dictation_input_bp.post("/input-grants/<int:grant_id>/revoke")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def revoke_teacher_input_grant(grant_id: int):
    user = request.current_api_user
    grant = db.session.get(DictationInputGrant, grant_id)
    if not grant:
        return jsonify({"ok": False, "error": "grant_not_found"}), 404
    profile = db.session.get(StudentProfile, grant.student_profile_id)
    if not profile or not teacher_can_manage_student(user, profile):
        return jsonify({"ok": False, "error": "forbidden_grant"}), 403
    if grant.teacher_id != user.id and user.role != User.ROLE_ADMIN:
        return jsonify({"ok": False, "error": "forbidden_grant"}), 403
    if not grant.revoked_at:
        grant.revoked_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"ok": True, "grant": grant_payload(grant)})
