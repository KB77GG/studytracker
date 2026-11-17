"""Local files and mocked process commands only; never stop a real service."""

import contextlib
import importlib.util
import io
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "pilot_rollout", Path(__file__).with_name("activate_and_restart.py")
)
rollout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rollout)


class RolloutTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.selection = self.root / "private.json"
        self.env = self.root / ".env"
        self.original = b"# secret comment\r\nSECRET_KEY='PRIVATE_TOKEN_123'\r\nVOCABULARY_ERROR_REVIEW_ENABLED=false\r\nOTHER=\xe4\xb8\xad\xe6\x96\x87\r\n VOCABULARY_ERROR_REVIEW_ENABLED = off\r\nTAIL=no-newline"
        self.env.write_bytes(self.original)
        self.env.chmod(0o640)
        self.calls = []
        self.activation_returncode = 0
        self.start_returncode = 0
        self.stop_error = None
        self.start_error = None

    def tearDown(self):
        self.temp.cleanup()

    def subprocess(self, command, **kwargs):
        self.calls.append(command)
        if command[:2] == ["systemctl", "stop"]:
            if self.stop_error:
                raise self.stop_error
            return subprocess.CompletedProcess(command, 0)
        if command[:2] == ["systemctl", "start"]:
            if self.start_error:
                raise self.start_error
            return subprocess.CompletedProcess(command, self.start_returncode)
        self.assertIn("scripts/activate_vocabulary_pilot.py", command)
        self.assertIn("--apply", command)
        self.assertEqual(self.env.read_bytes(), self.original)
        return subprocess.CompletedProcess(
            command,
            self.activation_returncode,
            json.dumps({"ok": not self.activation_returncode, "enrolled_count": 4}),
        )

    def execute(self, head="expected", dirty=""):
        with (
            patch.object(rollout.subprocess, "check_output", side_effect=[head, dirty]),
            patch.object(rollout.subprocess, "run", side_effect=self.subprocess),
        ):
            return rollout.rollout(self.root, self.selection, "expected")

    def test_enrollment_failure_restarts_and_preserves_original_flag(self):
        self.activation_returncode = 1
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertFalse(result["feature_flag_written"])
        self.assertTrue(result["service_start_command_succeeded"])
        self.assertEqual(self.env.read_bytes(), self.original)
        self.assertEqual(self.calls[-1][:2], ["systemctl", "start"])

    def test_success_changes_only_target_lines_preserves_bytes_mode_owner(self):
        before = self.env.stat()
        result = self.execute()
        self.assertTrue(result["ok"])
        expected = b"# secret comment\r\nSECRET_KEY='PRIVATE_TOKEN_123'\r\nOTHER=\xe4\xb8\xad\xe6\x96\x87\r\nTAIL=no-newline\nVOCABULARY_ERROR_REVIEW_ENABLED=true\n"
        self.assertEqual(self.env.read_bytes(), expected)
        after = self.env.stat()
        self.assertEqual(
            (stat.S_IMODE(after.st_mode), after.st_uid, after.st_gid),
            (0o640, before.st_uid, before.st_gid),
        )
        backup = self.root / "vocabulary-20261117.env-before"
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertNotIn("PRIVATE_TOKEN_123", json.dumps(result))

    def test_wrong_head_or_tracked_source_never_stops_or_writes_backup(self):
        for head, dirty in (("other", ""), ("expected", " M models.py")):
            with self.assertRaises(ValueError):
                self.execute(head, dirty)
            self.assertEqual(self.calls, [])
            self.assertEqual(self.env.read_bytes(), self.original)
            self.assertFalse((self.root / "vocabulary-20261117.env-before").exists())

    def test_stop_exception_still_starts_without_enrollment_or_config_change(self):
        self.stop_error = subprocess.TimeoutExpired("private-stop-command", 30)
        result = self.execute()
        self.assertFalse(result["ok"])
        self.assertTrue(result["service_start_command_succeeded"])
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.env.read_bytes(), self.original)

    def test_start_failure_and_timeout_are_explicit_not_false_success(self):
        for failure in (1, "timeout"):
            with self.subTest(failure=failure):
                self.env.write_bytes(self.original)
                self.start_returncode = 1 if failure == 1 else 0
                self.start_error = (
                    subprocess.TimeoutExpired("PRIVATE_TOKEN_123", 30)
                    if failure == "timeout"
                    else None
                )
                result = self.execute()
                self.assertFalse(result["ok"])
                self.assertFalse(result["service_start_command_succeeded"])
                self.assertEqual(result["error"], "service_start_failed")
                self.assertTrue(result["feature_flag_written"])
                self.assertNotIn("PRIVATE_TOKEN_123", json.dumps(result))

    def test_write_failure_restarts_and_top_level_exceptions_are_redacted(self):
        with patch.object(rollout, "atomic_write", side_effect=OSError("PRIVATE_TOKEN_123")):
            result = self.execute()
        self.assertFalse(result["ok"])
        self.assertTrue(result["service_start_command_succeeded"])
        self.assertEqual(self.env.read_bytes(), self.original)
        with (
            patch.object(rollout, "rollout", side_effect=ValueError("PRIVATE_TOKEN_123")),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            status = rollout.main(["--expected-head", "expected", "--apply"])
        self.assertEqual(status, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])
        self.assertNotIn("PRIVATE_TOKEN_123", output.getvalue())


if __name__ == "__main__":
    unittest.main()
