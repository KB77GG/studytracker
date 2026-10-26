"""Stable task bindings for the web-only IELTS writing library."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import quote

from models import PlanItem, StudentProfile, Task, WritingTypingAttempt, db
from services.task_date_gate import TaskDateGateError, assert_task_write_allowed
from services.writing_library import (
    get_exercise,
    get_mother_topic,
    load_catalog,
    load_mother_topics,
)

TASK_TYPE = "writing_practice"
RESOURCE_EXERCISE = "exercise"
RESOURCE_MOTHER_TOPIC = "mother_topic"
RESOURCE_TYPES = {RESOURCE_EXERCISE, RESOURCE_MOTHER_TOPIC}
PLAN_RESOURCE_EXERCISE = "writing_exercise"
PLAN_RESOURCE_MOTHER_TOPIC = "writing_mother_topic"


class WritingAssignmentError(ValueError):
    """Raised when a task does not point at a valid writing resource."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def catalog_options() -> list[dict[str, Any]]:
    """Return the safe, compact inventory used by the staff task picker."""

    options: list[dict[str, Any]] = []
    for exercise in load_catalog()["exercises"]:
        options.append(
            {
                "resource_type": RESOURCE_EXERCISE,
                "id": exercise["id"],
                "title": exercise["topic_zh"],
                "title_en": exercise["title_en"],
                "label": exercise["task_label"],
                "meta": exercise["task_type_zh"],
                "prompt": exercise["prompt"],
                "planned_minutes": 20 if exercise["task"] == "task1" else 40,
            }
        )
    for topic in load_mother_topics()["topics"]:
        options.append(
            {
                "resource_type": RESOURCE_MOTHER_TOPIC,
                "id": topic["id"],
                "title": f"{topic['code']} · {topic['title_zh']}",
                "title_en": topic["title_en"],
                "label": "大作文母题",
                "meta": f"{topic['prompt_count']} 道同类题 · 4 条逻辑链",
                "prompt": topic["representative_prompt"]["prompt"],
                "planned_minutes": 30,
            }
        )
    return options


def build_snapshot(resource_type: Any, resource_id: Any) -> dict[str, Any]:
    """Validate a picker value and freeze its display metadata on the task."""

    kind = _text(resource_type)
    identifier = _text(resource_id)
    if kind not in RESOURCE_TYPES or not identifier:
        raise WritingAssignmentError("请选择写作练习")
    if kind == RESOURCE_EXERCISE:
        exercise = get_exercise(identifier)
        if not exercise:
            raise WritingAssignmentError("选择的写作真题不存在")
        return {
            "version": 1,
            "writing_resource_type": kind,
            "writing_resource_id": exercise["id"],
            "title": exercise["topic_zh"],
            "title_en": exercise["title_en"],
            "label": exercise["task_label"],
            "task": exercise["task"],
            "task_type_zh": exercise["task_type_zh"],
            "prompt": exercise["prompt"],
            "planned_minutes": 20 if exercise["task"] == "task1" else 40,
        }
    topic = get_mother_topic(identifier)
    if not topic:
        raise WritingAssignmentError("选择的大作文母题不存在")
    return {
        "version": 1,
        "writing_resource_type": kind,
        "writing_resource_id": topic["id"],
        "title": f"{topic['code']} · {topic['title_zh']}",
        "title_en": topic["title_en"],
        "label": "大作文母题",
        "task": "task2_topic",
        "task_type_zh": topic["family"],
        "prompt": topic["representative_prompt"]["prompt"],
        "planned_minutes": 30,
    }


def dump_snapshot(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))


def snapshot_from_task(task: Task | None) -> dict[str, Any] | None:
    if not task or task.grading_mode != TASK_TYPE:
        return None
    snapshot = _json_object(task.question_ids)
    kind = _text(snapshot.get("writing_resource_type"))
    identifier = _text(snapshot.get("writing_resource_id"))
    if kind not in RESOURCE_TYPES or not identifier:
        return None
    return snapshot


def typing_attempt_ids(task: Task) -> list[int]:
    """Return only server-created attempt bindings, never infer by resource/date."""

    values = (snapshot_from_task(task) or {}).get("writing_attempt_ids", [])
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(value for value in values if type(value) is int and value > 0))


def bind_typing_attempt(task: Task, attempt: WritingTypingAttempt) -> None:
    """Persist the association in the same transaction as attempt creation."""

    snapshot = snapshot_from_task(task)
    if (
        not snapshot
        or snapshot["writing_resource_type"] != RESOURCE_EXERCISE
        or snapshot["writing_resource_id"] != attempt.exercise_id
        or not attempt.id
        or attempt.student_profile.full_name != task.student_name
    ):
        raise WritingAssignmentError("writing_task_not_found")
    snapshot["writing_attempt_ids"] = [*typing_attempt_ids(task), attempt.id]
    # A concurrent start must not silently overwrite another attempt's binding.
    changed = Task.query.filter_by(
        id=task.id, question_ids=task.question_ids, status=task.status
    ).update({Task.question_ids: dump_snapshot(snapshot)}, synchronize_session=False)
    if changed != 1:
        raise WritingAssignmentError("writing_task_changed_retry")
    db.session.expire(task, ["question_ids"])


def typing_attempt_task(
    attempt: WritingTypingAttempt,
    *,
    student: StudentProfile,
    task_id: Any = None,
) -> Task | None:
    """Find an attempt's original task, even if a finish omits its task ID."""

    candidates = Task.query.filter_by(
        student_name=student.full_name, grading_mode=TASK_TYPE
    ).all()
    bound = [task for task in candidates if attempt.id in typing_attempt_ids(task)]
    if len(bound) > 1:
        raise WritingAssignmentError("writing_attempt_task_mismatch")
    task = bound[0] if bound else None
    if task_id:
        requested = assigned_task(
            task_id, student=student, resource_type=RESOURCE_EXERCISE,
            resource_id=attempt.exercise_id,
        )
        if not requested or not task or requested.id != task.id:
            raise WritingAssignmentError("writing_attempt_task_mismatch")
    if task:
        snapshot = snapshot_from_task(task)
        if (
            snapshot["writing_resource_type"] != RESOURCE_EXERCISE
            or snapshot["writing_resource_id"] != attempt.exercise_id
        ):
            raise WritingAssignmentError("writing_attempt_task_mismatch")
        # Completed retries are read-only, including after the task's cutoff.
        if attempt.status != WritingTypingAttempt.STATUS_COMPLETED:
            require_student_task(
                task.id, student=student, resource_type=RESOURCE_EXERCISE,
                resource_id=attempt.exercise_id,
            )
    return task


def record_topic_completion(task: Task, *, submitted_at: datetime, duration_seconds: int) -> None:
    snapshot = snapshot_from_task(task)
    if snapshot and snapshot["writing_resource_type"] == RESOURCE_MOTHER_TOPIC:
        snapshot["writing_topic_result"] = {
            "completed_at": submitted_at.isoformat() + "Z",
            "duration_seconds": max(0, int(duration_seconds)),
        }
        task.question_ids = dump_snapshot(snapshot)


def assignment_url(task: Task, *, absolute: bool = False) -> str | None:
    snapshot = snapshot_from_task(task)
    if not snapshot:
        return None
    identifier = quote(snapshot["writing_resource_id"], safe="")
    if snapshot["writing_resource_type"] == RESOURCE_MOTHER_TOPIC:
        path = f"/writing/topics/{identifier}?task_id={int(task.id)}"
    else:
        path = f"/writing/{identifier}?task_id={int(task.id)}"
    return f"https://studytracker.xin{path}" if absolute else path


def plan_resource(snapshot: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    kind = snapshot["writing_resource_type"]
    resource_type = (
        PLAN_RESOURCE_MOTHER_TOPIC if kind == RESOURCE_MOTHER_TOPIC else PLAN_RESOURCE_EXERCISE
    )
    return resource_type, snapshot["writing_resource_id"], dict(snapshot)


def assigned_task(
    task_id: Any,
    *,
    student: StudentProfile | None,
    resource_type: str,
    resource_id: str,
) -> Task | None:
    """Resolve an assignment without allowing one student to claim another's task."""

    try:
        task_key = int(task_id)
    except (TypeError, ValueError):
        return None
    task = db.session.get(Task, task_key)
    snapshot = snapshot_from_task(task)
    if not task or not snapshot:
        return None
    if (
        snapshot["writing_resource_type"] != resource_type
        or snapshot["writing_resource_id"] != resource_id
    ):
        return None
    if student and task.student_name != student.full_name:
        return None
    return task


def require_student_task(
    task_id: Any,
    *,
    student: StudentProfile,
    resource_type: str,
    resource_id: str,
) -> Task:
    task = assigned_task(
        task_id,
        student=student,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if not task:
        raise WritingAssignmentError("writing_task_not_found")
    try:
        assert_task_write_allowed(task)
    except TaskDateGateError as exc:
        raise WritingAssignmentError(exc.error) from exc
    return task


def complete_task(
    task: Task,
    *,
    submitted_at: datetime,
    duration_seconds: int = 0,
    accuracy: float | None = None,
    note: str = "",
) -> None:
    # A second tab may have loaded the same pending task before the first tab
    # committed. Claim completion before flushing either attempt's result.
    with db.session.no_autoflush:
        changed = Task.query.filter_by(id=task.id, status=task.status).update(
            {Task.status: "done"}, synchronize_session=False
        )
    if changed != 1:
        raise WritingAssignmentError("writing_task_changed_retry")
    elapsed = max(0, int(duration_seconds or 0))
    task.status = "done"
    task.completion_rate = 100.0
    task.actual_seconds = max(int(task.actual_seconds or 0), elapsed)
    task.student_submitted = True
    task.submitted_at = submitted_at
    task.ended_at = submitted_at
    if accuracy is not None:
        task.accuracy = max(0.0, min(100.0, float(accuracy)))
    if note:
        task.student_note = note[:500]
    item = task.plan_item
    if item:
        item.student_status = PlanItem.STUDENT_SUBMITTED
        item.review_status = PlanItem.REVIEW_PENDING
        item.submitted_at = submitted_at
        item.actual_seconds = max(int(item.actual_seconds or 0), elapsed)
        if note:
            item.student_comment = note[:255]
