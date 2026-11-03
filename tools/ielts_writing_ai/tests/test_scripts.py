"""start.sh / stop.sh / status.sh must only ever signal a verified instance of this tool.

Every process touched here is created by the test itself (sleep / python decoys and
trial servers on a temporary data dir and a free port).

Scripts run under a UTF-8 locale (like a default macOS terminal) with every bash found
on the machine; on macOS that includes /bin/bash 3.2, which reads high bytes after an
unbraced ``$VAR`` as part of the name. Extra shells/locales can be added with
IWA_TEST_BASH, IWA_TEST_LOCALE and IWA_TEST_LOCPATH (e.g. a Latin-1 locale on Linux,
whose libc classifies 0x80-0xFF bytes like macOS does).
"""

import fcntl
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BIN = REPO_ROOT / "tools" / "ielts_writing_ai" / "bin"
CTL_LOCK = REPO_ROOT / "tools" / "ielts_writing_ai" / "ctl_lock.py"


def _utf8_locale() -> str | None:
    try:
        names = subprocess.run(["locale", "-a"], capture_output=True, text=True).stdout.split()
    except OSError:
        return None
    by_key = {n.lower().replace("-", ""): n for n in names}
    for wanted in ("en_us.utf8", "c.utf8"):
        if wanted in by_key:
            return by_key[wanted]
    return None


UTF8_LOCALE = _utf8_locale()


def _shells() -> list[str]:
    found = []
    for candidate in ("/bin/bash", shutil.which("bash"), os.environ.get("IWA_TEST_BASH")):
        if candidate and os.path.exists(candidate):
            real = os.path.realpath(candidate)
            if real not in {os.path.realpath(f) for f in found}:
                found.append(candidate)
    return found


SHELLS = _shells()
DEFAULT_BASH = SHELLS[0] if SHELLS else "bash"


def locale_env(name: str | None) -> dict:
    return {"LANG": name, "LC_ALL": name} if name else {}


def shell_variants() -> list[tuple[str, dict]]:
    variants = [(bash, locale_env(UTF8_LOCALE)) for bash in SHELLS]
    extra = os.environ.get("IWA_TEST_LOCALE")
    if extra:
        env = locale_env(extra)
        if os.environ.get("IWA_TEST_LOCPATH"):
            env["LOCPATH"] = os.environ["IWA_TEST_LOCPATH"]
        variants += [(bash, env) for bash in SHELLS]
    return variants


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def lstart(pid: int) -> str:
    out = subprocess.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
    ).stdout
    return out.strip()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


@unittest.skipUnless(shutil.which("curl") and shutil.which("ps"), "needs curl and ps")
class ScriptSafetyTest(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp(prefix="iwa-scripts-")
        self.addCleanup(shutil.rmtree, self.data_dir, ignore_errors=True)
        self.port = free_port()
        self.env = self.make_env(self.data_dir, self.port)
        self.pid_file = Path(self.data_dir) / "iwa.pid"
        self.addCleanup(self.run_script, "stop.sh")

    @staticmethod
    def make_env(data_dir, port):
        env = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
        env.update(
            {
                "IWA_ENV_FILE": "/nonexistent/iwa.env",  # never read a developer's real .env
                "IWA_DATA_DIR": data_dir,
                "IWA_PORT": str(port),
                "IWA_LOCK_WAIT": "0.5",
                "PYTHON": sys.executable,
                "PYTHONDONTWRITEBYTECODE": "1",
                **locale_env(UTF8_LOCALE),
            }
        )
        return env

    def run_script(self, name, env=None, bash=None):
        # Strict UTF-8 decoding: a message cut inside a multi-byte character fails here.
        result = subprocess.run(
            [bash or DEFAULT_BASH, str(BIN / name)],
            cwd=REPO_ROOT,
            env=env or self.env,
            capture_output=True,
            encoding="utf-8",
            errors="strict",
            timeout=90,
        )
        self.assertNotIn("unbound variable", result.stdout + result.stderr, result.stderr)
        return result

    def decoy(self, *argv):
        proc = subprocess.Popen(list(argv), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        time.sleep(0.1)
        return proc

    def write_pid_file(self, pid, started, mode="flask"):
        self.pid_file.write_text(
            f"pid={pid}\nstarted={started}\nmode={mode}\ndata_dir={self.data_dir}\n",
            encoding="utf-8",
        )

    # -- shell portability (macOS bash 3.2 + UTF-8) ---------------------------

    def test_scripts_only_use_braced_variable_expansions(self):
        unbraced = re.compile(r"\$[A-Za-z_]")
        offenders = [
            f"{path.name}:{number}: {line.strip()}"
            for path in sorted(BIN.glob("*.sh"))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if unbraced.search(line)
        ]
        self.assertEqual(offenders, [], "write ${VAR}: bash 3.2 can swallow bytes after $VAR")

    def test_every_message_path_under_each_shell_and_locale(self):
        self.assertTrue(SHELLS, "no bash found")
        for bash, extra_env in shell_variants():
            with self.subTest(bash=bash, locale=extra_env.get("LC_ALL")):
                env = {**self.env, **extra_env}
                # legacy PID file: the message that used to crash with "INSTANCE_PID\xef"
                proc = self.decoy(
                    sys.executable, "-c", "import time; time.sleep(60)", "ielts_writing_ai"
                )
                self.pid_file.write_text(f"{proc.pid}\n", encoding="utf-8")
                for script in ("stop.sh", "status.sh", "start.sh"):
                    result = self.run_script(script, env=env, bash=bash)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(f"手动执行 kill {proc.pid}，再删除", result.stdout)
                self.assertIsNone(proc.poll())
                proc.kill()
                proc.wait()
                self.pid_file.unlink()

                # start / already running / status / stop success messages
                started = self.run_script("start.sh", env=env, bash=bash)
                self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
                pid = int(re.search(r"已启动（PID (\d+)）：http", started.stdout).group(1))
                again = self.run_script("start.sh", env=env, bash=bash)
                self.assertIn(f"已在运行（PID {pid}），地址", again.stdout)
                status = self.run_script("status.sh", env=env, bash=bash)
                self.assertIn(f"运行中（PID {pid}，启动于", status.stdout)
                stopped = self.run_script("stop.sh", env=env, bash=bash)
                self.assertIn(f"已停止（PID {pid}）", stopped.stdout)
                self.assertFalse(self.pid_file.exists())

    # -- concurrent starts ----------------------------------------------------

    def lock_file(self) -> Path:
        return Path(self.data_dir) / "iwa.ctl.flock"

    def try_lock(self) -> bool:
        """True if the control lock is free right now (taken and released at once)."""
        fd = os.open(self.lock_file(), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False
        finally:
            os.close(fd)

    def test_concurrent_starts_leave_exactly_one_verified_instance(self):
        procs = [
            subprocess.Popen(
                [DEFAULT_BASH, str(BIN / "start.sh")],
                cwd=REPO_ROOT,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(5)
        ]
        outputs = []
        for proc in procs:
            out, err = proc.communicate(timeout=120)
            outputs.append((proc.returncode, out.decode("utf-8"), err.decode("utf-8")))
        started = [o for o in outputs if "已启动" in o[1]]
        self.assertEqual(len(started), 1, outputs)
        self.assertEqual(sum(1 for o in outputs if "已在运行" in o[1]), len(procs) - 1, outputs)
        self.assertTrue(all(code == 0 for code, _, _ in outputs), outputs)
        pid = int(re.search(r"已启动（PID (\d+)）", started[0][1]).group(1))
        fields = dict(
            line.split("=", 1) for line in self.pid_file.read_text().splitlines() if "=" in line
        )
        self.assertEqual(int(fields["pid"]), pid)
        self.assertEqual(self.run_script("status.sh").returncode, 0)
        # The running server must not have inherited the control lock.
        self.assertTrue(self.try_lock())

    def test_control_lock_is_mutually_exclusive_even_with_a_leftover_lock_file(self):
        # Third review: two scripts could both take over a leftover lock. With flock a
        # leftover file is just a file; only one holder can be inside at any time.
        self.lock_file().write_text("left by a crashed run", encoding="utf-8")
        inside = Path(self.data_dir) / "inside"
        body = f'mkdir "{inside}" || exit 9; sleep 0.15; rmdir "{inside}"'  # fails if overlapping
        procs = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    str(CTL_LOCK),
                    str(self.lock_file()),
                    "30",
                    "--",
                    DEFAULT_BASH,
                    "-c",
                    body,
                ]
            )
            for _ in range(8)
        ]
        codes = [proc.wait(timeout=60) for proc in procs]
        self.assertEqual(codes, [0] * len(procs))
        self.assertFalse(inside.exists())

    def test_lock_of_a_killed_holder_is_released_by_the_kernel(self):
        holder = subprocess.Popen(
            [sys.executable, "-I", str(CTL_LOCK), str(self.lock_file()), "30", "--", "sleep", "60"]
        )
        self.addCleanup(holder.wait)
        for _ in range(50):
            if not self.try_lock():
                break
            time.sleep(0.1)
        self.assertFalse(self.try_lock())  # held
        holder.kill()  # SIGKILL: no cleanup code runs
        holder.wait()
        self.assertTrue(self.try_lock())
        result = self.run_script("start.sh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_busy_lock_times_out_without_any_change(self):
        fd = os.open(self.lock_file(), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            env = {**self.env, "IWA_CTL_LOCK_TIMEOUT": "1"}
            for script in ("start.sh", "stop.sh"):
                result = self.run_script(script, env=env)
                self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
                self.assertIn("另一个启动或停止操作仍在进行", result.stderr)
            self.assertFalse(self.pid_file.exists())
        finally:
            os.close(fd)
        self.assertEqual(self.run_script("start.sh").returncode, 0)

    def test_previous_version_directory_lock_is_cleaned_up(self):
        old = Path(self.data_dir) / "iwa.ctl.lock"
        old.mkdir()
        (old / "owner").write_text("12345", encoding="utf-8")
        self.assertEqual(self.run_script("start.sh").returncode, 0)
        self.assertFalse(old.exists())

    # -- PID reuse ----------------------------------------------------------

    def test_stop_never_signals_an_unrelated_process_with_a_reused_pid(self):
        proc = self.decoy("sleep", "60")
        self.write_pid_file(proc.pid, lstart(proc.pid))  # even with a matching start time
        result = self.run_script("stop.sh")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("复用", result.stdout)
        self.assertIsNone(proc.poll())
        self.assertFalse(self.pid_file.exists())

    def test_stop_never_signals_on_start_time_mismatch(self):
        proc = self.decoy(sys.executable, "-c", "import time; time.sleep(60)", "ielts_writing_ai")
        self.write_pid_file(proc.pid, "Thu Jan  1 00:00:00 2026")
        result = self.run_script("stop.sh")
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(proc.poll())
        self.assertEqual(self.run_script("status.sh").returncode, 1)

    def test_legacy_pid_file_is_never_trusted(self):
        proc = self.decoy(sys.executable, "-c", "import time; time.sleep(60)", "ielts_writing_ai")
        self.pid_file.write_text(f"{proc.pid}\n", encoding="utf-8")
        result = self.run_script("stop.sh")
        self.assertEqual(result.returncode, 1)
        self.assertIn("旧格式", result.stdout)
        self.assertIsNone(proc.poll())
        self.assertTrue(self.pid_file.exists())  # left for the operator to inspect

    def test_stale_pid_file_is_cleaned_up(self):
        proc = subprocess.Popen(["sleep", "0"])
        proc.wait()
        self.write_pid_file(proc.pid, "Thu Jan  1 00:00:00 2026")
        result = self.run_script("stop.sh")
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.pid_file.exists())

    # -- real lifecycle -----------------------------------------------------

    def test_start_status_stop_lifecycle(self):
        started = self.run_script("start.sh")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        fields = dict(
            line.split("=", 1) for line in self.pid_file.read_text().splitlines() if "=" in line
        )
        pid = int(fields["pid"])
        self.assertEqual(fields["started"], lstart(pid))
        self.assertEqual(self.run_script("status.sh").returncode, 0)
        again = self.run_script("start.sh")
        self.assertIn("已在运行", again.stdout)

        stopped = self.run_script("stop.sh")
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        for _ in range(40):
            if not alive(pid):
                break
            time.sleep(0.1)
        self.assertFalse(alive(pid))
        self.assertFalse(self.pid_file.exists())

    def test_second_start_on_same_database_fails_and_first_keeps_running(self):
        self.assertEqual(self.run_script("start.sh").returncode, 0)
        first_pid = int(
            next(
                line.split("=", 1)[1]
                for line in self.pid_file.read_text().splitlines()
                if line.startswith("pid=")
            )
        )
        # Simulate a lost PID file: start.sh can no longer see the first instance.
        saved = self.pid_file.read_text()
        self.pid_file.unlink()
        second = self.run_script("start.sh", env={**self.env, "IWA_PORT": str(free_port())})
        self.assertEqual(second.returncode, 1, second.stdout + second.stderr)
        self.assertIn("另一个试用工具实例", second.stderr)
        self.assertTrue(alive(first_pid))
        self.pid_file.write_text(saved)

    def test_start_does_not_mistake_another_server_on_the_port_for_success(self):
        self.assertEqual(self.run_script("start.sh").returncode, 0)
        other_dir = tempfile.mkdtemp(prefix="iwa-scripts-other-")
        self.addCleanup(shutil.rmtree, other_dir, ignore_errors=True)
        other_env = self.make_env(other_dir, self.port)  # same port, different data dir
        result = self.run_script("start.sh", env=other_env)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse((Path(other_dir) / "iwa.pid").exists())
        self.assertEqual(self.run_script("status.sh").returncode, 0)


if __name__ == "__main__":
    unittest.main()
