"""Take an exclusive kernel lock (``fcntl.flock``), then become the locked command.

start.sh and stop.sh re-execute themselves through this program::

    python -I tools/ielts_writing_ai/ctl_lock.py <lock-file> <timeout-seconds> -- <cmd...>

After taking the lock it places the locked descriptor on fd 9 and ``exec``s the
command, so the lock is held by the very process that runs the start/stop logic
(same PID) - there is no separate launcher whose death could release it early.
Children that the operation starts (curl, sleep, ps, ...) inherit fd 9 as well, so
the lock stays held while any part of the operation is still running, and the
kernel releases it once the last of them has exited - including after SIGKILL.
The long-running server is launched with fd 9 closed (see start.sh) and never
holds the lock.

Standard library only and run as a plain script (no package import), so stop.sh
works even in an environment where Flask is not installed.
"""

from __future__ import annotations

import fcntl
import os
import sys
import time

EXIT_BUSY = 75  # EX_TEMPFAIL
LOCK_FD = 9  # start.sh closes this fd for the background server
USAGE = "usage: ctl_lock.py <lock-file> <timeout-seconds> -- <command> [args...]"


def acquire(lock_path: str, timeout: float) -> int | None:
    """Return a locked descriptor, or None if the lock stayed busy until the timeout."""
    directory = os.path.dirname(lock_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
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
    if fd != LOCK_FD:
        os.dup2(fd, LOCK_FD)  # same open file description, so the same lock
        os.close(fd)
    os.set_inheritable(LOCK_FD, True)
    env = dict(
        os.environ,
        IWA_CTL_LOCK_HELD=lock_path,
        IWA_CTL_LOCK_PID=str(os.getpid()),  # exec keeps the PID: proves we are the holder
        IWA_CTL_LOCK_FD=str(LOCK_FD),
    )
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        os.execvpe(command[0], command, env)
    except OSError as exc:
        print(f"无法执行 {command[0]}：{exc}", file=sys.stderr)
        return 127
    return 0  # not reached


if __name__ == "__main__":
    sys.exit(main())
