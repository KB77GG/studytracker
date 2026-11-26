"""Renew only an explicit, private 九分学长 session using the official flow.

The installed 0.9.20-rc.1 client establishes the endpoint and response fields;
see docs/reviews/exam-sprint-repair-20261126/session-lifecycle.md. This module
never discovers a profile, logs in, retries a POST, or returns credentials.
Callers must schedule at most one attempt per day, including failed attempts.
"""

from __future__ import annotations

import fcntl
import http.client
import json
import os
import stat
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

from services.ninefen_source import verified_https_handler

RENEW_URL = "https://www.9fnnn.com/api/user-auth/v1/session/renew"
TIMEOUT_SECONDS = 10
SUCCESS_INTERVAL_SECONDS = 86400
MAX_SESSION_BYTES = 16384
MAX_RESPONSE_BYTES = 65536
TOKEN_FIELDS = ("token", "accessToken", "studentToken")
USER_FIELDS = ("user", "wxUser", "student", "userInfo")
AUTH_CODES = {401, 403, 10401, 10403}


class RenewalError(ValueError):
    """A fixed, credential-free failure; never retain the source response."""

    def __init__(self, message, *, http_status=None, reason_code="renewal_failed"):
        super().__init__(message)
        self.http_status = (
            http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        )
        self.reason_code = (
            reason_code
            if type(reason_code) is str
            and reason_code in {"renewal_failed", "owner_missing", "owner_mismatch"}
            else "renewal_failed"
        )


class AuthenticationRejected(RenewalError):
    """Normal login is required; callers must stop automatic authentication."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RenewalError("Official renewal redirected; stopped without retry")


def _text(value, limit, message):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= limit
        or any(ord(char) < 33 or ord(char) > 126 for char in value)
    ):
        raise RenewalError(message)
    return value


def _token(value):
    return _text(value, 8192, "Session token is missing or invalid")


def _owner(value):
    return _text(value, 128, "Session owner is missing or invalid")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Invalid JSON number")


def _decode(raw):
    try:
        result = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise RenewalError("Session renewal JSON is invalid") from None
    if not isinstance(result, dict):
        raise RenewalError("Session renewal JSON must be an object")
    return result


def _check_private(info, mode=0o600):
    regular = stat.S_ISDIR(info.st_mode) if mode == 0o700 else stat.S_ISREG(info.st_mode)
    if (
        not regular
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != mode
        or (mode == 0o600 and info.st_nlink != 1)
    ):
        raise RenewalError("Session storage must be owned and private (directory 700, file 600)")


@contextmanager
def _locked_directory(path):
    directory_fd = lock_fd = None
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        _check_private(os.fstat(directory_fd), 0o700)
        lock_fd = os.open(
            f".{path.name}.renew.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        _check_private(os.fstat(lock_fd))
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RenewalError("Session renewal is already in progress") from None
        yield directory_fd
    except OSError:
        raise RenewalError("Cannot access private session storage") from None
    finally:
        for fd in (lock_fd, directory_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _read_session(directory_fd, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        _check_private(info)
        raw = handle.read(MAX_SESSION_BYTES + 1)
    if len(raw) > MAX_SESSION_BYTES:
        raise RenewalError("Private session file exceeds size limit")
    payload = _decode(raw)
    _token(payload.get("token"))
    try:
        _owner(payload.get("owner"))
    except RenewalError:
        raise RenewalError(
            "Session owner binding is missing or invalid; normal login required",
            reason_code="owner_missing",
        ) from None
    return raw, payload, (info.st_dev, info.st_ino)


def _user_owner(user):
    if not isinstance(user, dict):
        raise RenewalError("Renewal response has no valid identity")
    values = []
    for key in ("userId", "id"):
        value = user.get(key)
        if value is None or value == "":
            continue
        if type(value) is int:
            value = str(value)
        values.append(_owner(value))
    if not values or len(set(values)) != 1:
        raise RenewalError("Renewal response identity is missing or conflicting")
    return values[0]


def _consistent_alias(data, fields, validate):
    values = [validate(data[key]) for key in fields if key in data and data[key] is not None]
    if not values or len(set(values)) != 1:
        raise RenewalError("Renewal response fields are missing or conflicting")
    return values[0]


def _renewed_token(raw, expected_owner):
    envelope = _decode(raw)
    code = envelope.get("code")
    if type(code) is str and code in {str(value) for value in AUTH_CODES}:
        code = int(code)
    if type(code) is int and code in AUTH_CODES:
        raise AuthenticationRejected(
            "Official renewal rejected authentication; normal login required"
        )
    if not ((type(code) is int and code == 200) or (type(code) is str and code == "200")):
        raise RenewalError("Official renewal refused the request")
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise RenewalError("Renewal response has no object data")
    # zo(e) explicitly accepts e.data || e after request() unwraps the envelope.
    if "data" in data:
        if not isinstance(data["data"], dict) or any(
            key in data for key in (*TOKEN_FIELDS, *USER_FIELDS)
        ):
            raise RenewalError("Renewal response has ambiguous nested data")
        data = data["data"]
    token = _consistent_alias(data, TOKEN_FIELDS, _token)
    owner = _consistent_alias(data, USER_FIELDS, _user_owner)
    if owner != expected_owner:
        raise RenewalError(
            "Renewal response changed identity; session preserved", reason_code="owner_mismatch"
        )
    return token


def _request_renewal(token, owner):
    request = urllib.request.Request(
        RENEW_URL,
        data=b"{}",
        headers={"Accept": "application/json", "Content-Type": "application/json", "token": token},
        method="POST",
    )
    # No cookies, environment proxy credentials, redirect handlers or retry loop.
    try:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect(), verified_https_handler()
        )
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != RENEW_URL:
                raise RenewalError("Official renewal returned an unexpected HTTP response")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise RenewalError("Official renewal returned an unexpected content type")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        error = AuthenticationRejected if status in (401, 403) else RenewalError
        raise error(
            "Official renewal HTTP request failed; stopped without retry", http_status=status
        ) from None
    except (OSError, urllib.error.URLError, http.client.HTTPException):
        raise RenewalError(
            "Official renewal network request failed; stopped without retry"
        ) from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RenewalError("Official renewal response exceeds size limit")
    return _renewed_token(raw, owner)


def _replace_session(directory_fd, name, original, payload):
    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(raw) > MAX_SESSION_BYTES:
        raise RenewalError("Renewed session exceeds private file size limit")
    temporary = f".renew-{uuid.uuid4().hex}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        current_raw, _, current_identity = _read_session(directory_fd, name)
        if (current_raw, current_identity) != original:
            raise RenewalError("Session changed during renewal; newer session preserved")
        # After the atomic commit, never report failure or restore an old token:
        # the source may already have invalidated it. Report durability separately.
        os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        try:
            os.fsync(directory_fd)
        except OSError:
            return False
        return True
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except OSError:
            pass


def renew_session_file(session_file: str | Path, *, now: int | None = None) -> dict:
    """Renew one explicitly supplied session, or skip a recent successful renewal.

    Input is an owned mode-600 JSON file in an owned mode-700 directory, with
    string ``token`` and ``owner`` fields. Only token and integer ``renewed_at``
    change on success. Output contains only status/time/durability metadata.
    Any failure preserves the file; a server-side rotation can still have
    occurred after network loss. ``durability_confirmed=False`` is a committed
    renewal, not a failure or permission to retry: the directory fsync failed.
    ``AuthenticationRejected`` means stop and request normal interactive login.
    This success cooldown does not replace the caller's daily attempt limit.
    """
    timestamp = int(time.time()) if now is None else now
    if type(timestamp) is not int or timestamp <= 0:
        raise RenewalError("Renewal time must be a positive integer")
    path = Path(session_file).absolute()
    with _locked_directory(path) as directory_fd:
        raw, payload, identity = _read_session(directory_fd, path.name)
        previous = payload.get("renewed_at")
        if previous is not None:
            if type(previous) is not int or not 0 < previous <= timestamp:
                raise RenewalError("Stored renewal time is invalid")
            if timestamp - previous < SUCCESS_INTERVAL_SECONDS:
                return {"status": "skipped_recent", "renewed_at": previous}
        token = _request_renewal(payload["token"], payload["owner"])
        updated = {**payload, "token": token, "renewed_at": timestamp}
        durable = _replace_session(directory_fd, path.name, (raw, identity), updated)
    return {"status": "renewed", "renewed_at": timestamp, "durability_confirmed": durable}
