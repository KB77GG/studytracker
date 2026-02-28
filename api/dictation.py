"""
Dictation API - Listening Practice System
Handles word book management, Excel upload, TTS generation, and practice records.
"""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from functools import wraps
import jwt
import requests
from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from sqlalchemy.orm import joinedload
from models import db, User, DictationBook, DictationWord, DictationRecord, Task


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
                payload = jwt.decode(
                    token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
                )
            except jwt.PyJWTError:
                return jsonify({"ok": False, "error": "invalid_token"}), 401

            user = User.query.get(int(payload.get("sub", 0)))
            if not user or not user.is_active:
                return jsonify({"ok": False, "error": "forbidden"}), 403

            request.current_api_user = user
            return fn(*args, **kwargs)

        return jsonify({"ok": False, "error": "unauthorized"}), 401

    return wrapper

dictation_bp = Blueprint("dictation", __name__, url_prefix="/api/dictation")

# Allowed Excel extensions
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def role_required(*roles):
    """Require current user to have one of the roles (admins bypass)."""
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


# ============================================================================
# Book Management APIs
# ============================================================================

@dictation_bp.route("/books", methods=["GET"])
@require_session_or_bearer
def get_books():
    """Get all dictation books."""
    books = DictationBook.query.options(joinedload(DictationBook.creator)).filter_by(is_deleted=False, is_active=True).order_by(DictationBook.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "books": [
            {
                "id": book.id,
                "title": book.title,
                "description": book.description,
                "word_count": book.word_count,
                "created_at": book.created_at.isoformat() if book.created_at else None,
                "creator": book.creator.display_name or book.creator.username if book.creator else None
            }
            for book in books
        ]
    })


@dictation_bp.route("/books", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def upload_book():
    """Upload Excel file to create a new dictation book.
    
    Note: Audio is NOT generated during upload to avoid timeout issues.
    The Mini Program will use its built-in TTS to speak words.
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "missing_file"}), 400
    
    file = request.files["file"]
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    
    if file.filename == "":
        return jsonify({"ok": False, "error": "empty_filename"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"ok": False, "error": "invalid_extension", "message": "Only .xlsx or .xls files allowed"}), 400
    
    if not title:
        # Use filename as title if not provided
        title = os.path.splitext(file.filename)[0]
    
    try:
        import pandas as pd
        
        # Read Excel file
        df = pd.read_excel(file)
        
        # Normalize column names (handle different naming conventions)
        df.columns = df.columns.str.strip().str.lower()
        
        # Map possible column names
        word_col = None
        phonetic_col = None
        translation_col = None
        
        for col in df.columns:
            if col in ['单词', 'word', 'words', '词汇']:
                word_col = col
            elif col in ['音标', 'phonetic', 'ipa', 'pronunciation']:
                phonetic_col = col
            elif col in ['释义', 'translation', 'meaning', '翻译', '中文']:
                translation_col = col
        
        if not word_col:
            return jsonify({
                "ok": False, 
                "error": "missing_word_column",
                "message": "Excel must have a column named '单词' or 'word'"
            }), 400
        
        # Create book
        book = DictationBook(
            title=title,
            description=description,
            word_count=len(df),
            created_by=current_user.id
        )
        db.session.add(book)
        db.session.flush()  # Get book.id
        
        # Process each word (NO audio generation - Mini Program will use built-in TTS)
        words_added = 0
        for idx, row in df.iterrows():
            word_text = str(row[word_col]).strip()
            if not word_text or word_text == 'nan':
                continue
            
            phonetic = str(row[phonetic_col]).strip() if phonetic_col and pd.notna(row.get(phonetic_col)) else None
            translation = str(row[translation_col]).strip() if translation_col and pd.notna(row.get(translation_col)) else None
            
            # Create word entry (no audio paths - using Mini Program TTS)
            word = DictationWord(
                book_id=book.id,
                sequence=words_added + 1,
                word=word_text,
                phonetic=phonetic if phonetic != 'nan' else None,
                translation=translation if translation != 'nan' else None,
                audio_us=None,  # Will use Mini Program TTS
                audio_uk=None   # Will use Mini Program TTS
            )
            db.session.add(word)
            words_added += 1
        
        book.word_count = words_added
        db.session.commit()
        
        return jsonify({
            "ok": True,
            "book": {
                "id": book.id,
                "title": book.title,
                "word_count": words_added
            },
            "message": f"Successfully created book with {words_added} words"
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Failed to upload dictation book")
        return jsonify({"ok": False, "error": "upload_failed", "message": str(e)}), 500


@dictation_bp.route("/books/<int:book_id>", methods=["GET"])
@require_session_or_bearer
def get_book(book_id):
    """Get a specific book with its words."""
    book = DictationBook.query.filter_by(id=book_id, is_deleted=False).first_or_404()
    words = DictationWord.query.filter_by(book_id=book_id).order_by(DictationWord.sequence).all()
    
    return jsonify({
        "ok": True,
        "book": {
            "id": book.id,
            "title": book.title,
            "description": book.description,
            "word_count": book.word_count,
            "created_at": book.created_at.isoformat() if book.created_at else None
        },
        "words": [
            {
                "id": w.id,
                "sequence": w.sequence,
                "word": w.word,
                "phonetic": w.phonetic,
                "translation": w.translation,
                "audio_us": w.audio_us,
                "audio_uk": w.audio_uk
            }
            for w in words
        ]
    })


@dictation_bp.route("/books/<int:book_id>", methods=["DELETE"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def delete_book(book_id):
    """Soft delete a dictation book."""
    book = DictationBook.query.filter_by(id=book_id, is_deleted=False).first_or_404()
    book.is_deleted = True
    db.session.commit()
    return jsonify({"ok": True})


# ============================================================================
# Audio APIs
# ============================================================================

@dictation_bp.route("/words/<int:word_id>/audio", methods=["GET"])
@require_session_or_bearer
def get_word_audio(word_id):
    """Get audio file for a word. Use ?accent=uk for British, default is American."""
    word = DictationWord.query.get_or_404(word_id)
    accent = request.args.get("accent", "us").lower()
    
    audio_path = word.audio_uk if accent == "uk" else word.audio_us
    
    if not audio_path:
        return jsonify({"ok": False, "error": "audio_not_found"}), 404
    
    full_path = os.path.join(current_app.root_path, audio_path)
    if not os.path.exists(full_path):
        return jsonify({"ok": False, "error": "audio_file_missing"}), 404
    
    return send_file(full_path, mimetype="audio/mpeg")


# ============================================================================
# TTS proxy & cache for mini-program playback
# Primary: Aliyun DashScope (neural TTS, accurate for all word forms)
# Fallback: Youdao dictvoice (fast but unreliable for inflected forms)
# ============================================================================

def _dashscope_tts(text: str) -> bytes | None:
    """Primary TTS using Aliyun DashScope (neural model, handles plurals/tenses)."""
    api_key = current_app.config.get("ALIYUN_API_KEY")
    if not api_key:
        return None

    model = current_app.config.get("ALIYUN_TTS_MODEL", "qwen3-tts-flash")
    voice = current_app.config.get("ALIYUN_TTS_VOICE", "Cherry")
    language_type = current_app.config.get("ALIYUN_TTS_LANGUAGE", "English")
    region = (current_app.config.get("ALIYUN_ASR_REGION") or "cn-beijing").lower()
    host = current_app.config.get("ALIYUN_ASR_HOST")
    if host:
        host = host.replace("https://", "").replace("http://", "").strip("/")
    else:
        host = "dashscope.aliyuncs.com" if region.startswith("cn") else "dashscope-intl.aliyuncs.com"

    url = f"https://{host}/api/v1/services/aigc/multimodal-generation/generation"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
            "language_type": language_type
        },
        "parameters": {
            "format": "mp3"
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code != 200:
            current_app.logger.warning("DashScope TTS failed %s: %s", text, resp.status_code)
            return None
        data = resp.json()
        audio_url = data.get("output", {}).get("audio", {}).get("url")
        if not audio_url:
            return None
        audio_resp = requests.get(audio_url, timeout=15)
        if audio_resp.status_code == 200 and audio_resp.content:
            raw = audio_resp.content
            # Convert WAV → MP3 via ffmpeg for smaller file size
            return _wav_to_mp3(raw) or raw
    except Exception as exc:
        current_app.logger.warning("DashScope TTS error for %s: %s", text, exc)

    return None


def _wav_to_mp3(raw_audio: bytes) -> bytes | None:
    """Convert WAV/PCM audio bytes to MP3 using ffmpeg. Returns None on failure."""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
            tmp_in.write(raw_audio)
            tmp_in_path = tmp_in.name
        tmp_out_path = tmp_in_path.replace(".wav", ".mp3")
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path, "-codec:a", "libmp3lame",
             "-b:a", "64k", "-ar", "48000", "-ac", "1", tmp_out_path],
            capture_output=True, timeout=10
        )
        if result.returncode == 0 and os.path.exists(tmp_out_path):
            mp3_bytes = Path(tmp_out_path).read_bytes()
            return mp3_bytes if mp3_bytes else None
    except Exception:
        return None
    finally:
        for p in (tmp_in_path, tmp_out_path):
            try:
                os.unlink(p)
            except OSError:
                pass
    return None


def _youdao_tts(text: str) -> bytes | None:
    """Fallback TTS using Youdao dictvoice (fast but dictionary-based)."""
    url = f"https://dict.youdao.com/dictvoice?audio={requests.utils.quote(text)}&type=2"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and resp.content:
            return resp.content
        current_app.logger.warning("Youdao TTS fetch failed %s: %s", text, resp.status_code)
    except Exception as exc:
        current_app.logger.warning("Youdao TTS proxy error for %s: %s", text, exc)
    return None


@dictation_bp.route("/tts", methods=["GET"])
def proxy_tts():
    """Proxy TTS audio with file cache. Aliyun primary, Youdao fallback."""
    word = (request.args.get("word") or "").strip()
    if not word:
        return jsonify({"ok": False, "error": "missing_word"}), 400

    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", word.lower()) or "tts"
    tts_dir = Path(current_app.config.get("UPLOAD_FOLDER", Path(current_app.root_path) / "uploads")) / "tts_cache"
    tts_dir.mkdir(parents=True, exist_ok=True)
    cache_path = tts_dir / f"{safe_name}.mp3"

    if cache_path.exists():
        try:
            return send_file(cache_path, mimetype="audio/mpeg")
        except Exception:
            cache_path.unlink(missing_ok=True)

    # Primary: Aliyun DashScope (neural TTS — correct for plurals, tenses, etc.)
    audio = _dashscope_tts(word)
    if audio:
        cache_path.write_bytes(audio)
        return send_file(cache_path, mimetype="audio/mpeg")

    # Fallback: Youdao dictvoice (dictionary pronunciation lookup)
    audio = _youdao_tts(word)
    if audio:
        cache_path.write_bytes(audio)
        return send_file(cache_path, mimetype="audio/mpeg")

    return jsonify({"ok": False, "error": "tts_fetch_failed"}), 502


# ============================================================================
# Practice APIs (for Mini Program)
# ============================================================================

@dictation_bp.route("/submit", methods=["POST"])
@login_required
def submit_answer():
    """Submit a dictation answer and check if correct."""
    data = request.get_json() or {}
    word_id = data.get("word_id")
    student_answer = (data.get("answer") or "").strip().lower()
    book_id = data.get("book_id")
    task_id = data.get("task_id")
    
    if not word_id or not student_answer:
        return jsonify({"ok": False, "error": "missing_params"}), 400
    
    word = DictationWord.query.get_or_404(word_id)
    correct_answer = word.word.lower().strip()
    
    # Check correctness (exact match for now, can add fuzzy matching later)
    is_correct = student_answer == correct_answer
    
    # Record the attempt
    record = DictationRecord(
        student_id=current_user.id,
        task_id=task_id,
        book_id=book_id or word.book_id,
        word_id=word_id,
        student_answer=student_answer,
        is_correct=is_correct
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        "ok": True,
        "is_correct": is_correct,
        "correct_answer": word.word,
        "phonetic": word.phonetic,
        "translation": word.translation
    })


@dictation_bp.route("/history", methods=["GET"])
@login_required
def get_history():
    """Get student's dictation history."""
    book_id = request.args.get("book_id", type=int)
    task_id = request.args.get("task_id", type=int)
    
    query = DictationRecord.query.filter_by(student_id=current_user.id)
    
    if book_id:
        query = query.filter_by(book_id=book_id)
    if task_id:
        query = query.filter_by(task_id=task_id)
    
    records = query.order_by(DictationRecord.created_at.desc()).limit(100).all()
    
    # Calculate stats
    total = len(records)
    correct = sum(1 for r in records if r.is_correct)
    accuracy = round(correct / total * 100, 1) if total > 0 else 0
    
    return jsonify({
        "ok": True,
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "records": [
            {
                "id": r.id,
                "word": r.word.word if r.word else None,
                "student_answer": r.student_answer,
                "is_correct": r.is_correct,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records[:50]  # Limit response size
        ]
    })


@dictation_bp.route("/stats/<int:book_id>", methods=["GET"])
@login_required
def get_book_stats(book_id):
    """Get student's stats for a specific book."""
    # Get all words in the book
    words = DictationWord.query.filter_by(book_id=book_id).all()
    word_ids = [w.id for w in words]
    
    # Get student's records for this book
    records = DictationRecord.query.filter(
        DictationRecord.student_id == current_user.id,
        DictationRecord.word_id.in_(word_ids)
    ).all()
    
    # Calculate stats
    attempted = set(r.word_id for r in records)
    correct = set(r.word_id for r in records if r.is_correct)
    
    # Wrong words (attempted but never got right)
    wrong_words = []
    for word in words:
        word_records = [r for r in records if r.word_id == word.id]
        if word_records and not any(r.is_correct for r in word_records):
            wrong_words.append({
                "id": word.id,
                "word": word.word,
                "phonetic": word.phonetic,
                "translation": word.translation,
                "attempts": len(word_records)
            })
    
    return jsonify({
        "ok": True,
        "total_words": len(words),
        "attempted": len(attempted),
        "correct": len(correct),
        "accuracy": round(len(correct) / len(attempted) * 100, 1) if attempted else 0,
        "wrong_words": wrong_words
    })
