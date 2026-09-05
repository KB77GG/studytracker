"""Beijing-time availability rules for scheduled student tasks.

The assignment date is a calendar day, not a rolling 24-hour window. Each
assignment keeps that date while receiving a fixed grace period until 03:00
the following day. This module is deliberately model-light so every
student-facing workflow can use the same decision without importing a
blueprint or duplicating date math.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc  # noqa: UP017 -- production runs Python 3.10.
TASK_CUTOFF_HOUR = 3

STATE_TODAY = "today"
STATE_FUTURE = "future"
STATE_EXPIRED = "expired"
STATE_COMPLETED = "completed"

_COMPLETED_TASK_STATUSES = frozenset({"done", "completed", "finished"})
_SUBMITTED_TASK_STATUSES = frozenset({"submitted"})
_IN_PROGRESS_TASK_STATUSES = frozenset({"progress", "in_progress", "started"})


class TaskDateGateError(Exception):
    """A stable, user-facing rejection for a student task write."""

    def __init__(
        self,
        error: str,
        message: str,
        *,
        state: str,
        task_date: date | None,
        status_label: str | None = None,
    ):
        super().__init__(error)
        self.error = error
        self.message = message
        self.status_code = 403
        self.details = {
            "task_date": task_date.isoformat() if task_date else None,
            "task_date_state": state,
            "availability_status": state,
            "availability_label": state_label(state),
            "status_label": status_label or state_label(state),
            "read_only": True,
            "can_start": False,
            "can_write": False,
        }


@dataclass(frozen=True)
class TaskDateAccess:
    """The derived state sent to clients and used by write endpoints."""

    task_date: date | None
    state: str
    label: str
    completed: bool
    can_start: bool
    can_write: bool
    read_only: bool
    is_grace_period: bool
    cutoff_at: datetime | None
    workflow_status: str
    workflow_label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_date": self.task_date.isoformat() if self.task_date else None,
            "task_date_state": self.state,
            "availability_status": self.state,
            "availability_label": self.label,
            "task_status": self.workflow_status,
            "task_status_label": self.workflow_label,
            "status_label": self.workflow_label,
            "can_start": self.can_start,
            "can_write": self.can_write,
            "read_only": self.read_only,
            "is_grace_period": self.is_grace_period,
            "task_cutoff_at": self.cutoff_at.isoformat() if self.cutoff_at else None,
        }


def _local_now(value: datetime | None = None) -> datetime:
    """Normalize a test or application clock to Asia/Shanghai.

    Naive values are interpreted as UTC, matching the database timestamp
    convention used by the existing services.  Tests that express a wall
    clock boundary can pass an aware ``Asia/Shanghai`` value.
    """

    value = value or datetime.now(SHANGHAI)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).astimezone(SHANGHAI)
    return value.astimezone(SHANGHAI)


def beijing_now(value: datetime | None = None) -> datetime:
    """Return the current instant in the product's calendar timezone."""

    return _local_now(value)


def beijing_today(value: datetime | None = None) -> date:
    return _local_now(value).date()


def next_beijing_midnight(value: datetime | None = None) -> datetime:
    return datetime.combine(
        beijing_today(value) + timedelta(days=1),
        datetime.min.time(),
        tzinfo=SHANGHAI,
    )


def active_task_grace_date(value: datetime | None = None) -> date | None:
    """Return yesterday while its assignment window remains open.

    The server clock is authoritative. From local midnight through 02:59:59,
    both the new calendar day's tasks and the previous assignment day's tasks
    can be available, while each task keeps its original assigned date.
    """

    current = _local_now(value)
    cutoff = datetime.combine(
        current.date(),
        time(hour=TASK_CUTOFF_HOUR),
        tzinfo=SHANGHAI,
    )
    if current < cutoff:
        return current.date() - timedelta(days=1)
    return None


def _parse_task_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def task_date(task: Any) -> date | None:
    """Read either a StudyPlan/PlanItem date or a legacy Task date."""

    plan = getattr(task, "plan", None)
    if plan is not None:
        planned = _parse_task_date(getattr(plan, "plan_date", None))
        if planned is not None:
            return planned
    plan_item = getattr(task, "plan_item", None)
    if plan_item is not None:
        plan = getattr(plan_item, "plan", None)
        planned = _parse_task_date(getattr(plan, "plan_date", None))
        if planned is not None:
            return planned
    return _parse_task_date(getattr(task, "plan_date", None)) or _parse_task_date(
        getattr(task, "date", None)
    )


def task_date_cutoff_local(task: Any) -> datetime | None:
    """Return the exclusive Shanghai-time cutoff for an assigned task."""

    planned = task_date(task)
    if planned is None:
        return None
    return datetime.combine(
        planned + timedelta(days=1),
        time(hour=TASK_CUTOFF_HOUR),
        tzinfo=SHANGHAI,
    )


def task_is_completed(task: Any) -> bool:
    """Only a genuinely finished task is a completed historical task.

    ``submitted`` remains a separate workflow state and is intentionally not
    treated as completed here. A submitted task stays eligible for the
    existing withdrawal flow during the assignment window, but becomes
    read-only after the next-day 03:00 cutoff.
    """

    status = str(getattr(task, "status", "") or "").strip().lower()
    if status in _COMPLETED_TASK_STATUSES:
        return True
    review_status = str(getattr(task, "review_status", "") or "").strip().lower()
    if review_status in {"approved", "completed", "done"}:
        return True
    return False


def task_is_submitted(task: Any) -> bool:
    """Return whether a learner submitted but staff has not completed it."""

    if task_is_completed(task):
        return False
    status = str(getattr(task, "status", "") or "").strip().lower()
    if status in _SUBMITTED_TASK_STATUSES:
        return True
    if bool(getattr(task, "student_submitted", False)):
        return True
    plan_item = getattr(task, "plan_item", None)
    plan_status = str(
        getattr(task, "student_status", "")
        or getattr(plan_item, "student_status", "")
        or ""
    ).strip().lower()
    if plan_status in _SUBMITTED_TASK_STATUSES:
        return True
    return bool(getattr(task, "submitted_at", None))


def task_workflow_status(task: Any) -> str:
    """Derive learner workflow state independently from date availability."""

    if task_is_completed(task):
        return "completed"
    if task_is_submitted(task):
        return "submitted"
    plan_item = getattr(task, "plan_item", None)
    plan_status = str(
        getattr(task, "student_status", "")
        or getattr(plan_item, "student_status", "")
        or ""
    ).strip().lower()
    status = str(getattr(task, "status", "") or "").strip().lower()
    if plan_status in _IN_PROGRESS_TASK_STATUSES or status in _IN_PROGRESS_TASK_STATUSES:
        return "in_progress"
    if getattr(task, "actual_seconds", 0):
        return "in_progress"
    return "pending"


def task_workflow_label(task: Any) -> str:
    return {
        "pending": "待完成",
        "in_progress": "进行中",
        "submitted": "已提交，待批改",
        "completed": "已完成",
    }[task_workflow_status(task)]


def task_display_status_label(task: Any, availability_state: str) -> str:
    """Keep submitted visible while expiring only genuinely incomplete work."""

    workflow = task_workflow_status(task)
    if workflow in {"pending", "in_progress"}:
        if availability_state == STATE_FUTURE:
            return "尚未开放"
        if availability_state == STATE_EXPIRED:
            return "未完成·已截止"
    return task_workflow_label(task)


def state_label(state: str) -> str:
    """Describe calendar availability without implying workflow completion."""

    return {
        STATE_TODAY: "今日可操作",
        STATE_FUTURE: "尚未开放",
        STATE_EXPIRED: "已截止",
        STATE_COMPLETED: "已完成",
    }.get(state, "今日可操作")


def task_date_access(
    task: Any,
    now: datetime | None = None,
    *,
    allow_completed_today: bool = False,
) -> TaskDateAccess:
    """Derive display and write state without changing task completion.

    Most completed assignments are immutable. Practice workflows that retain
    every attempt may opt into another submission during the assignment
    window; the same task remains read-only before it opens or after cutoff.
    """

    planned = task_date(task)
    current = _local_now(now)
    completed = task_is_completed(task)
    cutoff = task_date_cutoff_local(task)
    starts_at = (
        datetime.combine(planned, time.min, tzinfo=SHANGHAI)
        if planned is not None
        else None
    )
    within_assigned_window = bool(
        starts_at is not None
        and cutoff is not None
        and starts_at <= current < cutoff
    )
    is_grace_period = bool(
        within_assigned_window and planned is not None and current.date() > planned
    )
    if completed:
        state = STATE_COMPLETED
    elif planned is None or within_assigned_window:
        # Undated legacy/self-practice tasks predate the scheduled-assignment
        # contract. Preserve their existing behavior until they are assigned
        # a real calendar date.
        state = STATE_TODAY
    elif starts_at is not None and current < starts_at:
        state = STATE_FUTURE
    else:
        state = STATE_EXPIRED
    # Retrying a completed assignment is an explicit assigned-window
    # exception. An undated legacy row has no safe cutoff to compare against,
    # so it must not gain an open-ended retry window through this opt-in.
    writable = (state == STATE_TODAY and not completed) or (
        allow_completed_today and completed and within_assigned_window
    )
    return TaskDateAccess(
        task_date=planned,
        state=state,
        label=(
            "宽限期内·03:00 截止"
            if is_grace_period and not completed
            else state_label(state)
        ),
        completed=completed,
        can_start=writable,
        can_write=writable,
        read_only=not writable,
        is_grace_period=is_grace_period,
        cutoff_at=cutoff,
        workflow_status=task_workflow_status(task),
        workflow_label=task_display_status_label(task, state),
    )


def task_date_end_utc(task: Any) -> datetime | None:
    """Return the exclusive next-day 03:00 cutoff as naive UTC."""

    local_end = task_date_cutoff_local(task)
    if local_end is None:
        return None
    return local_end.astimezone(UTC).replace(tzinfo=None)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def bounded_task_session_end(
    task: Any,
    started_at: datetime,
    now: datetime | None = None,
    seconds_hint: int | None = None,
) -> datetime:
    """Choose a session end that cannot pass now or the task cutoff."""

    current = _utc_naive(now or datetime.utcnow())
    started = _utc_naive(started_at)
    candidate = (
        started + timedelta(seconds=max(0, int(seconds_hint)))
        if seconds_hint is not None
        else current
    )
    candidate = min(candidate, current)
    cutoff = task_date_end_utc(task)
    if cutoff is not None:
        candidate = min(candidate, cutoff)
    return max(candidate, started)


def close_expired_task_session(
    session: Any,
    task: Any,
    now: datetime | None = None,
) -> bool:
    """Close one open session exactly at the next-day 03:00 boundary.

    Callers must verify ownership before invoking this helper. It only
    handles an already-expired task whose session started before the boundary;
    future tasks and sessions opened after the boundary are never closable.
    The model's ``close`` method preserves the repository's naive-UTC storage
    convention and computes the capped duration.
    """

    if getattr(session, "ended_at", None):
        return False
    current = _utc_naive(now or datetime.utcnow())
    access = task_date_access(task, current)
    cutoff = task_date_end_utc(task)
    started = getattr(session, "started_at", None)
    if access.state != STATE_EXPIRED or cutoff is None or started is None:
        return False
    started_utc = _utc_naive(started)
    if started_utc >= cutoff or current < cutoff:
        return False
    session.close(bounded_task_session_end(task, started, current))
    return True


def assert_task_write_allowed(
    task: Any,
    now: datetime | None = None,
    *,
    allow_completed_today: bool = False,
) -> TaskDateAccess:
    """Raise a stable error unless a task can be changed right now."""

    access = task_date_access(
        task,
        now,
        allow_completed_today=allow_completed_today,
    )
    if access.can_write:
        return access
    if access.state == STATE_FUTURE:
        raise TaskDateGateError(
            "task_not_open",
            "该任务尚未开放，请在所属日期再开始。",
            state=access.state,
            task_date=access.task_date,
            status_label=access.workflow_label,
        )
    if access.state == STATE_EXPIRED:
        raise TaskDateGateError(
            "task_expired",
            "该任务已于次日凌晨3:00截止，当前仅可查看，不能继续提交。",
            state=access.state,
            task_date=access.task_date,
            status_label=access.workflow_label,
        )
    raise TaskDateGateError(
        "task_completed_read_only",
        "该任务已完成，当前仅可查看结果。",
        state=access.state,
        task_date=access.task_date,
        status_label=access.workflow_label,
    )


def add_task_date_access(
    payload: dict[str, Any], task: Any, now: datetime | None = None
) -> dict[str, Any]:
    """Add derived fields while preserving the original completion fields."""

    payload.update(task_date_access(task, now).as_dict())
    return payload


def gate_error_payload(error: TaskDateGateError) -> dict[str, Any]:
    return {"ok": False, "error": error.error, "message": error.message, **error.details}
