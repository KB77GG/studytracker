"""Build permission-neutral first/latest attempt summaries for IELTS practice."""

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
    """Load immutable snapshots in one query for authorized practice reports."""
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
    correct_count = int(row.correct_count or 0)
    total_count = int(row.total_count or 0)
    return {
        "attempt_number": number,
        "correct_count": correct_count,
        "total_count": total_count,
        "wrong_count": max(0, total_count - correct_count),
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


def attempt_wrong_answer_details(row) -> list[dict]:
    """Serialize retained wrong-answer rows without exposing unrelated data."""
    details = []
    for index, result in enumerate(_json_list(row.results_json)):
        if not isinstance(result, dict):
            continue
        status = result.get("status")
        if status == "correct" or (status is None and result.get("correct") is True):
            continue

        raw_numbers = result.get("numbers") or []
        if not isinstance(raw_numbers, list):
            raw_numbers = [raw_numbers]
        numbers = [value for value in raw_numbers if value not in (None, "")]
        raw_label = result.get("q")
        if numbers:
            question_label = "、".join(f"Q{number}" for number in numbers)
        elif raw_label not in (None, ""):
            label = str(raw_label)
            question_label = label if label.upper().startswith("Q") else f"Q{label}"
        else:
            question_label = f"Q{index + 1}"

        awarded = result.get("awarded") or 0
        marks = result.get("marks") or 1
        normalized_status = status or (
            "correct" if result.get("correct") is True else "incorrect"
        )
        details.append(
            {
                "question_label": question_label,
                "student_answer": (
                    result.get("value")
                    if result.get("value") not in (None, "")
                    else "未作答"
                ),
                "correct_answer": result.get("answer") or "",
                "awarded": awarded,
                "marks": marks,
                "status": normalized_status,
                "status_label": result.get("status_label")
                or (
                    f"部分正确 {awarded}/{marks}"
                    if normalized_status == "partial" or awarded
                    else "错误"
                ),
            }
        )
    return details


def build_detailed_attempt_history(
    submission,
    snapshots: Iterable[PracticeSubmissionAttempt],
    *,
    kind: str,
) -> dict:
    """Build one permission-neutral history payload for authorized viewers."""
    overview = build_attempt_overview(submission, snapshots, kind=kind)
    summaries = {
        int(attempt["attempt_number"]): attempt for attempt in overview["attempts"]
    }
    detailed_attempts = []
    for attempt_number, row in retained_attempt_records(
        submission,
        snapshots,
        kind=kind,
    ):
        summary = dict(summaries.get(attempt_number) or {})
        if not summary:
            continue
        summary["wrong_details"] = attempt_wrong_answer_details(row)
        detailed_attempts.append(summary)
    overview["attempts"] = detailed_attempts
    return overview
