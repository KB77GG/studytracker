from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from models import PlanItem, StudyPlan
from services.task_date_gate import (
    SHANGHAI,
    STATE_COMPLETED,
    STATE_EXPIRED,
    STATE_FUTURE,
    STATE_TODAY,
    TaskDateGateError,
    active_task_grace_date,
    assert_task_write_allowed,
    close_expired_task_session,
    task_date_access,
    task_date_cutoff_local,
    task_date_end_utc,
    task_workflow_status,
)

TODAY = datetime(2026, 9, 4, 12, 0, tzinfo=SHANGHAI)


def task(task_date, *, status="pending", plan_item=None, **attributes):
    return SimpleNamespace(
        date=task_date,
        status=status,
        plan_item=plan_item,
        **attributes,
    )


def test_assignment_is_writable_through_next_day_before_three_am():
    scheduled = task("2026-09-04")

    at_start = task_date_access(
        scheduled,
        datetime(2026, 9, 4, 0, 0, tzinfo=SHANGHAI),
    )
    during_grace = task_date_access(
        scheduled,
        datetime(2026, 9, 5, 2, 59, 59, 999999, tzinfo=SHANGHAI),
    )

    assert at_start.state == STATE_TODAY
    assert at_start.can_write is True
    assert at_start.is_grace_period is False
    assert during_grace.state == STATE_TODAY
    assert during_grace.can_write is True
    assert during_grace.is_grace_period is True
    assert during_grace.task_date.isoformat() == "2026-09-04"
    assert during_grace.label == "宽限期内·03:00 截止"
    assert during_grace.as_dict()["task_cutoff_at"].startswith("2026-09-05T03:00:00")


def test_next_day_three_am_expires_an_incomplete_task():
    scheduled = task("2026-09-04")

    access = task_date_access(
        scheduled,
        datetime(2026, 9, 5, 3, 0, tzinfo=SHANGHAI),
    )

    assert access.state == STATE_EXPIRED
    assert access.label == "已截止"
    assert access.workflow_label == "未完成·已截止"
    assert access.as_dict()["status_label"] == "未完成·已截止"
    assert access.read_only is True
    with pytest.raises(TaskDateGateError) as raised:
        assert_task_write_allowed(scheduled, datetime(2026, 9, 5, 3, 0, tzinfo=SHANGHAI))
    assert raised.value.error == "task_expired"
    assert raised.value.status_code == 403
    assert raised.value.message == "该任务已于次日凌晨3:00截止，当前仅可查看，不能继续提交。"


def test_home_grace_date_uses_shanghai_clock_and_ends_exactly_at_three():
    assert active_task_grace_date(
        datetime(2026, 9, 5, 2, 59, 59, tzinfo=SHANGHAI)
    ).isoformat() == "2026-09-04"
    assert active_task_grace_date(
        datetime(2026, 9, 5, 3, 0, tzinfo=SHANGHAI)
    ) is None
    assert task_date_cutoff_local(task("2026-09-04")).strftime(
        "%Y-%m-%d %H:%M"
    ) == "2026-09-05 03:00"


def test_future_task_is_not_open():
    scheduled = task("2026-09-05")

    access = task_date_access(scheduled, TODAY)

    assert access.state == STATE_FUTURE
    assert access.can_start is False
    with pytest.raises(TaskDateGateError) as raised:
        assert_task_write_allowed(scheduled, TODAY)
    assert raised.value.error == "task_not_open"
    assert raised.value.details["availability_label"] == "尚未开放"


def test_historical_completed_task_remains_viewable_but_read_only():
    scheduled = task("2026-09-03", status="done")

    access = task_date_access(scheduled, TODAY)

    assert access.state == STATE_COMPLETED
    assert access.completed is True
    assert access.label == "已完成"
    assert access.read_only is True
    with pytest.raises(TaskDateGateError) as raised:
        assert_task_write_allowed(scheduled, TODAY)
    assert raised.value.error == "task_completed_read_only"
    assert raised.value.message == "该任务已完成，当前仅可查看结果。"


def test_attempt_retaining_practice_can_retry_through_its_grace_period():
    scheduled = task("2026-09-04", status="done")
    just_before_cutoff = datetime(
        2026,
        9,
        5,
        2,
        59,
        59,
        999999,
        tzinfo=SHANGHAI,
    )
    at_cutoff = datetime(2026, 9, 5, 3, 0, tzinfo=SHANGHAI)

    default_access = task_date_access(scheduled, TODAY)
    retry_access = task_date_access(
        scheduled,
        just_before_cutoff,
        allow_completed_today=True,
    )

    assert default_access.read_only is True
    assert retry_access.state == STATE_COMPLETED
    assert retry_access.workflow_label == "已完成"
    assert retry_access.can_start is True
    assert retry_access.can_write is True
    assert retry_access.read_only is False
    assert retry_access.is_grace_period is True
    assert_task_write_allowed(
        scheduled,
        just_before_cutoff,
        allow_completed_today=True,
    )

    with pytest.raises(TaskDateGateError) as raised:
        assert_task_write_allowed(
            scheduled,
            at_cutoff,
            allow_completed_today=True,
        )
    assert raised.value.error == "task_completed_read_only"


def test_attempt_retaining_practice_does_not_open_an_undated_completed_task():
    scheduled = task(None, status="done")

    access = task_date_access(
        scheduled,
        TODAY,
        allow_completed_today=True,
    )

    assert access.state == STATE_COMPLETED
    assert access.can_write is False
    assert access.read_only is True
    with pytest.raises(TaskDateGateError) as raised:
        assert_task_write_allowed(
            scheduled,
            TODAY,
            allow_completed_today=True,
        )
    assert raised.value.error == "task_completed_read_only"


def test_plan_item_date_takes_precedence_for_legacy_linked_task():
    plan_item = SimpleNamespace(
        plan=SimpleNamespace(plan_date=TODAY.date()),
    )
    scheduled = task("2026-09-03", plan_item=plan_item)

    access = task_date_access(scheduled, TODAY + timedelta(hours=1))

    assert access.task_date == TODAY.date()
    assert access.state == STATE_TODAY
    assert access.can_write is True


@pytest.mark.parametrize(
    "scheduled, expected_today_write",
    [
        pytest.param(task("2026-09-04", status="submitted"), True, id="legacy_status"),
        pytest.param(
            task("2026-09-04", status="progress", student_submitted=True),
            True,
            id="legacy_flag",
        ),
        pytest.param(
            task(
                "2026-09-04",
                plan_item=SimpleNamespace(
                    plan=SimpleNamespace(plan_date="2026-09-04"),
                    student_status="submitted",
                    review_status="pending",
                ),
            ),
            True,
            id="plan_item_status",
        ),
    ],
)
def test_submitted_tasks_keep_workflow_label_and_same_day_withdrawal(
    scheduled, expected_today_write
):
    today_access = task_date_access(scheduled, TODAY)
    assert today_access.state == STATE_TODAY
    assert today_access.can_write is expected_today_write
    assert today_access.read_only is False
    assert task_workflow_status(scheduled) == "submitted"
    assert today_access.workflow_label == "已提交，待批改"
    assert today_access.as_dict()["status_label"] == "已提交，待批改"

    historical_access = task_date_access(scheduled, TODAY + timedelta(days=1))
    assert historical_access.state == STATE_EXPIRED
    assert historical_access.completed is False
    assert historical_access.read_only is True
    assert historical_access.label == "已截止"
    assert historical_access.workflow_label == "已提交，待批改"
    with pytest.raises(TaskDateGateError) as raised:
        assert_task_write_allowed(scheduled, TODAY + timedelta(days=1))
    assert raised.value.error == "task_expired"
    assert raised.value.details["status_label"] == "已提交，待批改"


def test_direct_plan_item_student_status_is_submitted_without_task_wrapper():
    plan = StudyPlan(
        student_id=1,
        plan_date=TODAY.date(),
        status=StudyPlan.STATUS_PUBLISHED,
        created_by=1,
    )
    item = PlanItem(
        plan=plan,
        exam_system="IELTS",
        module="listening",
        task_name="直接 PlanItem 提交态",
        student_status=PlanItem.STUDENT_SUBMITTED,
    )

    access = task_date_access(item, TODAY)

    assert task_workflow_status(item) == "submitted"
    assert access.state == STATE_TODAY
    assert access.workflow_label == "已提交，待批改"
    assert access.read_only is False

    historical = task_date_access(item, TODAY + timedelta(days=1))
    assert historical.state == STATE_EXPIRED
    assert historical.workflow_label == "已提交，待批改"
    assert historical.read_only is True


class _FakeTimerSession:
    def __init__(self, started_at):
        self.started_at = started_at
        self.ended_at = None
        self.duration_seconds = 0

    def close(self, ended_at):
        if self.ended_at:
            return
        self.ended_at = ended_at
        self.duration_seconds = max(
            0, int((ended_at - self.started_at).total_seconds())
        )


@pytest.mark.parametrize("session_name", ["PlanItemSession", "StudySession"])
def test_expired_timer_session_closes_at_three_am_for_both_models(session_name):
    scheduled = task("2026-09-04")
    session = _FakeTimerSession(datetime(2026, 9, 4, 18, 59, 50))
    now = datetime(2026, 9, 4, 19, 0, 5)

    assert close_expired_task_session(session, scheduled, now) is True
    assert session.ended_at == datetime(2026, 9, 4, 19, 0, 0)
    assert session.duration_seconds == 10, session_name
    assert close_expired_task_session(session, scheduled, now) is False
    assert task_date_end_utc(scheduled) == datetime(2026, 9, 4, 19, 0, 0)


def test_future_or_post_boundary_session_cannot_be_closed_by_expiry_helper():
    future = task("2026-09-05")
    future_session = _FakeTimerSession(datetime(2026, 9, 4, 19, 0, 0))
    assert close_expired_task_session(
        future_session,
        future,
        datetime(2026, 9, 4, 19, 0, 5),
    ) is False
    assert future_session.ended_at is None

    expired = task("2026-09-04")
    post_boundary_session = _FakeTimerSession(datetime(2026, 9, 4, 19, 0, 1))
    assert close_expired_task_session(
        post_boundary_session,
        expired,
        datetime(2026, 9, 4, 19, 0, 5),
    ) is False
    assert post_boundary_session.ended_at is None


@pytest.mark.parametrize(
    "resource_field",
    [
        "dictation_book_id",
        "vocabulary_book_id",
        "speaking_book_id",
        "listening_exercise_id",
        "reading_test_id",
    ],
)
def test_major_assigned_task_shapes_use_the_same_date_gate(resource_field):
    scheduled = task("2026-09-03", **{resource_field: 123})

    access = task_date_access(scheduled, TODAY)

    assert access.state == STATE_EXPIRED
    assert access.read_only is True
    with pytest.raises(TaskDateGateError) as raised:
        assert_task_write_allowed(scheduled, TODAY)
    assert raised.value.error == "task_expired"
