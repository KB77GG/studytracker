"""
Speaking Practice API - Listen & Repeat System
Handles phrase book management and Excel upload for TOEFL speaking practice.
TTS is handled by the existing /api/dictation/tts endpoint.
"""

import os
from functools import wraps
import jwt
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from models import db, User, SpeakingBook, SpeakingPhrase


def require_session_or_bearer(fn):
    """Allow either Flask-Login session or Authorization Bearer token."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated:
            return fn(*args, **kwargs)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            except jwt.PyJWTError:
                return jsonify({"ok": False, "error": "invalid_token"}), 401
            user = User.query.get(int(payload.get("sub", 0)))
            if not user or not user.is_active:
                return jsonify({"ok": False, "error": "forbidden"}), 403
            request.current_api_user = user
            return fn(*args, **kwargs)
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return wrapper


def role_required(*roles):
    from functools import wraps
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"ok": False, "error": "unauthorized"}), 401
            if current_user.role not in roles and current_user.role != User.ROLE_ADMIN:
                return jsonify({"ok": False, "error": "forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


speaking_bp = Blueprint("speaking", __name__, url_prefix="/api/speaking")

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@speaking_bp.route("/books", methods=["GET"])
@require_session_or_bearer
def get_books():
    """Get all speaking books."""
    books = SpeakingBook.query.options(joinedload(SpeakingBook.creator)).filter_by(
        is_deleted=False, is_active=True
    ).order_by(SpeakingBook.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "books": [
            {
                "id": book.id,
                "title": book.title,
                "description": book.description,
                "topic_category": book.topic_category,
                "phrase_count": book.phrase_count,
                "created_at": book.created_at.isoformat() if book.created_at else None,
                "creator": book.creator.display_name or book.creator.username if book.creator else None
            }
            for book in books
        ]
    })


@speaking_bp.route("/books", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def upload_book():
    """Upload Excel file to create a new speaking book.

    Excel columns: sentence/phrase/句子 (required), translation/翻译/中文 (optional)
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "missing_file"}), 400

    file = request.files["file"]
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    topic_category = request.form.get("topic_category", "").strip()

    if file.filename == "":
        return jsonify({"ok": False, "error": "empty_filename"}), 400
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "invalid_extension", "message": "Only .xlsx or .xls files allowed"}), 400
    if not title:
        title = os.path.splitext(file.filename)[0]

    try:
        import pandas as pd
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip().str.lower()

        phrase_col = None
        translation_col = None

        for col in df.columns:
            if col in ['sentence', 'phrase', '句子', '英文', 'english']:
                phrase_col = col
            elif col in ['translation', '翻译', '中文', '释义', 'meaning', 'chinese']:
                translation_col = col

        if not phrase_col:
            return jsonify({
                "ok": False,
                "error": "missing_phrase_column",
                "message": "Excel must have a column named 'sentence', 'phrase', or '句子'"
            }), 400

        book = SpeakingBook(
            title=title,
            description=description,
            topic_category=topic_category or None,
            phrase_count=0,
            created_by=current_user.id
        )
        db.session.add(book)
        db.session.flush()

        phrases_added = 0
        for idx, row in df.iterrows():
            phrase_text = str(row[phrase_col]).strip()
            if not phrase_text or phrase_text == 'nan':
                continue
            translation = str(row[translation_col]).strip() if translation_col and pd.notna(row.get(translation_col)) else None

            phrase = SpeakingPhrase(
                book_id=book.id,
                sequence=phrases_added + 1,
                phrase=phrase_text,
                translation=translation if translation != 'nan' else None
            )
            db.session.add(phrase)
            phrases_added += 1

        book.phrase_count = phrases_added
        db.session.commit()

        return jsonify({
            "ok": True,
            "book": {"id": book.id, "title": book.title, "phrase_count": phrases_added},
            "message": f"Successfully created book with {phrases_added} phrases"
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to upload speaking book")
        return jsonify({"ok": False, "error": "upload_failed", "message": str(e)}), 500


@speaking_bp.route("/books/<int:book_id>", methods=["GET"])
@require_session_or_bearer
def get_book(book_id):
    """Get a specific book with all its phrases."""
    book = SpeakingBook.query.filter_by(id=book_id, is_deleted=False).first_or_404()
    phrases = SpeakingPhrase.query.filter_by(book_id=book_id).order_by(SpeakingPhrase.sequence).all()
    return jsonify({
        "ok": True,
        "book": {
            "id": book.id,
            "title": book.title,
            "description": book.description,
            "topic_category": book.topic_category,
            "phrase_count": book.phrase_count,
            "created_at": book.created_at.isoformat() if book.created_at else None
        },
        "phrases": [
            {
                "id": p.id,
                "sequence": p.sequence,
                "phrase": p.phrase,
                "translation": p.translation
            }
            for p in phrases
        ]
    })


@speaking_bp.route("/books/<int:book_id>", methods=["DELETE"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def delete_book(book_id):
    """Soft delete a speaking book."""
    book = SpeakingBook.query.filter_by(id=book_id, is_deleted=False).first_or_404()
    book.is_deleted = True
    db.session.commit()
    return jsonify({"ok": True})
