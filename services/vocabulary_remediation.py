"""Shared, bounded remediation policy for vocabulary flows.

Both the teacher-task group flow and the independent review flow use these
rules. The policy contains no database or HTTP code so a page cannot create a
second interpretation of correction, related dimensions, or the per-word
budget.
"""

from __future__ import annotations

MAX_CORRECTION_ATTEMPTS = 2
MAX_REMEDIATION_PER_WORD = 2
MIN_OTHER_FORMAL_QUESTIONS = 5
MAX_FORMAL_QUESTIONS_PER_WORD = 4

# Autonomous review uses one dimension per sense per available review day.
# Keep this order in the shared policy so API/page code cannot accidentally
# reintroduce a four-mode burst when several due timestamps coincide.
AUTONOMOUS_DIMENSION_ORDER = (
    "meaning_recall",
    "audio_form_recall",
    "form_recall",
    "context_use",
)

RELATED_DIMENSION_BY_ERROR = {
    "meaning_recall": "context_use",
    "form_recall": "context_use",
    "audio_form_recall": "form_recall",
    "context_use": "form_recall",
}


def related_dimension_for(dimension: str) -> str | None:
    """Return at most one related capability for a failed dimension."""

    return RELATED_DIMENSION_BY_ERROR.get(str(dimension or "").strip().lower())


def correction_state(previous_count: int, is_correct: bool) -> dict:
    """Describe the finite correction transition without mutating a model."""

    count = max(0, int(previous_count or 0)) + 1
    correct = bool(is_correct)
    exhausted = not correct and count >= MAX_CORRECTION_ATTEMPTS
    return {
        "count": count,
        "is_correct": correct,
        "completed": correct or exhausted,
        "required": not correct and not exhausted,
        "retry_allowed": not correct and not exhausted,
        "exhausted": exhausted,
    }


def remediation_kind_for_dimension(*, is_retry: bool, is_related: bool = False) -> str | None:
    """Use stable public labels for autonomous queue snapshots."""

    if is_related:
        return "related_dimension"
    if is_retry:
        return "same_dimension"
    return None


def remediation_priority(kind: str | None) -> int:
    """Rank bounded remediation above ordinary due dimensions."""

    return {
        "related_dimension": 3,
        "same_dimension": 2,
    }.get(str(kind or ""), 0)


def dimension_priority(dimension: str) -> int:
    """Return the stable release rank for a valid autonomous dimension."""

    try:
        return AUTONOMOUS_DIMENSION_ORDER.index(dimension)
    except ValueError:
        return len(AUTONOMOUS_DIMENSION_ORDER)
