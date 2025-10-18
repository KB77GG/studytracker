import os
import secrets
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload
from sqlalchemy import false

from config import Config
from models import (
    AuditLogEntry,
    PlanEvidence,
    PlanItem,
    PlanItemSession,
    PlanReviewLog,
    PlanTemplate,
    PlanTemplateItem,
    ScoreRecord,
    StudentProfile,
    StudyPlan,
    TaskCatalog,
    TeacherStudentLink,
    User,
    db,
    # Legacy models
    StudySession,
    Task,
)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

UPLOAD_ROOT = Path(app.config.get("UPLOAD_FOLDER", Path(app.root_path) / "uploads"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EVIDENCE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "mp3", "mp4", "wav", "doc", "docx"}


def allowed_evidence(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EVIDENCE_EXTENSIONS

# Flask-Login 配置
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 首页路由
@app.route("/")
@login_required
def index():
    if current_user.role in (User.ROLE_TEACHER, User.ROLE_ASSISTANT):
        return redirect(url_for("teacher_plans"))
    if current_user.role == User.ROLE_STUDENT:
        return redirect(url_for("student_today"))
    return render_template("index.html")

# 登录路由
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))
        flash("用户名或密码不正确，或账号已被停用。")
    return render_template("login.html")


# 登出路由
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---- Admin 权限校验装饰器 ----
from functools import wraps
def admin_required(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != User.ROLE_ADMIN:
            # 非管理员直接回首页
            return redirect(url_for("index"))
        return view_fn(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Require current user to have one of the roles (admins bypass)."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles and current_user.role != User.ROLE_ADMIN:
                if request.accept_mimetypes.best == "application/json":
                    return jsonify({"ok": False, "error": "forbidden"}), 403
                flash("无权限执行该操作。")
                return redirect(url_for("index"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def get_accessible_student_ids(user: User) -> set[int]:
    """Students a teacher/assistant/admin can manage."""

    if user.role == User.ROLE_ADMIN:
        return {
            sid
            for (sid,) in db.session.query(StudentProfile.id)
            .filter(StudentProfile.is_deleted.is_(False))
            .all()
        }
    if user.role in (User.ROLE_TEACHER, User.ROLE_ASSISTANT):
        return {
            link.student_id
            for link in user.student_links.filter(
                TeacherStudentLink.student.has(StudentProfile.is_deleted.is_(False))
            ).all()
        }
    if user.role == User.ROLE_STUDENT and user.student_profile:
        return {user.student_profile.id}
    return set()


def require_student_access(student_id: int):
    if student_id not in get_accessible_student_ids(current_user):
        raise PermissionError("forbidden_student")


def ensure_guardian_token(student: StudentProfile) -> str:
    """Ensure student has a guardian view token; create if missing."""

    if not student.guardian_view_token:
        student.guardian_view_token = secrets.token_urlsafe(16)
        db.session.commit()
    return student.guardian_view_token

# ---- 用户管理页：创建/停用/删除 ----
@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users_page():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", User.ROLE_ASSISTANT)
            allowed_roles = {
                User.ROLE_ADMIN,
                User.ROLE_TEACHER,
                User.ROLE_ASSISTANT,
                User.ROLE_STUDENT,
            }
            if role not in allowed_roles:
                role = User.ROLE_ASSISTANT
            if username and password:
                # 检查用户名是否已存在
                exists = User.query.filter_by(username=username).first()
                if exists:
                    flash("该用户名已存在")
                else:
                    u = User(username=username, role=role, display_name=username)
                    u.set_password(password)
                    db.session.add(u)
                    db.session.flush()
                    if role == User.ROLE_STUDENT:
                        profile = StudentProfile(
                            user_id=u.id,
                            full_name=username,
                            guardian_view_token=secrets.token_urlsafe(16),
                        )
                        db.session.add(profile)
                    db.session.commit()
                    flash("创建成功")
        elif action == "toggle":
            uid = int(request.form.get("user_id"))
            u = User.query.get(uid)
            if u and u.id != current_user.id:  # 不允许自己停用自己
                u.is_active = not u.is_active
                db.session.commit()
                flash("状态已切换")
        elif action == "delete":
            uid = int(request.form.get("user_id"))
            u = User.query.get(uid)
            if u and u.id != current_user.id:
                db.session.delete(u)
                db.session.commit()
                flash("用户已删除")

    users = User.query.order_by(User.id.asc()).all()
    return render_template("users.html", users=users)

 # ---- AJAX: 启用/停用 切换（无刷新）----
@app.post("/api/users/<int:uid>/toggle")
@login_required
@admin_required
def api_toggle_user(uid):
    u = User.query.get_or_404(uid)
    if u.id == current_user.id:
        return jsonify({"ok": False, "error": "cannot_toggle_self"}), 400
    u.is_active = not u.is_active
    db.session.commit()
    return jsonify({"ok": True, "user": {"id": u.id, "is_active": u.is_active}})


# ---- AJAX: 删除用户（无刷新）----
@app.post("/api/users/<int:uid>/delete")
@login_required
@admin_required
def api_delete_user(uid):
    u = User.query.get_or_404(uid)
    if u.id == current_user.id:
        return jsonify({"ok": False, "error": "cannot_delete_self"}), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify({"ok": True})

# ---- AJAX: 修改密码（无刷新）----
@app.post("/api/users/<int:uid>/password")
@login_required
@admin_required
def api_change_password(uid):
    u = User.query.get_or_404(uid)
    data = request.get_json(silent=True) or {}
    new_password = (data.get("new_password") or "").strip()
    if not new_password:
        return jsonify({"ok": False, "error": "empty_password"}), 400
    if len(new_password) < 6:
        return jsonify({"ok": False, "error": "too_short"}), 400
    u.set_password(new_password)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/teacher/plans", methods=["GET"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def teacher_plans():
    date_str = request.args.get("date") or date.today().isoformat()
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        selected_date = date.today()
        date_str = selected_date.isoformat()

    accessible_ids = get_accessible_student_ids(current_user)
    student_query = StudentProfile.query.filter(StudentProfile.is_deleted.is_(False))
    if current_user.role != User.ROLE_ADMIN:
        if not accessible_ids:
            students = []
        else:
            student_query = student_query.filter(StudentProfile.id.in_(accessible_ids))
            students = student_query.order_by(StudentProfile.full_name.asc()).all()
    else:
        students = student_query.order_by(StudentProfile.full_name.asc()).all()
        accessible_ids = {s.id for s in students}

    catalog = (
        TaskCatalog.query.filter(
            TaskCatalog.is_active.is_(True), TaskCatalog.is_deleted.is_(False)
        )
        .order_by(TaskCatalog.exam_system.asc(), TaskCatalog.module.asc(), TaskCatalog.task_name.asc())
        .all()
    )
    catalog_payload = [
        {
            "id": t.id,
            "exam_system": t.exam_system,
            "module": t.module,
            "task_name": t.task_name,
            "default_minutes": t.default_minutes,
            "description": t.description or "",
        }
        for t in catalog
    ]

    plans_query = StudyPlan.query.filter(
        StudyPlan.plan_date == selected_date, StudyPlan.is_deleted.is_(False)
    ).options(
        joinedload(StudyPlan.student),
        joinedload(StudyPlan.items).joinedload(PlanItem.evidences),
        joinedload(StudyPlan.items).joinedload(PlanItem.sessions),
    )
    if current_user.role != User.ROLE_ADMIN:
        if accessible_ids:
            plans_query = plans_query.filter(StudyPlan.student_id.in_(accessible_ids))
        else:
            plans_query = plans_query.filter(false())
    plans = plans_query.order_by(StudyPlan.plan_date.asc()).all()

    pending_items_query = PlanItem.query.filter(
        PlanItem.review_status == PlanItem.REVIEW_PENDING,
        PlanItem.student_status == PlanItem.STUDENT_SUBMITTED,
        PlanItem.is_deleted.is_(False),
        PlanItem.plan.has(StudyPlan.is_deleted.is_(False)),
    ).options(
        joinedload(PlanItem.plan).joinedload(StudyPlan.student),
        joinedload(PlanItem.evidences),
    )
    if current_user.role != User.ROLE_ADMIN:
        if accessible_ids:
            pending_items_query = pending_items_query.filter(
                PlanItem.plan.has(StudyPlan.student_id.in_(accessible_ids))
            )
        else:
            pending_items_query = pending_items_query.filter(false())
    pending_items = pending_items_query.order_by(PlanItem.created_at.asc()).all()

    # ensure guardian tokens for accessible students (lazy creation)
    token_map = {}
    for stu in students:
        if stu.guardian_view_token:
            token_map[stu.id] = stu.guardian_view_token

    student_payload = [
        {
            "id": stu.id,
            "name": stu.full_name,
            "nickname": stu.nickname,
            "token": token_map.get(stu.id),
            "exam_target": stu.exam_target,
        }
        for stu in students
    ]

    return render_template(
        "teacher_plans.html",
        students=students,
        students_payload=student_payload,
        catalog=catalog,
        catalog_payload=catalog_payload,
        plans=plans,
        pending_items=pending_items,
        selected_date=date_str,
        token_map=token_map,
    )


# ---- Student dashboard & APIs ----


@app.route("/student/today", methods=["GET"])
@login_required
@role_required(User.ROLE_STUDENT)
def student_today():
    profile = current_user.student_profile
    if not profile or profile.is_deleted:
        flash("未找到对应的学生信息，请联系老师。")
        return redirect(url_for("logout"))

    today = date.today()
    plan = (
        StudyPlan.query.filter_by(
            student_id=profile.id, plan_date=today, is_deleted=False
        )
        .options(
            joinedload(StudyPlan.items)
            .joinedload(PlanItem.evidences),
            joinedload(StudyPlan.items).joinedload(PlanItem.sessions),
        )
        .first()
    )

    recent_plans = (
        StudyPlan.query.filter(
            StudyPlan.student_id == profile.id,
            StudyPlan.plan_date < today,
            StudyPlan.is_deleted.is_(False),
        )
        .order_by(StudyPlan.plan_date.desc())
        .limit(3)
        .all()
    )

    return render_template(
        "student_today.html",
        profile=profile,
        today=today,
        plan=plan,
        recent_plans=recent_plans,
    )


def _load_plan_item_for_student(item_id: int) -> PlanItem:
    item = (
        PlanItem.query.options(
            joinedload(PlanItem.plan),
            joinedload(PlanItem.sessions),
            joinedload(PlanItem.evidences),
        )
        .filter(PlanItem.id == item_id, PlanItem.is_deleted.is_(False))
        .first_or_404()
    )
    profile = current_user.student_profile
    if not profile or profile.is_deleted or item.plan.student_id != profile.id:
        raise PermissionError("forbidden_student_item")
    return item


def _plan_item_payload(item: PlanItem) -> dict:
    sessions = [sess for sess in item.sessions if not sess.is_deleted]
    evidences = [ev for ev in item.evidences if not ev.is_deleted]
    total_sessions = sum(sess.duration_seconds for sess in sessions)
    return {
        "id": item.id,
        "plan_id": item.plan_id,
        "task_name": item.task_name,
        "custom_title": item.custom_title,
        "instructions": item.instructions,
        "planned_minutes": item.planned_minutes,
        "actual_seconds": item.actual_seconds,
        "manual_minutes": item.manual_minutes,
        "student_status": item.student_status,
        "review_status": item.review_status,
        "review_comment": item.review_comment,
        "student_comment": item.student_comment,
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "sessions": [
            {
                "id": sess.id,
                "started_at": sess.started_at.isoformat(),
                "ended_at": sess.ended_at.isoformat() if sess.ended_at else None,
                "duration_seconds": sess.duration_seconds,
            }
            for sess in sessions
        ],
        "evidence": [
            {
                "id": ev.id,
                "file_type": ev.file_type,
                "note": ev.note,
                "uploaded_at": ev.created_at.isoformat() if hasattr(ev, "created_at") else None,
            }
            for ev in evidences
        ],
        "total_session_seconds": total_sessions,
    }


@app.post("/api/student/plan-items/<int:item_id>/timer/start")
@login_required
@role_required(User.ROLE_STUDENT)
def api_student_timer_start(item_id):
    try:
        item = _load_plan_item_for_student(item_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    now = datetime.utcnow()
    session = PlanItemSession(
        plan_item=item,
        started_at=now,
        created_by=current_user.id,
        source="timer",
    )
    db.session.add(session)
    if item.student_status == PlanItem.STUDENT_PENDING:
        item.student_status = PlanItem.STUDENT_IN_PROGRESS
    db.session.commit()
    return jsonify({"ok": True, "session_id": session.id, "started_at": now.isoformat()})


@app.post("/api/student/plan-items/<int:item_id>/timer/<int:session_id>/stop")
@login_required
@role_required(User.ROLE_STUDENT)
def api_student_timer_stop(item_id, session_id):
    try:
        item = _load_plan_item_for_student(item_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    session = (
        PlanItemSession.query.filter_by(
            id=session_id,
            plan_item_id=item.id,
            created_by=current_user.id,
            is_deleted=False,
        ).first()
    )
    if not session:
        return jsonify({"ok": False, "error": "session_not_found"}), 404

    if session.ended_at:
        return jsonify({"ok": True, "actual_seconds": item.actual_seconds})

    session.close(datetime.utcnow())
    item.actual_seconds = (item.actual_seconds or 0) + session.duration_seconds
    db.session.commit()
    return jsonify({"ok": True, "actual_seconds": item.actual_seconds, "session_seconds": session.duration_seconds})


@app.post("/api/student/plan-items/<int:item_id>/submit")
@login_required
@role_required(User.ROLE_STUDENT)
def api_student_submit(item_id):
    try:
        item = _load_plan_item_for_student(item_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    manual_minutes = max(0, int(data.get("manual_minutes") or 0))
    comment = (data.get("comment") or "").strip()

    if manual_minutes:
        item.manual_minutes = manual_minutes
        manual_seconds = manual_minutes * 60
        if manual_seconds > item.actual_seconds:
            item.actual_seconds = manual_seconds
    if comment:
        item.student_comment = comment
    item.student_status = PlanItem.STUDENT_SUBMITTED
    item.submitted_at = datetime.utcnow()

    db.session.commit()
    return jsonify({"ok": True, "item": _plan_item_payload(item)})


@app.post("/api/student/plan-items/<int:item_id>/reset-status")
@login_required
@role_required(User.ROLE_STUDENT)
def api_student_reset_status(item_id):
    """Allow student to revert a submission before老师审核."""
    try:
        item = _load_plan_item_for_student(item_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    if item.review_status != PlanItem.REVIEW_PENDING:
        return jsonify({"ok": False, "error": "already_reviewed"}), 400
    item.student_status = PlanItem.STUDENT_PENDING
    item.submitted_at = None
    item.student_comment = None
    db.session.commit()
    return jsonify({"ok": True, "item": _plan_item_payload(item)})


@app.post("/api/student/plan-items/<int:item_id>/evidence")
@login_required
@role_required(User.ROLE_STUDENT)
def api_student_upload_evidence(item_id):
    try:
        item = _load_plan_item_for_student(item_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "missing_file"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "empty_filename"}), 400
    if not allowed_evidence(file.filename):
        return jsonify({"ok": False, "error": "invalid_extension"}), 400

    filename = secure_filename(file.filename)
    student_dir = UPLOAD_ROOT / f"student_{item.plan.student_id}"
    student_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    stored_name = f"{item.id}_{timestamp}_{filename}"
    save_path = student_dir / stored_name
    file.save(save_path)

    evidence = PlanEvidence(
        plan_item=item,
        uploader_id=current_user.id,
        file_type=filename.rsplit(".", 1)[1].lower(),
        storage_path=str(save_path),
        original_filename=filename,
        file_size=save_path.stat().st_size,
    )
    db.session.add(evidence)
    db.session.commit()

    return jsonify(
        {
            "ok": True,
            "evidence": {
                "id": evidence.id,
                "file_type": evidence.file_type,
                "original_filename": evidence.original_filename,
                "note": evidence.note,
            },
        }
    )


def _build_parent_report(student: StudentProfile, start_date: date, end_date: date):
    items = (
        PlanItem.query.join(StudyPlan)
        .filter(
            StudyPlan.student_id == student.id,
            StudyPlan.plan_date >= start_date,
            StudyPlan.plan_date <= end_date,
            StudyPlan.is_deleted.is_(False),
            PlanItem.is_deleted.is_(False),
        )
        .options(joinedload(PlanItem.plan))
        .order_by(StudyPlan.plan_date.asc(), PlanItem.order_index.asc())
        .all()
    )

    filtered_items = [
        item
        for item in items
        if item.review_status in (PlanItem.REVIEW_APPROVED, PlanItem.REVIEW_PARTIAL, PlanItem.REVIEW_REJECTED)
    ]
    total_items = len(items)
    reviewed_items = len(filtered_items)

    planned_total = sum(item.planned_minutes for item in items)
    actual_total = sum((item.actual_seconds or 0) for item in items)
    manual_total = sum((item.manual_minutes or 0) * 60 for item in items)

    module_breakdown = defaultdict(lambda: {"planned": 0, "actual": 0})
    daily = defaultdict(list)
    for item in items:
        module_breakdown[item.module]["planned"] += item.planned_minutes
        module_breakdown[item.module]["actual"] += int((item.actual_seconds or 0) / 60)
        daily[item.plan.plan_date].append(item)

    completion_rate = (
        round(reviewed_items * 100.0 / total_items, 1) if total_items else 0.0
    )

    score_records = (
        ScoreRecord.query.filter(
            ScoreRecord.student_id == student.id,
            ScoreRecord.is_deleted.is_(False),
        )
        .order_by(ScoreRecord.taken_on.desc())
        .limit(5)
        .all()
    )

    return {
        "student": student,
        "start_date": start_date,
        "end_date": end_date,
        "items": items,
        "daily_items": dict(sorted(daily.items())),
        "planned_minutes_total": planned_total,
        "actual_minutes_total": round(actual_total / 60),
        "manual_minutes_total": round(manual_total / 60),
        "completion_rate": completion_rate,
        "module_breakdown": dict(module_breakdown),
        "reviewed_items": reviewed_items,
        "total_items": total_items,
        "score_records": score_records,
    }


@app.route("/parent/report/<token>", methods=["GET"])
def parent_report_view(token):
    student = (
        StudentProfile.query.filter_by(
            guardian_view_token=token, is_deleted=False
        ).first_or_404()
    )
    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    context = _build_parent_report(student, start_date, end_date)
    context.update({"readonly": True, "token": token})
    return render_template("parent_report.html", **context)


@app.route("/teacher/report/<int:student_id>", methods=["GET"])
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def teacher_parent_report(student_id):
    try:
        require_student_access(student_id)
    except PermissionError:
        flash("无权查看该学生的报告。")
        return redirect(url_for("teacher_plans"))
    student = StudentProfile.query.get_or_404(student_id)
    end_date = date.today()
    start_date = end_date - timedelta(days=6)
    context = _build_parent_report(student, start_date, end_date)
    context.update(
        {
            "readonly": False,
            "token": student.guardian_view_token,
        }
    )
    return render_template("parent_report.html", **context)


# ---- Teacher APIs & Tools ----


@app.get("/api/catalog/tasks")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def api_catalog_tasks():
    tasks = (
        TaskCatalog.query.filter(
            TaskCatalog.is_active.is_(True), TaskCatalog.is_deleted.is_(False)
        )
        .order_by(TaskCatalog.exam_system, TaskCatalog.module, TaskCatalog.task_name)
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "tasks": [
                {
                    "id": t.id,
                    "exam_system": t.exam_system,
                    "module": t.module,
                    "task_name": t.task_name,
                    "description": t.description,
                    "default_minutes": t.default_minutes,
                }
                for t in tasks
            ],
        }
    )


@app.post("/api/plans")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def api_create_plan():
    payload = request.get_json(silent=True) or {}
    student_id = payload.get("student_id")
    plan_date_str = payload.get("plan_date")
    items = payload.get("items") or []
    notes = payload.get("notes", "")
    template_id = payload.get("template_id")
    status = payload.get("status") or StudyPlan.STATUS_PUBLISHED
    replace_existing = bool(payload.get("replace"))

    if not student_id or not plan_date_str:
        return jsonify({"ok": False, "error": "missing_student_or_date"}), 400
    try:
        plan_date = datetime.strptime(plan_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_date"}), 400
    if not items:
        return jsonify({"ok": False, "error": "empty_items"}), 400

    try:
        student_id = int(student_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid_student"}), 400

    try:
        require_student_access(student_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    plan = (
        StudyPlan.query.filter_by(student_id=student_id, plan_date=plan_date, is_deleted=False)
        .options(joinedload(StudyPlan.items))
        .first()
    )

    if plan and not replace_existing:
        return jsonify({"ok": False, "error": "plan_exists"}), 409

    if not plan:
        plan = StudyPlan(
            student_id=student_id,
            plan_date=plan_date,
            created_by=current_user.id,
        )
        db.session.add(plan)
    else:
        # 软删除旧 items
        for old in plan.items:
            old.is_deleted = True

    plan.notes = notes
    plan.status = status
    if status == StudyPlan.STATUS_PUBLISHED:
        plan.published_by = current_user.id
        plan.published_at = datetime.utcnow()
    if template_id:
        try:
            template_id = int(template_id)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_template"}), 400
    plan.template_id = template_id

    for idx, item in enumerate(items):
        catalog_id = item.get("catalog_id")
        custom_title = item.get("custom_title")
        instructions = item.get("instructions")
        planned_minutes = max(0, int(item.get("planned_minutes") or 0))

        exam_system = item.get("exam_system")
        module = item.get("module")
        task_name = item.get("task_name")

        if catalog_id:
            catalog = TaskCatalog.query.get(catalog_id)
            if not catalog:
                return jsonify({"ok": False, "error": f"catalog_not_found_{catalog_id}"}), 400
            exam_system = catalog.exam_system
            module = catalog.module
            task_name = catalog.task_name
            if planned_minutes <= 0:
                planned_minutes = catalog.default_minutes
        else:
            if not (exam_system and module and task_name):
                return jsonify({"ok": False, "error": "missing_task_fields"}), 400

        plan_item = PlanItem(
            plan=plan,
            catalog_id=catalog_id,
            exam_system=exam_system,
            module=module,
            task_name=task_name,
            custom_title=custom_title,
            instructions=instructions,
            planned_minutes=planned_minutes,
            order_index=idx,
        )
        db.session.add(plan_item)

    db.session.commit()
    return jsonify({"ok": True, "plan_id": plan.id})


@app.post("/api/plan-items/<int:item_id>/review")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def api_review_plan_item(item_id):
    item = (
        PlanItem.query.options(joinedload(PlanItem.plan).joinedload(StudyPlan.student))
        .filter(PlanItem.id == item_id, PlanItem.is_deleted.is_(False))
        .first_or_404()
    )
    try:
        require_student_access(item.plan.student_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    target_status = data.get("status")
    comment = (data.get("comment") or "").strip()
    if target_status not in {
        PlanItem.REVIEW_APPROVED,
        PlanItem.REVIEW_PARTIAL,
        PlanItem.REVIEW_REJECTED,
    }:
        return jsonify({"ok": False, "error": "invalid_status"}), 400

    previous_status = item.review_status
    item.review_status = target_status
    item.review_comment = comment
    item.review_by = current_user.id
    item.review_at = datetime.utcnow()
    item.locked = target_status in (PlanItem.REVIEW_APPROVED, PlanItem.REVIEW_PARTIAL, PlanItem.REVIEW_REJECTED)

    log = PlanReviewLog(
        plan_item=item,
        reviewer_id=current_user.id,
        from_status=previous_status,
        to_status=target_status,
        comment=comment,
        originated_from="manual",
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({"ok": True, "item_id": item.id, "review_status": item.review_status})


@app.post("/api/students/<int:student_id>/guardian-token")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def api_refresh_guardian_token(student_id):
    try:
        require_student_access(student_id)
    except PermissionError:
        return jsonify({"ok": False, "error": "forbidden"}), 403

    student = StudentProfile.query.get_or_404(student_id)
    action = (request.get_json(silent=True) or {}).get("action", "refresh")
    if action == "clear":
        student.guardian_view_token = None
        db.session.commit()
        return jsonify({"ok": True, "token": None})

    token = secrets.token_urlsafe(16)
    student.guardian_view_token = token
    db.session.commit()
    return jsonify({"ok": True, "token": token})


@app.route("/teacher/evidence/<int:evidence_id>")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def teacher_download_evidence(evidence_id):
    evidence = (
        PlanEvidence.query.options(
            joinedload(PlanEvidence.plan_item).joinedload(PlanItem.plan)
        )
        .filter(PlanEvidence.id == evidence_id, PlanEvidence.is_deleted.is_(False))
        .first_or_404()
    )
    try:
        require_student_access(evidence.plan_item.plan.student_id)
    except PermissionError:
        flash("无权访问该证据。")
        return redirect(url_for("teacher_plans"))

    file_path = Path(evidence.storage_path)
    try:
        file_path.relative_to(UPLOAD_ROOT)
    except ValueError:
        flash("证据文件路径异常。")
        return redirect(url_for("teacher_plans"))
    if not file_path.exists():
        flash("证据文件不存在或已被删除。")
        return redirect(url_for("teacher_plans"))
    return send_from_directory(
        file_path.parent,
        file_path.name,
        as_attachment=True,
        download_name=evidence.original_filename or file_path.name,
    )


@app.route("/tasks", methods=["GET", "POST"])
@login_required
def tasks_page():
    if request.method == "POST":
        d = request.form.get("date") or date.today().isoformat()
        student = request.form.get("student_name", "").strip()
        category = request.form.get("category", "").strip()
        detail = request.form.get("detail", "").strip()
        status = request.form.get("status", "pending")
        note = request.form.get("note", "").strip()
        if student and category and detail:
            t = Task(
                date=d,
                student_name=student,
                category=category,
                detail=detail,
                status=status,
                note=note,
                created_by=current_user.id,
                planned_minutes=int(request.form.get("planned_minutes", 0) or 0),
                accuracy=min(100.0, max(0.0, float(request.form.get("accuracy", 0) or 0))),
            )
            db.session.add(t)
            db.session.commit()
            flash("已添加")
        else:
            flash("请填写：学生、类别、任务描述")
    # 列表：按创建倒序，最多显示最近 30 条
    items = Task.query.order_by(Task.id.desc()).limit(30).all()
    # 为每个任务计算衍生字段：实际分钟、进度百分比
    enriched_items = []
    for t in items:
        actual_minutes = round(int(t.actual_seconds or 0) / 60, 1)
        planned = int(t.planned_minutes or 0)
        progress = round(actual_minutes / planned * 100, 1) if planned > 0 else 0
        enriched_items.append({
            "id": t.id,
            "date": t.date,
            "student_name": t.student_name,
            "category": t.category,
            "detail": t.detail,
            "status": t.status,
            "note": t.note,
            "planned_minutes": planned,
            "actual_minutes": actual_minutes,
            "progress": progress,
        })
    return render_template("tasks.html", items=enriched_items, today=date.today().isoformat())

# ---- AJAX: 删除任务 ----
@app.post("/api/tasks/<int:tid>/delete")
@login_required
def api_task_delete(tid):
    t = Task.query.get_or_404(tid)
    # 权限：创建者或管理员可删
    if t.created_by != current_user.id and current_user.role != "admin":
        return jsonify({"ok": False, "error": "no_permission"}), 403
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})

# ---- AJAX: 编辑任务（可修改日期/学生/类别/详情/状态/备注，部分字段可选）----
@app.post("/api/tasks/<int:tid>/edit")
@login_required
def api_task_edit(tid):
    t = Task.query.get_or_404(tid)
    # 权限：创建者或管理员可改
    if t.created_by != current_user.id and current_user.role != "admin":
        return jsonify({"ok": False, "error": "no_permission"}), 403

    data = request.get_json(silent=True) or {}
    # 允许的状态
    allowed_status = {"pending", "progress", "done"}

    # 按需更新（有传才更新）
    if "date" in data:
        val = (data.get("date") or "").strip()
        if val:
            t.date = val
    if "student_name" in data:
        val = (data.get("student_name") or "").strip()
        if val:
            t.student_name = val
    if "category" in data:
        val = (data.get("category") or "").strip()
        if val:
            t.category = val
    if "detail" in data:
        val = (data.get("detail") or "").strip()
        if val:
            t.detail = val
    if "status" in data:
        val = (data.get("status") or "").strip()
        if val in allowed_status:
            t.status = val
        else:
            return jsonify({"ok": False, "error": "invalid_status"}), 400
    if "note" in data:
        t.note = (data.get("note") or "").strip()
    # 允许更新正确率（0~100）
    if "accuracy" in data:
        try:
            acc = float(data.get("accuracy") or 0.0)
            t.accuracy = min(100.0, max(0.0, acc))
        except Exception:
            return jsonify({"ok": False, "error": "invalid_accuracy"}), 400

    # 允许更新计划/实际用时（可选）
    if "planned_minutes" in data:
        try:
            pm = int(data.get("planned_minutes") or 0)
            t.planned_minutes = max(0, pm)
        except Exception:
            return jsonify({"ok": False, "error": "invalid_planned"}), 400
    if "actual_seconds" in data:
        try:
            as_ = int(data.get("actual_seconds") or 0)
            t.actual_seconds = max(0, as_)
        except Exception:
            return jsonify({"ok": False, "error": "invalid_actual"}), 400

    db.session.commit()
    return jsonify({
        "ok": True,
        "task": {
            "id": t.id,
            "date": t.date,
            "student_name": t.student_name,
            "category": t.category,
            "detail": t.detail,
            "status": t.status,
            "note": t.note,
            "accuracy": t.accuracy
        }
    })


# ---- 计时会话：开始/结束 ----


@app.post("/api/session/start")
@login_required
def api_session_start():
    payload = request.get_json(silent=True) or {}
    task_id = payload.get("task_id")
    sess = StudySession(
        task_id=task_id,
        started_at=datetime.utcnow(),
        created_by=current_user.id
    )
    db.session.add(sess)

    # 若关联了任务：首次开始则写入 Task.started_at（仅当为空）
    if task_id:
        t = Task.query.get(task_id)
        if t and t.created_by in (current_user.id,) or (current_user.role == "admin"):
            if not t.started_at:
                t.started_at = sess.started_at

    db.session.commit()
    return jsonify({"ok": True, "session_id": sess.id, "started_at": sess.started_at.isoformat() + "Z"})

@app.post("/api/session/stop/<int:sid>")
@login_required
def api_session_stop(sid):
    sess = StudySession.query.get_or_404(sid)
    if sess.created_by != current_user.id and current_user.role != "admin":
        return jsonify({"ok": False, "error": "no_permission"}), 403
    if not sess.ended_at:
        sess.close(datetime.utcnow())
        # 若有关联任务则累加实际用时，并填写 ended_at（如未填）
        if sess.task_id:
            t = Task.query.get(sess.task_id)
            if t:
                t.actual_seconds = int((t.actual_seconds or 0) + (sess.seconds or 0))
                if not t.started_at:
                    t.started_at = sess.started_at
                t.ended_at = sess.ended_at  # 最后一次结束时间
        db.session.commit()
    return jsonify({"ok": True, "session_id": sess.id, "seconds": sess.seconds})
# ---- 设置任务的预计用时（分钟）----
@app.post("/api/tasks/<int:tid>/plan")
@login_required
def api_task_plan(tid):
    t = Task.query.get_or_404(tid)
    if t.created_by != current_user.id and current_user.role != "admin":
        return jsonify({"ok": False, "error": "no_permission"}), 403
    data = request.get_json(silent=True) or {}
    try:
        pm = int(data.get("planned_minutes") or 0)
        t.planned_minutes = max(0, pm)
        db.session.commit()
        return jsonify({"ok": True, "planned_minutes": t.planned_minutes})
    except Exception:
        return jsonify({"ok": False, "error": "invalid_planned"}), 400

# ---- 重置任务计时（清零实际用时与起止时间）----
@app.post("/api/tasks/<int:tid>/time_reset")
@login_required
def api_task_time_reset(tid):
    t = Task.query.get_or_404(tid)
    if t.created_by != current_user.id and current_user.role != "admin":
        return jsonify({"ok": False, "error": "no_permission"}), 403
    t.actual_seconds = 0
    t.started_at = None
    t.ended_at = None
    db.session.commit()
    return jsonify({"ok": True})


# ---- 批量添加任务 ----
@app.route("/bulk", methods=["GET", "POST"])
@login_required
def bulk_page():
    """
    批量添加任务：
    行格式： 学生名 | 类别 | 任务描述 | 备注(可选)
    例如：
    张三 | 基础-四级词汇 | 四级词汇 Day3
    李四 | 雅思-听力-精听 | TPO1 S3 精听 | 家里环境安静
    """
    preview = []
    msg = None

    if request.method == "POST":
        action = request.form.get("action")
        raw = (request.form.get("lines") or "").strip()
        date_str = request.form.get("date") or date.today().isoformat()
        status = request.form.get("status") or "pending"

        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        def parse_line(ln):
            parts = [p.strip() for p in ln.split("|")]
            if len(parts) == 1 and "｜" in ln:
                parts = [p.strip() for p in ln.split("｜")]
            while len(parts) < 3:
                parts.append("")
            student, category, detail, *rest = parts
            note = rest[0].strip() if rest else ""
            return student, category, detail, note

        if action == "preview":
            for ln in lines:
                s, c, d, n = parse_line(ln)
                if s and c and d:
                    preview.append({"student": s, "category": c, "detail": d, "note": n})
            if not preview:
                msg = "没有可预览的有效行（每行至少包含：学生 | 类别 | 任务描述）"

        elif action == "create":
            created = 0
            for ln in lines:
                s, c, d, n = parse_line(ln)
                if not (s and c and d):
                    continue
                t = Task(
                    date=date_str,
                    student_name=s,
                    category=c,
                    detail=d,
                    status=status,
                    note=n,
                    created_by=current_user.id
                )
                db.session.add(t)
                created += 1
            if created:
                db.session.commit()
                flash(f"已创建 {created} 条任务")
                return redirect(url_for("tasks_page"))
            else:
                msg = "没有可创建的有效行"

    return render_template("bulk.html",
                           today=date.today().isoformat(),
                           preview=preview,
                           msg=msg)

if __name__ == "__main__":
    app.run(debug=True)

# ---- 学生任务汇总报告 ----
@app.route("/report", methods=["GET"]) 
@login_required
def report_page():
    """
    汇总每位学生的任务：总数、各状态数量、计划/实际用时（总和与平均）。
    可选筛选：start（开始日期 YYYY-MM-DD）、end（结束日期 YYYY-MM-DD）、category、student。
    """
    q = Task.query

    # 读取筛选参数
    start = (request.args.get("start") or "").strip()
    end   = (request.args.get("end") or "").strip()
    category = (request.args.get("category") or "").strip()
    student  = (request.args.get("student") or "").strip()

    # 日期过滤（闭区间）
    if start:
        q = q.filter(Task.date >= start)
    if end:
        q = q.filter(Task.date <= end)
    if category:
        q = q.filter(Task.category == category)
    if student:
        q = q.filter(Task.student_name == student)

    rows = q.all()

    # 聚合
    acc = defaultdict(lambda: {
        "total": 0,
        "pending": 0,
        "progress": 0,
        "done": 0,
        "planned_minutes_sum": 0,
        "actual_seconds_sum": 0,
        "first_date": None,
        "last_date": None,
    })

    for t in rows:
        key = t.student_name or "(未填写)"
        a = acc[key]
        a["total"] += 1
        a[t.status] = a.get(t.status, 0) + 1
        a["planned_minutes_sum"] += int(t.planned_minutes or 0)
        a["actual_seconds_sum"] += int(t.actual_seconds or 0)
        # 记录时间范围
        d = t.date or ""
        if d:
            if a["first_date"] is None or d < a["first_date"]:
                a["first_date"] = d
            if a["last_date"] is None or d > a["last_date"]:
                a["last_date"] = d

    # 整理为列表并计算派生字段
    summary = []
    totals = {
        "students": 0,
        "tasks": 0,
        "planned_minutes_sum": 0,
        "actual_seconds_sum": 0,
        "done": 0,
    }
    for stu, a in acc.items():
        avg_planned = round(a["planned_minutes_sum"]/a["total"], 1) if a["total"] else 0
        avg_actual_min = round((a["actual_seconds_sum"]/60)/a["total"], 1) if a["total"] else 0
        done_rate = round((a["done"]*100.0)/a["total"], 1) if a["total"] else 0
        summary.append({
            "student": stu,
            "total": a["total"],
            "pending": a.get("pending", 0),
            "progress": a.get("progress", 0),
            "done": a.get("done", 0),
            "done_rate": done_rate,                   # 完成率 %
            "planned_minutes_sum": a["planned_minutes_sum"],
            "actual_minutes_sum": round(a["actual_seconds_sum"]/60),
            "avg_planned": avg_planned,               # 平均计划分钟/任务
            "avg_actual": avg_actual_min,             # 平均实际分钟/任务
            "first_date": a["first_date"],
            "last_date": a["last_date"],
        })
        totals["students"] += 1
        totals["tasks"] += a["total"]
        totals["planned_minutes_sum"] += a["planned_minutes_sum"]
        totals["actual_seconds_sum"] += a["actual_seconds_sum"]
        totals["done"] += a.get("done", 0)

    # 排序：按完成率/任务数/学生名
    summary.sort(key=lambda r: (-r["done_rate"], -r["total"], r["student"]))

    return render_template(
        "report.html",
        summary=summary,
        totals={
            **totals,
            "actual_minutes_sum": round(totals["actual_seconds_sum"]/60)
        },
        filters={
            "start": start,
            "end": end,
            "category": category,
            "student": student,
        }
    )

# ---- JSON: 汇总统计报告（所有学生）----
@app.get("/api/report/summary")
@login_required
def api_report_summary():
    """
    返回所有学生的任务汇总数据（JSON格式）
    支持参数：start, end, category
    """
    q = Task.query
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()
    category = (request.args.get("category") or "").strip()

    if start:
        q = q.filter(Task.date >= start)
    if end:
        q = q.filter(Task.date <= end)
    if category:
        q = q.filter(Task.category == category)

    rows = q.all()

    from collections import defaultdict as _dd
    acc = _dd(lambda: {"total":0,"done":0,"progress":0,"pending":0,
                       "planned":0,"actual":0})
    for t in rows:
        key = t.student_name or "(未填写)"
        a = acc[key]
        a["total"] += 1
        a[t.status] = a.get(t.status, 0) + 1
        a["planned"] += int(t.planned_minutes or 0)
        a["actual"] += int(t.actual_seconds or 0)

    result = []
    for stu, a in acc.items():
        result.append({
            "student": stu,
            "total": a["total"],
            "done": a.get("done", 0),
            "progress": a.get("progress", 0),
            "pending": a.get("pending", 0),
            "done_rate": round(a.get("done",0) * 100.0 / a["total"], 1) if a["total"] else 0,
            "planned_minutes": a["planned"],
            "actual_minutes": round(a["actual"] / 60, 1)
        })
    return jsonify({"ok": True, "summary": result})


# ---- JSON: 单个学生的详细任务曲线 ----
@app.get("/api/report/student/<name>")
@login_required
def api_report_student(name):
    """
    返回单个学生的任务详细信息，用于前端生成趋势图。
    支持参数：start, end, category
    """
    q = Task.query.filter_by(student_name=name)
    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()
    category = (request.args.get("category") or "").strip()

    if start:
        q = q.filter(Task.date >= start)
    if end:
        q = q.filter(Task.date <= end)
    if category:
        q = q.filter(Task.category == category)

    rows = q.order_by(Task.date.asc()).all()
    data = [{
        "date": t.date,
        "category": t.category,
        "status": t.status,
        "planned": int(t.planned_minutes or 0),
        "actual": round(int(t.actual_seconds or 0) / 60, 1),
        "accuracy": float(t.accuracy or 0.0),
    } for t in rows]

    return jsonify({"ok": True, "student": name, "records": data})

# 提供一个 JSON 版本（便于将来前端图表或导出）
@app.get("/api/report")
@login_required
def api_report():
    # 直接复用页面逻辑的核心部分（简单实现）
    with app.test_request_context():
        return report_page()

# ---- 导出汇总报告为 Excel（含完成率与平均正确率）----
from io import BytesIO
from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

@app.route("/report/export", methods=["GET"])
@login_required
def export_report_excel():
    """
    导出所有学生（可筛选）的任务汇总为 Excel：
    列：学生、任务总数、完成率%、平均正确率%、计划用时(分)、实际用时(分)
    支持 query 参数：start, end, category, student
    """
    q = Task.query

    start = (request.args.get("start") or "").strip()
    end = (request.args.get("end") or "").strip()
    category = (request.args.get("category") or "").strip()
    student = (request.args.get("student") or "").strip()

    if start:
        q = q.filter(Task.date >= start)
    if end:
        q = q.filter(Task.date <= end)
    if category:
        q = q.filter(Task.category == category)
    if student:
        q = q.filter(Task.student_name == student)

    rows = q.all()

    # 聚合：按学生名汇总
    agg = {}
    for t in rows:
        key = t.student_name or "(未填写)"
        if key not in agg:
            agg[key] = {
                "total": 0,
                "done": 0,
                "planned": 0,
                "actual_sec": 0,
                "acc_sum": 0.0,
            }
        a = agg[key]
        a["total"] += 1
        if (t.status or "") == "done":
            a["done"] += 1
        a["planned"] += int(t.planned_minutes or 0)
        a["actual_sec"] += int(t.actual_seconds or 0)
        a["acc_sum"] += float(t.accuracy or 0.0)

    # 生成 Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "任务汇总"

    headers = ["学生", "任务总数", "完成率 (%)", "平均正确率 (%)", "计划用时 (分钟)", "实际用时 (分钟)"]
    ws.append(headers)

    # 表头样式
    bold = Font(bold=True)
    center = Alignment(horizontal="center")
    for cell in ws[1]:
        cell.font = bold
        cell.alignment = center

    # 数据行
    # 为了稳定输出顺序，按学生名排序
    for stu in sorted(agg.keys()):
        a = agg[stu]
        total = a["total"]
        done_rate = round(a["done"] * 100.0 / total, 1) if total else 0.0
        avg_acc = round(a["acc_sum"] / total, 1) if total else 0.0
        actual_min = round(a["actual_sec"] / 60.0, 1)
        ws.append([stu, total, done_rate, avg_acc, a["planned"], actual_min])

    # 自适应列宽
    for col in ws.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
        col_letter = col[0].column_letter
        ws.column_dimensions[col_letter].width = min(max_len + 2, 40)

    # 写入字节流并返回
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"report_{date.today().isoformat()}.xlsx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
