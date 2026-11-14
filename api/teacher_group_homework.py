"""Teacher-owned small-class homework with atomic per-student assignments."""

import hashlib
import json
import math
import re
from datetime import date

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError, OperationalError

from api.auth_utils import require_api_user
from api.miniprogram import (
    _build_teacher_homework_values,
    _normalize_subscribe_push_error,
    _serialize_teacher_homework_task,
    _task_template_id,
    _teacher_practice_result_with_attempts,
    _update_teacher_homework,
    send_subscribe_message_result,
)
from api.teacher_practice_access import validate_quick_practice_request
from models import (
    AuditLogEntry,
    ListeningTestSubmission,
    ReadingTestSubmission,
    StudentProfile,
    Task,
    User,
    db,
)
from services.practice_attempt_reporting import load_attempts_by_task
from services.task_assignment_duplicates import begin_assignment_transaction
from services.task_date_gate import task_date_cutoff_local
from services.teacher_homework_recipients import (
    HomeworkRecipientsError,
    preview_recipients,
    validate_recipients,
)

teacher_group_homework_bp = Blueprint(
    "teacher_group_homework", __name__, url_prefix="/api/miniprogram/teacher/homework"
)
_RECEIPT_TYPE = "teacher_group_homework"
_ITEM_FIELDS = {
    "date",
    "source_type",
    "category",
    "detail",
    "planned_minutes",
    "note",
    "practice_test_id",
    "practice_scope",
    "practice_section_number",
    "practice_passage_number",
    "practice_exercise_id",
    "listening_training_mode",
}


def _error(code, status=400, message=None, members=None):
    payload = {"ok": False, "error": code}
    if message:
        payload["message"] = message
    if members is not None:
        payload["members"] = members
    return jsonify(payload), status


@teacher_group_homework_bp.errorhandler(HomeworkRecipientsError)
def _recipient_error(error):
    db.session.rollback()
    return _error(error.code, error.status, error.message, error.members)


def _json_data():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise HomeworkRecipientsError("invalid_request", 400, "作业参数不正确")
    return data


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _check_item_types(payload):
    numeric = {"planned_minutes", "practice_section_number", "practice_passage_number"}
    for key in _ITEM_FIELDS - numeric:
        if payload.get(key) is not None and not isinstance(payload[key], str):
            raise HomeworkRecipientsError("invalid_items", 400, "作业参数不正确")
    for key in numeric:
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            number = float(value)
            valid = not isinstance(value, bool) and math.isfinite(number) and number.is_integer()
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            raise HomeworkRecipientsError("invalid_items", 400, "作业时长或练习范围不正确")


def _trusted_context(data, context):
    # Neither an item nor a shortcut for a different student may replace the
    # class that the roster token authorized.
    return {**data, **context["schedule"]}


def _validated_items(user, data):
    items = data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 20:
        raise HomeworkRecipientsError("invalid_items", 400, "请选择1至20项作业")
    prepared = []
    for item in items:
        if not isinstance(item, dict):
            raise HomeworkRecipientsError("invalid_items", 400, "作业参数不正确")
        # Item payloads may never replace the verified class/teacher context.
        payload = {**data, **{key: item[key] for key in _ITEM_FIELDS if key in item}}
        payload.pop("items", None)
        _check_item_types(payload)
        _context, error, status = validate_quick_practice_request(user, payload)
        if error:
            raise HomeworkRecipientsError(error, status, "学科权限已失效，请返回课表重新进入")
        values, error, status = _build_teacher_homework_values(payload)
        if error:
            raise HomeworkRecipientsError(error, status, "请检查作业日期、内容和练习范围")
        prepared.append((payload, values))
    return prepared


def _receipt(user_id, request_key):
    return AuditLogEntry.query.filter_by(
        entity_type=_RECEIPT_TYPE, actor_id=user_id, field=request_key, action="create"
    ).first()


def _existing_receipt(user_id, request_key, fingerprint):
    receipt = _receipt(user_id, request_key)
    if not receipt:
        return None
    saved = receipt.metadata_payload or {}
    if saved.get("fingerprint") != fingerprint:
        raise HomeworkRecipientsError(
            "idempotency_conflict", 409, "这次提交已用于其他作业，请刷新后重新布置"
        )
    ids = saved.get("task_ids") or []
    tasks = Task.query.filter(Task.id.in_(ids)).all()
    if len(tasks) != len(ids):
        raise HomeworkRecipientsError(
            "assignment_changed", 409, "这批作业已有删除，请刷新作业列表，不会重复创建"
        )
    ordered = {task.id: task for task in tasks}
    return [ordered[task_id] for task_id in ids]


def _create_tasks(user, profiles, prepared, request_key, fingerprint):
    # Existing infrastructure serializes SQLite writers across gunicorn threads.
    identities = [(profile.id, profile.full_name) for profile in profiles]
    begin_assignment_transaction()
    replay = _existing_receipt(user.id, request_key, fingerprint)
    if replay is not None:
        db.session.rollback()
        return replay, True
    tasks = []
    for profile_id, profile_name in identities:
        # Recheck local identity under the writer lock, after roster verification.
        matches = StudentProfile.query.filter_by(full_name=profile_name, is_deleted=False).all()
        if len(matches) != 1 or matches[0].id != profile_id:
            raise HomeworkRecipientsError("roster_changed", 409, "学生档案有变化，请重新核对名单")
        for index, (payload, _values) in enumerate(prepared):
            # Build per recipient: access tokens MUST NOT be shared across Tasks.
            values, error, status = _build_teacher_homework_values(payload)
            if error:
                raise HomeworkRecipientsError(error, status, "练习素材有变化，请重新选择")
            task = Task(
                **values,
                student_name=profile_name,
                created_by=user.id,
                status="pending",
                assignment_idempotency_key=f"ghw:{request_key}:{profile_id}:{index}",
            )
            db.session.add(task)
            tasks.append(task)
    db.session.flush()
    db.session.add(
        AuditLogEntry(
            entity_type=_RECEIPT_TYPE,
            entity_id=tasks[0].id,
            action="create",
            actor_id=user.id,
            field=request_key,
            metadata_payload={
                "fingerprint": fingerprint,
                "task_ids": [task.id for task in tasks],
                "profile_ids": [profile.id for profile in profiles],
            },
        )
    )
    db.session.commit()
    return tasks, False


def _notify(profile, task):
    template_id = _task_template_id()
    openid = profile.user.wechat_openid if profile.user and profile.user.is_active else None
    if not template_id:
        return "missing_template_id"
    if not openid:
        return "no_student_openid"
    cutoff = task_date_cutoff_local(task)
    payload = {
        "thing1": {"value": (task.detail or "学习任务")[:20]},
        "time2": {"value": f"{task.date} 08:00"},
        "time3": {"value": cutoff.strftime("%Y-%m-%d %H:%M") if cutoff else f"{task.date} 23:59"},
        "thing4": {"value": (task.category or "学习任务")[:20]},
    }
    try:
        result = send_subscribe_message_result(
            openid, template_id, payload, page="pages/student/home/index"
        )
        return None if result.get("ok") else _normalize_subscribe_push_error(result)
    except Exception:
        # Assignment is already committed; delivery failure must never look like
        # a failed save and encourage a duplicate assignment.
        current_app.logger.warning("Group homework reminder failed for task %s", task.id)
        return "send_failed"


def _result(tasks, profiles, *, replayed):
    recipients = []
    for profile in profiles:
        owned = [task for task in tasks if task.student_name == profile.full_name]
        errors, sent = [], 0
        if not replayed:
            for task in owned:
                error = _notify(profile, task)
                if error:
                    errors.append(error)
                else:
                    sent += 1
        recipients.append(
            {
                "profile_id": profile.id,
                "student_name": profile.full_name,
                "task_ids": [task.id for task in owned],
                "push_sent": sent,
                "push_errors": errors,
            }
        )
    return jsonify(
        ok=True,
        tasks=[_serialize_teacher_homework_task(task) for task in tasks],
        member_count=len(profiles),
        task_count=len(tasks),
        recipients=recipients,
        push_sent=sum(row["push_sent"] for row in recipients),
        replayed=replayed,
    )


@teacher_group_homework_bp.get("/recipients")
@require_api_user(User.ROLE_TEACHER)
def recipients_preview():
    return jsonify(preview_recipients(request.current_api_user, request.args.to_dict()))


@teacher_group_homework_bp.post("/group")
@require_api_user(User.ROLE_TEACHER)
def create_group_homework():
    user, data = request.current_api_user, _json_data()
    profiles, context = validate_recipients(user, data)
    if not context["is_group"]:
        return _error("not_a_group", 400, "请选择小班课程")
    data = _trusted_context(data, context)
    raw_key = data.get("idempotency_key")
    if not isinstance(raw_key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", raw_key):
        return _error("invalid_idempotency_key", 400, "请刷新后重新布置")
    prepared = _validated_items(user, data)
    request_key = _digest([user.id, raw_key])
    fingerprint = _digest(
        {
            "roster": context["fingerprint"],
            "items": [
                {
                    key: value
                    for key, value in values.items()
                    if key not in {"listening_access_token", "reading_access_token"}
                }
                for _payload, values in prepared
            ],
        }
    )
    try:
        tasks, replayed = _create_tasks(user, profiles, prepared, request_key, fingerprint)
    except IntegrityError:
        db.session.rollback()
        return _error("assignment_conflict", 409, "已有相同提交，请刷新作业列表后重试")
    except OperationalError:
        db.session.rollback()
        return _error("assignment_busy", 409, "正在保存作业，请稍后重试")
    return _result(tasks, profiles, replayed=replayed)


@teacher_group_homework_bp.get("/group")
@require_api_user(User.ROLE_TEACHER)
def list_group_homework():
    data, user = request.args.to_dict(), request.current_api_user
    profiles, _context = validate_recipients(user, data, require_selection=False)
    scope, task_date = data.get("scope", "date"), data.get("date") or date.today().isoformat()
    try:
        date.fromisoformat(task_date)
    except (TypeError, ValueError):
        return _error("invalid_date")
    if scope not in {"date", "recent"}:
        return _error("invalid_scope")
    query = Task.query.filter(
        Task.student_name.in_([profile.full_name for profile in profiles]),
        Task.created_by == user.id,
    )
    if scope == "date":
        query = query.filter(Task.date == task_date)
    tasks = query.order_by(Task.date.desc(), Task.id.desc()).limit(300).all()
    return jsonify(ok=True, tasks=_tasks_with_results(tasks))


def _tasks_with_results(tasks):
    if not tasks:
        return []
    by_id = {task.id: task for task in tasks}
    attempts = load_attempts_by_task(list(by_id))
    results = {}
    for kind, model in (("listening", ListeningTestSubmission), ("reading", ReadingTestSubmission)):
        for row in model.query.filter(model.task_id.in_(list(by_id))).all():
            results[row.task_id], _overview = _teacher_practice_result_with_attempts(
                by_id[row.task_id], kind, row, attempts.get(row.task_id, [])
            )
    return [_serialize_teacher_homework_task(task, results.get(task.id)) for task in tasks]


@teacher_group_homework_bp.patch("/group/<int:task_id>")
@require_api_user(User.ROLE_TEACHER)
def update_group_member_homework(task_id):
    user, data = request.current_api_user, _json_data()
    _check_item_types(data)
    profiles, context = validate_recipients(user, data, require_selection=False)
    data = _trusted_context(data, context)
    task = db.session.get(Task, task_id)
    if (
        not task
        or task.created_by != user.id
        or task.student_name not in {profile.full_name for profile in profiles}
    ):
        return _error("forbidden_task", 403)
    _quick, error, status = validate_quick_practice_request(user, data)
    if error:
        return _error(error, status)
    # The signed class roster has already authorized this individual member.
    # Remove only shortcut routing fields; source validation above still applies.
    payload = dict(data)
    for key in ("quick_practice", "subject_key", "allowed_source", "practice_context_token"):
        payload.pop(key, None)
    return _update_teacher_homework(task_id, payload)
