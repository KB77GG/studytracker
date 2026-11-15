"""Optional integrity storage, isolated from exam transactions and fail-open for students.

Only the teacher panel calls ensure_schema. No student operation performs DDL or
uses Flask-SQLAlchemy's request-scoped db.session.
"""

from __future__ import annotations

import os
import threading
import weakref
from contextlib import contextmanager

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
BUSY_TIMEOUT_MS = 500
_CRITICAL_EVENTS = {"leave", "locked", "unlock", "device_conflict"}
_TABLES = (ExamIntegrityPolicy, ExamIntegrityState, ExamIntegrityEvent)
_SCHEMA_READY = weakref.WeakSet()
_LOCK = threading.RLock()  # Only schema creation; never hold it during event writes.


def off_policy():
    return {"mode": "off", "max_leaves": 3, "max_hidden_seconds": 60}


def _engine(engine=None):
    return engine if engine is not None else db.engine


def unavailable():
    """A transient storage failure must never look like an authoritative policy off."""
    return {"ok": False, "error": "integrity_temporarily_unavailable"}


@contextmanager
def _connection(engine=None):
    """Bound SQLite waits for this isolated operation, restoring the pooled connection."""
    with _engine(engine).connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        previous = None
        try:
            if sqlite:
                previous = connection.exec_driver_sql("PRAGMA busy_timeout").scalar()
                connection.exec_driver_sql(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
                connection.commit()
            yield connection
        finally:
            connection.rollback()
            if sqlite and previous is not None:
                connection.exec_driver_sql(f"PRAGMA busy_timeout={int(previous)}")
                connection.commit()


@contextmanager
def _session(*, write=False):
    with _connection() as connection, Session(bind=connection) as session:
        if write:
            with session.begin():
                if connection.dialect.name == "sqlite":
                    # Serialize before reading counters, without a process mutex or a
                    # read-to-write lock upgrade. Concurrent failures each wait <=500ms.
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                yield session
        else:
            yield session


def ensure_schema(engine=None):
    """Teacher-only, idempotent CREATE of exactly three independent new tables."""
    try:
        engine = _engine(engine)
        with _LOCK:
            if engine not in _SCHEMA_READY:
                with _connection(engine) as connection, connection.begin():
                    for model in _TABLES:
                        model.__table__.create(connection, checkfirst=True)
                _SCHEMA_READY.add(engine)
        return True
    except Exception:
        return False


def read_policy(exam_ref, exam_kind=KIND, engine=None, *, strict=False):
    """A read-only independent connection must not rollback a pending exam write."""
    if os.environ.get("EXAM_INTEGRITY_DISABLED") == "1":
        return off_policy()
    try:
        table = ExamIntegrityPolicy.__table__
        with _connection(engine) as conn:
            row = (
                conn.execute(
                    select(table).where(
                        table.c.exam_kind == exam_kind, table.c.exam_ref == str(exam_ref)
                    )
                )
                .mappings()
                .first()
            )
        if not row or row["mode"] not in {"off", "monitor", "enforce"}:
            return off_policy()
        return {
            "mode": row["mode"],
            "max_leaves": row["max_leaves"],
            "max_hidden_seconds": row["max_hidden_seconds"],
        }
    except Exception:
        if strict:
            raise
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
            ExamIntegrityEvent.state_id == state.id,
        )
    )
    for log in logs:
        if log["type"] == "heartbeat":
            continue
        if count >= MAX_EVENTS and log["type"] not in _CRITICAL_EVENTS:
            continue
        session.add(
            ExamIntegrityEvent(
                state_id=state.id, exam_kind=KIND, exam_ref=state.exam_ref, created_at=now, **log
            )
        )
        count += 1


def student_state(exam_ref, session_ref, device_id="", section="process", now=None):
    try:
        policy = read_policy(exam_ref, strict=True)
        if policy["mode"] == "off":
            return serialize(None, policy, now=now)
        with _session() as session:
            state = session.scalar(_state_query(exam_ref, session_ref))
            return serialize(state, policy, device_id=device_id, section=section, now=now)
    except Exception:
        return unavailable()


get_state = student_state


def record_event(
    exam_ref,
    session_ref,
    payload,
    *,
    current_section=None,
    submitted_sections=(),
    active_sections=None,
    now=None,
):
    now = as_utc(now)
    try:
        policy = read_policy(exam_ref, strict=True)
        if policy["mode"] == "off":
            return serialize(None, policy, now=now)
        with _session(write=True) as session:
            state = _get_or_create(session, exam_ref, session_ref)
            logs = transition(
                state,
                policy,
                payload,
                now=now,
                current_section=current_section,
                submitted_sections=submitted_sections,
                active_sections=active_sections,
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
        return unavailable()


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
    with _session(write=True) as session:
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


def emergency_off(exam_ref, actor=None, now=None):
    """Change only mode and its audit fields; preserve the teacher's thresholds."""
    now = as_utc(now)
    with _session(write=True) as session:
        policy = session.scalar(
            select(ExamIntegrityPolicy).where(
                ExamIntegrityPolicy.exam_kind == KIND, ExamIntegrityPolicy.exam_ref == str(exam_ref)
            )
        )
        if policy is None:
            policy = ExamIntegrityPolicy(exam_kind=KIND, exam_ref=str(exam_ref), created_at=now)
            session.add(policy)
        policy.mode, policy.updated_by, policy.updated_at = "off", actor, now
        session.flush()
        return {
            "mode": "off",
            "max_leaves": policy.max_leaves,
            "max_hidden_seconds": policy.max_hidden_seconds,
        }


def admin_action(exam_ref, session_ref, action, actor=None, exempt=True, now=None):
    if action not in {"unlock", "reset-device", "exempt"}:
        raise ValueError("invalid_action")
    now = as_utc(now)
    policy = read_policy(exam_ref, strict=True)
    with _session(write=True) as session:
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
    policy = read_policy(exam_ref, strict=True)
    with _session() as session:
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
    with _session() as session:
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
