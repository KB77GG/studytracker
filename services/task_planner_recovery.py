"""Staff-reviewed recovery of unfinished work from confirmed learning lines.

Decisions are append-only. Original Tasks, answers and scores stay intact;
explicit entry IDs resolve only the selected gate. Makeup creates fresh native
Tasks today and shifts the remaining frozen calendar in one writer transaction.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date, timedelta
from types import SimpleNamespace

from models import Task, db, utcnow_naive
from models_task_planner import (
    TaskPlannerEntry,
    TaskPlannerRecoveryDecision,
    TaskPlannerSeries,
    TaskPlannerSeriesItem,
)
from services import task_planner as planner
from services import task_planner_bundles as bundles
from services import task_planner_resources as resources
from services import task_planner_series as series_service
from services.task_assignment_duplicates import begin_assignment_transaction
from services.task_date_gate import beijing_now, task_workflow_label
from services.task_planner_history import HistoryIndex

ACTIONS = {"makeup": "今天补做，后续顺延", "continue": "忽略本次未完成，继续计划"}
PENDING = {"ready", "blocked", "failed"}


def _decisions(series_id):
    return TaskPlannerRecoveryDecision.query.filter_by(series_id=series_id).order_by(
        TaskPlannerRecoveryDecision.id,
    ).all()


def waived_entry_ids(series_id, now=None):
    today = beijing_now(now).date()
    return {int(entry_id) for decision in _decisions(series_id) if decision.applied_date <= today
            for entry_id in json.loads(decision.snapshot_json).get("waived_entry_ids", [])}


def _rows(series_id):
    return db.session.query(TaskPlannerEntry, TaskPlannerSeriesItem).join(
        TaskPlannerSeriesItem, TaskPlannerSeriesItem.entry_id == TaskPlannerEntry.id,
    ).filter(TaskPlannerSeriesItem.series_id == series_id).order_by(TaskPlannerSeriesItem.order_index).all()


def _task_label(task, profile):
    review = getattr(task.plan_item, "review_status", None)
    if review in {"partial", "rejected"}:
        return "部分通过，需补做" if review == "partial" else "已退回，需补做"
    if task.vocabulary_goal:
        return "词汇已有效结算" if planner._prerequisite_complete(task, profile) else "词汇尚未有效结算"
    return task_workflow_label(task)


def _task_payload(task, profile):
    return {"id": task.id, "title": task.detail or task.category or "学习任务", "status_label": _task_label(task, profile)}


def _unfinished(rows, profile, source_date, waived):
    result = []
    for entry, _link in rows:
        if entry.target_date != source_date or entry.id in waived or entry.status != "published":
            continue
        task = db.session.get(Task, entry.published_task_id) if entry.published_task_id else None
        if (task and not task.cancelled_at and task.status != Task.STATUS_CANCELLED
                and not planner._prerequisite_complete(task, profile)):
            result.append((entry, task))
    return result


def _item(line, profile, source_date, tasks, decision=None):
    result = {"id": f"{line.id}:{source_date.isoformat()}", "series_id": line.id,
              "student_id": profile.id, "student_name": profile.full_name, "series_name": line.name,
              "source_date": source_date.isoformat(), "tasks": [_task_payload(task, profile) for task in tasks],
              "status": "resolved" if decision else "pending", "decision": None}
    if decision:
        applied = json.loads(decision.result_json)
        result["id"] += f":decision:{decision.id}"
        result["decision"] = {"id": decision.id, "action": decision.action,
                              "action_label": ACTIONS[decision.action],
                              "decided_at": decision.created_at.isoformat() + "Z",
                              "makeup_date": decision.applied_date.isoformat() if decision.action == "makeup" else None,
                              "makeup_task_ids": applied.get("created_task_ids", [])}
    return result


def list_inbox(student_id=None, view="pending", now=None):
    if view not in {"pending", "resolved"}:
        raise planner.TaskPlannerError("收件箱视图无效")
    now = beijing_now(now)
    today = now.date()
    query = TaskPlannerSeries.query
    if student_id not in (None, ""):
        query = query.filter_by(student_id=planner._integer(student_id, "学生"))
    if view == "pending":
        query = query.filter_by(status="ready")
    output = []
    for line in query.order_by(TaskPlannerSeries.id.desc()):
        try:
            profile = planner._student(line.student_id)
        except planner.TaskPlannerError:
            continue
        decisions = _decisions(line.id)
        if view == "resolved":
            for decision in decisions:
                ids = json.loads(decision.snapshot_json).get("source_task_ids", [])
                tasks = [task for task_id in ids if (task := db.session.get(Task, task_id)) is not None]
                output.append(_item(line, profile, decision.source_date, tasks, decision))
            continue
        rows = _rows(line.id)
        waived = {entry_id for decision in decisions if decision.applied_date <= today
                  for entry_id in json.loads(decision.snapshot_json).get("waived_entry_ids", [])}
        for source_date in sorted({entry.target_date for entry, _link in rows if entry.target_date < today}):
            unfinished = _unfinished(rows, profile, source_date, waived)
            if unfinished:
                output.append(_item(line, profile, source_date, [task for _entry, task in unfinished]))
    if view == "resolved":
        return sorted(output, key=lambda item: item["decision"]["id"], reverse=True)[:500]
    return sorted(output, key=lambda item: (item["source_date"], item["series_id"]))[:500]


def _source(data, actor_id, now):
    planner._actor(actor_id)
    if (not isinstance(data, dict) or not isinstance(data.get("action"), str)
            or data["action"] not in ACTIONS):
        raise planner.TaskPlannerError("请选择补做或继续计划")
    line = series_service._series(data.get("series_id"))
    profile = planner._student(line.student_id)
    today = beijing_now(now).date()
    try:
        source_date = date.fromisoformat(str(data.get("source_date")))
    except ValueError:
        raise planner.TaskPlannerError("未完成作业日期无效") from None
    if source_date >= today:
        raise planner.TaskPlannerError("只能处理昨天及更早的未完成作业")
    rows = _rows(line.id)
    waived = waived_entry_ids(line.id, now)
    unfinished = _unfinished(rows, profile, source_date, waived)
    for _entry, task in unfinished:
        if (task.student_name != profile.full_name or task.date != source_date.isoformat()
                or (task.plan_item and task.plan_item.plan.student_id != profile.id)):
            raise planner.TaskPlannerError("原任务学生、日期或学习计划关联已变化，请核对任务管理")
    return line, profile, today, source_date, rows, unfinished


def _ancestor_tasks(line_id, tasks):
    parents = {}
    for decision in _decisions(line_id):
        for mapping in json.loads(decision.result_json).get("task_mappings", []):
            parents[int(mapping["makeup_task_id"])] = int(mapping["source_task_id"])
    allowed = {task.id for _entry, task in tasks}
    frontier = list(allowed)
    while frontier:
        parent = parents.get(frontier.pop())
        if parent is not None and parent not in allowed:
            allowed.add(parent)
            frontier.append(parent)
        if len(allowed) > 1000:
            raise planner.TaskPlannerError("补做历史链过长，请联系管理员")
    return allowed


def _validate_entry(entry, profile, target):
    planner._actor(entry.confirmed_by)
    prepared = json.loads(entry.prepared_json)
    resources.revalidate_resource(prepared)
    prerequisite = planner._prerequisite(entry.prerequisite_task_id, profile, target)
    if not planner._prerequisite_complete(prerequisite, profile):
        raise planner.TaskPlannerError("另有关联前置任务尚未完成")
    planner._conflicts(SimpleNamespace(id=entry.id, student_id=entry.student_id, target_date=target), prepared, profile)
    return prepared


def _check_gate(rows, line, profile, target, waived):
    if not line.wait_for_previous:
        return
    earlier = [entry for entry, _link in rows if entry.target_date < target]
    if not earlier:
        return
    previous_date = max(entry.target_date for entry in earlier)
    for entry in earlier:
        if entry.target_date != previous_date or entry.id in waived:
            continue
        if entry.status != "published" or not entry.published_task_id:
            raise planner.TaskPlannerError("还有其他上一学习日安排未布置，请先处理更早的阻塞")
        task = planner._prerequisite(entry.published_task_id, profile, target)
        if not planner._prerequisite_complete(task, profile):
            raise planner.TaskPlannerError("上一学习日还有其他未完成作业，本次决定不能一并忽略")


def _state_hash(line, rows, profile, today):
    tasks = Task.query.filter_by(student_name=profile.full_name).order_by(Task.id).all()
    task_state = [{"id": task.id, "date": task.date, "status": task.status,
                   "cancelled": str(task.cancelled_at), "submitted": str(task.submitted_at),
                   "complete": planner._prerequisite_complete(task, profile),
                   "review": getattr(task.plan_item, "review_status", None),
                   "identity": series_service._digest({column.name: str(getattr(task, column.name))
                                                       for column in Task.__table__.columns}),
                   "updated": str(getattr(task, "updated_at", None))} for task in tasks]
    return series_service._digest({"today": today.isoformat(), "line_version": line.version,
        "definition": line.definition_json, "line_status": line.status,
        "rows": [[entry.id, entry.version, entry.status, entry.target_date.isoformat(), entry.prepared_json,
                  entry.published_task_id, entry.confirmed_by, link.order_index] for entry, link in rows],
        "tasks": task_state, "decisions": [decision.id for decision in _decisions(line.id)]})


def _preview(data, actor_id, now=None):
    line, profile, today, source_date, rows, unfinished = _source(data, actor_id, now)
    action = data["action"]
    pending = [(entry, link) for entry, link in rows if entry.status not in {"published", "cancelled"}]
    blockers, warnings, changes, skipped = [], [], [], []
    if line.status != "ready":
        blockers.append("学习线已取消或尚未确认，不能在这里恢复")
    else:
        try:
            planner._actor(line.confirmed_by)
        except ValueError as exc:
            blockers.append(f"原学习线确认人：{exc}")
    if not unfinished:
        blockers.append("该日作业已经完成或已处理，请刷新收件箱")
    if len(unfinished) > 200 or len(pending) > 1000:
        blockers.append("本次涉及的任务过多，请分批或联系管理员处理")
    frozen = json.loads(line.definition_json).get("rows", [])
    if len(frozen) != len(rows) or any(link.order_index != i for i, (_entry, link) in enumerate(rows)):
        blockers.append("学习线记录与冻结预览不一致，请联系管理员")
    else:
        for entry, link in rows:
            item = frozen[link.order_index]
            if (item.get("kind", line.kind) != entry.kind or item.get("target_date") != entry.target_date.isoformat()
                    or item.get("selection") != json.loads(entry.selection_json)):
                blockers.append("学习线内容与冻结预览不一致，请联系管理员")
    prepared = {}
    delta = 0
    waived = waived_entry_ids(line.id, now) | {entry.id for entry, _task in unfinished}
    if action == "makeup":
        if any(entry.status == "published" and entry.target_date >= today for entry, _link in rows):
            blockers.append("今天或之后已有本线任务发给学生，不能撤回后改成只补做；可选择忽略本次未完成并继续")
        if pending:
            delta = max(1, (today + timedelta(days=1) - min(entry.target_date for entry, _link in pending)).days)
        history = HistoryIndex(profile, exclude_task_ids=_ancestor_tasks(line.id, unfinished))
        for entry, task in unfinished:
            try:
                choice = json.loads(entry.prepared_json)
                resources.revalidate_resource(choice)
                if task.student_name != profile.full_name or task.date != source_date.isoformat():
                    raise planner.TaskPlannerError("原任务学生或日期已变化，请核对任务管理")
                reason = history.reason(choice)
                if reason:
                    raise planner.TaskPlannerError(f"补做内容与其他任务或安排重叠（{reason}）")
                history.reserve(choice, "本次补做已选择")
                prepared[entry.id] = choice
            except ValueError as exc:
                blockers.append(f"{entry.title}：{exc}")
        warnings.append("仅调整当前学习线；今天只发补做，其他学习线不变。后续按天整体后移，星期安排可能变化。")
    else:
        for entry, _link in pending:
            if entry.target_date < today:
                if entry.target_date <= source_date:
                    blockers.append("还有更早的未布置安排，请先处理对应阻塞")
                skipped.append({"entry_id": entry.id, "title": entry.title, "date": entry.target_date.isoformat()})
                waived.add(entry.id)
        warnings.append("仅豁免本次列出的未完成作业，不修改原成绩或整条学习线的等待规则。")
        if skipped:
            warnings.append("下面列出的过期未布置内容将明确跳过，保留处理记录。")
    candidates = pending if action == "makeup" else [(entry, link) for entry, link in pending if entry.target_date <= today]
    for entry, _link in candidates:
        target = entry.target_date + timedelta(days=delta) if action == "makeup" else entry.target_date
        if entry.status not in PENDING:
            blockers.append(f"{entry.title}：存在未确认草稿，请先整理学习线")
            continue
        if target > today + timedelta(days=90):
            blockers.append("顺延后超过未来90天，不能应用；请缩短或重新安排剩余内容")
        try:
            found = bundles._bundle(entry)
            if found:
                bundles._validate_shape(entry, *found, allowed_statuses=PENDING)
            prepared[entry.id] = _validate_entry(entry, profile, target)
        except ValueError as exc:
            blockers.append(f"{entry.title}：{exc}")
        if action == "makeup":
            changes.append({"entry_id": entry.id, "title": entry.title,
                            "from": entry.target_date.isoformat(), "to": target.isoformat()})
    today_entries = [entry for entry, _link in pending if entry.target_date == today]
    if action == "continue" and today_entries:
        try:
            _check_gate(rows, line, profile, today, waived)
        except ValueError as exc:
            blockers.append(str(exc))
    summary = (f"今天补做{len(unfinished)}项；本线{len(changes)}项未布置内容整体顺延{delta}天。"
               if action == "makeup" else f"忽略本次{len(unfinished)}项未完成作业，今天继续布置{len(today_entries)}项。")
    public = {"action": action, "today": today.isoformat(), "series_id": line.id,
              "source_date": source_date.isoformat(), "tasks": [_task_payload(task, profile) for _entry, task in unfinished],
              "changes": changes, "skipped_entries": skipped, "today_entry_count": len(today_entries),
              "warnings": warnings, "blockers": list(dict.fromkeys(blockers)), "can_apply": not blockers,
              "summary": summary}
    public["preview_hash"] = series_service._digest({"preview": public, "actor_id": actor_id,
                                                     "state": _state_hash(line, rows, profile, today)})
    state = {"line": line, "profile": profile, "today": today, "source_date": source_date,
             "rows": rows, "unfinished": unfinished, "pending": pending, "prepared": prepared,
             "frozen": frozen, "delta": delta, "today_entries": today_entries}
    return public, state


def preview_recovery(data, actor_id, now=None):
    return _preview(data, actor_id, beijing_now(now))[0]


def _publish(entry, profile, prepared, actor_id):
    task = resources.create_resource_task(profile, prepared, creator_id=actor_id,
        due_date=entry.target_date.isoformat(), planned_minutes=entry.planned_minutes,
        note=entry.note, idempotency_key=f"planner:{entry.id}:{profile.id}")
    entry.status, entry.last_error = "published", ""
    entry.published_task_id, entry.published_at = task.id, utcnow_naive()
    entry.version += 1
    planner._event(entry, "recovery_publish", actor_id)
    return task


def _makeup(state, decision, actor_id):
    line, profile, today = state["line"], state["profile"], state["today"]
    definition = json.loads(line.definition_json)
    frozen = definition["rows"]
    for entry, link in state["pending"]:
        old_bundle = frozen[link.order_index].get("bundle_id")
        entry.target_date += timedelta(days=state["delta"])
        entry.status, entry.last_error = "ready", ""
        entry.version, entry.updated_by = entry.version + 1, actor_id
        frozen[link.order_index]["target_date"] = entry.target_date.isoformat()
        if old_bundle:
            frozen[link.order_index]["bundle_id"] = f"shift:{decision.id}:{series_service._digest(old_bundle)[:24]}"
        planner._event(entry, "recovery_shift", actor_id, f"补做决定 #{decision.id}，顺延至{entry.target_date}")
    originals = {entry.id: frozen[link.order_index] for entry, link in state["rows"]}
    bundle_counts = {}
    for entry, _task in state["unfinished"]:
        marker = originals[entry.id].get("bundle_id")
        if marker:
            bundle_counts[marker] = bundle_counts.get(marker, 0) + 1
    mappings, created = [], []
    for source_entry, source_task in state["unfinished"]:
        prepared = state["prepared"][source_entry.id]
        entry = TaskPlannerEntry(student_id=profile.id, target_date=today, kind=source_entry.kind,
            title=("补做 · " + prepared["title"])[:240], selection_json=planner._dump(prepared["selection"]),
            prepared_json=planner._dump(prepared), planned_minutes=source_entry.planned_minutes,
            note=(f"补做{state['source_date']}作业。" + (source_entry.note or ""))[:200],
            status="ready", version=1, created_by=actor_id, updated_by=actor_id,
            confirmed_by=actor_id, confirmed_at=utcnow_naive())
        db.session.add(entry)
        db.session.flush()
        item = copy.deepcopy(originals[source_entry.id])
        item.update(target_date=today.isoformat(), title=entry.title, note=entry.note,
                    recovery_decision_id=decision.id, makeup_source_entry_id=source_entry.id)
        marker = item.pop("bundle_id", None)
        if marker and bundle_counts.get(marker) == 3:
            item["bundle_id"] = f"makeup:{decision.id}:{series_service._digest(marker)[:24]}"
        elif marker:
            item["unit_count"] = 1
        db.session.add(TaskPlannerSeriesItem(series_id=line.id, entry_id=entry.id,
            order_index=len(frozen), previous_entry_id=None, unit_count=item.get("unit_count", 1)))
        frozen.append(item)
        task = _publish(entry, profile, prepared, actor_id)
        mappings.append({"source_task_id": source_task.id, "source_entry_id": source_entry.id,
                         "makeup_task_id": task.id, "makeup_entry_id": entry.id})
        created.append(task.id)
    definition["recovery_notice"] = (f"本学习线最近于{today}整体顺延{state['delta']}天；"
                                       "实际日期以每天安排为准，原星期规则仅作创建时参考。")
    line.end_date = max([today] + [entry.target_date for entry, _link in state["rows"]])
    definition["end_date"] = line.end_date.isoformat()
    line.definition_json = planner._dump(definition)
    return created, [item["makeup_entry_id"] for item in mappings], mappings


def _continue(state, preview, actor_id, now):
    skipped = {item["entry_id"] for item in preview["skipped_entries"]}
    for entry, _link in state["pending"]:
        if entry.id in skipped:
            entry.status = "cancelled"
            entry.last_error = "助教选择继续计划，已明确跳过此过期未布置内容"
            entry.version, entry.updated_by = entry.version + 1, actor_id
            planner._event(entry, "recovery_skip", actor_id, entry.last_error)
    for entry in state["today_entries"]:
        planner._series_prerequisite(entry, state["profile"], now)
        _validate_entry(entry, state["profile"], entry.target_date)
    created = [_publish(entry, state["profile"], state["prepared"][entry.id], actor_id).id
               for entry in state["today_entries"]]
    return created, [entry.id for entry in state["today_entries"]], []


def apply_recovery(data, actor_id, now=None):
    now = beijing_now(now)
    begin_assignment_transaction()
    try:
        planner._actor(actor_id)
        if not isinstance(data, dict):
            raise planner.TaskPlannerError("处理请求无效")
        key = data.get("request_key")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{15,95}", key):
            raise planner.TaskPlannerError("缺少有效请求标识，请重新预览")
        request_hash = series_service._digest({"actor_id": actor_id, **{
            name: data.get(name) for name in ("series_id", "source_date", "action", "preview_hash")}})
        existing = TaskPlannerRecoveryDecision.query.filter_by(request_key=key).first()
        if existing:
            if existing.request_hash != request_hash:
                raise planner.TaskPlannerError("该请求标识已用于不同处理", code="idempotency_conflict", status=409)
            db.session.commit()
            return json.loads(existing.result_json)
        preview, state = _preview(data, actor_id, now)
        if data.get("preview_hash") != preview["preview_hash"]:
            raise planner.TaskPlannerError("作业、计划或日期已变化，请重新预览", code="preview_changed", status=409)
        if not preview["can_apply"]:
            raise planner.TaskPlannerError("；".join(preview["blockers"]), code="recovery_blocked", status=409)
        source_ids = [entry.id for entry, _task in state["unfinished"]]
        snapshot = {"source_entry_ids": source_ids,
                    "source_task_ids": [task.id for _entry, task in state["unfinished"]],
                    "waived_entry_ids": source_ids + [item["entry_id"] for item in preview["skipped_entries"]],
                    "changes": preview["changes"], "skipped_entries": preview["skipped_entries"]}
        decision = TaskPlannerRecoveryDecision(series_id=state["line"].id, student_id=state["profile"].id,
            source_date=state["source_date"], source_fingerprint=series_service._digest(sorted(source_ids)),
            action=data["action"], applied_date=state["today"], request_key=key, request_hash=request_hash,
            preview_hash=preview["preview_hash"], snapshot_json=planner._dump(snapshot), result_json="{}", created_by=actor_id)
        db.session.add(decision)
        db.session.flush()
        if data["action"] == "makeup":
            created, published, mappings = _makeup(state, decision, actor_id)
        else:
            created, published, mappings = _continue(state, preview, actor_id, now)
        state["line"].version += 1
        state["line"].updated_by = actor_id
        result = {"decision_id": decision.id, "action": decision.action, "series_id": decision.series_id,
                  "source_date": decision.source_date.isoformat(), "applied_date": decision.applied_date.isoformat(),
                  "created_task_ids": created, "published_entry_ids": published, "task_mappings": mappings,
                  "message": preview["summary"]}
        decision.result_json = planner._dump(result)
        for entry, _task in state["unfinished"]:
            planner._event(entry, "recovery_" + decision.action, actor_id, f"未完成处理决定 #{decision.id}")
        db.session.commit()
        return result
    except Exception:
        db.session.rollback()
        raise
