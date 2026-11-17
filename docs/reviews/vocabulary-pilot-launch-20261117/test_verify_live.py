"""Local synthetic/mocked safety tests; never contact a production service."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "live_verifier", Path(__file__).with_name("verify_live.py")
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class LiveVerificationTest(unittest.TestCase):
    def test_schema_inspection_before_after_migration_is_readonly(self):
        from tests.test_vocabulary_checkpoint_migration import CheckpointMigrationTest, migration

        fixture = CheckpointMigrationTest()
        fixture.setUp()
        try:
            for expected in ("legacy", "sources_v1"):
                if expected == "sources_v1":
                    # Only this temporary synthetic fixture is migrated.
                    with contextlib.closing(sqlite3.connect(fixture.path)) as writable:
                        migration.migrate_connection(writable, apply=True)
                before = fixture.path.read_bytes()
                observations = []
                with contextlib.closing(
                    runner.readonly_connection(fixture.path, observations)
                ) as conn:
                    conn.execute("BEGIN")
                    result = migration.inspect(conn)
                    self.assertEqual(result["schema_version"], expected)
                    self.assertEqual(conn.total_changes, 0)
                self.assertEqual(before, fixture.path.read_bytes())
                self.assertEqual(observations[0]["blocked"], 0)
        finally:
            fixture.tearDown()

    def test_selection_is_private_exact_four_or_six_and_does_not_guess(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            path.write_text(json.dumps({"student_ids": [6, 5, 4, 3, 2, 1]}))
            path.chmod(0o600)
            self.assertEqual(runner.load_selection(path), [1, 2, 3, 4, 5, 6])
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                runner.load_selection(path)
            path.chmod(0o600)
            path.write_text(json.dumps({"student_ids": [4, 3, 2, 1]}))
            self.assertEqual(runner.load_selection(path, 4), [1, 2, 3, 4])
            with self.assertRaises(ValueError):
                runner.load_selection(path)
            with self.assertRaises(ValueError):
                runner.load_selection(path, 5)
            path.chmod(0o600)
            path.write_text(json.dumps({"student_ids": [1, 1, 2, 3, 4, 5]}))
            with self.assertRaises(ValueError):
                runner.load_selection(path)

    def test_manifest_checks_every_path_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = {}
            for name in runner.REQUIRED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
                manifest[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest))
            self.assertEqual(runner.manifest_check(root, path)[0], len(runner.REQUIRED))
            manifest["../escape"] = "0" * 64
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                runner.manifest_check(root, path)

    def test_readonly_guard_blocks_writes_ddl_attach_and_setting_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.db"
            with contextlib.closing(sqlite3.connect(path)) as seed:
                seed.execute("CREATE TABLE fixture (value INTEGER)")
            before = path.read_bytes()
            observations = []
            conn = runner.readonly_connection(path, observations)
            try:
                for sql in (
                    "INSERT INTO fixture VALUES (1)",
                    "DROP TABLE fixture",
                    "ATTACH ':memory:' AS other",
                    "PRAGMA query_only=OFF",
                    "PRAGMA journal_mode=WAL",
                    "SELECT load_extension('secret')",
                    "BEGIN IMMEDIATE",
                ):
                    with self.assertRaises(sqlite3.DatabaseError):
                        conn.execute(sql)
                self.assertEqual(conn.total_changes, 0)
                self.assertEqual(conn.execute("PRAGMA query_only").fetchone()[0], 1)
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "delete")
                self.assertTrue(conn.execute("PRAGMA table_info(fixture)").fetchall())
            finally:
                conn.close()
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(observations[0]["blocked"], 6)
            missing = Path(folder) / "missing.db"
            with self.assertRaises(sqlite3.OperationalError):
                runner.readonly_connection(missing, [])
            self.assertFalse(missing.exists())

    def test_enrollment_requires_exact_selected_set_and_started_date(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE vocabulary_review_policy_enrollment(student_id,enabled,starts_at)"
        )
        conn.executemany(
            "INSERT INTO vocabulary_review_policy_enrollment VALUES (?,1,?)",
            [(i, "2026-11-16 00:00:00") for i in range(1, 7)],
        )
        now = datetime(2026, 11, 17)
        self.assertTrue(runner.enrollment_check(conn, list(range(1, 7)), True, now)["ok"])
        conn.execute(
            "INSERT INTO vocabulary_review_policy_enrollment VALUES (7,1,'2026-11-16 00:00:00')"
        )
        self.assertFalse(runner.enrollment_check(conn, list(range(1, 7)), True, now)["ok"])
        conn.execute("UPDATE vocabulary_review_policy_enrollment SET enabled=0")
        self.assertTrue(runner.enrollment_check(conn, list(range(1, 7)), False, now)["ok"])
        conn.execute(
            "UPDATE vocabulary_review_policy_enrollment SET enabled=1,starts_at='2026-11-18 00:00:00' WHERE student_id=1"
        )
        self.assertFalse(runner.enrollment_check(conn, list(range(1, 7)), True, now)["ok"])
        conn.close()

    def test_four_selected_never_accepts_an_enabled_student_outside_the_list(self):
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(
                "CREATE TABLE vocabulary_review_policy_enrollment(student_id,enabled,starts_at)"
            )
            conn.executemany(
                "INSERT INTO vocabulary_review_policy_enrollment VALUES (?,1,?)",
                [(i, "2026-11-16 00:00:00") for i in range(1, 5)],
            )
            now = datetime(2026, 11, 17)
            self.assertTrue(runner.enrollment_check(conn, [1, 2, 3, 4], True, now)["ok"])
            conn.execute(
                "INSERT INTO vocabulary_review_policy_enrollment VALUES (5,1,'2026-11-16 00:00:00')"
            )
            result = runner.enrollment_check(conn, [1, 2, 3, 4], True, now)
            self.assertFalse(result["ok"])
            self.assertEqual(result["selected_enabled"], 4)
            self.assertEqual(result["other_enabled"], 1)
        finally:
            conn.close()

    def test_expected_size_cli_is_explicit_and_defaults_to_six(self):
        common = ["--expected-head", "test", "--manifest", "fixture", "--selection", "private"]
        for expected, extra in ((6, []), (4, ["--expected-size", "4"])):
            with (
                patch.object(runner, "run", return_value={"ok": True}) as run,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(runner.main(common + extra), 0)
                self.assertEqual(run.call_args.args[0].expected_size, expected)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            runner.main(common + ["--expected-size", "5"])

    def test_effective_environment_and_worker_start_are_checked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            proc = root / "proc"
            (proc / "100/task/100").mkdir(parents=True)
            (proc / "101").mkdir()
            (proc / "100/task/100/children").write_text("101")
            (proc / "stat").write_text("btime 1000\n")
            fields = ["0"] * 20
            fields[19] = "2000"
            (proc / "101/stat").write_text("101 (gunicorn worker) " + " ".join(fields))
            (root / ".env").write_text(
                "VOCABULARY_ERROR_REVIEW_ENABLED=true\nSECRET=never-output\n"
            )
            os.utime(root / ".env", (900, 900))
            for pid in (100, 101):
                (proc / f"{pid}/environ").write_bytes(b"SECRET=not-exported\0")
            with patch.object(runner.os, "sysconf", return_value=100):
                config, result = runner.runtime_settings(
                    root, {"systemd": {"MainPID": "100"}}, True, 900, runner.DEFAULTS, proc
                )
                self.assertTrue(result["ok"])
                self.assertTrue(config[runner.PREFIX + "ENABLED"])
                self.assertNotIn("SECRET", json.dumps(result))
                self.assertNotIn("never-output", json.dumps(result))
                (proc / "101/environ").write_bytes(b"VOCABULARY_ERROR_REVIEW_ENABLED=false\0")
                self.assertFalse(
                    runner.runtime_settings(
                        root, {"systemd": {"MainPID": "100"}}, True, 900, runner.DEFAULTS, proc
                    )[1]["ok"]
                )
                (proc / "101/environ").write_bytes(b"")
                os.utime(root / ".env", (1030, 1030))
                self.assertFalse(
                    runner.runtime_settings(
                        root, {"systemd": {"MainPID": "100"}}, True, 900, runner.DEFAULTS, proc
                    )[1]["ok"]
                )

    def test_launch_checks_runtime_thread_worker_overrides(self):
        root = Path("/synthetic")
        good = "{ argv[]=/synthetic/venv/bin/gunicorn -c gunicorn.conf.py --threads 6 -k gthread app:app ; ignore_errors=no ; }"
        self.assertTrue(runner.launch_verified(root, good, str(root)))
        for bad in (
            good.replace("--threads 6", "--threads=8"),
            good.replace("-k gthread", "-kgevent"),
            good.replace("gunicorn.conf.py", "other.py"),
        ):
            self.assertFalse(runner.launch_verified(root, bad, str(root)))
        self.assertFalse(runner.launch_verified(root, good, "/other"))

    def test_errors_never_print_sensitive_exception_values(self):
        output = io.StringIO()
        with (
            patch.object(runner, "run", side_effect=ValueError("secret student=123 token=abcdef")),
            contextlib.redirect_stdout(output),
        ):
            status = runner.main(
                [
                    "--expected-head",
                    "test",
                    "--manifest",
                    "secret-path",
                    "--selection",
                    "private-path",
                ]
            )
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())["error_type"], "ValueError")
        for secret in ("123", "abcdef", "secret", "private-path"):
            self.assertNotIn(secret, output.getvalue())

    def test_real_minimal_flask_replay_is_readonly_on_and_off(self):
        from models import db
        from tests.test_vocabulary_error_review_integration import ErrorReviewIntegrationTest

        fixture = ErrorReviewIntegrationTest()
        fixture.setUp()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.db"
            try:
                with fixture.app.app_context():
                    fixture._enable()
                    with contextlib.closing(sqlite3.connect(path)) as destination:
                        db.session.connection().connection.driver_connection.backup(destination)
                    db.session.remove()
                before = path.read_bytes()
                previous = runner.load_module(
                    "live_prior_test",
                    ROOT / "docs/reviews/miniprogram-entry-20261116/verify_production_entry.py",
                )
                for enabled in (False, True):
                    observations = []
                    config = {
                        runner.PREFIX + "ENABLED": enabled,
                        **{runner.PREFIX + key: value for key, value in runner.DEFAULTS.items()},
                    }
                    result = runner.replay(
                        ROOT, path, [fixture.student_id], config, enabled, observations, previous
                    )
                    self.assertTrue(result["all_ok"], result)
                    self.assertEqual(result["sample_count"], 1)
                    self.assertEqual(sum(row["blocked"] for row in observations), 0)
                    self.assertNotIn("student_id", json.dumps(result))
                self.assertEqual(before, path.read_bytes())
            finally:
                fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
