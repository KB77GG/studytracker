"""Read-only teacher digest and task-assignment warnings for review pilot."""

from flask import Blueprint, jsonify, redirect, render_template, request
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from api.auth_utils import require_api_user
from models import User
from services import vocabulary_error_reporting as reporting

vocabulary_error_reports_bp = Blueprint("vocabulary_error_reports", __name__)


def _web_staff():
    if not getattr(current_user, "is_authenticated", False):
        return jsonify(ok=False, error="unauthorized"), 401
    if not current_user.is_active or current_user.role not in reporting.STAFF_ROLES:
        return jsonify(ok=False, error="forbidden"), 403
    return None


@vocabulary_error_reports_bp.errorhandler(reporting.VocabularyReportError)
def report_error(error):
    return jsonify(ok=False, error=error.code), error.status


@vocabulary_error_reports_bp.errorhandler(SQLAlchemyError)
def report_unavailable(_error):
    # A missing/temporarily locked pilot table must not expose SQL or identities.
    return jsonify(ok=False, error="vocabulary_report_unavailable"), 503


def _weekly(user):
    return reporting.weekly_report(
        user, week=request.args.get("week"), profile_id=request.args.get("profile_id")
    )


def _load(user):
    return reporting.assignment_load(
        user,
        profile_id=request.args.get("profile_id"),
        student_name=request.args.get("student_name"),
    )


@vocabulary_error_reports_bp.get("/teacher/vocabulary-review")
def teacher_weekly_page():
    if not getattr(current_user, "is_authenticated", False):
        return redirect("/login?next=/teacher/vocabulary-review")
    denied = _web_staff()
    if denied:
        return denied
    return render_template("vocabulary_error_report.html", report=_weekly(current_user))


@vocabulary_error_reports_bp.get("/api/teacher/vocabulary-review/weekly")
def teacher_weekly_api():
    denied = _web_staff()
    if denied:
        return denied
    return jsonify(ok=True, **_weekly(current_user))


@vocabulary_error_reports_bp.get("/api/teacher/vocabulary-review/assignment-load")
def teacher_assignment_load_api():
    denied = _web_staff()
    if denied:
        return denied
    return jsonify(ok=True, **_load(current_user))


@vocabulary_error_reports_bp.get("/api/miniprogram/teacher/vocabulary-review/weekly")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def miniprogram_weekly_api():
    return jsonify(ok=True, **_weekly(request.current_api_user))


@vocabulary_error_reports_bp.get("/api/miniprogram/teacher/vocabulary-review/assignment-load")
@require_api_user(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def miniprogram_assignment_load_api():
    return jsonify(ok=True, **_load(request.current_api_user))
