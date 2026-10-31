"""Finite learning lines: preview exact dated work, then confirm it atomically.

There is no hidden rolling cursor: one confirmed line freezes at most 31 days
of ordinary planner entries. Existing scheduler and assignment contracts apply.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from types import SimpleNamespace

from models import DictationBook, DictationWord, StudentProfile, db, utcnow_naive
from models_task_planner import TaskPlannerEntry, TaskPlannerSeries, TaskPlannerSeriesItem
from services import task_planner as planner
from services import task_planner_resources as resources
from services.question_type_practice import cambridge_test_numbers, practice_type_members
from services.task_assignment_duplicates import begin_assignment_transaction

REQUEST_FIELDS = (
    "name", "student_id", "start_date", "end_date", "weekday_counts", "kind",
    "selection", "source_scope", "start_group_id", "wait_for_previous",
    "planned_minutes", "note", "preview_hash", "source_scopes", "start_resource_id",
)
SEQUENCE_KINDS = frozenset({"listening_test", "reading_passage", "intensive"})
NEW_REQUEST_FIELDS = frozenset({"source_scopes", "start_resource_id"})


def _digest(value):
    return hashlib.sha256(planner._dump(value).encode("utf-8")).hexdigest()


def _natural(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower())
                 for part in re.split(r"(\d+)", str(value)))


def _sort_group(row):
    numbers = cambridge_test_numbers(row)
    if numbers:
        return (0, numbers, row["unit_index"], row["group_index"])
    return (1, _natural(row["test_id"]), row["unit_index"], row["group_index"])


def _source_groups(subject, standard_type):
    if subject not in {"reading", "listening"}:
        raise planner.TaskPlannerError("请选择阅读或听力")
    allowed = practice_type_members(subject, standard_type)
    return sorted((row for row in resources._groups()
                   if row["subject"] == subject and row["standard_type"] in allowed
                   and row["safety_status"] == "publishable"), key=_sort_group)


def _matches_scope(row, scope):
    numbers = cambridge_test_numbers(row)
    return scope == "test:" + row["test_id"] or bool(
        numbers and scope == "cambridge:" + str(numbers[0]))


def _group_label(row):
    return (f"{row['test_title']} · {row['unit_label']} {row['unit_number']} · "
            f"{row['original_question_range']} · {row['standard_type_display_label']}")


def series_sources(subject, standard_type="all", source_scope=None):
    """Explicit book/test choices and naturally ordered starting groups."""
    rows = _source_groups(subject, standard_type)
    sources = {}
    for row in rows:
        keys = [("test:" + row["test_id"], row["test_title"])]
        numbers = cambridge_test_numbers(row)
        if numbers:
            keys.insert(0, ("cambridge:" + str(numbers[0]), f"剑雅 {numbers[0]}"))
        for key, label in keys:
            sources.setdefault(key, {"id": key, "label": label, "count": 0})["count"] += 1
    if source_scope and source_scope not in sources:
        raise planner.TaskPlannerError("所选教材或试卷不存在，或没有可布置的该类题组")
    return {
        "sources": list(sources.values()),
        "groups": [{"id": row["question_group_id"], "label": _group_label(row),
                    "question_count": row["question_count"]}
                   for row in rows if source_scope and _matches_scope(row, source_scope)],
    }


def _definition(data, actor_id, now):
    if not isinstance(data, dict):
        raise planner.TaskPlannerError("连续安排内容必须为对象")
    planner._actor(actor_id)
    profile = planner._student(data.get("student_id"))
    kind = data.get("kind")
    if kind not in {"question_type", "dictation"} | SEQUENCE_KINDS:
        raise planner.TaskPlannerError("不支持的连续安排类型")
    start = planner._date(data.get("start_date"), now)
    end = planner._date(data.get("end_date"), now)
    if not 0 <= (end - start).days <= 30:
        raise planner.TaskPlannerError("连续安排须为1至31天，结束日期不能早于开始日期")
    counts = data.get("weekday_counts")
    if not isinstance(counts, list) or len(counts) != 7:
        raise planner.TaskPlannerError("请分别填写周一至周日的学习量")
    limit = 1200 if kind == "dictation" else 20
    counts = [planner._integer(count, "每日学习量", 0, limit) for count in counts]
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    schedule = [(day, counts[day.weekday()]) for day in days if counts[day.weekday()]]
    if not schedule:
        raise planner.TaskPlannerError("所选日期范围内至少需要安排一天学习")
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 120:
        raise planner.TaskPlannerError("请填写1至120字的学习线名称")
    wait = data.get("wait_for_previous", False)
    if not isinstance(wait, bool):
        raise planner.TaskPlannerError("前置完成条件必须为true或false")
    note = str(data.get("note") or "").strip()
    if len(note) > 200:
        raise planner.TaskPlannerError("说明不能超过200字")
    selection = data.get("selection")
    if not isinstance(selection, dict):
        raise planner.TaskPlannerError("请选择连续练习内容")
    definition = {
        "student_id": profile.id, "name": name, "kind": kind,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "weekday_counts": counts, "wait_for_previous": wait,
        "planned_minutes": planner._integer(data.get("planned_minutes", 20), "预计分钟", 1, 180),
        "note": note,
    }
    if kind in SEQUENCE_KINDS:
        scopes = data.get("source_scopes")
        start_id = data.get("start_resource_id")
        if (not isinstance(scopes, list) or not 1 <= len(scopes) <= 100
                or any(not isinstance(scope, str) or not scope.strip() for scope in scopes)):
            raise planner.TaskPlannerError("请选择1至100个明确的教材或来源")
        if not isinstance(start_id, str) or not start_id.strip():
            raise planner.TaskPlannerError("请选择起始篇章或套题")
        definition.update(source_scopes=sorted(set(scopes)), start_resource_id=start_id)
    return profile, definition, schedule, selection


def _sequence_selections(kind, data, selection, schedule):
    from services.task_planner_sequence import sequence_sources

    catalog = sequence_sources(kind, selection, data["source_scopes"])
    items = catalog["items"]
    ids = [item["id"] for item in items]
    if data["start_resource_id"] not in ids:
        raise planner.TaskPlannerError("起始内容不属于所选教材或练习范围，或已不可布置")
    queue = items[ids.index(data["start_resource_id"]):]
    needed = sum(count for _, count in schedule)
    if len(queue) < needed:
        raise planner.TaskPlannerError(f"所选起点后仅有{len(queue)}项，安排需要{needed}项，缺少{needed-len(queue)}项；请补充教材、缩短范围或调整每日数量")
    offset = 0
    for day, count in schedule:
        for item in queue[offset:offset + count]:
            yield day, 1, item.get("question_count", 0), item["selection"], [item["label"]]
        offset += count


def _selections(kind, data, selection, schedule):
    if kind in SEQUENCE_KINDS:
        yield from _sequence_selections(kind, data, selection, schedule)
        return
    needed = sum(count for _, count in schedule)
    if kind == "question_type":
        subject = str(selection.get("subject") or "")
        standard_type = str(selection.get("standard_type") or "all")
        scope, start_id = str(data.get("source_scope") or ""), str(data.get("start_group_id") or "")
        if not scope or not start_id:
            raise planner.TaskPlannerError("请明确选择教材或试卷，以及起始题组")
        groups = [row for row in _source_groups(subject, standard_type) if _matches_scope(row, scope)]
        ids = [row["question_group_id"] for row in groups]
        if start_id not in ids:
            raise planner.TaskPlannerError("起始题组不属于所选教材和题型，或已不可布置")
        groups = groups[ids.index(start_id):]
        if len(groups) < needed:
            raise planner.TaskPlannerError(f"所选起点后仅有{len(groups)}组，安排需要{needed}组，缺少{needed-len(groups)}组；请缩短范围或调整每日数量")
        offset = 0
        for day, count in schedule:
            chosen = groups[offset:offset + count]
            offset += count
            yield day, count, sum(row["question_count"] for row in chosen), {
                "subject": subject, "standard_type": standard_type,
                "group_ids": [row["question_group_id"] for row in chosen],
                "pace": selection.get("pace") or "training",
            }, [_group_label(row) for row in chosen]
        return
    book_id = planner._integer(selection.get("book_id"), "词书")
    start = planner._integer(selection.get("word_start"), "开始词序")
    book = db.session.get(DictationBook, book_id)
    if not book or not book.is_active:
        raise planner.TaskPlannerError("词书不存在或已停用")
    words = DictationWord.query.filter(DictationWord.book_id == book_id, DictationWord.sequence >= start).order_by(
        DictationWord.sequence, DictationWord.id).all()
    if not words or words[0].sequence != start:
        raise planner.TaskPlannerError("开始词序在该词书中不存在")
    if len(words) < needed:
        raise planner.TaskPlannerError(f"所选起点后仅有{len(words)}词，安排需要{needed}词，缺少{needed-len(words)}词；请缩短范围或调整每日数量")
    selected = words[:needed]
    if len({word.sequence for word in words}) != len(words):
        raise planner.TaskPlannerError("词书存在重复词序，请先整理词书后再连续安排")
    offset = 0
    for day, count in schedule:
        chosen = selected[offset:offset + count]
        offset += count
        yield day, count, 0, {
            "book_id": book_id, "word_start": chosen[0].sequence, "word_end": chosen[-1].sequence,
            "vocabulary_goal": selection.get("vocabulary_goal") or "reading",
            "dictation_mode": selection.get("dictation_mode") or "audio_to_en",
            "dictation_order": selection.get("dictation_order") or "sequence",
        }, [f"{book.title} · 第{chosen[0].sequence}–{chosen[-1].sequence}词"]


def _build_preview(data, actor_id, now=None):
    profile, definition, schedule, selection = _definition(data, actor_id, now)
    rows, prepared_rows = [], []
    for day, count, questions, choice, labels in _selections(definition["kind"], data, selection, schedule):
        prepared = resources.prepare_resource(definition["kind"], choice)
        planner._conflicts(SimpleNamespace(id=None, student_id=profile.id, target_date=day), prepared, profile)
        if any(resources.resource_overlap(prepared, previous) for previous in prepared_rows):
            raise planner.TaskPlannerError("本次连续安排包含重复或重叠内容，请检查所选教材来源", code="duplicate_plan", status=409)
        rows.append({"target_date": day.isoformat(), "title": prepared["title"],
                     "unit_count": count, "question_count": questions, "selection": prepared["selection"],
                     "content_labels": labels})
        prepared_rows.append(prepared)
    public = {
        **definition, "rows": rows,
        "quota_unit": _quota_unit(definition["kind"], rows),
        "totals": {"days": len({row["target_date"] for row in rows}), "units": sum(row["unit_count"] for row in rows),
                   "questions": sum(row["question_count"] for row in rows)},
        "warnings": (["上一学习日尚有任务未发布、未完成或被退回时，本线后续日期进入待处理；同日任务不互相等待。需助教处理或取消剩余后重建，不会自动顺延。"]
                     if definition["wait_for_previous"] else []),
    }
    public["preview_hash"] = _digest({"definition": definition, "rows": rows, "prepared": prepared_rows})
    return public, prepared_rows


def _quota_unit(kind, rows):
    if kind == "question_type":
        return "组"
    if kind == "dictation":
        return "词"
    if kind == "listening_test" and rows and rows[0].get("selection", {}).get("section_number") is None:
        return "套"
    return "篇"


def preview_series(data, actor_id, now=None):
    return _build_preview(data, actor_id, now)[0]


def _series(series_id, version=None):
    row = db.session.get(TaskPlannerSeries, planner._integer(series_id, "学习线"))
    if row is None:
        raise planner.TaskPlannerError("学习线不存在", status=404)
    if version is not None and row.version != planner._integer(version, "版本"):
        raise planner.TaskPlannerError("学习线已更新，请刷新后操作", code="version_conflict", status=409)
    return row


def _items(series_id):
    return TaskPlannerSeriesItem.query.filter_by(series_id=series_id).order_by(TaskPlannerSeriesItem.order_index).all()


def create_series(data, actor_id, now=None):
    """Revalidate preview under the writer lock; save all entries or none."""
    begin_assignment_transaction()
    try:
        planner._actor(actor_id)
        if not isinstance(data, dict):
            raise planner.TaskPlannerError("连续安排内容必须为对象")
        key = data.get("request_key")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{15,95}", key):
            raise planner.TaskPlannerError("缺少有效的连续安排请求标识，请重新预览")
        request_hash = _digest({"actor_id": actor_id, "data": {
            name: data.get(name) for name in REQUEST_FIELDS if name not in NEW_REQUEST_FIELDS or name in data
        }})
        existing = TaskPlannerSeries.query.filter_by(request_key=key).first()
        if existing:
            if existing.request_hash != request_hash:
                raise planner.TaskPlannerError("该请求标识已经用于不同安排，请重新预览", code="idempotency_conflict", status=409)
            db.session.commit()
            return existing
        preview, prepared_rows = _build_preview(data, actor_id, now)
        if data.get("preview_hash") != preview["preview_hash"]:
            raise planner.TaskPlannerError("安排内容或资源已变化，请重新预览后保存", code="preview_changed", status=409)
        row = TaskPlannerSeries(
            student_id=preview["student_id"], name=preview["name"], kind=preview["kind"],
            start_date=planner._date(preview["start_date"], now), end_date=planner._date(preview["end_date"], now),
            weekday_counts_json=planner._dump(preview["weekday_counts"]),
            definition_json=planner._dump({name: value for name, value in preview.items() if name != "warnings"}),
            wait_for_previous=preview["wait_for_previous"], status="draft", version=1,
            request_key=key, request_hash=request_hash, preview_hash=preview["preview_hash"],
            created_by=actor_id, updated_by=actor_id,
        )
        db.session.add(row)
        db.session.flush()
        previous_day_id, last_entry_id, last_date = None, None, None
        for index, (item, prepared) in enumerate(zip(preview["rows"], prepared_rows, strict=True)):
            if item["target_date"] != last_date:
                previous_day_id = last_entry_id
            entry = TaskPlannerEntry(
                student_id=row.student_id, target_date=planner._date(item["target_date"], now),
                kind=row.kind, title=prepared["title"][:240], selection_json=planner._dump(prepared["selection"]),
                prepared_json=planner._dump(prepared), planned_minutes=preview["planned_minutes"], note=preview["note"],
                status="draft", version=1, created_by=actor_id, updated_by=actor_id,
            )
            db.session.add(entry)
            db.session.flush()
            db.session.add(TaskPlannerSeriesItem(series_id=row.id, entry_id=entry.id,
                                                previous_entry_id=previous_day_id, order_index=index,
                                                unit_count=item["unit_count"]))
            planner._event(entry, "save_draft", actor_id, f"连续安排：{row.name}")
            last_entry_id, last_date = entry.id, item["target_date"]
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def confirm_series(series_id, version, actor_id, now=None):
    begin_assignment_transaction()
    try:
        planner._actor(actor_id)
        row = _series(series_id, version)
        if row.status != "draft":
            raise planner.TaskPlannerError("只有整条草稿学习线可以确认", status=409)
        profile = planner._student(row.student_id)
        items = _items(row.id)
        if not items:
            raise planner.TaskPlannerError("学习线没有安排，无法确认", status=409)
        for item in items:
            entry = planner._entry(item.entry_id)
            if entry.status != "draft":
                raise planner.TaskPlannerError("学习线包含已变化的安排，请刷新后处理", status=409)
            planner._date(entry.target_date.isoformat(), now)
            prepared = json.loads(entry.prepared_json)
            resources.revalidate_resource(prepared)
            planner._conflicts(entry, prepared, profile)
            entry.status, entry.last_error = "ready", ""
            entry.confirmed_by, entry.confirmed_at = actor_id, utcnow_naive()
            entry.updated_by, entry.version = actor_id, entry.version + 1
            planner._event(entry, "confirm", actor_id, f"连续安排：{row.name}")
        row.status, row.version, row.updated_by = "ready", row.version + 1, actor_id
        row.confirmed_by, row.confirmed_at = actor_id, utcnow_naive()
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def cancel_series(series_id, version, actor_id, now=None):
    begin_assignment_transaction()
    try:
        planner._actor(actor_id)
        row = _series(series_id, version)
        if row.status == "cancelled":
            raise planner.TaskPlannerError("该学习线已取消", status=409)
        for item in _items(row.id):
            entry = planner._entry(item.entry_id)
            if entry.status not in {"published", "cancelled"}:
                entry.status, entry.last_error = "cancelled", ""
                entry.version, entry.updated_by = entry.version + 1, actor_id
                planner._event(entry, "cancel", actor_id, f"取消连续安排：{row.name}")
        row.status, row.version, row.updated_by = "cancelled", row.version + 1, actor_id
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def list_series(student_id=None):
    query = TaskPlannerSeries.query
    if student_id not in (None, ""):
        query = query.filter_by(student_id=planner._integer(student_id, "学生"))
    return query.order_by(TaskPlannerSeries.id.desc()).limit(200).all()


def series_payload(row):
    items = _items(row.id)
    profile = db.session.get(StudentProfile, row.student_id)
    definition = json.loads(row.definition_json)
    counts = {}
    for item in items:
        entry = db.session.get(TaskPlannerEntry, item.entry_id)
        if entry:
            counts[entry.status] = counts.get(entry.status, 0) + 1
    return {
        "id": row.id, "version": row.version, "name": row.name, "student_id": row.student_id,
        "kind": row.kind, "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(),
        "quota_unit": definition.get("quota_unit") or _quota_unit(row.kind, definition.get("rows", [])),
        "weekday_counts": json.loads(row.weekday_counts_json), "wait_for_previous": row.wait_for_previous,
        "status": row.status, "entry_ids": [item.entry_id for item in items], "entry_count": len(items),
        "counts": counts, "status_counts": counts, "published_count": counts.get("published", 0),
        "student_name": profile.full_name if profile else "学生档案已停用",
    }
