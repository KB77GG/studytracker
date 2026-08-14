"""Canonical, server-side scoring for listening-cloze first attempts."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


SPEAKER_LABEL_PATTERN = re.compile(
    r"^(?:[A-Z][A-Z\s.'&/-]{0,40}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s*:\s*"
)
EDGE_PUNCTUATION_PATTERN = re.compile(r'''^[.,!?;:"'“”‘’()\[\]{}]+|[.,!?;:"'“”‘’()\[\]{}]+$''')


class ListeningClozeValidationError(ValueError):
    """Raised when a client submission cannot be graded canonically."""


@dataclass(frozen=True)
class _Token:
    index: int
    display: str
    normalized: str
    speaker_label: bool


def strip_speaker_label(text: Any) -> str:
    return SPEAKER_LABEL_PATTERN.sub("", str(text or "").strip())


def normalize_word(value: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "")).lower()
    return re.sub(r"[^a-z0-9]", "", decomposed)


def _tokenize(text: str) -> list[_Token]:
    source = str(text or "").strip()
    words = re.findall(r"\S+", source)
    label_match = SPEAKER_LABEL_PATTERN.match(source)
    label_count = len(re.findall(r"\S+", label_match.group(0))) if label_match else 0
    tokens = []
    for index, raw in enumerate(words):
        display = EDGE_PUNCTUATION_PATTERN.sub("", raw)
        tokens.append(
            _Token(
                index=index,
                display=display,
                normalized=normalize_word(display),
                speaker_label=index < label_count,
            )
        )
    return tokens


def find_exercise_segment(exercise_data: dict, segment_index: int) -> dict | None:
    fallback_index = 0
    for part in exercise_data.get("parts", []):
        for segment in part.get("segments", []):
            source_index = segment.get("source_index")
            resolved_index = source_index if isinstance(source_index, int) else fallback_index
            if resolved_index == segment_index:
                return segment
            fallback_index += 1
    return None


def grade_first_attempt(
    exercise_data: dict,
    segment_index: int,
    *,
    segment_text: Any,
    hidden_word_indices: Any,
    answers: Any,
) -> dict:
    """Validate coordinates and recompute a first-attempt score from source data."""

    segment = find_exercise_segment(exercise_data, segment_index)
    if not segment:
        raise ListeningClozeValidationError("segment_not_found")

    canonical_text = str(segment.get("text") or "").strip()
    submitted_text = str(segment_text or "").strip()
    stripped_text = strip_speaker_label(canonical_text)
    if submitted_text == canonical_text:
        scoring_text = canonical_text
    elif submitted_text == stripped_text:
        scoring_text = stripped_text
    else:
        raise ListeningClozeValidationError("segment_text_mismatch")

    if not isinstance(hidden_word_indices, list) or not hidden_word_indices:
        raise ListeningClozeValidationError("invalid_hidden_word_indices")
    if not isinstance(answers, list):
        raise ListeningClozeValidationError("invalid_answers")
    if not any(str(answer or "").strip() for answer in answers):
        raise ListeningClozeValidationError("empty_answers")

    indices: list[int] = []
    for raw_index in hidden_word_indices:
        if isinstance(raw_index, bool) or not isinstance(raw_index, int):
            raise ListeningClozeValidationError("invalid_hidden_word_indices")
        if raw_index in indices:
            raise ListeningClozeValidationError("duplicate_hidden_word_index")
        indices.append(raw_index)

    tokens = _tokenize(scoring_text)
    token_by_index = {token.index: token for token in tokens}
    expected = []
    for index in indices:
        token = token_by_index.get(index)
        if not token or not token.normalized or token.speaker_label:
            raise ListeningClozeValidationError("hidden_word_index_out_of_range")
        expected.append(token)

    supplied = [str(answer or "") for answer in answers]
    results = []
    for position, token in enumerate(expected):
        raw_answer = supplied[position] if position < len(supplied) else ""
        is_correct = normalize_word(raw_answer) == token.normalized
        results.append(
            {
                "index": position,
                "word_index": token.index,
                "answer": token.display,
                "raw_answer": raw_answer,
                "is_correct": is_correct,
                "is_extra": False,
            }
        )
    for position, raw_answer in enumerate(supplied[len(expected):], start=len(expected)):
        results.append(
            {
                "index": position,
                "word_index": None,
                "answer": "",
                "raw_answer": raw_answer,
                "is_correct": False,
                "is_extra": True,
            }
        )

    correct_words = sum(1 for result in results if result["is_correct"])
    total_words = len(results)
    accuracy = round(correct_words / total_words * 100, 1) if total_words else 0.0
    return {
        "segment_text": scoring_text,
        "hidden_word_indices": indices,
        "answers": supplied,
        "results": results,
        "correct_words": correct_words,
        "total_words": total_words,
        "accuracy": accuracy,
    }
