"""Build answer-free IELTS payloads for an active mock-exam session.

The practice library keeps answers and teaching material in the source JSON because
review mode needs them.  An active simulation must never serialize those fields to
the browser.  This module derives the small amount of response-shape metadata the
renderers need, then removes grading and teaching material from a deep copy.
"""

from __future__ import annotations

import re
from copy import deepcopy

_FORBIDDEN_KEYS = {
    "answer",
    "answers",
    "correct_answer",
    "correct_answers",
    "analysis",
    "explanation",
    "answer_sentences",
    "transcript",
    "translation",
    "translations",
}


def _option_key(option: dict) -> str:
    return str(option.get("key") or option.get("title") or "").strip().upper()


def _option_text(option: dict) -> str:
    return str(option.get("text") or option.get("content") or "").strip().upper()


def _answer_letters(answer: object) -> list[str]:
    rows = [row.strip().upper() for row in re.split(r"\s*[,/]\s*", str(answer or ""))]
    rows = [row for row in rows if row]
    return rows if len(rows) > 1 and all(re.fullmatch(r"[A-Z]", row) for row in rows) else []


def _judgment_value(value: object) -> bool:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().upper())
    return normalized in {
        "Y",
        "YES",
        "N",
        "NO",
        "NG",
        "NOT GIVEN",
        "T",
        "TRUE",
        "F",
        "FALSE",
    }


def _annotate_group(group: dict, kind: str) -> None:
    questions = group.get("questions") or []
    group_options = (group.get("collect_option") or {}).get("list") or []

    if kind == "listening" and int(group.get("type") or 0) == 2 and questions and group_options:
        answers = [str(question.get("answer") or "") for question in questions]
        letters = _answer_letters(answers[0])
        if letters and all(answer == answers[0] for answer in answers):
            group["response_layout"] = "combined_multi"
            group["max_selections"] = len(letters)

    group_keys = {_option_key(option) for option in group_options}
    for question in questions:
        answer = question.get("answer")
        question_options = question.get("options") or []
        letters = _answer_letters(answer)

        uses_group_options = False
        if group_options:
            if not question_options:
                uses_group_options = int(group.get("type") or 0) != 2
            elif kind == "reading":
                judgment_options = all(
                    _judgment_value(_option_key(option))
                    or _judgment_value(_option_text(option))
                    for option in question_options
                )
                uses_group_options = (
                    str(answer or "").strip().upper() in group_keys and judgment_options
                )

        if uses_group_options:
            question["response_kind"] = "group_select"
            question["uses_group_options"] = True
        elif question_options:
            is_multi = bool(letters) or int(group.get("type") or 0) == 9
            question["response_kind"] = "multiple_choice_multiple" if is_multi else "multiple_choice_single"
            if is_multi:
                question["max_selections"] = len(letters) or max(1, int(group.get("max_selections") or 1))
        elif group_options:
            question["response_kind"] = "group_select"
            question["uses_group_options"] = True
        else:
            question["response_kind"] = "text"


def _strip_forbidden(value):
    if isinstance(value, dict):
        for key in list(value):
            if str(key).lower() in _FORBIDDEN_KEYS:
                value.pop(key, None)
            else:
                _strip_forbidden(value[key])
    elif isinstance(value, list):
        for item in value:
            _strip_forbidden(item)


def build_simulation_payload(payload: dict, kind: str) -> dict:
    """Return a deep-copied, renderable payload with no grading material."""
    if kind not in {"listening", "reading"}:
        raise ValueError("unsupported_ielts_payload_kind")
    safe = deepcopy(payload or {})
    container = "sections" if kind == "listening" else "passages"
    for unit in safe.get(container) or []:
        for group in unit.get("groups") or []:
            _annotate_group(group, kind)
    _strip_forbidden(safe)
    safe["simulation_payload"] = True
    return safe
