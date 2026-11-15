#!/usr/bin/env python3
"""Run a due, initialized local week; publish only after complete validation."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("Asia/Shanghai")
LABEL = "com.sagepath.studytracker-exam-sprint"
MAX_WEEKLY_ATTEMPTS = 3


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
    try:
        return subprocess.run(
            command,
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        ).returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 126


def run_due(root: Path, *, now: datetime | None = None, check_only: bool = False) -> int:
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
    week = due_week(now or datetime.now(ZONE))
    last = state.get("last_success_week")
    if not isinstance(last, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last):
        raise ValueError("Initial published week required")
    if last >= week:
        event("already_published", week=week)
        return 0
    attempts = state.get("attempts", {}).get(week, 0)
    if type(attempts) is not int or attempts < 0:
        raise ValueError("Invalid retry counter")
    if attempts >= MAX_WEEKLY_ATTEMPTS:
        event("retry_limit_reached", week=week)
        return 2
    if check_only:
        event("due", week=week, attempts=attempts)
        return 0
    python = config.get("python")
    if not isinstance(python, str) or not Path(python).is_absolute() or not Path(python).is_file():
        raise ValueError("Stable Python executable required")
    if any(
        str(Path(python).absolute()).startswith(prefix) for prefix in ("/tmp/", "/private/tmp/")
    ):
        raise ValueError("Temporary interpreter is not supported")
    # Validate only permissions here; only the source session client reads the token.
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
    args = parser.parse_args(argv)
    try:
        root = args.runtime_dir.absolute()
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
            return run_due(root, check_only=args.check)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        event("invalid_local_configuration")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
