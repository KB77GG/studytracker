"""Run a command while holding an exclusive kernel lock (``fcntl.flock``).

start.sh and stop.sh re-execute themselves through this wrapper::

    python -I tools/ielts_writing_ai/ctl_lock.py <lock-file> <timeout-seconds> -- <cmd...>

The lock is held by this process for the child's whole lifetime and released by the
kernel when it exits - normally, by Ctrl-C or by SIGKILL - so there is never a stale
lock to detect or take over. Taking the lock is a single atomic system call, so two
scripts can never both hold it.

Runs as a plain script (standard library only, no package import), so stop.sh works
even in an environment where Flask is not installed. The lock descriptor is not
inheritable, so the server started inside the critical section does not keep it.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys
import time

EXIT_BUSY = 75  # EX_TEMPFAIL
USAGE = "usage: ctl_lock.py <lock-file> <timeout-seconds> -- <command> [args...]"


def acquire(lock_path: str, timeout: float) -> int | None:
    """Return a locked descriptor, or None if the lock stayed busy until the timeout."""
    directory = os.path.dirname(lock_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)  # O_CLOEXEC by default
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                return None
            time.sleep(0.1)


def main(argv: list[str] | None = None) -> int:
    sys.stderr.reconfigure(errors="backslashreplace")
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 4 or args[2] != "--":
        print(USAGE, file=sys.stderr)
        return 2
    lock_path, command = args[0], args[3:]
    try:
        timeout = float(args[1])
    except ValueError:
        print(USAGE, file=sys.stderr)
        return 2
    fd = acquire(lock_path, timeout)
    if fd is None:
        print(
            f"另一个启动或停止操作仍在进行（锁：{lock_path}），{timeout:g} 秒内没有结束，"
            "本次没有做任何改动，请稍后再试。",
            file=sys.stderr,
        )
        return EXIT_BUSY
    try:
        env = dict(os.environ, IWA_CTL_LOCK_HELD=lock_path)
        return subprocess.call(command, env=env, close_fds=True)
    except KeyboardInterrupt:
        return 130
    finally:
        os.close(fd)  # the kernel would release it on exit anyway


if __name__ == "__main__":
    sys.exit(main())
