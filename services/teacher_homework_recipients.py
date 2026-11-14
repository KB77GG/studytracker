"""Resolve homework recipients from a teacher's current scheduler roster.

The scheduler's combined student record is not a StudyTracker account.  A
preview explicitly binds each authoritative roster name to one individual
profile; publishing verifies that exact binding again before creating tasks.
"""

import hashlib
import json
import re
import time
from datetime import date

import jwt
from flask import current_app

from api.teacher_practice_access import _schedule_context
from models import StudentProfile, User
from services.scheduler_client import coerce_schedule_list, fetch_range_schedules_by_dates

ROSTER_TOKEN_TYPE = "teacher_homework_roster"
ROSTER_TOKEN_TTL = 30 * 60
MAX_MEMBERS = 50


class HomeworkRecipientsError(Exception):
    def __init__(self, code, status=400, message=None, members=None):
        self.code = code
        self.status = status
        self.message = message or code
        self.members = members
        super().__init__(self.message)


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _identifier(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return ""
    return str(value).strip()


def _scheduler_id(value):
    value = _identifier(value)
    return int(value) if value.isdigit() and int(value) > 0 else None


def _requested_day(data):
    value = _text(data.get("schedule_date")) or _text(data.get("start_time"))[:10]
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError:
        raise HomeworkRecipientsError(
            "invalid_schedule_date", message="请从课表重新进入布置作业"
        ) from None


def _load_schedule(user, data):
    supplied_teacher = _identifier(data.get("teacher_id"))
    teacher_id = _scheduler_id(user.scheduler_teacher_id)
    if user.role == User.ROLE_ADMIN and supplied_teacher:
        teacher_id = _scheduler_id(supplied_teacher)
    if not teacher_id:
        raise HomeworkRecipientsError(
            "missing_scheduler_teacher_id", message="请先关联老师的排课账号"
        )
    if user.role != User.ROLE_ADMIN and supplied_teacher and supplied_teacher != str(teacher_id):
        raise HomeworkRecipientsError("forbidden_schedule", 403, "当前课表不属于你")
    day = _requested_day(data)
    schedule_id = _identifier(data.get("schedule_id"))
    schedule_uid = _text(data.get("schedule_uid"))
    if not schedule_id and not schedule_uid:
        raise HomeworkRecipientsError("missing_schedule", message="请从课表重新进入布置作业")
    payload, error = fetch_range_schedules_by_dates(day, day, teacher_id=teacher_id)
    if error:
        raise HomeworkRecipientsError(
            "scheduler_verification_failed", 503, "课表校验失败，请稍后重试"
        )
    matches = []
    for raw in coerce_schedule_list(payload):
        if not isinstance(raw, dict):
            continue
        schedule = _schedule_context(raw)
        if _identifier(schedule["teacher_id"]) != str(teacher_id):
            continue
        if str(schedule.get("schedule_date") or "")[:10] != day.isoformat():
            continue
        if schedule_id and _identifier(schedule["schedule_id"]) != schedule_id:
            continue
        if schedule_uid and schedule["schedule_uid"] != schedule_uid:
            continue
        matches.append((raw, schedule))
    if len(matches) != 1:
        raise HomeworkRecipientsError("forbidden_schedule", 403, "课表已变更，请返回课表重新进入")
    return matches[0]


def _split_names(value):
    # Only explicit slash-separated legacy rosters are expanded.  Spaces in
    # English names remain part of the student's name.
    return [part.strip() for part in re.split(r"[/／]", _text(value)) if part.strip()]


def legacy_homework_is_group(data, quick_context=None):
    """Keep older single-recipient clients from silently sending to one member."""
    names = [data.get("student_name")]
    if isinstance(quick_context, dict):
        schedule = quick_context.get("schedule")
        if isinstance(schedule, dict):
            # The top-level quick-context name may already be replaced by the
            # first locally bound profile.  The verified schedule keeps the roster.
            names.append(schedule.get("student_name"))
    return any(len(_split_names(name)) > 1 for name in names)


def _candidate_members(raw, schedule):
    entries = raw.get("student_profiles")
    candidates = []
    if isinstance(entries, list) and entries:
        for entry in entries:
            if not isinstance(entry, dict):
                raise HomeworkRecipientsError(
                    "invalid_roster", 409, "课表成员信息不完整，请先核对排课名单"
                )
            names = _split_names(
                entry.get("name") or entry.get("student_name") or entry.get("full_name")
            )
            if not names:
                raise HomeworkRecipientsError(
                    "invalid_roster", 409, "课表成员姓名缺失，请先核对排课名单"
                )
            individual_id = _scheduler_id(
                entry.get("scheduler_student_id") or entry.get("student_id") or entry.get("id")
            )
            candidates.extend((name, individual_id if len(names) == 1 else None) for name in names)
        legacy_names = _split_names(schedule["student_name"])
        if len(legacy_names) > 1:
            structured_names = [name for name, _student_id in candidates]
            if any(name not in legacy_names for name in structured_names):
                raise HomeworkRecipientsError(
                    "invalid_roster", 409, "课表姓名与成员名单不一致，请先核对排课名单"
                )
            candidates.extend((name, None) for name in legacy_names if name not in structured_names)
    else:
        names = _split_names(schedule["student_name"])
        candidates = [
            (name, _scheduler_id(schedule["student_id"]) if len(names) == 1 else None)
            for name in names
        ]
    if not candidates or len(candidates) > MAX_MEMBERS:
        raise HomeworkRecipientsError("invalid_roster", 409, "课表成员数量不正确，请先核对排课名单")
    return candidates


def _resolve_member(name, scheduler_id):
    named = StudentProfile.query.filter_by(full_name=name, is_deleted=False).all()
    bound = None
    if scheduler_id:
        bound = StudentProfile.query.filter_by(
            scheduler_student_id=scheduler_id, is_deleted=False
        ).first()
    profile = bound or (named[0] if len(named) == 1 else None)
    ambiguous = len(named) > 1 or (bound and named and any(row.id != bound.id for row in named))
    if profile and not ambiguous:
        # Task ownership still uses full_name.  Selecting a profile ID cannot
        # safely disambiguate two accounts sharing that task namespace.
        ambiguous = (
            StudentProfile.query.filter_by(full_name=profile.full_name, is_deleted=False).count()
            != 1
        )
    status = "ambiguous" if ambiguous else "ready" if profile else "missing"
    if status != "ready":
        profile = None
    member = {
        "student_name": profile.full_name if profile else name,
        "profile_id": profile.id if profile else None,
        "status": status,
        "has_wechat_binding": bool(
            profile and profile.user and profile.user.is_active and profile.user.wechat_openid
        ),
    }
    return member, profile


def _roster(user, data):
    raw, schedule = _load_schedule(user, data)
    candidates = _candidate_members(raw, schedule)
    resolved = [_resolve_member(name, student_id) for name, student_id in candidates]
    members = [member for member, _profile in resolved]
    names = [member["student_name"] for member in members]
    ids = [member["profile_id"] for member in members if member["profile_id"]]
    for member in members:
        if names.count(member["student_name"]) > 1 or (
            member["profile_id"] and ids.count(member["profile_id"]) > 1
        ):
            member.update(status="ambiguous", profile_id=None, has_wechat_binding=False)
    profiles = [profile for member, profile in resolved if member["status"] == "ready"]
    identity = {
        key: schedule[key]
        for key in (
            "schedule_id",
            "schedule_uid",
            "student_id",
            "teacher_id",
            "course_name",
            "start_time",
            "end_time",
            "schedule_date",
        )
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "schedule": identity,
                "candidates": candidates,
                "members": [
                    {key: item[key] for key in ("student_name", "profile_id", "status")}
                    for item in members
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    context = {
        "schedule": schedule,
        "members": members,
        "fingerprint": fingerprint,
        "is_group": len(members) > 1,
    }
    return profiles, context


def _preview_message(members):
    missing = [row["student_name"] for row in members if row["status"] == "missing"]
    ambiguous = [row["student_name"] for row in members if row["status"] == "ambiguous"]
    parts = []
    if missing:
        parts.append(f"未找到个人档案：{'、'.join(missing)}")
    if ambiguous:
        parts.append(f"成员匹配不唯一：{'、'.join(ambiguous)}")
    if parts:
        return "；".join(parts) + "。请先核对或补齐个人档案，本次不会给部分成员布置。"
    return f"将为 {len(members)} 位学生分别布置作业，完成记录各自独立。"


def preview_recipients(user, data):
    _profiles, context = _roster(user, data)
    can_assign = all(member["status"] == "ready" for member in context["members"])
    token = None
    if can_assign:
        now = int(time.time())
        token = jwt.encode(
            {
                "typ": ROSTER_TOKEN_TYPE,
                "sub": str(user.id),
                "teacher_id": str(user.scheduler_teacher_id),
                "fingerprint": context["fingerprint"],
                "iat": now,
                "exp": now + ROSTER_TOKEN_TTL,
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
    return {
        "ok": True,
        "is_group": context["is_group"],
        "members": context["members"],
        "can_assign": can_assign,
        "roster_token": token,
        "message": _preview_message(context["members"]),
    }


def validate_recipients(user, data, *, require_selection=True):
    token = _text(data.get("roster_token"))
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise HomeworkRecipientsError(
            "roster_expired", 409, "成员确认已过期，请刷新名单后再布置"
        ) from None
    except jwt.PyJWTError:
        raise HomeworkRecipientsError(
            "invalid_roster_token", 403, "请先确认本次作业的接收成员"
        ) from None
    if (
        payload.get("typ") != ROSTER_TOKEN_TYPE
        or payload.get("sub") != str(user.id)
        or payload.get("teacher_id") != str(user.scheduler_teacher_id)
    ):
        raise HomeworkRecipientsError("invalid_roster_token", 403, "成员确认与当前账号不符")
    profiles, context = _roster(user, data)
    if not all(member["status"] == "ready" for member in context["members"]):
        raise HomeworkRecipientsError(
            "roster_incomplete", 409, _preview_message(context["members"]), context["members"]
        )
    if payload.get("fingerprint") != context["fingerprint"]:
        raise HomeworkRecipientsError(
            "roster_changed", 409, "课表成员或档案已变更，请刷新名单重新确认", context["members"]
        )
    if require_selection:
        supplied_ids = data.get("recipient_profile_ids")
        expected_ids = sorted(profile.id for profile in profiles)
        if (
            not isinstance(supplied_ids, list)
            or any(type(value) is not int or value <= 0 for value in supplied_ids)
            or sorted(supplied_ids) != expected_ids
        ):
            raise HomeworkRecipientsError(
                "recipient_mismatch",
                409,
                "接收成员与确认名单不一致，请刷新后重试",
                context["members"],
            )
    return profiles, context
