"""Shared policy for assigned intensive-listening training modes.

Legacy tasks deliberately keep ``listening_training_mode`` unset.  That is a
compatibility signal: old assignments retain the historical student-choice
behaviour, while newly assigned tasks explicitly store and enforce a mode.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from services.listening_cloze import find_exercise_segment, normalize_word, strip_speaker_label

MODE_SYSTEM = "system"
MODE_REVIEW = "review"
MODE_BASIC = "basic"
MODE_STANDARD = "standard"
MODE_CHALLENGE = "challenge"

TRAINING_MODE_OPTIONS = (
    {
        "key": MODE_SYSTEM,
        "label": "系统推荐",
        "description": "默认标准辨音；长句自动降为关键词，避免工作记忆过载",
    },
    {
        "key": MODE_REVIEW,
        "label": "听辨核对",
        "description": "完整听完后查看原文并标记本句完成",
    },
    {
        "key": MODE_BASIC,
        "label": "关键词听写",
        "description": "每句通常听写 1–2 个高价值关键词",
    },
    {
        "key": MODE_STANDARD,
        "label": "标准辨音",
        "description": "每句通常听写 2–4 个连读、弱读或信息词",
    },
    {
        "key": MODE_CHALLENGE,
        "label": "整句听写",
        "description": "短句整句听写；长句自动降为标准辨音",
    },
)

VALID_TRAINING_MODES = frozenset(option["key"] for option in TRAINING_MODE_OPTIONS)
DICTATION_LEVELS = (MODE_BASIC, MODE_STANDARD, MODE_CHALLENGE)
MAX_CHALLENGE_SECONDS = 15.0
MAX_CHALLENGE_WORDS = 20


def normalize_training_mode(value: Any, *, default: str | None = None) -> str | None:
    mode = str(value or "").strip().lower()
    if mode in VALID_TRAINING_MODES:
        return mode
    return default


def task_training_mode(task: Any) -> str | None:
    return normalize_training_mode(getattr(task, "listening_training_mode", None))


def training_mode_option(mode: str | None) -> dict:
    normalized = normalize_training_mode(mode)
    return next(
        (dict(option) for option in TRAINING_MODE_OPTIONS if option["key"] == normalized),
        {
            "key": None,
            "label": "学生自选",
            "description": "旧任务兼容：保留原有自由切换方式",
        },
    )


def _content_word_count(text: Any) -> int:
    return sum(1 for raw in re.findall(r"\S+", strip_speaker_label(text)) if normalize_word(raw))


def challenge_allowed(segment: dict | None) -> bool:
    segment = segment or {}
    try:
        duration = max(0.0, float(segment.get("end") or 0) - float(segment.get("start") or 0))
    except (TypeError, ValueError):
        duration = 0.0
    return (
        duration <= MAX_CHALLENGE_SECONDS
        and _content_word_count(segment.get("text") or "") <= MAX_CHALLENGE_WORDS
    )


def effective_dictation_level(mode: str | None, segment: dict | None) -> str | None:
    normalized = normalize_training_mode(mode)
    if normalized in {None, MODE_REVIEW}:
        return None
    if normalized == MODE_SYSTEM:
        return MODE_STANDARD if challenge_allowed(segment) else MODE_BASIC
    if normalized == MODE_CHALLENGE and not challenge_allowed(segment):
        return MODE_STANDARD
    return normalized


def task_training_policy(task: Any, exercise_data: dict | None = None) -> dict:
    configured_mode = task_training_mode(task)
    option = training_mode_option(configured_mode)
    locked = configured_mode is not None
    policy = {
        "configured_mode": configured_mode,
        "label": option["label"],
        "description": option["description"],
        "locked": locked,
        "initial_mode": "listen" if configured_mode == MODE_REVIEW else "dictation",
        "review_only": configured_mode == MODE_REVIEW,
        "review_after_first_attempt": bool(locked and configured_mode != MODE_REVIEW),
        "upgrade_after_first_attempt": bool(locked and configured_mode != MODE_REVIEW),
        "challenge_max_seconds": MAX_CHALLENGE_SECONDS,
        "challenge_max_words": MAX_CHALLENGE_WORDS,
    }
    if exercise_data is not None:
        annotate_exercise_segments(exercise_data, configured_mode)
    return policy


def annotate_exercise_segments(exercise_data: dict, configured_mode: str | None) -> dict:
    for part in exercise_data.get("parts", []):
        for segment in part.get("segments", []):
            segment["challenge_allowed"] = challenge_allowed(segment)
            segment["assigned_training_level"] = effective_dictation_level(
                configured_mode,
                segment,
            )
    return exercise_data


def validate_first_attempt_level(
    task: Any,
    exercise_data: dict,
    segment_index: int,
    *,
    submitted_level: Any,
    hidden_word_indices: Any,
) -> str | None:
    """Validate the task-owned level while tolerating pre-upgrade clients.

    New clients send ``training_level`` and must match exactly. A missing
    value identifies a pre-upgrade client: keep its historically valid
    basic/standard/challenge shape working, then record the level that was
    actually rendered. This prevents an older installed mini-program from
    becoming unusable while users gradually receive the new package.
    """

    configured_mode = task_training_mode(task)
    segment = find_exercise_segment(exercise_data, segment_index)
    if not segment:
        raise ValueError("segment_not_found")
    normalized_submitted = normalize_training_mode(submitted_level)
    submitted_value = str(submitted_level or "").strip()
    if submitted_value and normalized_submitted not in DICTATION_LEVELS:
        raise ValueError("training_level_mismatch")

    if configured_mode is None:
        return normalized_submitted if normalized_submitted in DICTATION_LEVELS else None
    if configured_mode == MODE_REVIEW and normalized_submitted:
        raise ValueError("listening_review_task")

    effective_level = effective_dictation_level(configured_mode, segment)
    if normalized_submitted and normalized_submitted != effective_level:
        raise ValueError("training_level_mismatch")

    if normalized_submitted is None:
        if not isinstance(hidden_word_indices, list):
            raise ValueError("training_level_mismatch")
        unique_indices = {
            value
            for value in hidden_word_indices
            if isinstance(value, int) and not isinstance(value, bool)
        }
        count = len(unique_indices)
        word_count = _content_word_count(segment.get("text") or "")
        compatible_with_assigned = (
            (effective_level == MODE_BASIC and 1 <= count <= 2)
            or (effective_level == MODE_STANDARD and 1 <= count <= 4)
            or (effective_level == MODE_CHALLENGE and count == word_count)
        )
        if compatible_with_assigned:
            return effective_level
        if count == word_count and word_count > 0:
            return MODE_CHALLENGE
        if 1 <= count <= 4:
            return MODE_STANDARD
        if count <= 0:
            raise ValueError("training_level_mismatch")
        raise ValueError("training_level_mismatch")
    return effective_level


def selected_segment_indices(task: Any) -> list[int] | None:
    import json

    raw = str(getattr(task, "question_ids", "") or "").strip()
    if not raw:
        return None
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(values, list):
        return None
    selected = []
    for value in values:
        try:
            selected.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(selected)) if selected else None


def selected_segment_count(task: Any, exercise_data: dict) -> int:
    selected = set(selected_segment_indices(task) or [])
    count = 0
    fallback_index = 0
    for part in exercise_data.get("parts", []):
        for segment in part.get("segments", []):
            source_index = segment.get("source_index")
            resolved = source_index if isinstance(source_index, int) else fallback_index
            if not selected or resolved in selected:
                count += 1
            fallback_index += 1
    return count


def update_task_progress_summary(
    task: Any,
    rows: Iterable[Any],
    *,
    total_segments: int,
    duration_seconds: Any = None,
) -> dict:
    selected = set(selected_segment_indices(task) or [])
    relevant = [
        row for row in rows if not selected or int(getattr(row, "segment_index", -1)) in selected
    ]
    completed_count = sum(1 for row in relevant if bool(getattr(row, "is_completed", False)))
    total_correct = sum(int(getattr(row, "correct_words", 0) or 0) for row in relevant)
    total_words = sum(int(getattr(row, "total_words", 0) or 0) for row in relevant)

    task.completion_rate = (
        round(completed_count / total_segments * 100, 1) if total_segments > 0 else 0.0
    )
    review_only = bool(relevant) and all(
        getattr(row, "training_level", None) == MODE_REVIEW for row in relevant
    )
    task.accuracy = (
        round(total_correct / total_words * 100, 1)
        if total_words > 0
        else None if review_only else 0.0
    )
    if duration_seconds is not None:
        try:
            task.actual_seconds = max(int(task.actual_seconds or 0), max(0, int(duration_seconds)))
        except (TypeError, ValueError):
            pass
    if completed_count >= total_segments and total_segments > 0:
        task.status = "done"
    elif completed_count > 0:
        task.status = "progress"
    return {
        "completed_count": completed_count,
        "total_segments": total_segments,
        "accuracy": task.accuracy,
        "completion_rate": task.completion_rate,
        "status": task.status,
    }
