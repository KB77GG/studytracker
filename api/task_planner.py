"""Staff workbench for explicit, dated assignment drafts."""

from __future__ import annotations

import secrets
from datetime import date, timedelta
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, redirect, render_template, request, session
from flask_login import current_user
from sqlalchemy import and_, or_

from models import StudentProfile, Task, db
from models_task_planner import TaskPlannerEntry, TaskPlannerEvent, TaskPlannerStudent
from services import task_planner as planner
from services import task_planner_resources as resources
from services.task_date_gate import beijing_now, task_workflow_label

task_planner_bp = Blueprint("task_planner", __name__)


@task_planner_bp.before_request
def staff_and_csrf():
    if not getattr(current_user, "is_authenticated", False):
        if request.path == "/task-planner":
            return redirect("/login?next=/task-planner")
        return jsonify(ok=False, error="unauthorized", message="请先登录"), 401
    if not current_user.is_active or current_user.role not in planner.STAFF_ROLES:
        return jsonify(ok=False, error="forbidden", message="仅教师、助教和管理员可使用"), 403
    if request.method in {"POST", "PATCH", "DELETE"}:
        expected = session.get("task_planner_csrf")
        actual = request.headers.get("X-CSRF-Token", "")
        if not expected or not secrets.compare_digest(str(expected), actual):
            return jsonify(ok=False, error="csrf", message="页面已过期，请刷新后重试"), 403
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(ok=False, error="csrf", message="请求来源无效"), 403
        if not request.is_json:
            return jsonify(ok=False, error="json_required", message="请使用JSON请求"), 400
        if request.content_length and request.content_length > 65536:
            return jsonify(ok=False, error="too_large", message="选择内容过多"), 413


@task_planner_bp.errorhandler(planner.TaskPlannerError)
def planner_error(error):
    db.session.rollback()
    return jsonify(ok=False, error=error.code, message=error.message), error.status


@task_planner_bp.errorhandler(ValueError)
def invalid_input(error):
    db.session.rollback()
    return jsonify(ok=False, error="invalid_request", message=str(error)[:500]), 400


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise planner.TaskPlannerError("请求内容必须为对象")
    return data


@task_planner_bp.get("/task-planner")
def workbench():
    return render_template("task_planner.html")


@task_planner_bp.get("/api/task-planner/bootstrap")
def bootstrap():
    token = session.setdefault("task_planner_csrf", secrets.token_urlsafe(32))
    settings = {row.student_id: row.enabled for row in TaskPlannerStudent.query.all()}
    profiles = StudentProfile.query.filter_by(is_deleted=False).order_by(StudentProfile.full_name).all()
    return jsonify(ok=True, today=beijing_now().date().isoformat(), csrf_token=token,
                   students=[{"id": row.id, "name": row.full_name,
                              "enabled": bool(settings.get(row.id))} for row in profiles],
                   kinds=planner.KINDS, schedule_label="每天03:05布置，09:00前补跑")


@task_planner_bp.get("/api/task-planner/catalog")
def catalog():
    result = resources.catalog(request.args.get("kind", ""), request.args.to_dict())
    return jsonify(ok=True, **result)


@task_planner_bp.get("/api/task-planner/entries")
def entries():
    today = beijing_now().date()
    try:
        start = date.fromisoformat(request.args.get("from") or today.isoformat())
        end = date.fromisoformat(request.args.get("to") or (today + timedelta(days=6)).isoformat())
    except ValueError:
        raise planner.TaskPlannerError("日期格式不正确") from None
    if end < start or (end - start).days > 93:
        raise planner.TaskPlannerError("查询日期范围不得超过93天")
    status = request.args.get("status")
    query = TaskPlannerEntry.query
    if status == "attention":
        query = query.filter(TaskPlannerEntry.target_date <= end, or_(
            TaskPlannerEntry.status.in_(["draft", "blocked", "failed"]),
            and_(TaskPlannerEntry.status == "ready", TaskPlannerEntry.target_date < today),
        ))
    else:
        query = query.filter(TaskPlannerEntry.target_date.between(start, end))
    if request.args.get("student_id"):
        query = query.filter_by(student_id=planner._integer(request.args["student_id"], "学生"))
    if request.args.get("series_id"):
        from models_task_planner import TaskPlannerSeriesItem
        query = query.join(TaskPlannerSeriesItem, TaskPlannerSeriesItem.entry_id == TaskPlannerEntry.id).filter(
            TaskPlannerSeriesItem.series_id == planner._integer(request.args["series_id"], "学习线"),
        )
    if status and status != "attention":
        if status not in planner.STATUS_LABELS:
            raise planner.TaskPlannerError("任务状态不正确")
        query = query.filter_by(status=status)
    rows = query.order_by(TaskPlannerEntry.target_date, TaskPlannerEntry.id).limit(501).all()
    summary = {key: 0 for key in planner.STATUS_LABELS}
    for row in rows[:500]:
        summary[row.status] += 1
    return jsonify(ok=True, entries=[planner.entry_payload(row) for row in rows[:500]],
                   summary=summary, has_more=len(rows) > 500)


@task_planner_bp.post("/api/task-planner/entries")
def create_entry():
    row = planner.save_entry(_body(), current_user.id)
    return jsonify(ok=True, entry=planner.entry_payload(row)), 201


@task_planner_bp.patch("/api/task-planner/entries/<int:entry_id>")
def edit_entry(entry_id):
    data = _body()
    row = planner.save_entry(data, current_user.id, entry_id, data.get("version"))
    return jsonify(ok=True, entry=planner.entry_payload(row))


@task_planner_bp.post("/api/task-planner/entries/<int:entry_id>/confirm")
def confirm_entry(entry_id):
    data = _body()
    if data.get("version") is None:
        raise planner.TaskPlannerError("缺少安排版本")
    row = planner.confirm_entry(entry_id, data["version"], current_user.id)
    return jsonify(ok=True, entry=planner.entry_payload(row))


@task_planner_bp.post("/api/task-planner/entries/<int:entry_id>/cancel")
def cancel_entry(entry_id):
    data = _body()
    if data.get("version") is None:
        raise planner.TaskPlannerError("缺少安排版本")
    row = planner.cancel_entry(entry_id, data["version"], current_user.id)
    return jsonify(ok=True, entry=planner.entry_payload(row))


@task_planner_bp.post("/api/task-planner/entries/<int:entry_id>/publish")
def publish_entry(entry_id):
    data = _body()
    row = planner.publish_entry(entry_id, current_user.id, data.get("version"))
    return jsonify(ok=True, entry=planner.entry_payload(row))


@task_planner_bp.post("/api/task-planner/students/<int:student_id>/enable")
def enable_student(student_id):
    row = planner.set_student_enabled(student_id, _body().get("enabled"), current_user.id)
    return jsonify(ok=True, student_id=row.student_id, enabled=row.enabled)


@task_planner_bp.get("/api/task-planner/students/<int:student_id>/tasks")
def student_tasks(student_id):
    profile = planner._student(student_id)
    rows = Task.query.filter_by(student_name=profile.full_name).order_by(Task.date.desc(), Task.id.desc()).limit(100).all()
    return jsonify(ok=True, tasks=[{
        "id": row.id, "title": row.detail or row.category or "学习任务",
        "date": row.date, "status_label": task_workflow_label(row),
    } for row in rows])


@task_planner_bp.get("/api/task-planner/entries/<int:entry_id>/events")
def entry_events(entry_id):
    planner._entry(entry_id)
    rows = TaskPlannerEvent.query.filter_by(entry_id=entry_id).order_by(TaskPlannerEvent.id.desc()).limit(50).all()
    return jsonify(ok=True, events=[{"action": row.action, "detail": row.detail,
                                    "created_at": row.created_at.isoformat() + "Z"} for row in rows])


@task_planner_bp.get("/api/task-planner/series-sources")
def series_sources():
    from services.task_planner_series import series_sources as sources
    return jsonify(ok=True, **sources(
        request.args.get("subject", "reading"), request.args.get("standard_type", "all"),
        request.args.get("source_scope"),
    ))


@task_planner_bp.post("/api/task-planner/series/preview")
def preview_series():
    from services.task_planner_series import preview_series as preview
    return jsonify(ok=True, preview=preview(_body(), current_user.id))


@task_planner_bp.post("/api/task-planner/series")
def create_series():
    from services.task_planner_series import create_series as create
    from services.task_planner_series import series_payload
    row = create(_body(), current_user.id)
    return jsonify(ok=True, series=series_payload(row)), 201


@task_planner_bp.get("/api/task-planner/series")
def list_series():
    from services.task_planner_series import list_series as listing
    from services.task_planner_series import series_payload
    rows = listing(student_id=request.args.get("student_id"))
    return jsonify(ok=True, series=[series_payload(row) for row in rows])


@task_planner_bp.get("/api/task-planner/series/<int:series_id>")
def series_details(series_id):
    from models_task_planner import TaskPlannerSeries, TaskPlannerSeriesItem
    from services.task_planner_series import series_payload
    row = db.session.get(TaskPlannerSeries, series_id)
    if not row:
        raise planner.TaskPlannerError("学习线不存在", status=404)
    entries = TaskPlannerEntry.query.join(
        TaskPlannerSeriesItem, TaskPlannerSeriesItem.entry_id == TaskPlannerEntry.id,
    ).filter(TaskPlannerSeriesItem.series_id == series_id).order_by(TaskPlannerEntry.target_date).all()
    return jsonify(ok=True, series=series_payload(row),
                   entries=[planner.entry_payload(entry) for entry in entries])


@task_planner_bp.post("/api/task-planner/series/<int:series_id>/confirm")
def confirm_series(series_id):
    from services.task_planner_series import confirm_series as confirm
    from services.task_planner_series import series_payload
    data = _body()
    if data.get("version") is None:
        raise planner.TaskPlannerError("缺少学习线版本")
    row = confirm(series_id, data["version"], current_user.id)
    return jsonify(ok=True, series=series_payload(row))


@task_planner_bp.post("/api/task-planner/series/<int:series_id>/cancel")
def cancel_series(series_id):
    from services.task_planner_series import cancel_series as cancel
    from services.task_planner_series import series_payload
    data = _body()
    if data.get("version") is None:
        raise planner.TaskPlannerError("缺少学习线版本")
    row = cancel(series_id, data["version"], current_user.id)
    return jsonify(ok=True, series=series_payload(row))
