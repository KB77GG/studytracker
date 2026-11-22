"""Persist and read homework answer timelines (作答过程记录).

Submission handlers call :func:`record_answer_timeline` only *after* their own
commit succeeded.  The log is then written in its own short transaction: any
problem with the payload, the analysis or the INSERT itself is logged and
rolled back on its own, so answers, grades and task status are never lost.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import defer

from models import AnswerIntegrityLog, Task, db, utcnow_naive
from services.answer_timeline_rules import (
    BASELINE_MIN_ATTEMPTS,
    LEVEL_LABELS,
    SOURCE_LABELS,
    analyze_timeline,
    sanitize_timeline,
)

logger = logging.getLogger(__name__)

BASELINE_LOOKBACK = 10


def _baseline_accuracy(student_name: str, source: str) -> float | None:
    rows = (
        db.session.query(AnswerIntegrityLog.accuracy)
        .filter(
            AnswerIntegrityLog.student_name == student_name,
            AnswerIntegrityLog.source == source,
            AnswerIntegrityLog.mode == "practice",
            AnswerIntegrityLog.accuracy.isnot(None),
        )
        .order_by(AnswerIntegrityLog.submitted_at.desc(), AnswerIntegrityLog.id.desc())
        .limit(BASELINE_LOOKBACK)
        .all()
    )
    values = [float(row[0]) for row in rows]
    if len(values) < BASELINE_MIN_ATTEMPTS:
        return None
    return sum(values) / len(values)


def record_answer_timeline(
    task: Task,
    *,
    source: str,
    raw_timeline,
    duration_seconds: int,
    question_count: int,
    correct_count: int | None,
    accuracy: float | None,
    fallback_mode: str = "practice",
) -> AnswerIntegrityLog | None:
    """Write one log row in its own transaction; call after the submission commit."""
    if db.session.new or db.session.dirty or db.session.deleted:
        # Never piggyback on (and risk rolling back) an uncommitted submission.
        logger.error("answer timeline skipped: submission for task %s not committed", task.id)
        return None
    try:
        timeline = sanitize_timeline(raw_timeline, duration_seconds=duration_seconds)
        mode = timeline["mode"] if timeline else fallback_mode
        if timeline and fallback_mode != "practice" and mode == "practice":
            mode = fallback_mode
            timeline["mode"] = mode
        analysis = analyze_timeline(
            source,
            timeline,
            question_count=int(question_count or 0),
            accuracy=accuracy,
            baseline_accuracy=_baseline_accuracy(task.student_name, source),
        )
        row = AnswerIntegrityLog(
            task_id=task.id,
            student_name=task.student_name,
            source=source,
            mode=mode,
            question_count=int(question_count or 0),
            correct_count=correct_count,
            accuracy=accuracy,
            duration_seconds=max(0, int(duration_seconds or 0)),
            has_timeline=timeline is not None,
            level=analysis["level"],
            events_json=json.dumps(timeline["events"]) if timeline else None,
            metrics_json=json.dumps(analysis["metrics"], ensure_ascii=False),
            flags_json=json.dumps(analysis["flags"], ensure_ascii=False),
            submitted_at=utcnow_naive(),
        )
        db.session.add(row)
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        logger.exception("answer timeline recording skipped for task %s", getattr(task, "id", None))
        return None


def _loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def serialize_log(row: AnswerIntegrityLog, *, include_events: bool = False) -> dict:
    payload = {
        "id": row.id,
        "task_id": row.task_id,
        "source": row.source,
        "source_label": SOURCE_LABELS.get(row.source, row.source),
        "mode": row.mode,
        "question_count": row.question_count,
        "correct_count": row.correct_count,
        "accuracy": row.accuracy,
        "duration_seconds": row.duration_seconds,
        "has_timeline": bool(row.has_timeline),
        "level": row.level,
        "level_label": LEVEL_LABELS.get(row.level, row.level),
        "flags": _loads(row.flags_json, []),
        "metrics": _loads(row.metrics_json, None),
        "submitted_at": row.submitted_at.isoformat() + "Z" if row.submitted_at else None,
    }
    if include_events:
        payload["events"] = _loads(row.events_json, [])
    return payload


def latest_logs_by_task(task_ids: list[int]) -> dict[int, AnswerIntegrityLog]:
    if not task_ids:
        return {}
    latest: dict[int, AnswerIntegrityLog] = {}
    rows = (
        AnswerIntegrityLog.query.options(defer(AnswerIntegrityLog.events_json))
        .filter(AnswerIntegrityLog.task_id.in_(task_ids))
        .order_by(AnswerIntegrityLog.task_id, AnswerIntegrityLog.id)
        .all()
    )
    for row in rows:
        latest[row.task_id] = row
    return latest


def task_logs(task_id: int) -> list[AnswerIntegrityLog]:
    return (
        AnswerIntegrityLog.query.filter_by(task_id=task_id)
        .order_by(AnswerIntegrityLog.id.desc())
        .all()
    )
