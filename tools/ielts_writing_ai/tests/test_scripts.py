"""start.sh / stop.sh / status.sh must only ever signal a verified instance of this tool.

Every process touched here is created by the test itself (sleep / python decoys and
trial servers on a temporary data dir and a free port).
"""

import os
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
            }
        )
        return env

    def run_script(self, name, env=None):
        return subprocess.run(
            ["bash", str(BIN / name)],
            cwd=REPO_ROOT,
            env=env or self.env,
            capture_output=True,
            text=True,
            timeout=60,
        )

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
