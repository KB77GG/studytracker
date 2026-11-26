"""Resolve the existing practice identity without issuing a new login token."""

import hashlib
import hmac
from dataclasses import dataclass

from flask import current_app, request, session
from flask_login import current_user

from models import StudentProfile, User


@dataclass(frozen=True)
class PracticeStudent:
    profile: StudentProfile
    user: User
    via: str
    identity_key: str


class PracticeIdentityError(Exception):
    def __init__(self, code: str, status: int = 403):
        super().__init__(code)
        self.code = code
        self.status = status


def _identity(profile, user, via):
    secret = current_app.config["SECRET_KEY"]
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    message = f"practice-vocab:{profile.id}:{user.id}".encode()
    key = hmac.new(secret, message, hashlib.sha256).hexdigest()[:20]
    return PracticeStudent(profile, user, via, key)


def resolve_practice_student() -> PracticeStudent:
    """Account identity wins; an unambiguous verified name is the fallback.

    A disabled/unlinked student account never falls through to a different
    name-session identity. No account or profile is created by this resolver.
    """
    known_user = not getattr(current_user, "is_anonymous", True)
    if known_user and current_user.role == User.ROLE_STUDENT:
        if not current_user.is_active:
            raise PracticeIdentityError("student_account_missing")
        profile = StudentProfile.query.filter_by(user_id=current_user.id, is_deleted=False).first()
        if not profile:
            raise PracticeIdentityError("student_account_unlinked")
        return _identity(profile, current_user._get_current_object(), "account")

    staff_roles = {User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT}
    if (
        known_user
        and current_user.role in staff_roles
        or session.get("classroom_unlocked")
        or request.cookies.get("classroom_unlocked") == "1"
    ):
        raise PracticeIdentityError("staff_mode")

    name = str(session.get("practice_student_name") or "").strip()
    if not name:
        raise PracticeIdentityError("identity_missing", 401)
    profiles = StudentProfile.query.filter_by(full_name=name, is_deleted=False).limit(2).all()
    if not profiles:
        session.pop("practice_student_name", None)
        raise PracticeIdentityError("identity_missing", 401)
    if len(profiles) != 1:
        raise PracticeIdentityError("ambiguous_student_name", 409)
    profile = profiles[0]
    user = profile.user
    if not user or not user.is_active or user.role != User.ROLE_STUDENT:
        raise PracticeIdentityError("student_account_missing")
    return _identity(profile, user, "name_session")
