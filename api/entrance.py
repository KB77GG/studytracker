"""入学英语水平测试 (Entrance Test) API blueprint.

Phase 1: Skeleton — endpoints return placeholders so we can verify routing
and deployment without breaking any existing studytracker functionality.

Phase 2 will implement actual business logic.
"""

from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from models import (
    db,
    User,
    EntranceTestPaper,
    EntranceTestInvitation,
    EntranceTestAttempt,
)


entrance_bp = Blueprint("entrance", __name__, url_prefix="/api/entrance")


def _admin_required():
    """Return None if current_user is teacher/admin, else error tuple."""
    if not current_user.is_authenticated:
        return jsonify({"ok": False, "error": "not_logged_in"}), 401
    if current_user.role not in ("admin", "teacher"):
        return jsonify({"ok": False, "error": "no_permission"}), 403
    return None


# ---------- Public endpoints (token-based, for the student taking the test) ----------


@entrance_bp.route("/invitation/<token>", methods=["GET"])
def get_invitation(token):
    """Validate token, return student info + paper meta."""
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    return jsonify(
        {
            "ok": True,
            "phase": "skeleton",
            "invitation": {
                "id": inv.id,
                "student_name": inv.student_name,
                "status": inv.status,
            },
        }
    )


@entrance_bp.route("/paper/<token>", methods=["GET"])
def get_paper(token):
    """Return the full paper for the student to answer."""
    return jsonify({"ok": True, "phase": "skeleton", "todo": "fetch paper"})


@entrance_bp.route("/submit/<token>", methods=["POST"])
def submit_answers(token):
    """Receive student answers, auto-grade objective questions."""
    return jsonify({"ok": True, "phase": "skeleton", "todo": "submit answers"})


# ---------- Admin endpoints (teacher login required) ----------


@entrance_bp.route("/admin/papers", methods=["GET"])
@login_required
def admin_list_papers():
    err = _admin_required()
    if err:
        return err
    papers = EntranceTestPaper.query.order_by(EntranceTestPaper.created_at.desc()).all()
    return jsonify(
        {
            "ok": True,
            "papers": [
                {
                    "id": p.id,
                    "title": p.title,
                    "exam_type": p.exam_type,
                    "level": p.level,
                    "is_active": p.is_active,
                }
                for p in papers
            ],
        }
    )


@entrance_bp.route("/admin/invitations", methods=["GET"])
@login_required
def admin_list_invitations():
    err = _admin_required()
    if err:
        return err
    invs = EntranceTestInvitation.query.order_by(
        EntranceTestInvitation.created_at.desc()
    ).limit(200).all()
    return jsonify(
        {
            "ok": True,
            "invitations": [
                {
                    "id": i.id,
                    "token": i.token,
                    "student_name": i.student_name,
                    "target_exam": i.target_exam,
                    "status": i.status,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in invs
            ],
        }
    )


@entrance_bp.route("/admin/invitations", methods=["POST"])
@login_required
def admin_create_invitation():
    err = _admin_required()
    if err:
        return err
    return jsonify({"ok": True, "phase": "skeleton", "todo": "create invitation"})


@entrance_bp.route("/admin/attempts/<int:attempt_id>", methods=["GET"])
@login_required
def admin_get_attempt(attempt_id):
    err = _admin_required()
    if err:
        return err
    return jsonify({"ok": True, "phase": "skeleton", "todo": "fetch attempt detail"})


@entrance_bp.route("/admin/attempts/<int:attempt_id>/grade", methods=["POST"])
@login_required
def admin_grade_attempt(attempt_id):
    err = _admin_required()
    if err:
        return err
    return jsonify({"ok": True, "phase": "skeleton", "todo": "save grading"})


@entrance_bp.route("/admin/attempts/<int:attempt_id>/report.pdf", methods=["GET"])
@login_required
def admin_report_pdf(attempt_id):
    err = _admin_required()
    if err:
        return err
    return jsonify({"ok": True, "phase": "skeleton", "todo": "render PDF"})
