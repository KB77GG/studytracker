"""Publish an explicitly frozen full-reading Test as one atomic bundle.

The caller already holds the assignment writer lock and has checked date,
actor/version and automatic enrollment/window. Old unmarked passage entries
continue through the ordinary publisher without any grouping inference.
"""

from __future__ import annotations

import json

from flask import current_app

from models import db, utcnow_naive
from models_task_planner import TaskPlannerEntry, TaskPlannerSeries, TaskPlannerSeriesItem
from services import task_planner as planner
from services import task_planner_resources as resources
from services.task_assignment_duplicates import begin_assignment_transaction


def _bundle(row):
    link = planner._series_item(row.id)
    if not link:
        return None
    series = db.session.get(TaskPlannerSeries, link.series_id)
    if not series:
        return None
    frozen = json.loads(series.definition_json).get("rows", [])
    if not 0 <= link.order_index < len(frozen):
        raise planner.TaskPlannerError("连续安排条目与预览不一致，请重新安排", status=409)
    marker = frozen[link.order_index].get("bundle_id")
    if marker is None:
        return None
    if not isinstance(marker, str) or not marker:
        raise planner.TaskPlannerError("整套阅读标识无效，请重新安排", status=409)
    indices = [index for index, item in enumerate(frozen) if item.get("bundle_id") == marker]
    members = db.session.query(TaskPlannerEntry, TaskPlannerSeriesItem.order_index).join(
        TaskPlannerSeriesItem, TaskPlannerSeriesItem.entry_id == TaskPlannerEntry.id,
    ).filter(TaskPlannerSeriesItem.series_id == link.series_id,
             TaskPlannerSeriesItem.order_index.in_(indices)).order_by(TaskPlannerSeriesItem.order_index).all()
    return members, frozen


def _validate_shape(row, members, frozen, allowed_statuses=None):
    allowed_statuses = {"ready", "failed"} if allowed_statuses is None else allowed_statuses
    if len(members) != 3 or row.id not in {entry.id for entry, _index in members}:
        raise planner.TaskPlannerError("整套阅读条目不完整，请取消后重新安排")
    tests, numbers = set(), set()
    for entry, index in members:
        selection = json.loads(entry.selection_json)
        if (entry.kind != "reading_passage" or entry.student_id != row.student_id
                or entry.target_date != row.target_date
                or entry.status not in allowed_statuses or not entry.confirmed_at
                or frozen[index].get("kind") != "reading_passage"
                or frozen[index].get("target_date") != entry.target_date.isoformat()
                or frozen[index].get("selection") != selection):
            raise planner.TaskPlannerError("整套阅读条目已变化，请取消未布置部分后重新安排")
        tests.add(selection.get("test_id"))
        numbers.add(selection.get("passage_number"))
    if len(tests) != 1 or not next(iter(tests)) or numbers != {1, 2, 3}:
        raise planner.TaskPlannerError("整套阅读必须包含同一Test的Passage 1、2、3")


def bundle_entry_ids(row):
    """Best-effort runner accounting; malformed metadata cannot stop its loop."""
    try:
        found = _bundle(row)
        return [entry.id for entry, _index in found[0]] if found else [row.id]
    except (ValueError, TypeError, AttributeError, KeyError):
        return [row.id]


def _prepare(row, members, frozen, now=None):
    _validate_shape(row, members, frozen)
    profile = planner._student(row.student_id)
    prepared_rows = []
    for entry, _index in members:
        planner._actor(entry.confirmed_by)
        planner._series_prerequisite(entry, profile, now)
        prerequisite = planner._prerequisite(entry.prerequisite_task_id, profile, entry.target_date)
        if not planner._prerequisite_complete(prerequisite, profile):
            raise planner.TaskPlannerError("前置任务尚未完成或被退回，请处理后重新安排")
        prepared = json.loads(entry.prepared_json)
        resources.revalidate_resource(prepared)
        planner._conflicts(entry, prepared, profile)
        prepared_rows.append(prepared)
    return profile, prepared_rows


def _block(members, message, actor_id):
    for entry, _index in members:
        if entry.status not in {"published", "cancelled"}:
            entry.status, entry.last_error = "blocked", str(message)[:500]
            entry.version += 1
            planner._event(entry, "blocked", actor_id, entry.last_error)
    db.session.commit()


def _failed(row_id, locked_versions, actor_id):
    db.session.rollback()
    current_app.logger.exception("Task planner full-reading bundle failed for entry %s", row_id)
    begin_assignment_transaction()
    entries = [planner._entry(entry_id) for entry_id in locked_versions]
    if all(entry.version == locked_versions[entry.id] and entry.status in {"ready", "failed"}
           for entry in entries):
        for entry in entries:
            entry.status = "failed"
            entry.last_error = "整套阅读布置失败，本套任务未保存。可以重试；持续失败请联系管理员。"
            entry.version += 1
            planner._event(entry, "failed", actor_id, entry.last_error)
    db.session.commit()
    return planner._entry(row_id)


def publish_reading_bundle(row, *, actor_id, automatic, now=None):
    """Return the requested native entry, or None when it has no bundle marker."""
    found = _bundle(row)
    if found is None:
        return None
    members, frozen = found
    locked_versions = {entry.id: entry.version for entry, _index in members}
    try:
        profile, prepared_rows = _prepare(row, members, frozen, now)
    except ValueError as exc:
        _block(members, f"整套阅读暂未布置：{exc}", actor_id)
        return row
    row_id = row.id
    try:
        for (entry, _index), prepared in zip(members, prepared_rows, strict=True):
            task = resources.create_resource_task(
                profile, prepared, creator_id=entry.confirmed_by,
                due_date=entry.target_date.isoformat(), planned_minutes=entry.planned_minutes,
                note=entry.note, idempotency_key=f"planner:{entry.id}:{profile.id}",
            )
            db.session.flush()
            entry.status, entry.last_error = "published", ""
            entry.published_task_id, entry.published_at = task.id, utcnow_naive()
            entry.version += 1
            planner._event(entry, "auto_publish" if automatic else "publish", actor_id)
        db.session.commit()
        return row
    except Exception:
        return _failed(row_id, locked_versions, actor_id)
