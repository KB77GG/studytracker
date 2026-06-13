import copy
import json
import re
import subprocess
import uuid
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import requests
from flask import Blueprint, current_app, jsonify, render_template, request, session
from flask_login import current_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.aliyun_asr import transcribe_audio_url
from api.tencent_soe import evaluate_pronunciation
from models import (
    StudentProfile,
    ToeflQuestionResponse,
    ToeflTestSubmission,
    User,
    db,
)


toefl_bp = Blueprint("toefl", __name__)

TOEFL_DATA_ROOT = Path(__file__).resolve().parent / "data" / "toefl_practice"
SAFE_EXAM_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}$")
SUBJECTS = {
    "reading": {"label": "Reading", "label_zh": "阅读", "minutes": 30},
    "listening": {"label": "Listening", "label_zh": "听力", "minutes": 29},
    "writing": {"label": "Writing", "label_zh": "写作", "minutes": 23},
    "speaking": {"label": "Speaking", "label_zh": "口语", "minutes": 16},
}
RECORDING_TOKEN_MAX_AGE = 24 * 60 * 60
MAX_RECORDING_BYTES = 20 * 1024 * 1024


def _load_manifest(exam_id: str) -> dict:
    if not SAFE_EXAM_ID_RE.fullmatch(exam_id or ""):
        return {}
    path = TOEFL_DATA_ROOT / exam_id / "manifest.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_is_published(manifest: dict) -> bool:
    return (
        bool(manifest)
        and manifest.get("publish_status") == "published"
        and manifest.get("duplicate_status") == "clear"
    )


def _load_source_exam(exam_id: str, subject: str) -> dict | None:
    if not SAFE_EXAM_ID_RE.fullmatch(exam_id or "") or subject not in SUBJECTS:
        return None
    if not _manifest_is_published(_load_manifest(exam_id)):
        return None
    path = TOEFL_DATA_ROOT / exam_id / f"{subject}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("questions"), list):
        return None
    return payload


def _question_is_displayable(question: dict) -> bool:
    response_type = question.get("response_type")
    if response_type == "mc":
        return len(question.get("options") or []) >= 2
    if response_type == "fill":
        return bool((question.get("passage") or {}).get("text"))
    if response_type == "order":
        return bool(_normalized_order_sequence(question.get("scramble_words")))
    if response_type in {"free", "record"}:
        return bool(question.get("prompt") or question.get("directive"))
    return False


def _question_is_gradable(question: dict) -> bool:
    response_type = question.get("response_type")
    answer = question.get("answer") or {}
    if response_type == "mc":
        option_keys = {
            str(option.get("key") or "").strip().lower()
            for option in question.get("options") or []
        }
        expected = set(_normalized_sequence(answer.get("keys")))
        return bool(option_keys) and bool(expected) and expected <= option_keys
    if response_type == "fill":
        return bool(answer.get("words"))
    if response_type == "order":
        available = Counter(_normalized_order_sequence(question.get("scramble_words")))
        required = Counter(_normalized_order_sequence(answer.get("ordered")))
        return bool(available) and bool(required) and not (required - available)
    return False


def _module_id(question_id: str) -> str:
    match = re.search(r"_m(\d+)_", question_id or "")
    return f"m{match.group(1)}" if match else "main"


def _question_task_type(subject: str, question: dict) -> str:
    directive = str(question.get("directive") or "").lower()
    if subject == "speaking":
        return "listen_repeat" if "listen and repeat" in directive else "interview"
    if subject == "writing" and question.get("response_type") == "free":
        return "email" if "email" in directive else "academic_discussion"
    return str(question.get("response_type") or "")


def _question_item_count(question: dict) -> int:
    if question.get("response_type") == "fill":
        return max(1, len((question.get("answer") or {}).get("words") or []))
    return 1


def _exam_identity(exam_id: str, manifest: dict) -> dict:
    if manifest:
        return {
            "title": manifest.get("title") or exam_id,
            "subtitle": manifest.get("subtitle") or "",
            "date": "",
            "volume": "",
            "source_kind": manifest.get("source_kind") or "official",
            "sort_key": manifest.get("sort_key") or exam_id,
        }
    return {
        "title": f"{exam_id[:10]} 真题 {exam_id.rsplit('_', 1)[-1]} 卷",
        "subtitle": "2026 新托福真题",
        "date": exam_id[:10],
        "volume": exam_id.rsplit("_", 1)[-1],
        "source_kind": "real_exam",
        "sort_key": exam_id,
    }


def public_exam_payload(exam_id: str, subject: str) -> dict | None:
    source = _load_source_exam(exam_id, subject)
    if not source:
        return None
    manifest = _load_manifest(exam_id)

    questions = []
    usable_item_count = 0
    for raw in source.get("questions") or []:
        if not isinstance(raw, dict) or not _question_is_displayable(raw):
            continue
        usable_item_count += _question_item_count(raw)
        question = copy.deepcopy(raw)
        question.pop("answer", None)
        question["module_id"] = _module_id(str(question.get("id") or ""))
        question["task_type"] = _question_task_type(subject, question)
        questions.append(question)

    audio_modules = []
    for module in (source.get("exam") or {}).get("audio_modules") or []:
        source_url = str(module.get("url") or "")
        filename = Path(source_url).name
        folder = "speaking" if subject == "speaking" else "audio"
        audio_modules.append({
            "id": module.get("id"),
            "label": module.get("label"),
            "url": (
                source_url
                if source_url.startswith("/static/")
                else f"/static/toefl/{folder}/{filename}" if filename else ""
            ),
        })

    subject_config = SUBJECTS[subject]
    identity = _exam_identity(exam_id, manifest)
    source_exam = source.get("exam") or {}
    return {
        "id": exam_id,
        **identity,
        "subject": subject,
        "subject_label": subject_config["label"],
        "subject_label_zh": subject_config["label_zh"],
        "duration_seconds": int(
            source_exam.get("duration_seconds") or subject_config["minutes"] * 60
        ),
        "module_durations": source_exam.get("module_durations") or {},
        "questions": questions,
        "item_count": usable_item_count,
        "audio_modules": audio_modules,
        "source_question_count": len(source.get("questions") or []),
        "omitted_question_count": len(source.get("questions") or []) - len(questions),
    }


def exam_catalog() -> list[dict]:
    exams = []
    if not TOEFL_DATA_ROOT.exists():
        return exams
    for exam_dir in TOEFL_DATA_ROOT.iterdir():
        if not exam_dir.is_dir() or not SAFE_EXAM_ID_RE.fullmatch(exam_dir.name):
            continue
        manifest = _load_manifest(exam_dir.name)
        if not _manifest_is_published(manifest):
            continue
        identity = _exam_identity(exam_dir.name, manifest)
        subjects = []
        for subject, config in SUBJECTS.items():
            payload = public_exam_payload(exam_dir.name, subject)
            if not payload:
                continue
            subjects.append({
                "id": subject,
                "label": config["label"],
                "label_zh": config["label_zh"],
                "question_count": len(payload["questions"]),
                "item_count": payload["item_count"],
                "omitted_question_count": payload["omitted_question_count"],
                "minutes": round(payload["duration_seconds"] / 60),
            })
        if subjects:
            exams.append({
                "id": exam_dir.name,
                **identity,
                "subjects": subjects,
            })
    return sorted(exams, key=lambda exam: exam["sort_key"], reverse=True)


def catalog_summary() -> dict:
    exams = exam_catalog()
    return {
        "exam_count": len(exams),
        "subject_count": sum(len(exam["subjects"]) for exam in exams),
        "question_count": sum(
            subject["item_count"]
            for exam in exams
            for subject in exam["subjects"]
        ),
    }


def _normalized_sequence(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value]


def _normalized_order_sequence(value) -> list[str]:
    return [
        token
        for token in _normalized_sequence(value)
        if token and not re.fullmatch(r"[^\w']+", token)
    ]


def _current_practice_profile() -> StudentProfile | None:
    if getattr(current_user, "is_authenticated", False):
        if current_user.role != User.ROLE_STUDENT:
            return None
        profile = StudentProfile.query.filter_by(
            user_id=current_user.id,
            is_deleted=False,
        ).first()
        if profile:
            return profile
        name = (current_user.display_name or current_user.username or "").strip()
        if name:
            return StudentProfile.query.filter_by(
                full_name=name,
                is_deleted=False,
            ).first()
        return None

    name = (session.get("practice_student_name") or "").strip()
    if not name:
        return None
    profile = StudentProfile.query.filter_by(
        full_name=name,
        is_deleted=False,
    ).first()
    if not profile:
        session.pop("practice_student_name", None)
    return profile


def _recording_actor(profile: StudentProfile | None) -> str | None:
    if profile:
        return f"student:{profile.id}"
    is_staff = bool(
        getattr(current_user, "is_authenticated", False)
        and current_user.role in {
            User.ROLE_ADMIN,
            User.ROLE_TEACHER,
            User.ROLE_ASSISTANT,
        }
    )
    if not is_staff and not session.get("classroom_unlocked"):
        return None
    actor = str(session.get("toefl_recording_actor") or "").strip()
    if not actor:
        actor = f"staff:{uuid.uuid4().hex}"
        session["toefl_recording_actor"] = actor
    return actor


def _recording_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="toefl-recording-v1",
    )


def _recording_root() -> Path:
    root = Path(current_app.config["UPLOAD_FOLDER"]) / "toefl"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _audio_extension(filename: str, mimetype: str) -> str | None:
    extension = Path(filename or "").suffix.lower().lstrip(".")
    allowed = {"webm", "ogg", "mp4", "m4a", "wav", "mp3"}
    if extension in allowed:
        return extension
    mime_map = {
        "audio/webm": "webm",
        "video/webm": "webm",
        "audio/ogg": "ogg",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
    }
    return mime_map.get((mimetype or "").split(";", 1)[0].lower())


def _convert_recording_to_mp3(source: Path, destination: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "48k",
        str(destination),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if completed.returncode != 0 or not destination.is_file():
        raise RuntimeError((completed.stderr or "ffmpeg conversion failed")[:500])


def _probe_audio_duration(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    try:
        return max(0.0, round(float(completed.stdout.strip()), 2))
    except (TypeError, ValueError):
        return 0.0


def _speech_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+", (value or "").lower())


def _evaluate_listen_repeat(reference: str, transcript: str, metrics: dict) -> dict:
    expected = _speech_tokens(reference)
    actual = _speech_tokens(transcript)
    if not actual:
        return {
            "status": "auto_scored",
            "score": 0,
            "score_max": 5,
            "task_type": "listen_repeat",
            "feedback_zh": "未识别到有效英语作答。",
            "alignment": {
                "similarity": 0.0,
                "content_recall": 0.0,
                "missing_words": expected,
                "replacements": [],
            },
            "audio_metrics": metrics,
            "confidence": "low",
        }

    matcher = SequenceMatcher(a=expected, b=actual, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    similarity = matcher.ratio()
    recall = matched / len(expected) if expected else 0.0
    missing_words = []
    replacements = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"delete", "replace"}:
            missing_words.extend(expected[i1:i2])
        if tag == "replace":
            replacements.append({
                "expected": " ".join(expected[i1:i2]),
                "heard_as": " ".join(actual[j1:j2]),
            })

    if actual == expected:
        score = 5
    elif similarity >= 0.84 and recall >= 0.84:
        score = 4
    elif similarity >= 0.62 and recall >= 0.62:
        score = 3
    elif similarity >= 0.30 or recall >= 0.35:
        score = 2
    else:
        score = 1

    if score >= 4:
        feedback = "复述基本完整；重点检查少量遗漏或替换词。"
    elif score == 3:
        feedback = "大部分内容已复述，但有多处遗漏或替换，原句意义可能受影响。"
    elif score == 2:
        feedback = "只完成了部分原句，建议先按意群记忆，再完整复述。"
    else:
        feedback = "有效复述内容较少，建议先听清关键词并缩短起始停顿。"

    return {
        "status": "auto_scored",
        "score": score,
        "score_max": 5,
        "task_type": "listen_repeat",
        "feedback_zh": feedback,
        "alignment": {
            "similarity": round(similarity * 100.0, 1),
            "content_recall": round(recall * 100.0, 1),
            "missing_words": missing_words[:12],
            "replacements": replacements[:8],
        },
        "audio_metrics": metrics,
        "confidence": "medium",
        "grading_engine": "asr_reference_alignment",
        "limitation_note": "分数基于独立 ASR 转写与原句对齐，是练习估分，不是 ETS 正式换算分。",
    }


def _evaluate_listen_repeat_soe(payload: dict, duration_seconds: float) -> dict:
    accuracy = round(float(payload.get("pron_accuracy") or 0.0), 1)
    fluency = round(float(payload.get("pron_fluency") or 0.0), 1)
    completion = round(float(payload.get("pron_completion") or 0.0), 1)
    if accuracy <= 0 and completion <= 0:
        score = 0
    elif completion >= 97 and accuracy >= 88 and fluency >= 75:
        score = 5
    elif completion >= 88 and accuracy >= 74:
        score = 4
    elif completion >= 65 and accuracy >= 58:
        score = 3
    elif completion >= 35 or accuracy >= 40:
        score = 2
    else:
        score = 1

    weak_words = []
    for item in payload.get("words") or []:
        if not isinstance(item, dict):
            continue
        try:
            word_accuracy = round(float(item.get("PronAccuracy") or 0.0), 1)
        except (TypeError, ValueError):
            continue
        if word_accuracy >= 75:
            continue
        weak_words.append({
            "word": str(item.get("Word") or "").strip(),
            "accuracy": word_accuracy,
        })
    weak_words.sort(key=lambda item: item["accuracy"])

    if score >= 4:
        feedback = "复述完整度较高，重点修正个别发音或轻微遗漏。"
    elif score == 3:
        feedback = "主要内容基本保留，但完整度或清晰度仍有明显损失。"
    elif score == 2:
        feedback = "只完成了部分原句，建议按意群记忆后再完整复述。"
    else:
        feedback = "有效复述较少，先抓住内容词并保证句子完整。"

    return {
        "status": "auto_scored",
        "score": score,
        "score_max": 5,
        "task_type": "listen_repeat",
        "feedback_zh": feedback,
        "pronunciation": {
            "accuracy": accuracy,
            "fluency": fluency,
            "completion": completion,
            "suggested_score_100": round(
                float(payload.get("suggested_score_100") or 0.0),
                1,
            ),
            "weak_words": weak_words[:8],
        },
        "audio_metrics": {
            "duration_seconds": duration_seconds,
            "audio_size_bytes": payload.get("audio_size_bytes"),
            "evidence": "tencent_soe",
        },
        "confidence": "high",
        "grading_engine": payload.get("engine") or "tencent_soe",
        "limitation_note": "0-5 为练习估分，不是 ETS 正式科目分换算。",
    }


def _extract_json_object(value: str) -> dict | None:
    text_value = (value or "").strip()
    try:
        parsed = json.loads(text_value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text_value.find("{")
        end = text_value.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text_value[start : end + 1])
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None


def _deepseek_json(system_prompt: str, payload: dict, max_tokens: int = 1400) -> tuple[dict | None, str]:
    api_key = current_app.config.get("DEEPSEEK_API_KEY")
    if not api_key:
        return None, "missing_deepseek_key"
    base_url = (
        current_app.config.get("DEEPSEEK_CHAT_URL")
        or f"{str(current_app.config.get('DEEPSEEK_API_BASE') or 'https://api.deepseek.com').rstrip('/')}/v1/chat/completions"
    )
    model = current_app.config.get("DEEPSEEK_MODEL") or "deepseek-chat"
    try:
        response = requests.post(
            base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                "temperature": 0.1,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=min(
                45.0,
                float(current_app.config.get("DEEPSEEK_TIMEOUT") or 45),
            ),
        )
        response.raise_for_status()
        raw = response.json()
        content = raw.get("choices", [{}])[0].get("message", {}).get("content", "")
        parsed = _extract_json_object(content)
        if not parsed:
            return None, "invalid_ai_json"
        parsed["_model"] = raw.get("model") or model
        return parsed, ""
    except (requests.RequestException, ValueError, TypeError) as exc:
        current_app.logger.warning("TOEFL grading request failed: %s", exc)
        return None, "ai_grading_failed"


def _score_0_to_5(value) -> int:
    try:
        return max(0, min(5, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def _normalize_ai_grade(payload: dict | None, task_type: str, error: str = "") -> dict:
    if not payload:
        return {
            "status": "pending_review",
            "score": None,
            "score_max": 5,
            "task_type": task_type,
            "feedback_zh": "作答已保存，自动评分暂不可用，等待教师复核。",
            "grading_error": error,
        }
    score = _score_0_to_5(payload.get("score"))
    return {
        "status": "auto_scored",
        "score": score,
        "score_max": 5,
        "task_type": task_type,
        "feedback_zh": str(payload.get("feedback_zh") or "").strip(),
        "strengths": [
            str(item).strip()
            for item in payload.get("strengths") or []
            if str(item).strip()
        ][:3],
        "improvements": [
            str(item).strip()
            for item in payload.get("improvements") or []
            if str(item).strip()
        ][:3],
        "dimensions": (
            payload.get("dimensions")
            if isinstance(payload.get("dimensions"), dict)
            else {}
        ),
        "grading_model": payload.get("_model"),
        "limitation_note": "机器评分为 0-5 练习估分，可由教师复核覆盖。",
    }


def _evaluate_interview(
    question: str,
    transcript: str,
    metrics: dict,
) -> dict:
    if not _speech_tokens(transcript):
        return {
            "status": "auto_scored",
            "score": 0,
            "score_max": 5,
            "task_type": "interview",
            "feedback_zh": "未识别到有效英语回答。",
            "audio_metrics": metrics,
            "confidence": "low",
        }
    payload, error = _deepseek_json(
        (
            "You are a TOEFL iBT 2026 Take an Interview evaluator. "
            "Use a holistic integer 0-5 practice score. Judge task response and relevance, "
            "elaboration, language accuracy and precision, and delivery only from the supplied "
            "local-ASR transcript and audio metrics. Do not claim that you heard pronunciation. "
            "Return JSON only."
        ),
        {
            "question": question,
            "transcript": transcript,
            "audio_metrics": metrics,
            "rubric": {
                "5": "fully addresses, clear, fluent, well elaborated, precise language",
                "4": "addresses and elaborates, generally clear, minor limitations",
                "3": "on topic but underdeveloped or choppy, limited precision",
                "2": "minimal relevant support and meaning often difficult to discern",
                "1": "vaguely connected, isolated words or phrases",
                "0": "blank, no English, unrelated, or unintelligible",
            },
            "output_schema": {
                "score": "integer 0-5",
                "feedback_zh": "concise Chinese summary",
                "strengths": ["Chinese string"],
                "improvements": ["Chinese string"],
                "dimensions": {
                    "task_response": "integer 0-5",
                    "elaboration": "integer 0-5",
                    "language": "integer 0-5",
                    "delivery_estimate": "integer 0-5",
                },
            },
        },
    )
    grade = _normalize_ai_grade(payload, "interview", error)
    grade["audio_metrics"] = metrics
    grade["confidence"] = "medium" if payload else "low"
    grade["grading_engine"] = "aliyun_asr+deepseek"
    return grade


def _evaluate_writing(question: dict, response_text: str) -> dict:
    task_type = _question_task_type("writing", question)
    if not response_text.strip():
        return {
            "status": "auto_scored",
            "score": 0,
            "score_max": 5,
            "task_type": task_type,
            "feedback_zh": "未作答。",
        }
    if task_type == "email":
        rubric = {
            "focus": "communicative purpose, elaboration, language facility, and social conventions",
            "5": "effective, clearly expressed, precise and idiomatic, appropriate register, almost no errors",
            "4": "mostly effective, adequately elaborated, appropriate wording and conventions, few errors",
            "3": "generally accomplishes the task but only partial elaboration and noticeable errors",
            "2": "mostly ineffective, limited or irrelevant elaboration and accumulated errors",
            "1": "very little elaboration, disconnected language, serious frequent errors",
            "0": "blank, non-English, copied, unrelated, or arbitrary text",
        }
        dimensions = {
            "task_fulfillment": "integer 0-5",
            "elaboration": "integer 0-5",
            "language": "integer 0-5",
            "register_and_conventions": "integer 0-5",
        }
    else:
        rubric = {
            "focus": "relevance, contribution to the discussion, elaboration, and language facility",
            "5": "relevant, very clear, well elaborated, precise and idiomatic, almost no errors",
            "4": "relevant, easily understood, adequately elaborated, few errors",
            "3": "mostly relevant and understandable, some elaboration gaps and noticeable errors",
            "2": "partially relevant, poorly elaborated, limited language and accumulated errors",
            "1": "few coherent ideas, severely limited language, serious frequent errors",
            "0": "blank, non-English, copied, unrelated, or arbitrary text",
        }
        dimensions = {
            "relevance": "integer 0-5",
            "elaboration": "integer 0-5",
            "organization": "integer 0-5",
            "language": "integer 0-5",
        }

    payload, error = _deepseek_json(
        (
            "You are a TOEFL iBT 2026 Writing evaluator. "
            "Assign one holistic integer 0-5 practice score using the supplied task-specific rubric. "
            "Do not invent an ETS scaled score. Return JSON only."
        ),
        {
            "task_type": task_type,
            "prompt": question.get("prompt") or "",
            "student_response": response_text,
            "word_count": len(response_text.split()),
            "rubric": rubric,
            "output_schema": {
                "score": "integer 0-5",
                "feedback_zh": "concise Chinese summary",
                "strengths": ["Chinese string"],
                "improvements": ["Chinese string"],
                "dimensions": dimensions,
            },
        },
    )
    return _normalize_ai_grade(payload, task_type, error)


def _load_recording_metadata(
    token: str,
    actor: str,
    exam_id: str,
    question_id: str,
) -> dict | None:
    try:
        signed = _recording_serializer().loads(
            token,
            max_age=RECORDING_TOKEN_MAX_AGE,
        )
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(signed, dict):
        return None
    if (
        signed.get("actor") != actor
        or signed.get("exam_id") != exam_id
        or signed.get("question_id") != question_id
    ):
        return None
    relative = Path(str(signed.get("metadata_path") or ""))
    root = _recording_root().resolve()
    metadata_path = (root / relative).resolve()
    if root not in metadata_path.parents or not metadata_path.is_file():
        return None
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def grade_exam_payload(exam_id: str, subject: str, responses: dict) -> dict | None:
    source = _load_source_exam(exam_id, subject)
    public = public_exam_payload(exam_id, subject)
    if not source or not public:
        return None

    usable_ids = {question["id"] for question in public["questions"]}
    results = []
    auto_total = 0
    correct_count = 0
    manual_count = 0
    review_only_count = 0

    for question in source.get("questions") or []:
        question_id = question.get("id")
        if question_id not in usable_ids:
            continue
        response_type = question.get("response_type")
        response = responses.get(question_id)
        if response_type in {"free", "record"}:
            manual_count += 1
            results.append({"id": question_id, "status": "manual"})
            continue
        if not _question_is_gradable(question):
            review_only_count += 1
            results.append({"id": question_id, "status": "review_only"})
            continue

        answer = question.get("answer") or {}
        if response_type == "mc":
            auto_total += 1
            expected = _normalized_sequence(answer.get("keys"))
            actual = [str(response or "").strip().lower()] if response else []
            is_correct = actual == expected
            correct_count += int(is_correct)
            result = {
                "id": question_id,
                "status": "correct" if is_correct else "incorrect",
                "correct_items": int(is_correct),
                "total_items": 1,
            }
        elif response_type == "fill":
            expected = _normalized_sequence(answer.get("words"))
            actual = _normalized_sequence(response)
            auto_total += len(expected)
            correct_items = sum(
                index < len(actual) and actual[index] == expected_value
                for index, expected_value in enumerate(expected)
            )
            correct_count += correct_items
            result = {
                "id": question_id,
                "status": "correct" if correct_items == len(expected) else "incorrect",
                "correct_items": correct_items,
                "total_items": len(expected),
            }
        else:
            auto_total += 1
            expected = _normalized_order_sequence(answer.get("ordered"))
            actual = _normalized_order_sequence(response)
            is_correct = actual == expected
            correct_count += int(is_correct)
            result = {
                "id": question_id,
                "status": "correct" if is_correct else "incorrect",
                "correct_items": int(is_correct),
                "total_items": 1,
            }
        results.append(result)

    accuracy = round(correct_count / auto_total * 100, 1) if auto_total else 0.0
    return {
        "ok": True,
        "correct": correct_count,
        "auto_total": auto_total,
        "manual_count": manual_count,
        "review_only_count": review_only_count,
        "accuracy": accuracy,
        "results": results,
    }


def _apply_constructed_response_grades(
    exam_id: str,
    subject: str,
    responses: dict,
    recording_tokens: dict,
    profile: StudentProfile | None,
    result: dict,
) -> tuple[dict, dict]:
    source = _load_source_exam(exam_id, subject) or {}
    public = public_exam_payload(exam_id, subject) or {}
    usable_ids = {question["id"] for question in public.get("questions") or []}
    result_by_id = {item["id"]: item for item in result.get("results") or []}
    response_metadata = {}
    constructed_scores = []
    pending_review_count = 0
    machine_scored_count = 0
    actor = _recording_actor(profile)

    for question in source.get("questions") or []:
        question_id = str(question.get("id") or "")
        if question_id not in usable_ids:
            continue
        response_type = question.get("response_type")
        if response_type == "free":
            evaluation = _evaluate_writing(
                question,
                str(responses.get(question_id) or ""),
            )
            response_metadata[question_id] = {"evaluation": evaluation}
        elif response_type == "record":
            metadata = None
            token = str(recording_tokens.get(question_id) or "")
            if token and actor:
                metadata = _load_recording_metadata(
                    token,
                    actor,
                    exam_id,
                    question_id,
                )
            if metadata:
                evaluation = metadata.get("evaluation") or {
                    "status": "pending_review",
                    "score": None,
                    "score_max": 5,
                    "task_type": _question_task_type(subject, question),
                }
                response_metadata[question_id] = metadata
            else:
                evaluation = {
                    "status": "auto_scored",
                    "score": 0,
                    "score_max": 5,
                    "task_type": _question_task_type(subject, question),
                    "feedback_zh": "未提交有效录音。",
                }
                response_metadata[question_id] = {"evaluation": evaluation}
        else:
            continue

        row = result_by_id.get(question_id) or {"id": question_id}
        row.update({
            "status": evaluation.get("status") or "pending_review",
            "task_type": evaluation.get("task_type"),
            "score": evaluation.get("score"),
            "score_max": evaluation.get("score_max") or 5,
            "feedback_zh": evaluation.get("feedback_zh") or "",
            "strengths": evaluation.get("strengths") or [],
            "improvements": evaluation.get("improvements") or [],
        })
        result_by_id[question_id] = row
        if evaluation.get("score") is not None:
            constructed_scores.append(float(evaluation["score"]))
        if evaluation.get("status") == "pending_review":
            pending_review_count += 1
        else:
            machine_scored_count += 1

    result["results"] = [
        result_by_id.get(item["id"], item)
        for item in result.get("results") or []
    ]
    result["manual_count"] = pending_review_count
    result["pending_review_count"] = pending_review_count
    result["machine_scored_count"] = machine_scored_count
    result["practice_score"] = (
        round(sum(constructed_scores) / len(constructed_scores), 1)
        if constructed_scores
        else None
    )
    result["practice_score_max"] = 5 if constructed_scores else None
    result["score_note"] = (
        "0-5 为练习估分；ETS 正式科目分由统计程序生成，本系统不做伪换算。"
        if constructed_scores
        else ""
    )
    return result, response_metadata


def _response_text(value) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


def _persist_submission(
    profile: StudentProfile,
    public: dict,
    responses: dict,
    result: dict,
    response_metadata: dict,
    duration_seconds: int,
) -> ToeflTestSubmission:
    latest = (
        ToeflTestSubmission.query.filter_by(
            student_id=profile.id,
            exam_id=public["id"],
            subject=public["subject"],
        )
        .order_by(ToeflTestSubmission.attempt_number.desc())
        .first()
    )
    attempt_number = int(latest.attempt_number or 0) + 1 if latest else 1
    now = datetime.utcnow()
    submission = ToeflTestSubmission(
        student_id=profile.id,
        student_name=profile.full_name,
        exam_id=public["id"],
        exam_title=public.get("title"),
        subject=public["subject"],
        attempt_number=attempt_number,
        status=(
            "review_pending"
            if int(result.get("pending_review_count") or 0)
            else "graded"
        ),
        correct_count=int(result.get("correct") or 0),
        auto_total=int(result.get("auto_total") or 0),
        accuracy=float(result.get("accuracy") or 0.0),
        practice_score=result.get("practice_score"),
        score_max=result.get("practice_score_max"),
        duration_seconds=max(0, int(duration_seconds or 0)),
        responses_json=json.dumps(responses, ensure_ascii=False),
        results_json=json.dumps(result.get("results") or [], ensure_ascii=False),
        submitted_at=now,
    )
    db.session.add(submission)
    db.session.flush()

    results_by_id = {
        str(item.get("id") or ""): item
        for item in result.get("results") or []
        if isinstance(item, dict)
    }
    for question in public.get("questions") or []:
        question_id = str(question.get("id") or "")
        response_result = results_by_id.get(question_id) or {}
        metadata = response_metadata.get(question_id) or {}
        evaluation = metadata.get("evaluation") or {}
        response_type = str(question.get("response_type") or "")
        machine_score = response_result.get("score")
        score_max = response_result.get("score_max")
        if response_type not in {"free", "record"}:
            machine_score = float(response_result.get("correct_items") or 0)
            score_max = float(response_result.get("total_items") or 1)
        grading_engine = "answer_key"
        if response_type == "record":
            grading_engine = (
                evaluation.get("grading_engine")
                or (
                    "tencent_soe"
                    if question.get("task_type") == "listen_repeat"
                    else "aliyun_asr+deepseek"
                )
            )
        elif response_type == "free":
            grading_engine = "deepseek"

        db.session.add(ToeflQuestionResponse(
            submission_id=submission.id,
            question_id=question_id,
            question_number=str(question.get("number") or ""),
            response_type=response_type,
            task_type=question.get("task_type"),
            response_text=_response_text(responses.get(question_id)),
            audio_url=metadata.get("audio_url"),
            transcript=metadata.get("transcript"),
            machine_score=machine_score,
            final_score=machine_score,
            score_max=score_max,
            status=str(response_result.get("status") or "submitted"),
            grading_engine=grading_engine,
            result_json=json.dumps(
                evaluation or response_result,
                ensure_ascii=False,
            ),
        ))

    db.session.commit()
    return submission


def _serialize_submission(submission: ToeflTestSubmission) -> dict:
    return {
        "id": submission.id,
        "exam_id": submission.exam_id,
        "exam_title": submission.exam_title,
        "subject": submission.subject,
        "attempt_number": submission.attempt_number,
        "status": submission.status,
        "correct": submission.correct_count,
        "auto_total": submission.auto_total,
        "accuracy": submission.accuracy,
        "practice_score": submission.practice_score,
        "score_max": submission.score_max,
        "duration_seconds": submission.duration_seconds,
        "submitted_at": (
            submission.submitted_at.isoformat()
            if submission.submitted_at
            else None
        ),
    }


def _is_toefl_staff() -> bool:
    return bool(
        getattr(current_user, "is_authenticated", False)
        and current_user.role in {
            User.ROLE_ADMIN,
            User.ROLE_TEACHER,
            User.ROLE_ASSISTANT,
        }
    )


def _can_access_submission(submission: ToeflTestSubmission) -> bool:
    if _is_toefl_staff():
        return True
    profile = _current_practice_profile()
    return bool(profile and submission.student_id == profile.id)


def _serialize_question_response(row: ToeflQuestionResponse) -> dict:
    try:
        result = json.loads(row.result_json or "{}")
    except json.JSONDecodeError:
        result = {}
    return {
        "id": row.id,
        "question_id": row.question_id,
        "question_number": row.question_number,
        "response_type": row.response_type,
        "task_type": row.task_type,
        "response_text": row.response_text or "",
        "audio_url": row.audio_url or "",
        "transcript": row.transcript or "",
        "machine_score": row.machine_score,
        "teacher_score": row.teacher_score,
        "final_score": row.final_score,
        "score_max": row.score_max,
        "status": row.status,
        "grading_engine": row.grading_engine,
        "result": result if isinstance(result, dict) else {},
        "teacher_feedback": row.teacher_feedback or "",
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }


@toefl_bp.get("/toefl/tests")
def index():
    return render_template("toefl/index.html", exams=exam_catalog())


@toefl_bp.get("/toefl/test/<exam_id>/<subject>")
def exam(exam_id: str, subject: str):
    payload = public_exam_payload(exam_id, subject)
    if not payload:
        return "托福套卷或科目不存在", 404
    profile = _current_practice_profile()
    payload["save_enabled"] = bool(profile)
    payload["student_name"] = profile.full_name if profile else ""
    return render_template("toefl/exam.html", exam=payload)


@toefl_bp.post("/api/toefl/test/<exam_id>/speaking/recording")
def upload_speaking_recording(exam_id: str):
    source = _load_source_exam(exam_id, "speaking")
    public = public_exam_payload(exam_id, "speaking")
    if not source or not public:
        return jsonify({"ok": False, "error": "exam_not_found"}), 404

    profile = _current_practice_profile()
    actor = _recording_actor(profile)
    if not actor:
        return jsonify({
            "ok": False,
            "error": "student_not_verified",
            "message": "请先在刷题首页验证学生姓名。",
        }), 401

    question_id = str(request.form.get("question_id") or "")
    questions = {
        str(question.get("id") or ""): question
        for question in source.get("questions") or []
    }
    question = questions.get(question_id)
    if not question or question.get("response_type") != "record":
        return jsonify({"ok": False, "error": "question_not_found"}), 404

    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"ok": False, "error": "missing_audio"}), 400
    extension = _audio_extension(audio_file.filename, audio_file.mimetype)
    if not extension:
        return jsonify({"ok": False, "error": "unsupported_audio"}), 400

    actor_folder = f"student_{profile.id}" if profile else re.sub(r"[^a-zA-Z0-9_-]", "_", actor)
    destination_dir = _recording_root() / actor_folder / exam_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    stem = uuid.uuid4().hex
    raw_path = destination_dir / f"{stem}.{extension}"
    mp3_path = destination_dir / f"{stem}.mp3"
    metadata_path = destination_dir / f"{stem}.json"
    retained_audio_path = mp3_path
    audio_file.save(str(raw_path))
    if raw_path.stat().st_size > MAX_RECORDING_BYTES:
        raw_path.unlink(missing_ok=True)
        return jsonify({"ok": False, "error": "audio_too_large"}), 413

    conversion_error = ""
    try:
        if extension == "mp3":
            raw_path.replace(mp3_path)
        else:
            _convert_recording_to_mp3(raw_path, mp3_path)
            raw_path.unlink(missing_ok=True)
    except Exception as exc:
        current_app.logger.exception(
            "TOEFL speaking conversion failed exam=%s question=%s",
            exam_id,
            question_id,
        )
        conversion_error = str(exc)[:200]
        if not mp3_path.is_file() and raw_path.is_file():
            retained_audio_path = raw_path

    upload_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    audio_relative = retained_audio_path.resolve().relative_to(upload_root).as_posix()
    audio_url = f"/uploads/{audio_relative}"
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip()
    base_url = request.host_url.rstrip("/")
    if forwarded_proto:
        base_url = re.sub(r"^https?://", f"{forwarded_proto}://", base_url)
    absolute_audio_url = f"{base_url}{audio_url}"
    task_type = _question_task_type("speaking", question)
    transcript = ""
    metrics = {
        "duration_seconds": _probe_audio_duration(retained_audio_path),
        "evidence": "recording_saved",
    }
    evaluation = None
    analysis_errors = {}

    if conversion_error:
        analysis_errors["conversion"] = conversion_error
    elif task_type == "listen_repeat":
        soe_ok, soe_payload = evaluate_pronunciation(
            absolute_audio_url,
            str(question.get("prompt") or ""),
        )
        if soe_ok:
            evaluation = _evaluate_listen_repeat_soe(
                soe_payload,
                metrics["duration_seconds"],
            )
            metrics = evaluation.get("audio_metrics") or metrics
        else:
            analysis_errors["tencent_soe"] = soe_payload
            asr_ok, asr_payload = transcribe_audio_url(absolute_audio_url)
            if asr_ok:
                transcript = str(asr_payload.get("transcript") or "").strip()
                metrics = asr_payload.get("audio_metrics") or metrics
                metrics["evidence"] = "aliyun_asr_fallback"
                evaluation = _evaluate_listen_repeat(
                    str(question.get("prompt") or ""),
                    transcript,
                    metrics,
                )
            else:
                analysis_errors["aliyun_asr"] = asr_payload
    else:
        asr_ok, asr_payload = transcribe_audio_url(absolute_audio_url)
        if asr_ok:
            transcript = str(asr_payload.get("transcript") or "").strip()
            metrics = asr_payload.get("audio_metrics") or metrics
            metrics["evidence"] = "aliyun_asr"
            evaluation = _evaluate_interview(
                str(question.get("prompt") or ""),
                transcript,
                metrics,
            )
        else:
            analysis_errors["aliyun_asr"] = asr_payload

    if evaluation is None:
        evaluation = {
            "status": "pending_review",
            "score": None,
            "score_max": 5,
            "task_type": task_type,
            "feedback_zh": "录音已保存，自动分析暂不可用，等待教师复核。",
            "grading_error": analysis_errors,
        }

    metadata_relative = metadata_path.resolve().relative_to(
        _recording_root().resolve()
    ).as_posix()
    metadata = {
        "exam_id": exam_id,
        "question_id": question_id,
        "task_type": task_type,
        "audio_url": audio_url,
        "transcript": transcript,
        "audio_metrics": metrics,
        "evaluation": evaluation,
        "created_at": datetime.utcnow().isoformat(),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )
    token = _recording_serializer().dumps({
        "actor": actor,
        "exam_id": exam_id,
        "question_id": question_id,
        "metadata_path": metadata_relative,
    })
    return jsonify({
        "ok": True,
        "recording_token": token,
        "audio_url": metadata["audio_url"],
        "transcript": transcript,
        "evaluation": evaluation,
    })


@toefl_bp.post("/api/toefl/test/<exam_id>/<subject>/grade")
def grade(exam_id: str, subject: str):
    body = request.get_json(silent=True) or {}
    responses = body.get("responses")
    if not isinstance(responses, dict):
        return jsonify({"ok": False, "error": "invalid_responses"}), 400
    result = grade_exam_payload(exam_id, subject, responses)
    if not result:
        return jsonify({"ok": False, "error": "exam_not_found"}), 404
    profile = _current_practice_profile()
    recording_tokens = (
        body.get("recording_tokens")
        if isinstance(body.get("recording_tokens"), dict)
        else {}
    )
    response_metadata = {}
    if subject in {"writing", "speaking"}:
        result, response_metadata = _apply_constructed_response_grades(
            exam_id,
            subject,
            responses,
            recording_tokens,
            profile,
            result,
        )
    try:
        duration_seconds = max(0, int(body.get("duration_seconds") or 0))
    except (TypeError, ValueError):
        duration_seconds = 0
    public = public_exam_payload(exam_id, subject)
    submission = None
    if profile and public:
        submission = _persist_submission(
            profile,
            public,
            responses,
            result,
            response_metadata,
            duration_seconds,
        )
    result["synced"] = bool(submission)
    result["student_name"] = profile.full_name if profile else ""
    result["submission"] = _serialize_submission(submission) if submission else None
    return jsonify(result)


@toefl_bp.get("/api/toefl/submissions")
def submission_history():
    profile = _current_practice_profile()
    if not profile:
        return jsonify({"ok": False, "error": "student_not_verified"}), 401
    query = ToeflTestSubmission.query.filter_by(student_id=profile.id)
    exam_id = str(request.args.get("exam_id") or "").strip()
    subject = str(request.args.get("subject") or "").strip()
    if exam_id:
        query = query.filter_by(exam_id=exam_id)
    if subject in SUBJECTS:
        query = query.filter_by(subject=subject)
    rows = query.order_by(ToeflTestSubmission.submitted_at.desc()).limit(30).all()
    return jsonify({
        "ok": True,
        "student_name": profile.full_name,
        "submissions": [_serialize_submission(row) for row in rows],
    })


@toefl_bp.get("/api/toefl/submissions/<int:submission_id>")
def submission_detail(submission_id: int):
    submission = ToeflTestSubmission.query.get(submission_id)
    if not submission:
        return jsonify({"ok": False, "error": "submission_not_found"}), 404
    if not _can_access_submission(submission):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    return jsonify({
        "ok": True,
        "submission": _serialize_submission(submission),
        "student_name": submission.student_name,
        "responses": [
            _serialize_question_response(row)
            for row in sorted(
                submission.responses,
                key=lambda item: item.id,
            )
        ],
    })


@toefl_bp.patch("/api/toefl/responses/<int:response_id>/review")
def review_question_response(response_id: int):
    if not _is_toefl_staff():
        return jsonify({"ok": False, "error": "forbidden"}), 403
    row = ToeflQuestionResponse.query.get(response_id)
    if not row:
        return jsonify({"ok": False, "error": "response_not_found"}), 404
    if row.response_type not in {"free", "record"}:
        return jsonify({"ok": False, "error": "objective_score_locked"}), 400
    body = request.get_json(silent=True) or {}
    try:
        score = float(body.get("score"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_score"}), 400
    if score < 0 or score > 5:
        return jsonify({"ok": False, "error": "invalid_score"}), 400

    row.teacher_score = round(score, 1)
    row.final_score = row.teacher_score
    row.teacher_feedback = str(body.get("feedback") or "").strip()[:4000]
    row.reviewed_by = current_user.id
    row.reviewed_at = datetime.utcnow()
    row.status = "reviewed"

    submission = row.submission
    constructed = [
        response
        for response in submission.responses
        if response.response_type in {"free", "record"}
        and response.final_score is not None
    ]
    submission.practice_score = (
        round(sum(float(item.final_score) for item in constructed) / len(constructed), 1)
        if constructed
        else None
    )
    submission.score_max = 5 if constructed else None
    submission.status = (
        "review_pending"
        if any(item.status == "pending_review" for item in submission.responses)
        else "graded"
    )
    try:
        stored_results = json.loads(submission.results_json or "[]")
    except json.JSONDecodeError:
        stored_results = []
    if isinstance(stored_results, list):
        for item in stored_results:
            if isinstance(item, dict) and item.get("id") == row.question_id:
                item["score"] = row.final_score
                item["status"] = "reviewed"
                item["teacher_feedback"] = row.teacher_feedback
        submission.results_json = json.dumps(stored_results, ensure_ascii=False)
    db.session.commit()
    return jsonify({
        "ok": True,
        "response": _serialize_question_response(row),
        "submission": _serialize_submission(submission),
    })
