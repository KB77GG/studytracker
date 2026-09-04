"""Teacher-facing history helpers for the task assignment form."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

_STATUS_LABELS = {
    "pending": "未开始",
    "progress": "进行中",
    "in_progress": "进行中",
    "submitted": "已提交，待批改",
    "done": "已完成",
    "completed": "已完成",
    "finished": "已完成",
    "partial": "部分完成",
    "rejected": "已退回",
}
_NON_REPEATABLE_STATUSES = {"done", "completed", "finished", "submitted"}


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json_payload(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _question_ids(value: Any) -> list[int]:
    payload = _json_payload(value)
    if not isinstance(payload, list):
        return []
    ids = []
    for item in payload:
        item_id = _safe_int(item)
        if item_id is not None:
            ids.append(item_id)
    return ids


def _listening_section_number(value: Any) -> int | None:
    payload = _json_payload(value)
    if not isinstance(payload, dict):
        return None
    section = _safe_int(payload.get("listening_section_number"))
    return section if section in {1, 2, 3, 4} else None


def _resource_source(task: Any) -> tuple[str, str | None]:
    if getattr(task, "grading_mode", None) == "writing_practice":
        return "writing", None
    if getattr(task, "dictation_book_id", None):
        return "material", f"dictation-{task.dictation_book_id}"
    if getattr(task, "speaking_book_id", None):
        return "material", f"speaking-{task.speaking_book_id}"
    if getattr(task, "material_id", None):
        return "material", str(task.material_id)
    if getattr(task, "listening_exercise_id", None):
        return "listening", None
    if getattr(task, "reading_test_id", None):
        return "reading", None
    return "custom", None


def _range_label(task: Any, dictation_book: Any | None) -> str:
    start = _safe_int(getattr(task, "dictation_word_start", None), 1) or 1
    stored_end = _safe_int(getattr(task, "dictation_word_end", None))
    book_end = _safe_int(getattr(dictation_book, "word_count", None))
    end = stored_end or book_end
    if end:
        return f"第 {start}–{end} 词"
    return f"第 {start} 词起"


def _repeat_payload(task: Any) -> dict[str, Any]:
    source, material_value = _resource_source(task)
    writing_snapshot = (
        _json_payload(getattr(task, "question_ids", None))
        if source == "writing"
        else {}
    )
    if not isinstance(writing_snapshot, dict):
        writing_snapshot = {}
    return {
        "source": source,
        "category": getattr(task, "category", None) or "",
        "detail": getattr(task, "detail", None) or "",
        "planned_minutes": _safe_int(getattr(task, "planned_minutes", None), 0) or 0,
        "note": getattr(task, "note", None) or "",
        "material_value": material_value,
        "question_ids": _question_ids(getattr(task, "question_ids", None)),
        "dictation_word_start": _safe_int(getattr(task, "dictation_word_start", None), 1) or 1,
        "dictation_word_end": _safe_int(getattr(task, "dictation_word_end", None)),
        "vocabulary_goal": getattr(task, "vocabulary_goal", None) or "",
        "dictation_mode": getattr(task, "dictation_mode", None) or "audio_to_en",
        "dictation_order": getattr(task, "dictation_order", None) or "sequence",
        "speaking_phrase_start": _safe_int(getattr(task, "speaking_phrase_start", None), 1) or 1,
        "speaking_phrase_end": _safe_int(getattr(task, "speaking_phrase_end", None)),
        "listening_resource_type": getattr(task, "listening_resource_type", None) or "intensive",
        "listening_exercise_id": getattr(task, "listening_exercise_id", None) or "",
        "listening_training_mode": getattr(task, "listening_training_mode", None) or "",
        "listening_section_number": _listening_section_number(getattr(task, "question_ids", None)),
        "reading_test_id": getattr(task, "reading_test_id", None) or "",
        "reading_passage_number": _safe_int(getattr(task, "reading_passage_number", None)),
        "writing_resource_type": writing_snapshot.get("writing_resource_type") or "",
        "writing_resource_id": writing_snapshot.get("writing_resource_id") or "",
    }


def serialize_previous_day_assignments(
    tasks: Iterable[Any],
    *,
    dictation_books: dict[int, Any] | None = None,
    speaking_books: dict[int, Any] | None = None,
    materials: dict[int, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Group yesterday's tasks by exact student name for safe JSON rendering."""

    dictation_books = dictation_books or {}
    speaking_books = speaking_books or {}
    materials = materials or {}
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

    for task in tasks:
        student_name = str(getattr(task, "student_name", "") or "").strip()
        if not student_name:
            continue

        dictation_book_id = _safe_int(getattr(task, "dictation_book_id", None))
        speaking_book_id = _safe_int(getattr(task, "speaking_book_id", None))
        material_id = _safe_int(getattr(task, "material_id", None))
        dictation_book = dictation_books.get(dictation_book_id)
        speaking_book = speaking_books.get(speaking_book_id)
        material = materials.get(material_id)

        title = (
            getattr(dictation_book, "title", None)
            or getattr(speaking_book, "title", None)
            or getattr(material, "title", None)
            or getattr(task, "detail", None)
            or getattr(task, "category", None)
            or "未命名任务"
        )
        resource_kind = "task"
        resource_meta = "普通任务"
        range_label = ""
        if dictation_book_id:
            resource_kind = "dictation"
            range_label = _range_label(task, dictation_book)
            resource_meta = f"词书 · {range_label}"
        elif speaking_book_id:
            resource_kind = "speaking"
            start = _safe_int(getattr(task, "speaking_phrase_start", None), 1) or 1
            end = _safe_int(getattr(task, "speaking_phrase_end", None))
            range_label = f"第 {start}–{end} 句" if end else f"第 {start} 句起"
            resource_meta = f"跟读材料 · {range_label}"
        elif getattr(task, "listening_exercise_id", None):
            resource_kind = "listening"
            resource_meta = "听力题库"
        elif getattr(task, "reading_test_id", None):
            resource_kind = "reading"
            resource_meta = "阅读题库"
        elif getattr(task, "grading_mode", None) == "writing_practice":
            snapshot = _json_payload(getattr(task, "question_ids", None)) or {}
            resource_kind = "writing"
            title = snapshot.get("title") or title
            resource_meta = (
                "写作真题"
                if snapshot.get("writing_resource_type") == "exercise"
                else "大作文母题"
            )
        elif material_id:
            resource_kind = "material"
            resource_meta = "材料库"

        status = str(getattr(task, "status", "pending") or "pending").lower()
        student_submitted = bool(getattr(task, "student_submitted", False))
        display_status = status
        if student_submitted and status not in {"done", "completed", "finished"}:
            status_label = "已提交，待批改"
            repeatable = False
            display_status = "submitted"
        else:
            status_label = _STATUS_LABELS.get(status, status or "未知状态")
            repeatable = status not in _NON_REPEATABLE_STATUSES

        grouped[student_name].append(
            {
                "id": _safe_int(getattr(task, "id", None)),
                "title": str(title),
                "category": getattr(task, "category", None) or "",
                "resource_kind": resource_kind,
                "resource_meta": resource_meta,
                "range_label": range_label,
                "status": display_status,
                "status_label": status_label,
                "repeatable": repeatable,
                "repeat": _repeat_payload(task),
            }
        )

    return dict(grouped)


def load_previous_day_assignments(task_date: str) -> dict[str, list[dict[str, Any]]]:
    """Load and serialize all tasks assigned on one calendar date."""

    from models import DictationBook, MaterialBank, SpeakingBook, Task

    tasks = (
        Task.query.filter(Task.date == task_date)
        .order_by(Task.student_name.asc(), Task.id.desc())
        .all()
    )
    dictation_ids = {task.dictation_book_id for task in tasks if task.dictation_book_id}
    speaking_ids = {task.speaking_book_id for task in tasks if task.speaking_book_id}
    material_ids = {task.material_id for task in tasks if task.material_id}

    dictation_books = {
        book.id: book
        for book in (
            DictationBook.query.filter(DictationBook.id.in_(dictation_ids)).all()
            if dictation_ids
            else []
        )
    }
    speaking_books = {
        book.id: book
        for book in (
            SpeakingBook.query.filter(SpeakingBook.id.in_(speaking_ids)).all()
            if speaking_ids
            else []
        )
    }
    materials = {
        material.id: material
        for material in (
            MaterialBank.query.filter(MaterialBank.id.in_(material_ids)).all()
            if material_ids
            else []
        )
    }
    return serialize_previous_day_assignments(
        tasks,
        dictation_books=dictation_books,
        speaking_books=speaking_books,
        materials=materials,
    )
