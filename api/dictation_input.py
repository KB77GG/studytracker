"""Staff-authorized native input policy for English spelling practice."""

from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request
from flask_login import current_user

from api.auth_utils import require_api_user
from models import DictationInputGrant, StudentProfile, Task, User, db
from services.dictation_input_policy import (
    AUTHORIZED_GRANT_DAYS,
    create_input_grant,
    grant_payload,
    input_policy,
    staff_can_manage_student,
    supersede_active_input_grants,
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
    if not staff_can_manage_student(user, profile):
        return None, ("forbidden_student", 403)
    return profile, None


def _grant_row_payload(grant: DictationInputGrant, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    return grant_payload(grant) | {
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        "teacher_id": grant.teacher_id,
        "active": bool(not grant.revoked_at and grant.expires_at and grant.expires_at > now),
    }


def _list_grants_for_user(user: User, raw_student_profile_id):
    student_profile_id = _int_arg(raw_student_profile_id, "invalid_student_profile_id")
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
    now = datetime.utcnow()
    serialized = [_grant_row_payload(row, now) for row in rows]
    active = next((row for row in serialized if row["active"]), None)
    return jsonify({
        "ok": True,
        "student_profile_id": profile.id,
        "student_name": profile.full_name,
        "student_has_login": bool(profile.user_id),
        "active_grant": active,
        "grants": serialized,
    })


def _create_grant_for_user(user: User, data: dict):
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
        return jsonify({
            "ok": False,
            "error": "invalid_duration_days",
            "allowed": sorted(AUTHORIZED_GRANT_DAYS),
        }), 400

    task_id = _int_arg(data.get("task_id"), "invalid_task_id")
    if isinstance(task_id, str):
        return jsonify({"ok": False, "error": task_id}), 400
    task = None
    if task_id is not None:
        task = db.session.get(Task, task_id)
        if (
            not task
            or (
                task.created_by != user.id
                and user.role not in {User.ROLE_ADMIN, User.ROLE_ASSISTANT}
            )
            or task.student_name != profile.full_name
        ):
            return jsonify({"ok": False, "error": "forbidden_task"}), 403
        if not task.dictation_book_id:
            return jsonify({"ok": False, "error": "task_not_dictation"}), 409

    now = datetime.utcnow()
    try:
        grant = create_input_grant(
            user,
            profile,
            duration_days=duration_days,
            task=task,
            reason=data.get("reason"),
            now=now,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    supersede_active_input_grants(profile, task=task, now=now)
    db.session.add(grant)
    db.session.commit()
    return jsonify({"ok": True, "grant": _grant_row_payload(grant, now)}), 201


def _revoke_grant_for_user(user: User, grant_id: int):
    grant = db.session.get(DictationInputGrant, grant_id)
    if not grant:
        return jsonify({"ok": False, "error": "grant_not_found"}), 404
    profile = db.session.get(StudentProfile, grant.student_profile_id)
    if not profile or not staff_can_manage_student(user, profile):
        return jsonify({"ok": False, "error": "forbidden_grant"}), 403
    if (
        grant.teacher_id != user.id
        and user.role not in {User.ROLE_ADMIN, User.ROLE_ASSISTANT}
    ):
        return jsonify({"ok": False, "error": "forbidden_grant"}), 403
    if not grant.revoked_at:
        grant.revoked_at = datetime.utcnow()
        db.session.commit()
    return jsonify({"ok": True, "grant": _grant_row_payload(grant)})


def require_web_input_staff(fn):
    """JSON auth guard for the cookie-authenticated staff back office."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"ok": False, "error": "login_required"}), 401
        if current_user.role not in {
            User.ROLE_ADMIN,
            User.ROLE_TEACHER,
            User.ROLE_ASSISTANT,
        }:
            return jsonify({"ok": False, "error": "forbidden"}), 403
        return fn(*args, **kwargs)

    return wrapper


@dictation_input_bp.get("/input-grants")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def list_input_grants():
    return _list_grants_for_user(
        request.current_api_user,
        request.args.get("student_profile_id"),
    )


@dictation_input_bp.post("/input-grants")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def create_teacher_input_grant():
    return _create_grant_for_user(
        request.current_api_user,
        request.get_json(silent=True) or {},
    )


@dictation_input_bp.post("/input-grants/<int:grant_id>/revoke")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def revoke_teacher_input_grant(grant_id: int):
    return _revoke_grant_for_user(request.current_api_user, grant_id)


@dictation_input_bp.get("/staff/input-grants")
@require_web_input_staff
def list_staff_input_grants():
    return _list_grants_for_user(current_user, request.args.get("student_profile_id"))


@dictation_input_bp.post("/staff/input-grants")
@require_web_input_staff
def create_staff_input_grant():
    return _create_grant_for_user(current_user, request.get_json(silent=True) or {})


@dictation_input_bp.post("/staff/input-grants/<int:grant_id>/revoke")
@require_web_input_staff
def revoke_staff_input_grant(grant_id: int):
    return _revoke_grant_for_user(current_user, grant_id)
