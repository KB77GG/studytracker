"""One transaction for vocabulary settlement and the linked plan projection."""

import json

from models import PlanItem, Task, VocabularyTaskSettlement
from services.task_plan_item_sync import sync_plan_item_from_task_submission
from services.vocabulary_group_learning import (
    VocabularyGroupLearningError,
    finalize_vocabulary_group_task,
)
from services.vocabulary_mastery import is_vocabulary_v2_task


def _owned_task(user, task_id):
    task = Task.query.filter(Task.id == task_id, Task.cancelled_at.is_(None)).first()
    profile = getattr(user, "student_profile", None)
    if not task:
        raise VocabularyGroupLearningError("task_not_found", 404)
    if not profile or task.student_name != profile.full_name:
        raise VocabularyGroupLearningError("forbidden", 403)
    if not is_vocabulary_v2_task(task):
        raise VocabularyGroupLearningError("task_not_vocabulary_v2", 409)
    return task


def settle_vocabulary_group_submission(user, task_id, payload, *, uploader_id=None) -> dict:
    """Return a durable result on retry without replaying submission effects.

    The HTTP caller commits or rolls back. A saved settlement is read-only even
    after the task cutoff; it cannot add evidence or increase either duration.
    """
    task = _owned_task(user, task_id)
    saved = VocabularyTaskSettlement.query.filter_by(student_id=user.id, task_id=task.id).first()
    if saved:
        token = str(payload.get("queue_token") or "").strip()
        if not token:
            raise VocabularyGroupLearningError("queue_token_required", 400)
        if token != saved.queue_token:
            raise VocabularyGroupLearningError("queue_changed", 409)
        return dict(json.loads(saved.result_json), already_settled=True)

    result = finalize_vocabulary_group_task(user, task.id, payload)
    # A concurrent unique-settlement loser can recover the winning result from
    # finalize after rollback. Its PlanItem already shares the saved submission
    # timestamp: do not append evidence or replay the losing caller's duration.
    item = task.plan_item
    already_synced = bool(
        item
        and item.student_status == PlanItem.STUDENT_SUBMITTED
        and item.submitted_at is not None
        and item.submitted_at == task.submitted_at
    )
    if not already_synced:
        sync_plan_item_from_task_submission(
            task,
            note=payload.get("note"),
            evidence_files=payload.get("evidence_files") or [],
            duration=task.actual_seconds or 0,
            uploader_id=uploader_id,
        )
    return result
