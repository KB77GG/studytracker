"""Read-only vocabulary fields for the existing assigned practice task list."""

from sqlalchemy import and_, func

from models import DictationBook, Task, VocabularyLearningFlow, db
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


def vocabulary_task_clause():
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


def vocabulary_practice_fields(task, flow_state=None) -> dict | None:
    goal = vocabulary_goal_for_task(task)
    if not goal:
        return None
    title = str(getattr(task, "detail", "") or "").strip()
    if not title:
        book = db.session.get(DictationBook, task.dictation_book_id)
        book_title = book.title if book else "词汇学习"
        start = getattr(task, "dictation_word_start", None) or 1
        end = getattr(task, "dictation_word_end", None)
        scope = f"第{start}–{end}词" if end else f"第{start}词起"
        title = f"{book_title} · {scope}"
    return {
        "category": "词汇",
        "source_label": GOAL_LABELS[goal],
        "title": title,
        "url": f"/practice/vocabulary/tasks/{task.id}",
        "in_progress": flow_state == VocabularyLearningFlow.STATUS_ACTIVE,
    }
