#!/usr/bin/env python3
"""Run a due, initialized local week; publish only after complete validation."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import selectors
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ninefen_auth import (  # noqa: E402
    AuthenticationRejected,
    RenewalError,
    renew_session_file,
)

ZONE = ZoneInfo("Asia/Shanghai")
LABEL = "com.sagepath.studytracker-exam-sprint"
MAX_WEEKLY_ATTEMPTS = 3
SESSION_RENEWAL_INTERVAL = 86400
MAX_DIAGNOSTIC_LINE = 4096
MAX_DIAGNOSTIC_BYTES = 256 * 1024
MAX_DIAGNOSTIC_EVENTS = 160


def _safe_diagnostic(raw: bytes) -> dict | None:
    """An independent, closed log boundary; never forward arbitrary child JSON."""
    if len(raw) > MAX_DIAGNOSTIC_LINE:
        return None
    try:
        record = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        return None
    if not isinstance(record, dict) or type(record.get("diagnostic_version")) is not int:
        return None
    if record["diagnostic_version"] != 1:
        return None
    name = record.get("event")
    base = {"diagnostic_version", "event"}
    if name == "sprint_sync_busy":
        return record if set(record) == base else None
    if name == "sprint_sync_progress":
        if (
            set(record) == base | {"processed", "action", "unit_id"}
            and type(record["processed"]) is int
            and 1 <= record["processed"] <= 140
            and record["action"] in ("reused", "imported")
            and isinstance(record["unit_id"], str)
            and re.fullmatch(r"[0-9]{1,24}", record["unit_id"])
        ):
            return record
    elif name == "sprint_sync_completed":
        if (
            set(record)
            == base | {"ok", "dry_run", "total", "verified_practice_links", "fetched_at"}
            and record["ok"] is True
            and type(record["dry_run"]) is bool
            and type(record["total"]) is int
            and type(record["verified_practice_links"]) is int
            and 0 <= record["verified_practice_links"] <= record["total"] <= 140
            and isinstance(record["fetched_at"], str)
            and re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]{8,24}(?:Z)?", record["fetched_at"]
            )
        ):
            return record
    elif name == "sprint_sync_failed":
        required = base | {"stage", "error_code", "exception_type"}
        if not required <= set(record) <= required | {"http_status", "location"}:
            return None
        # These enums intentionally do not come from the child or its exception text.
        if (
            record["stage"]
            not in (
                "local_setup",
                "hotlist",
                "exam_read",
                "exam_fetch",
                "exam_cache",
                "session",
                "collection_lock",
                "collector",
                "prepare",
                "publish",
            )
            or record["error_code"]
            not in (
                "official_collection_failed",
                "new_attempt_required",
                "uncertain_submission",
                "review_mismatch",
                "public_source_failed",
                "media_failed",
                "conversion_failed",
                "store_failed",
                "incomplete_snapshot",
                "local_io_failed",
                "invalid_data",
                "missing_field",
                "invalid_type",
                "runtime_failed",
                "invalid_attribute",
                "unexpected_error",
                "session_rejected",
            )
            or record["exception_type"]
            not in (
                "CollectionError",
                "NewAttemptRequired",
                "UncertainSubmission",
                "ReviewMismatch",
                "NinefenSourceError",
                "NinefenAssetError",
                "NinefenContentError",
                "SprintStoreError",
                "IncompleteSprintError",
                "OSError",
                "ValueError",
                "KeyError",
                "TypeError",
                "RuntimeError",
                "AttributeError",
                "UnknownError",
            )
        ):
            return None
        if "http_status" in record and (
            type(record["http_status"]) is not int or not 100 <= record["http_status"] <= 599
        ):
            return None
        if "location" in record:
            location = record["location"]
            if (
                not isinstance(location, dict)
                or set(location) != {"module", "line"}
                or location["module"]
                not in (
                    "scripts/sync_exam_sprint.py",
                    "services/exam_sprint.py",
                    "services/exam_sprint_import.py",
                    "services/exam_sprint_store.py",
                    "services/ninefen_source.py",
                    "services/ninefen_session.py",
                    "services/ninefen_content.py",
                    "services/ninefen_assets.py",
                    "services/practice_library_offline.py",
                )
                or type(location["line"]) is not int
                or not 1 <= location["line"] <= 100000
            ):
                return None
        return record
    return None


class _DiagnosticCapture:
    """Bound memory/log volume while draining both child pipes without raw logs."""

    def __init__(self, stage):
        self.stage = stage
        self.bytes_seen = 0
        self.events_seen = 0
        self.buffers = {}
        self.limited = False

    def feed(self, stream, chunk):
        remaining = MAX_DIAGNOSTIC_BYTES - self.bytes_seen
        self.bytes_seen += len(chunk)
        if len(chunk) > remaining:
            chunk = chunk[: max(0, remaining)]
            if not self.limited:
                event("child_output_limited", stage=self.stage)
                self.limited = True
        buffer, dropping = self.buffers.get(stream, (b"", False))
        pieces = chunk.split(b"\n")
        for index, piece in enumerate(pieces):
            if len(buffer) + len(piece) > MAX_DIAGNOSTIC_LINE:
                buffer, dropping = b"", True
            if not dropping:
                buffer += piece
            if index < len(pieces) - 1:
                record = None if dropping else _safe_diagnostic(buffer)
                if record is not None and self.events_seen < MAX_DIAGNOSTIC_EVENTS:
                    event("child_diagnostic", stage=self.stage, diagnostic=record)
                    self.events_seen += 1
                elif record is not None and not self.limited:
                    event("child_output_limited", stage=self.stage)
                    self.limited = True
                buffer, dropping = b"", False
        self.buffers[stream] = (buffer, dropping)


def due_week(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("Aware time required")
    local = now.astimezone(ZONE)
    due = (local - timedelta(days=local.weekday())).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    if local < due:
        due -= timedelta(days=7)
    return due.date().isoformat()


def system_timezone_is_shanghai() -> bool:
    try:
        return str(Path("/etc/localtime").resolve()).endswith("/Asia/Shanghai")
    except OSError:
        return False


def read_private_json(path: Path) -> dict:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise ValueError("Owned mode-600 JSON required")
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise ValueError("Control file too large")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Control object required")
    return payload


def write_private_json(path: Path, payload: dict):
    fd, temporary = tempfile.mkstemp(prefix=".weekly-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def event(action: str, **values):
    # Never emit a config/session value or raw child output.
    print(
        json.dumps({"time": datetime.now(ZONE).isoformat(), "event": action, **values}), flush=True
    )


def _stage(command: list[str], root: Path, state_dir: Path, timeout: int) -> int:
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    environment.update(
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        EXAM_SPRINT_STATE_DIR=str(state_dir),
    )
    stage = {"sync_exam_sprint.py": "sync", "publish_exam_sprint.py": "publish"}.get(
        Path(command[1]).name if len(command) > 1 else "", "unknown"
    )
    capture = _DiagnosticCapture(stage)
    try:
        with (
            subprocess.Popen(
                command,
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as child,
            selectors.DefaultSelector() as selector,
        ):
            deadline = time.monotonic() + timeout
            for pipe in (child.stdout, child.stderr):
                selector.register(pipe, selectors.EVENT_READ)
            try:
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    available = selector.select(min(remaining, 0.2))
                    if not available and child.poll() is not None:
                        break
                    for key, _mask in available:
                        chunk = os.read(key.fd, MAX_DIAGNOSTIC_LINE)
                        if chunk:
                            capture.feed(key.fd, chunk)
                        else:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                return child.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                event("child_stage_timeout", stage=stage)
                return 124
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
    except OSError:
        event("child_stage_unavailable", stage=stage)
        return 126


def _session_file_version(path):
    info = path.lstat()
    return {
        "device": info.st_dev,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
        "size": info.st_size,
    }


def _renew_session_if_due(state_path, state, session_file, now, *, manual_resume=False):
    """Persist the attempt before normal renewal; log only closed, safe codes."""
    previous = state.get("session_renewal", {})
    if not isinstance(previous, dict):
        raise ValueError("Invalid session renewal state")
    attempted_at = previous.get("last_attempt_at")
    if attempted_at is not None and (type(attempted_at) is not int or attempted_at <= 0):
        raise ValueError("Invalid session renewal attempt time")
    if manual_resume:
        # The explicit recovery operation is separate from the automatic daily
        # schedule. Require a replaced login file, never retry the rejected file.
        version = _session_file_version(session_file)
        previous_version = previous.get("session_file_version")
        unchanged = (
            previous_version == version
            if previous_version is not None
            else (attempted_at is not None and version["mtime_ns"] // 1_000_000_000 <= attempted_at)
        )
        if unchanged:
            if previous.get("login_required") is False and previous.get("status") in (
                "renewed",
                "skipped_recent",
            ):
                event("session_recovery_not_needed")
                return True
            event("session_login_required", error_code="replace_session_before_resume")
            return False
    else:
        if previous.get("login_required") is True:
            event("session_login_required", error_code="manual_login_required")
            return False
        if attempted_at is not None and now - attempted_at < SESSION_RENEWAL_INTERVAL:
            return True
    renewal = dict(previous)
    renewal.update(
        last_attempt_at=now,
        status="attempting",
        error_code=None,
        login_required=manual_resume,
        session_file_version=_session_file_version(session_file),
    )
    renewal.pop("http_status", None)
    state["session_renewal"] = renewal
    write_private_json(state_path, state)
    try:
        result = renew_session_file(session_file, now=now)
        if (
            not isinstance(result, dict)
            or result.get("status") not in ("renewed", "skipped_recent")
            or type(result.get("renewed_at")) is not int
            or not 0 < result["renewed_at"] <= now
            or (
                result["status"] == "renewed"
                and type(result.get("durability_confirmed")) is not bool
            )
        ):
            raise RenewalError("Invalid renewal summary")
    except AuthenticationRejected as exc:
        renewal.update(
            status="login_required", error_code="authentication_rejected", login_required=True
        )
        if type(exc.http_status) is int and exc.http_status in (401, 403):
            renewal["http_status"] = exc.http_status
        write_private_json(state_path, state)
        event("session_login_required", error_code="authentication_rejected")
        return False
    except (RenewalError, OSError, ValueError, TypeError) as exc:
        code = getattr(exc, "reason_code", "renewal_failed")
        if code not in ("owner_missing", "owner_mismatch"):
            code = "renewal_failed"
        blocked = code in ("owner_missing", "owner_mismatch") or manual_resume
        renewal.update(
            status="login_required" if blocked else "failed",
            error_code=code,
            login_required=blocked,
        )
        write_private_json(state_path, state)
        event("session_login_required" if blocked else "session_renewal_failed", error_code=code)
        # A transient renewal failure does not assert that the existing token is
        # rejected. The normal sync still enforces authentication and its own cap.
        return not blocked and not manual_resume
    if manual_resume and result["status"] != "renewed":
        # A recent local timestamp is not an authentication check. Recovery must
        # observe a live, owner-verified renewal before unblocking automatic work.
        renewal.update(
            status="login_required", error_code="live_renewal_required", login_required=True
        )
        write_private_json(state_path, state)
        event("session_login_required", error_code="live_renewal_required")
        return False
    renewal.update(
        status=result["status"],
        last_success_at=result["renewed_at"],
        error_code=None,
        login_required=False,
        session_file_version=_session_file_version(session_file),
    )
    if "durability_confirmed" in result:
        renewal["durability_confirmed"] = result["durability_confirmed"]
    write_private_json(state_path, state)
    event("session_renewal_completed")
    return True


def run_due(
    root: Path,
    *,
    now: datetime | None = None,
    check_only: bool = False,
    resume_session_after_login: bool = False,
) -> int:
    root = root.absolute()
    info = root.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("Runtime must be an owned mode-700 directory")
    config = read_private_json(root / "weekly-config.json")
    if config.get("schema_version") != 1 or config.get("enabled") is not True:
        event("disabled")
        return 0
    if not system_timezone_is_shanghai():
        event("timezone_mismatch")
        return 2
    state_dir = root / "instance" / "exam_sprint"
    session_file = state_dir / "private" / "session.json"
    state_path = root / "weekly-state.json"
    state = read_private_json(state_path)
    if state.get("initialized_after_publish") is not True:
        event("not_initialized")
        return 2
    current_time = now or datetime.now(ZONE)
    week = due_week(current_time)
    last = state.get("last_success_week")
    if not isinstance(last, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last):
        raise ValueError("Initial published week required")
    attempts = state.get("attempts", {}).get(week, 0)
    if type(attempts) is not int or attempts < 0:
        raise ValueError("Invalid retry counter")
    if check_only:
        if resume_session_after_login:
            raise ValueError("Check mode cannot recover a session")
        if last >= week:
            event("already_published", week=week)
            return 0
        if attempts >= MAX_WEEKLY_ATTEMPTS:
            event("retry_limit_reached", week=week)
            return 2
        event("due", week=week, attempts=attempts)
        return 0
    renewal_enabled = config.get("session_renewal_enabled") is True
    if resume_session_after_login:
        if not renewal_enabled:
            raise ValueError("Session renewal must be explicitly enabled")
        return (
            0
            if _renew_session_if_due(
                state_path,
                state,
                session_file,
                int(current_time.timestamp()),
                manual_resume=True,
            )
            else 2
        )
    pending_publication = state.get("pending_publication_week") == week
    authenticated = True
    if renewal_enabled and not pending_publication:
        authenticated = _renew_session_if_due(
            state_path,
            state,
            session_file,
            int(current_time.timestamp()),
        )
    if last >= week:
        event("already_published", week=week)
        return 0 if authenticated else 2
    if attempts >= MAX_WEEKLY_ATTEMPTS:
        event("retry_limit_reached", week=week)
        return 2
    if not authenticated:
        event("sync_deferred_for_login", week=week)
        return 2
    python = config.get("python")
    if not isinstance(python, str) or not Path(python).is_absolute() or not Path(python).is_file():
        raise ValueError("Stable Python executable required")
    if any(
        str(Path(python).absolute()).startswith(prefix) for prefix in ("/tmp/", "/private/tmp/")
    ):
        raise ValueError("Temporary interpreter is not supported")
    # Publishing an already verified candidate does not need a source session.
    if not pending_publication:
        session_info = session_file.lstat()
        if (
            not stat.S_ISREG(session_info.st_mode)
            or session_info.st_uid != os.getuid()
            or stat.S_IMODE(session_info.st_mode) != 0o600
        ):
            raise ValueError("Explicit local mode-600 session required")
    if (
        config.get("host") != "root@47.110.45.193"
        or config.get("remote_root") != "/root/apps/studytracker"
    ):
        raise ValueError("Unexpected publication destination")
    for script in ("sync_exam_sprint.py", "publish_exam_sprint.py"):
        if not (root / "scripts" / script).is_file():
            raise ValueError("Runtime code is incomplete")
    state["attempts"] = {week: attempts + 1}
    write_private_json(state_path, state)
    if state.get("pending_publication_week") != week:
        event("sync_started", week=week, attempt=attempts + 1)
        code = _stage(
            [
                python,
                str(root / "scripts" / "sync_exam_sprint.py"),
                "--output-dir",
                str(state_dir),
                "--session-file",
                str(session_file),
                "--allow-new-attempts",
            ],
            root,
            state_dir,
            10800,
        )
        if code:
            event("sync_failed", week=week, exit_code=code)
            return 1
        snapshot = state_dir / "current.json"
        if (
            snapshot.is_symlink()
            or not snapshot.is_file()
            or snapshot.stat().st_size > 2 * 1024 * 1024
        ):
            raise ValueError("Sync did not leave a bounded complete snapshot")
        state["pending_publication_week"] = week
        state["pending_snapshot_sha256"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        write_private_json(state_path, state)
    snapshot = state_dir / "current.json"
    if (
        snapshot.is_symlink()
        or not snapshot.is_file()
        or snapshot.stat().st_size > 2 * 1024 * 1024
        or hashlib.sha256(snapshot.read_bytes()).hexdigest() != state.get("pending_snapshot_sha256")
    ):
        raise ValueError("Pending publication snapshot changed; manual review required")
    event("publish_started", week=week)
    code = _stage(
        [
            python,
            str(root / "scripts" / "publish_exam_sprint.py"),
            "--state-dir",
            str(state_dir),
            "--host",
            config["host"],
            "--remote-root",
            config["remote_root"],
        ],
        root,
        state_dir,
        1800,
    )
    if code:
        event("publish_failed", week=week, exit_code=code)
        return 1
    state.update(last_success_week=week, last_success_at=datetime.now(ZONE).isoformat())
    state.pop("pending_publication_week", None)
    state.pop("pending_snapshot_sha256", None)
    write_private_json(state_path, state)
    event("published", week=week)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT)
    parser.add_argument(
        "--check", action="store_true", help="Report due status without network work"
    )
    parser.add_argument(
        "--resume-session-after-login",
        action="store_true",
        help="Verify a replaced bound session only; does not sync, publish, or reset weekly retries",
    )
    args = parser.parse_args(argv)
    if args.check and args.resume_session_after_login:
        parser.error("--check cannot be combined with --resume-session-after-login")
    try:
        root = args.runtime_dir.absolute()
        if args.check:
            return run_due(root, check_only=True)
        fd = os.open(root / ".weekly.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as lock:
            info = os.fstat(lock.fileno())
            if (
                info.st_uid != os.getuid()
                or not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise ValueError("Invalid weekly lock")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                event("already_running")
                return 0
            return run_due(root, resume_session_after_login=args.resume_session_after_login)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        event("invalid_local_configuration")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
