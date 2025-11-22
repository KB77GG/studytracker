import os
import re
import secrets
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    current_app,
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
from sqlalchemy import false, inspect, text

from config import Config
from pypinyin import lazy_pinyin
from api import init_app as init_api
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

def time_ago(dt):
    """Helper to format time difference"""
    if not dt:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
            
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "刚刚"
    elif seconds < 3600:
        return f"{int(seconds // 60)}分钟前"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}小时前"
    elif seconds < 2592000: # 30 days
        return f"{int(seconds // 86400)}天前"
    else:
        return dt.strftime("%Y-%m-%d")


app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
init_api(app)

UPLOAD_ROOT = Path(app.config.get("UPLOAD_FOLDER", Path(app.root_path) / "uploads"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_EVIDENCE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "mp3", "mp4", "wav", "doc", "docx"}


def allowed_evidence(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EVIDENCE_EXTENSIONS


def ensure_legacy_schema() -> None:
    """Ensure legacy Task table has columns expected by the assistant view."""

    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())

    if "task" in tables:
        columns = {col["name"] for col in inspector.get_columns("task")}
        if "completion_rate" not in columns:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE task ADD COLUMN completion_rate FLOAT"))
            except Exception as exc:  # pragma: no cover - best-effort safeguard
                current_app.logger.warning(
                    "Failed to add completion_rate to task table: %s", exc
                )

    if "plan_item" in tables:
        columns = {col["name"] for col in inspector.get_columns("plan_item")}
        if "student_reset_count" not in columns:
            try:
                with db.engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE plan_item "
                            "ADD COLUMN student_reset_count INTEGER NOT NULL DEFAULT 0"
                        )
                    )
            except Exception as exc:  # pragma: no cover - best-effort safeguard
                current_app.logger.warning(
                    "Failed to add student_reset_count to plan_item table: %s", exc
                )
        if "evidence_policy" not in columns:
            try:
                with db.engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE plan_item "
                            "ADD COLUMN evidence_policy VARCHAR(20) DEFAULT 'optional'"
                        )
                    )
            except Exception as exc:  # pragma: no cover - best-effort safeguard
                current_app.logger.warning(
                    "Failed to add evidence_policy to plan_item table: %s", exc
                )
    if "plan_evidence" in tables:
        columns = {col["name"] for col in inspector.get_columns("plan_evidence")}
        if "text_content" not in columns:
            try:
                with db.engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE plan_evidence ADD COLUMN text_content TEXT")
                    )
            except Exception as exc:  # pragma: no cover - best-effort safeguard
                current_app.logger.warning(
                    "Failed to add text_content to plan_evidence table: %s", exc
                )


with app.app_context():
    ensure_legacy_schema()

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

# 静态文件路由 - 提供上传文件访问
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    """提供上传文件的访问"""
    from flask import send_from_directory
    return send_from_directory(UPLOAD_ROOT, filename)

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


def _slugify_name(full_name: str) -> str:
    base = "".join(lazy_pinyin(full_name, errors="ignore"))
    base = re.sub(r"[^a-z0-9]", "", base.lower())
    return base or "student"


class AccountCreationError(Exception):
    """Raised when automatic account provisioning fails."""

    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.code = code


def create_student_parent_accounts(full_name: str) -> dict[str, str]:
    """Create paired student + parent accounts and return their credentials."""

    clean_name = (full_name or "").strip()
    if not clean_name:
        raise AccountCreationError("请填写学生姓名。", code="missing_full_name")

    student_username = clean_name
    parent_username = f"{clean_name}家长"

    conflict = (
        db.session.query(User.username)
        .filter(User.username.in_([student_username, parent_username]))
        .first()
    )
    if conflict:
        raise AccountCreationError("已存在同名账号，请检查后再试。", code="duplicate_username")

    slug = _slugify_name(clean_name)
    student_password = f"{slug}123"
    parent_password = f"{slug}123prt"

    student_user = User(
        username=student_username,
        role=User.ROLE_STUDENT,
        display_name=clean_name,
    )
    student_user.set_password(student_password)
    db.session.add(student_user)

    parent_user = User(
        username=parent_username,
        role=User.ROLE_PARENT,
        display_name=f"{clean_name}家长",
    )
    parent_user.set_password(parent_password)
    db.session.add(parent_user)
    db.session.flush()

    profile_kwargs = {
        "user_id": student_user.id,
        "full_name": clean_name,
        "guardian_view_token": secrets.token_urlsafe(16),
    }
    if hasattr(StudentProfile, "primary_parent_id"):
        profile_kwargs["primary_parent_id"] = parent_user.id
    elif hasattr(StudentProfile, "primary_parent"):
        profile_kwargs["primary_parent"] = parent_user
    profile = StudentProfile(**profile_kwargs)
    db.session.add(profile)
    
    # [NEW] Create ParentStudentLink for Miniprogram support
    link = ParentStudentLink(
        parent_id=parent_user.id,
        student_name=clean_name,
        relation="家长",
        is_active=True
    )
    db.session.add(link)

    try:
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        current_app.logger.exception(
            "Automatic account creation failed for %s", clean_name
        )
        raise AccountCreationError(f"创建账号失败：{exc}", code="db_error") from exc

    return {
        "student_username": student_username,
        "student_password": student_password,
        "parent_username": parent_username,
        "parent_password": parent_password,
    }

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
                User.ROLE_PARENT,
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
        elif action == "auto_student":
            try:
                creds = create_student_parent_accounts(request.form.get("full_name"))
            except AccountCreationError as exc:
                flash(str(exc))
            else:
                flash(
                    "学生账号：{student_username} / {student_password}；家长账号：{parent_username} / {parent_password}".format(
                        **creds
                    )
                )
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

@app.post("/api/users/auto-student")
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_ASSISTANT)
def api_auto_create_student():
    data = request.get_json(silent=True) or {}
    try:
        creds = create_student_parent_accounts(data.get("full_name"))
    except AccountCreationError as exc:
        status = 400 if exc.code in {"missing_full_name", "duplicate_username"} else 500
        return jsonify({"ok": False, "error": exc.code, "message": str(exc)}), status
    return jsonify({"ok": True, "data": creds})


@app.route("/teacher/plans", methods=["GET", "POST"])
@login_required
def teacher_plans():
    if current_user.role not in [User.ROLE_TEACHER, User.ROLE_ASSISTANT, User.ROLE_ADMIN]:
        flash("权限不足", "error")
        return redirect(url_for("index"))

    # --- 处理添加任务 (POST) ---
    if request.method == "POST":
        date_str = request.form.get("date")
        student_name = request.form.get("student_name")
        category = request.form.get("category")
        planned_minutes = request.form.get("planned_minutes")
        detail = request.form.get("detail")

        if not date_str or not student_name or not category:
            flash("请填写必填项", "error")
        else:
            try:
                task_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                new_task = Task(
                    date=task_date,
                    student_name=student_name,
                    category=category,
                    planned_minutes=int(planned_minutes) if planned_minutes else 0,
                    detail=detail,
                    status="pending",
                    created_by=current_user.id
                )
                db.session.add(new_task)
                db.session.commit()
                flash("任务添加成功", "success")
            except ValueError:
                flash("日期格式错误", "error")
            except Exception as e:
                db.session.rollback()
                flash(f"添加失败: {str(e)}", "error")
        
        return redirect(url_for("teacher_plans", date=date_str, student_name=student_name))

    # --- 处理页面显示 (GET) ---
    date_str = request.args.get("date")
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    # 获取所有学生姓名供下拉选择
    all_students = [s.full_name for s in StudentProfile.query.filter_by(is_deleted=False).order_by(StudentProfile.full_name).all()]

    # 获取任务列表
    filter_student = request.args.get("student_name")
    tasks_query = Task.query.filter(Task.date == selected_date)
    if filter_student:
        tasks_query = tasks_query.filter(Task.student_name == filter_student)
    
    # 权限过滤（如果是普通老师/助教，可能只能看自己关联的学生？目前 Task 表没有关联 ID，暂时不做严格过滤，或者依赖 student_name）
    # 这里为了简单，先显示所有，或者后续根据 TeacherStudentLink 过滤 student_name
    
    tasks = tasks_query.order_by(Task.id.desc()).all()

    # --- 待审核提交 (Pending Reviews) ---
    # 1. PlanItem (新版)
    pending_items_query = PlanItem.query.filter(
        PlanItem.review_status == PlanItem.REVIEW_PENDING,
        PlanItem.student_status == PlanItem.STUDENT_SUBMITTED,
        PlanItem.is_deleted.is_(False),
        PlanItem.plan.has(StudyPlan.is_deleted.is_(False)),
    ).options(
        joinedload(PlanItem.plan).joinedload(StudyPlan.student),
    )
    pending_items = pending_items_query.order_by(PlanItem.created_at.asc()).all()

    pending_reviews = []
    for item in pending_items:
        pending_reviews.append({
            "type": "plan_item",
            "id": item.id,
            "student_name": item.plan.student.full_name,
            "task_name": item.task_name,
            "submitted_at": item.submitted_at,
            "time_ago": time_ago(item.submitted_at) if item.submitted_at else "",
        })

    # 2. Task (旧版)
    pending_legacy_tasks = Task.query.filter(
        Task.student_submitted == True,
        Task.status != 'done' # 假设审核通过会改为 done
    ).all()

    for task in pending_legacy_tasks:
        pending_reviews.append({
            "type": "legacy_task",
            "id": task.id,
            "student_name": task.student_name,
            "task_name": f"{task.category} {task.detail or ''}",
            "submitted_at": task.submitted_at,
            "time_ago": time_ago(task.submitted_at) if task.submitted_at else "",
        })

    # 按提交时间排序
    pending_reviews.sort(key=lambda x: x['submitted_at'] or datetime.min, reverse=True)

    return render_template(
        "teacher_plans.html",
        selected_date=selected_date,
        all_students=all_students,
        tasks=tasks,
        pending_reviews=pending_reviews,
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
        "student_reset_count": item.student_reset_count,
        "evidence_policy": item.evidence_policy,
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
                "original_filename": ev.original_filename,
                "text_content": ev.text_content,
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

        raw_policy = item.get("evidence_policy")
        if isinstance(raw_policy, str):
            evidence_policy = raw_policy.strip().lower()
        else:
            evidence_policy = PlanItem.EVIDENCE_OPTIONAL
        allowed_policies = {
            PlanItem.EVIDENCE_OPTIONAL,
            PlanItem.EVIDENCE_TEXT,
            PlanItem.EVIDENCE_IMAGE,
            PlanItem.EVIDENCE_AUDIO,
            PlanItem.EVIDENCE_REQUIRED,
        }
        if evidence_policy not in allowed_policies:
            evidence_policy = PlanItem.EVIDENCE_OPTIONAL

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
            evidence_policy=evidence_policy,
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
            return redirect(url_for("tasks_page"))
        else:
            flash("请填写：学生、类别、任务描述")
    # Filter by period
    period = request.args.get("period", "week")
    today_obj = date.today()
    if period == "month":
        start_date = today_obj - timedelta(days=30)
    elif period == "year":
        start_date = today_obj - timedelta(days=365)
    else:  # week
        start_date = today_obj - timedelta(days=7)

    # Query tasks within the date range
    query = Task.query.filter(Task.date >= start_date.isoformat())
    
    # Filter by student_name if provided
    filter_student = request.args.get("student_name")
    if filter_student:
        query = query.filter(Task.student_name == filter_student)
        
    items = query.order_by(Task.date.desc(), Task.id.desc()).all()
    # 为每个任务计算衍生字段：实际分钟、进度百分比
    enriched_items = []
    for t in items:
        actual_minutes = round(int(t.actual_seconds or 0) / 60, 1)
        planned = int(t.planned_minutes or 0)
        progress = round(actual_minutes / planned * 100, 1) if planned > 0 else 0
        manual_progress = (
            float(t.completion_rate)
            if t.completion_rate is not None
            else None
        )
        accuracy_value = float(t.accuracy) if t.accuracy is not None else None
        
        # 解析证据照片
        evidence_photos = []
        if t.evidence_photos:
            try:
                import json
                evidence_photos = json.loads(t.evidence_photos)
            except:
                pass
        
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
            "completion_rate": manual_progress,
            "accuracy": accuracy_value,
            "student_submitted": t.student_submitted,
            "evidence_photos": evidence_photos,
            "student_note": t.student_note,
        })
    total_tasks = len(enriched_items)
    completed_tasks = sum(1 for t in enriched_items if t["status"] == "done")
    total_minutes = round(sum((t["actual_minutes"] or 0) for t in enriched_items), 1)
    accuracy_values = [t["accuracy"] for t in enriched_items if t["accuracy"] is not None]
    avg_accuracy = round(sum(accuracy_values) / len(accuracy_values), 1) if accuracy_values else 0.0
    stats_payload = {
        "total": total_tasks,
        "completed": completed_tasks,
        "total_minutes": total_minutes,
        "avg_accuracy": avg_accuracy,
    }
    top_map = {}
    for t in enriched_items:
        key = (t["student_name"] or "").strip() or "未填写学生"
        entry = top_map.setdefault(
            key, {"minutes": 0.0, "tasks": 0, "accuracy_sum": 0.0, "accuracy_cnt": 0}
        )
        entry["minutes"] += t["actual_minutes"] or 0.0
        entry["tasks"] += 1
        if t["accuracy"] is not None:
            entry["accuracy_sum"] += t["accuracy"]
            entry["accuracy_cnt"] += 1
    top_students = []
    for name, payload in top_map.items():
        avg_acc = (
            round(payload["accuracy_sum"] / payload["accuracy_cnt"], 1)
            if payload["accuracy_cnt"]
            else None
        )
        top_students.append(
            {
                "name": name,
                "minutes": round(payload["minutes"], 1),
                "tasks": payload["tasks"],
                "accuracy": avg_acc,
            }
        )
    top_students.sort(key=lambda item: item["minutes"], reverse=True)
    top_students = top_students[:5]
    recent_tasks = enriched_items[:5]

    # 获取所有学生用于下拉框
    all_students = [s.full_name for s in StudentProfile.query.filter_by(is_deleted=False).order_by(StudentProfile.full_name).all()]

    # --- 待审核提交 (Pending Reviews) ---
    # 1. PlanItem (新版)
    pending_items_query = PlanItem.query.filter(
        PlanItem.review_status == PlanItem.REVIEW_PENDING,
        PlanItem.student_status == PlanItem.STUDENT_SUBMITTED,
        PlanItem.is_deleted.is_(False),
        PlanItem.plan.has(StudyPlan.is_deleted.is_(False)),
    ).options(
        joinedload(PlanItem.plan).joinedload(StudyPlan.student),
    )
    pending_items = pending_items_query.order_by(PlanItem.created_at.asc()).all()

    pending_reviews = []
    for item in pending_items:
        pending_reviews.append({
            "type": "plan_item",
            "id": item.id,
            "student_name": item.plan.student.full_name,
            "task_name": item.task_name,
            "submitted_at": item.submitted_at,
            "time_ago": time_ago(item.submitted_at) if item.submitted_at else "",
        })

    # 2. Task (旧版)
    pending_legacy_tasks = Task.query.filter(
        Task.student_submitted == True,
        Task.status != 'done'
    ).all()

    for task in pending_legacy_tasks:
        pending_reviews.append({
            "type": "legacy_task",
            "id": task.id,
            "student_name": task.student_name,
            "task_name": f"{task.category} {task.detail or ''}",
            "submitted_at": task.submitted_at,
            "time_ago": time_ago(task.submitted_at) if task.submitted_at else "",
        })

    # 按提交时间排序
    pending_reviews.sort(key=lambda x: x['submitted_at'] or datetime.min, reverse=True)

    return render_template(
        "tasks.html",
        items=enriched_items,
        today=date.today().isoformat(),
        stats=stats_payload,
        top_students=top_students,
        recent_tasks=recent_tasks,
        all_students=all_students,
        period=period,
        pending_reviews=pending_reviews,
    )

# ---- AJAX: 删除任务 ----
@app.post("/api/tasks/<int:tid>/delete")
@login_required
def api_task_delete(tid):
    t = Task.query.get_or_404(tid)
    # 权限：创建者、管理员或助教可删
    if t.created_by != current_user.id and current_user.role not in ["admin", "assistant"]:
        return jsonify({"ok": False, "error": "no_permission"}), 403
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})

# ---- AJAX: 编辑任务（可修改日期/学生/类别/详情/状态/备注，部分字段可选）----
@app.post("/api/tasks/<int:tid>/edit")
@login_required
def api_task_edit(tid):
    t = Task.query.get_or_404(tid)
    # 权限：创建者、管理员或助教可改
    if t.created_by != current_user.id and current_user.role not in ["admin", "assistant"]:
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
    if "completion_rate" in data:
        val = data.get("completion_rate")
        if val in ("", None):
            t.completion_rate = None
        else:
            try:
                comp = float(val)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "invalid_completion"}), 400
            t.completion_rate = min(100.0, max(0.0, comp))

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
            "accuracy": t.accuracy,
            "completion_rate": t.completion_rate,
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
        if t and (t.created_by == current_user.id or current_user.role in ["admin", "assistant"]):
            if not t.started_at:
                t.started_at = sess.started_at

    db.session.commit()
    return jsonify({"ok": True, "session_id": sess.id, "started_at": sess.started_at.isoformat() + "Z"})

@app.post("/api/session/stop/<int:sid>")
@login_required
def api_session_stop(sid):
    sess = StudySession.query.get_or_404(sid)
    if sess.created_by != current_user.id and current_user.role not in ["admin", "assistant"]:
        return jsonify({"ok": False, "error": "no_permission"}), 403
    payload = request.get_json(silent=True) or {}
    seconds_hint = payload.get("seconds")
    if isinstance(seconds_hint, (int, float)):
        seconds_hint = max(0, int(seconds_hint))
    else:
        seconds_hint = None

    if not sess.ended_at:
        if seconds_hint is not None:
            ended_at = sess.started_at + timedelta(seconds=seconds_hint)
        else:
            ended_at = datetime.utcnow()
        sess.close(ended_at)
        # 若有关联任务则累加实际用时，并填写 ended_at（如未填）
        if sess.task_id:
            t = Task.query.get(sess.task_id)
            if t:
                t.actual_seconds = int((t.actual_seconds or 0) + (sess.seconds or 0))
                if not t.started_at:
                    t.started_at = sess.started_at
                t.ended_at = sess.ended_at  # 最后一次结束时间
        db.session.commit()
    return jsonify({"ok": True, "session_id": sess.id, "seconds": sess.seconds or 0})
# ---- 设置任务的预计用时（分钟）----
@app.post("/api/tasks/<int:tid>/plan")
@login_required
def api_task_plan(tid):
    t = Task.query.get_or_404(tid)
    if t.created_by != current_user.id and current_user.role not in ["admin", "assistant"]:
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
    if t.created_by != current_user.id and current_user.role not in ["admin", "assistant"]:
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

def _safe_report_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _extract_report_students():
    values = request.args.getlist("student")
    if not values:
        single = (request.args.get("student") or "").strip()
        if single:
            values = [single]
    cleaned = []
    seen = set()
    for val in values:
        name = (val or "").strip()
        if name and name not in seen:
            seen.add(name)
            cleaned.append(name)
    return cleaned


def _parse_report_filters():
    today = date.today()
    period_param = (request.args.get("period") or "").strip()
    if period_param in {"7", "14", "30"}:
        default_days = int(period_param)
    else:
        default_days = 7

    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()

    start_date = _safe_report_date(start_raw)
    end_date = _safe_report_date(end_raw)

    if not end_date:
        end_date = today
    if not start_date:
        start_date = end_date - timedelta(days=max(default_days, 1) - 1)

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    period_value = period_param or str(default_days)
    if (start_raw and not period_param) or (end_raw and not period_param):
        period_value = "custom"

    return {
        "start": start_date,
        "end": end_date,
        "start_str": start_date.isoformat(),
        "end_str": end_date.isoformat(),
        "category": (request.args.get("category") or "").strip(),
        "students": _extract_report_students(),
        "period": period_value,
    }


def _iter_date_labels(start_date, end_date):
    labels = []
    current = start_date
    while current <= end_date:
        labels.append(current.isoformat())
        current += timedelta(days=1)
    return labels


def _query_report_tasks(filters):
    q = Task.query
    if filters.get("start"):
        q = q.filter(Task.date >= filters["start_str"])
    if filters.get("end"):
        q = q.filter(Task.date <= filters["end_str"])
    if filters.get("category"):
        q = q.filter(Task.category == filters["category"])
    if filters.get("students"):
        q = q.filter(Task.student_name.in_(filters["students"]))
    return q.order_by(Task.date.asc()).all()


def _available_report_students():
    rows = (
        db.session.query(Task.student_name)
        .filter(Task.student_name.isnot(None))
        .filter(Task.student_name != "")
        .distinct()
        .order_by(Task.student_name.asc())
        .all()
    )
    return [row[0] for row in rows]


def _build_report_payload(tasks, filters):
    summary_map = defaultdict(
        lambda: {
            "total": 0,
            "pending": 0,
            "progress": 0,
            "done": 0,
            "planned_minutes_sum": 0,
            "actual_seconds_sum": 0,
            "first_date": None,
            "last_date": None,
            "accuracy_sum": 0.0,
            "accuracy_count": 0,
            "completion_sum": 0.0,
            "completion_count": 0,
        }
    )

    daily_counts = defaultdict(lambda: {"total": 0, "pending": 0, "progress": 0, "done": 0})
    category_daily_minutes = defaultdict(lambda: defaultdict(float))
    category_totals = defaultdict(float)
    accuracy_by_category = defaultdict(lambda: {"sum": 0.0, "count": 0})

    completion_values = []
    accuracy_values = []
    actual_seconds_total = 0
    planned_minutes_total = 0
    total_done = 0

    for task in tasks:
        student = (task.student_name or "").strip() or "未填写学生"
        status = (task.status or "pending").lower()
        if status not in {"pending", "progress", "done"}:
            status = "pending"

        planned_minutes = max(0, int(task.planned_minutes or 0))
        actual_seconds = max(0, int(task.actual_seconds or 0))
        actual_minutes = actual_seconds / 60.0

        completion = task.completion_rate
        if completion is None and planned_minutes > 0:
            completion = (actual_minutes / planned_minutes) * 100.0
        if completion is not None:
            completion = round(float(completion), 1)
            completion_values.append(completion)

        accuracy = task.accuracy
        if accuracy is not None:
            accuracy = round(float(accuracy), 1)
            accuracy_values.append(accuracy)

        entry = summary_map[student]
        entry["total"] += 1
        entry[status] += 1
        entry["planned_minutes_sum"] += planned_minutes
        entry["actual_seconds_sum"] += actual_seconds

        if accuracy is not None:
            entry["accuracy_sum"] += accuracy
            entry["accuracy_count"] += 1
        if completion is not None:
            entry["completion_sum"] += completion
            entry["completion_count"] += 1

        task_date_obj = _safe_report_date(task.date)
        if task_date_obj:
            date_key = task_date_obj.isoformat()
            stats = daily_counts[date_key]
            stats["total"] += 1
            stats[status] += 1

            category = (task.category or "").strip() or "未分类"
            category_daily_minutes[category][date_key] += actual_minutes
            category_totals[category] += actual_minutes

            if accuracy is not None:
                cat_acc = accuracy_by_category[category]
                cat_acc["sum"] += accuracy
                cat_acc["count"] += 1

            if entry["first_date"] is None or date_key < entry["first_date"]:
                entry["first_date"] = date_key
            if entry["last_date"] is None or date_key > entry["last_date"]:
                entry["last_date"] = date_key

        actual_seconds_total += actual_seconds
        planned_minutes_total += planned_minutes
        if status == "done":
            total_done += 1

    summary = []
    for student, data in summary_map.items():
        total = data["total"]
        actual_minutes_sum = round(data["actual_seconds_sum"] / 60.0, 1)
        avg_planned = round(data["planned_minutes_sum"] / total, 1) if total else 0.0
        avg_actual = round(actual_minutes_sum / total, 1) if total else 0.0
        done_rate = round(data["done"] * 100.0 / total, 1) if total else 0.0
        avg_accuracy = (
            round(data["accuracy_sum"] / data["accuracy_count"], 1)
            if data["accuracy_count"]
            else 0.0
        )
        avg_completion = (
            round(data["completion_sum"] / data["completion_count"], 1)
            if data["completion_count"]
            else None
        )
        summary.append(
            {
                "student": student,
                "total": total,
                "pending": data["pending"],
                "progress": data["progress"],
                "done": data["done"],
                "done_rate": done_rate,
                "avg_completion": avg_completion,
                "avg_accuracy": avg_accuracy,
                "planned_minutes_sum": data["planned_minutes_sum"],
                "actual_minutes_sum": actual_minutes_sum,
                "avg_planned": avg_planned,
                "avg_actual": avg_actual,
                "first_date": data["first_date"],
                "last_date": data["last_date"],
            }
        )

    summary.sort(key=lambda r: (-r["done_rate"], -r["total"], r["student"]))

    totals = {
        "students": len(summary_map),
        "tasks": len(tasks),
        "planned_minutes_sum": planned_minutes_total,
        "actual_minutes_sum": round(actual_seconds_total / 60.0, 1),
        "done": total_done,
        "avg_completion": (
            round(sum(completion_values) / len(completion_values), 1)
            if completion_values
            else None
        ),
        "avg_accuracy": (
            round(sum(accuracy_values) / len(accuracy_values), 1) if accuracy_values else None
        ),
    }

    date_labels = _iter_date_labels(filters["start"], filters["end"])
    daily_task_chart = {
        "labels": date_labels,
        "datasets": {
            "assigned": [daily_counts.get(day, {}).get("total", 0) for day in date_labels],
            "completed": [daily_counts.get(day, {}).get("done", 0) for day in date_labels],
            "inProgress": [daily_counts.get(day, {}).get("progress", 0) for day in date_labels],
            "pending": [daily_counts.get(day, {}).get("pending", 0) for day in date_labels],
        },
    }

    sorted_categories = sorted(
        category_totals.items(), key=lambda item: item[1], reverse=True
    )
    top_categories = [cat for cat, _ in sorted_categories[:5]]
    category_datasets = []
    for cat in top_categories:
        date_map = category_daily_minutes[cat]
        category_datasets.append(
            {"label": cat, "data": [round(date_map.get(day, 0.0), 2) for day in date_labels]}
        )
    if len(sorted_categories) > len(top_categories):
        other_by_date = {day: 0.0 for day in date_labels}
        for cat, _total in sorted_categories[len(top_categories) :]:
            for day, minutes in category_daily_minutes[cat].items():
                other_by_date[day] = other_by_date.get(day, 0.0) + minutes
        category_datasets.append(
            {"label": "其他", "data": [round(other_by_date.get(day, 0.0), 2) for day in date_labels]}
        )

    category_share_labels = [cat for cat, _ in sorted_categories[:5]]
    category_share_data = [round(total, 2) for _, total in sorted_categories[:5]]
    if len(sorted_categories) > 5:
        other_total = sum(total for _, total in sorted_categories[5:])
        category_share_labels.append("其他")
        category_share_data.append(round(other_total, 2))

    accuracy_by_student_labels = [row["student"] for row in summary]
    accuracy_by_student_data = [row["avg_accuracy"] for row in summary]

    accuracy_by_category_labels = []
    accuracy_by_category_data = []
    for cat, stats in sorted(accuracy_by_category.items(), key=lambda item: item[0]):
        if stats["count"]:
            accuracy_by_category_labels.append(cat)
            accuracy_by_category_data.append(round(stats["sum"] / stats["count"], 1))

    total_hours = round(actual_seconds_total / 3600.0, 2)
    day_count = max(1, len(date_labels))
    avg_daily_hours = round(total_hours / day_count, 2) if day_count else 0.0
    avg_completion_rate = totals["avg_completion"]
    if avg_completion_rate is None:
        avg_completion_rate = (
            round(total_done * 100.0 / len(tasks), 1) if tasks else 0.0
        )

    top_category = None
    if sorted_categories:
        cat_name, minutes = sorted_categories[0]
        top_category = {
            "name": cat_name,
            "hours": round(minutes / 60.0, 2),
        }

    cards = {
        "total_tasks": len(tasks),
        "completed_tasks": total_done,
        "avg_completion_rate": avg_completion_rate,
        "total_hours": total_hours,
        "avg_daily_hours": avg_daily_hours,
        "top_category": top_category,
        "avg_accuracy": totals["avg_accuracy"] or 0.0,
        "total_students": totals["students"],
    }

    return {
        "filters": {
            "start": filters["start_str"],
            "end": filters["end_str"],
            "category": filters.get("category"),
            "students": filters.get("students", []),
            "period": filters.get("period"),
        },
        "summary": summary,
        "totals": totals,
        "cards": cards,
        "charts": {
            "dailyTasks": daily_task_chart,
            "dailyCategoryMinutes": {"labels": date_labels, "datasets": category_datasets},
            "categoryShare": {"labels": category_share_labels, "data": category_share_data},
            "accuracyByStudent": {
                "labels": accuracy_by_student_labels,
                "data": accuracy_by_student_data,
            },
            "accuracyByCategory": {
                "labels": accuracy_by_category_labels,
                "data": accuracy_by_category_data,
            },
        },
        "availableStudents": _available_report_students(),
        "dateLabels": date_labels,
        "hasData": bool(tasks),
    }


@app.route("/report", methods=["GET"])
@login_required
def report_page():
    filters = _parse_report_filters()
    tasks = _query_report_tasks(filters)
    payload = _build_report_payload(tasks, filters)
    return render_template(
        "report.html",
        report_payload=payload,
        summary=payload["summary"],
        totals=payload["totals"],
        filters=payload["filters"],
    )


@app.route("/report/student-view", methods=["GET"])
@login_required
def report_student_view():
    filters = _parse_report_filters()
    available_students = _available_report_students()
    selected = filters["students"][0] if filters["students"] else None
    if not selected and available_students:
        selected = available_students[0]
        filters["students"] = [selected]
    elif selected:
        filters["students"] = [selected]

    tasks = _query_report_tasks(filters) if selected else []
    payload = _build_report_payload(tasks, filters)

    student_summary = payload["summary"][0] if payload["summary"] else None
    records = [
        {
            "id": task.id,
            "date": task.date,
            "category": task.category,
            "detail": task.detail,
            "status": task.status,
            "planned_minutes": int(task.planned_minutes or 0),
            "actual_minutes": round(int(task.actual_seconds or 0) / 60.0, 1),
            "completion_rate": float(task.completion_rate)
            if task.completion_rate is not None
            else None,
            "accuracy": float(task.accuracy or 0.0),
            "note": task.note or "",
        }
        for task in tasks
    ]
    records.sort(key=lambda row: row["date"] or "", reverse=True)

    return render_template(
        "report_student.html",
        selected_student=selected,
        report_payload=payload,
        student_summary=student_summary,
        student_records=records,
        available_students=available_students,
    )


# ---- JSON: 汇总统计报告（所有学生）----
@app.get("/api/report/summary")
@login_required
def api_report_summary():
    filters = _parse_report_filters()
    tasks = _query_report_tasks(filters)
    payload = _build_report_payload(tasks, filters)
    return jsonify({"ok": True, "data": payload})


# ---- JSON: 单个学生的详细任务曲线 ----
@app.get("/api/report/student/<name>")
@login_required
def api_report_student(name):
    filters = _parse_report_filters()
    filters["students"] = [name]
    tasks = _query_report_tasks(filters)
    payload = _build_report_payload(tasks, filters)
    records = [
        {
            "id": task.id,
            "date": task.date,
            "category": task.category,
            "detail": task.detail,
            "status": task.status,
            "planned": int(task.planned_minutes or 0),
            "actual": round(int(task.actual_seconds or 0) / 60.0, 1),
            "completion_rate": float(task.completion_rate)
            if task.completion_rate is not None
            else None,
            "accuracy": float(task.accuracy or 0.0),
            "note": task.note,
        }
        for task in tasks
    ]
    return jsonify({"ok": True, "student": name, "records": records, "summary": payload})


@app.get("/api/report")
@login_required
def api_report():
    filters = _parse_report_filters()
    tasks = _query_report_tasks(filters)
    payload = _build_report_payload(tasks, filters)
    return jsonify({"ok": True, "data": payload})

# ---- 导出汇总报告为 Excel（含完成率与平均正确率）----
from io import BytesIO
from flask import send_file
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

try:
    from weasyprint import HTML, CSS
except ImportError:  # pragma: no cover - optional dependency
    HTML = None
    CSS = None

@app.route("/report/export", methods=["GET"])
@login_required
def export_report_excel():
    filters = _parse_report_filters()
    tasks = _query_report_tasks(filters)
    payload = _build_report_payload(tasks, filters)

    selected_students = payload["filters"].get("students") or []
    single_student = selected_students[0] if len(selected_students) == 1 else None
    if selected_students:
        tasks = [
            task
            for task in tasks
            if ((task.student_name or "").strip() or "未填写学生") in selected_students
        ]

    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = f"{single_student}-汇总" if single_student else "汇总"

    summary_headers = [
        "学生",
        "任务总数",
        "未开始",
        "进行中",
        "已完成",
        "完成率 (%)",
        "平均完成率 (%)",
        "平均正确率 (%)",
        "计划用时 (分钟)",
        "实际用时 (分钟)",
    ]
    summary_ws.append(summary_headers)

    header_font = Font(bold=True)
    header_alignment = Alignment(horizontal="center")
    for cell in summary_ws[1]:
        cell.font = header_font
        cell.alignment = header_alignment

    summary_rows = payload["summary"]
    if selected_students:
        summary_rows = [
            row for row in summary_rows if row["student"] in selected_students
        ]

    for row in summary_rows:
        avg_completion = row.get("avg_completion")
        summary_ws.append(
            [
                row["student"],
                row["total"],
                row["pending"],
                row["progress"],
                row["done"],
                row["done_rate"],
                avg_completion if avg_completion is not None else "",
                row["avg_accuracy"],
                row["planned_minutes_sum"],
                row["actual_minutes_sum"],
            ]
        )

    for column in summary_ws.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column)
        summary_ws.column_dimensions[column[0].column_letter].width = min(max_len + 2, 40)

    detail_title = f"{single_student}-任务明细" if single_student else "任务明细"
    detail_ws = wb.create_sheet(detail_title)
    detail_headers = [
        "学生",
        "日期",
        "类别",
        "任务",
        "状态",
        "计划 (分钟)",
        "实际 (分钟)",
        "完成率 (%)",
        "正确率 (%)",
        "备注",
    ]
    detail_ws.append(detail_headers)
    for cell in detail_ws[1]:
        cell.font = header_font
        cell.alignment = header_alignment

    for task in tasks:
        detail_ws.append(
            [
                (task.student_name or "").strip() or "未填写学生",
                task.date,
                task.category or "",
                task.detail or "",
                task.status or "",
                int(task.planned_minutes or 0),
                round(int(task.actual_seconds or 0) / 60.0, 1),
                float(task.completion_rate) if task.completion_rate is not None else "",
                float(task.accuracy or 0.0),
                task.note or "",
            ]
        )

    for column in detail_ws.columns:
        max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column)
        detail_ws.column_dimensions[column[0].column_letter].width = min(max_len + 2, 60)

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


@app.route("/report/export/pdf", methods=["GET"])
@login_required
def export_report_pdf():
    if HTML is None or CSS is None:
        flash("服务器未安装 PDF 导出依赖（weasyprint），请联系管理员。")
        referrer = request.referrer or url_for("report_page")
        return redirect(referrer)

    filters = _parse_report_filters()
    tasks = _query_report_tasks(filters)
    payload = _build_report_payload(tasks, filters)

    selected_students = payload["filters"].get("students") or []
    single_student = selected_students[0] if len(selected_students) == 1 else None

    summary_rows = payload["summary"]
    if selected_students:
        summary_rows = [
            row for row in summary_rows if row["student"] in selected_students
        ]
        tasks = [
            task
            for task in tasks
            if ((task.student_name or "").strip() or "未填写学生") in selected_students
        ]

    task_rows = [
        {
            "student": (task.student_name or "").strip() or "未填写学生",
            "date": task.date,
            "category": task.category or "",
            "detail": task.detail or "",
            "status": task.status or "",
            "planned_minutes": int(task.planned_minutes or 0),
            "actual_minutes": round(int(task.actual_seconds or 0) / 60.0, 1),
            "completion_rate": (
                f"{float(task.completion_rate):.1f}%"
                if task.completion_rate is not None
                else "—"
            ),
            "accuracy": (
                f"{float(task.accuracy or 0.0):.1f}%"
                if task.accuracy is not None
                else "0.0%"
            ),
            "note": task.note or "",
        }
        for task in tasks
    ]

    generated_at = datetime.now()
    html = render_template(
        "report_pdf.html",
        generated_at=generated_at,
        filters=payload["filters"],
        cards=payload["cards"],
        summary=summary_rows,
        tasks=task_rows,
        selected_students=selected_students,
        single_student=single_student,
    )

    css = CSS(
        string="""
@page {
  size: A4;
  margin: 20mm 16mm 22mm 16mm;
  @top-center {
    content: "Sage Path 学习管理系统";
    font-size: 8pt;
    color: #5f6c7b;
    padding-bottom: 3mm;
    border-bottom: 1px solid #e0e6ed;
  }
  @bottom-center {
    content: "第 " counter(page) " 页，共 " counter(pages) " 页";
    font-size: 8pt;
    color: #5f6c7b;
  }
}

/* Base Styles */
body {
  font-family: 'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'WenQuanYi Micro Hei', sans-serif;
  color: #1f2d3d;
  font-size: 10pt;
  line-height: 1.5;
}

/* Header Section with Logo */
.header-section {
  display: flex;
  align-items: center;
  margin-bottom: 8mm;
  padding-bottom: 5mm;
  border-bottom: 3px solid #2F8E87;
}

.logo-container {
  margin-right: 6mm;
}

.logo {
  width: 50px;
  height: 50px;
  object-fit: contain;
  border-radius: 8px;
}

.title-group {
  flex: 1;
}

h1 {
  font-size: 22pt;
  margin: 0 0 2mm;
  color: #2F8E87;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.title-underline {
  width: 60px;
  height: 3px;
  background: linear-gradient(90deg, #2F8E87 0%, #5FBAB4 100%);
  border-radius: 2px;
}

/* Meta Information */
.meta {
  background: #f8fafa;
  padding: 4mm;
  border-radius: 8px;
  border-left: 3px solid #2F8E87;
  margin-bottom: 6mm;
  font-size: 9.5pt;
}

.meta-row {
  margin-bottom: 2mm;
}

.meta-row:last-child {
  margin-bottom: 0;
}

.meta-label {
  font-weight: 600;
  color: #2F8E87;
}

/* Section Divider */
.section-divider {
  height: 2px;
  background: linear-gradient(90deg, #2F8E87 0%, transparent 100%);
  margin: 6mm 0;
}

/* Cards */
.cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4mm;
  margin-bottom: 6mm;
}

.card {
  border: 1px solid #d1e7e5;
  border-radius: 10px;
  padding: 5mm;
  background: linear-gradient(135deg, #ffffff 0%, #f9fdfc 100%);
  box-shadow: 0 2px 4px rgba(47, 142, 135, 0.08);
  text-align: center;
}

.card-icon {
  font-size: 20pt;
  margin-bottom: 2mm;
}

.card-content {
  text-align: center;
}

.card-title {
  font-size: 8.5pt;
  color: #5f6c7b;
  margin-bottom: 2mm;
  font-weight: 500;
}

.card-value {
  font-size: 18pt;
  font-weight: 700;
  color: #2F8E87;
  margin-bottom: 2mm;
}

.card-subtitle {
  font-size: 7.5pt;
  color: #8492a6;
  line-height: 1.4;
}

/* Progress Bar */
.progress-bar {
  width: 100%;
  height: 4px;
  background: #e8ecf5;
  border-radius: 2px;
  margin-top: 2mm;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2F8E87 0%, #5FBAB4 100%);
  border-radius: 2px;
}

/* Section Title */
h2.section-title {
  font-size: 14pt;
  font-weight: 700;
  margin: 0 0 4mm;
  color: #2F8E87;
  display: flex;
  align-items: center;
  padding-bottom: 2mm;
  border-bottom: 2px solid #e8ecf5;
}

.section-icon {
  margin-right: 2mm;
  font-size: 14pt;
}

/* Table Styles */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 8.5pt;
  margin-bottom: 6mm;
}

th, td {
  border: 1px solid #d1e7e5;
  padding: 2.5mm 2mm;
  text-align: center;
}

th {
  background: linear-gradient(180deg, #2F8E87 0%, #287f78 100%);
  font-weight: 600;
  color: #ffffff;
  font-size: 9pt;
}

tbody tr:nth-child(odd) {
  background: #fbfdfc;
}

tbody tr:nth-child(even) {
  background: #ffffff;
}

tbody tr:hover {
  background: #f0f7f6;
}

/* Special Table Cells */
.student-name {
  font-weight: 600;
  color: #2F8E87;
}

.highlight-done {
  font-weight: 700;
  color: #10b981;
}

.highlight-accuracy {
  font-weight: 600;
  color: #f59e0b;
}

.category-cell {
  font-size: 8pt;
  color: #5f6c7b;
}

.detail-cell {
  text-align: left;
  font-size: 8pt;
}

.date-range {
  font-size: 7.5pt;
  line-height: 1.3;
  color: #5f6c7b;
}

.note-cell {
  text-align: left;
  font-size: 7.5pt;
  color: #8492a6;
}

/* Status Badges */
.status-badge {
  display: inline-block;
  padding: 1mm 2.5mm;
  border-radius: 4px;
  font-size: 7.5pt;
  font-weight: 600;
}

.status-done {
  background: #d1fae5;
  color: #065f46;
}

.status-progress {
  background: #dbeafe;
  color: #1e40af;
}

.status-pending {
  background: #f3f4f6;
  color: #6b7280;
}

/* Page Break */
.page-break {
  page-break-before: always;
}

/* Footer Note */
.footer-note {
  display: flex;
  align-items: center;
  margin-top: 8mm;
  padding: 4mm;
  background: #f8fafa;
  border-radius: 8px;
  border-left: 3px solid #2F8E87;
  font-size: 8.5pt;
  color: #5f6c7b;
}

.footer-icon {
  margin-right: 2mm;
  font-size: 12pt;
}
"""
    )

    pdf_stream = BytesIO()
    HTML(string=html, base_url=request.base_url).write_pdf(
        target=pdf_stream, stylesheets=[css]
    )
    pdf_stream.seek(0)

    filename_student = single_student if single_student else "all"
    filename = f"report_{filename_student}_{date.today().isoformat()}.pdf"
    return send_file(
        pdf_stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )
