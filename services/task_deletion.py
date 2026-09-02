"""Safety checks for deleting accidentally assigned legacy tasks."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from models import AuditLogEntry, PlanItem, Task, db, utcnow_naive
from services.task_assignment_duplicates import begin_assignment_transaction


class TaskDeletionError(RuntimeError):
    """Stable application error returned by staff task-delete endpoints."""

    def __init__(self, code: str, status: int):
        super().__init__(code)
        self.code = code
        self.status = status


def task_reference_columns():
    """Return every mapped foreign-key column that points at ``task.id``."""

    references = []
    for table in db.metadata.tables.values():
        for column in table.columns:
            if any(foreign_key.target_fullname == "task.id" for foreign_key in column.foreign_keys):
                references.append((table, column))
    return tuple(references)


def task_plan_item_is_shared(task: Task) -> bool:
    """Return whether another legacy task still points at this plan item."""

    if not task.plan_item_id:
        return False
    return bool(
        Task.query.filter(
            Task.plan_item_id == task.plan_item_id,
            Task.id != task.id,
        ).first()
    )


def task_deletion_block_reason(
    task: Task,
    *,
    plan_item_is_shared: bool | None = None,
) -> str | None:
    """Explain why a task is no longer safe to cancel.

    The staff delete action is intentionally limited to fresh, accidental
    assignments. Once a learner, timer, review, or practice flow has touched a
    task, its history must be preserved instead of cascading or orphaning it.
    """

    if (task.status or Task.__table__.c.status.default.arg or "pending") != "pending":
        return "task_has_activity"
    if any(
        (
            int(task.actual_seconds or 0) > 0,
            bool(task.started_at),
            bool(task.ended_at),
            bool(task.student_submitted),
            bool(task.submitted_at),
            bool(task.evidence_photos),
            bool(task.student_note),
            bool(task.feedback_text),
            bool(task.feedback_audio),
            bool(task.feedback_image),
            float(task.completion_rate or 0) > 0,
            float(task.accuracy or 0) > 0,
        )
    ):
        return "task_has_activity"

    if plan_item_is_shared is None:
        plan_item_is_shared = task_plan_item_is_shared(task)
    plan_item = task.plan_item
    if plan_item and not plan_item_is_shared and any(
        (
            plan_item.student_status != PlanItem.STUDENT_PENDING,
            int(plan_item.actual_seconds or 0) > 0,
            int(plan_item.manual_minutes or 0) > 0,
            bool(plan_item.student_comment),
            bool(plan_item.submitted_at),
            plan_item.review_status != PlanItem.REVIEW_PENDING,
            bool(plan_item.review_comment),
            bool(plan_item.review_by),
            bool(plan_item.review_at),
            bool(plan_item.locked),
            int(plan_item.student_reset_count or 0) > 0,
            bool(plan_item.sessions),
            bool(plan_item.evidences),
            bool(plan_item.review_logs),
        )
    ):
        return "task_has_activity"

    available_tables = set(sa_inspect(db.session.get_bind()).get_table_names())
    for table, column in task_reference_columns():
        if table.name not in available_tables:
            continue
        linked_row = db.session.execute(
            select(column).where(column == task.id).limit(1)
        ).first()
        if linked_row:
            return "task_has_activity"
    return None


def delete_unstarted_task(
    task_id: int,
    *,
    actor_id: int,
    is_allowed: Callable[[Task], bool],
    permission_error: str = "no_permission",
) -> None:
    """Cancel one fresh mistaken assignment while preserving all history."""

    try:
        # Serialize the read/check/cancel sequence on SQLite. The Task row is
        # retained as a tombstone, so even a delayed learner write that began
        # from a stale read cannot become an orphan.
        begin_assignment_transaction()
        task = db.session.get(Task, task_id)
        if not task:
            db.session.rollback()
            raise TaskDeletionError("task_not_found", 404)
        if not is_allowed(task):
            db.session.rollback()
            raise TaskDeletionError(permission_error, 403)

        plan_item_is_shared = task_plan_item_is_shared(task)
        block_reason = task_deletion_block_reason(
            task,
            plan_item_is_shared=plan_item_is_shared,
        )
        if block_reason:
            db.session.rollback()
            raise TaskDeletionError(block_reason, 409)

        if task.plan_item and not plan_item_is_shared:
            task.plan_item.is_deleted = True
        db.session.add(
            AuditLogEntry(
                entity_type="task",
                entity_id=task.id,
                action="delete",
                actor_id=actor_id,
                metadata_payload={"reason": "staff_deleted_unstarted_assignment"},
            )
        )
        task.status = Task.STATUS_CANCELLED
        task.cancelled_at = utcnow_naive()
        task.assignment_idempotency_key = None
        task.listening_access_token = None
        task.reading_access_token = None
        db.session.commit()
    except TaskDeletionError:
        raise
    except IntegrityError as error:
        db.session.rollback()
        raise TaskDeletionError("task_has_activity", 409) from error
    except OperationalError as error:
        db.session.rollback()
        raise TaskDeletionError("task_delete_busy", 409) from error
