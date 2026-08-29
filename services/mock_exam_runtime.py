"""Server-owned timing and draft rules for IELTS mock-exam objective sections."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from services.ielts_practice_scoring import (
    grade_listening_test_answers,
    grade_reading_test_answers,
)

OBJECTIVE_SECTIONS = {"listening", "reading"}
MAX_DRAFT_BYTES = 100_000


def listening_runtime_minutes(configured_minutes: int | None) -> int:
    """Legacy exams stored 30 recording minutes; official flow adds 2 review minutes."""
    configured = max(1, int(configured_minutes or 30))
    return 32 if configured == 30 else configured


def listening_runtime_seconds(
    configured_minutes: int | None,
    audio_duration_seconds: object = None,
) -> int:
    """Use verified client media duration only to shorten, never extend, the server cap."""
    cap = listening_runtime_minutes(configured_minutes) * 60
    try:
        duration = float(audio_duration_seconds)
    except (TypeError, ValueError):
        return cap
    if not math.isfinite(duration) or duration < 10 * 60:
        return cap
    return min(cap, math.ceil(duration) + 2 * 60)


def _field(section: str, suffix: str) -> str:
    if section not in OBJECTIVE_SECTIONS:
        raise ValueError("unsupported_objective_section")
    return f"{section}_{suffix}"


def parse_draft(mock_session, section: str) -> dict:
    raw = getattr(mock_session, _field(section, "answers_json"), None)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def deadline_expired(mock_session, section: str, now: datetime | None = None) -> bool:
    deadline = getattr(mock_session, _field(section, "deadline_at"), None)
    return bool(deadline and (now or datetime.utcnow()) >= deadline)


def start_section(
    mock_session,
    section: str,
    minutes: int,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    started_field = _field(section, "started_at")
    deadline_field = _field(section, "deadline_at")
    started_at = getattr(mock_session, started_field, None)
    deadline_at = getattr(mock_session, deadline_field, None)
    if not started_at or not deadline_at:
        started_at = now or datetime.utcnow()
        deadline_at = started_at + timedelta(minutes=max(1, int(minutes or 0)))
        setattr(mock_session, started_field, started_at)
        setattr(mock_session, deadline_field, deadline_at)
    mock_session.current_section = section
    return started_at, deadline_at


def start_section_seconds(
    mock_session,
    section: str,
    seconds: int,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    started_field = _field(section, "started_at")
    deadline_field = _field(section, "deadline_at")
    started_at = getattr(mock_session, started_field, None)
    deadline_at = getattr(mock_session, deadline_field, None)
    if not started_at or not deadline_at:
        started_at = now or datetime.utcnow()
        deadline_at = started_at + timedelta(seconds=max(1, int(seconds or 0)))
        setattr(mock_session, started_field, started_at)
        setattr(mock_session, deadline_field, deadline_at)
    mock_session.current_section = section
    return started_at, deadline_at


def close_listening_to_review_window(
    mock_session,
    now: datetime | None = None,
) -> datetime:
    """Idempotently cap the remaining Listening review window at two minutes."""
    if not mock_session.listening_started_at:
        raise ValueError("section_not_started")
    current_time = now or datetime.utcnow()
    review_deadline = current_time + timedelta(minutes=2)
    existing = mock_session.listening_deadline_at
    mock_session.listening_deadline_at = min(existing, review_deadline) if existing else review_deadline
    return mock_session.listening_deadline_at


def save_draft(
    mock_session,
    section: str,
    answers: dict,
    now: datetime | None = None,
) -> bool:
    if not isinstance(answers, dict):
        raise ValueError("answers_must_be_object")
    if deadline_expired(mock_session, section, now):
        return False
    payload = json.dumps(answers, ensure_ascii=False, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise ValueError("draft_too_large")
    setattr(mock_session, _field(section, "answers_json"), payload)
    return True


def submission_answers(
    mock_session,
    section: str,
    incoming_answers: dict,
    now: datetime | None = None,
) -> tuple[dict, bool]:
    expired = deadline_expired(mock_session, section, now)
    if expired:
        return parse_draft(mock_session, section), True
    return (incoming_answers if isinstance(incoming_answers, dict) else {}), False


def grade_objective_section(payload: dict, answers: dict, section: str) -> dict:
    if section == "listening":
        return grade_listening_test_answers(payload, answers)
    if section == "reading":
        return grade_reading_test_answers(payload, answers)
    raise ValueError("unsupported_objective_section")


def persist_section_grade(
    mock_session,
    section: str,
    grade: dict,
    answers: dict,
    duration_seconds: int,
    auto_submitted: bool,
    *,
    has_writing: bool = False,
    now: datetime | None = None,
) -> None:
    submitted_at = now or datetime.utcnow()
    setattr(mock_session, _field(section, "submitted_at"), submitted_at)
    setattr(mock_session, _field(section, "correct"), grade.get("correct"))
    setattr(mock_session, _field(section, "total"), grade.get("total"))
    setattr(mock_session, _field(section, "accuracy"), grade.get("accuracy"))
    setattr(mock_session, _field(section, "ielts_score"), grade.get("ielts_score"))
    duration_field = _field(section, "duration_seconds")
    setattr(
        mock_session,
        duration_field,
        max(int(getattr(mock_session, duration_field, 0) or 0), int(duration_seconds or 0)),
    )
    setattr(
        mock_session,
        _field(section, "answers_json"),
        json.dumps(answers, ensure_ascii=False),
    )
    setattr(
        mock_session,
        _field(section, "results_json"),
        json.dumps(grade.get("results") or [], ensure_ascii=False),
    )
    setattr(
        mock_session,
        _field(section, "wrong_numbers_json"),
        json.dumps(grade.get("wrong_numbers") or [], ensure_ascii=False),
    )
    setattr(mock_session, _field(section, "auto_submitted"), bool(auto_submitted))

    if section == "listening":
        mock_session.current_section = "reading"
    elif has_writing:
        mock_session.current_section = "writing"
    else:
        mock_session.current_section = "finished"
        mock_session.status = "submitted"
        mock_session.finished_at = submitted_at


def finalize_expired_section(
    mock_session,
    exam,
    section: str,
    payload: dict,
    now: datetime | None = None,
) -> dict | None:
    current_time = now or datetime.utcnow()
    if getattr(mock_session, _field(section, "submitted_at"), None):
        return None
    if not deadline_expired(mock_session, section, current_time):
        return None
    answers = parse_draft(mock_session, section)
    grade = grade_objective_section(payload, answers, section)
    started_at = getattr(mock_session, _field(section, "started_at"), None)
    duration_seconds = int(max(0, (current_time - started_at).total_seconds())) if started_at else 0
    persist_section_grade(
        mock_session,
        section,
        grade,
        answers,
        duration_seconds,
        True,
        has_writing=bool(getattr(exam, "writing_test_id", None)),
        now=current_time,
    )
    return grade
