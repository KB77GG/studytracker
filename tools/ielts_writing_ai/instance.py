"""Single-instance guard for one trial database.

A second server pointed at the same database must not run startup recovery
(which marks queued/running work as interrupted) while the first one is still
working.  The lock is an OS-level ``flock`` on ``<db>.lock``: it is released by
the kernel when the owning process exits, so a crash never leaves a stale lock.
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import time
from pathlib import Path

from .config import ConfigError


class InstanceLocked(ConfigError):
    """Another live process already owns this trial database."""


def lock_path_for(db_path: Path) -> Path:
    return Path(str(db_path) + ".lock")


def read_owner(db_path: Path) -> dict:
    try:
        return json.loads(lock_path_for(db_path).read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return {}


class InstanceLock:
    def __init__(self, db_path: Path):
        self.path = lock_path_for(db_path)
        self.instance_id = secrets.token_hex(8)
        self._fd: int | None = None

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self, wait_seconds: float = 0.0) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        deadline = time.monotonic() + max(0.0, wait_seconds)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    owner = read_owner(Path(str(self.path)[: -len(".lock")]))
                    detail = f"（PID {owner.get('pid')}）" if owner.get("pid") else ""
                    raise InstanceLocked(
                        f"已有另一个试用工具实例{detail}在使用这个数据库，本次启动已放弃，"
                        "没有改动任何任务状态。"
                    ) from None
                time.sleep(0.1)
        # We own the lock: record who we are (informational only, never trusted for locking).
        os.ftruncate(fd, 0)
        os.write(
            fd,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "instance_id": self.instance_id,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            ).encode("utf-8"),
        )
        os.fsync(fd)
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            return
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None
