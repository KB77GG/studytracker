"""Shared navigation policy for the multi-entry Practices module.

The browser keeps the immediate parent (for example a Cambridge catalog) and
the module exit target (for example a student's Today page) as two different
values.  This module owns the server-side defaults and local-URL validation;
the matching browser implementation lives in ``static/js/practice_shell.js``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit


STAFF_ROLES = {"admin", "teacher", "assistant"}


def safe_local_target(value: object, fallback: str = "") -> str:
    """Return a same-site path or ``fallback``.

    Navigation context is allowed to retain a query string and fragment, but
    never a scheme, host, protocol-relative path, backslash, or control byte.
    """

    candidate = str(value or "").strip()
    if not candidate:
        return fallback
    if any(ord(char) < 32 for char in candidate) or "\\" in candidate:
        return fallback
    parsed = urlsplit(candidate)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
        return fallback
    if parsed.path.startswith("//"):
        return fallback
    return parsed.path + (f"?{parsed.query}" if parsed.query else "") + (
        f"#{parsed.fragment}" if parsed.fragment else ""
    )


@dataclass(frozen=True)
class PracticeNavigationDefaults:
    identity_mode: str
    module_root_url: str
    module_exit_url: str
    module_exit_label: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def navigation_defaults(
    *,
    authenticated: bool,
    role: str | None,
    classroom_mode: bool,
    verified_student: bool,
) -> PracticeNavigationDefaults:
    """Resolve the stable exit used when there is no captured entry page."""

    if authenticated and role == "student":
        return PracticeNavigationDefaults(
            identity_mode="student_account",
            module_root_url="/practice",
            module_exit_url="/student/today",
            module_exit_label="返回今日计划",
        )
    if authenticated and role in STAFF_ROLES:
        return PracticeNavigationDefaults(
            identity_mode="staff",
            module_root_url="/practice",
            module_exit_url="/",
            module_exit_label="返回工作台",
        )
    if classroom_mode:
        return PracticeNavigationDefaults(
            identity_mode="classroom",
            module_root_url="/practice",
            module_exit_url="/login",
            module_exit_label="退出课堂刷题",
        )
    if verified_student:
        return PracticeNavigationDefaults(
            identity_mode="verified_student",
            module_root_url="/practice",
            module_exit_url="/login",
            module_exit_label="退出刷题",
        )
    return PracticeNavigationDefaults(
        identity_mode="guest",
        module_root_url="/practice",
        module_exit_url="/login",
        module_exit_label="退出刷题",
    )
