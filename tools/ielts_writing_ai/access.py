"""Trial access: one-time-displayed access codes, sessions and CSRF.

Trial users are not StudyTracker accounts.  An operator issues a code with the
CLI; the code is shown once and only its SHA-256 is stored.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

from .storage import parse_iso, utcnow

CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O/1/I
CODE_GROUPS = 4
CODE_GROUP_LEN = 4


def generate_code() -> str:
    groups = [
        "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_GROUP_LEN))
        for _ in range(CODE_GROUPS)
    ]
    return "IWA-" + "-".join(groups)


def normalize_code(value: str | None) -> str:
    cleaned = "".join(ch for ch in (value or "").upper() if ch.isalnum())
    if cleaned.startswith("IWA"):
        cleaned = cleaned[3:]
    return cleaned


def hash_code(value: str) -> str:
    return hashlib.sha256(("iwa:" + normalize_code(value)).encode("utf-8")).hexdigest()


def code_hint(value: str) -> str:
    return normalize_code(value)[-4:]


def user_block_reason(user: dict | None) -> str | None:
    if not user:
        return "unknown"
    if user.get("disabled_at"):
        return "disabled"
    expires = parse_iso(user.get("expires_at"))
    if expires is not None and expires <= utcnow():
        return "expired"
    return None


class LoginLimiter:
    """Per-client sliding window of failed attempts."""

    def __init__(self, max_failures: int = 8, window_seconds: int = 900):
        self.max_failures = max_failures
        self.window = window_seconds
        self._failures: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque:
        bucket = self._failures[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        return bucket

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._trim(key, time.monotonic())) >= self.max_failures

    def fail(self, key: str) -> None:
        with self._lock:
            self._trim(key, time.monotonic()).append(time.monotonic())

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
