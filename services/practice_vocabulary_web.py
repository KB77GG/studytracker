"""Web-only presentation and transport adapter for existing vocabulary services."""

from __future__ import annotations

import json
from copy import deepcopy

from sqlalchemy import func

from dictation_answers import canonical_vocabulary_word
from models import (
    DictationBook,
    Task,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyTaskSettlement,
    db,
)
from services import vocabulary_group_learning as learning
from services.task_date_gate import task_date_access
from services.vocabulary_autonomous_review import review_preflight
from services.vocabulary_mastery import is_vocabulary_v2_task

GOAL_LABELS = {
    "reading": "阅读词汇",
    "listening": "听力词汇",
    "writing": "写作词汇",
    "comprehensive": "综合训练",
}
PROMPT_FIELDS = {
    "en_to_zh": {"word", "phonetic", "instruction", "audio_url", "audio_tts_url"},
    "zh_to_en": {"meaning", "instruction", "input_hint"},
    "audio_to_en": {"instruction", "input_hint", "audio_url", "audio_tts_url"},
    "audio_to_zh": {"instruction", "input_hint", "audio_url", "audio_tts_url"},
    "context_choice": {
        "instruction",
        "sentence",
        "target_word",
        "translation",
        "translation_label",
    },
    "context_fill": {"instruction", "sentence", "translation", "translation_label", "input_hint"},
}


class PracticeVocabularyError(Exception):
    def __init__(self, error, status_code=400, **details):
        self.error, self.status_code, self.details = error, status_code, details
        super().__init__(error)


def json_value(raw, default):
    try:
        value = json.loads(raw or "null")
    except (ValueError, TypeError):
        return default
    return value if isinstance(value, type(default)) else default


def owned_task(student, task_id):
    task = Task.query.filter(Task.id == task_id, Task.cancelled_at.is_(None)).first()
    if not task or task.student_name != student.profile.full_name:
        raise PracticeVocabularyError("task_not_found", 404)
    if not is_vocabulary_v2_task(task):
        raise PracticeVocabularyError("task_not_vocabulary_v2", 409)
    return task


def task_metadata(task):
    book = db.session.get(DictationBook, task.dictation_book_id)
    title = book.title if book else "词汇任务"
    start, end = task.dictation_word_start, task.dictation_word_end
    scope = f"第 {start or 1}–{end} 词" if end else f"第 {start or 1} 词起"
    goal = str(task.vocabulary_goal or "").strip().lower()
    return {
        "id": task.id,
        "title": task.detail or f"{title} · {scope}",
        "book_id": task.dictation_book_id,
        "book_title": title,
        "word_start": start,
        "word_end": end,
        "scope": scope,
        "goal": goal,
        "goal_label": GOAL_LABELS.get(goal, "词汇学习"),
    }


def envelope(student, task, stage, **data):
    access = task_date_access(task)
    return {
        "ok": True,
        "stage": stage,
        "task": task_metadata(task),
        "access": {**access.as_dict(), "label": access.label},
        "identity_key": student.identity_key,
        **data,
    }


def stable_hash(value):
    """FNV-1a over UTF-16 code units, matching JavaScript charCodeAt."""
    data = str(value or "").encode("utf-16-le", "surrogatepass")
    result = 2166136261
    for index in range(0, len(data), 2):
        result = ((result ^ (data[index] | data[index + 1] << 8)) * 16777619) & 0xFFFFFFFF
    return result


def meaning_choice_options(question, familiarity):
    """Mirror vocabulary-interaction.js without exposing the source meanings."""
    supplied = (question.get("question") or {}).get("options") or []
    candidates, seen = [], set()

    def add(identifier, label):
        label = str(label or "").strip()
        if label and label not in seen:
            seen.add(label)
            candidates.append(
                {"id": str(identifier or f"meaning-{len(candidates) + 1}").strip(), "label": label}
            )

    for option in supplied:
        add(option.get("id"), option.get("label"))
    target = None
    if not supplied:
        row = next(
            (row for row in familiarity if str(row.get("word_id")) == str(question.get("word_id"))),
            None,
        )
        if row:
            add(f"meaning-{row.get('word_id')}", row.get("meaning"))
            target = candidates[0] if candidates else None
        for row in familiarity:
            add(f"meaning-{row.get('word_id')}", row.get("meaning"))
    seed = (
        question.get("question_id")
        or question.get("learning_question_id")
        or question.get("word_id")
        or ""
    )
    if target:
        others = sorted(
            (row for row in candidates if row is not target),
            key=lambda row: stable_hash(f"{seed}|pick|{row['label']}"),
        )[:3]
        candidates = [target, *others]
    return sorted(candidates, key=lambda row: stable_hash(f"{seed}|order|{row['label']}"))[:4]


def sanitize_question(question, *, reveal=False):
    question = deepcopy(question)
    for key in list(question):
        if key.startswith(("first_", "retry_")) or key in {
            "revealed_answer",
            "revealed_answer_option_id",
            "answer_feedback",
        }:
            if not reveal:
                question.pop(key, None)
    snapshot = question.get("question") or {}
    mode = question.get("mode") or snapshot.get("mode")
    allowed = PROMPT_FIELDS.get(mode, {"instruction"})
    clean_snapshot = {
        key: deepcopy(snapshot[key])
        for key in ("question_id", "mode", "context_kind", "answer_type", "numeric_kind")
        if key in snapshot
    }
    clean_snapshot["prompt"] = {
        key: value for key, value in (snapshot.get("prompt") or {}).items() if key in allowed
    }
    if mode in {"audio_to_zh", "context_choice"}:
        clean_snapshot["options"] = [
            {"id": row.get("id"), "label": row.get("label")}
            for row in snapshot.get("options") or []
        ]
    question["question"] = clean_snapshot
    return question


def sanitize_flow(payload, flow=None):
    """Remove test/retest answers, including those carried by error snapshots."""
    result = deepcopy(payload)
    familiarity = result.get("familiarity") or []
    question = result.get("current_question")
    if question:
        if question.get("mode") == "audio_to_zh":
            question.setdefault("question", {})["options"] = meaning_choice_options(
                question, familiarity
            )
        result["current_question"] = sanitize_question(
            question, reveal=bool(result.get("correction_required"))
        )
    if result.get("phase") != "familiarity":
        result["familiarity"] = [
            {"word_id": row.get("word_id"), "viewed": bool(row.get("viewed"))}
            for row in familiarity
        ]
    # An exact requested attempt may be recovered. A generic previous answer
    # must not accidentally reveal the current retry's word/meaning.
    result.pop("last_saved_response", None)
    if not result.get("settlement"):
        result.pop("forgot_items", None)
    result["group_results"] = (result.get("group_results") or [])[-1:]
    if flow is not None:
        counts = dict(
            db.session.query(
                VocabularyLearningQuestion.phase, func.count(VocabularyLearningQuestion.id)
            )
            .filter_by(flow_id=flow.id, group_index=flow.current_group_index)
            .group_by(VocabularyLearningQuestion.phase)
            .all()
        )
        counts["familiarity"] = len(familiarity)
        counts["retry"] = len(json_value(flow.retry_question_ids_json, []))
        result["phase_counts"] = counts
        result["group_results"] = json_value(flow.group_results_json, [])[-1:]
    return result


def sanitize_review(payload):
    result = deepcopy(payload)
    items = [
        sanitize_question(row, reveal=bool(row.get("answered")))
        for row in result.get("items") or []
    ]
    result["items"] = items
    result["words"] = items
    return result


def answer_feedback(word, question=None):
    if not word:
        return {}
    snapshot = json_value(getattr(question, "question_snapshot_json", None), {})
    audio = (snapshot.get("prompt") or {}).get("audio_tts_url") or f"/dictation/words/{word.id}/tts"
    return {
        "word": canonical_vocabulary_word(word.word, word.accepted_answers) or word.word,
        "phonetic": word.phonetic,
        "core_meaning_zh": word.core_meaning_zh or word.translation,
        "usage_pattern": word.usage_pattern,
        "example_en": word.example_en,
        "example_zh": word.example_zh,
        "usage_note": word.usage_note,
        "audio_tts_url": audio,
    }


def learning_flow(user, task):
    return VocabularyLearningFlow.query.filter_by(student_id=user.id, task_id=task.id).first()


def flow_envelope(student, task, payload):
    flow = learning_flow(student.user, task)
    clean = sanitize_flow(payload, flow)
    stage = (
        "result"
        if clean.get("settlement")
        else "read_only" if task_date_access(task).read_only else "learning"
    )
    return envelope(student, task, stage, flow=clean, settlement=clean.get("settlement"))


def read_state(student, task):
    """A read never initializes or advances the learning state machine."""
    access = task_date_access(task)
    settlement = VocabularyTaskSettlement.query.filter_by(
        student_id=student.user.id, task_id=task.id
    ).first()
    if access.read_only:
        result = learning.get_vocabulary_group_queue(
            student.user, task.id, supports_correction=True
        )
        response = flow_envelope(student, task, result)
        if settlement:
            response.update(stage="result", settlement=json_value(settlement.result_json, {}))
        return response
    flow = learning_flow(student.user, task)
    if flow:
        return envelope(
            student,
            task,
            "in_progress",
            completed=flow.status == VocabularyLearningFlow.STATUS_COMPLETED,
        )
    gate = review_preflight(student.user, task.id, gate_only=True)
    return envelope(
        student,
        task,
        "review_gate" if gate["required"] else "not_started",
        gate=gate,
        preflight=gate,
    )


def sync_state(student, task, payload):
    if task_date_access(task).read_only:
        return read_state(student, task)
    gate = review_preflight(student.user, task.id, gate_only=True)
    if gate["required"]:
        response = envelope(student, task, "review_gate", gate=gate, preflight=gate)
        if payload.get("attempt_id"):
            response["saved_response"] = learning.recover_vocabulary_group_attempt(
                student.user, task.id, str(payload["attempt_id"])
            )
        return response
    result = learning.get_vocabulary_group_queue(
        student.user,
        task.id,
        supports_correction=True,
        recovery_attempt_id=payload.get("attempt_id"),
    )
    return flow_envelope(student, task, result)


def sanitized_error_details(details):
    result = deepcopy(details)
    for key in ("state", "flow"):
        if isinstance(result.get(key), dict):
            result[key] = sanitize_flow(result[key])
    return result
