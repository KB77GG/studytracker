import os
import re
import secrets
import uuid
import subprocess
import json
from pathlib import Path
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    current_app,
    flash,
    jsonify,
    make_response,
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
from api.wechat import send_subscribe_message
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
    StudySession,
    Task,
    CoursePlan,
    StageReport,
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
        if "question_ids" not in columns:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text("ALTER TABLE task ADD COLUMN question_ids TEXT"))
            except Exception as exc:  # pragma: no cover - best-effort safeguard
                current_app.logger.warning(
                    "Failed to add question_ids to task table: %s", exc
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
    if "student_profile" in tables:
        columns = {col["name"] for col in inspector.get_columns("student_profile")}
        if "scheduler_student_id" not in columns:
            try:
                with db.engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE student_profile ADD COLUMN scheduler_student_id INTEGER")
                    )
            except Exception as exc:  # pragma: no cover
                current_app.logger.warning(
                    "Failed to add scheduler_student_id to student_profile table: %s", exc
                )
        try:
            existing_indexes = {idx["name"] for idx in inspector.get_indexes("student_profile")}
            if "ix_student_profile_scheduler_student_id" not in existing_indexes:
                with db.engine.begin() as conn:
                    conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS "
                            "ix_student_profile_scheduler_student_id "
                            "ON student_profile (scheduler_student_id)"
                        )
                    )
        except Exception as exc:  # pragma: no cover
            current_app.logger.warning(
                "Failed to ensure index on student_profile.scheduler_student_id: %s", exc
            )
    if "user" in tables:
        columns = {col["name"] for col in inspector.get_columns("user")}
        if "scheduler_teacher_id" not in columns:
            try:
                with db.engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE user ADD COLUMN scheduler_teacher_id INTEGER")
                    )
            except Exception as exc:  # pragma: no cover
                current_app.logger.warning(
                    "Failed to add scheduler_teacher_id to user table: %s", exc
                )
        try:
            existing_indexes = {idx["name"] for idx in inspector.get_indexes("user")}
            if "ix_user_scheduler_teacher_id" not in existing_indexes:
                with db.engine.begin() as conn:
                    conn.execute(
                        text(
                            "CREATE UNIQUE INDEX IF NOT EXISTS "
                            "ix_user_scheduler_teacher_id ON user (scheduler_teacher_id)"
                        )
                    )
        except Exception as exc:  # pragma: no cover
            current_app.logger.warning(
                "Failed to ensure index on user.scheduler_teacher_id: %s", exc
            )

    try:
        StageReport.__table__.create(bind=db.engine, checkfirst=True)
    except Exception as exc:  # pragma: no cover
        current_app.logger.warning(
            "Failed to ensure stage_report table exists: %s", exc
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
    if current_user.role in (User.ROLE_TEACHER, User.ROLE_ASSISTANT, User.ROLE_ADMIN):
        return redirect(url_for("materials_list"))
    if current_user.role == User.ROLE_COURSE_PLANNER:
        return redirect(url_for("course_plan_list"))
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


SPECIAL_STAGE_REPORT_USERS = {"陈悦"}


def can_access_stage_report(user: User) -> bool:
    """Allow only admins and explicitly whitelisted user names."""

    if not user or not user.is_authenticated:
        return False
    if user.role == User.ROLE_ADMIN:
        return True
    names = {(user.username or "").strip(), (user.display_name or "").strip()}
    return any(name in SPECIAL_STAGE_REPORT_USERS for name in names if name)


def stage_report_access_required(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not can_access_stage_report(current_user):
            if request.accept_mimetypes.best == "application/json":
                return jsonify({"ok": False, "error": "forbidden"}), 403
            flash("无权限访问阶段学习报告。")
            return redirect(url_for("index"))
        return view_fn(*args, **kwargs)

    return wrapper


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
                User.ROLE_COURSE_PLANNER,
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
        elif action == "create_student":
            # 仅创建学生档案，不创建User账号（学生将通过微信小程序绑定）
            full_name = request.form.get("full_name", "").strip()
            if not full_name:
                flash("请输入学生姓名")
            else:
                # 检查是否已存在同名学生
                existing = StudentProfile.query.filter_by(full_name=full_name, is_deleted=False).first()
                if existing:
                    flash(f"学生'{full_name}'已存在")
                else:
                    profile = StudentProfile(
                        full_name=full_name,
                        guardian_view_token=secrets.token_urlsafe(16),
                    )
                    db.session.add(profile)
                    db.session.commit()
                    flash(f"学生档案'{full_name}'创建成功，学生可通过微信小程序绑定")
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
        elif action == "delete_student":
            # 删除学生档案
            student_id = int(request.form.get("student_id"))
            student = StudentProfile.query.get(student_id)
            if student:
                student.is_deleted = True
                db.session.commit()
                flash(f"学生档案'{student.full_name}'已删除")

    users = User.query.order_by(User.id.asc()).all()
    students = StudentProfile.query.filter_by(is_deleted=False).order_by(StudentProfile.id.asc()).all()
    return render_template("users.html", users=users, students=students)

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

# ---- AJAX: 设置/清除教师排课ID ----
@app.post("/api/users/<int:uid>/scheduler_teacher")
@login_required
@admin_required
def api_set_scheduler_teacher(uid):
    u = User.query.get_or_404(uid)
    data = request.get_json(silent=True) or {}
    value = data.get("scheduler_teacher_id")
    # 仅老师账号可设置
    if u.role != User.ROLE_TEACHER:
        return jsonify({"ok": False, "error": "not_teacher"}), 400
    if value in (None, "", "null"):
        u.scheduler_teacher_id = None
        db.session.commit()
        return jsonify({"ok": True, "scheduler_teacher_id": None})
    try:
        value_int = int(value)
    except Exception:
        return jsonify({"ok": False, "error": "invalid_id"}), 400
    # 防占用
    exists = User.query.filter(
        User.scheduler_teacher_id == value_int,
        User.id != u.id
    ).first()
    if exists:
        return jsonify({"ok": False, "error": "id_taken"}), 409
    u.scheduler_teacher_id = value_int
    db.session.commit()
    return jsonify({"ok": True, "scheduler_teacher_id": value_int})

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
    """
    DEPRECATED: Redirects to /tasks page.
    Material bank selection has been integrated into the main tasks page.
    """
    if current_user.role not in [User.ROLE_TEACHER, User.ROLE_ASSISTANT, User.ROLE_ADMIN]:
        flash("权限不足", "error")
        return redirect(url_for("index"))
    
    flash("任务管理已迁移到新页面", "info")
    return redirect(url_for("tasks_page"))


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
    def _collect_stats(range_start: date, range_end: date):
        items = (
            PlanItem.query.join(StudyPlan)
            .filter(
                StudyPlan.student_id == student.id,
                StudyPlan.plan_date >= range_start,
                StudyPlan.plan_date <= range_end,
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
            if item.review_status
            in (
                PlanItem.REVIEW_APPROVED,
                PlanItem.REVIEW_PARTIAL,
                PlanItem.REVIEW_REJECTED,
            )
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
            module_breakdown[item.module]["actual"] += int(
                (item.actual_seconds or 0) / 60
            )
            daily[item.plan.plan_date].append(item)

        completion_rate = (
            round(reviewed_items * 100.0 / total_items, 1) if total_items else 0.0
        )

        return {
            "items": items,
            "daily": daily,
            "planned_total": planned_total,
            "actual_total": actual_total,
            "manual_total": manual_total,
            "module_breakdown": module_breakdown,
            "completion_rate": completion_rate,
            "reviewed_items": reviewed_items,
            "total_items": total_items,
        }

    # Current week stats
    cur = _collect_stats(start_date, end_date)

    # Previous period for comparison
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    prev = _collect_stats(prev_start, prev_end)

    score_records = (
        ScoreRecord.query.filter(
            ScoreRecord.student_id == student.id,
            ScoreRecord.is_deleted.is_(False),
        )
        .order_by(ScoreRecord.taken_on.desc())
        .limit(5)
        .all()
    )

    def delta(cur_val: float, prev_val: float) -> float:
        return round(cur_val - prev_val, 1)

    module_sorted = sorted(
        cur["module_breakdown"].items(),
        key=lambda kv: kv[1]["actual"],
        reverse=True,
    )

    # Highlights / risks heuristic
    highlights = []
    risks = []
    if cur["completion_rate"] >= 85:
        highlights.append("完成率优秀，继续保持当前节奏。")
    elif cur["completion_rate"] >= 70:
        highlights.append("完成率较稳定，可适度提升难度或任务量。")
    else:
        risks.append("完成率偏低，需督促按时提交。")

    if module_sorted:
        top_mod, top_data = module_sorted[0]
        highlights.append(f"{top_mod}投入最多（实际 {top_data['actual']} 分）")

    if cur["actual_total"] < cur["planned_total"] * 0.6:
        risks.append("实际用时明显低于计划，建议查原因或调整计划。")

    # Sample evidences (up to 3)
    sample_evidences = []
    for item in cur["items"]:
        evs = [
            ev
            for ev in getattr(item, "evidences", []) or []
            if not getattr(ev, "is_deleted", False)
        ]
        if not evs:
            continue
        for ev in evs:
            sample_evidences.append(
                {
                    "task": item.task_name,
                    "module": item.module,
                    "url": ev.storage_path,
                    "type": ev.file_type or "file",
                }
            )
            if len(sample_evidences) >= 3:
                break
        if len(sample_evidences) >= 3:
            break

    # Classification summary
    classification = [
        {"module": mod, "planned": data["planned"], "actual": data["actual"]}
        for mod, data in module_sorted
    ]

    return {
        "student": student,
        "start_date": start_date,
        "end_date": end_date,
        "items": cur["items"],
        "daily_items": dict(sorted(cur["daily"].items())),
        "planned_minutes_total": cur["planned_total"],
        "actual_minutes_total": round(cur["actual_total"] / 60),
        "manual_minutes_total": round(cur["manual_total"] / 60),
        "completion_rate": cur["completion_rate"],
        "module_breakdown": dict(cur["module_breakdown"]),
        "reviewed_items": cur["reviewed_items"],
        "total_items": cur["total_items"],
        "comparison": {
            "completion_delta": delta(cur["completion_rate"], prev["completion_rate"]),
            "actual_delta": delta(
                round(cur["actual_total"] / 60, 1),
                round(prev["actual_total"] / 60, 1),
            ),
            "planned_delta": delta(
                round(cur["planned_total"], 1), round(prev["planned_total"], 1)
            ),
        },
        "highlights": highlights,
        "risks": risks,
        "sample_evidences": sample_evidences,
        "classification": classification,
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
        material_id = request.form.get("material_id")
        question_ids_raw = (request.form.get("question_ids") or "").strip()
        question_ids = question_ids_raw if question_ids_raw else None
        
        # 如果选择了材料，自动填充描述
        material_data = None
        dictation_book_data = None
        
        if material_id:
            from models import MaterialBank, DictationBook
            
            if material_id.startswith("dictation-"):
                 # It's a dictation book
                 book_id = int(material_id.split("-")[1])
                 dictation_book_data = DictationBook.query.get(book_id)
                 if dictation_book_data and not detail:
                     detail = dictation_book_data.title
                 question_ids = None
            else:
                # It's a standard material
                material_data = MaterialBank.query.get(int(material_id))
                if material_data and not detail:
                    detail = material_data.title
                if not material_data or material_data.type not in {"speaking_part1", "speaking_part2", "speaking_part2_3"}:
                    question_ids = None
        
        # Validate: need either category or material_id
        if not student:
            flash("请填写学生姓名")
        elif not category and not material_id:
            flash("请选择任务类别或材料")
        elif not detail:
            flash("请填写任务描述")
        else:
            # Set grading mode based on material selection
            grading_mode = "image"
            if material_id:
                grading_mode = "material"
                if not category:
                    category = "材料练习"
            
            dictation_word_start = request.form.get("dictation_word_start")
            dictation_word_end = request.form.get("dictation_word_end")

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
                material_id=int(material_id) if material_id and not material_id.startswith("dictation-") else None,
                question_ids=question_ids,
                dictation_book_id=int(material_id.split("-")[1]) if material_id and material_id.startswith("dictation-") else None,
                dictation_word_start=int(dictation_word_start) if dictation_word_start else 1,
                dictation_word_end=int(dictation_word_end) if dictation_word_end else None,
                grading_mode=grading_mode,
            )
            db.session.add(t)
            db.session.commit()
            # Try sending subscription notification if openid exists
            student_profile = StudentProfile.query.filter_by(full_name=student, is_deleted=False).first()
            if student_profile and student_profile.user and student_profile.user.wechat_openid:
                template_id = current_app.config.get("WECHAT_TASK_TEMPLATE_ID", "GElWxP8srvY_TwH-h69q4XcmgLyNZBsvjp6rSt8dhUU")
                data = {
                    "thing1": {"value": detail[:20]},
                    "time2": {"value": f"{d} 08:00"},
                    "time3": {"value": f"{d} 23:59"},
                    "thing4": {"value": "学习任务"}
                }
                try:
                    send_subscribe_message(student_profile.user.wechat_openid, template_id, data)
                except Exception as exc:
                    current_app.logger.warning("Failed to send subscribe message: %s", exc)
            flash("已添加")
            return redirect(url_for("tasks_page"))
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
    # Query tasks within the date range
    query = Task.query.filter(Task.date >= start_date.isoformat())
    
    # Filter by student_name if provided
    filter_student = request.args.get("student_name")
    if filter_student:
        query = query.filter(Task.student_name == filter_student)
        
    items = query.order_by(Task.date.desc(), Task.id.desc()).all()
    
    # [NEW] Pre-fetch active sessions for the current user
    active_sessions = StudySession.query.filter(
        StudySession.created_by == current_user.id,
        StudySession.ended_at.is_(None),
        StudySession.task_id.in_([t.id for t in items])
    ).all()
    active_session_map = {s.task_id: s for s in active_sessions}

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
        
        # Check for active session
        sess = active_session_map.get(t.id)
        current_session_id = sess.id if sess else None
        current_session_start = sess.started_at.isoformat() + "Z" if sess else None

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
            "session_id": current_session_id,
            "session_start": current_session_start,
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
    
    # 获取所有材料用于材料库选择
    from models import MaterialBank, Question
    materials_query = MaterialBank.query.filter_by(is_deleted=False, is_active=True).order_by(MaterialBank.created_at.desc()).all()
    all_materials = []
    for m in materials_query:
        question_count = Question.query.filter_by(material_id=m.id).count()
        all_materials.append({
            "id": m.id,
            "title": m.title,
            "type": m.type,
            "type": m.type,
            "question_count": f"{question_count}题"
        })

    # Add Dictation Books to material dropdown
    from models import DictationBook
    dictation_books = DictationBook.query.filter_by(is_deleted=False, is_active=True).order_by(DictationBook.created_at.desc()).all()
    for book in dictation_books:
        all_materials.append({
            "id": f"dictation-{book.id}",  # Special ID format to distinguish
            "title": book.title,
            "type": "听写词库",
            "question_count": f"{book.word_count}词"
        })

    # Dictation range hints: latest assigned range per student & dictation book
    dictation_range_hints = {}
    dictation_tasks = (
        Task.query.filter(Task.dictation_book_id.isnot(None))
        .order_by(Task.id.desc())
        .all()
    )
    for t in dictation_tasks:
        student_key = (t.student_name or "").strip()
        if not student_key or not t.dictation_book_id:
            continue
        student_map = dictation_range_hints.setdefault(student_key, {})
        book_key = str(t.dictation_book_id)
        if book_key in student_map:
            continue
        start_val = int(t.dictation_word_start or 1)
        end_val = int(t.dictation_word_end) if t.dictation_word_end else None
        student_map[book_key] = {
            "start": start_val,
            "end": end_val,
            "next_start": (end_val + 1) if end_val else None,
            "last_date": t.date,
        }

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
        all_materials=all_materials,
        pending_reviews=pending_reviews,
        dictation_range_hints=dictation_range_hints,
    )

# ---- Grading Interface ----

@app.route("/teacher/grading")
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def grading_list():
    # List tasks that are submitted by students but not yet marked as done
    tasks = Task.query.filter(
        Task.student_submitted == True,
        Task.status != 'done'
    ).order_by(Task.submitted_at.desc()).all()
    
    return render_template("teacher/grading_list.html", tasks=tasks)

@app.route("/teacher/grading/<int:task_id>")
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def grading_detail(task_id):
    task = Task.query.get_or_404(task_id)
    
    # Parse evidence photos
    evidence_photos = []
    if task.evidence_photos:
        try:
            evidence_photos = json.loads(task.evidence_photos)
        except:
            evidence_photos = []
            
    return render_template(
        "teacher/grading_detail.html", 
        task=task,
        evidence_photos=evidence_photos
    )

@app.route("/teacher/grading/<int:task_id>/submit", methods=["POST"])
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def grading_submit(task_id):
    task = Task.query.get_or_404(task_id)
    
    accuracy = request.form.get("accuracy")
    completion_rate = request.form.get("completion_rate")
    feedback_text = request.form.get("feedback_text")
    
    if accuracy:
        try:
            task.accuracy = float(accuracy)
        except ValueError:
            pass
    
    if completion_rate:
        try:
            task.completion_rate = float(completion_rate)
        except ValueError:
            pass
        
    if feedback_text:
        task.feedback_text = feedback_text
        
    # Mark as done
    task.status = "done"
    
    db.session.commit()
    
    flash("评分已提交", "success")
    return redirect(url_for("grading_list"))


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


# ---- 批改任务页面和API ----
@app.route("/tasks/<int:tid>/review")
@login_required
def review_task_page(tid):
    """批改任务页面"""
    # 权限检查：只有老师、助教、管理员可以批改
    if current_user.role not in ["teacher", "assistant", "admin"]:
        flash("您没有权限访问此页面", "error")
        return redirect(url_for("index"))
    
    task = Task.query.get_or_404(tid)
    evidence_photos = []
    if task.evidence_photos:
        try:
            import json
            evidence_photos = json.loads(task.evidence_photos)
        except:
            pass
    return render_template("review_task.html", task=task, evidence_photos=evidence_photos)


@app.post("/api/tasks/<int:tid>/review")
@login_required
def api_review_task(tid):
    """提交批改（图片+音频+文本）"""
    # 权限检查：只有老师、助教、管理员可以批改
    if current_user.role not in ["teacher", "assistant", "admin"]:
        return jsonify({"ok": False, "error": "no_permission"}), 403
    
    task = Task.query.get_or_404(tid)
    
    # 1. Handle Image Upload (Annotated)
    if "feedback_image" in request.files:
        f = request.files["feedback_image"]
        if f and f.filename:
            filename = f"feedback_img_{tid}_{uuid.uuid4().hex}.png"
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            f.save(path)
            task.feedback_image = f"/uploads/{filename}"
            
    # 2. Handle Audio Upload
    if "feedback_audio" in request.files:
        f = request.files["feedback_audio"]
        if f and f.filename:
            # Save original (likely webm)
            raw_filename = f"feedback_audio_{tid}_{uuid.uuid4().hex}.webm"
            raw_path = os.path.join(app.config["UPLOAD_FOLDER"], raw_filename)
            f.save(raw_path)
            
            # Convert to MP3 using ffmpeg
            mp3_filename = raw_filename.replace(".webm", ".mp3")
            mp3_path = os.path.join(app.config["UPLOAD_FOLDER"], mp3_filename)
            
            try:
                subprocess.run(
                    ["ffmpeg", "-i", raw_path, "-acodec", "libmp3lame", "-y", mp3_path],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                task.feedback_audio = f"/uploads/{mp3_filename}"
                # Clean up webm file
                os.remove(raw_path)
            except Exception as e:
                current_app.logger.error(f"Audio conversion failed: {e}")

    # 3. Update Text Fields
    data = request.form
    if "accuracy" in data:
        try:
            task.accuracy = float(data["accuracy"])
        except:
            pass
    if "completion_rate" in data:
        try:
            task.completion_rate = float(data["completion_rate"])
        except:
            pass
    if "note" in data:
        task.note = data["note"]
        
    task.status = "done"
    db.session.commit()
    
    return jsonify({"ok": True})


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


def _available_stage_report_students():
    return (
        StudentProfile.query.filter(StudentProfile.is_deleted.is_(False))
        .order_by(StudentProfile.full_name.asc())
        .all()
    )


def _parse_stage_report_filters(students):
    today = date.today()
    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    start_date = _safe_report_date(start_raw)
    end_date = _safe_report_date(end_raw)

    if not end_date:
        end_date = today
    if not start_date:
        start_date = end_date - timedelta(days=59)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    selected_student_id = request.args.get("student_id", type=int)
    student_ids = {student.id for student in students}
    if selected_student_id not in student_ids:
        selected_student_id = students[0].id if students else None

    return {
        "student_id": selected_student_id,
        "start": start_date,
        "end": end_date,
        "start_str": start_date.isoformat(),
        "end_str": end_date.isoformat(),
    }


def _mastery_label(score_value: float) -> str:
    if score_value >= 0.85:
        return "掌握较好"
    if score_value >= 0.65:
        return "基本掌握"
    return "需重点提升"


def _build_stage_report_payload(student: StudentProfile, start_date: date, end_date: date):
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
    legacy_tasks = []
    if not items and student and student.full_name:
        legacy_tasks = (
            Task.query.filter(
                Task.student_name == student.full_name,
                Task.date >= start_date.isoformat(),
                Task.date <= end_date.isoformat(),
            )
            .order_by(Task.date.asc(), Task.id.asc())
            .all()
        )

    module_map = defaultdict(
        lambda: {
            "planned_minutes": 0,
            "actual_minutes": 0,
            "approved": 0,
            "partial": 0,
            "rejected": 0,
            "pending": 0,
            "total": 0,
            "contents": [],
            "content_seen": set(),
            "mastery_sum": 0.0,
            "mastery_count": 0,
        }
    )

    if items:
        for item in items:
            module = (item.module or "").strip() or "未分类"
            row = module_map[module]
            row["total"] += 1
            row["planned_minutes"] += int(item.planned_minutes or 0)
            row["actual_minutes"] += int((item.actual_seconds or 0) / 60) + int(item.manual_minutes or 0)

            review_status = item.review_status or PlanItem.REVIEW_PENDING
            mastery_value = 0.35
            if review_status == PlanItem.REVIEW_APPROVED:
                row["approved"] += 1
                mastery_value = 1.0
            elif review_status == PlanItem.REVIEW_PARTIAL:
                row["partial"] += 1
                mastery_value = 0.65
            elif review_status == PlanItem.REVIEW_REJECTED:
                row["rejected"] += 1
                mastery_value = 0.2
            else:
                row["pending"] += 1

            row["mastery_sum"] += mastery_value
            row["mastery_count"] += 1

            content_name = (item.custom_title or item.task_name or "").strip()
            if (
                content_name
                and content_name not in row["content_seen"]
                and len(row["contents"]) < 8
            ):
                row["contents"].append(content_name)
                row["content_seen"].add(content_name)
    else:
        for task in legacy_tasks:
            raw_category = (task.category or "").strip() or "未分类"
            parts = [part for part in raw_category.split("-") if part]
            module = parts[1] if len(parts) >= 2 else parts[0]
            row = module_map[module]
            row["total"] += 1
            row["planned_minutes"] += int(task.planned_minutes or 0)
            row["actual_minutes"] += int((task.actual_seconds or 0) / 60)

            task_status = (task.status or "pending").lower()
            status_value = 0.2
            if task_status == "done":
                row["approved"] += 1
                status_value = 0.85
            elif task_status == "progress" or task_status == "in_progress":
                row["partial"] += 1
                status_value = 0.55
            else:
                row["pending"] += 1

            accuracy_value = float(task.accuracy or 0.0)
            if accuracy_value > 0:
                status_value = max(status_value, min(1.0, accuracy_value / 100.0))
            row["mastery_sum"] += status_value
            row["mastery_count"] += 1

            content_name = (task.detail or raw_category).strip()
            if (
                content_name
                and content_name not in row["content_seen"]
                and len(row["contents"]) < 8
            ):
                row["contents"].append(content_name)
                row["content_seen"].add(content_name)

    subject_rows = []
    for module, row in module_map.items():
        total = row["total"]
        reviewed = row["approved"] + row["partial"] + row["rejected"]
        mastery_score = (row["mastery_sum"] / row["mastery_count"]) if row["mastery_count"] else 0.0
        review_rate = round(reviewed * 100.0 / total, 1) if total else 0.0
        execution_rate = (
            round(row["actual_minutes"] * 100.0 / row["planned_minutes"], 1)
            if row["planned_minutes"] > 0
            else 0.0
        )
        mastery_text = _mastery_label(mastery_score)
        content_text = "、".join(row["contents"]) if row["contents"] else "暂无任务记录"
        if mastery_score >= 0.85:
            teacher_comment = "任务完成质量稳定，可进入更高难度训练。"
        elif mastery_score >= 0.65:
            teacher_comment = "已具备基础能力，建议通过限时训练提升稳定性。"
        else:
            teacher_comment = "建议先补基础再提速，优先解决高频错误。"

        subject_rows.append(
            {
                "module": module,
                "content_text": content_text,
                "planned_minutes": row["planned_minutes"],
                "actual_minutes": row["actual_minutes"],
                "review_rate": review_rate,
                "execution_rate": execution_rate,
                "mastery_score": round(mastery_score * 100, 1),
                "mastery_label": mastery_text,
                "teacher_comment": teacher_comment,
            }
        )

    subject_rows.sort(key=lambda entry: entry["planned_minutes"], reverse=True)

    if items:
        total_items = len(items)
        reviewed_items = sum(
            1
            for item in items
            if item.review_status
            in (PlanItem.REVIEW_APPROVED, PlanItem.REVIEW_PARTIAL, PlanItem.REVIEW_REJECTED)
        )
    else:
        total_items = len(legacy_tasks)
        reviewed_items = sum(
            1 for task in legacy_tasks if (task.status or "").lower() in {"done", "progress", "in_progress"}
        )
    planned_total = sum(row["planned_minutes"] for row in subject_rows)
    actual_total = sum(row["actual_minutes"] for row in subject_rows)
    stage_completion_rate = round(reviewed_items * 100.0 / total_items, 1) if total_items else 0.0
    avg_mastery = (
        round(sum(row["mastery_score"] for row in subject_rows) / len(subject_rows), 1)
        if subject_rows
        else 0.0
    )

    phase_score_records = (
        ScoreRecord.query.filter(
            ScoreRecord.student_id == student.id,
            ScoreRecord.is_deleted.is_(False),
            ScoreRecord.taken_on >= start_date,
            ScoreRecord.taken_on <= end_date,
        )
        .order_by(ScoreRecord.taken_on.desc())
        .all()
    )
    recent_score_records = (
        ScoreRecord.query.filter(
            ScoreRecord.student_id == student.id,
            ScoreRecord.is_deleted.is_(False),
        )
        .order_by(ScoreRecord.taken_on.desc())
        .limit(5)
        .all()
    )
    score_records = phase_score_records or recent_score_records
    score_scope_label = "阶段内模考/测评分数" if phase_score_records else "近期模考/测评分数（阶段内暂无）"

    ordered_for_estimate = sorted(
        [record for record in recent_score_records if record.total_score is not None],
        key=lambda record: record.taken_on,
    )
    latest_score = ordered_for_estimate[-1].total_score if ordered_for_estimate else None
    predicted_score = None
    prediction_basis = "暂无可用分数记录"
    if latest_score is not None:
        if len(ordered_for_estimate) >= 2:
            latest_delta = ordered_for_estimate[-1].total_score - ordered_for_estimate[-2].total_score
            predicted_score = round(ordered_for_estimate[-1].total_score + latest_delta * 0.5, 1)
            prediction_basis = "基于最近两次总分趋势做线性外推"
        else:
            predicted_score = round(ordered_for_estimate[-1].total_score, 1)
            prediction_basis = "仅有一次分数记录，预估分等于最近分数"

    weak_subjects = sorted(subject_rows, key=lambda row: row["mastery_score"])
    focus_points = []
    for row in weak_subjects[:2]:
        focus_points.append(
            f"{row['module']}：当前{row['mastery_label']}，建议围绕“{row['content_text'].split('、')[0]}”做专项强化。"
        )
    if not focus_points and subject_rows:
        focus_points.append(f"{subject_rows[0]['module']}：保持当前训练节奏，逐步提高题目难度。")
    if not focus_points:
        focus_points.append("当前阶段暂无任务记录，建议先制定分学科的周计划。")

    suggestions = []
    if stage_completion_rate < 70:
        suggestions.append("优先提高作业提交和审核通过率，建议固定每日提交时段。")
    if planned_total > 0 and actual_total < planned_total * 0.75:
        suggestions.append("实际学习时长偏低，建议每周增加 2-3 次限时训练。")
    if avg_mastery < 70:
        suggestions.append("先补薄弱知识点再做套题，避免无效刷题。")
    if not suggestions:
        suggestions.append("保持当前节奏，下一阶段重点放在稳定输出和错题复盘。")

    if total_items == 0:
        stage_overall_comment = "该阶段暂无学习任务数据，建议先补充阶段计划后再出具报告。"
    elif stage_completion_rate >= 85 and avg_mastery >= 75:
        stage_overall_comment = "该阶段执行度和掌握度整体良好，可在下一阶段提高难度并增加综合训练。"
    elif stage_completion_rate >= 70:
        stage_overall_comment = "该阶段整体达标，但学科表现存在差异，建议对薄弱模块做专项提分。"
    else:
        stage_overall_comment = "该阶段执行度偏低，建议先修复学习节奏与提交习惯，再推进冲分训练。"

    return {
        "student": student,
        "start_date": start_date,
        "end_date": end_date,
        "subject_rows": subject_rows,
        "score_records": score_records,
        "score_scope_label": score_scope_label,
        "total_items": total_items,
        "reviewed_items": reviewed_items,
        "planned_total": planned_total,
        "actual_total": actual_total,
        "stage_completion_rate": stage_completion_rate,
        "avg_mastery": avg_mastery,
        "latest_score": latest_score,
        "predicted_score": predicted_score,
        "prediction_basis": prediction_basis,
        "focus_points": focus_points,
        "suggestions": suggestions,
        "stage_overall_comment": stage_overall_comment,
    }


def _serialize_score_record(score: ScoreRecord) -> dict:
    return {
        "taken_on": score.taken_on.isoformat() if score.taken_on else "",
        "assessment_name": score.assessment_name,
        "total_score": score.total_score,
        "component_scores": score.component_scores or {},
        "notes": score.notes or "",
    }


def _build_stage_report_data(student: StudentProfile, start_date: date, end_date: date) -> dict:
    payload = _build_stage_report_payload(student, start_date, end_date)
    next_stage_plan_text = "\n".join(payload["focus_points"] + payload["suggestions"]).strip()
    return {
        "subject_rows": payload["subject_rows"],
        "score_scope_label": payload["score_scope_label"],
        "score_records": [_serialize_score_record(score) for score in payload["score_records"]],
        "total_items": payload["total_items"],
        "reviewed_items": payload["reviewed_items"],
        "planned_total": payload["planned_total"],
        "actual_total": payload["actual_total"],
        "stage_completion_rate": payload["stage_completion_rate"],
        "avg_mastery": payload["avg_mastery"],
        "latest_score": payload["latest_score"],
        "predicted_score": payload["predicted_score"],
        "prediction_basis": payload["prediction_basis"],
        "class_summary_text": "",
        "mock_review_rows": _default_mock_review_rows(),
        "next_stage_plan_text": next_stage_plan_text,
        "focus_points_text": "\n".join(payload["focus_points"]),
        "suggestions_text": "\n".join(payload["suggestions"]),
        "overall_comment": payload["stage_overall_comment"],
    }


def _stage_report_title(student: StudentProfile, start_date: date, end_date: date) -> str:
    return f"{student.full_name} 阶段学习报告 ({start_date.isoformat()} 至 {end_date.isoformat()})"


def _default_class_summary_rows(existing_rows=None):
    subjects = ["听力", "口语", "阅读", "写作"]
    existing_map = {}
    for row in existing_rows or []:
        subject = (row.get("subject") or "").strip()
        if subject:
            existing_map[subject] = row.get("summary") or ""
    return [{"subject": subject, "summary": existing_map.get(subject, "")} for subject in subjects]


def _default_mock_review_rows(existing_rows=None):
    subjects = ["听力", "口语", "阅读", "写作"]
    existing_map = {}
    for row in existing_rows or []:
        subject = (row.get("subject") or "").strip()
        if subject:
            existing_map[subject] = row

    rows = []
    for subject in subjects:
        found = existing_map.get(subject, {})
        rows.append(
            {
                "subject": subject,
                "accuracy_rate": (found.get("accuracy_rate") or "").strip()
                if isinstance(found.get("accuracy_rate"), str)
                else (str(found.get("accuracy_rate")) if found.get("accuracy_rate") is not None else ""),
                "mock_score": (found.get("mock_score") or "").strip()
                if isinstance(found.get("mock_score"), str)
                else (str(found.get("mock_score")) if found.get("mock_score") is not None else ""),
                "teacher_comment": (found.get("teacher_comment") or "").strip(),
            }
        )
    return rows


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

# ============================================================================
# Material Bank Web Routes
# ============================================================================

@app.route("/materials")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def materials_list():
    """Material bank list page."""
    return render_template("materials.html")


@app.route("/materials/create")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def materials_create():
    """Create new material."""
    return render_template("material_form.html")


@app.route("/materials/<int:material_id>")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def materials_view(material_id):
    """View material details."""
    from models import MaterialBank
    material = MaterialBank.query.filter_by(id=material_id, is_deleted=False).first_or_404()
    return render_template("material_view.html", material=material)


@app.route("/materials/<int:material_id>/edit")
@login_required
@role_required(User.ROLE_TEACHER, User.ROLE_ASSISTANT)
def materials_edit(material_id):
    """Edit material."""
    from models import MaterialBank, Question, QuestionOption
    import json
    
    material = MaterialBank.query.filter_by(id=material_id, is_deleted=False).first_or_404()
    
    # Fetch all questions for this material
    questions = Question.query.filter_by(material_id=material_id).order_by(Question.sequence).all()
    
    questions_data = []
    for q in questions:
        options = QuestionOption.query.filter_by(question_id=q.id).order_by(QuestionOption.option_key).all()
        questions_data.append({
            "sequence": q.sequence,
            "content": q.content,
            "question_type": q.question_type,
            "reference_answer": q.reference_answer,
            "hint": q.hint,
            "points": q.points,
            "options": [{"key": opt.option_key, "text": opt.option_text} for opt in options]
        })
    
    # Pass questions as JSON string to template
    questions_json = json.dumps(questions_data, ensure_ascii=False)
    
    return render_template("material_form.html", material=material, questions_json=questions_json)


# --- Course Plan Generator Routes ---

@app.route("/admin/course-plan")
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_COURSE_PLANNER)
def course_plan_list():
    plans = CoursePlan.query.filter_by(is_deleted=False).order_by(CoursePlan.created_at.desc()).all()
    return render_template("admin/course_plan_list.html", plans=plans)

@app.route("/admin/course-plan/create")
@app.route("/admin/course-plan/<int:plan_id>/edit")
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_COURSE_PLANNER)
def course_plan_create(plan_id=None):
    plan_data = None
    if plan_id:
        plan = CoursePlan.query.get_or_404(plan_id)
        plan_payload = dict(plan.plan_data or {})
        plan_payload["id"] = plan.id
        plan_data = json.dumps(plan_payload, ensure_ascii=False)
    return render_template("admin/course_plan_create.html", initial_data=plan_data)

@app.route("/api/course-plans", methods=["POST"])
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_COURSE_PLANNER)
def save_course_plan():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    plan_id = data.get("id")
    student_info = data.get("student", {})
    student_name = student_info.get("name")
    
    if not student_name:
        return jsonify({"error": "Student name is required"}), 400
        
    # Find or create student profile
    student_profile = StudentProfile.query.filter_by(full_name=student_name).first()
    if not student_profile:
        student_profile = StudentProfile(
            full_name=student_name,
            grade_level=student_info.get("currentGradeAndPlan", "")[:32], # Truncate if needed
            notes=f"Created via Course Plan Generator on {datetime.now().strftime('%Y-%m-%d')}"
        )
        db.session.add(student_profile)
        db.session.flush() # Get ID
        
    exam_type = (student_info.get("examType") or "IELTS").upper()
    exam_label = "托福" if exam_type.startswith("TOEFL") else "雅思"
    title = f"{student_name} - {exam_label}学习方案 ({datetime.now().strftime('%Y-%m-%d')})"

    # Update existing plan if id provided, else create new
    if plan_id:
        plan = CoursePlan.query.get(plan_id)
        if not plan:
            return jsonify({"error": "Plan not found"}), 404
        plan.student_id = student_profile.id
        plan.plan_data = data
        plan.title = title
    else:
        plan = CoursePlan(
            student_id=student_profile.id,
            created_by=current_user.id,
            plan_data=data,
            title=title
        )
        db.session.add(plan)
    
    db.session.commit()
    
    return jsonify({"ok": True, "id": plan.id})

@app.route("/api/course-plans/<int:plan_id>", methods=["DELETE"])
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER)
def delete_course_plan(plan_id):
    plan = CoursePlan.query.get_or_404(plan_id)
    plan.is_deleted = True
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/api/course-plans/<int:plan_id>/pdf")
@login_required
@role_required(User.ROLE_ADMIN, User.ROLE_TEACHER)
def export_course_plan_pdf(plan_id):
    plan = CoursePlan.query.get_or_404(plan_id)
    
    # Prepare data for template
    data = plan.plan_data
    student = data.get("student", {})
    phases = data.get("phases", [])
    pricing = data.get("pricing", [])
    exam_type = (student.get("examType") or "IELTS").upper()
    exam_label = "托福" if exam_type.startswith("TOEFL") else "雅思"
    
    # Calculate totals
    total_amount = sum(row.get("subtotal", 0) for row in pricing)
    discounted_total = sum(row.get("discountedSubtotal", row.get("subtotal", 0)) for row in pricing)
    final_total = data.get("discountedTotalOverride")
    has_override = final_total not in (None, "", "null")
    if not has_override:
        final_total = discounted_total
    try:
        final_total = float(final_total)
    except Exception:
        final_total = discounted_total
    
    has_discount = False
    for row in pricing:
        try:
            percent = float(row.get("discountPercent") or 0)
        except Exception:
            percent = 0
        try:
            subtotal = float(row.get("subtotal") or 0)
        except Exception:
            subtotal = 0
        try:
            if row.get("discountedSubtotal") is None:
                discounted_subtotal = subtotal
            else:
                discounted_subtotal = float(row.get("discountedSubtotal"))
        except Exception:
            discounted_subtotal = subtotal
        if percent > 0 or discounted_subtotal < subtotal:
            has_discount = True
            break
    show_discount_total = has_discount or has_override
    
    # Load and encode logo as base64
    import base64
    logo_path = os.path.join(app.static_folder, 'sagepath_logo.jpg')
    logo_base64 = ""
    try:
        with open(logo_path, 'rb') as f:
            logo_base64 = base64.b64encode(f.read()).decode('utf-8')
    except:
        pass  # If logo doesn't exist, template will handle gracefully
    
    html = render_template(
        "admin/course_plan_pdf.html",
        plan=plan,
        student=student,
        phases=phases,
        pricing=pricing,
        total_amount=total_amount,
        discounted_total=discounted_total,
        final_total=final_total,
        show_discount_total=show_discount_total,
        generated_at=datetime.now(),
        logo_base64=logo_base64,
        exam_label=exam_label,
    )
    
    css = CSS(string="""
        @page { size: A4; margin: 20mm; }
        body { font-family: "Noto Sans CJK SC", sans-serif; }
    """)
    
    pdf = HTML(string=html).write_pdf(stylesheets=[css])
    
    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    # Use URL encoding for Chinese characters in filename
    from urllib.parse import quote
    filename = quote(f"{plan.title}.pdf")
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
    return response


# --- Stage Report Routes ---

@app.route("/admin/stage-report")
@login_required
@stage_report_access_required
def stage_report_list():
    reports = (
        StageReport.query.filter(StageReport.is_deleted.is_(False))
        .options(joinedload(StageReport.student), joinedload(StageReport.creator))
        .order_by(StageReport.updated_at.desc())
        .all()
    )
    return render_template("admin/stage_report_list.html", reports=reports)


@app.route("/admin/stage-report/create", methods=["GET", "POST"])
@app.route("/admin/stage-report/<int:report_id>/edit", methods=["GET", "POST"])
@login_required
@stage_report_access_required
def stage_report_create(report_id=None):
    students = _available_stage_report_students()
    report = None
    if report_id is not None:
        report = StageReport.query.filter(
            StageReport.id == report_id,
            StageReport.is_deleted.is_(False),
        ).first_or_404()

    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        selected_student = StudentProfile.query.filter(
            StudentProfile.id == student_id,
            StudentProfile.is_deleted.is_(False),
        ).first()
        if not selected_student:
            flash("请选择有效学生。")
            return redirect(url_for("stage_report_list"))

        start_date = _safe_report_date((request.form.get("start_date") or "").strip())
        end_date = _safe_report_date((request.form.get("end_date") or "").strip())
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=59)
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        stage_data = _build_stage_report_data(selected_student, start_date, end_date)

        subject_rows = stage_data.get("subject_rows") or []
        for idx, row in enumerate(subject_rows):
            teacher_comment = (request.form.get(f"teacher_comment_{idx}") or "").strip()
            if teacher_comment:
                row["teacher_comment"] = teacher_comment
        stage_data["subject_rows"] = subject_rows

        stage_data["class_summary_text"] = (
            request.form.get("class_summary_text") or ""
        ).strip()

        mock_review_rows = []
        for idx, row in enumerate(_default_mock_review_rows()):
            mock_review_rows.append(
                {
                    "subject": row["subject"],
                    "accuracy_rate": (request.form.get(f"mock_accuracy_{idx}") or "").strip(),
                    "mock_score": (request.form.get(f"mock_score_{idx}") or "").strip(),
                    "teacher_comment": (request.form.get(f"mock_comment_{idx}") or "").strip(),
                }
            )
        stage_data["mock_review_rows"] = mock_review_rows
        stage_data["next_stage_plan_text"] = (
            request.form.get("next_stage_plan_text") or ""
        ).strip()

        stage_data["overall_comment"] = (request.form.get("overall_comment") or "").strip()
        # Legacy fields kept for compatibility with older exports/records.
        stage_data["focus_points_text"] = stage_data["next_stage_plan_text"]
        stage_data["suggestions_text"] = ""

        stage_data["visible_sections"] = {
            "overview": request.form.get("sec_overview") == "1",
            "subjects": request.form.get("sec_subjects") == "1",
            "class_summary": request.form.get("sec_class_summary") == "1",
            "mock_exam": request.form.get("sec_mock_exam") == "1",
            "next_plan": request.form.get("sec_next_plan") == "1",
        }

        title = (request.form.get("title") or "").strip()
        if not title:
            title = _stage_report_title(selected_student, start_date, end_date)

        if report:
            report.student_id = selected_student.id
            report.start_date = start_date
            report.end_date = end_date
            report.title = title
            report.report_data = stage_data
        else:
            report = StageReport(
                student_id=selected_student.id,
                created_by=current_user.id,
                start_date=start_date,
                end_date=end_date,
                title=title,
                report_data=stage_data,
            )
            db.session.add(report)

        db.session.commit()
        flash("阶段学习报告已保存。")
        return redirect(url_for("stage_report_create", report_id=report.id))

    if report:
        selected_student = report.student
        start_date = report.start_date
        end_date = report.end_date
        stage_data = dict(report.report_data or {})
    else:
        filters = _parse_stage_report_filters(students)
        selected_student = None
        if filters["student_id"] is not None:
            selected_student = next(
                (student for student in students if student.id == filters["student_id"]),
                None,
            )
        start_date = filters["start"]
        end_date = filters["end"]
        stage_data = (
            _build_stage_report_data(selected_student, start_date, end_date)
            if selected_student
            else {}
        )

    if stage_data.get("focus_points_text") is None:
        stage_data["focus_points_text"] = ""
    if stage_data.get("suggestions_text") is None:
        stage_data["suggestions_text"] = ""
    if stage_data.get("overall_comment") is None:
        stage_data["overall_comment"] = ""
    if stage_data.get("class_summary_text") is None:
        stage_data["class_summary_text"] = ""
    stage_data["mock_review_rows"] = _default_mock_review_rows(
        stage_data.get("mock_review_rows")
    )
    if stage_data.get("next_stage_plan_text") is None:
        legacy_combined = "\n".join(
            [value for value in [stage_data.get("focus_points_text"), stage_data.get("suggestions_text")] if value]
        ).strip()
        stage_data["next_stage_plan_text"] = legacy_combined

    if stage_data.get("class_summary_text") is None:
        legacy_rows = _default_class_summary_rows(stage_data.get("class_summary_rows"))
        stage_data["class_summary_text"] = "\n".join(
            f"{row['subject']}：{row['summary']}" for row in legacy_rows if (row.get("summary") or "").strip()
        ).strip()
    stage_data["mock_review_rows"] = _default_mock_review_rows(
        stage_data.get("mock_review_rows")
    )

    title_value = report.title if report else _stage_report_title(selected_student, start_date, end_date) if selected_student else "阶段学习报告"

    return render_template(
        "admin/stage_report_create.html",
        report=report,
        students=students,
        selected_student=selected_student,
        start_date=start_date,
        end_date=end_date,
        stage_data=stage_data,
        title_value=title_value,
    )


@app.post("/admin/stage-report/<int:report_id>/delete")
@login_required
@stage_report_access_required
def delete_stage_report(report_id):
    report = StageReport.query.filter(
        StageReport.id == report_id,
        StageReport.is_deleted.is_(False),
    ).first_or_404()
    report.is_deleted = True
    db.session.commit()
    flash("阶段学习报告已删除。")
    return redirect(url_for("stage_report_list"))


@app.route("/api/stage-reports/<int:report_id>/pdf")
@login_required
@stage_report_access_required
def export_stage_report_pdf(report_id):
    if HTML is None or CSS is None:
        return jsonify({"ok": False, "error": "weasyprint_not_installed"}), 500

    report = StageReport.query.filter(
        StageReport.id == report_id,
        StageReport.is_deleted.is_(False),
    ).first_or_404()

    data = report.report_data or {}
    subject_rows = data.get("subject_rows") or []
    class_summary_text = (data.get("class_summary_text") or "").strip()
    if not class_summary_text:
        legacy_rows = _default_class_summary_rows(data.get("class_summary_rows"))
        class_summary_text = "\n".join(
            f"{row['subject']}：{row['summary']}" for row in legacy_rows if (row.get("summary") or "").strip()
        ).strip()
    mock_review_rows = _default_mock_review_rows(data.get("mock_review_rows"))
    next_stage_plan_text = (data.get("next_stage_plan_text") or "").strip()
    if not next_stage_plan_text:
        next_stage_plan_text = "\n".join(
            [value for value in [data.get("focus_points_text"), data.get("suggestions_text")] if value]
        ).strip()

    import base64

    logo_path = os.path.join(app.static_folder, "sagepath_logo.jpg")
    logo_base64 = ""
    try:
        with open(logo_path, "rb") as f:
            logo_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        logo_base64 = ""

    visible_sections = data.get("visible_sections", {})

    html = render_template(
        "admin/stage_report_pdf.html",
        report=report,
        student=report.student,
        data=data,
        subject_rows=subject_rows,
        class_summary_text=class_summary_text,
        mock_review_rows=mock_review_rows,
        next_stage_plan_text=next_stage_plan_text,
        generated_at=datetime.now(),
        logo_base64=logo_base64,
        secs=visible_sections,
    )

    css = CSS(string="""
        @page { size: A4; margin: 18mm; }
        body { font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif; }
    """)
    pdf = HTML(string=html).write_pdf(stylesheets=[css])

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    from urllib.parse import quote

    filename = quote(f"{report.title or '阶段学习报告'}.pdf")
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
