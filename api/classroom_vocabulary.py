"""Staff-only classroom vocabulary import; assignments stay in the task drawer."""

from __future__ import annotations

import secrets
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, render_template, request, session
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError

from models import User, db
from services.classroom_vocabulary import (
    MAX_BYTES,
    ClassroomVocabularyError,
    preview_text,
    preview_workbook,
    save_book,
)

classroom_vocabulary_bp = Blueprint("classroom_vocabulary", __name__)


@classroom_vocabulary_bp.before_request
@login_required
def staff_and_csrf():
    if not current_user.is_active or current_user.role not in {
        User.ROLE_ADMIN,
        User.ROLE_TEACHER,
        User.ROLE_ASSISTANT,
    }:
        return jsonify(ok=False, error="forbidden", message="仅教师、助教和管理员可录入词表"), 403
    if request.method == "POST":
        expected = session.get("classroom_vocabulary_csrf")
        actual = request.headers.get("X-CSRF-Token", "")
        if not expected or not secrets.compare_digest(str(expected), actual):
            return jsonify(ok=False, error="csrf", message="页面已过期，请刷新后重试"), 403
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(ok=False, error="csrf", message="请求来源无效"), 403
        if request.content_length and request.content_length > 2 * MAX_BYTES:
            return jsonify(ok=False, error="too_large", message="词表内容过大，请分批录入"), 413


@classroom_vocabulary_bp.errorhandler(ClassroomVocabularyError)
def input_error(error):
    db.session.rollback()
    return (
        jsonify(ok=False, error="invalid_word_list", message=error.message, errors=error.errors),
        error.status,
    )


@classroom_vocabulary_bp.errorhandler(SQLAlchemyError)
def save_error(error):
    db.session.rollback()
    current_app.logger.exception("Classroom vocabulary database operation failed")
    return jsonify(ok=False, error="save_failed", message="词表暂时未能保存，请稍后重试"), 500


@classroom_vocabulary_bp.get("/materials/classroom-vocabulary")
def classroom_vocabulary():
    token = session.setdefault("classroom_vocabulary_csrf", secrets.token_urlsafe(32))
    return render_template("classroom_vocabulary.html", csrf_token=token)


@classroom_vocabulary_bp.post("/api/classroom-vocabulary/preview")
def preview():
    text = request.form.get("text", "")
    file = request.files.get("file")
    if file and text.strip():
        raise ClassroomVocabularyError("请只选择粘贴词表或上传 Excel 中的一种方式")
    result = preview_workbook(file) if file else preview_text(text)
    return jsonify(ok=True, **result)


@classroom_vocabulary_bp.post("/api/classroom-vocabulary/books")
def create_book():
    book, reused = save_book(request.get_json(silent=True), current_user.id)
    return jsonify(
        ok=True,
        book={"id": book.id, "title": book.title, "word_count": book.word_count},
        reused=reused,
        assignment_url=f"/tasks?preset_dictation_book={book.id}",
    )
