"""Read-only vocabulary fields for the existing assigned practice task list."""

from sqlalchemy import and_, func

from models import DictationBook, Task, VocabularyLearningFlow, db
from services.task_date_gate import task_date_access, task_workflow_status
from services.vocabulary_mastery import (
    VALID_GOALS,
    is_vocabulary_v2_task,
    vocabulary_goal_for_task,
)

GOAL_LABELS = {
    "reading": "阅读词汇",
    "listening": "听力词汇",
    "writing": "写作词汇",
    "comprehensive": "综合训练",
}


def vocabulary_task_clause(*, enabled=True):
    if not enabled:
        return False
    return and_(
        Task.dictation_book_id.isnot(None),
        func.lower(func.trim(Task.vocabulary_goal)).in_(sorted(VALID_GOALS)),
    )


def vocabulary_flow_states(profile, tasks) -> dict[int, str]:
    """Fetch only this student's existing flow states, without claiming any."""
    user_id = getattr(profile, "user_id", None)
    task_ids = [task.id for task in tasks if is_vocabulary_v2_task(task)]
    if not user_id or not task_ids:
        return {}
    rows = db.session.query(VocabularyLearningFlow.task_id, VocabularyLearningFlow.status).filter(
        VocabularyLearningFlow.student_id == user_id,
        VocabularyLearningFlow.task_id.in_(task_ids),
    )
    return dict(rows.all())


def vocabulary_task_metadata(task, *, book_titles=None) -> dict:
    """One presentation contract for task cards and detail-page boot data.

    A supplied mapping, even empty, is authoritative and never triggers a
    per-task lookup. Detail requests omit it and load their one book directly.
    """
    if book_titles is None:
        book = db.session.get(DictationBook, task.dictation_book_id)
        book_title = book.title if book else None
    else:
        book_title = book_titles.get(task.dictation_book_id)
    book_title = book_title or "词汇学习"
    start = getattr(task, "dictation_word_start", None)
    end = getattr(task, "dictation_word_end", None)
    scope = f"第{start or 1}–{end}词" if end else f"第{start or 1}词起"
    title = str(getattr(task, "detail", "") or "").strip() or f"{book_title} · {scope}"
    goal = str(task.vocabulary_goal or "").strip().lower()
    return {
        "id": task.id,
        "title": title,
        "book_id": task.dictation_book_id,
        "book_title": book_title,
        "word_start": start,
        "word_end": end,
        "scope": scope,
        "goal": goal,
        "goal_label": GOAL_LABELS.get(goal, "词汇学习"),
    }


def vocabulary_practice_fields(task, flow_state=None, *, book_titles=None) -> dict | None:
    goal = vocabulary_goal_for_task(task)
    if not goal:
        return None
    return {
        "category": "词汇",
        "source_label": GOAL_LABELS[goal],
        "title": vocabulary_task_metadata(task, book_titles=book_titles)["title"],
        "url": f"/practice/vocabulary/tasks/{task.id}",
        "in_progress": flow_state == VocabularyLearningFlow.STATUS_ACTIVE,
    }


def _is_vocabulary_list_task(task) -> bool:
    # Existing task kinds retain priority even on mixed legacy records.
    return is_vocabulary_v2_task(task) and not (
        task.grading_mode in {"question_type_practice", "writing_practice"}
        or task.listening_exercise_id
        or task.reading_test_id
    )


def _list_payload(task, flow_state, book_titles) -> dict:
    fields = vocabulary_practice_fields(task, flow_state, book_titles=book_titles)
    access = task_date_access(task)
    access_fields = access.as_dict()
    workflow = task_workflow_status(task)
    status = "done" if workflow == "completed" else workflow
    if status == "pending" and fields["in_progress"]:
        status = "in_progress"
        access_fields.update(task_status=status, task_status_label="进行中")
        if access.state not in {"future", "expired"}:
            access_fields["status_label"] = "进行中"
    completion = float(task.completion_rate) if task.completion_rate is not None else None
    return {
        "id": task.id,
        "category": fields["category"],
        "source_label": fields["source_label"],
        "title": fields["title"],
        "url": fields["url"],
        "date": task.date or "",
        "status": status,
        "raw_status": status,
        "display_status": access.state,
        **access_fields,
        "accuracy": round(float(task.accuracy or 0.0), 1) if status == "done" else None,
        "completion_rate": round(completion, 1) if completion is not None else None,
        "note": task.note or "",
    }


def vocabulary_list_payloads(profile, tasks, *, enabled=False) -> dict[int, dict]:
    """Batch the added flow and book-title lookups, with one query each.

    Shared date/workflow helpers may still load existing PlanItem relations.
    """
    if not enabled:
        return {}
    tasks = [task for task in tasks if _is_vocabulary_list_task(task)]
    if not tasks:
        return {}
    states = vocabulary_flow_states(profile, tasks)
    book_ids = {task.dictation_book_id for task in tasks}
    titles = dict(
        db.session.query(DictationBook.id, DictationBook.title)
        .filter(DictationBook.id.in_(book_ids))
        .all()
    )
    return {task.id: _list_payload(task, states.get(task.id), titles) for task in tasks}


def sort_practice_tasks(tasks, vocabulary_payloads, legacy_key):
    """Sort active vocabulary exactly as an existing in-progress task."""

    def key(task):
        original = legacy_key(task)
        payload = vocabulary_payloads.get(task.id)
        if payload and payload["status"] == "in_progress":
            return (0, *original[1:])
        return original

    return sorted(tasks, key=key)
