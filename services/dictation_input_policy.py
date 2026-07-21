"""Server-owned input policy for vocabulary spelling practice.

The client may choose strict or compatible input, but it can never grant
itself compatible input.  This module is intentionally independent from the
HTTP blueprints so answer submission and policy discovery share one rule.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import or_

from models import (
    DictationInputGrant,
    StudentProfile,
    Task,
    TeacherStudentLink,
    User,
)

MODE_AUDIO_TO_EN = "audio_to_en"
MODE_ZH_TO_EN = "zh_to_en"
MODE_SPELLING_DRILL = "spelling_drill"
MODE_EN_TO_ZH = "en_to_zh"

INPUT_STRICT = "strict"
INPUT_COMPATIBLE = "compatible"
INPUT_NATIVE = "native"

# Explicit server-side whitelist for vocabulary/dictation tasks only.  Reading
# and listening exercise APIs do not call this service.
WORD_TASK_ENGLISH_MODES = {
    MODE_AUDIO_TO_EN,
    MODE_ZH_TO_EN,
    MODE_SPELLING_DRILL,
}

AUTHORIZED_GRANT_DAYS = {7, 30}


def is_english_spelling_mode(mode: str | None) -> bool:
    return str(mode or "").strip().lower() in WORD_TASK_ENGLISH_MODES


def normalize_input_mode(value: str | None) -> str:
    return str(value or "").strip().lower()


def _active_grant_query(student_id: int, task_id: int | None, now: datetime):
    query = DictationInputGrant.query.filter(
        DictationInputGrant.student_id == student_id,
        DictationInputGrant.revoked_at.is_(None),
        DictationInputGrant.expires_at > now,
    )
    if task_id is None:
        query = query.filter(DictationInputGrant.scope == DictationInputGrant.SCOPE_STUDENT)
    else:
        query = query.filter(
            or_(
                DictationInputGrant.scope == DictationInputGrant.SCOPE_STUDENT,
                DictationInputGrant.task_id == task_id,
            )
        )
    return query.order_by(
        DictationInputGrant.expires_at.desc(),
        DictationInputGrant.id.desc(),
    )


def active_input_grant(
    student_id: int,
    task_id: int | None = None,
    *,
    now: datetime | None = None,
) -> DictationInputGrant | None:
    now = now or datetime.utcnow()
    return _active_grant_query(student_id, task_id, now).first()


def grant_payload(grant: DictationInputGrant | None) -> dict | None:
    if not grant:
        return None
    return {
        "id": grant.id,
        "scope": grant.scope,
        "task_id": grant.task_id,
        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
        "reason": grant.reason or "",
    }


def input_policy(
    user: User,
    mode: str | None,
    *,
    task_id: int | None = None,
    now: datetime | None = None,
) -> dict:
    """Return the effective client policy, defaulting safely to strict."""

    normalized_mode = str(mode or "").strip().lower()
    now = now or datetime.utcnow()
    if not is_english_spelling_mode(normalized_mode):
        return {
            "mode": normalized_mode or MODE_EN_TO_ZH,
            "is_english_spelling": False,
            "default_input_mode": INPUT_NATIVE,
            "compatible_allowed": False,
            "grant": None,
        }

    grant = active_input_grant(user.id, task_id, now=now)
    return {
        "mode": normalized_mode,
        "is_english_spelling": True,
        "default_input_mode": INPUT_STRICT,
        "compatible_allowed": bool(grant),
        "grant": grant_payload(grant),
    }


def resolve_submission_input(
    user: User,
    mode: str,
    requested_input_mode: str | None,
    *,
    task_id: int | None = None,
    now: datetime | None = None,
) -> tuple[str, int | None]:
    """Validate and normalize the input mode attached to an answer."""

    normalized_mode = str(mode or "").strip().lower()
    if not is_english_spelling_mode(normalized_mode):
        return INPUT_NATIVE, None

    requested = normalize_input_mode(requested_input_mode) or INPUT_STRICT
    if requested == INPUT_STRICT:
        return INPUT_STRICT, None
    if requested != INPUT_COMPATIBLE:
        raise ValueError("invalid_input_mode")

    grant = active_input_grant(user.id, task_id, now=now)
    if not grant:
        raise PermissionError("compatible_input_not_authorized")
    return INPUT_COMPATIBLE, grant.id


def staff_can_manage_student(staff: User, profile: StudentProfile) -> bool:
    """Match the existing back-office student management permissions.

    Assistants and admins operate the shared student queue.  Teachers remain
    restricted to students explicitly assigned to them.
    """

    if staff.role in {User.ROLE_ADMIN, User.ROLE_ASSISTANT}:
        return True
    if staff.role != User.ROLE_TEACHER:
        return False
    if profile.primary_teacher_id == staff.id:
        return True
    return TeacherStudentLink.query.filter_by(
        teacher_id=staff.id,
        student_id=profile.id,
    ).first() is not None


def supersede_active_input_grants(
    profile: StudentProfile,
    *,
    task: Task | None = None,
    now: datetime | None = None,
) -> None:
    """Revoke the current grant in the same scope before replacing it."""

    if not profile.user_id:
        return
    now = now or datetime.utcnow()
    query = DictationInputGrant.query.filter(
        DictationInputGrant.student_id == profile.user_id,
        DictationInputGrant.revoked_at.is_(None),
        DictationInputGrant.expires_at > now,
    )
    if task:
        query = query.filter(
            DictationInputGrant.scope == DictationInputGrant.SCOPE_TASK,
            DictationInputGrant.task_id == task.id,
        )
    else:
        query = query.filter(
            DictationInputGrant.scope == DictationInputGrant.SCOPE_STUDENT,
        )
    for grant in query.all():
        grant.revoked_at = now


def create_input_grant(
    teacher: User,
    profile: StudentProfile,
    *,
    duration_days: int,
    task: Task | None = None,
    reason: str | None = None,
    now: datetime | None = None,
) -> DictationInputGrant:
    if duration_days not in AUTHORIZED_GRANT_DAYS:
        raise ValueError("invalid_duration_days")
    if not profile.user_id:
        raise ValueError("student_has_no_login")
    now = now or datetime.utcnow()
    scope = DictationInputGrant.SCOPE_TASK if task else DictationInputGrant.SCOPE_STUDENT
    expires_at = now + timedelta(days=duration_days)
    grant = DictationInputGrant(
        student_id=profile.user_id,
        student_profile_id=profile.id,
        teacher_id=teacher.id,
        task_id=task.id if task else None,
        scope=scope,
        expires_at=expires_at,
        reason=str(reason or "教务授权单词任务实体键盘")[:255],
    )
    return grant


def grant_is_for_task(grant: DictationInputGrant | None, task_id: int | None) -> bool:
    if not grant:
        return False
    return grant.scope == DictationInputGrant.SCOPE_STUDENT or grant.task_id == task_id
