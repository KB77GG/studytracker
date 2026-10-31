"""Additive scheduling tables; drafts never masquerade as student tasks."""

from models import TimestampMixin, db, utcnow_naive


class TaskPlannerStudent(db.Model, TimestampMixin):
    __tablename__ = "task_planner_student"

    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), primary_key=True)
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class TaskPlannerEntry(db.Model, TimestampMixin):
    __tablename__ = "task_planner_entry"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False, index=True)
    target_date = db.Column(db.Date, nullable=False, index=True)
    kind = db.Column(db.String(32), nullable=False)
    title = db.Column(db.String(240), nullable=False)
    selection_json = db.Column(db.Text, nullable=False)
    prepared_json = db.Column(db.Text, nullable=False)
    planned_minutes = db.Column(db.Integer, nullable=False, default=20)
    note = db.Column(db.String(200), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    prerequisite_task_id = db.Column(db.Integer, db.ForeignKey("task.id"))
    published_task_id = db.Column(db.Integer, db.ForeignKey("task.id"), unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    confirmed_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    last_error = db.Column(db.String(500), nullable=False, default="")


class TaskPlannerEvent(db.Model):
    __tablename__ = "task_planner_event"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("task_planner_entry.id"), index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(32), nullable=False)
    detail = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utcnow_naive, nullable=False)


class TaskPlannerSeries(db.Model, TimestampMixin):
    """A finite, explicitly previewed sequence sharing one weekly schedule."""

    __tablename__ = "task_planner_series"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student_profile.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(32), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    weekday_counts_json = db.Column(db.Text, nullable=False)
    definition_json = db.Column(db.Text, nullable=False)
    wait_for_previous = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    version = db.Column(db.Integer, nullable=False, default=1)
    request_key = db.Column(db.String(96), nullable=False, unique=True)
    request_hash = db.Column(db.String(64), nullable=False)
    preview_hash = db.Column(db.String(64), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    confirmed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    confirmed_at = db.Column(db.DateTime)


class TaskPlannerSeriesItem(db.Model):
    """Links new series to unchanged, already deployed planner-entry schema."""

    __tablename__ = "task_planner_series_item"
    __table_args__ = (db.UniqueConstraint("series_id", "order_index"),)

    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey("task_planner_series.id"), nullable=False, index=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("task_planner_entry.id"), nullable=False, unique=True)
    previous_entry_id = db.Column(db.Integer, db.ForeignKey("task_planner_entry.id"))
    order_index = db.Column(db.Integer, nullable=False)
    unit_count = db.Column(db.Integer, nullable=False)


def ensure_schema():
    """Only create this feature's new tables; never alter existing task data."""
    for model in (TaskPlannerStudent, TaskPlannerEntry, TaskPlannerEvent,
                  TaskPlannerSeries, TaskPlannerSeriesItem):
        model.__table__.create(bind=db.engine, checkfirst=True)
