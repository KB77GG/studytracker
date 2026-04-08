"""入学英语水平测试 (Entrance Test) API blueprint.

Phase 2: business logic implementation.

设计原则：
- 与现有 studytracker 业务表完全隔离（仅通过 user.id 引用老师）
- 学生不需要登录，靠 invitation token 鉴权
- 客观题（single_choice + short_answer）自动评分
- 主观题（essay）等老师人工录入
"""

import json
import secrets
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from models import (
    db,
    User,
    EntranceTestPaper,
    EntranceTestSection,
    EntranceTestQuestion,
    EntranceTestInvitation,
    EntranceTestAttempt,
    EntranceTestAnswer,
)


entrance_bp = Blueprint("entrance", __name__, url_prefix="/api/entrance")


# ============================================================================
# Helpers
# ============================================================================


def _admin_required():
    """Return None if current_user is teacher/admin, else error tuple."""
    if not current_user.is_authenticated:
        return jsonify({"ok": False, "error": "not_logged_in"}), 401
    if current_user.role not in ("admin", "teacher"):
        return jsonify({"ok": False, "error": "no_permission"}), 403
    return None


def _serialize_paper_for_student(paper):
    """Return paper structure WITHOUT correct answers / reference answers."""
    sections = []
    for section in paper.sections:
        questions = []
        for q in section.questions:
            options = []
            if q.options_json:
                try:
                    options = json.loads(q.options_json)
                except Exception:
                    options = []
            questions.append(
                {
                    "id": q.id,
                    "sequence": q.sequence,
                    "question_type": q.question_type,
                    "stem": q.stem,
                    "options": options,
                    "points": q.points,
                }
            )
        sections.append(
            {
                "id": section.id,
                "section_type": section.section_type,
                "sequence": section.sequence,
                "title": section.title,
                "instructions": section.instructions,
                "audio_url": section.audio_url,
                "passage": section.passage,
                "duration_minutes": section.duration_minutes,
                "questions": questions,
            }
        )
    return {
        "id": paper.id,
        "title": paper.title,
        "exam_type": paper.exam_type,
        "level": paper.level,
        "description": paper.description,
        "sections": sections,
    }


def _serialize_paper_full(paper):
    """For admin/teacher viewing — includes answers."""
    data = _serialize_paper_for_student(paper)
    for section, section_data in zip(paper.sections, data["sections"]):
        for q, q_data in zip(section.questions, section_data["questions"]):
            q_data["correct_answer"] = q.correct_answer
            q_data["reference_answer"] = q.reference_answer
    return data


def _normalize_short_answer(s):
    """Normalize a short answer for comparison: lowercase + strip + collapse spaces."""
    if s is None:
        return ""
    return " ".join(str(s).strip().lower().split())


def _grade_objective_question(question, student_answer):
    """Return (is_correct, points_earned) for one objective question.

    Returns (None, None) for essay (cannot auto-grade).
    """
    if question.question_type == "essay":
        return None, None

    student_norm = _normalize_short_answer(student_answer)
    if not student_norm:
        return False, 0

    if question.question_type == "single_choice":
        # correct_answer is the option key (A/B/C/D)
        correct = _normalize_short_answer(question.correct_answer)
        is_correct = student_norm == correct
    elif question.question_type == "short_answer":
        # correct_answer may contain multiple acceptable answers separated by |
        accepted = [
            _normalize_short_answer(a)
            for a in (question.correct_answer or "").split("|")
            if a.strip()
        ]
        is_correct = student_norm in accepted
    else:
        return None, None

    points = question.points if is_correct else 0
    return is_correct, points


# ============================================================================
# Public endpoints (token-based, for the student taking the test)
# ============================================================================


@entrance_bp.route("/invitation/<token>", methods=["GET"])
def get_invitation(token):
    """Validate token, return student info + paper meta. Marks started_at on first access."""
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404

    # First access → mark started_at
    if not inv.started_at:
        inv.started_at = datetime.utcnow()
        if inv.status == "pending":
            inv.status = "in_progress"
        db.session.commit()

    paper_meta = None
    if inv.paper:
        paper_meta = {
            "id": inv.paper.id,
            "title": inv.paper.title,
            "exam_type": inv.paper.exam_type,
            "level": inv.paper.level,
            "section_count": inv.paper.sections.count(),
        }

    return jsonify(
        {
            "ok": True,
            "invitation": {
                "token": inv.token,
                "student_name": inv.student_name,
                "student_age": inv.student_age,
                "student_grade": inv.student_grade,
                "target_exam": inv.target_exam,
                "has_studied_target": inv.has_studied_target,
                "status": inv.status,
                "started_at": inv.started_at.isoformat() if inv.started_at else None,
                "submitted_at": inv.submitted_at.isoformat() if inv.submitted_at else None,
            },
            "paper": paper_meta,
        }
    )


@entrance_bp.route("/paper/<token>", methods=["GET"])
def get_paper(token):
    """Return the full paper (no answers) for the student to answer."""
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    if inv.status == "submitted" or inv.status == "graded":
        return jsonify({"ok": False, "error": "already_submitted"}), 400
    if not inv.paper:
        return jsonify({"ok": False, "error": "no_paper_assigned"}), 400
    if not inv.paper.is_active:
        return jsonify({"ok": False, "error": "paper_not_active"}), 400

    return jsonify({"ok": True, "paper": _serialize_paper_for_student(inv.paper)})


@entrance_bp.route("/submit/<token>", methods=["POST"])
def submit_answers(token):
    """Receive student answers, auto-grade objective questions, save attempt.

    Body: { "answers": [ { "question_id": int, "answer_text": str }, ... ] }
    """
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    if inv.status in ("submitted", "graded"):
        return jsonify({"ok": False, "error": "already_submitted"}), 400
    if not inv.paper:
        return jsonify({"ok": False, "error": "no_paper_assigned"}), 400

    payload = request.get_json(silent=True) or {}
    submitted_answers = payload.get("answers") or []
    if not isinstance(submitted_answers, list):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    # Build a map: question_id -> answer_text
    answer_map = {}
    for item in submitted_answers:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id")
        ans = item.get("answer_text", "")
        if qid is not None:
            answer_map[int(qid)] = ans

    # Create or get attempt
    attempt = EntranceTestAttempt.query.filter_by(invitation_id=inv.id).first()
    if attempt is None:
        attempt = EntranceTestAttempt(
            invitation_id=inv.id,
            paper_id=inv.paper_id,
            started_at=inv.started_at or datetime.utcnow(),
        )
        db.session.add(attempt)
        db.session.flush()
    else:
        # Re-submit: clear old answers
        EntranceTestAnswer.query.filter_by(attempt_id=attempt.id).delete()

    # Iterate all questions in the paper, grade objective ones
    listening_score = 0
    reading_score = 0
    total_max = 0

    for section in inv.paper.sections:
        for question in section.questions:
            student_text = answer_map.get(question.id, "")
            is_correct, points = _grade_objective_question(question, student_text)

            answer_row = EntranceTestAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                answer_text=student_text,
                is_correct=is_correct,
                points_earned=points,
            )
            db.session.add(answer_row)

            # Accumulate scores by section type (only objective)
            if question.question_type != "essay":
                total_max += question.points or 1
                if is_correct:
                    if section.section_type == "listening":
                        listening_score += question.points or 1
                    elif section.section_type == "reading":
                        reading_score += question.points or 1

    attempt.auto_score_listening = listening_score
    attempt.auto_score_reading = reading_score
    attempt.auto_score_total_max = total_max
    attempt.submitted_at = datetime.utcnow()

    inv.submitted_at = attempt.submitted_at
    inv.status = "submitted"

    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "attempt_id": attempt.id,
            "auto_score": {
                "listening": listening_score,
                "reading": reading_score,
                "total_max": total_max,
            },
            "message": "提交成功，老师将稍后批改写作部分并联系你安排口语测试。",
        }
    )


# ============================================================================
# Admin endpoints (teacher login required)
# ============================================================================


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
                    "description": p.description,
                    "is_active": p.is_active,
                    "section_count": p.sections.count(),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in papers
            ],
        }
    )


@entrance_bp.route("/admin/papers/<int:paper_id>", methods=["GET"])
@login_required
def admin_get_paper(paper_id):
    err = _admin_required()
    if err:
        return err
    paper = EntranceTestPaper.query.get_or_404(paper_id)
    return jsonify({"ok": True, "paper": _serialize_paper_full(paper)})


@entrance_bp.route("/admin/papers/<int:paper_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_paper(paper_id):
    err = _admin_required()
    if err:
        return err
    paper = EntranceTestPaper.query.get_or_404(paper_id)
    paper.is_active = not paper.is_active
    db.session.commit()
    return jsonify({"ok": True, "is_active": paper.is_active})


@entrance_bp.route("/admin/invitations", methods=["GET"])
@login_required
def admin_list_invitations():
    err = _admin_required()
    if err:
        return err
    status_filter = request.args.get("status")
    q = EntranceTestInvitation.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    invs = q.order_by(EntranceTestInvitation.created_at.desc()).limit(200).all()

    result = []
    for i in invs:
        attempt = i.attempt  # 1:1
        result.append(
            {
                "id": i.id,
                "token": i.token,
                "student_name": i.student_name,
                "student_phone": i.student_phone,
                "student_age": i.student_age,
                "student_grade": i.student_grade,
                "target_exam": i.target_exam,
                "has_studied_target": i.has_studied_target,
                "status": i.status,
                "paper_title": i.paper.title if i.paper else None,
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "submitted_at": i.submitted_at.isoformat() if i.submitted_at else None,
                "attempt_id": attempt.id if attempt else None,
            }
        )
    return jsonify({"ok": True, "invitations": result})


@entrance_bp.route("/admin/invitations", methods=["POST"])
@login_required
def admin_create_invitation():
    err = _admin_required()
    if err:
        return err
    data = request.get_json(silent=True) or {}

    student_name = (data.get("student_name") or "").strip()
    if not student_name:
        return jsonify({"ok": False, "error": "missing_student_name"}), 400

    paper_id = data.get("paper_id")
    if paper_id:
        paper = EntranceTestPaper.query.get(int(paper_id))
        if not paper:
            return jsonify({"ok": False, "error": "paper_not_found"}), 404
        if not paper.is_active:
            return jsonify({"ok": False, "error": "paper_not_active"}), 400

    token = secrets.token_urlsafe(24)

    inv = EntranceTestInvitation(
        token=token,
        paper_id=int(paper_id) if paper_id else None,
        student_name=student_name,
        student_phone=(data.get("student_phone") or "").strip() or None,
        student_age=int(data["student_age"]) if data.get("student_age") else None,
        student_grade=(data.get("student_grade") or "").strip() or None,
        has_studied_target=bool(data.get("has_studied_target")),
        target_exam=(data.get("target_exam") or "").strip() or None,
        created_by=current_user.id,
        status="pending",
    )
    db.session.add(inv)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "invitation": {
                "id": inv.id,
                "token": inv.token,
                "student_name": inv.student_name,
                "url_path": f"/entrance/student.html?token={inv.token}",
            },
        }
    )


@entrance_bp.route("/admin/attempts/<int:attempt_id>", methods=["GET"])
@login_required
def admin_get_attempt(attempt_id):
    err = _admin_required()
    if err:
        return err
    attempt = EntranceTestAttempt.query.get_or_404(attempt_id)
    inv = attempt.invitation
    paper = attempt.paper

    # Build sections + questions + student answers
    answers_by_qid = {a.question_id: a for a in attempt.answers}
    sections = []
    for section in paper.sections:
        questions = []
        for q in section.questions:
            options = []
            if q.options_json:
                try:
                    options = json.loads(q.options_json)
                except Exception:
                    options = []
            ans = answers_by_qid.get(q.id)
            questions.append(
                {
                    "id": q.id,
                    "sequence": q.sequence,
                    "question_type": q.question_type,
                    "stem": q.stem,
                    "options": options,
                    "correct_answer": q.correct_answer,
                    "reference_answer": q.reference_answer,
                    "points": q.points,
                    "student_answer": ans.answer_text if ans else None,
                    "is_correct": ans.is_correct if ans else None,
                    "points_earned": ans.points_earned if ans else None,
                }
            )
        sections.append(
            {
                "id": section.id,
                "section_type": section.section_type,
                "sequence": section.sequence,
                "title": section.title,
                "passage": section.passage,
                "audio_url": section.audio_url,
                "questions": questions,
            }
        )

    return jsonify(
        {
            "ok": True,
            "attempt": {
                "id": attempt.id,
                "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
                "submitted_at": attempt.submitted_at.isoformat() if attempt.submitted_at else None,
                "auto_score_listening": attempt.auto_score_listening,
                "auto_score_reading": attempt.auto_score_reading,
                "auto_score_total_max": attempt.auto_score_total_max,
                "writing_score": attempt.writing_score,
                "writing_comment": attempt.writing_comment,
                "speaking_score": attempt.speaking_score,
                "speaking_comment": attempt.speaking_comment,
                "overall_level": attempt.overall_level,
                "overall_comment": attempt.overall_comment,
                "report_pdf_path": attempt.report_pdf_path,
            },
            "invitation": {
                "id": inv.id,
                "student_name": inv.student_name,
                "student_phone": inv.student_phone,
                "student_age": inv.student_age,
                "student_grade": inv.student_grade,
                "target_exam": inv.target_exam,
                "has_studied_target": inv.has_studied_target,
                "status": inv.status,
            },
            "paper": {
                "id": paper.id,
                "title": paper.title,
                "exam_type": paper.exam_type,
                "level": paper.level,
            },
            "sections": sections,
        }
    )


@entrance_bp.route("/admin/attempts/<int:attempt_id>/grade", methods=["POST"])
@login_required
def admin_grade_attempt(attempt_id):
    err = _admin_required()
    if err:
        return err
    attempt = EntranceTestAttempt.query.get_or_404(attempt_id)
    data = request.get_json(silent=True) or {}

    def _to_float(val):
        if val is None or val == "":
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    if "writing_score" in data:
        attempt.writing_score = _to_float(data.get("writing_score"))
    if "writing_comment" in data:
        attempt.writing_comment = (data.get("writing_comment") or "").strip() or None
    if "speaking_score" in data:
        attempt.speaking_score = _to_float(data.get("speaking_score"))
    if "speaking_comment" in data:
        attempt.speaking_comment = (data.get("speaking_comment") or "").strip() or None
    if "overall_level" in data:
        attempt.overall_level = (data.get("overall_level") or "").strip() or None
    if "overall_comment" in data:
        attempt.overall_comment = (data.get("overall_comment") or "").strip() or None

    attempt.reviewer_id = current_user.id
    attempt.reviewed_at = datetime.utcnow()

    if attempt.invitation:
        attempt.invitation.status = "graded"

    db.session.commit()

    return jsonify({"ok": True, "attempt_id": attempt.id})


@entrance_bp.route("/admin/attempts/<int:attempt_id>/report.pdf", methods=["GET"])
@login_required
def admin_report_pdf(attempt_id):
    err = _admin_required()
    if err:
        return err
    # PDF generation will be implemented in Phase 3 alongside the template
    return jsonify(
        {
            "ok": False,
            "error": "not_implemented_yet",
            "message": "PDF 报告生成将在 Phase 3 与前端一起实现",
        }
    ), 501
