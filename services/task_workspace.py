"""Query helpers for the staff task workspace.

The task table used to render every row for the selected period and hide most
of them in the browser.  These helpers keep filtering, metrics and pagination
in SQL so the HTML payload stays bounded as task history grows.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import ceil

from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from models import Task

PAGE_SIZES = (10, 25, 50)
TASK_STATUSES = {"pending", "progress", "submitted", "done"}


def _clean(value: object, *, limit: int = 120) -> str:
    return str(value or "").strip()[:limit]


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _iso_date(value: object) -> str:
    candidate = _clean(value, limit=10)
    if len(candidate) != 10:
        return ""
    try:
        year, month, day = (int(part) for part in candidate.split("-"))
        date(year, month, day)
    except (TypeError, ValueError):
        return ""
    return candidate


def _literal_contains(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@dataclass(frozen=True)
class TaskWorkspaceFilters:
    query: str = ""
    student: str = ""
    student_exact: bool = False
    category: str = ""
    status: str = ""
    due_date: str = ""
    task_id: int | None = None
    page: int = 1
    page_size: int = 10

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> TaskWorkspaceFilters:
        status = _clean(values.get("status"), limit=16)
        page_size = _positive_int(values.get("page_size"), 10)
        if page_size not in PAGE_SIZES:
            page_size = 10
        raw_task_id = _positive_int(values.get("task_id"), 0)
        explicit_student = _clean(values.get("student"), limit=64)
        legacy_student = _clean(values.get("student_name"), limit=64)
        return cls(
            query=_clean(values.get("q"), limit=100),
            student=explicit_student or legacy_student,
            student_exact=bool(legacy_student and not explicit_student),
            category=_clean(values.get("category"), limit=64),
            status=status if status in TASK_STATUSES else "",
            due_date=_iso_date(values.get("due_date")),
            task_id=raw_task_id or None,
            page=_positive_int(values.get("page"), 1),
            page_size=page_size,
        )

    def query_params(self) -> dict[str, str | int]:
        params: dict[str, str | int] = {}
        for key, value in (
            ("q", self.query),
            ("student_name" if self.student_exact else "student", self.student),
            ("category", self.category),
            ("status", self.status),
            ("due_date", self.due_date),
            ("task_id", self.task_id),
        ):
            if value not in (None, ""):
                params[key] = value
        params["page_size"] = self.page_size
        return params


def apply_task_filters(query, filters: TaskWorkspaceFilters, student_names: Sequence[str] = ()):
    if filters.task_id:
        query = query.filter(Task.id == filters.task_id)
    if filters.query:
        term = f"%{_literal_contains(filters.query)}%"
        query = query.filter(
            or_(
                Task.student_name.ilike(term, escape="\\"),
                Task.category.ilike(term, escape="\\"),
                Task.detail.ilike(term, escape="\\"),
                Task.note.ilike(term, escape="\\"),
            )
        )
    if filters.student:
        if filters.student_exact:
            query = query.filter(Task.student_name == filters.student)
        else:
            conditions = [
                Task.student_name.ilike(
                    f"%{_literal_contains(filters.student)}%", escape="\\"
                )
            ]
            if student_names:
                conditions.append(Task.student_name.in_(tuple(student_names)))
            query = query.filter(or_(*conditions))
    if filters.category:
        query = query.filter(Task.category == filters.category)
    if filters.status:
        query = query.filter(Task.status == filters.status)
    if filters.due_date:
        query = query.filter(Task.date == filters.due_date)
    return query


def task_metrics(query) -> dict[str, float | int]:
    total, completed, seconds, average = query.with_entities(
        func.count(Task.id),
        func.coalesce(func.sum(case((Task.status == "done", 1), else_=0)), 0),
        func.coalesce(func.sum(Task.actual_seconds), 0),
        func.avg(Task.accuracy),
    ).one()
    return {
        "total": int(total or 0),
        "completed": int(completed or 0),
        "total_minutes": round(float(seconds or 0) / 60, 1),
        "avg_accuracy": round(float(average or 0), 1),
    }


def top_students(query, *, limit: int = 5) -> list[dict[str, float | int | str | None]]:
    rows = (
        query.with_entities(
            Task.student_name,
            func.coalesce(func.sum(Task.actual_seconds), 0).label("seconds"),
            func.count(Task.id).label("tasks"),
            func.avg(Task.accuracy).label("accuracy"),
        )
        .group_by(Task.student_name)
        .order_by(func.coalesce(func.sum(Task.actual_seconds), 0).desc(), func.count(Task.id).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "name": (name or "").strip() or "未填写学生",
            "minutes": round(float(seconds or 0) / 60, 1),
            "tasks": int(tasks or 0),
            "accuracy": round(float(accuracy), 1) if accuracy is not None else None,
        }
        for name, seconds, tasks, accuracy in rows
    ]


def paginate_tasks(query, filters: TaskWorkspaceFilters) -> tuple[list[Task], dict[str, int | bool]]:
    total = query.order_by(None).count()
    page_count = max(1, ceil(total / filters.page_size))
    page = min(filters.page, page_count)
    items = (
        query.options(
            joinedload(Task.listening_test_submission),
            joinedload(Task.reading_test_submission),
        )
        .order_by(Task.date.desc(), Task.id.desc())
        .offset((page - 1) * filters.page_size)
        .limit(filters.page_size)
        .all()
    )
    start = (page - 1) * filters.page_size + 1 if total else 0
    end = min(page * filters.page_size, total)
    return items, {
        "page": page,
        "page_size": filters.page_size,
        "page_count": page_count,
        "total": total,
        "start": start,
        "end": end,
        "has_previous": page > 1,
        "has_next": page < page_count,
    }


def pagination_window(page: int, page_count: int) -> list[int | None]:
    """Return a compact page-number window; ``None`` represents an ellipsis."""

    if page_count <= 7:
        return list(range(1, page_count + 1))
    numbers = {1, page_count, page - 1, page, page + 1}
    ordered = sorted(number for number in numbers if 1 <= number <= page_count)
    result: list[int | None] = []
    previous = 0
    for number in ordered:
        if previous and number - previous > 1:
            result.append(None)
        result.append(number)
        previous = number
    return result
