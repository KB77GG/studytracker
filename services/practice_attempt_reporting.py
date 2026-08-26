"""Build teacher-facing first/latest attempt summaries for IELTS practice."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable

from models import PracticeSubmissionAttempt


def _json_list(value: str | None) -> list:
    try:
        decoded = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []


def load_attempts_by_task(
    task_ids: Iterable[int],
) -> dict[int, list[PracticeSubmissionAttempt]]:
    """Load immutable snapshots in one query for a teacher homework list."""
    normalized_ids = sorted({int(task_id) for task_id in task_ids if task_id})
    if not normalized_ids:
        return {}
    rows = (
        PracticeSubmissionAttempt.query.filter(
            PracticeSubmissionAttempt.task_id.in_(normalized_ids)
        )
        .order_by(
            PracticeSubmissionAttempt.task_id.asc(),
            PracticeSubmissionAttempt.attempt_number.asc(),
            PracticeSubmissionAttempt.id.asc(),
        )
        .all()
    )
    grouped: dict[int, list[PracticeSubmissionAttempt]] = defaultdict(list)
    for row in rows:
        grouped[int(row.task_id)].append(row)
    return dict(grouped)


def retained_attempt_records(
    submission,
    snapshots: Iterable[PracticeSubmissionAttempt],
    *,
    kind: str,
) -> list[tuple[int, object]]:
    """Return known attempts without pretending overwritten legacy rows exist."""
    current_number = max(1, int(submission.attempt_count or 1))
    by_number: dict[int, object] = {}
    for row in snapshots:
        if row.kind != kind or int(row.task_id or 0) != int(submission.task_id or 0):
            continue
        number = max(1, int(row.attempt_number or 1))
        by_number[number] = row

    # The retained submission row is the canonical latest result. Newer
    # deployments also snapshot it, while legacy rows may have no snapshot.
    by_number[current_number] = submission
    return sorted(by_number.items())


def _attempt_summary(number: int, row, *, latest_number: int) -> dict:
    return {
        "attempt_number": number,
        "correct_count": int(row.correct_count or 0),
        "total_count": int(row.total_count or 0),
        "accuracy": round(float(row.accuracy or 0.0), 1),
        "ielts_score": row.ielts_score,
        "duration_seconds": int(row.duration_seconds or 0),
        "wrong_numbers": _json_list(row.wrong_numbers_json),
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "is_first": number == 1,
        "is_latest": number == latest_number,
    }


def build_attempt_overview(
    submission,
    snapshots: Iterable[PracticeSubmissionAttempt],
    *,
    kind: str,
) -> dict:
    """Summarize known first/latest attempts and disclose unrecoverable gaps."""
    records = retained_attempt_records(submission, snapshots, kind=kind)
    current_number = max(1, int(submission.attempt_count or 1))
    retained_numbers = {number for number, _row in records if number <= current_number}
    attempts = [
        _attempt_summary(number, row, latest_number=current_number) for number, row in records
    ]
    first_attempt = next(
        (attempt for attempt in attempts if attempt["attempt_number"] == 1),
        None,
    )
    latest_attempt = next(
        (attempt for attempt in attempts if attempt["attempt_number"] == current_number),
        attempts[-1] if attempts else None,
    )
    score_delta = None
    if first_attempt and latest_attempt and current_number > 1:
        score_delta = round(
            float(latest_attempt["accuracy"]) - float(first_attempt["accuracy"]),
            1,
        )

    return {
        "attempt_count": current_number,
        "retained_attempt_count": len(retained_numbers),
        "legacy_missing_attempts": max(
            0,
            current_number - len(retained_numbers),
        ),
        "first_attempt": first_attempt,
        "latest_attempt": latest_attempt,
        "best_accuracy": (
            max(float(attempt["accuracy"]) for attempt in attempts) if attempts else None
        ),
        "score_delta": score_delta,
        "attempts": attempts,
    }
