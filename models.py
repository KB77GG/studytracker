from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class TimestampMixin:
    """Add created_at / updated_at columns to track record lifecycle."""

    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        index=True,
    )


class SoftDeleteMixin:
    """Optional soft-delete flag for business records."""

    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)


class User(db.Model, UserMixin, TimestampMixin):
    """Unified user table with role-based access."""

    __tablename__ = "user"

    ROLE_ADMIN = "admin"
    ROLE_TEACHER = "teacher"
    ROLE_ASSISTANT = "assistant"
    ROLE_STUDENT = "student"
    ROLE_PARENT = "parent"
    ROLE_COURSE_PLANNER = "course_planner"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    display_name = db.Column(db.String(64))
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default=ROLE_ASSISTANT, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    auth_token_hash = db.Column(db.String(128))
    wechat_openid = db.Column(db.String(64), index=True)
    wechat_unionid = db.Column(db.String(64), index=True)
    wechat_nickname = db.Column(db.String(64))
    scheduler_teacher_id = db.Column(db.Integer, unique=True, index=True)

    # Relationships populated further down the file (e.g., student_profile, plans).

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self) -> str:
        return str(self.id)

    def set_api_token(self, token_hash: str) -> None:
        self.auth_token_hash = token_hash
        self.token_issued_at = datetime.utcnow()

    def clear_api_token(self) -> None:
        self.auth_token_hash = None
        self.token_issued_at = None


class StudentProfile(db.Model, TimestampMixin, SoftDeleteMixin):
    """Master data for each student; optionally linked to a user login."""

    __tablename__ = "student_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
    full_name = db.Column(db.String(64), nullable=False, index=True)
    nickname = db.Column(db.String(64))
    grade_level = db.Column(db.String(32))
    exam_target = db.Column(db.String(32))  # 基础 / 雅思 / 托福 / 其他
    guardian_name = db.Column(db.String(64))
    guardian_contact = db.Column(db.String(64))
    guardian_view_token = db.Column(db.String(64), unique=True, index=True)
    notes = db.Column(db.Text)
    primary_teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    primary_parent_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    
    wechat_openid = db.Column(db.String(64), index=True)
    scheduler_student_id = db.Column(db.Integer, unique=True, index=True)

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("student_profile", uselist=False),
    )
    primary_teacher = db.relationship(
        "User",
        foreign_keys=[primary_teacher_id],
        backref=db.backref("primary_students", lazy="dynamic"),
    )
    primary_parent = db.relationship(
        "User",
        foreign_keys=[primary_parent_id],
        backref=db.backref("linked_children", lazy="dynamic"),
    )


class ParentStudentLink(db.Model, TimestampMixin):
    """Link between a parent (User) and a student (by name string)."""
    
    __tablename__ = "parent_student_link"
    
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    student_name = db.Column(db.String(64), nullable=False)
    relation = db.Column(db.String(32))  # 父亲/母亲/其他
    is_active = db.Column(db.Boolean, default=True)
    
    parent = db.relationship(
        "User",
        backref=db.backref("student_links_as_parent", lazy="dynamic")
    )
    
    __table_args__ = (
        db.UniqueConstraint("parent_id", "student_name", name="uq_parent_student"),
    )


class TeacherStudentLink(db.Model, TimestampMixin):
    """Junction table to manage teacher → student assignments."""

    __tablename__ = "teacher_student_link"

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student_profile.id"), nullable=False
    )
    role = db.Column(db.String(32), default="coach", nullable=False)  # coach / reviewer
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    teacher = db.relationship(
        "User",
        foreign_keys=[teacher_id],
        backref=db.backref("student_links", lazy="dynamic"),
    )
    student = db.relationship(
        "StudentProfile",
        backref=db.backref("teacher_links", lazy="dynamic", cascade="all, delete-orphan"),
    )
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint("teacher_id", "student_id", name="uq_teacher_student"),
    )


class TaskCatalog(db.Model, TimestampMixin, SoftDeleteMixin):
    """
    Reference list of granular tasks (三级分类：考试体系 / 模块 / 具体任务).
    Used by计划和模板，确保统计口径统一。
    """

    __tablename__ = "task_catalog"

    id = db.Column(db.Integer, primary_key=True)
    exam_system = db.Column(db.String(32), nullable=False, index=True)  # 基础/雅思/托福...
    module = db.Column(db.String(32), nullable=False, index=True)  # 听力/阅读/口语/写作/词汇/语法
    task_name = db.Column(db.String(64), nullable=False, index=True)
    description = db.Column(db.Text)
    default_minutes = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    creator = db.relationship("User", backref=db.backref("created_tasks", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint(
            "exam_system",
            "module",
            "task_name",
            name="uq_task_catalog_unique",
        ),
    )


class PlanTemplate(db.Model, TimestampMixin, SoftDeleteMixin):
    """Reusable task bundle (e.g., 雅思听力日常包)."""

    __tablename__ = "plan_template"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    default_recurrence = db.Column(
        db.String(32), default="once", nullable=False
    )  # once / daily / weekdays / custom

    creator = db.relationship(
        "User", backref=db.backref("plan_templates", lazy="dynamic")
    )


class PlanTemplateItem(db.Model, TimestampMixin, SoftDeleteMixin):
    """Items under a plan template, preserving order and defaults."""

    __tablename__ = "plan_template_item"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("plan_template.id"), nullable=False)
    catalog_id = db.Column(db.Integer, db.ForeignKey("task_catalog.id"))
    exam_system = db.Column(db.String(32), nullable=False)
    module = db.Column(db.String(32), nullable=False)
    task_name = db.Column(db.String(64), nullable=False)
    instructions = db.Column(db.Text)
    default_minutes = db.Column(db.Integer, default=0, nullable=False)
    order_index = db.Column(db.Integer, default=0, nullable=False)

    template = db.relationship(
        "PlanTemplate",
        backref=db.backref(
            "items", lazy="dynamic", cascade="all, delete-orphan", order_by="PlanTemplateItem.order_index"
        ),
    )
    catalog = db.relationship("TaskCatalog", backref="template_items")


class StudyPlan(db.Model, TimestampMixin, SoftDeleteMixin):
    """A daily plan for a student, authored by a teacher."""

    __tablename__ = "study_plan"

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_LOCKED = "locked"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    plan_date = db.Column(db.Date, nullable=False, index=True)
    window_start = db.Column(db.Time)
    window_end = db.Column(db.Time)
    status = db.Column(db.String(20), default=STATUS_DRAFT, nullable=False, index=True)
    notes = db.Column(db.Text)
    template_id = db.Column(db.Integer, db.ForeignKey("plan_template.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    published_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    published_at = db.Column(db.DateTime)
    finalized_at = db.Column(db.DateTime)

    student = db.relationship(
        "StudentProfile",
        backref=db.backref("study_plans", lazy="dynamic", cascade="all, delete-orphan"),
    )
    template = db.relationship("PlanTemplate", backref="instantiated_plans")
    creator = db.relationship("User", foreign_keys=[created_by], backref="authored_plans")
    publisher = db.relationship("User", foreign_keys=[published_by])

    __table_args__ = (
        db.UniqueConstraint("student_id", "plan_date", name="uq_plan_student_date"),
    )


class PlanItem(db.Model, TimestampMixin, SoftDeleteMixin):
    """Specific task scheduled within a study plan."""

    __tablename__ = "plan_item"

    EVIDENCE_OPTIONAL = "optional"
    EVIDENCE_TEXT = "text"
    EVIDENCE_IMAGE = "image"
    EVIDENCE_AUDIO = "audio"
    EVIDENCE_REQUIRED = "required"

    REVIEW_PENDING = "pending"
    REVIEW_APPROVED = "approved"
    REVIEW_PARTIAL = "partial"
    REVIEW_REJECTED = "rejected"

    STUDENT_PENDING = "pending"
    STUDENT_IN_PROGRESS = "in_progress"
    STUDENT_SUBMITTED = "submitted"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("study_plan.id"), nullable=False, index=True)
    template_item_id = db.Column(db.Integer, db.ForeignKey("plan_template_item.id"))
    catalog_id = db.Column(db.Integer, db.ForeignKey("task_catalog.id"))

    exam_system = db.Column(db.String(32), nullable=False, index=True)
    module = db.Column(db.String(32), nullable=False, index=True)
    task_name = db.Column(db.String(64), nullable=False)
    custom_title = db.Column(db.String(128))
    instructions = db.Column(db.Text)
    order_index = db.Column(db.Integer, default=0, nullable=False)

    planned_minutes = db.Column(db.Integer, default=0, nullable=False)
    planned_start = db.Column(db.Time)
    planned_end = db.Column(db.Time)

    student_status = db.Column(db.String(20), default=STUDENT_PENDING, nullable=False)
    student_comment = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime)

    actual_seconds = db.Column(db.Integer, default=0, nullable=False)
    manual_minutes = db.Column(db.Integer, default=0, nullable=False)

    review_status = db.Column(db.String(20), default=REVIEW_PENDING, nullable=False, index=True)
    review_comment = db.Column(db.String(255))
    review_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    review_at = db.Column(db.DateTime)
    locked = db.Column(db.Boolean, default=False, nullable=False)
    student_reset_count = db.Column(db.Integer, default=0, nullable=False)
    evidence_policy = db.Column(
        db.String(20),
        default=EVIDENCE_OPTIONAL,
        nullable=False,
        index=True,
        doc="optional/text/image/audio/required（任意类型）",
    )

    plan = db.relationship(
        "StudyPlan",
        backref=db.backref("items", lazy="selectin", cascade="all, delete-orphan"),
    )
    template_item = db.relationship("PlanTemplateItem")
    catalog = db.relationship("TaskCatalog")
    reviewer = db.relationship("User", foreign_keys=[review_by])


class PlanItemSession(db.Model, TimestampMixin, SoftDeleteMixin):
    """Timer segments recorded by students, later rolled up to PlanItem.actual_seconds."""

    __tablename__ = "plan_item_session"

    id = db.Column(db.Integer, primary_key=True)
    plan_item_id = db.Column(db.Integer, db.ForeignKey("plan_item.id"), nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer, default=0, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    source = db.Column(db.String(32), default="manual", nullable=False)  # manual / timer
    device_info = db.Column(db.String(128))

    plan_item = db.relationship(
        "PlanItem",
        backref=db.backref("sessions", lazy="selectin", cascade="all, delete-orphan"),
    )
    creator = db.relationship("User", backref=db.backref("plan_sessions", lazy="dynamic"))

    def close(self, ended_at: datetime) -> None:
        if self.ended_at:
            return
        self.ended_at = ended_at
        self.duration_seconds = max(
            0, int((self.ended_at - self.started_at).total_seconds())
        )


class PlanEvidence(db.Model, TimestampMixin, SoftDeleteMixin):
    """Evidence uploaded by students (photos, audio, documents)."""

    __tablename__ = "plan_evidence"

    id = db.Column(db.Integer, primary_key=True)
    plan_item_id = db.Column(db.Integer, db.ForeignKey("plan_item.id"), nullable=False, index=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)  # image / audio / doc / other
    storage_path = db.Column(db.String(256), nullable=False)
    preview_path = db.Column(db.String(256))
    original_filename = db.Column(db.String(128))
    file_size = db.Column(db.Integer, default=0, nullable=False)
    note = db.Column(db.String(255))
    sha256 = db.Column(db.String(64))
    text_content = db.Column(db.Text)

    plan_item = db.relationship(
        "PlanItem",
        backref=db.backref("evidences", lazy="selectin", cascade="all, delete-orphan"),
    )
    uploader = db.relationship("User", backref=db.backref("uploaded_evidence", lazy="dynamic"))


class PlanReviewLog(db.Model, TimestampMixin):
    """Audit trail for teacher reviews (通过 / 部分 / 未完成)."""

    __tablename__ = "plan_review_log"

    id = db.Column(db.Integer, primary_key=True)
    plan_item_id = db.Column(db.Integer, db.ForeignKey("plan_item.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    from_status = db.Column(db.String(20))
    to_status = db.Column(db.String(20), nullable=False)
    comment = db.Column(db.String(255))
    decided_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    originated_from = db.Column(db.String(32), default="manual", nullable=False)  # manual / bulk / api

    plan_item = db.relationship(
        "PlanItem",
        backref=db.backref("review_logs", lazy="selectin", cascade="all, delete-orphan"),
    )
    reviewer = db.relationship("User", backref=db.backref("review_logs", lazy="dynamic"))


class ScoreRecord(db.Model, TimestampMixin, SoftDeleteMixin):
    """Assessment scores to correlate投入-产出."""

    __tablename__ = "score_record"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False, index=True)
    exam_system = db.Column(db.String(32), nullable=False, index=True)
    assessment_name = db.Column(db.String(128), nullable=False)
    taken_on = db.Column(db.Date, nullable=False, index=True)
    total_score = db.Column(db.Float)
    component_scores = db.Column(db.JSON)  # {"listening": 6.5, "reading": 7.0, ...}
    notes = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    student = db.relationship(
        "StudentProfile",
        backref=db.backref("score_records", lazy="dynamic", cascade="all, delete-orphan"),
    )
    recorder = db.relationship("User", backref=db.backref("score_entries", lazy="dynamic"))


class AuditLogEntry(db.Model):
    """Generic audit log for critical mutations across the system."""

    __tablename__ = "audit_log_entry"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(64), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(32), nullable=False)  # create / update / delete / review
    field = db.Column(db.String(64))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    metadata_payload = db.Column(db.JSON)

    actor = db.relationship("User", backref=db.backref("audit_logs", lazy="dynamic"))


# ---- Legacy models (kept temporarily for compatibility with existing views) ----


class Task(db.Model):
    """Legacy task entity used by当前页面；后续将由 PlanItem 取代。"""

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), index=True)  # YYYY-MM-DD
    student_name = db.Column(db.String(64), index=True)
    category = db.Column(db.String(32))
    detail = db.Column(db.String(200))
    status = db.Column(db.String(12), default="pending")  # pending / progress / done
    note = db.Column(db.String(200))
    accuracy = db.Column(db.Float, default=0.0)
    completion_rate = db.Column(db.Float)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    planned_minutes = db.Column(db.Integer, default=0)
    actual_seconds = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    
    # Material Bank Fields
    material_id = db.Column(db.Integer, db.ForeignKey("material_bank.id"), index=True)
    question_ids = db.Column(db.Text)  # JSON list of selected question IDs
    dictation_book_id = db.Column(db.Integer, db.ForeignKey("dictation_book.id"), index=True)
    dictation_word_start = db.Column(db.Integer, default=1)  # 1-based index
    dictation_word_end = db.Column(db.Integer)              # Inclusive
    grading_mode = db.Column(db.String(50), default="image")  # image/material/hybrid
    
    # Mini Program Fields
    student_submitted = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime)
    evidence_photos = db.Column(db.Text)  # JSON array of URLs
    student_note = db.Column(db.Text)
    
    # Teacher Feedback
    feedback_text = db.Column(db.Text)  # Teacher's written feedback
    feedback_audio = db.Column(db.String(200))
    feedback_image = db.Column(db.String(200))

    creator = db.relationship("User", backref=db.backref("legacy_tasks", lazy="dynamic"))
    material = db.relationship("MaterialBank", backref=db.backref("tasks", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<Task {self.student_name} {self.category} {self.status}>"


# ---- Class Feedback (Scheduler) ----

class ClassFeedback(db.Model, TimestampMixin):
    """Teacher feedback for a scheduled class (external scheduler)."""

    __tablename__ = "class_feedback"

    id = db.Column(db.Integer, primary_key=True)
    schedule_uid = db.Column(db.String(64), unique=True, nullable=False, index=True)
    schedule_id = db.Column(db.String(64), index=True)
    scheduler_student_id = db.Column(db.Integer, index=True)
    student_name = db.Column(db.String(64), index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    teacher_name = db.Column(db.String(64))
    course_name = db.Column(db.String(128))
    start_time = db.Column(db.String(32))
    end_time = db.Column(db.String(32))
    schedule_date = db.Column(db.String(10), index=True)
    feedback_text = db.Column(db.Text, nullable=False)
    feedback_image = db.Column(db.String(200))
    pushed_at = db.Column(db.DateTime)
    push_success = db.Column(db.Boolean, default=False, nullable=False)

    teacher = db.relationship("User", backref=db.backref("class_feedback", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<ClassFeedback {self.schedule_uid}>"


class ScheduleSnapshot(db.Model, TimestampMixin):
    """Snapshot of schedules for change detection."""

    __tablename__ = "schedule_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    schedule_uid = db.Column(db.String(64), unique=True, nullable=False, index=True)
    schedule_id = db.Column(db.String(64), index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    scheduler_teacher_id = db.Column(db.Integer, index=True)
    student_id = db.Column(db.Integer, index=True)
    student_name = db.Column(db.String(64), index=True)
    course_name = db.Column(db.String(128))
    start_time = db.Column(db.String(32))
    end_time = db.Column(db.String(32))
    schedule_date = db.Column(db.String(10), index=True)
    status = db.Column(db.String(16), default="active", nullable=False)
    last_seen = db.Column(db.DateTime, index=True)

    teacher = db.relationship("User", backref=db.backref("schedule_snapshots", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<ScheduleSnapshot {self.schedule_uid} {self.status}>"

# ============================================================================
# Material Bank System (Structured Questions)
# ============================================================================

class MaterialBank(db.Model, TimestampMixin, SoftDeleteMixin):
    """Material bank for structured learning materials."""
    
    __tablename__ = "material_bank"
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), nullable=False, index=True)  # grammar/translation/speaking/writing
    description = db.Column(db.Text)  # Knowledge points explanation
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    creator = db.relationship("User", backref=db.backref("materials", lazy="dynamic"))
    questions = db.relationship("Question", backref="material", lazy="dynamic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MaterialBank {self.id}: {self.title}>"


class Question(db.Model, TimestampMixin):
    """Individual question within a material."""
    
    __tablename__ = "question"
    
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("material_bank.id"), nullable=False, index=True)
    sequence = db.Column(db.Integer, nullable=False)  # Order in material (1, 2, 3...)
    question_type = db.Column(db.String(50), nullable=False)  # text/audio/choice
    content = db.Column(db.Text, nullable=False)  # Question text
    reference_answer = db.Column(db.Text)  # Reference answer (for teacher)
    hint = db.Column(db.Text)  # Optional hint for students
    explanation = db.Column(db.Text)  # Grammar explanation for translation exercises
    points = db.Column(db.Integer, default=1)  # Points for this question
    
    # Relationships
    options = db.relationship("QuestionOption", backref="question", lazy="dynamic", cascade="all, delete-orphan")
    answers = db.relationship("StudentAnswer", backref="question", lazy="dynamic")
    
    def __repr__(self):
        return f"<Question {self.id}: {self.sequence}. {self.content[:30]}...>"


class QuestionOption(db.Model):
    """Multiple choice options for questions."""
    
    __tablename__ = "question_option"
    
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, index=True)
    option_key = db.Column(db.String(10), nullable=False)  # A, B, C, D
    option_text = db.Column(db.Text, nullable=False)
    
    def __repr__(self):
        return f"<QuestionOption {self.option_key}: {self.option_text[:20]}...>"


class StudentAnswer(db.Model, TimestampMixin):
    """Student answers to questions."""
    
    __tablename__ = "student_answer"
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    
    # Answer content
    answer_type = db.Column(db.String(50), nullable=False)  # text/audio/choice
    text_answer = db.Column(db.Text)  # For text/choice questions
    audio_url = db.Column(db.String(500))  # For audio questions
    submitted_at = db.Column(db.DateTime)
    
    # Grading
    reviewed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_correct = db.Column(db.Boolean)  # Optional: correct/incorrect
    teacher_comment = db.Column(db.Text)  # Teacher's feedback
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_at = db.Column(db.DateTime)
    
    # Relationships
    task = db.relationship("Task", backref=db.backref("student_answers", lazy="dynamic"))
    student = db.relationship("User", foreign_keys=[student_id], backref=db.backref("my_answers", lazy="dynamic"))
    reviewer = db.relationship("User", foreign_keys=[reviewed_by], backref=db.backref("reviewed_answers", lazy="dynamic"))
    
    def __repr__(self):
        return f"<StudentAnswer task={self.task_id} q={self.question_id} student={self.student_id}>"


class StudySession(db.Model):
    """Legacy timer segments; superseded by PlanItemSession."""

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"))
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime)
    seconds = db.Column(db.Integer, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    task = db.relationship("Task", backref=db.backref("sessions", lazy="dynamic"))
    creator = db.relationship("User", backref=db.backref("legacy_sessions", lazy="dynamic"))

    def close(self, ended_at: datetime) -> None:
        if self.ended_at:
            return
        self.ended_at = ended_at
        delta = (self.ended_at - self.started_at).total_seconds()
        self.seconds = max(0, int(delta))

    def __repr__(self) -> str:
        return f"<StudySession id={self.id} task={self.task_id} sec={self.seconds}>"

class CoursePlan(db.Model, TimestampMixin, SoftDeleteMixin):
    """Stores generated IELTS/TOEFL study plans."""

    __tablename__ = "course_plan"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student_profile.id"), nullable=False
    )
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Store the full JSON structure from the frontend
    # { student: {...}, phases: [...], pricing: [...] }
    plan_data = db.Column(db.JSON, nullable=False)

    # Metadata for easier querying
    title = db.Column(db.String(200))  # e.g. "张三 - 2025雅思规划"
    
    # Relationships
    student = db.relationship("StudentProfile", backref="course_plans")
    creator = db.relationship("User", backref="created_course_plans")

    def __repr__(self):
        return f"<CoursePlan {self.title}>"


# ============================================================================
# Dictation System (Listening Practice)
# ============================================================================

class DictationBook(db.Model, TimestampMixin, SoftDeleteMixin):
    """Word book/list for dictation practice."""
    
    __tablename__ = "dictation_book"
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    word_count = db.Column(db.Integer, default=0, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    creator = db.relationship("User", backref=db.backref("dictation_books", lazy="dynamic"))
    words = db.relationship("DictationWord", backref="book", lazy="dynamic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DictationBook {self.title}>"


class DictationWord(db.Model, TimestampMixin):
    """Individual word entry in a dictation book."""
    
    __tablename__ = "dictation_word"
    
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("dictation_book.id"), nullable=False, index=True)
    sequence = db.Column(db.Integer, nullable=False)  # Order in book (1, 2, 3...)
    word = db.Column(db.String(100), nullable=False)
    phonetic = db.Column(db.String(100))  # IPA phonetic notation
    translation = db.Column(db.Text)  # Chinese translation/meaning
    audio_us = db.Column(db.String(200))  # American English audio path
    audio_uk = db.Column(db.String(200))  # British English audio path
    
    def __repr__(self):
        return f"<DictationWord {self.word}>"


class DictationRecord(db.Model, TimestampMixin):
    """Student's dictation answer record."""
    
    __tablename__ = "dictation_record"
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), index=True)  # Optional: linked task
    book_id = db.Column(db.Integer, db.ForeignKey("dictation_book.id"), nullable=False, index=True)
    word_id = db.Column(db.Integer, db.ForeignKey("dictation_word.id"), nullable=False, index=True)
    student_answer = db.Column(db.String(100))
    is_correct = db.Column(db.Boolean, nullable=False)
    
    # Relationships
    student = db.relationship("User", backref=db.backref("dictation_records", lazy="dynamic"))
    book = db.relationship("DictationBook", backref=db.backref("records", lazy="dynamic"))
    word = db.relationship("DictationWord", backref=db.backref("records", lazy="dynamic"))
    task = db.relationship("Task", backref=db.backref("dictation_records", lazy="dynamic"))
    
    def __repr__(self):
        return f"<DictationRecord student={self.student_id} word={self.word_id} correct={self.is_correct}>"


class SpeakingSession(db.Model, TimestampMixin):
    """Speaking practice session for a student."""

    __tablename__ = "speaking_session"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student_profile.id"), nullable=False, index=True
    )
    part = db.Column(db.String(16), nullable=False)
    question = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(32))
    source = db.Column(db.String(16))
    part2_topic = db.Column(db.String(32))

    student = db.relationship(
        "StudentProfile",
        backref=db.backref("speaking_sessions", lazy="dynamic", cascade="all, delete-orphan"),
    )


class SpeakingMessage(db.Model, TimestampMixin):
    """Chat-style messages for speaking sessions."""

    __tablename__ = "speaking_message"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer, db.ForeignKey("speaking_session.id"), nullable=False, index=True
    )
    role = db.Column(db.String(16), nullable=False)  # system/user/assistant
    content = db.Column(db.Text)
    result_json = db.Column(db.Text)
    audio_url = db.Column(db.Text)
    meta_json = db.Column(db.Text)

    session = db.relationship(
        "SpeakingSession",
        backref=db.backref("messages", lazy="dynamic", cascade="all, delete-orphan"),
    )
