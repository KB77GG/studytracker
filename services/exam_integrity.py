"""Optional integrity storage, isolated from exam transactions and fail-open for students.

Only the teacher panel calls ensure_schema. No student operation performs DDL or
uses Flask-SQLAlchemy's request-scoped db.session.
"""

from __future__ import annotations

import os
import threading
import weakref

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import ExamIntegrityEvent, ExamIntegrityPolicy, ExamIntegrityState, db
from services.exam_integrity_rules import (
    as_utc,
    clear_hidden,
    serialize,
    timestamp,
    transition,
)

KIND = "ielts_mock"
MAX_EVENTS = 2000
_TABLES = (ExamIntegrityPolicy, ExamIntegrityState, ExamIntegrityEvent)
_SCHEMA_READY = weakref.WeakSet()
_LOCK = threading.RLock()  # Production is explicitly one worker / six threads.


def off_policy():
    return {"mode": "off", "max_leaves": 3, "max_hidden_seconds": 60}


def _engine(engine=None):
    return engine if engine is not None else db.engine


def ensure_schema(engine=None):
    """Teacher-only, idempotent CREATE of exactly three independent new tables."""
    try:
        engine = _engine(engine)
        with _LOCK:
            if engine not in _SCHEMA_READY:
                for model in _TABLES:
                    model.__table__.create(engine, checkfirst=True)
                _SCHEMA_READY.add(engine)
        return True
    except Exception:
        return False


def read_policy(exam_ref, exam_kind=KIND, engine=None):
    """A read-only independent connection must not rollback a pending exam write."""
    if os.environ.get("EXAM_INTEGRITY_DISABLED") == "1":
        return off_policy()
    try:
        table = ExamIntegrityPolicy.__table__
        with _engine(engine).connect() as conn:
            row = (
                conn.execute(
                    select(table).where(
                        table.c.exam_kind == exam_kind, table.c.exam_ref == str(exam_ref)
                    )
                )
                .mappings()
                .first()
            )
        if not row or row["mode"] not in {"monitor", "enforce"}:
            return off_policy()
        return {
            "mode": row["mode"],
            "max_leaves": row["max_leaves"],
            "max_hidden_seconds": row["max_hidden_seconds"],
        }
    except Exception:
        return off_policy()


def _state_query(exam_ref, session_ref):
    return select(ExamIntegrityState).where(
        ExamIntegrityState.exam_kind == KIND,
        ExamIntegrityState.exam_ref == str(exam_ref),
        ExamIntegrityState.session_ref == str(session_ref),
    )


def _get_or_create(session, exam_ref, session_ref):
    state = session.scalar(_state_query(exam_ref, session_ref))
    if state is None:
        state = ExamIntegrityState(
            exam_kind=KIND, exam_ref=str(exam_ref), session_ref=str(session_ref)
        )
        session.add(state)
        session.flush()
    return state


def _append_events(session, state, logs, now):
    count = session.scalar(
        select(func.count())
        .select_from(ExamIntegrityEvent)
        .where(
            ExamIntegrityEvent.exam_kind == KIND,
            ExamIntegrityEvent.exam_ref == state.exam_ref,
        )
    )
    for log in logs[: max(0, MAX_EVENTS - count)]:
        session.add(
            ExamIntegrityEvent(
                state_id=state.id, exam_kind=KIND, exam_ref=state.exam_ref, created_at=now, **log
            )
        )


def student_state(exam_ref, session_ref, device_id="", section="process", now=None):
    policy = read_policy(exam_ref)
    if policy["mode"] == "off":
        return serialize(None, policy, now=now)
    try:
        with Session(db.engine) as session:
            state = session.scalar(_state_query(exam_ref, session_ref))
            return serialize(state, policy, device_id=device_id, section=section, now=now)
    except Exception:
        return serialize(None, off_policy(), now=now)


get_state = student_state


def record_event(
    exam_ref, session_ref, payload, *, current_section=None, submitted_sections=(), now=None
):
    now = as_utc(now)
    try:
        with _LOCK:
            policy = read_policy(exam_ref)
            if policy["mode"] == "off":
                return serialize(None, policy, now=now)
            with Session(db.engine) as session, session.begin():
                state = _get_or_create(session, exam_ref, session_ref)
                logs = transition(
                    state,
                    policy,
                    payload,
                    now=now,
                    current_section=current_section,
                    submitted_sections=submitted_sections,
                )
                _append_events(session, state, logs, now)
                session.flush()
                return serialize(
                    state,
                    policy,
                    device_id=payload.get("device_id", ""),
                    section=payload.get("section", "process"),
                    now=now,
                )
    except Exception:
        return serialize(None, off_policy(), now=now)


def set_policy(exam_ref, mode, max_leaves=3, max_hidden_seconds=60, actor=None, now=None):
    if mode not in {"off", "monitor", "enforce"}:
        raise ValueError("invalid_mode")
    if (
        isinstance(max_leaves, bool)
        or not isinstance(max_leaves, int)
        or not 1 <= max_leaves <= 100
    ):
        raise ValueError("invalid_max_leaves")
    if (
        isinstance(max_hidden_seconds, bool)
        or not isinstance(max_hidden_seconds, int)
        or not 2 <= max_hidden_seconds <= 3600
    ):
        raise ValueError("invalid_max_hidden_seconds")
    now = as_utc(now)
    with _LOCK, Session(db.engine) as session, session.begin():
        policy = session.scalar(
            select(ExamIntegrityPolicy).where(
                ExamIntegrityPolicy.exam_kind == KIND, ExamIntegrityPolicy.exam_ref == str(exam_ref)
            )
        )
        if policy is None:
            policy = ExamIntegrityPolicy(exam_kind=KIND, exam_ref=str(exam_ref), created_at=now)
            session.add(policy)
        policy.mode, policy.max_leaves = mode, max_leaves
        policy.max_hidden_seconds, policy.updated_by, policy.updated_at = (
            max_hidden_seconds,
            actor,
            now,
        )
        # Changing modes must not resurrect old locks/bindings or pending departures.
        for state in session.scalars(
            select(ExamIntegrityState).where(
                ExamIntegrityState.exam_kind == KIND, ExamIntegrityState.exam_ref == str(exam_ref)
            )
        ):
            clear_hidden(state, discard=True)
            if mode != "enforce":
                state.is_locked = False
                state.device_hash = None
                state.device_conflict_at = None
    return {"mode": mode, "max_leaves": max_leaves, "max_hidden_seconds": max_hidden_seconds}


def admin_action(exam_ref, session_ref, action, actor=None, exempt=True, now=None):
    if action not in {"unlock", "reset-device", "exempt"}:
        raise ValueError("invalid_action")
    now = as_utc(now)
    policy = read_policy(exam_ref)
    with _LOCK, Session(db.engine) as session, session.begin():
        state = _get_or_create(session, exam_ref, session_ref)
        if action == "unlock":
            if not state.is_locked:
                # Repeated clicks on a healthy student must not lower their limit.
                return serialize(state, policy, now=now)
            state.is_locked = False
            state.unlock_count += 1
            state.unlocked_at, state.unlocked_by = now, actor
            state.unlock_leave_count, state.unlock_hidden_seconds = (
                state.leave_count,
                state.hidden_seconds,
            )
            clear_hidden(state, discard=True)
        elif action == "reset-device":
            state.device_hash = None
            state.device_conflict_at = None
            clear_hidden(state, discard=True)
            state.current_page_id = None
        else:
            state.exempt, state.exempt_by = bool(exempt), actor
            if exempt:
                state.is_locked = False
                state.device_conflict_at = None
                clear_hidden(state, discard=True)
        _append_events(
            session,
            state,
            [
                {
                    "type": action,
                    "section": state.current_section,
                    "detail_json": '{"actor":%s}' % (actor or 0),
                }
            ],
            now,
        )
        session.flush()
        return serialize(state, policy, now=now)


def admin_states(exam_ref, session_refs, now=None):
    policy = read_policy(exam_ref)
    with Session(db.engine) as session:
        refs = [str(ref) for ref in session_refs]
        states = {
            state.session_ref: state
            for state in session.scalars(
                select(ExamIntegrityState).where(
                    ExamIntegrityState.exam_kind == KIND,
                    ExamIntegrityState.exam_ref == str(exam_ref),
                    ExamIntegrityState.session_ref.in_(refs),
                )
            )
        }
        result = {ref: serialize(states.get(ref), policy, now=now) for ref in refs}
        for ref, state in states.items():
            # Teacher reports the stored lock, even on the inter-section page.
            result[ref]["is_locked"] = bool(
                state.is_locked and policy["mode"] == "enforce" and not state.exempt
            )
        return result


def event_timeline(session_ref, limit=200):
    with Session(db.engine) as session:
        state = session.scalar(
            select(ExamIntegrityState).where(
                ExamIntegrityState.exam_kind == KIND,
                ExamIntegrityState.session_ref == str(session_ref),
            )
        )
        if state is None:
            return []
        events = session.scalars(
            select(ExamIntegrityEvent)
            .where(ExamIntegrityEvent.state_id == state.id)
            .order_by(ExamIntegrityEvent.id.desc())
            .limit(min(2000, max(1, int(limit))))
        )
        return [
            {
                "id": event.id,
                "type": event.type,
                "section": event.section,
                "question_ref": event.question_ref,
                "duration_seconds": event.duration_seconds,
                "detail_json": event.detail_json,
                "created_at": timestamp(event.created_at),
            }
            for event in events
        ]
