import copy
import json
import re
from collections import Counter
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request


toefl_bp = Blueprint("toefl", __name__)

TOEFL_DATA_ROOT = Path(__file__).resolve().parent / "data" / "toefl_practice"
SAFE_EXAM_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{2,63}$")
SUBJECTS = {
    "reading": {"label": "Reading", "label_zh": "阅读", "minutes": 30},
    "listening": {"label": "Listening", "label_zh": "听力", "minutes": 29},
    "writing": {"label": "Writing", "label_zh": "写作", "minutes": 23},
    "speaking": {"label": "Speaking", "label_zh": "口语", "minutes": 16},
}


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


@toefl_bp.get("/toefl/tests")
def index():
    return render_template("toefl/index.html", exams=exam_catalog())


@toefl_bp.get("/toefl/test/<exam_id>/<subject>")
def exam(exam_id: str, subject: str):
    payload = public_exam_payload(exam_id, subject)
    if not payload:
        return "托福套卷或科目不存在", 404
    return render_template("toefl/exam.html", exam=payload)


@toefl_bp.post("/api/toefl/test/<exam_id>/<subject>/grade")
def grade(exam_id: str, subject: str):
    body = request.get_json(silent=True) or {}
    responses = body.get("responses")
    if not isinstance(responses, dict):
        return jsonify({"ok": False, "error": "invalid_responses"}), 400
    result = grade_exam_payload(exam_id, subject, responses)
    if not result:
        return jsonify({"ok": False, "error": "exam_not_found"}), 404
    return jsonify(result)
