"""Create question-type assignments inside the existing Task/PlanItem system."""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime

from sqlalchemy import func

from models import PlanItem, StudentProfile, StudyPlan, Task, db
from services.question_type_practice import (
    TASK_TYPE,
    dump_snapshot,
    question_type_display_label,
)


def _plan_date(value: str | None) -> date:
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


def _study_plan(profile: StudentProfile, due_date: str, creator_id: int) -> StudyPlan:
    target_date = _plan_date(due_date)
    plan = StudyPlan.query.filter_by(
        student_id=profile.id,
        plan_date=target_date,
        is_deleted=False,
    ).first()
    if plan:
        return plan
    plan = StudyPlan(
        student_id=profile.id,
        plan_date=target_date,
        status=StudyPlan.STATUS_PUBLISHED,
        created_by=creator_id,
        published_by=creator_id,
        published_at=datetime.utcnow(),
    )
    db.session.add(plan)
    db.session.flush()
    return plan


def _plan_item(
    *,
    profile: StudentProfile,
    due_date: str,
    creator_id: int,
    title: str,
    note: str,
    planned_minutes: int,
    token: str,
    snapshot: dict,
) -> PlanItem:
    plan = _study_plan(profile, due_date, creator_id)
    order_index = (
        db.session.query(func.max(PlanItem.order_index))
        .filter(PlanItem.plan_id == plan.id, PlanItem.is_deleted.is_(False))
        .scalar()
        or 0
    ) + 1
    metadata = {
        "task_type": TASK_TYPE,
        "subject": snapshot["subject"],
        "standard_type": snapshot["standard_type"],
        "pace": snapshot["pace"],
        "snapshot_hash": snapshot["snapshot_hash"],
        "group_ids": snapshot["group_ids"],
        "question_count": snapshot["question_count"],
    }
    item = PlanItem(
        plan_id=plan.id,
        exam_system="雅思",
        module="听力" if snapshot["subject"] == "listening" else "阅读",
        task_name="题型专项",
        custom_title=title[:128],
        instructions=(note or "")[:2000],
        order_index=order_index,
        resource_type=PlanItem.RESOURCE_QUESTION_TYPE_PRACTICE,
        resource_id=snapshot["snapshot_hash"],
        access_token=token,
        resource_metadata=json.dumps(metadata, ensure_ascii=False),
        planned_minutes=planned_minutes,
        student_status=PlanItem.STUDENT_PENDING,
        review_status=PlanItem.REVIEW_PENDING,
    )
    db.session.add(item)
    db.session.flush()
    return item


def assignment_title(snapshot: dict) -> str:
    subject = "听力" if snapshot["subject"] == "listening" else "阅读"
    pace = "考试节奏" if snapshot["pace"] == "exam" else "训练节奏"
    return (
        f"{subject} · {question_type_display_label(snapshot['standard_type'])} · "
        f"{len(snapshot['group_ids'])}组/{snapshot['question_count']}题 · {pace}"
    )


def create_assignment(
    *,
    profile: StudentProfile,
    snapshot: dict,
    creator_id: int,
    due_date: str,
    planned_minutes: int,
    note: str = "",
) -> Task:
    """Create one Task plus its normal published PlanItem shadow."""

    token = secrets.token_urlsafe(24)
    title = assignment_title(snapshot)
    plan_item = _plan_item(
        profile=profile,
        due_date=due_date,
        creator_id=creator_id,
        title=title,
        note=note,
        planned_minutes=planned_minutes,
        token=token,
        snapshot=snapshot,
    )
    task = Task(
        date=_plan_date(due_date).isoformat(),
        student_name=profile.full_name,
        category=(
            "雅思-听力-题型专项" if snapshot["subject"] == "listening" else "雅思-阅读-题型专项"
        ),
        detail=title[:200],
        status="pending",
        note=(note or "")[:200],
        created_by=creator_id,
        plan_item_id=plan_item.id,
        planned_minutes=max(1, min(int(planned_minutes or 20), 180)),
        grading_mode=TASK_TYPE,
        question_ids=dump_snapshot(snapshot),
        listening_access_token=token if snapshot["subject"] == "listening" else None,
        reading_access_token=token if snapshot["subject"] == "reading" else None,
    )
    db.session.add(task)
    db.session.flush()
    return task


def assignment_url(task: Task) -> str | None:
    if task.grading_mode != TASK_TYPE:
        return None
    token = task.listening_access_token or task.reading_access_token
    if not token:
        return None
    return f"/practice/question-types/task/{task.id}?token={token}"


def complete_assignment_plan_item(task: Task, *, submitted_at: datetime) -> None:
    item = task.plan_item
    if not item:
        return
    item.student_status = PlanItem.STUDENT_SUBMITTED
    item.review_status = PlanItem.REVIEW_PENDING
    item.submitted_at = submitted_at
    item.actual_seconds = max(int(item.actual_seconds or 0), int(task.actual_seconds or 0))
