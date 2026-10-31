"""Explicitly confirmed, student-opt-in scheduled assignments.

SQLite's writer lock covers reread, checks, Task/PlanItem creation and planner
state. No HTTP assignment routes, message sending, or model inference here.
"""

from __future__ import annotations

import json
from datetime import date, time, timedelta

from flask import current_app

from models import StudentProfile, Task, User, db, utcnow_naive
from models_task_planner import TaskPlannerEntry, TaskPlannerEvent, TaskPlannerStudent
from services import task_planner_resources as resources
from services.task_assignment_duplicates import (
    begin_assignment_transaction,
    validate_publish_conflicts,
)
from services.task_date_gate import beijing_now, task_workflow_status

STAFF_ROLES = {User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT}
KINDS = [
    {"id": "question_type", "label": "听力 / 阅读题型专项"},
    {"id": "reading_passage", "label": "阅读整篇"},
    {"id": "dictation", "label": "词汇指定范围"},
    {"id": "intensive", "label": "精听指定内容"},
]
STATUS_LABELS = {
    "draft": "草稿", "ready": "待布置", "blocked": "待处理",
    "failed": "执行失败", "published": "已布置", "cancelled": "已取消",
}


class TaskPlannerError(ValueError):
    def __init__(self, message, *, code="invalid_request", status=400):
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _integer(value, label, minimum=1, maximum=2147483647):
    if isinstance(value, bool):
        raise TaskPlannerError(f"{label}格式不正确")
    try:
        result = int(str(value))
    except (TypeError, ValueError):
        raise TaskPlannerError(f"{label}格式不正确") from None
    if not minimum <= result <= maximum:
        raise TaskPlannerError(f"{label}超出允许范围")
    return result


def _actor(actor_id):
    actor = db.session.get(User, _integer(actor_id, "操作账号"))
    if not actor or not actor.is_active or actor.role not in STAFF_ROLES:
        raise TaskPlannerError("需要有效的教师或助教账号", code="forbidden", status=403)
    return actor


def _student(student_id):
    profile = db.session.get(StudentProfile, _integer(student_id, "学生"))
    if not profile or profile.is_deleted:
        raise TaskPlannerError("学生档案不存在或已停用", status=404)
    if profile.user and not profile.user.is_active:
        raise TaskPlannerError("学生账号已停用")
    # Legacy Tasks still identify students by name. Never guess between two IDs.
    names = StudentProfile.query.filter_by(full_name=profile.full_name, is_deleted=False).count()
    if names != 1:
        raise TaskPlannerError("存在同名学生档案，请先在学生管理中区分姓名", code="ambiguous_student")
    return profile


def _entry(entry_id, version=None, *, editable=False):
    row = db.session.get(TaskPlannerEntry, _integer(entry_id, "安排"))
    if not row:
        raise TaskPlannerError("安排不存在", status=404)
    if version is not None and row.version != _integer(version, "版本"):
        raise TaskPlannerError("安排已被更新，请刷新后再操作", code="version_conflict", status=409)
    if editable and row.status in {"published", "cancelled"}:
        raise TaskPlannerError("已布置或取消的安排不能修改，请另建草稿", status=409)
    return row


def _date(value, now=None):
    try:
        result = date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise TaskPlannerError("请选择有效的任务日期") from None
    today = beijing_now(now).date()
    if result < today or result > today + timedelta(days=90):
        raise TaskPlannerError("任务日期须在今天至未来90天内")
    return result


def _prerequisite(task_id, profile, target_date):
    if task_id in (None, ""):
        return None
    task = db.session.get(Task, _integer(task_id, "前置任务"))
    if not task or task.cancelled_at or task.student_name != profile.full_name:
        raise TaskPlannerError("前置任务必须属于当前学生且未取消")
    if task.plan_item and task.plan_item.plan.student_id != profile.id:
        raise TaskPlannerError("前置任务学生关联不一致")
    if not task.date or task.date > target_date.isoformat():
        raise TaskPlannerError("前置任务日期不能晚于本次安排")
    return task


def _prerequisite_complete(task, profile):
    if task is None:
        return True
    review = getattr(task.plan_item, "review_status", None)
    if review in {"partial", "rejected"}:
        return False
    if task.vocabulary_goal:
        from models import VocabularyTaskSettlement
        return bool(profile.user_id and VocabularyTaskSettlement.query.filter_by(
            task_id=task.id, student_id=profile.user_id,
        ).first())
    return task_workflow_status(task) in {"completed", "submitted"}


def _event(row, action, actor_id=None, detail=""):
    db.session.add(TaskPlannerEvent(
        entry_id=row.id, student_id=row.student_id, actor_id=actor_id,
        action=action, detail=str(detail)[:500],
    ))


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _conflicts(row, prepared, profile):
    payload = dict(prepared["duplicate_payload"], due_date=row.target_date.isoformat())
    result = validate_publish_conflicts([profile.full_name], payload)
    if not result["can_publish"]:
        raise TaskPlannerError("与已布置任务内容重叠，请查看任务管理后调整；试用版不自动重复布置", code="duplicate_assignment", status=409)
    overlap_task = getattr(resources, "overlaps_task", None)
    if overlap_task:
        for task in Task.query.filter_by(student_name=profile.full_name).all():
            if overlap_task(prepared, task):
                raise TaskPlannerError("与已有整篇或专项任务内容重叠，请调整选择", code="duplicate_assignment", status=409)
    for other in TaskPlannerEntry.query.filter(
        TaskPlannerEntry.student_id == row.student_id,
        TaskPlannerEntry.id != row.id,
        TaskPlannerEntry.status.in_(["ready", "blocked", "failed"]),
    ).all():
        if resources.resource_overlap(prepared, json.loads(other.prepared_json)):
            raise TaskPlannerError(f"与待布置安排 #{other.id} 内容重叠，请修改或取消其中一项", code="duplicate_plan", status=409)


def save_entry(data, actor_id, entry_id=None, expected_version=None, now=None):
    begin_assignment_transaction()
    try:
        _actor(actor_id)
        if entry_id is not None and expected_version is None:
            raise TaskPlannerError("缺少安排版本")
        row = _entry(entry_id, expected_version, editable=True) if entry_id else None
        profile = _student(data.get("student_id"))
        target = _date(data.get("target_date"), now)
        kind = str(data.get("kind") or "")
        if kind not in {item["id"] for item in KINDS}:
            raise TaskPlannerError("不支持的任务类型")
        selection = data.get("selection")
        if not isinstance(selection, dict):
            raise TaskPlannerError("请选择具体练习内容")
        prepared = resources.prepare_resource(kind, selection)
        prerequisite = _prerequisite(data.get("prerequisite_task_id"), profile, target)
        minutes = _integer(data.get("planned_minutes", 20), "预计分钟", 1, 180)
        note = str(data.get("note") or "").strip()
        if len(note) > 200:
            raise TaskPlannerError("说明不能超过200字")
        if row is None:
            row = TaskPlannerEntry(created_by=actor_id, version=1)
            db.session.add(row)
        else:
            row.version += 1
        row.student_id, row.target_date, row.kind = profile.id, target, kind
        row.title = prepared["title"][:240]
        row.selection_json = _dump(prepared.get("selection", selection))
        row.prepared_json = _dump(prepared)
        row.planned_minutes, row.note = minutes, note
        row.prerequisite_task_id = prerequisite.id if prerequisite else None
        row.status, row.last_error = "draft", ""
        row.updated_by = actor_id
        row.confirmed_by, row.confirmed_at = None, None
        db.session.flush()
        _event(row, "save_draft", actor_id)
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def confirm_entry(entry_id, version, actor_id, now=None):
    begin_assignment_transaction()
    try:
        _actor(actor_id)
        row = _entry(entry_id, version, editable=True)
        profile = _student(row.student_id)
        _date(row.target_date.isoformat(), now)
        _prerequisite(row.prerequisite_task_id, profile, row.target_date)
        prepared = json.loads(row.prepared_json)
        resources.revalidate_resource(prepared)
        _conflicts(row, prepared, profile)
        row.status, row.last_error = "ready", ""
        row.confirmed_by, row.confirmed_at = actor_id, utcnow_naive()
        row.updated_by, row.version = actor_id, row.version + 1
        _event(row, "confirm", actor_id)
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def cancel_entry(entry_id, version, actor_id, now=None):
    begin_assignment_transaction()
    try:
        _actor(actor_id)
        row = _entry(entry_id, version, editable=True)
        row.status, row.last_error = "cancelled", ""
        row.version, row.updated_by = row.version + 1, actor_id
        _event(row, "cancel", actor_id)
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def set_student_enabled(student_id, enabled, actor_id):
    if not isinstance(enabled, bool):
        raise TaskPlannerError("启用状态必须为true或false")
    begin_assignment_transaction()
    try:
        _actor(actor_id)
        profile = _student(student_id)
        row = db.session.get(TaskPlannerStudent, profile.id)
        if row is None:
            row = TaskPlannerStudent(student_id=profile.id, updated_by=actor_id)
            db.session.add(row)
        row.enabled, row.updated_by = enabled, actor_id
        db.session.add(TaskPlannerEvent(student_id=profile.id, actor_id=actor_id,
                                       action="enable" if enabled else "disable"))
        db.session.commit()
        return row
    except Exception:
        db.session.rollback()
        raise


def _blocked(row, message, actor_id):
    row.status, row.last_error = "blocked", str(message)[:500]
    row.version += 1
    _event(row, "blocked", actor_id, row.last_error)
    db.session.commit()
    return row


def publish_entry(entry_id, actor_id=None, expected_version=None, now=None, automatic=False):
    begin_assignment_transaction()
    row_id, locked_version = None, None
    try:
        if not automatic:
            _actor(actor_id)
        row = _entry(entry_id)
        # Retrying an already committed publish must return the original task.
        if row.status == "published" and row.published_task_id:
            db.session.commit()
            return row
        if not automatic:
            if expected_version is None:
                raise TaskPlannerError("缺少安排版本")
            _entry(entry_id, expected_version)
        if row.status not in {"ready", "failed"} or not row.confirmed_at:
            raise TaskPlannerError("请先确认本次安排；待处理项需调整后重新确认", status=409)
        current = beijing_now(now)
        if row.target_date != current.date():
            raise TaskPlannerError("仅能布置今天的安排；其他日期请等待或修改草稿", code="wrong_date", status=409)
        if automatic:
            setting = db.session.get(TaskPlannerStudent, row.student_id)
            if not setting or not setting.enabled:
                raise TaskPlannerError("该学生尚未启用自动布置", code="not_enabled", status=409)
            if not time(3, 5) <= current.time().replace(tzinfo=None) < time(9):
                raise TaskPlannerError("不在自动布置时间内", code="outside_window", status=409)
        row_id, locked_version = row.id, row.version
        try:
            _actor(row.confirmed_by)
            profile = _student(row.student_id)
            prerequisite = _prerequisite(row.prerequisite_task_id, profile, row.target_date)
            if not _prerequisite_complete(prerequisite, profile):
                return _blocked(row, "前置任务尚未完成或被退回，请处理后重新确认", actor_id)
            prepared = json.loads(row.prepared_json)
            resources.revalidate_resource(prepared)
            _conflicts(row, prepared, profile)
        except ValueError as exc:
            return _blocked(row, str(exc), actor_id)
        task = resources.create_resource_task(
            profile, prepared, creator_id=row.confirmed_by,
            due_date=row.target_date.isoformat(), planned_minutes=row.planned_minutes,
            note=row.note, idempotency_key=f"planner:{row.id}:{profile.id}",
        )
        db.session.flush()
        row.status, row.last_error = "published", ""
        row.published_task_id, row.published_at = task.id, utcnow_naive()
        row.version += 1
        _event(row, "auto_publish" if automatic else "publish", actor_id)
        db.session.commit()
        return row
    except TaskPlannerError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Task planner publish failed for entry %s", entry_id)
        if row_id is None:
            raise
        begin_assignment_transaction()
        row = _entry(row_id)
        if row.version == locked_version and row.status in {"ready", "failed"}:
            row.status = "failed"
            row.last_error = "布置失败，任务未保存。可以重试；持续失败请联系管理员。"
            row.version += 1
            _event(row, "failed", actor_id, row.last_error)
        db.session.commit()
        return row


def run_due(now=None, dry_run=False):
    current = beijing_now(now)
    report = {"eligible": 0, "published": 0, "blocked": 0, "failed": 0, "skipped": 0,
              "dry_run": bool(dry_run), "date": current.date().isoformat()}
    if not time(3, 5) <= current.time().replace(tzinfo=None) < time(9):
        report["outside_window"] = True
        return report
    ids = [entry_id for (entry_id,) in db.session.query(TaskPlannerEntry.id).join(
        TaskPlannerStudent, TaskPlannerStudent.student_id == TaskPlannerEntry.student_id,
    ).filter(TaskPlannerStudent.enabled.is_(True),
             TaskPlannerEntry.target_date == current.date(),
             TaskPlannerEntry.status.in_(["ready", "failed"])).order_by(TaskPlannerEntry.id).all()]
    report["eligible"] = len(ids)
    if dry_run:
        return report
    for entry_id in ids:
        try:
            row = publish_entry(entry_id, now=current, automatic=True)
            report[row.status if row.status in {"published", "blocked", "failed"} else "skipped"] += 1
        except TaskPlannerError:
            report["skipped"] += 1
        except Exception:
            db.session.rollback()
            report["failed"] += 1
            current_app.logger.exception("Task planner runner failed for entry %s", entry_id)
    return report


def entry_payload(row):
    profile = db.session.get(StudentProfile, row.student_id)
    setting = db.session.get(TaskPlannerStudent, row.student_id)
    today = beijing_now().date()
    message = row.last_error
    task = db.session.get(Task, row.published_task_id) if row.published_task_id else None
    if row.status == "published" and (task is None or task.cancelled_at):
        message = "正式任务已取消或不可用；本安排不会再次自动布置"
    if row.status in {"draft", "ready"} and row.target_date < today:
        message = "目标日期已过，未自动补发；请改期并重新确认"
    return {
        "id": row.id, "version": row.version, "student_id": row.student_id,
        "student_name": profile.full_name if profile else "学生档案已停用",
        "student_enabled": bool(setting and setting.enabled),
        "target_date": row.target_date.isoformat(), "kind": row.kind, "title": row.title,
        "selection": json.loads(row.selection_json), "planned_minutes": row.planned_minutes,
        "note": row.note, "status": row.status, "status_label": STATUS_LABELS[row.status],
        "error": message, "published_task_id": row.published_task_id,
        "prerequisite_task_id": row.prerequisite_task_id,
    }
