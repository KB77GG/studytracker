"""Offline scheduling/install checks; no real sessions, network, or launchd calls."""

import contextlib
import hashlib
import io
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts import install_exam_sprint_launchd as installer
from scripts import run_exam_sprint_weekly as runner
from scripts import sync_exam_sprint as sync
from services.ninefen_auth import AuthenticationRejected, RenewalError
from services.ninefen_session import CollectionError
from services.ninefen_source import NinefenSourceError

ROOT = Path(__file__).resolve().parents[1]


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.failure = {
            "diagnostic_version": 1,
            "event": "sprint_sync_failed",
            "stage": "prepare",
            "error_code": "session_rejected",
            "exception_type": "CollectionError",
            "http_status": 401,
            "location": {"module": "services/ninefen_session.py", "line": 190},
        }

    def test_whitelist_rejects_unexpected_fields_and_values(self):
        self.assertEqual(runner._safe_diagnostic(json.dumps(self.failure).encode()), self.failure)
        for field, value in (
            ("message", "synthetic-secret"),
            ("stage", "synthetic-secret"),
            ("error_code", "synthetic-secret"),
            ("exception_type", "synthetic-secret"),
            ("http_status", "synthetic-secret"),
            ("http_status", True),
            ("location", {"module": "/private/synthetic-secret", "line": 1}),
            ("location", {"module": "services/ninefen_session.py", "line": "synthetic-secret"}),
        ):
            with self.subTest(field=field, value=value):
                self.assertIsNone(
                    runner._safe_diagnostic(
                        json.dumps(dict(self.failure, **{field: value})).encode()
                    )
                )
        for raw in (b"not JSON synthetic-secret", b"[1,2]", b"{" * 4096, b"x" * 4097):
            self.assertIsNone(runner._safe_diagnostic(raw))

    def test_fragmented_lines_and_oversize_suffix_never_leak(self):
        raw = json.dumps(self.failure).encode() + b"\n"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            capture = runner._DiagnosticCapture("sync")
            capture.feed(1, b"synthetic-secret\n" + raw[:30])
            capture.feed(1, raw[30:])
            capture.feed(2, b"x" * (runner.MAX_DIAGNOSTIC_LINE + 1))
            capture.feed(2, raw)  # A valid-looking suffix of an oversized line is dropped.
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["diagnostic"], self.failure)
        self.assertNotIn("synthetic-secret", output.getvalue())
        self.assertTrue(
            all(len(value[0]) <= runner.MAX_DIAGNOSTIC_LINE for value in capture.buffers.values())
        )

    def test_capture_bounds_total_bytes_and_events(self):
        raw = json.dumps(self.failure).encode() + b"\n"
        for limit, value in (("MAX_DIAGNOSTIC_BYTES", len(raw) * 2), ("MAX_DIAGNOSTIC_EVENTS", 2)):
            output = io.StringIO()
            with patch.object(runner, limit, value), contextlib.redirect_stdout(output):
                capture = runner._DiagnosticCapture("sync")
                for _ in range(20):
                    capture.feed(1, raw)
            rows = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(sum(row["event"] == "child_diagnostic" for row in rows), 2)
            self.assertEqual(sum(row["event"] == "child_output_limited" for row in rows), 1)

    def test_subprocess_forwards_only_safe_json_from_both_pipes(self):
        script = self.root / "sync_exam_sprint.py"
        script.write_text(
            "import json, sys\n"
            "print('synthetic-secret', flush=True)\n"
            f"print({json.dumps(self.failure)!r}, file=sys.stderr, flush=True)\n"
            "sys.stdout.write('x' * 1000000)\n"
            "raise SystemExit(7)\n"
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = runner._stage([sys.executable, str(script)], self.root, self.root, 5)
        self.assertEqual(code, 7)
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertIn(self.failure, [row.get("diagnostic") for row in rows])
        self.assertNotIn("synthetic-secret", output.getvalue())
        self.assertLess(len(output.getvalue()), 2048)

    def test_subprocess_timeout_and_spawn_error_remain_fixed_codes(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(
                runner._stage(
                    [sys.executable, "-c", "import time; time.sleep(2)"], self.root, self.root, 0.05
                ),
                124,
            )
            self.assertEqual(
                runner._stage([str(self.root / "synthetic-secret")], self.root, self.root, 1), 126
            )
        self.assertNotIn("synthetic-secret", output.getvalue())
        self.assertEqual(
            [json.loads(line)["event"] for line in output.getvalue().splitlines()],
            ["child_stage_timeout", "child_stage_unavailable"],
        )

    def test_sync_failure_preserves_old_snapshot_and_has_no_exception_text(self):
        previous = b'{"old":"snapshot"}'
        (self.root / "current.json").write_bytes(previous)
        stderr = io.StringIO()
        with (
            patch.object(sync, "fetch_public_hotlist", return_value={}),
            patch.object(sync, "ranked_rows", return_value=[]),
            patch.object(
                sync,
                "prepare_complete_snapshot",
                side_effect=CollectionError("synthetic-secret", http_status=401),
            ),
            patch.object(sync, "publish_snapshot") as publish,
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(sync.main(["--output-dir", str(self.root)]), 1)
        record = json.loads(stderr.getvalue())
        self.assertEqual(record["error_code"], "session_rejected")
        self.assertEqual(record["http_status"], 401)
        self.assertEqual(record["stage"], "prepare")
        self.assertEqual(record["location"]["module"], "scripts/sync_exam_sprint.py")
        self.assertIsNotNone(runner._safe_diagnostic(stderr.getvalue().encode()))
        self.assertNotIn("synthetic-secret", stderr.getvalue())
        self.assertEqual((self.root / "current.json").read_bytes(), previous)
        publish.assert_not_called()

    def test_sync_public_source_failure_has_distinct_safe_stage(self):
        stderr = io.StringIO()
        with (
            patch.object(
                sync, "fetch_public_hotlist", side_effect=NinefenSourceError("synthetic-secret")
            ),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(sync.main(["--output-dir", str(self.root)]), 1)
        record = json.loads(stderr.getvalue())
        self.assertEqual(record["stage"], "hotlist")
        self.assertEqual(record["error_code"], "public_source_failed")
        self.assertNotIn("synthetic-secret", stderr.getvalue())

    def test_successful_sync_events_pass_the_same_closed_boundary(self):
        def prepare(*args, progress, **kwargs):
            progress(1, "123", "reused")
            return {
                "subjects": {"reading": [{"items": [{"mapping": {"target_id": "test"}}]}]},
                "fetched_at": "2026-11-23T06:00:00+08:00",
            }

        stdout = io.StringIO()
        with (
            patch.object(sync, "fetch_public_hotlist", return_value={}),
            patch.object(sync, "ranked_rows", return_value=[]),
            patch.object(sync, "prepare_complete_snapshot", side_effect=prepare),
            patch.object(sync, "publish_snapshot") as publish,
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(sync.main(["--output-dir", str(self.root), "--dry-run"]), 0)
        records = [
            runner._safe_diagnostic(line.encode()) for line in stdout.getvalue().splitlines()
        ]
        self.assertEqual(
            [record["event"] for record in records],
            ["sprint_sync_progress", "sprint_sync_completed"],
        )
        self.assertEqual(records[1]["verified_practice_links"], 1)
        publish.assert_not_called()


class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        (self.root / "scripts").mkdir()
        for name in ("sync_exam_sprint.py", "publish_exam_sprint.py"):
            (self.root / "scripts" / name).write_text("# test only\n")
        self.state_dir = self.root / "instance" / "exam_sprint"
        (self.state_dir / "private").mkdir(parents=True)
        (self.state_dir / "private" / "session.json").write_text("{}")
        (self.state_dir / "private" / "session.json").chmod(0o600)
        (self.state_dir / "current.json").write_text('{"snapshot":"synthetic"}')
        runner.write_private_json(
            self.root / "weekly-config.json",
            {
                "schema_version": 1,
                "enabled": True,
                "python": sys.executable,
                "host": "root@47.110.45.193",
                "remote_root": "/root/apps/studytracker",
            },
        )
        runner.write_private_json(
            self.root / "weekly-state.json",
            {
                "initialized_after_publish": True,
                "last_success_week": "2026-11-09",
                "attempts": {},
            },
        )
        self.tz = patch.object(runner, "system_timezone_is_shanghai", return_value=True)
        self.tz.start()
        self.addCleanup(self.tz.stop)
        self.log = contextlib.redirect_stdout(io.StringIO())
        self.log.__enter__()
        self.addCleanup(self.log.__exit__, None, None, None)
        self.now = datetime.fromisoformat("2026-11-16T06:00:00+08:00")

    def state(self):
        return runner.read_private_json(self.root / "weekly-state.json")

    def test_due_boundary_and_sleep_catchup(self):
        self.assertEqual(
            runner.due_week(datetime.fromisoformat("2026-11-16T05:59:59+08:00")), "2026-11-09"
        )
        self.assertEqual(runner.due_week(self.now), "2026-11-16")
        self.assertEqual(
            runner.due_week(datetime.fromisoformat("2026-11-19T18:00:00+08:00")), "2026-11-16"
        )

    @patch.object(runner, "_stage")
    def test_first_published_week_does_no_work(self, stage):
        state = self.state()
        state["last_success_week"] = "2026-11-16"
        runner.write_private_json(self.root / "weekly-state.json", state)
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    def test_uninitialized_and_wrong_timezone_refuse(self, stage):
        state = self.state()
        state["initialized_after_publish"] = False
        runner.write_private_json(self.root / "weekly-state.json", state)
        self.assertEqual(runner.run_due(self.root, now=self.now), 2)
        with patch.object(runner, "system_timezone_is_shanghai", return_value=False):
            self.assertEqual(runner.run_due(self.root, now=self.now), 2)
        stage.assert_not_called()

    @patch.object(runner, "_stage", return_value=0)
    def test_only_publish_success_advances_week_and_rerun_is_read_only(self, stage):
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(stage.call_count, 2)
        self.assertIn("--allow-new-attempts", stage.call_args_list[0].args[0])
        self.assertNotIn("--session-file", stage.call_args_list[1].args[0])
        self.assertEqual(self.state()["last_success_week"], "2026-11-16")
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(stage.call_count, 2)

    @patch.object(runner, "_stage", return_value=1)
    def test_sync_failure_preserves_week_and_is_bounded(self, stage):
        for _ in range(3):
            self.assertEqual(runner.run_due(self.root, now=self.now), 1)
        self.assertEqual(runner.run_due(self.root, now=self.now), 2)
        self.assertEqual(stage.call_count, 3)
        self.assertEqual(self.state()["last_success_week"], "2026-11-09")

    @patch.object(runner, "_stage", side_effect=[0, 1, 0])
    def test_publish_retry_does_not_sync_or_submit_again(self, stage):
        self.assertEqual(runner.run_due(self.root, now=self.now), 1)
        self.assertEqual(self.state()["last_success_week"], "2026-11-09")
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(stage.call_count, 3)
        self.assertIn("publish_exam_sprint.py", stage.call_args_list[2].args[0][1])

    @patch.object(runner, "_stage", side_effect=[0, 1])
    def test_changed_pending_candidate_is_never_published(self, stage):
        runner.run_due(self.root, now=self.now)
        (self.state_dir / "current.json").write_text("{}")
        with self.assertRaises(ValueError):
            runner.run_due(self.root, now=self.now)
        self.assertEqual(stage.call_count, 2)

    @patch.object(runner, "_stage")
    def test_check_only_does_no_work(self, stage):
        self.assertEqual(runner.run_due(self.root, now=self.now, check_only=True), 0)
        stage.assert_not_called()
        self.assertEqual(self.state()["attempts"], {})

    def test_private_controls_reject_symlink_and_mode(self):
        target = self.root / "weekly-config.json"
        target.chmod(0o644)
        with self.assertRaises(ValueError):
            runner.read_private_json(target)
        target.chmod(0o600)
        alias = self.root / "alias"
        alias.symlink_to(target)
        with self.assertRaises(OSError):
            runner.read_private_json(alias)

    @patch.object(installer, "install")
    def test_installer_defaults_to_plan(self, install):
        self.assertEqual(installer.main([]), 0)
        install.assert_not_called()

    def test_plist_and_repo_template_match(self):
        expected = installer.build_plist(Path("__RUNTIME_DIR__"), "__PYTHON__")
        actual = plistlib.loads(
            (ROOT / "deploy/exam-sprint/com.sagepath.studytracker-exam-sprint.plist").read_bytes()
        )
        self.assertEqual(expected, actual)
        self.assertEqual(expected["StartInterval"], 1800)
        self.assertEqual(expected["StartCalendarInterval"], {"Weekday": 1, "Hour": 6, "Minute": 0})
        self.assertTrue(expected["RunAtLoad"])

    def test_copy_tree_refuses_symlinks_and_keeps_private_mode(self):
        source = self.root / "source"
        source.mkdir()
        (source / "private").mkdir()
        (source / "private" / "session.json").write_text("{}")
        dest = self.root / "destination"
        installer._copy_tree(source, dest)
        self.assertEqual((dest / "private").stat().st_mode & 0o777, 0o700)
        self.assertEqual((dest / "private" / "session.json").stat().st_mode & 0o777, 0o600)
        (source / "alias").symlink_to(source / "private" / "session.json")
        with self.assertRaises(ValueError):
            installer._copy_tree(source, self.root / "other")


class SessionRenewalScheduleTests(unittest.TestCase):
    setUp = WeeklyTests.setUp
    state = WeeklyTests.state

    def enable(self, *, published=True):
        config = runner.read_private_json(self.root / "weekly-config.json")
        config["session_renewal_enabled"] = True
        runner.write_private_json(self.root / "weekly-config.json", config)
        state = self.state()
        if published:
            state["last_success_week"] = runner.due_week(self.now)
        runner.write_private_json(self.root / "weekly-state.json", state)

    def summary(self, timestamp=None, *, durable=True):
        return {
            "status": "renewed",
            "renewed_at": timestamp or int(self.now.timestamp()),
            "durability_confirmed": durable,
        }

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_published_week_renews_daily_and_persists_attempt_before_call(self, renew, stage):
        self.enable()
        timestamp = int(self.now.timestamp())

        def success(path, *, now):
            self.assertEqual(path, self.state_dir / "private/session.json")
            self.assertEqual(self.state()["session_renewal"]["last_attempt_at"], now)
            self.assertEqual(self.state()["session_renewal"]["status"], "attempting")
            return self.summary(now)

        renew.side_effect = success
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        later = datetime.fromtimestamp(timestamp + 86399, runner.ZONE)
        self.assertEqual(runner.run_due(self.root, now=later), 0)
        self.assertEqual(renew.call_count, 1)
        next_day = datetime.fromtimestamp(timestamp + 86400, runner.ZONE)
        self.assertEqual(runner.run_due(self.root, now=next_day), 0)
        self.assertEqual(renew.call_count, 2)
        self.assertEqual(self.state()["attempts"], {})
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_check_never_renews_or_changes_any_state_or_creates_lock(self, renew, stage):
        self.enable(published=False)
        state_path = self.root / "weekly-state.json"
        original = state_path.read_bytes()
        self.assertEqual(runner.run_due(self.root, now=self.now, check_only=True), 0)
        self.assertEqual(runner.main(["--runtime-dir", str(self.root), "--check"]), 0)
        self.assertEqual(state_path.read_bytes(), original)
        self.assertFalse((self.root / ".weekly.lock").exists())
        renew.assert_not_called()
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_auth_rejection_blocks_until_explicit_login_recovery_without_leaking(
        self, renew, stage
    ):
        self.enable(published=False)
        renew.side_effect = AuthenticationRejected("synthetic-secret", http_status=401)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(runner.run_due(self.root, now=self.now), 2)
            later = datetime.fromtimestamp(int(self.now.timestamp()) + 86400, runner.ZONE)
            self.assertEqual(runner.run_due(self.root, now=later), 2)
        self.assertEqual(renew.call_count, 1)
        state = self.state()
        self.assertEqual(state["session_renewal"]["error_code"], "authentication_rejected")
        self.assertTrue(state["session_renewal"]["login_required"])
        self.assertEqual(state["attempts"], {})
        self.assertEqual(state["last_success_week"], "2026-11-09")
        self.assertNotIn("synthetic-secret", output.getvalue())
        self.assertNotIn("synthetic-secret", json.dumps(state))
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_owner_binding_errors_require_login_not_guessing(self, renew, stage):
        for code in ("owner_missing", "owner_mismatch"):
            with self.subTest(code=code):
                self.enable(published=False)
                state = self.state()
                state.pop("session_renewal", None)
                runner.write_private_json(self.root / "weekly-state.json", state)
                renew.side_effect = RenewalError("synthetic-secret", reason_code=code)
                self.assertEqual(runner.run_due(self.root, now=self.now), 2)
                self.assertEqual(self.state()["session_renewal"]["error_code"], code)
                self.assertTrue(self.state()["session_renewal"]["login_required"])
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_network_failure_preserves_session_and_has_daily_not_unbounded_retries(
        self, renew, stage
    ):
        self.enable()
        session = self.state_dir / "private/session.json"
        original = session.read_bytes()
        renew.side_effect = RenewalError("synthetic-secret")
        for _ in range(3):
            self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        self.assertEqual(renew.call_count, 1)
        self.assertEqual(session.read_bytes(), original)
        self.assertEqual(self.state()["session_renewal"]["error_code"], "renewal_failed")
        self.assertFalse(self.state()["session_renewal"]["login_required"])
        tomorrow = datetime.fromtimestamp(int(self.now.timestamp()) + 86400, runner.ZONE)
        runner.run_due(self.root, now=tomorrow)
        self.assertEqual(renew.call_count, 2)
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_committed_renewal_summary_stays_private_and_is_not_retried_for_fsync_warning(
        self, renew, stage
    ):
        self.enable()
        renew.return_value = {
            **self.summary(durable=False),
            "token": "synthetic-secret",
            "user": "synthetic-owner",
        }
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(runner.run_due(self.root, now=self.now), 0)
            self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        renew.assert_called_once()
        state = self.state()
        self.assertFalse(state["session_renewal"]["durability_confirmed"])
        self.assertEqual(state["session_renewal"]["last_success_at"], int(self.now.timestamp()))
        for text in (output.getvalue(), json.dumps(state)):
            self.assertNotIn("synthetic-secret", text)
            self.assertNotIn("synthetic-owner", text)
        self.assertNotIn("durability_confirmed", output.getvalue())
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_retry_budget_stays_exhausted_even_when_daily_renewal_succeeds(self, renew, stage):
        self.enable(published=False)
        state = self.state()
        state["attempts"] = {"2026-11-16": 3}
        runner.write_private_json(self.root / "weekly-state.json", state)
        renew.return_value = self.summary()
        self.assertEqual(runner.run_due(self.root, now=self.now), 2)
        renew.assert_called_once()
        self.assertEqual(self.state()["attempts"], {"2026-11-16": 3})
        stage.assert_not_called()

    @patch.object(runner, "_stage", return_value=0)
    @patch.object(runner, "renew_session_file")
    def test_pending_candidate_publishes_without_renewal_or_even_source_session(self, renew, stage):
        self.enable(published=False)
        state = self.state()
        state.update(
            pending_publication_week="2026-11-16",
            pending_snapshot_sha256=hashlib.sha256(
                (self.state_dir / "current.json").read_bytes()
            ).hexdigest(),
        )
        state["session_renewal"] = {
            "login_required": True,
            "last_attempt_at": int(self.now.timestamp()),
            "error_code": "authentication_rejected",
        }
        runner.write_private_json(self.root / "weekly-state.json", state)
        (self.state_dir / "private/session.json").unlink()
        self.assertEqual(runner.run_due(self.root, now=self.now), 0)
        renew.assert_not_called()
        stage.assert_called_once()
        self.assertIn("publish_exam_sprint.py", stage.call_args.args[0][1])
        self.assertEqual(self.state()["last_success_week"], "2026-11-16")

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_manual_login_recovery_requires_replacement_and_never_resets_weekly_attempts(
        self, renew, stage
    ):
        self.enable(published=False)
        timestamp = int(self.now.timestamp())
        state = self.state()
        state["attempts"] = {"2026-11-16": 3}
        state["session_renewal"] = {
            "last_attempt_at": timestamp,
            "login_required": True,
            "error_code": "authentication_rejected",
        }
        runner.write_private_json(self.root / "weekly-state.json", state)
        session = self.state_dir / "private/session.json"
        os.utime(session, (timestamp - 1, timestamp - 1))
        self.assertEqual(
            runner.run_due(self.root, now=self.now, resume_session_after_login=True), 2
        )
        renew.assert_not_called()
        os.utime(session, (timestamp + 1, timestamp + 1))
        renew.return_value = self.summary(timestamp + 2)
        later = datetime.fromtimestamp(timestamp + 2, runner.ZONE)
        self.assertEqual(runner.run_due(self.root, now=later, resume_session_after_login=True), 0)
        self.assertFalse(self.state()["session_renewal"]["login_required"])
        self.assertEqual(self.state()["attempts"], {"2026-11-16": 3})
        self.assertEqual(self.state()["last_success_week"], "2026-11-09")
        stage.assert_not_called()

    def blocked_recovery_state(self):
        self.enable(published=False)
        timestamp = int(self.now.timestamp())
        state = self.state()
        state["attempts"] = {"2026-11-16": 3}
        state["session_renewal"] = {
            "last_attempt_at": timestamp,
            "login_required": True,
            "error_code": "authentication_rejected",
        }
        runner.write_private_json(self.root / "weekly-state.json", state)
        session = self.state_dir / "private/session.json"
        os.utime(session, (timestamp + 1, timestamp + 1))
        return datetime.fromtimestamp(timestamp + 2, runner.ZONE)

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_manual_recovery_cannot_unblock_from_only_a_recent_local_timestamp(self, renew, stage):
        later = self.blocked_recovery_state()
        renew.return_value = {"status": "skipped_recent", "renewed_at": int(self.now.timestamp())}
        self.assertEqual(runner.run_due(self.root, now=later, resume_session_after_login=True), 2)
        self.assertTrue(self.state()["session_renewal"]["login_required"])
        self.assertEqual(self.state()["session_renewal"]["error_code"], "live_renewal_required")
        tomorrow = datetime.fromtimestamp(int(later.timestamp()) + 86400, runner.ZONE)
        self.assertEqual(runner.run_due(self.root, now=tomorrow), 2)
        renew.assert_called_once()
        stage.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file", side_effect=KeyboardInterrupt)
    def test_interrupted_manual_recovery_keeps_auth_block_and_cannot_run_sync(self, renew, stage):
        later = self.blocked_recovery_state()
        with self.assertRaises(KeyboardInterrupt):
            runner.run_due(self.root, now=later, resume_session_after_login=True)
        self.assertTrue(self.state()["session_renewal"]["login_required"])
        self.assertEqual(self.state()["session_renewal"]["status"], "attempting")
        tomorrow = datetime.fromtimestamp(int(later.timestamp()) + 86400, runner.ZONE)
        self.assertEqual(runner.run_due(self.root, now=tomorrow), 2)
        renew.assert_called_once()
        stage.assert_not_called()

    @patch.object(runner, "renew_session_file")
    def test_manual_recovery_rejects_unchanged_file_even_with_fractional_mtime(self, renew):
        later = self.blocked_recovery_state()
        state = self.state()
        session = self.state_dir / "private/session.json"
        state["session_renewal"]["session_file_version"] = runner._session_file_version(session)
        runner.write_private_json(self.root / "weekly-state.json", state)
        self.assertEqual(runner.run_due(self.root, now=later, resume_session_after_login=True), 2)
        renew.assert_not_called()

    @patch.object(runner, "_stage")
    @patch.object(runner, "renew_session_file")
    def test_second_manual_recovery_after_atomic_token_rotation_is_a_noop(self, renew, stage):
        later = self.blocked_recovery_state()
        session = self.state_dir / "private/session.json"

        def rotate(path, *, now):
            replacement = path.parent / "synthetic-replacement.json"
            replacement.write_text('{"synthetic":"rotated"}')
            replacement.chmod(0o600)
            os.replace(replacement, path)
            return self.summary(now)

        renew.side_effect = rotate
        self.assertEqual(runner.run_due(self.root, now=later, resume_session_after_login=True), 0)
        previous = (self.root / "weekly-state.json").read_bytes()
        self.assertEqual(
            self.state()["session_renewal"]["session_file_version"],
            runner._session_file_version(session),
        )
        self.assertEqual(runner.run_due(self.root, now=later, resume_session_after_login=True), 0)
        renew.assert_called_once()
        stage.assert_not_called()
        self.assertEqual((self.root / "weekly-state.json").read_bytes(), previous)
        self.assertFalse(self.state()["session_renewal"]["login_required"])
        self.assertEqual(self.state()["attempts"], {"2026-11-16": 3})

    @patch.object(runner, "renew_session_file")
    def test_check_and_manual_recovery_are_mutually_exclusive(self, renew):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            runner.main(["--check", "--resume-session-after-login"])
        renew.assert_not_called()


class RuntimeDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.runtime = self.root / "runtime"
        self.state = self.root / "state"
        self.assets = self.root / "asset-source"
        for folder in (self.source, self.runtime, self.state, self.assets):
            folder.mkdir(mode=0o700)
        self.target_id = "synthetic_p1"
        self.folder = Path("static/listening_jijing")
        self.document = self.source / self.folder / "parts" / f"{self.target_id}.json"
        self.document.parent.mkdir(parents=True)
        self.document.write_text(
            json.dumps({"id": self.target_id, "audio": {"local_path": "audio/one.mp3"}})
        )
        (self.source / self.folder / "offline_tests.json").write_text('{"tests":[]}')
        audio = self.assets / self.folder / "audio"
        audio.mkdir(parents=True)
        (audio / "one.mp3").write_bytes(b"synthetic media bytes, not a playable asset")
        (audio / "unrelated.mp3").write_bytes(b"must not copy")
        self.mapping = {
            "subject": "listening",
            "source_id": "123",
            "target_id": self.target_id,
            "target_sha256": hashlib.sha256(self.document.read_bytes()).hexdigest(),
        }
        self._write_manifests()

    def _write_manifests(self, row_mapping=None):
        manifest = self.source / "data/exam_sprint/mappings.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"mappings": [self.mapping]}))
        (self.state / "current.json").write_text(
            json.dumps(
                {
                    "subjects": {
                        "listening": [
                            {
                                "items": [
                                    {"source_id": "123", "mapping": row_mapping or self.mapping}
                                ]
                            }
                        ]
                    }
                }
            )
        )

    def test_only_exact_reviewed_legacy_files_are_copied_privately(self):
        copied = installer._copy_legacy_dependencies(
            self.source, self.runtime, self.state, self.assets
        )
        self.assertEqual(copied, 3)
        paths = {
            p.relative_to(self.runtime).as_posix() for p in self.runtime.rglob("*") if p.is_file()
        }
        self.assertEqual(
            paths,
            {
                "static/listening_jijing/parts/synthetic_p1.json",
                "static/listening_jijing/audio/one.mp3",
                "static/listening_jijing/offline_tests.json",
            },
        )
        for path in self.runtime.rglob("*"):
            self.assertEqual(path.stat().st_mode & 0o777, 0o700 if path.is_dir() else 0o600)
        self.assertFalse((self.runtime / "instance").exists())

    def test_legacy_manifest_mismatch_or_changed_document_refuses_copy(self):
        bad = dict(self.mapping, target_id="different")
        self._write_manifests(bad)
        with self.assertRaises(ValueError):
            installer._copy_legacy_dependencies(self.source, self.runtime, self.state, self.assets)
        self._write_manifests()
        self.document.write_text('{"changed":true}')
        with self.assertRaises(ValueError):
            installer._copy_legacy_dependencies(self.source, self.runtime, self.state, self.assets)
        self.assertFalse(any(self.runtime.iterdir()))

    def test_legacy_audio_cannot_escape_explicit_asset_root(self):
        audio = self.assets / self.folder / "audio/one.mp3"
        audio.unlink()
        outside = self.root / "outside.mp3"
        outside.write_bytes(b"outside")
        audio.symlink_to(outside)
        with self.assertRaises(ValueError):
            installer._copy_legacy_dependencies(self.source, self.runtime, self.state, self.assets)
        self.assertFalse((self.runtime / self.folder / "audio/one.mp3").exists())

    def test_exact_code_copy_imports_without_original_tree_or_real_state(self):
        for relative in installer.CODE_FILES:
            installer._copy_file(ROOT / relative, self.runtime / relative)
        self.assertIn("scripts/activate_exam_sprint.py", installer.CODE_FILES)
        self.assertIn("services/ninefen_auth.py", installer.CODE_FILES)
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
        for script in (
            "sync_exam_sprint.py",
            "publish_exam_sprint.py",
            "run_exam_sprint_weekly.py",
        ):
            result = subprocess.run(
                [sys.executable, str(self.runtime / "scripts" / script), "--help"],
                cwd=self.runtime,
                env=environment,
                capture_output=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode()[:500])
        self.assertFalse((self.runtime / "instance").exists())

    def test_initial_private_root_and_session_must_be_owned_and_restricted(self):
        snapshot = {"schema_version": 1, "source": "ninefen", "subjects": {}}
        for subject, count in (("reading", 3), ("listening", 4)):
            snapshot["subjects"][subject] = [
                {
                    "part": part,
                    "items": [{"rank": rank, "source_available": False} for rank in range(1, 21)],
                }
                for part in range(1, count + 1)
            ]
        (self.state / "current.json").write_text(json.dumps(snapshot))
        private = self.state / "private"
        private.mkdir(mode=0o700)
        session = private / "session.json"
        session.write_text("{}")
        session.chmod(0o600)
        installer._validate_initial_snapshot(self.state)
        private.chmod(0o755)
        with self.assertRaises(ValueError):
            installer._validate_initial_snapshot(self.state)
        private.chmod(0o700)
        session.chmod(0o644)
        with self.assertRaises(ValueError):
            installer._validate_initial_snapshot(self.state)
        session.chmod(0o600)
        os.link(session, private / "hardlink.json")
        with self.assertRaises(ValueError):
            installer._validate_initial_snapshot(self.state)


if __name__ == "__main__":
    unittest.main()
