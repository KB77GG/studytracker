"""Finite one/two-week calendars, expanded into ordinary planner entries."""

from __future__ import annotations

import copy
import re
from datetime import timedelta

from services import task_planner as planner

ACTIVITY_FIELDS = frozenset({
    "id", "name", "kind", "selection", "source_scopes", "start_resource_id",
    "source_scope", "start_group_id", "planned_minutes", "note",
})
WAIT_WARNING = (
    "等待条件针对本安排上一学习日的全部任务；听力、阅读等活动共同检查。"
    "同日任务不互相等待，未完成时进入待处理，不会自动顺延或换题。"
)


def _activity(raw, common, actor_id, now):
    from services.task_planner_series import _definition

    if not isinstance(raw, dict) or set(raw) - ACTIVITY_FIELDS:
        raise planner.TaskPlannerError("练习项目包含不支持的字段")
    key = raw.get("id")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,39}", key):
        raise planner.TaskPlannerError("练习项目标识格式不正确")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise planner.TaskPlannerError("请填写1至80字的练习项目名称")
    # Reuse the ordinary line's limits and source validation; calendar quotas
    # are validated separately and cannot override the shared student/date.
    payload = {**common, **raw, "name": name.strip(), "weekday_counts": [1] * 7}
    _profile, definition, _schedule, selection = _definition(payload, actor_id, now)
    result = {
        "id": key, "name": name.strip(), "kind": definition["kind"],
        "selection": copy.deepcopy(selection), "planned_minutes": definition["planned_minutes"],
        "note": definition["note"],
    }
    for field in ("source_scopes", "start_resource_id", "ordered_book_ids"):
        if field in definition:
            result[field] = definition[field]
    for field in ("source_scope", "start_group_id"):
        if field in raw:
            result[field] = raw[field]
    return result


def _rules(raw, cycle_weeks, activities):
    if not isinstance(raw, list) or len(raw) != cycle_weeks:
        raise planner.TaskPlannerError("请填写与循环周数对应的每周安排")
    result, referenced = [], set()
    for week in raw:
        if not isinstance(week, list) or len(week) != 7:
            raise planner.TaskPlannerError("每周安排须包含周一至周日")
        normalized_week = []
        for day in week:
            if not isinstance(day, list) or len(day) > 12:
                raise planner.TaskPlannerError("每天最多安排12个练习项目")
            seen, normalized_day = set(), []
            for item in day:
                if not isinstance(item, dict) or set(item) != {"activity_id", "quantity"}:
                    raise planner.TaskPlannerError("日期规则须包含练习项目和数量")
                key = item.get("activity_id")
                if not isinstance(key, str) or key not in activities or key in seen:
                    raise planner.TaskPlannerError("日期规则引用了无效或重复的练习项目")
                maximum = 1200 if activities[key]["kind"] == "dictation" else 20
                quantity = planner._integer(item.get("quantity"), "每次学习量", 1, maximum)
                normalized_day.append({"activity_id": key, "quantity": quantity})
                seen.add(key)
                referenced.add(key)
            normalized_week.append(normalized_day)
        result.append(normalized_week)
    if not referenced:
        raise planner.TaskPlannerError("请至少安排一个练习项目")
    if referenced != set(activities):
        raise planner.TaskPlannerError("有练习项目尚未安排星期，请配置或移除")
    return result


def weekly_definition(data, actor_id, now=None):
    """Validate a weekly request and produce an explicit chronological calendar."""
    planner._actor(actor_id)
    profile = planner._student(data.get("student_id"))
    start, end = planner._date(data.get("start_date"), now), planner._date(data.get("end_date"), now)
    if not 0 <= (end - start).days <= 30:
        raise planner.TaskPlannerError("连续安排须为1至31天，结束日期不能早于开始日期")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        raise planner.TaskPlannerError("请填写1至120字的学习线名称")
    wait, skip = data.get("wait_for_previous", False), data.get("skip_assigned", True)
    if not isinstance(wait, bool) or not isinstance(skip, bool):
        raise planner.TaskPlannerError("等待与自动排除选项必须为true或false")
    cycle_weeks = planner._integer(data.get("cycle_weeks"), "循环周数", 1, 2)
    minutes = planner._integer(data.get("planned_minutes", 20), "预计分钟", 1, 180)
    note = str(data.get("note") or "").strip()
    if len(note) > 200:
        raise planner.TaskPlannerError("说明不能超过200字")
    common = {"student_id": profile.id, "start_date": start.isoformat(), "end_date": end.isoformat(),
              "wait_for_previous": wait, "planned_minutes": minutes, "note": note}
    raw = data.get("activities")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 12:
        raise planner.TaskPlannerError("请选择1至12个练习项目")
    activities = [_activity(item, common, actor_id, now) for item in raw]
    by_id = {item["id"]: item for item in activities}
    if len(by_id) != len(activities):
        raise planner.TaskPlannerError("练习项目标识不能重复")
    rules = _rules(data.get("week_rules"), cycle_weeks, by_id)
    anchor = start - timedelta(days=start.weekday())
    requests = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        week_index = ((day - anchor).days // 7) % cycle_weeks
        for item in rules[week_index][day.weekday()]:
            requests.append({"target_date": day, "activity_id": item["activity_id"],
                             "quantity": item["quantity"], "activity": by_id[item["activity_id"]]})
    if not requests:
        raise planner.TaskPlannerError("所选日期范围内没有学习日，请调整日期或星期安排")
    definition = {
        **common, "name": name.strip(), "kind": "weekly", "cycle_weeks": cycle_weeks,
        "cycle_anchor": anchor.isoformat(), "activities": activities, "week_rules": rules,
        "skip_assigned": skip,
        # Retained only for the existing storage column; week_rules is authoritative.
        "weekday_counts": [len(day) for day in rules[0]],
    }
    return profile, definition, requests


def build_allocated_preview(definition, requests, profile):
    from services.task_planner_allocator import allocate_requests
    from services.task_planner_series import _digest, _quota_unit

    rows, prepared_rows, skipped = allocate_requests(
        requests, profile, skip_assigned=definition.get("skip_assigned", False),
    )
    public = {
        **definition, "rows": rows, "skipped": skipped,
        "quota_unit": _quota_unit(definition["kind"], rows),
        "totals": {"days": len({row["target_date"] for row in rows}),
                   "units": sum(row["unit_count"] for row in rows),
                   "questions": sum(row["question_count"] for row in rows), "tasks": len(rows)},
        "warnings": [WAIT_WARNING] if definition["wait_for_previous"] else [],
    }
    if skipped:
        public["warnings"].append(f"已跳过{len(skipped)}项已布置、已确认或本次安排内重叠的内容，详情见跳过记录。")
    public["preview_hash"] = _digest({"definition": definition, "rows": rows,
                                      "prepared": prepared_rows, "skipped": skipped})
    return public, prepared_rows


def build_weekly_preview(data, actor_id, now=None):
    profile, definition, requests = weekly_definition(data, actor_id, now)
    return build_allocated_preview(definition, requests, profile)
