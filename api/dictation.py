"""
Dictation API - Listening Practice System
Handles word book management, Excel upload, TTS generation, and practice records.
"""

import os
import re
import hashlib
import io
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from datetime import datetime
from functools import lru_cache, wraps
import jwt
import requests
from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user, login_required

from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from models import (
    db,
    User,
    DictationAnswerAppeal,
    DictationBook,
    DictationWord,
    DictationRecord,
    StudentWordMastery,
)
from api.qwen import generate_word_enrichment
from dictation_answers import (
    is_chinese_answer_correct,
    is_english_answer_correct,
    parse_answer_variants,
    serialize_answer_variants,
    strip_part_of_speech_prefix,
)
from services.dictation_review import DictationReviewError, submit_dictation_answer


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

_HYPHENATOR = None

SYLLABLE_OVERRIDES = {
    # Teaching-display overrides for common CET/SAT-style vocabulary where
    # hyphenation libraries split differently from classroom syllable chunks.
    "achieve": "a·chieve",
    "agriculture": "ag·ri·cul·ture",
    "astronaut": "astro·naut",
    "content": "con·tent",
    "elicit": "e·li·cit",
    "fairly": "fair·ly",
    "heritage": "he·ri·tage",
    "independent": "in·de·pend·ent",
    "instruction": "in·struc·tion",
    "military": "mili·ta·ry",
    "pregnant": "preg·nant",
    "realistic": "re·al·is·tic",
    "reputation": "re·pu·ta·tion",
    "vision": "vi·sion",
}


def _current_api_user():
    if current_user.is_authenticated:
        return current_user
    return getattr(request, "current_api_user", None)

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


def _word_enrichment_payload(word):
    return {
        "core_meaning_zh": word.core_meaning_zh,
        "usage_pattern": word.usage_pattern,
        "example_en": word.example_en,
        "example_zh": word.example_zh,
        "usage_note": word.usage_note,
    }


@lru_cache(maxsize=8192)
def _syllabify_token(token):
    clean = str(token or "").strip()
    override = SYLLABLE_OVERRIDES.get(clean.lower())
    if override:
        return override
    if len(clean) <= 3 or not re.search(r"[A-Za-z]", clean):
        return clean

    global _HYPHENATOR
    if _HYPHENATOR is None:
        try:
            import pyphen
            _HYPHENATOR = pyphen.Pyphen(lang="en_US")
        except Exception:
            _HYPHENATOR = False

    if not _HYPHENATOR:
        return clean

    hyphenated = _HYPHENATOR.inserted(clean)
    parts = [part for part in hyphenated.split("-") if part]
    return "·".join(parts) if len(parts) > 1 else clean


@lru_cache(maxsize=8192)
def _syllabify(word):
    text = str(word or "").strip()
    if not text:
        return ""

    def replace(match):
        return _syllabify_token(match.group(0))

    return re.sub(r"[A-Za-z]+", replace, text)


def _word_student_payload(word):
    payload = {
        "id": word.id,
        "sequence": word.sequence,
        "word": word.word,
        "accepted_answers": parse_answer_variants(word.accepted_answers),
        "syllables": _syllabify(word.word),
        "phonetic": word.phonetic,
        "translation": word.translation,
        "audio_us": word.audio_us,
        "audio_uk": word.audio_uk,
    }
    payload.update(_word_enrichment_payload(word))
    return payload


def _apply_enrichment_result(word, result, status="generated"):
    now = datetime.utcnow()
    word.core_meaning_zh = result.get("core_meaning_zh") or None
    word.usage_pattern = result.get("usage_pattern") or None
    word.example_en = result.get("example_en") or None
    word.example_zh = result.get("example_zh") or None
    word.usage_note = result.get("usage_note") or None
    word.vocab_ai_status = status
    word.vocab_ai_model = result.get("model") or current_app.config.get("ALIYUN_QWEN_MODEL")
    word.vocab_ai_generated_at = now
    word.vocab_reviewed_at = None
    if word.vocab_report_count is None:
        word.vocab_report_count = 0


PHRASE_LINE_OVERRIDES = {
    "as/so long as": "as long as/so long as",
    "from one's standpoint/point of view": "from one's standpoint/from one's point of view",
    "keep abreast/up with": "keep abreast with/keep up with",
}


def _normalize_pdf_line(line):
    return re.sub(r"\s+", " ", str(line or "")).strip()


def _normalize_english_phrase(raw):
    text = _normalize_pdf_line(raw)
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\.{3,}", "…", text)
    text = re.sub(r"\s*([,;:])\s*", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return PHRASE_LINE_OVERRIDES.get(text, text)


def _normalize_chinese_translation(raw):
    text = _normalize_pdf_line(raw)
    text = text.replace("； ", "；").replace("; ", ";")
    return text


def _contains_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _is_translation_only_line(line):
    text = _normalize_pdf_line(line)
    return _contains_chinese(text) and not re.search(r"[A-Za-z]", text)


def _split_mixed_phrase_line(line):
    text = _normalize_pdf_line(line)
    match = re.search(r"[\u4e00-\u9fff]", text)
    if not match:
        return None
    english = _normalize_english_phrase(text[:match.start()])
    chinese = _normalize_chinese_translation(text[match.start():])
    if not english or not chinese:
        return None
    return english, chinese


def _append_vocab_entry(entries, seen, english, chinese, topic):
    english_text = _normalize_english_phrase(english)
    chinese_text = _normalize_chinese_translation(chinese)
    topic_text = _normalize_pdf_line(topic or "General") or "General"
    if not english_text or not chinese_text:
        return
    entry_key = (english_text.lower(), chinese_text, topic_text)
    if entry_key in seen:
        return
    seen.add(entry_key)
    entries.append({
        "english": english_text,
        "chinese": chinese_text,
        "topic": topic_text,
    })


def _extract_pdf_text(pdf_path):
    all_text = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)
    except ImportError:
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text.append(text)
        except ImportError:
            result = subprocess.run(
                ["pdftotext", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"failed to extract pdf text: {result.stderr.strip()}")
            if result.stdout:
                all_text.append(result.stdout)
    return "\n".join(all_text)


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
                "book_type": book.book_type or "dictation",
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

        # Warm Kokoro TTS cache in the background so students don't hit cold synthesis.
        schedule_prewarm_for_book(book.id)

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
            "book_type": book.book_type or "dictation",
            "created_at": book.created_at.isoformat() if book.created_at else None
        },
        "words": [_word_student_payload(w) for w in words]
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
# TTS proxy & cache for mini-program playback.
# Cache read order is controlled by DICTATION_TTS_PROVIDER_ORDER. Cache-miss
# generation is controlled separately by DICTATION_TTS_GENERATION_PROVIDER_ORDER.
# ============================================================================

_KOKORO_LOCK = threading.Lock()
_KOKORO_ENGINE = None
_PIPER_LOCK = threading.Lock()
_PIPER_VOICE = None
_TTS_WARMUP_LOCK = threading.Lock()
_TTS_WARMUP_KEYS = set()


def _flag_enabled(value, default=True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _config_float(name: str, default: float) -> float:
    try:
        return float(current_app.config.get(name) or default)
    except (TypeError, ValueError):
        return default


def _config_optional_float(name: str) -> float | None:
    raw = current_app.config.get(name)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _dictation_tts_provider_order() -> list[str]:
    providers = _parse_tts_provider_order(current_app.config.get("DICTATION_TTS_PROVIDER_ORDER"))
    return providers or ["youdao"]


def _dictation_tts_generation_provider_order() -> list[str]:
    providers = _parse_tts_provider_order(
        current_app.config.get("DICTATION_TTS_GENERATION_PROVIDER_ORDER")
    )
    return providers or ["youdao"]


def _parse_tts_provider_order(raw) -> list[str]:
    providers = []
    for item in str(raw).split(","):
        provider = item.strip().lower()
        if provider in {"piper", "kokoro", "dashscope", "youdao"} and provider not in providers:
            providers.append(provider)
    return providers


def _safe_cache_token(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip()) or "default"


def _piper_paths() -> tuple[Path, Path]:
    base_dir = Path(
        current_app.config.get(
            "PIPER_TTS_DIR",
            Path(current_app.root_path) / "data" / "piper",
        )
    )
    voice = _safe_cache_token(current_app.config.get("PIPER_TTS_VOICE") or "en_US-lessac-high")
    model_path = base_dir / f"{voice}.onnx"
    return model_path, Path(f"{model_path}.json")


def _piper_voice():
    global _PIPER_VOICE
    if not _flag_enabled(current_app.config.get("PIPER_TTS_ENABLED"), default=True):
        return None
    if _PIPER_VOICE is not None:
        return _PIPER_VOICE

    model_path, config_path = _piper_paths()
    if not model_path.exists() or not config_path.exists():
        return None

    with _PIPER_LOCK:
        if _PIPER_VOICE is not None:
            return _PIPER_VOICE
        try:
            from piper import PiperVoice

            _PIPER_VOICE = PiperVoice.load(model_path, config_path=config_path)
            return _PIPER_VOICE
        except Exception as exc:
            current_app.logger.warning("Piper init failed: %s", exc)
            return None


def _piper_tts(text: str) -> bytes | None:
    """Local Piper TTS. Returns MP3 bytes when the voice model is available."""
    voice = _piper_voice()
    if voice is None:
        return None

    try:
        from piper import SynthesisConfig

        syn_config = SynthesisConfig(
            length_scale=_config_float("PIPER_TTS_LENGTH_SCALE", 1.15),
            noise_scale=_config_optional_float("PIPER_TTS_NOISE_SCALE"),
            noise_w_scale=_config_optional_float("PIPER_TTS_NOISE_W_SCALE"),
            normalize_audio=True,
        )
        out = io.BytesIO()
        with _PIPER_LOCK:
            chunks = list(voice.synthesize(text, syn_config))
        if not chunks:
            return None
        with wave.open(out, "wb") as wav:
            first = chunks[0]
            wav.setframerate(first.sample_rate)
            wav.setsampwidth(first.sample_width)
            wav.setnchannels(first.sample_channels)
            for chunk in chunks:
                wav.writeframes(chunk.audio_int16_bytes)
        return _wav_to_mp3(out.getvalue())
    except Exception as exc:
        current_app.logger.warning("Piper TTS error for %s: %s", text, exc)
        return None


def _kokoro_paths() -> tuple[Path, Path]:
    base_dir = Path(
        current_app.config.get(
            "KOKORO_TTS_DIR",
            Path(current_app.root_path) / "data" / "kokoro",
        )
    )
    return base_dir / "kokoro-v1.0.onnx", base_dir / "voices-v1.0.bin"


def _download_file(url: str, target: Path) -> bool:
    if not url:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with tmp_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        tmp_path.replace(target)
        return True
    except Exception as exc:
        current_app.logger.warning("Kokoro model download failed %s: %s", url, exc)
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def _ensure_kokoro_files() -> bool:
    model_path, voices_path = _kokoro_paths()
    if not _flag_enabled(current_app.config.get("KOKORO_TTS_AUTO_DOWNLOAD"), default=False):
        return model_path.exists() and voices_path.exists()
    ok = True
    if not model_path.exists():
        ok = _download_file(current_app.config.get("KOKORO_TTS_MODEL_URL", ""), model_path) and ok
    if not voices_path.exists():
        ok = _download_file(current_app.config.get("KOKORO_TTS_VOICES_URL", ""), voices_path) and ok
    return ok and model_path.exists() and voices_path.exists()


def _kokoro_engine():
    global _KOKORO_ENGINE
    if _KOKORO_ENGINE is not None:
        return _KOKORO_ENGINE
    with _KOKORO_LOCK:
        if _KOKORO_ENGINE is not None:
            return _KOKORO_ENGINE
        if not _ensure_kokoro_files():
            return None
        try:
            from kokoro_onnx import Kokoro
            model_path, voices_path = _kokoro_paths()
            _KOKORO_ENGINE = Kokoro(str(model_path), str(voices_path))
            return _KOKORO_ENGINE
        except Exception as exc:
            current_app.logger.warning("Kokoro init failed: %s", exc)
            return None


def _pcm_to_wav_bytes(samples, sample_rate: int) -> bytes:
    import numpy as np

    audio = np.asarray(samples, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.reshape(-1)
    audio = np.clip(audio, -1.0, 1.0)
    pcm = (audio * 32767).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate or 24000))
        wav.writeframes(pcm.tobytes())
    return out.getvalue()


def _kokoro_tts(text: str) -> bytes | None:
    """Local Kokoro ONNX TTS. Returns MP3 bytes when available."""
    if not _flag_enabled(current_app.config.get("KOKORO_TTS_ENABLED"), default=True):
        return None
    engine = _kokoro_engine()
    if engine is None:
        return None

    voice = (current_app.config.get("KOKORO_TTS_VOICE") or "af_heart").strip()
    lang = (current_app.config.get("KOKORO_TTS_LANG") or "en-us").strip()
    try:
        speed = float(current_app.config.get("KOKORO_TTS_SPEED") or 0.88)
    except (TypeError, ValueError):
        speed = 0.88
    speed = min(1.4, max(0.6, speed))

    try:
        with _KOKORO_LOCK:
            samples, sample_rate = engine.create(text, voice=voice, speed=speed, lang=lang)
        wav_bytes = _pcm_to_wav_bytes(samples, sample_rate)
        mp3_bytes = _wav_to_mp3(wav_bytes)
        if not mp3_bytes:
            current_app.logger.warning("Kokoro TTS MP3 conversion failed for %s", text)
        return mp3_bytes
    except Exception as exc:
        current_app.logger.warning("Kokoro TTS error for %s: %s", text, exc)
        return None


def _dictation_tts_text(text: str) -> str:
    """Repeat dictation prompts so plural and tense suffixes are easier to hear."""
    cleaned = re.sub(r"\s+", " ", strip_part_of_speech_prefix(text))
    if not cleaned:
        return ""
    try:
        repeat_count = int(current_app.config.get("DICTATION_TTS_REPEAT_COUNT") or 2)
    except (TypeError, ValueError):
        repeat_count = 2
    repeat_count = min(3, max(1, repeat_count))
    if repeat_count <= 1:
        return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."
    return ". ".join([cleaned] * repeat_count) + "."


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
    timeout = _config_float("DICTATION_TTS_PROVIDER_TIMEOUT", 8)
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            current_app.logger.warning("DashScope TTS failed %s: %s", text, resp.status_code)
            return None
        data = resp.json()
        audio_url = data.get("output", {}).get("audio", {}).get("url")
        if not audio_url:
            return None
        audio_resp = requests.get(audio_url, timeout=timeout)
        if audio_resp.status_code == 200 and audio_resp.content:
            raw = audio_resp.content
            # Convert WAV → MP3 via ffmpeg for smaller file size
            return _wav_to_mp3(raw) or raw
    except Exception as exc:
        current_app.logger.warning("DashScope TTS error for %s: %s", text, exc)

    return None


def _wav_to_mp3(raw_audio: bytes) -> bytes | None:
    """Convert WAV/PCM audio bytes to MP3 using ffmpeg. Returns None on failure."""
    tmp_in_path = None
    tmp_out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
            tmp_in.write(raw_audio)
            tmp_in_path = tmp_in.name
        tmp_out_path = tmp_in_path.replace(".wav", ".mp3")
        ffmpeg_bin = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
        result = subprocess.run(
            [ffmpeg_bin, "-y", "-i", tmp_in_path, "-codec:a", "libmp3lame",
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
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass
    return None


def _youdao_tts(text: str) -> bytes | None:
    """Youdao dictvoice — high-quality for base forms, weak for inflected."""
    # dictvoice 对部分词的"带末尾句号"文本返回 500（如 "inhabitant."），
    # 去掉末尾句号不改变发音；缓存键仍按原 tts_text 计算，不受影响。
    query = text.strip().rstrip(".").strip()
    if not query:
        return None
    url = f"https://dict.youdao.com/dictvoice?audio={requests.utils.quote(query)}&type=2"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200 and resp.content:
            return resp.content
        current_app.logger.warning("Youdao TTS fetch failed %s: %s", text, resp.status_code)
    except Exception as exc:
        current_app.logger.warning("Youdao TTS proxy error for %s: %s", text, exc)
    return None


def _is_high_quality_mp3(data: bytes) -> bool:
    """Check MPEG version in frame header.

    Youdao returns MPEG v1 (48 kHz, real recording) for base-form words and
    MPEG v2 (24 kHz, synthesized — often drops inflections) for unknown forms.
    Returns True only when the audio is a genuine v1 recording.
    """
    if not data or len(data) < 4:
        return False
    # Scan for the first valid MPEG frame sync (0xFF followed by 0xE0+ mask)
    limit = min(len(data) - 1, 1024)
    for i in range(limit):
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            version_bits = (data[i + 1] >> 3) & 0x03
            return version_bits == 3  # 3 → MPEG v1, high quality
    return False


def _cache_file_is_high_quality(path: Path) -> bool:
    """True when a cached mp3 is a Youdao v1 human recording (not v2 synth)."""
    try:
        with path.open("rb") as fh:
            head = fh.read(2048)
    except OSError:
        return False
    return _is_high_quality_mp3(head)


def _dictation_provider_cache_key(provider: str) -> str:
    if provider == "piper":
        voice = _safe_cache_token(current_app.config.get("PIPER_TTS_VOICE") or "en_US-lessac-high")
        length = _safe_cache_token(current_app.config.get("PIPER_TTS_LENGTH_SCALE") or "1.15")
        noise = _safe_cache_token(current_app.config.get("PIPER_TTS_NOISE_SCALE") or "default")
        noise_w = _safe_cache_token(current_app.config.get("PIPER_TTS_NOISE_W_SCALE") or "default")
        return f"piper_{voice}_{length}_{noise}_{noise_w}"
    if provider == "kokoro":
        voice = _safe_cache_token(current_app.config.get("KOKORO_TTS_VOICE") or "af_heart")
        lang = _safe_cache_token(current_app.config.get("KOKORO_TTS_LANG") or "en-us")
        speed = _safe_cache_token(current_app.config.get("KOKORO_TTS_SPEED") or "0.88")
        return f"kokoro_{voice}_{lang}_{speed}"
    if provider == "dashscope":
        model = _safe_cache_token(current_app.config.get("ALIYUN_TTS_MODEL") or "qwen3-tts-flash")
        voice = _safe_cache_token(current_app.config.get("ALIYUN_TTS_VOICE") or "Cherry")
        return f"dashscope_{model}_{voice}"
    if provider == "youdao":
        return "youdao"
    return _safe_cache_token(provider)


def _dictation_provider_cache_keys(provider: str, include_legacy: bool = False) -> list[str]:
    keys = [_dictation_provider_cache_key(provider)]
    if include_legacy and provider == "kokoro":
        voice = _safe_cache_token(current_app.config.get("KOKORO_TTS_VOICE") or "af_heart")
        lang = _safe_cache_token(current_app.config.get("KOKORO_TTS_LANG") or "en-us")
        # Older Kokoro cache files kept the speed value as "0.88"; current safe
        # tokens normalize it to "0_88". Keep reading both so existing cache
        # survives provider changes.
        legacy_speed = str(current_app.config.get("KOKORO_TTS_SPEED") or "0.88").strip() or "0.88"
        legacy_key = f"kokoro_{voice}_{lang}_{legacy_speed}"
        if legacy_key not in keys:
            keys.append(legacy_key)
    return keys


def _dictation_tts_cache_texts(word: str, tts_text: str, include_legacy: bool = False) -> list[str]:
    texts = [tts_text]
    if include_legacy:
        cleaned = re.sub(r"\s+", " ", strip_part_of_speech_prefix(word))
        if cleaned:
            legacy_texts = [
                cleaned,
                ". ".join([cleaned] * 2) + ".",
                ". ".join([cleaned] * 3) + ".",
            ]
            for legacy_text in legacy_texts:
                if legacy_text not in texts:
                    texts.append(legacy_text)
    return texts


def _dictation_tts_cache_path_for_key(provider_key: str, word: str, tts_text: str) -> Path:
    speech_word = strip_part_of_speech_prefix(word)

    raw_safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", speech_word.lower()) or "tts"
    text_hash = hashlib.md5(tts_text.lower().encode()).hexdigest()
    safe_name = raw_safe if len(raw_safe) <= 64 else text_hash
    tts_dir = Path(current_app.config.get("UPLOAD_FOLDER", Path(current_app.root_path) / "uploads")) / "tts_cache"
    tts_dir.mkdir(parents=True, exist_ok=True)
    return tts_dir / f"{provider_key}_dict_{safe_name}_{text_hash[:8]}.mp3"


def _dictation_tts_cache_path(provider: str, word: str, tts_text: str | None = None) -> Path:
    speech_word = strip_part_of_speech_prefix(word)
    tts_text = tts_text if tts_text is not None else _dictation_tts_text(speech_word)
    provider_key = _dictation_provider_cache_key(provider)
    return _dictation_tts_cache_path_for_key(provider_key, speech_word, tts_text)


def _dictation_tts_cache_paths(word: str, tts_text: str | None = None) -> tuple[Path, Path]:
    """Backward-compatible primary/fallback cache paths for callers."""
    provider = _dictation_tts_provider_order()[0]
    return (
        _dictation_tts_cache_path(provider, word, tts_text),
        _dictation_tts_cache_path("youdao", word, tts_text),
    )


def _dictation_tts_cache_candidates(
    word: str,
    tts_text: str | None = None,
    providers: list[str] | None = None,
    include_legacy: bool = True,
) -> list[tuple[str, Path]]:
    tts_text = tts_text if tts_text is not None else _dictation_tts_text(word)
    provider_order = providers if providers is not None else _dictation_tts_provider_order()
    candidates: list[tuple[str, Path]] = []
    seen_paths: set[Path] = set()
    for provider in provider_order:
        for cache_text in _dictation_tts_cache_texts(word, tts_text, include_legacy):
            for provider_key in _dictation_provider_cache_keys(provider, include_legacy):
                path = _dictation_tts_cache_path_for_key(provider_key, word, cache_text)
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                candidates.append((provider, path))
    return candidates


def _send_tts_file(path: Path):
    response = send_file(path, mimetype="audio/mpeg", max_age=7 * 24 * 60 * 60)
    response.headers["Cache-Control"] = "public, max-age=604800"
    return response


def _tts_provider_audio(provider: str, tts_text: str) -> bytes | None:
    if provider == "piper":
        return _piper_tts(tts_text)
    if provider == "kokoro":
        return _kokoro_tts(tts_text)
    if provider == "dashscope":
        return _dashscope_tts(tts_text)
    if provider == "youdao":
        return _youdao_tts(tts_text)
    return None


def _generate_tts_to_cache(
    word: str,
    tts_text: str,
    primary_cache: Path | None = None,
    fallback_cache: Path | None = None,
    providers: list[str] | None = None,
) -> Path | None:
    del primary_cache, fallback_cache  # kept for old imports/call shape
    provider_order = providers if providers is not None else _dictation_tts_generation_provider_order()
    for provider, cache_path in _dictation_tts_cache_candidates(
        word,
        tts_text,
        provider_order,
        include_legacy=False,
    ):
        audio = _tts_provider_audio(provider, tts_text)
        if audio:
            cache_path.write_bytes(audio)
            return cache_path

    return None


def _prewarm_tts_cache(words: list[str]) -> None:
    for word in words:
        word = strip_part_of_speech_prefix(word)
        if not word:
            continue
        tts_text = _dictation_tts_text(word)
        cache_candidates = _dictation_tts_cache_candidates(word, tts_text)
        warmup_key = str(cache_candidates[0][1]) if cache_candidates else tts_text
        with _TTS_WARMUP_LOCK:
            if warmup_key in _TTS_WARMUP_KEYS:
                continue
            _TTS_WARMUP_KEYS.add(warmup_key)
        try:
            if not any(path.exists() for _, path in cache_candidates):
                _generate_tts_to_cache(word, tts_text)
        except Exception as exc:
            current_app.logger.warning("Dictation TTS warmup failed for %s: %s", word, exc)
        finally:
            with _TTS_WARMUP_LOCK:
                _TTS_WARMUP_KEYS.discard(warmup_key)


def schedule_prewarm_for_book(book_id: int) -> None:
    """Spawn a background thread that warms Kokoro TTS cache for every word in a book.

    Called after book upload and task creation so students never hit cold Kokoro
    synthesis on the play path. Idempotent — _prewarm_tts_cache dedups via
    _TTS_WARMUP_KEYS, so concurrent invocations are safe.
    """
    try:
        book = DictationBook.query.get(book_id)
    except Exception:
        book = None
    if book is None:
        return
    if (book.book_type or "dictation").lower() == "translation":
        return

    app_obj = current_app._get_current_object()

    def runner():
        with app_obj.app_context():
            try:
                rows = (
                    db.session.query(DictationWord.word)
                    .filter(DictationWord.book_id == book_id)
                    .all()
                )
                clean = [r[0].strip() for r in rows if r[0] and r[0].strip()]
                if clean:
                    _prewarm_tts_cache(clean)
            except Exception as exc:
                current_app.logger.warning(
                    "Background TTS prewarm failed for book %s: %s", book_id, exc
                )

    threading.Thread(target=runner, daemon=True).start()


@dictation_bp.route("/tts", methods=["GET"])
def proxy_tts():
    """Proxy TTS audio with a quality-gated hybrid of Youdao and Kokoro.

    Youdao serves a clean human recording (MPEG v1) for base dictionary words
    but degrades to a synthetic v2 voice for inflected/uncommon forms. Kokoro is
    a consistent neural voice that handles inflections but adds a leading-vowel
    artifact on some isolated words. So: prefer a Youdao v1 recording; when
    Youdao would only give v2, use the pre-baked Kokoro cache instead.
    """
    word = strip_part_of_speech_prefix(request.args.get("word"))
    if not word:
        return jsonify({"ok": False, "error": "missing_word"}), 400
    tts_text = _dictation_tts_text(word)

    youdao_cache = _dictation_tts_cache_path("youdao", word, tts_text)
    youdao_v2_cached = False  # a low-quality (v2 synth) Youdao clip is on disk

    # 1. Youdao human recording (v1). Fetch+cache on first miss; skip v2 synth.
    if youdao_cache.exists():
        if _cache_file_is_high_quality(youdao_cache):
            return _send_tts_file(youdao_cache)
        youdao_v2_cached = True
    else:
        audio = _youdao_tts(tts_text)
        if audio:
            youdao_cache.write_bytes(audio)
            if _is_high_quality_mp3(audio):
                return _send_tts_file(youdao_cache)
            youdao_v2_cached = True

    # 2. Youdao only offers a synth voice here → use the pre-baked Kokoro cache.
    for _provider, cache_path in _dictation_tts_cache_candidates(
        word, tts_text, providers=["kokoro"], include_legacy=True
    ):
        if not cache_path.exists():
            continue
        try:
            return _send_tts_file(cache_path)
        except Exception:
            cache_path.unlink(missing_ok=True)

    # 3. No Kokoro cache (e.g. free-typed word). Serve the Youdao v2 clip we
    #    already have, else fall back to the generation chain.
    if youdao_v2_cached and youdao_cache.exists():
        return _send_tts_file(youdao_cache)

    generated_cache = _generate_tts_to_cache(word, tts_text)
    if generated_cache:
        return _send_tts_file(generated_cache)

    return jsonify({"ok": False, "error": "tts_fetch_failed"}), 502


@dictation_bp.route("/tts/prewarm", methods=["POST"])
@require_session_or_bearer
def prewarm_tts():
    """Start background TTS cache generation for upcoming dictation words."""
    data = request.get_json(silent=True) or {}
    words = data.get("words") or []
    if not isinstance(words, list):
        return jsonify({"ok": False, "error": "invalid_words"}), 400

    clean_words = []
    seen = set()
    for raw in words:
        word = str(raw or "").strip()
        key = word.lower()
        if not word or key in seen:
            continue
        seen.add(key)
        clean_words.append(word)
        if len(clean_words) >= 80:
            break

    if not clean_words:
        return jsonify({"ok": True, "queued": 0})

    app_obj = current_app._get_current_object()

    def runner():
        with app_obj.app_context():
            _prewarm_tts_cache(clean_words)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return jsonify({"ok": True, "queued": len(clean_words)})


# ============================================================================
# Practice APIs (for Mini Program)
# ============================================================================

@dictation_bp.route("/submit", methods=["POST"])
@require_session_or_bearer
def submit_answer():
    """Submit a dictation answer and check if correct."""
    user = _current_api_user()
    if not user:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    try:
        result = submit_dictation_answer(user, data)
    except DictationReviewError as error:
        db.session.rollback()
        payload = {"ok": False, "error": error.error}
        payload.update(error.details)
        return jsonify(payload), error.status_code

    word = db.session.get(DictationWord, int(data.get("word_id")))
    db.session.commit()
    response = dict(result)
    response.update({
        "syllables": _syllabify(word.word),
        "phonetic": word.phonetic,
    })
    response.update(_word_enrichment_payload(word))
    return jsonify(response)


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


@dictation_bp.route("/review/today", methods=["GET"])
@require_session_or_bearer
def get_review_today():
    """Return words due for spaced-repetition review for the current student.

    A word is "due" when it has a mastery row with next_review_at <= now and
    review_level < graduated. Each word carries the practice mode it should be
    drilled with (rises from en_to_zh to zh_to_en to audio_to_en as level climbs).
    """
    from datetime import datetime
    user = _current_api_user()
    if not user:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    now = datetime.utcnow()
    limit = min(int(request.args.get("limit", 30) or 30), 100)

    rows = (
        StudentWordMastery.query
        .filter(StudentWordMastery.student_id == user.id)
        .filter(StudentWordMastery.review_level < StudentWordMastery.LEVEL_GRADUATED)
        .filter(StudentWordMastery.next_review_at <= now)
        .order_by(StudentWordMastery.next_review_at.asc())
        .limit(limit)
        .all()
    )

    items = []
    for m in rows:
        w = m.word
        if w is None:
            continue
        item = {
            "word_id": w.id,
            "id": w.id,
            "book_id": w.book_id,
            "word": w.word,
            "accepted_answers": parse_answer_variants(w.accepted_answers),
            "syllables": _syllabify(w.word),
            "phonetic": w.phonetic,
            "translation": w.translation,
            "mode": StudentWordMastery.mode_for_level(m.review_level),
            "review_level": m.review_level,
            "mistake_count": m.mistake_count,
        }
        item.update(_word_enrichment_payload(w))
        items.append(item)

    return jsonify({"ok": True, "count": len(items), "items": items})


@dictation_bp.route("/review/summary", methods=["GET"])
@require_session_or_bearer
def get_review_summary():
    """Lightweight summary for the home-page card: how many words are due now."""
    from datetime import datetime
    user = _current_api_user()
    if not user:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    now = datetime.utcnow()
    due_count = (
        StudentWordMastery.query
        .filter(StudentWordMastery.student_id == user.id)
        .filter(StudentWordMastery.review_level < StudentWordMastery.LEVEL_GRADUATED)
        .filter(StudentWordMastery.next_review_at <= now)
        .count()
    )
    return jsonify({"ok": True, "due_count": due_count})


def _admin_word_payload(word):
    book = word.book
    return {
        "id": word.id,
        "book_id": word.book_id,
        "book_title": book.title if book else "",
        "sequence": word.sequence,
        "word": word.word,
        "accepted_answers": parse_answer_variants(word.accepted_answers),
        "phonetic": word.phonetic,
        "translation": word.translation,
        "core_meaning_zh": word.core_meaning_zh,
        "usage_pattern": word.usage_pattern,
        "example_en": word.example_en,
        "example_zh": word.example_zh,
        "usage_note": word.usage_note,
        "vocab_ai_status": word.vocab_ai_status or "empty",
        "vocab_ai_model": word.vocab_ai_model,
        "vocab_ai_generated_at": word.vocab_ai_generated_at.isoformat() if word.vocab_ai_generated_at else None,
        "vocab_reviewed_at": word.vocab_reviewed_at.isoformat() if word.vocab_reviewed_at else None,
        "vocab_report_count": word.vocab_report_count or 0,
    }


def _answer_appeal_payload(appeal):
    student = appeal.student
    reviewer = appeal.reviewer
    word = appeal.word
    book = appeal.book
    return {
        "id": appeal.id,
        "student_id": appeal.student_id,
        "student_name": (
            (student.display_name or student.username) if student else "未知学生"
        ),
        "word_id": appeal.word_id,
        "word": word.word if word else appeal.reference_answer,
        "translation": word.translation if word else "",
        "accepted_answers": parse_answer_variants(word.accepted_answers) if word else [],
        "book_id": appeal.book_id,
        "book_title": book.title if book else "",
        "task_id": appeal.task_id,
        "mode": appeal.mode,
        "student_answer": appeal.student_answer,
        "reference_answer": appeal.reference_answer,
        "reason": appeal.reason or "",
        "status": appeal.status,
        "reviewer_name": (
            (reviewer.display_name or reviewer.username) if reviewer else ""
        ),
        "reviewed_at": appeal.reviewed_at.isoformat() if appeal.reviewed_at else None,
        "resolution_note": appeal.resolution_note or "",
        "added_to_accepted_answers": bool(appeal.added_to_accepted_answers),
        "created_at": appeal.created_at.isoformat() if appeal.created_at else None,
    }


@dictation_bp.route("/appeals", methods=["POST"])
@require_session_or_bearer
def create_answer_appeal():
    """Create a reviewable appeal for a vocabulary answer marked wrong."""
    user = _current_api_user()
    if not user:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    word_id = data.get("word_id")
    student_answer = str(data.get("answer") or "").strip()
    mode = str(data.get("mode") or "audio_to_en").strip().lower()
    if mode not in {"audio_to_en", "zh_to_en", "en_to_zh", "spelling_drill"}:
        mode = "audio_to_en"
    if not word_id or not student_answer:
        return jsonify({"ok": False, "error": "missing_params"}), 400

    word = DictationWord.query.get_or_404(word_id)
    if mode == "en_to_zh":
        already_accepted = is_chinese_answer_correct(student_answer, word.translation)
        reference_answer = word.translation or word.word
    else:
        already_accepted = is_english_answer_correct(
            student_answer,
            word.word,
            accepted_answers=word.accepted_answers,
        )
        reference_answer = word.word
    if already_accepted:
        return jsonify({"ok": False, "error": "answer_already_accepted"}), 409

    normalized_answer = (
        student_answer.lower() if mode != "en_to_zh" else student_answer
    )
    existing = (
        DictationAnswerAppeal.query
        .filter_by(
            student_id=user.id,
            word_id=word.id,
            mode=mode,
            student_answer=normalized_answer,
            status=DictationAnswerAppeal.STATUS_PENDING,
        )
        .order_by(DictationAnswerAppeal.id.desc())
        .first()
    )
    if existing:
        return jsonify({
            "ok": True,
            "duplicate": True,
            "appeal": _answer_appeal_payload(existing),
        })

    task_id = data.get("task_id")
    appeal = DictationAnswerAppeal(
        student_id=user.id,
        word_id=word.id,
        book_id=word.book_id,
        task_id=int(task_id) if str(task_id or "").isdigit() else None,
        mode=mode,
        student_answer=normalized_answer,
        reference_answer=str(reference_answer or word.word)[:200],
        reason=str(data.get("reason") or "我认为这个答案也应被接受").strip()[:500],
    )
    db.session.add(appeal)
    db.session.commit()
    return jsonify({"ok": True, "appeal": _answer_appeal_payload(appeal)}), 201


@dictation_bp.route("/appeals", methods=["GET"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def list_answer_appeals():
    status = str(request.args.get("status") or "pending").strip().lower()
    allowed_statuses = {
        DictationAnswerAppeal.STATUS_PENDING,
        DictationAnswerAppeal.STATUS_APPROVED,
        DictationAnswerAppeal.STATUS_REJECTED,
        "all",
    }
    if status not in allowed_statuses:
        status = DictationAnswerAppeal.STATUS_PENDING
    query = DictationAnswerAppeal.query.options(
        joinedload(DictationAnswerAppeal.student),
        joinedload(DictationAnswerAppeal.reviewer),
        joinedload(DictationAnswerAppeal.word),
        joinedload(DictationAnswerAppeal.book),
    )
    if status != "all":
        query = query.filter(DictationAnswerAppeal.status == status)
    rows = query.order_by(
        DictationAnswerAppeal.created_at.desc(), DictationAnswerAppeal.id.desc()
    ).limit(200).all()
    return jsonify({
        "ok": True,
        "status": status,
        "total": len(rows),
        "items": [_answer_appeal_payload(item) for item in rows],
    })


@dictation_bp.route("/appeals/<int:appeal_id>/review", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def review_answer_appeal(appeal_id):
    appeal = DictationAnswerAppeal.query.get_or_404(appeal_id)
    if appeal.status != DictationAnswerAppeal.STATUS_PENDING:
        return jsonify({"ok": False, "error": "appeal_already_reviewed"}), 409
    data = request.get_json() or {}
    decision = str(data.get("decision") or "").strip().lower()
    if decision not in {
        DictationAnswerAppeal.STATUS_APPROVED,
        DictationAnswerAppeal.STATUS_REJECTED,
    }:
        return jsonify({"ok": False, "error": "invalid_decision"}), 400

    added = False
    if decision == DictationAnswerAppeal.STATUS_APPROVED and appeal.mode != "en_to_zh":
        answer = parse_answer_variants([appeal.student_answer])
        if answer and re.search(r"[a-zA-Z]", answer[0]):
            accepted = parse_answer_variants(appeal.word.accepted_answers)
            if answer[0] not in accepted:
                accepted.append(answer[0])
                appeal.word.accepted_answers = serialize_answer_variants(accepted)
            added = True

    appeal.status = decision
    appeal.reviewer_id = current_user.id
    appeal.reviewed_at = datetime.utcnow()
    appeal.resolution_note = str(data.get("resolution_note") or "").strip()[:500]
    appeal.added_to_accepted_answers = added
    db.session.commit()
    return jsonify({"ok": True, "appeal": _answer_appeal_payload(appeal)})


def _has_enrichment_filter():
    return or_(
        DictationWord.core_meaning_zh.isnot(None),
        DictationWord.usage_pattern.isnot(None),
        DictationWord.example_en.isnot(None),
        DictationWord.example_zh.isnot(None),
        DictationWord.usage_note.isnot(None),
    )


@dictation_bp.route("/example/report/<int:word_id>", methods=["POST"])
@require_session_or_bearer
def report_word_enrichment(word_id):
    """Allow a student to report an incorrect or awkward enrichment block."""
    word = DictationWord.query.get_or_404(word_id)
    word.vocab_report_count = (word.vocab_report_count or 0) + 1
    word.vocab_reviewed_at = None
    if word.vocab_ai_status == "reviewed":
        word.vocab_ai_status = "generated"
    db.session.commit()
    return jsonify({"ok": True, "report_count": word.vocab_report_count})


@dictation_bp.route("/examples", methods=["GET"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def list_word_enrichments():
    """Teacher/TA review queue for vocabulary-enrichment content."""
    status = (request.args.get("status") or "pending").strip().lower()
    book_id = request.args.get("book_id", type=int)
    page = max(request.args.get("page", default=1, type=int), 1)
    per_page = min(max(request.args.get("per_page", default=50, type=int), 1), 100)

    query = DictationWord.query.options(joinedload(DictationWord.book)).join(DictationBook)
    query = query.filter(DictationBook.is_deleted == False)  # noqa: E712
    if book_id:
        query = query.filter(DictationWord.book_id == book_id)

    if status == "reported":
        query = query.filter((DictationWord.vocab_report_count != None) & (DictationWord.vocab_report_count > 0))  # noqa: E711
    elif status == "reviewed":
        query = query.filter(DictationWord.vocab_reviewed_at.isnot(None))
        query = query.filter((DictationWord.vocab_report_count == None) | (DictationWord.vocab_report_count == 0))  # noqa: E711
    elif status == "failed":
        query = query.filter(DictationWord.vocab_ai_status == "failed")
    else:
        status = "pending"
        query = query.filter(_has_enrichment_filter())
        query = query.filter(DictationWord.vocab_reviewed_at.is_(None))
        query = query.filter((DictationWord.vocab_report_count == None) | (DictationWord.vocab_report_count == 0))  # noqa: E711
        query = query.filter(or_(DictationWord.vocab_ai_status == None, DictationWord.vocab_ai_status != "failed"))  # noqa: E711

    total = query.count()
    rows = (
        query
        .order_by(DictationWord.updated_at.desc(), DictationWord.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    books = (
        DictationBook.query
        .filter_by(is_deleted=False)
        .order_by(DictationBook.title.asc())
        .all()
    )
    return jsonify({
        "ok": True,
        "status": status,
        "page": page,
        "per_page": per_page,
        "total": total,
        "items": [_admin_word_payload(word) for word in rows],
        "books": [
            {
                "id": book.id,
                "title": book.title,
                "word_count": book.word_count,
                "book_type": book.book_type or "dictation",
            }
            for book in books
        ],
    })


@dictation_bp.route("/example/<int:word_id>/approve", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def approve_word_enrichment(word_id):
    word = DictationWord.query.get_or_404(word_id)
    word.vocab_ai_status = "reviewed"
    word.vocab_reviewed_at = datetime.utcnow()
    word.vocab_report_count = 0
    db.session.commit()
    return jsonify({"ok": True, "item": _admin_word_payload(word)})


@dictation_bp.route("/example/<int:word_id>/edit", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def edit_word_enrichment(word_id):
    word = DictationWord.query.get_or_404(word_id)
    data = request.get_json() or {}
    for field in ("core_meaning_zh", "usage_pattern", "example_en", "example_zh", "usage_note"):
        if field in data:
            value = str(data.get(field) or "").strip()
            setattr(word, field, value or None)
    word.vocab_ai_status = "edited"
    word.vocab_reviewed_at = datetime.utcnow()
    word.vocab_report_count = 0
    db.session.commit()
    return jsonify({"ok": True, "item": _admin_word_payload(word)})


@dictation_bp.route("/example/<int:word_id>/regenerate", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def regenerate_word_enrichment(word_id):
    word = DictationWord.query.get_or_404(word_id)
    result = generate_word_enrichment(
        word.word,
        word.translation or "",
        word_id=word.id,
        phonetic=word.phonetic,
    )
    if not result:
        word.vocab_ai_status = "failed"
        db.session.commit()
        return jsonify({"ok": False, "error": "qwen_generation_failed"}), 502

    _apply_enrichment_result(word, result, status="generated")
    word.vocab_report_count = 0
    db.session.commit()
    return jsonify({"ok": True, "item": _admin_word_payload(word)})


@dictation_bp.route("/example/<int:word_id>/clear", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def clear_word_enrichment(word_id):
    word = DictationWord.query.get_or_404(word_id)
    word.core_meaning_zh = None
    word.usage_pattern = None
    word.example_en = None
    word.example_zh = None
    word.usage_note = None
    word.vocab_ai_status = "empty"
    word.vocab_ai_model = None
    word.vocab_ai_generated_at = None
    word.vocab_reviewed_at = None
    word.vocab_report_count = 0
    db.session.commit()
    return jsonify({"ok": True, "item": _admin_word_payload(word)})


@dictation_bp.route("/stubborn-words", methods=["GET"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def get_stubborn_words():
    """TA/teacher view: list students with their stubborn words (mistake_count >= threshold).

    Grouped by student so a TA can quickly see who needs targeted attention.
    """
    threshold = max(int(request.args.get("threshold", 3) or 3), 1)

    rows = (
        StudentWordMastery.query
        .filter(StudentWordMastery.mistake_count >= threshold)
        .order_by(
            StudentWordMastery.student_id.asc(),
            StudentWordMastery.mistake_count.desc(),
        )
        .all()
    )

    grouped = {}
    for m in rows:
        student = m.student
        word = m.word
        if student is None or word is None:
            continue
        bucket = grouped.setdefault(student.id, {
            "student_id": student.id,
            "student_name": getattr(student, "name", None) or student.username,
            "words": [],
        })
        bucket["words"].append({
            "word_id": word.id,
            "word": word.word,
            "translation": word.translation,
            "mistake_count": m.mistake_count,
            "review_level": m.review_level,
            "last_seen_at": m.last_seen_at.isoformat() if m.last_seen_at else None,
        })

    return jsonify({
        "ok": True,
        "threshold": threshold,
        "students": list(grouped.values()),
    })


@dictation_bp.route("/books/upload-vocab-pdf", methods=["POST"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def upload_vocab_pdf():
    """Upload a Chinese-English vocabulary PDF (e.g. TOEFL writing vocab).
    Creates a DictationBook with book_type='translation'.
    Practice mode: show Chinese, student types English.
    """
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "missing_file"}), 400

    file = request.files["file"]
    title = request.form.get("title", "").strip()
    topic_filter = request.form.get("topic", "").strip()  # Optional: only import one topic

    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return jsonify({"ok": False, "error": "must_be_pdf"}), 400

    # Save to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    file.save(tmp.name)
    tmp.close()

    try:
        full_text = _extract_pdf_text(tmp.name)
    finally:
        os.unlink(tmp.name)

    # Parse vocab entries
    entries = _parse_vocab_pdf(full_text)

    if not entries:
        return jsonify({"ok": False, "error": "no_entries", "message": "未识别到词汇条目"}), 400

    # If topic filter specified, only keep entries from that topic
    if topic_filter:
        entries = [e for e in entries if e['topic'] == topic_filter]
        if not entries:
            return jsonify({"ok": False, "error": "no_entries_for_topic"}), 400

    if not title:
        title = os.path.splitext(file.filename)[0]

    # Create book
    book = DictationBook(
        title=title,
        description=f"翻译练习 - 看中文写英文 ({len(entries)}词)",
        word_count=len(entries),
        created_by=current_user.id,
        book_type='translation'
    )
    db.session.add(book)
    db.session.flush()

    for i, entry in enumerate(entries):
        word = DictationWord(
            book_id=book.id,
            sequence=i + 1,
            word=entry['english'],
            translation=entry['chinese'],
            phonetic=entry.get('topic', '')  # Store topic in phonetic field
        )
        db.session.add(word)

    book.word_count = len(entries)
    db.session.commit()

    return jsonify({
        "ok": True,
        "book_id": book.id,
        "title": book.title,
        "word_count": len(entries),
        "topics": list(set(e['topic'] for e in entries))
    })


def _parse_vocab_pdf(full_text):
    """Parse Chinese-English vocabulary pairs from PDF text.

    Supports both:
    1. Chinese-English vocab lists where one line contains both languages.
    2. Phrase lists where several English lines are followed by one or more Chinese gloss lines.
    """
    entries = []
    seen = set()
    current_topic = "General"
    pending_phrases = []
    lines = [_normalize_pdf_line(line) for line in full_text.splitlines()]

    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue

        if line.startswith("[例]") or line.startswith("【例】"):
            index += 1
            continue

        # Skip title/header lines
        if "托福" in line or "1000" in line or "分话题" in line:
            index += 1
            continue

        if re.fullmatch(r"List\s*\d+", line, re.IGNORECASE):
            current_topic = line.replace(" ", "")
            index += 1
            continue

        # Topic header (single English words like "Education", "Technology")
        if re.match(r"^[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)*$", line):
            current_topic = line
            index += 1
            continue

        mixed = _split_mixed_phrase_line(line)
        if mixed:
            english, chinese = mixed
            _append_vocab_entry(entries, seen, english, chinese, current_topic)
            index += 1
            continue

        if _is_translation_only_line(line):
            if pending_phrases:
                translation_parts = [line]
                index += 1
                while index < len(lines):
                    next_line = lines[index]
                    if not next_line:
                        index += 1
                        continue
                    if _is_translation_only_line(next_line):
                        translation_parts.append(next_line)
                        index += 1
                        continue
                    break
                translation = "；".join(_normalize_chinese_translation(part) for part in translation_parts if part)
                for phrase in pending_phrases:
                    _append_vocab_entry(entries, seen, phrase, translation, current_topic)
                pending_phrases = []
                continue
            index += 1
            continue

        if re.search(r"[A-Za-z]", line):
            pending_phrases.append(_normalize_english_phrase(line))

        index += 1

    return entries
