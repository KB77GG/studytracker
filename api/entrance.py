"""入学英语水平测试 (Entrance Test) API blueprint.

Phase 2: business logic implementation.

设计原则：
- 与现有 studytracker 业务表完全隔离（仅通过 user.id 引用老师）
- 学生不需要登录，靠 invitation token 鉴权
- 客观题（single_choice + short_answer）自动评分
- 主观题（essay）等老师人工录入
"""

import base64
import html
import json
import os
import re
import secrets
from datetime import datetime
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, make_response, render_template, request
from flask_login import current_user, login_required

try:
    from weasyprint import CSS, HTML
except ImportError:  # pragma: no cover
    HTML = None
    CSS = None

from api.entrance_session import (
    EntranceSessionError,
    draft_answer_map,
    mark_audio_started,
    mark_heartbeat,
    mark_hidden,
    mark_visible,
    normalize_answer_map,
    paper_duration_minutes,
    save_answers,
    serialize_draft,
    start_or_resume,
    unlock_session,
    validate_active_session,
)
from models import (
    EntranceTestAnswer,
    EntranceTestAttempt,
    EntranceTestDraft,
    EntranceTestInvitation,
    EntranceTestPaper,
    EntranceTestQuestion,
    EntranceTestSection,
    User,
    db,
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


def _option_text_starts_with_key(text, key):
    return bool(re.match(rf"^\s*{re.escape(str(key or '').upper())}\s*[\.\uFF0E、)]\s*", str(text or ""), flags=re.IGNORECASE))


def _split_inline_options(value):
    text = html.unescape(str(value or ""))
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    marker = re.compile(r"(?<![A-Za-z])([A-Z])\s*[\.\uFF0E、)]\s*")
    matches = list(marker.finditer(text))
    if len(matches) < 2:
        return []

    options = []
    seen = set()
    for index, match in enumerate(matches):
        key = match.group(1).upper()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        option_text = text[start:end].strip(" \t\r\n;；")
        if not option_text or key in seen:
            continue
        seen.add(key)
        options.append({"key": key, "text": option_text})
    return options if len(options) >= 2 else []


def _extract_inline_options_from_stem(stem):
    text = str(stem or "").strip()
    match = re.search(r"(?<![A-Za-z])A\s*[\.\uFF0E、)]\s*", text)
    if not match:
        return text, []

    options = _split_inline_options(text[match.start():])
    if len(options) < 2:
        return text, []

    clean_stem = text[:match.start()].strip()
    return clean_stem or text, options


def _normalize_question_options(raw_options):
    rows = []
    for opt in raw_options or []:
        key = str((opt or {}).get("key") or (opt or {}).get("title") or "").strip().upper()
        text = str((opt or {}).get("text") or (opt or {}).get("content") or "").strip()
        # Keep letter-only options (text 为空) so 配对题/地图标注题（答案只是 A-H 字母）
        # 能渲染出可选项；前端 formatOptionLabel 对空 text 会只显示字母。
        if key:
            rows.append({"key": key, "text": text})

    if rows:
        combined_parts = []
        for row in rows:
            if _option_text_starts_with_key(row["text"], row["key"]):
                combined_parts.append(row["text"])
            else:
                combined_parts.append(f"{row['key']}. {row['text']}")
        parsed = _split_inline_options(" ".join(combined_parts))
        parsed_keys = [opt["key"] for opt in parsed]
        row_keys = [row["key"] for row in rows]
        if len(parsed) > len(rows) or (parsed and parsed_keys == row_keys):
            return parsed

    return rows


def _load_question_options(question):
    if not question.options_json:
        return []
    try:
        options = json.loads(question.options_json)
    except Exception:
        return []
    return options if isinstance(options, list) else []


def _normalize_stem_and_options(stem, raw_options):
    options = _normalize_question_options(raw_options)
    clean_stem, inline_options = _extract_inline_options_from_stem(stem)
    if inline_options:
        inline_keys = [opt["key"] for opt in inline_options]
        option_keys = [opt["key"] for opt in options]
        if not options:
            return clean_stem, inline_options
        if inline_keys == option_keys:
            return clean_stem, options
    return str(stem or "").strip(), options


def _display_stem_and_options(question):
    if question.question_type != "single_choice":
        return str(question.stem or "").strip(), []
    return _normalize_stem_and_options(question.stem, _load_question_options(question))


def _serialize_paper_for_student(paper):
    """Return paper structure WITHOUT correct answers / reference answers."""
    sections = []
    for section in paper.sections:
        questions = []
        for q in section.questions:
            stem, options = _display_stem_and_options(q)
            questions.append(
                {
                    "id": q.id,
                    "sequence": q.sequence,
                    "question_type": q.question_type,
                    "stem": stem,
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
    for section, section_data in zip(paper.sections, data["sections"], strict=True):
        for q, q_data in zip(
            section.questions,
            section_data["questions"],
            strict=True,
        ):
            q_data["correct_answer"] = q.correct_answer
            q_data["reference_answer"] = q.reference_answer
    return data


def _normalize_short_answer(s):
    """Normalize a short answer for comparison: lowercase + strip + collapse spaces.

    首尾标点/货币符号一并去掉（手机输入法常自动补句号；£115 与 115 视为等价）。
    学生答案与标准答案走同一函数，两侧对称。
    """
    if s is None:
        return ""
    text = " ".join(str(s).strip().lower().split())
    return text.strip(_ANSWER_EDGE_CHARS)


_ANSWER_EDGE_CHARS = (
    " \t\r\n"
    "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    "。，、；：！？·【】（）《》—…￡£€¥“”‘’＂＇．"
)


def _pdf_image_data_uri(url_path):
    """Convert a stem [image:/static/...] path into a base64 data URI for WeasyPrint.

    仅允许 static/uploads 目录下的真实文件，防止路径穿越。
    """
    rel = str(url_path or "").strip().lstrip("/")
    if not (rel.startswith("static/") or rel.startswith("uploads/")):
        return None
    root = os.path.realpath(current_app.root_path)
    full = os.path.realpath(os.path.join(root, rel))
    if not full.startswith(root + os.sep) or not os.path.isfile(full):
        return None
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(full.rsplit(".", 1)[-1].lower())
    if not mime:
        return None
    try:
        with open(full, "rb") as f:
            return f"data:{mime};base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return None


def _stem_parts_for_pdf(stem):
    """Split a stem into text lines and embedded images for the PDF template."""
    parts = []
    for line in str(stem or "").splitlines():
        match = re.match(r"^\[image:(.+)\]$", line.strip())
        if match:
            data_uri = _pdf_image_data_uri(match.group(1))
            if data_uri:
                parts.append({"type": "image", "value": data_uri})
            continue
        parts.append({"type": "text", "value": line})
    return parts


def _objective_section_maxes(paper):
    """Return (listening_max, reading_max) — sum of objective question points."""
    listening_max = 0
    reading_max = 0
    for section in paper.sections:
        for q in section.questions:
            if q.question_type == "essay":
                continue
            if section.section_type == "listening":
                listening_max += q.points or 1
            elif section.section_type == "reading":
                reading_max += q.points or 1
    return listening_max, reading_max


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


def _request_device_id(payload=None):
    payload = payload if isinstance(payload, dict) else {}
    return (request.headers.get("X-Entrance-Device") or payload.get("device_id") or "").strip()


def _session_error_response(error):
    # Device-change and interruption locks are state changes and must survive
    # the rejected request so a teacher can review/unlock them.
    db.session.commit()
    return jsonify({"ok": False, "error": error.code}), error.status_code


def _paper_question_ids(paper):
    return {
        question.id
        for section in paper.sections
        for question in section.questions
    }


def _finalize_attempt(invitation, answer_map, submitted_at=None):
    """Persist and grade a final answer map. Caller commits the transaction."""
    submitted_at = submitted_at or datetime.utcnow()
    attempt = EntranceTestAttempt.query.filter_by(invitation_id=invitation.id).first()
    if attempt is None:
        attempt = EntranceTestAttempt(
            invitation_id=invitation.id,
            paper_id=invitation.paper_id,
            started_at=invitation.started_at or submitted_at,
        )
        db.session.add(attempt)
        db.session.flush()
    else:
        EntranceTestAnswer.query.filter_by(attempt_id=attempt.id).delete()

    listening_score = 0
    reading_score = 0
    total_max = 0
    for section in invitation.paper.sections:
        for question in section.questions:
            student_text = answer_map.get(question.id, "")
            is_correct, points = _grade_objective_question(question, student_text)
            db.session.add(
                EntranceTestAnswer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    answer_text=student_text,
                    is_correct=is_correct,
                    points_earned=points,
                )
            )
            if question.question_type == "essay":
                continue
            total_max += question.points or 1
            if not is_correct:
                continue
            if section.section_type == "listening":
                listening_score += question.points or 1
            elif section.section_type == "reading":
                reading_score += question.points or 1

    attempt.auto_score_listening = listening_score
    attempt.auto_score_reading = reading_score
    attempt.auto_score_total_max = total_max
    attempt.submitted_at = submitted_at
    invitation.submitted_at = submitted_at
    invitation.status = "submitted"
    if invitation.draft:
        invitation.draft.hidden_at = None
        invitation.draft.last_seen_at = submitted_at
    return attempt, {
        "listening": listening_score,
        "reading": reading_score,
        "total_max": total_max,
    }


def _finalize_expired_draft(invitation, raw_answers=None):
    answer_map = draft_answer_map(invitation.draft)
    if raw_answers is not None:
        normalized = normalize_answer_map(raw_answers, _paper_question_ids(invitation.paper))
        answer_map.update({int(key): value for key, value in normalized.items()})
    attempt, scores = _finalize_attempt(invitation, answer_map)
    db.session.commit()
    return jsonify(
        {
            "ok": False,
            "error": "time_expired",
            "attempt_id": attempt.id,
            "auto_score": scores,
        }
    ), 409


# ============================================================================
# Public endpoints (token-based, for the student taking the test)
# ============================================================================


@entrance_bp.route("/invitation/<token>", methods=["GET"])
def get_invitation(token):
    """Validate token and return metadata without starting the timer."""
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404

    paper_meta = None
    if inv.paper:
        paper_meta = {
            "id": inv.paper.id,
            "title": inv.paper.title,
            "exam_type": inv.paper.exam_type,
            "level": inv.paper.level,
            "section_count": inv.paper.sections.count(),
            "duration_minutes": paper_duration_minutes(inv.paper),
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


@entrance_bp.route("/session/<token>/start", methods=["POST"])
def start_entrance_session(token):
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    if inv.status in ("submitted", "graded"):
        return jsonify({"ok": False, "error": "already_submitted"}), 400
    if not inv.paper:
        return jsonify({"ok": False, "error": "no_paper_assigned"}), 400
    if not inv.paper.is_active:
        return jsonify({"ok": False, "error": "paper_not_active"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        draft = start_or_resume(inv, _request_device_id(payload))
    except EntranceSessionError as error:
        if error.code == "time_expired" and inv.draft:
            return _finalize_expired_draft(inv)
        return _session_error_response(error)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "paper": _serialize_paper_for_student(inv.paper),
            "session": serialize_draft(draft),
        }
    )


@entrance_bp.route("/paper/<token>", methods=["GET"])
def get_paper(token):
    """Return paper + saved draft for an already-started valid session."""
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    if inv.status == "submitted" or inv.status == "graded":
        return jsonify({"ok": False, "error": "already_submitted"}), 400
    if not inv.paper:
        return jsonify({"ok": False, "error": "no_paper_assigned"}), 400
    if not inv.paper.is_active:
        return jsonify({"ok": False, "error": "paper_not_active"}), 400
    try:
        draft = validate_active_session(inv, _request_device_id())
    except EntranceSessionError as error:
        if error.code == "time_expired" and inv.draft:
            return _finalize_expired_draft(inv)
        return _session_error_response(error)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "paper": _serialize_paper_for_student(inv.paper),
            "session": serialize_draft(draft),
        }
    )


@entrance_bp.route("/session/<token>/save", methods=["POST"])
def save_entrance_draft(token):
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    if inv.status in ("submitted", "graded"):
        return jsonify({"ok": False, "error": "already_submitted"}), 400
    if not inv.paper:
        return jsonify({"ok": False, "error": "no_paper_assigned"}), 400

    payload = request.get_json(silent=True) or {}
    try:
        draft = save_answers(
            inv,
            _request_device_id(payload),
            payload.get("answers"),
        )
    except EntranceSessionError as error:
        if error.code == "time_expired" and inv.draft:
            return _finalize_expired_draft(inv, payload.get("answers"))
        return _session_error_response(error)
    db.session.commit()
    return jsonify({"ok": True, "session": serialize_draft(draft)})


@entrance_bp.route("/session/<token>/event", methods=["POST"])
def entrance_session_event(token):
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    if inv.status in ("submitted", "graded"):
        return jsonify({"ok": True, "submitted": True})

    payload = request.get_json(silent=True) or {}
    event_type = (payload.get("event") or "").strip().lower()
    try:
        if event_type == "hidden":
            draft = mark_hidden(inv, _request_device_id(payload))
        elif event_type == "visible":
            draft = mark_visible(inv, _request_device_id(payload))
        elif event_type == "heartbeat":
            draft = mark_heartbeat(inv, _request_device_id(payload))
        else:
            return jsonify({"ok": False, "error": "invalid_event"}), 400
    except EntranceSessionError as error:
        if error.code == "time_expired" and inv.draft:
            return _finalize_expired_draft(inv, payload.get("answers"))
        return _session_error_response(error)
    db.session.commit()
    return jsonify({"ok": True, "session": serialize_draft(draft)})


@entrance_bp.route("/session/<token>/audio/<int:section_id>/start", methods=["POST"])
def start_entrance_audio(token, section_id):
    inv = EntranceTestInvitation.query.filter_by(token=token).first()
    if not inv:
        return jsonify({"ok": False, "error": "invitation_not_found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        draft, started = mark_audio_started(
            inv,
            _request_device_id(payload),
            section_id,
        )
    except EntranceSessionError as error:
        if error.code == "time_expired" and inv.draft:
            return _finalize_expired_draft(inv, payload.get("answers"))
        return _session_error_response(error)
    db.session.commit()
    if not started:
        return jsonify({"ok": False, "error": "audio_already_started"}), 409
    return jsonify({"ok": True, "session": serialize_draft(draft)})


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
    try:
        draft = validate_active_session(inv, _request_device_id(payload))
        submitted_map = normalize_answer_map(
            payload.get("answers") or [],
            _paper_question_ids(inv.paper),
        )
    except EntranceSessionError as error:
        if error.code == "time_expired" and inv.draft:
            return _finalize_expired_draft(inv, payload.get("answers"))
        return _session_error_response(error)

    answer_map = draft_answer_map(draft)
    answer_map.update({int(key): value for key, value in submitted_map.items()})
    attempt, scores = _finalize_attempt(inv, answer_map)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "attempt_id": attempt.id,
            "auto_score": scores,
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
        draft = i.draft
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
                "session": {
                    "last_saved_at": (
                        draft.last_saved_at.isoformat() if draft and draft.last_saved_at else None
                    ),
                    "deadline_at": (
                        draft.deadline_at.isoformat() if draft and draft.deadline_at else None
                    ),
                    "exit_count": draft.exit_count if draft else 0,
                    "total_hidden_seconds": draft.total_hidden_seconds if draft else 0,
                    "device_switch_count": draft.device_switch_count if draft else 0,
                    "is_locked": bool(draft and draft.is_locked),
                    "locked_reason": draft.locked_reason if draft else None,
                    "unlock_count": draft.unlock_count if draft else 0,
                },
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


@entrance_bp.route("/admin/invitations/<int:invitation_id>/unlock", methods=["POST"])
@login_required
def admin_unlock_invitation(invitation_id):
    err = _admin_required()
    if err:
        return err
    inv = EntranceTestInvitation.query.get_or_404(invitation_id)
    draft = EntranceTestDraft.query.filter_by(invitation_id=inv.id).first()
    if not draft:
        return jsonify({"ok": False, "error": "draft_not_found"}), 404
    if inv.status in ("submitted", "graded"):
        return jsonify({"ok": False, "error": "already_submitted"}), 400

    data = request.get_json(silent=True) or {}
    try:
        extra_minutes = int(data.get("extra_minutes") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_extra_minutes"}), 400
    unlock_session(
        draft,
        reviewer_id=current_user.id,
        extra_minutes=extra_minutes,
        reset_device=data.get("reset_device", True) is not False,
    )
    if data.get("reset_audio"):
        draft.audio_state_json = "{}"
    db.session.commit()
    return jsonify({"ok": True, "session": serialize_draft(draft)})


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
            stem, options = _display_stem_and_options(q)
            ans = answers_by_qid.get(q.id)
            questions.append(
                {
                    "id": q.id,
                    "sequence": q.sequence,
                    "question_type": q.question_type,
                    "stem": stem,
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
            stem, opts = _display_stem_and_options(q)
            ans = answers_by_q.get(q.id)
            qs.append({
                "stem": stem,
                "stem_parts": _stem_parts_for_pdf(stem),
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

    listening_max, reading_max = _objective_section_maxes(paper)

    html = render_template(
        "entrance_report_pdf.html",
        invitation=invitation,
        attempt=attempt,
        paper=paper,
        sections=sections_data,
        listening_max=listening_max,
        reading_max=reading_max,
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
    stem = (data.get("stem") or "").strip()
    opts = data.get("options")
    if opts is not None and q.question_type == "single_choice":
        stem, opts = _normalize_stem_and_options(stem, opts)
    q.stem = stem
    if opts is not None:
        q.options_json = json.dumps(opts, ensure_ascii=False) if q.question_type == "single_choice" and opts else None
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
