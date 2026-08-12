"""Append-only snapshots for IELTS listening and reading submissions."""

from __future__ import annotations

from models import PracticeSubmissionAttempt, db


def _copy_submission(
    submission,
    *,
    kind: str,
    scope_number: int | None,
    attempt_number: int,
) -> PracticeSubmissionAttempt:
    return PracticeSubmissionAttempt(
        task_id=submission.task_id,
        student_name=submission.student_name,
        kind=kind,
        test_id=submission.test_id,
        test_title=submission.test_title,
        scope_number=scope_number,
        attempt_number=attempt_number,
        correct_count=int(submission.correct_count or 0),
        total_count=int(submission.total_count or 0),
        accuracy=float(submission.accuracy or 0.0),
        ielts_score=submission.ielts_score,
        completion_rate=float(submission.completion_rate or 0.0),
        duration_seconds=int(submission.duration_seconds or 0),
        answers_json=submission.answers_json,
        results_json=submission.results_json,
        wrong_numbers_json=submission.wrong_numbers_json,
        submitted_at=submission.submitted_at,
    )


def preserve_legacy_submission(
    submission,
    *,
    kind: str,
    scope_number: int | None,
) -> None:
    """Snapshot the retained legacy row before its next in-place update."""
    if not submission or not submission.submitted_at:
        return
    exists = PracticeSubmissionAttempt.query.filter_by(
        kind=kind,
        task_id=submission.task_id,
        attempt_number=max(1, int(submission.attempt_count or 1)),
    ).first()
    if exists:
        return
    db.session.add(
        _copy_submission(
            submission,
            kind=kind,
            scope_number=scope_number,
            attempt_number=max(1, int(submission.attempt_count or 1)),
        )
    )


def append_submission_attempt(
    submission,
    *,
    kind: str,
    scope_number: int | None,
) -> PracticeSubmissionAttempt:
    """Persist the just-written submission as one immutable attempt."""
    attempt = _copy_submission(
        submission,
        kind=kind,
        scope_number=scope_number,
        attempt_number=max(1, int(submission.attempt_count or 1)),
    )
    db.session.add(attempt)
    return attempt
