"""Read-only, staff-scoped reports for the vocabulary review pilot."""

from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy import func, or_, select, text

from models import (
    StudentProfile,
    TeacherStudentLink,
    User,
    VocabularyErrorQueue,
    VocabularyPolicyCheckpoint,
    VocabularyPolicyEvent,
    VocabularySense,
    db,
)
from services import vocabulary_error_queue as policy
from services import vocabulary_pilot_metrics
from services.dictation_review import local_date
from services.vocabulary_mastery import utc_naive

STAFF_ROLES = {User.ROLE_ADMIN, User.ROLE_ASSISTANT, User.ROLE_TEACHER}
MAX_STUDENTS = 200
MAX_WEEK_EVENTS = 5000
DIMENSION_LABELS = {
    "meaning_recall": "词义回忆",
    "form_recall": "拼写",
    "audio_form_recall": "听音拼写",
    "context_use": "语境运用",
}
EVENT_LABELS = {
    "paused": "连续失败，暂停并待讲解",
    "overdue_overload": "过载且逾期，转低频巩固",
    "reopened": "重新进入必做队列",
    "unanswerable": "题目材料待核对",
}
STATUS_LABELS = {
    "active": "待复测",
    "paused": "暂停，待讲解",
    "maintenance": "低频巩固",
    "closed": "已退出必做队列",
}


class VocabularyReportError(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code = code
        self.status = status


def feature_enabled():
    return bool(current_app.config.get("VOCABULARY_ERROR_REVIEW_ENABLED", False))


def _require_staff(user):
    if not user or not user.is_active or user.role not in STAFF_ROLES:
        raise VocabularyReportError("forbidden", 403)


def _profiles_query(user):
    """Match existing back-office student-management scope in SQL."""
    _require_staff(user)
    query = StudentProfile.query.filter(
        StudentProfile.is_deleted.is_(False), StudentProfile.user_id.is_not(None)
    )
    if user.role == User.ROLE_TEACHER:
        linked = select(TeacherStudentLink.student_id).where(
            TeacherStudentLink.teacher_id == user.id
        )
        query = query.filter(
            or_(StudentProfile.primary_teacher_id == user.id, StudentProfile.id.in_(linked))
        )
    return query


def _profile(user, profile_id=None, student_name=None):
    query = _profiles_query(user)
    if profile_id not in (None, ""):
        try:
            value = int(profile_id)
            if isinstance(profile_id, bool) or value < 1:
                raise ValueError
        except (TypeError, ValueError):
            raise VocabularyReportError("invalid_student") from None
        profile = query.filter(StudentProfile.id == value).first()
    elif isinstance(student_name, str) and 0 < len(student_name.strip()) <= 64:
        name = student_name.strip()
        # Task ownership still uses names. Refuse ambiguity even if only one
        # matching profile belongs to this teacher; never guess an identity.
        matches = StudentProfile.query.filter_by(full_name=name, is_deleted=False).limit(2).all()
        if len(matches) != 1:
            raise VocabularyReportError("student_unavailable", 404)
        profile = query.filter(StudentProfile.id == matches[0].id).first()
    else:
        raise VocabularyReportError("invalid_student")
    if not profile or not profile.user or not profile.user.is_active:
        raise VocabularyReportError("student_unavailable", 404)
    if profile.user.role != User.ROLE_STUDENT:
        raise VocabularyReportError("student_unavailable", 404)
    return profile


def _load_for_profile(profile, now):
    result = policy.summary(profile.user, now=now)
    return {
        "profile_id": profile.id,
        "name": profile.full_name,
        "enabled": bool(result.get("enabled")),
        "due_count": int(result.get("due_count", 0)),
        "required_count": int(result.get("required_count", 0)),
        "completed_count": int(result.get("completed_count", 0)),
        "daily_limit": int(result.get("daily_limit", 20)),
        "overloaded": bool(result.get("overloaded")),
        "overload_count": int(result.get("overload_count", 0)),
        "paused_count": int(result.get("paused_count", 0)),
        "maintenance_count": int(result.get("maintenance_count", 0)),
        "checkup_due_count": int(result.get("checkup_due_count", 0)),
    }


def assignment_load(user, *, profile_id=None, student_name=None, now=None):
    """Give an authorized assigning teacher a current load warning, never mutate."""
    _require_staff(user)
    if not feature_enabled():
        return {"enabled": False, "student": None}
    now = utc_naive(now or datetime.utcnow())
    with db.session.no_autoflush:
        profile = _profile(user, profile_id, student_name)
        load = _load_for_profile(profile, now)
    return {"enabled": load["enabled"], "student": load}


def _week(value, today):
    try:
        day = date.fromisoformat(value) if value else today
    except (TypeError, ValueError):
        raise VocabularyReportError("invalid_week") from None
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=7)


def _word_rows(events, profiles, today):
    grouped = {}
    for event, queue, checkpoint, sense in events:
        profile = profiles[event.student_id]
        ability = queue or checkpoint
        status_label = (
            "暂停期已到，可复测"
            if queue
            and queue.status == "paused"
            and queue.pause_until_local_date
            and queue.pause_until_local_date <= today
            else STATUS_LABELS.get(queue.status, "待核对") if queue else "抽查未完成，材料待核对"
        )
        key = sense.id
        item = grouped.setdefault(
            key,
            {
                "sense_id": sense.id,
                "word": sense.lemma,
                "meaning": sense.meaning_zh or "",
                "event_count": 0,
                "student_count": 0,
                "events": [],
            },
        )
        item["event_count"] += 1
        item["events"].append(
            {
                "profile_id": profile.id,
                "student_name": profile.full_name,
                "dimension": ability.dimension,
                "dimension_label": DIMENSION_LABELS.get(ability.dimension, "其他能力"),
                "kind": event.kind,
                "kind_label": EVENT_LABELS[event.kind],
                "event_date": event.local_date.isoformat(),
                "status": queue.status if queue else "sample_" + checkpoint.status,
                "status_label": status_label,
                "resume_date": (
                    queue.pause_until_local_date.isoformat()
                    if queue and queue.status == "paused" and queue.pause_until_local_date
                    else None
                ),
            }
        )
    for item in grouped.values():
        item["student_count"] = len({event["profile_id"] for event in item["events"]})
    return sorted(
        grouped.values(), key=lambda row: (-row["student_count"], row["word"], row["sense_id"])
    )


def weekly_report(user, *, week=None, profile_id=None, now=None):
    """Current load plus one Monday–Sunday event digest, scoped before querying."""
    _require_staff(user)
    now = utc_naive(now or datetime.utcnow())
    today = local_date(now)
    start, end = _week(week, today)
    result = {
        "enabled": feature_enabled(),
        "today": today.isoformat(),
        "week_start": start.isoformat(),
        "week_end": (end - timedelta(days=1)).isoformat(),
        "students": [],
        "words": [],
        "totals": {kind: 0 for kind in EVENT_LABELS},
        "has_more_students": False,
        "has_more_events": False,
    }
    if not result["enabled"]:
        return result
    result["pause_days"] = policy.policy_settings()["pause_days"]
    with db.session.no_autoflush:
        if profile_id not in (None, ""):
            profiles = [_profile(user, profile_id)]
        else:
            profiles = (
                _profiles_query(user)
                .join(User, StudentProfile.user_id == User.id)
                .filter(User.is_active.is_(True), User.role == User.ROLE_STUDENT)
                .order_by(StudentProfile.full_name, StudentProfile.id)
                .limit(MAX_STUDENTS + 1)
                .all()
            )
            result["has_more_students"] = len(profiles) > MAX_STUDENTS
            profiles = profiles[:MAX_STUDENTS]
        loads = [_load_for_profile(profile, now) for profile in profiles]
        result["students"] = [row for row in loads if row["enabled"]]
        active_ids = {row["profile_id"] for row in result["students"]}
        visible = {row.user_id: row for row in profiles if row.id in active_ids}
        if not visible:
            return result
        try:
            metric_rows = vocabulary_pilot_metrics.load_rows(
                lambda sql, params: db.session.execute(text(sql), params).mappings().all(),
                student_ids=list(visible),
                as_of=now,
            )
            metrics = vocabulary_pilot_metrics.aggregate(metric_rows, as_of=now, week=start)
            result["pilot_metrics"] = metrics["summary"]
            profiles_by_id = {profile.id: profile for profile in profiles}
            for student in result["students"]:
                profile = profiles_by_id[student["profile_id"]]
                student["weekly_paused_words"] = metrics["student_weekly_paused_words"].get(
                    profile.user_id, 0
                )
        except vocabulary_pilot_metrics.MetricsError:
            result["pilot_metrics_unavailable"] = True
        events = (
            db.session.query(
                VocabularyPolicyEvent,
                VocabularyErrorQueue,
                VocabularyPolicyCheckpoint,
                VocabularySense,
            )
            .outerjoin(
                VocabularyErrorQueue, VocabularyPolicyEvent.queue_id == VocabularyErrorQueue.id
            )
            .outerjoin(
                VocabularyPolicyCheckpoint,
                VocabularyPolicyEvent.checkpoint_id == VocabularyPolicyCheckpoint.id,
            )
            .join(
                VocabularySense,
                func.coalesce(VocabularyErrorQueue.sense_id, VocabularyPolicyCheckpoint.sense_id)
                == VocabularySense.id,
            )
            .filter(
                VocabularyPolicyEvent.student_id.in_(visible),
                or_(
                    VocabularyPolicyEvent.queue_id.is_(None),
                    VocabularyErrorQueue.student_id == VocabularyPolicyEvent.student_id,
                ),
                or_(
                    VocabularyPolicyEvent.checkpoint_id.is_(None),
                    VocabularyPolicyCheckpoint.student_id == VocabularyPolicyEvent.student_id,
                ),
                VocabularyPolicyEvent.local_date >= start,
                VocabularyPolicyEvent.local_date < end,
                VocabularyPolicyEvent.kind.in_(EVENT_LABELS),
            )
            .order_by(VocabularyPolicyEvent.local_date.desc(), VocabularyPolicyEvent.id.desc())
            .limit(MAX_WEEK_EVENTS + 1)
            .all()
        )
        result["has_more_events"] = len(events) > MAX_WEEK_EVENTS
        events = events[:MAX_WEEK_EVENTS]
        counts = defaultdict(int)
        for event, _queue, _checkpoint, _sense in events:
            counts[event.kind] += 1
        result["totals"].update(counts)
        result["words"] = _word_rows(events, visible, today)
    return result
