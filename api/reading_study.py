"""Reading Study blueprint: page route + read-only analysis API + expression saves.

Runtime is AI-free: everything here is a plain DB read, except the small
student-scoped expression bookmarks. Keep route functions thin (< 60 lines) and
push logic into ``_helper`` functions per repo convention.
"""

from __future__ import annotations

import re

from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    render_template,
    request,
    session,
)
from flask_login import current_user
from jinja2 import TemplateNotFound
from sqlalchemy.exc import IntegrityError

from api.reading_study_glossary import glossary_payload
from models import (
    ReadingPassageAnalysis,
    StudentProfile,
    StudentSavedExpression,
    User,
    db,
)

reading_study_bp = Blueprint("reading_study", __name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _normalize_expression_text(text: str) -> str:
    """lower + collapse whitespace (matches StudentSavedExpression.normalized_text)."""
    return " ".join(str(text or "").split()).lower()


def _passage_meta(row: ReadingPassageAnalysis) -> dict:
    return {
        "passage_id": row.passage_id,
        "title": row.passage_title,
        "difficulty": row.difficulty,
        "sentence_count": row.sentence_count,
    }


def _passage_sort_key(row: ReadingPassageAnalysis):
    """Order passages by their trailing _p<N> so P1/P2/P3 come out in sequence."""
    match = re.search(r"_p(\d+)$", row.passage_id or "")
    return (int(match.group(1)) if match else 999, row.passage_id or "")


def _ready_passages(test_id: str) -> list[ReadingPassageAnalysis]:
    return ReadingPassageAnalysis.query.filter_by(test_id=test_id, status="ready").all()


def _practice_url(test_id: str, source_kind: str) -> str:
    """Link back to the matching reading practice page (app.py routes)."""
    if source_kind == "reading_jijing":
        return f"/reading/jijing/{test_id}"
    return f"/reading/test/{test_id}"


def _current_student() -> StudentProfile | None:
    """Resolve the practice student identity for Reading Study.

    Thin re-implementation of app.py:_current_practice_student_profile
    (app.py:~1470): a logged-in student account wins; otherwise the public
    practice pages store a verified full name in session. Kept intentionally
    small to avoid importing app.py at request time (would risk a circular
    import / re-loading heavy app state). Note: the staff/classroom guard in the
    original is omitted here because Reading Study only ever needs to know
    whether a *student* identity exists.
    """
    user = current_user
    if getattr(user, "is_authenticated", False) and (
        getattr(user, "role", None) == User.ROLE_STUDENT
    ):
        profile = StudentProfile.query.filter_by(user_id=user.id, is_deleted=False).first()
        if profile:
            return profile
        name = (
            getattr(user, "display_name", None) or getattr(user, "username", None) or ""
        ).strip()
        if name:
            profile = StudentProfile.query.filter_by(full_name=name, is_deleted=False).first()
            if profile:
                return profile
    name = (session.get("practice_student_name") or "").strip()
    if not name:
        return None
    return StudentProfile.query.filter_by(full_name=name, is_deleted=False).first()


def _requested_normalized_text() -> str:
    """DELETE payload: query normalized_text wins, else body text/normalized_text."""
    normalized = (request.args.get("normalized_text") or "").strip().lower()
    if normalized:
        return normalized
    body = request.get_json(silent=True) or {}
    if body.get("normalized_text"):
        return str(body["normalized_text"]).strip().lower()
    return _normalize_expression_text(body.get("text"))


# --------------------------------------------------------------------------- #
# Page route
# --------------------------------------------------------------------------- #
@reading_study_bp.route("/reading/study/<test_id>")
def reading_study_page(test_id: str):
    rows = sorted(_ready_passages(test_id), key=_passage_sort_key)
    if not rows:
        abort(404)
    context = {
        "test_id": test_id,
        "passages": [_passage_meta(row) for row in rows],
        "source_kind": rows[0].source_kind,
        "practice_url": _practice_url(test_id, rows[0].source_kind),
    }
    try:
        return render_template("reading/study.html", **context)
    except TemplateNotFound:
        # 模板 reading/study.html 由 Phase B 创建；此处返回占位数据，
        # 让路由在模板缺失时仍可被联调 / 测试命中。
        return jsonify({"template": "reading/study.html", **context})


# --------------------------------------------------------------------------- #
# Read-only API
# --------------------------------------------------------------------------- #
@reading_study_bp.route("/api/reading-study/catalog")
def reading_study_catalog():
    test_id = (request.args.get("test_id") or "").strip()
    if test_id:
        rows = sorted(_ready_passages(test_id), key=_passage_sort_key)
        return jsonify({"test_id": test_id, "passages": [_passage_meta(row) for row in rows]})

    rows = ReadingPassageAnalysis.query.filter_by(status="ready").all()
    sources: dict[str, list] = {}
    for row in sorted(rows, key=lambda r: (r.source_kind, r.test_id or "", _passage_sort_key(r))):
        meta = _passage_meta(row)
        meta["test_id"] = row.test_id
        sources.setdefault(row.source_kind, []).append(meta)
    return jsonify({"test_id": None, "sources": sources})


@reading_study_bp.route("/api/reading-study/passage/<passage_id>")
def reading_study_passage(passage_id: str):
    row = ReadingPassageAnalysis.query.filter_by(passage_id=passage_id, status="ready").first()
    if row is None:
        abort(404)
    # payload_json 原样返回（已含归一化 concept / label）。
    return Response(row.payload_json, mimetype="application/json")


@reading_study_bp.route("/api/reading-study/glossary")
def reading_study_glossary_view():
    return jsonify(glossary_payload())


# --------------------------------------------------------------------------- #
# Saved expressions (student-scoped)
# --------------------------------------------------------------------------- #
@reading_study_bp.route("/api/reading-study/expressions", methods=["GET"])
def list_expressions():
    student = _current_student()
    if student is None:
        return jsonify({"student": None, "saved": []})
    query = StudentSavedExpression.query.filter_by(student_id=student.id)
    passage_id = (request.args.get("passage_id") or "").strip()
    if passage_id:
        query = query.filter_by(passage_id=passage_id)
    saved = [row.normalized_text for row in query.all()]
    return jsonify({"student": {"id": student.id, "name": student.full_name}, "saved": saved})


@reading_study_bp.route("/api/reading-study/expressions", methods=["POST"])
def save_expression():
    student = _current_student()
    if student is None:
        return jsonify({"error": "need_student"}), 401

    body = request.get_json(silent=True) or {}
    text = str(body.get("text") or "").strip()
    normalized = _normalize_expression_text(text)
    if not normalized:
        return jsonify({"error": "empty_text"}), 400

    existing = StudentSavedExpression.query.filter_by(
        student_id=student.id, normalized_text=normalized
    ).first()
    if existing is not None:
        return jsonify({"saved": True, "normalized_text": normalized})

    record = StudentSavedExpression(
        student_id=student.id,
        text=text[:255],
        normalized_text=normalized[:255],
        meaning_zh=str(body.get("meaning_zh") or "")[:255],
        source_kind=str(body.get("source_kind") or "")[:32],
        passage_id=str(body.get("passage_id") or "")[:64],
        sentence_id=str(body.get("sentence_id") or "")[:16],
    )
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError:
        # Concurrent save hit the unique constraint; treat as already saved.
        db.session.rollback()
    return jsonify({"saved": True, "normalized_text": normalized})


@reading_study_bp.route("/api/reading-study/expressions", methods=["DELETE"])
def delete_expression():
    student = _current_student()
    if student is None:
        return jsonify({"error": "need_student"}), 401

    normalized = _requested_normalized_text()
    if not normalized:
        return jsonify({"error": "empty_text"}), 400

    StudentSavedExpression.query.filter_by(
        student_id=student.id, normalized_text=normalized
    ).delete()
    db.session.commit()
    return jsonify({"saved": False, "normalized_text": normalized})
