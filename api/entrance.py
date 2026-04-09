"""入学英语水平测试 (Entrance Test) API blueprint.

Phase 2: business logic implementation.

设计原则：
- 与现有 studytracker 业务表完全隔离（仅通过 user.id 引用老师）
- 学生不需要登录，靠 invitation token 鉴权
- 客观题（single_choice + short_answer）自动评分
- 主观题（essay）等老师人工录入
"""

import base64
import json
import os
import secrets
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, jsonify, request, current_app, render_template, make_response
from flask_login import login_required, current_user

try:
    from weasyprint import HTML, CSS
except ImportError:  # pragma: no cover
    HTML = None
    CSS = None

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
    if HTML is None:
        return jsonify({"ok": False, "error": "weasyprint_not_installed"}), 500

    attempt = EntranceTestAttempt.query.get_or_404(attempt_id)
    invitation = attempt.invitation
    paper = EntranceTestPaper.query.get(attempt.paper_id)
    if not paper:
        return jsonify({"ok": False, "error": "paper_missing"}), 404

    # Build answer lookup
    answers_by_q = {a.question_id: a for a in attempt.answers}

    sections_data = []
    section_type_labels = {
        "listening": "听力",
        "reading": "阅读",
        "writing": "写作",
    }
    for section in sorted(paper.sections, key=lambda s: s.sequence):
        qs = []
        for q in sorted(section.questions, key=lambda x: x.sequence):
            opts = []
            if q.options_json:
                try:
                    opts = json.loads(q.options_json)
                except Exception:
                    opts = []
            ans = answers_by_q.get(q.id)
            qs.append({
                "stem": q.stem,
                "options": opts,
                "question_type": q.question_type,
                "correct_answer": q.correct_answer,
                "student_answer": ans.answer_text if ans else None,
                "is_correct": ans.is_correct if ans else None,
            })
        sections_data.append({
            "title": section.title,
            "section_type": section.section_type,
            "section_type_label": section_type_labels.get(section.section_type, section.section_type),
            "questions": qs,
        })

    # Embed logo
    logo_base64 = ""
    logo_path = os.path.join(current_app.static_folder, "sagepath_entrance_logo.png")
    try:
        with open(logo_path, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        logo_base64 = ""

    target_exam_label = {
        "ielts": "IELTS 雅思",
        "toefl": "TOEFL 托福",
        "toefl_junior": "TOEFL Junior 小托福",
    }.get(invitation.target_exam or "", invitation.target_exam or "—")

    reviewer_name = None
    if attempt.reviewer_id:
        reviewer = User.query.get(attempt.reviewer_id)
        reviewer_name = reviewer.username if reviewer else None

    html = render_template(
        "entrance_report_pdf.html",
        invitation=invitation,
        attempt=attempt,
        paper=paper,
        sections=sections_data,
        logo_base64=logo_base64,
        target_exam_label=target_exam_label,
        reviewer_name=reviewer_name,
        generated_at=datetime.now(),
    )

    css = CSS(string="""
        @page { size: A4; margin: 16mm; }
        body { font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif; }
    """)
    pdf_bytes = HTML(string=html).write_pdf(stylesheets=[css])

    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    filename = quote(f"入学测试报告_{invitation.student_name or attempt.id}.pdf")
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{filename}"
    return response


# ============================================================================
# Phase 4: Upload + Paper/Section/Question CRUD
# ============================================================================

from werkzeug.utils import secure_filename

_ALLOWED_AUDIO_EXT = {"mp3", "m4a", "wav", "ogg", "aac"}
_ALLOWED_PDF_EXT = {"pdf"}


def _upload_root():
    root = os.path.join(current_app.root_path, "uploads", "entrance")
    os.makedirs(os.path.join(root, "audio"), exist_ok=True)
    os.makedirs(os.path.join(root, "pdf"), exist_ok=True)
    return root


def _ext_ok(filename, allowed):
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in allowed


def _save_upload(file_storage, subdir, allowed_ext):
    if not file_storage or not file_storage.filename:
        return None, "no_file"
    if not _ext_ok(file_storage.filename, allowed_ext):
        return None, "invalid_extension"
    safe = secure_filename(file_storage.filename)
    # Prefix with token to avoid collisions
    unique = f"{secrets.token_urlsafe(8)}_{safe}"
    dest_dir = os.path.join(_upload_root(), subdir)
    full_path = os.path.join(dest_dir, unique)
    file_storage.save(full_path)
    url = f"/uploads/entrance/{subdir}/{unique}"
    return url, None


@entrance_bp.route("/admin/upload/audio", methods=["POST"])
@login_required
def admin_upload_audio():
    err = _admin_required()
    if err:
        return err
    f = request.files.get("file")
    url, e = _save_upload(f, "audio", _ALLOWED_AUDIO_EXT)
    if e:
        return jsonify({"ok": False, "error": e}), 400
    return jsonify({"ok": True, "url": url, "filename": os.path.basename(url)})


@entrance_bp.route("/admin/upload/pdf", methods=["POST"])
@login_required
def admin_upload_pdf():
    """Upload reference PDF for a paper (original test material archive)."""
    err = _admin_required()
    if err:
        return err
    f = request.files.get("file")
    url, e = _save_upload(f, "pdf", _ALLOWED_PDF_EXT)
    if e:
        return jsonify({"ok": False, "error": e}), 400
    return jsonify({"ok": True, "url": url, "filename": os.path.basename(url)})


# ---- Paper CRUD ----


@entrance_bp.route("/admin/papers", methods=["POST"])
@login_required
def admin_create_paper():
    err = _admin_required()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    exam_type = (data.get("exam_type") or "").strip()
    level = (data.get("level") or "").strip()
    if not title or not exam_type:
        return jsonify({"ok": False, "error": "missing_title_or_exam_type"}), 400
    paper = EntranceTestPaper(
        title=title,
        exam_type=exam_type,
        level=level,
        description=(data.get("description") or "").strip(),
        is_active=bool(data.get("is_active", False)),
        created_by=current_user.id,
    )
    db.session.add(paper)
    db.session.commit()
    return jsonify({"ok": True, "paper_id": paper.id})


@entrance_bp.route("/admin/papers/<int:paper_id>", methods=["PATCH"])
@login_required
def admin_update_paper(paper_id):
    err = _admin_required()
    if err:
        return err
    paper = EntranceTestPaper.query.get_or_404(paper_id)
    data = request.get_json(silent=True) or {}
    for field in ("title", "exam_type", "level", "description"):
        if field in data:
            setattr(paper, field, (data.get(field) or "").strip())
    if "is_active" in data:
        paper.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify({"ok": True})


@entrance_bp.route("/admin/papers/<int:paper_id>", methods=["DELETE"])
@login_required
def admin_delete_paper(paper_id):
    err = _admin_required()
    if err:
        return err
    paper = EntranceTestPaper.query.get_or_404(paper_id)
    # Prevent deletion if any invitation/attempt refers to this paper.
    # SQLite FK enforcement is off by default → we check explicitly to avoid orphan rows.
    if EntranceTestInvitation.query.filter_by(paper_id=paper.id).first():
        return jsonify({"ok": False, "error": "paper_has_invitations"}), 400
    if EntranceTestAttempt.query.filter_by(paper_id=paper.id).first():
        return jsonify({"ok": False, "error": "paper_has_attempts"}), 400
    db.session.delete(paper)  # cascades to sections/questions
    db.session.commit()
    return jsonify({"ok": True})


# ---- Section CRUD ----


@entrance_bp.route("/admin/papers/<int:paper_id>/sections", methods=["POST"])
@login_required
def admin_create_section(paper_id):
    err = _admin_required()
    if err:
        return err
    paper = EntranceTestPaper.query.get_or_404(paper_id)
    data = request.get_json(silent=True) or {}
    section_type = (data.get("section_type") or "").strip()
    if section_type not in ("listening", "reading", "writing"):
        return jsonify({"ok": False, "error": "invalid_section_type"}), 400
    next_seq = (paper.sections.count() or 0) + 1
    section = EntranceTestSection(
        paper_id=paper.id,
        section_type=section_type,
        sequence=data.get("sequence", next_seq),
        title=(data.get("title") or "").strip(),
        instructions=(data.get("instructions") or "").strip(),
        audio_url=(data.get("audio_url") or None),
        passage=(data.get("passage") or None),
        duration_minutes=data.get("duration_minutes"),
    )
    db.session.add(section)
    db.session.commit()
    return jsonify({"ok": True, "section_id": section.id})


@entrance_bp.route("/admin/sections/<int:section_id>", methods=["PATCH"])
@login_required
def admin_update_section(section_id):
    err = _admin_required()
    if err:
        return err
    section = EntranceTestSection.query.get_or_404(section_id)
    data = request.get_json(silent=True) or {}
    for field in ("title", "instructions", "audio_url", "passage"):
        if field in data:
            val = data.get(field)
            setattr(section, field, val if val != "" else None)
    if "duration_minutes" in data:
        dm = data.get("duration_minutes")
        section.duration_minutes = int(dm) if dm else None
    if "sequence" in data:
        section.sequence = int(data["sequence"])
    db.session.commit()
    return jsonify({"ok": True})


@entrance_bp.route("/admin/sections/<int:section_id>", methods=["DELETE"])
@login_required
def admin_delete_section(section_id):
    err = _admin_required()
    if err:
        return err
    section = EntranceTestSection.query.get_or_404(section_id)
    db.session.delete(section)
    db.session.commit()
    return jsonify({"ok": True})


# ---- Question CRUD ----


def _question_payload(data, question=None):
    q = question or EntranceTestQuestion()
    q.question_type = data.get("question_type", q.question_type or "single_choice")
    q.stem = (data.get("stem") or "").strip()
    opts = data.get("options")
    if opts is not None:
        # opts: list of {key, text}
        q.options_json = json.dumps(opts, ensure_ascii=False) if opts else None
    q.correct_answer = (data.get("correct_answer") or "").strip() or None
    q.reference_answer = (data.get("reference_answer") or "").strip() or None
    try:
        q.points = int(data.get("points") or 1)
    except (TypeError, ValueError):
        q.points = 1
    return q


@entrance_bp.route("/admin/sections/<int:section_id>/questions", methods=["POST"])
@login_required
def admin_create_question(section_id):
    err = _admin_required()
    if err:
        return err
    section = EntranceTestSection.query.get_or_404(section_id)
    data = request.get_json(silent=True) or {}
    q = _question_payload(data)
    q.section_id = section.id
    q.sequence = data.get("sequence") or ((section.questions.count() or 0) + 1)
    db.session.add(q)
    db.session.commit()
    return jsonify({"ok": True, "question_id": q.id})


@entrance_bp.route("/admin/questions/<int:question_id>", methods=["PATCH"])
@login_required
def admin_update_question(question_id):
    err = _admin_required()
    if err:
        return err
    q = EntranceTestQuestion.query.get_or_404(question_id)
    data = request.get_json(silent=True) or {}
    _question_payload(data, q)
    if "sequence" in data:
        q.sequence = int(data["sequence"])
    db.session.commit()
    return jsonify({"ok": True})


@entrance_bp.route("/admin/questions/<int:question_id>", methods=["DELETE"])
@login_required
def admin_delete_question(question_id):
    err = _admin_required()
    if err:
        return err
    q = EntranceTestQuestion.query.get_or_404(question_id)
    db.session.delete(q)
    db.session.commit()
    return jsonify({"ok": True})
