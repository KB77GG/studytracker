"""Teacher-owned practice access derived from scheduler course relationships."""

import hashlib
import re
import time
from datetime import date, timedelta

import jwt
from flask import Blueprint, current_app, jsonify, request

from models import StudentProfile, User
from services.scheduler_client import coerce_schedule_list, fetch_range_schedules_by_dates

from .auth_utils import require_api_user

teacher_practice_bp = Blueprint(
    "teacher_practice_access",
    __name__,
    url_prefix="/api/miniprogram/teacher",
)

PRACTICE_CONTEXT_TYPE = "teacher_practice_context"
PRACTICE_CONTEXT_TTL_SECONDS = 30 * 60

SUBJECTS = {
    "listening": {
        "label": "雅思听力",
        "allowed_source": "cambridge_listening",
    },
    "reading": {
        "label": "雅思阅读",
        "allowed_source": "cambridge_reading",
    },
}


def normalize_course_subject(course_name: str | None) -> str | None:
    """Map scheduler course names to the small set of supported subject keys."""

    value = re.sub(r"[\s_\-—–·|/]+", "", str(course_name or "")).lower()
    if ("雅思" in value or "ielts" in value) and (
        "听力" in value or "listening" in value
    ):
        return "listening"
    if ("雅思" in value or "ielts" in value) and (
        "阅读" in value or "reading" in value
    ):
        return "reading"
    return None


def subject_definition(subject_key: str) -> dict | None:
    definition = SUBJECTS.get(subject_key)
    return dict(definition) if definition else None


def _first_schedule_value(item: dict, *keys):
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _schedule_uid(schedule_id, teacher_id, student_id, course_name, start_time):
    if schedule_id:
        return f"id:{schedule_id}"
    raw = f"{teacher_id or ''}|{student_id or ''}|{course_name or ''}|{start_time or ''}"
    return f"hash:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:24]}"


def _schedule_context(item: dict, fallback_teacher_id=None) -> dict:
    schedule_id = _first_schedule_value(item, "schedule_id", "id", "scheduleId")
    student_id = _first_schedule_value(
        item,
        "scheduler_student_id",
        "student_id",
        "studentId",
        "studentID",
    )
    teacher_id = _first_schedule_value(
        item,
        "scheduler_teacher_id",
        "teacher_id",
        "teacherId",
        "teacherID",
    ) or fallback_teacher_id
    course_name = _first_schedule_value(item, "course_name", "courseName", "name") or ""
    start_time = _first_schedule_value(
        item,
        "start_time",
        "start_at",
        "startTime",
        "startAt",
        "datetime",
    )
    end_time = _first_schedule_value(
        item,
        "end_time",
        "end_at",
        "endTime",
        "endAt",
        "end_datetime",
    )
    schedule_date = _first_schedule_value(item, "schedule_date", "scheduleDate", "date")
    if schedule_date and start_time and len(str(start_time)) <= 5:
        start_time = f"{schedule_date} {start_time}"
    if schedule_date and end_time and len(str(end_time)) <= 5:
        end_time = f"{schedule_date} {end_time}"
    student_name = _first_schedule_value(
        item,
        "student_name",
        "student",
        "studentName",
        "student_full_name",
        "studentFullName",
    )
    teacher_name = _first_schedule_value(
        item,
        "teacher_name",
        "teacherName",
        "teacher",
    ) or "老师待定"
    return {
        "schedule_id": schedule_id,
        "schedule_uid": _schedule_uid(
            schedule_id,
            teacher_id,
            student_id,
            course_name,
            start_time,
        ),
        "student_id": student_id,
        "scheduler_student_id": student_id,
        "teacher_id": teacher_id,
        "course_name": course_name,
        "start_time": start_time,
        "end_time": end_time,
        "teacher_name": teacher_name,
        "student_name": str(student_name or "").strip(),
        "schedule_date": schedule_date or (str(start_time).split(" ")[0] if start_time else ""),
    }


def _student_key(student_id, student_name):
    if student_id not in (None, ""):
        return f"id:{student_id}"
    return f"name:{student_name}"


def _schedule_sort_key(schedule: dict):
    return (
        str(schedule.get("schedule_date") or "9999-99-99"),
        str(schedule.get("start_time") or "99:99"),
        str(schedule.get("schedule_uid") or ""),
    )


def aggregate_practice_students(
    schedules,
    *,
    scheduler_teacher_id=None,
    student_name_map: dict | None = None,
) -> list[dict]:
    """Aggregate one scheduler teacher's schedules by student and supported subject."""

    student_name_map = {str(key): value for key, value in (student_name_map or {}).items()}
    grouped = {}
    for item in schedules or []:
        context = _schedule_context(item, fallback_teacher_id=scheduler_teacher_id)
        if (
            scheduler_teacher_id is not None
            and context["teacher_id"] not in (None, "")
            and str(context["teacher_id"]) != str(scheduler_teacher_id)
        ):
            continue
        if not context["student_id"]:
            continue
        if not context["student_name"]:
            context["student_name"] = student_name_map.get(
                str(context["student_id"]),
                f"学生 {context['student_id']}",
            )
        subject_key = normalize_course_subject(context["course_name"])
        if not subject_key:
            continue

        student_key = _student_key(context["student_id"], context["student_name"])
        student = grouped.setdefault(
            student_key,
            {
                "student_id": context["student_id"],
                "student_name": context["student_name"],
                "subjects": {},
            },
        )
        if not student["student_name"] or student["student_name"].startswith("学生 "):
            student["student_name"] = context["student_name"]
        current = student["subjects"].get(subject_key)
        if current is None or _schedule_sort_key(context) < _schedule_sort_key(current):
            student["subjects"][subject_key] = context

    result = []
    for student in grouped.values():
        subjects = []
        for subject_key, schedule in sorted(student["subjects"].items()):
            definition = SUBJECTS[subject_key]
            subjects.append({
                "subject_key": subject_key,
                "subject_label": definition["label"],
                "allowed_source": definition["allowed_source"],
                "schedule": schedule,
            })
        student["subjects"] = subjects
        if subjects:
            result.append(student)
    result.sort(key=lambda item: (item["student_name"], str(item["student_id"])))
    return result


def _month_range(month_value: str | None):
    value = (month_value or date.today().strftime("%Y-%m")).strip()
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("invalid_month")
    try:
        year, month = (int(part) for part in value.split("-", 1))
        start = date(year, month, 1)
    except (TypeError, ValueError):
        raise ValueError("invalid_month") from None
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return value, start, end


def _student_name_map(student_ids) -> dict[str, str]:
    numeric_ids = []
    for value in student_ids:
        try:
            numeric_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    if not numeric_ids:
        return {}
    profiles = StudentProfile.query.filter(
        StudentProfile.scheduler_student_id.in_(numeric_ids),
        StudentProfile.is_deleted.is_(False),
    ).all()
    return {
        str(profile.scheduler_student_id): profile.full_name
        for profile in profiles
        if profile.scheduler_student_id
    }


def issue_practice_context_token(user: User, month: str, subject: dict) -> str:
    schedule = subject["schedule"]
    now = int(time.time())
    payload = {
        "typ": PRACTICE_CONTEXT_TYPE,
        "sub": str(user.id),
        "scheduler_teacher_id": str(user.scheduler_teacher_id),
        "scheduler_student_id": str(schedule["student_id"]),
        "subject_key": subject["subject_key"],
        "allowed_source": subject["allowed_source"],
        "month": month,
        "schedule_uid": schedule["schedule_uid"],
        "iat": now,
        "exp": now + PRACTICE_CONTEXT_TTL_SECONDS,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _decode_practice_context_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == PRACTICE_CONTEXT_TYPE else None


def _value_matches(left, right) -> bool:
    return left in (None, "") or str(left) == str(right)


def validate_quick_practice_request(user: User, data: dict):
    """Verify a shortcut context and re-check it against the live teacher schedule.

    Returns ``(context, error, status)``. A non-shortcut request returns
    ``(None, None, 200)`` so the existing generic homework flow is unchanged.
    """

    token = str(data.get("practice_context_token") or "").strip()
    quick_requested = bool(token) or str(data.get("quick_practice") or "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    quick_requested = quick_requested or bool(
        str(data.get("subject_key") or "").strip()
        or str(data.get("allowed_source") or "").strip()
    )
    if not quick_requested:
        return None, None, 200
    if not token or not user.scheduler_teacher_id:
        return None, "forbidden_subject", 403

    payload = _decode_practice_context_token(token)
    subject_key = str(data.get("subject_key") or "").strip()
    definition = subject_definition(subject_key)
    if not payload or not definition:
        return None, "forbidden_subject", 403
    if payload.get("sub") != str(user.id):
        return None, "forbidden_subject", 403
    if payload.get("scheduler_teacher_id") != str(user.scheduler_teacher_id):
        return None, "forbidden_subject", 403
    if payload.get("subject_key") != subject_key:
        return None, "forbidden_subject", 403
    if payload.get("allowed_source") != definition["allowed_source"]:
        return None, "forbidden_subject", 403
    if data.get("allowed_source") != definition["allowed_source"]:
        return None, "forbidden_subject", 403
    if data.get("source_type") != definition["allowed_source"]:
        return None, "forbidden_subject", 403
    if not _value_matches(data.get("student_id"), payload.get("scheduler_student_id")):
        return None, "forbidden_subject", 403
    if not _value_matches(data.get("teacher_id"), user.scheduler_teacher_id):
        return None, "forbidden_subject", 403

    try:
        month, start, end = _month_range(payload.get("month"))
    except ValueError:
        return None, "forbidden_subject", 403
    schedule_payload, scheduler_error = fetch_range_schedules_by_dates(
        start,
        end,
        teacher_id=user.scheduler_teacher_id,
    )
    if scheduler_error:
        return None, "scheduler_verification_failed", 503

    raw_schedules = coerce_schedule_list(schedule_payload)
    student_id = payload.get("scheduler_student_id")
    students = aggregate_practice_students(
        raw_schedules,
        scheduler_teacher_id=user.scheduler_teacher_id,
    )
    matched_subject = None
    for student in students:
        if str(student.get("student_id")) != str(student_id):
            continue
        matched_subject = next(
            (
                item
                for item in student.get("subjects") or []
                if item.get("subject_key") == subject_key
            ),
            None,
        )
        if matched_subject:
            break
    if not matched_subject:
        return None, "forbidden_subject", 403

    local_profile = StudentProfile.query.filter_by(
        scheduler_student_id=matched_subject["schedule"]["student_id"],
        is_deleted=False,
    ).first()
    scheduler_student_name = next(
        (
            student["student_name"]
            for student in students
            if str(student.get("student_id")) == str(student_id)
        ),
        matched_subject["schedule"].get("student_name") or "",
    )
    return {
        "month": month,
        "subject_key": subject_key,
        "allowed_source": definition["allowed_source"],
        "scheduler_student_id": matched_subject["schedule"]["student_id"],
        "student_name": local_profile.full_name if local_profile else scheduler_student_name,
        "schedule": matched_subject["schedule"],
    }, None, 200


@teacher_practice_bp.get("/practice-students")
@require_api_user(User.ROLE_TEACHER)
def get_teacher_practice_students():
    user = request.current_api_user
    if not user.scheduler_teacher_id:
        return jsonify({"ok": False, "error": "missing_scheduler_teacher_id"}), 400
    try:
        month, start, end = _month_range(request.args.get("month"))
    except ValueError:
        return jsonify({"ok": False, "error": "invalid_month"}), 400

    payload, scheduler_error = fetch_range_schedules_by_dates(
        start,
        end,
        teacher_id=user.scheduler_teacher_id,
    )
    if scheduler_error:
        return jsonify({"ok": False, "error": scheduler_error}), 502

    schedules = coerce_schedule_list(payload)
    schedule_contexts = [
        _schedule_context(item, user.scheduler_teacher_id) for item in schedules
    ]
    student_ids = {
        context["student_id"] for context in schedule_contexts if context["student_id"]
    }
    students = aggregate_practice_students(
        schedules,
        scheduler_teacher_id=user.scheduler_teacher_id,
        student_name_map=_student_name_map(student_ids),
    )
    for student in students:
        for subject in student["subjects"]:
            subject["practice_context_token"] = issue_practice_context_token(
                user,
                month,
                subject,
            )

    return jsonify({
        "ok": True,
        "month": month,
        "student_count": len(students),
        "students": students,
    })
