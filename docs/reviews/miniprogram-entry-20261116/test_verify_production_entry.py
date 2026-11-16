"""Synthetic, file-backed safety checks for the production read-only runner."""

import ast
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load(
    "entry_acceptance", Path(__file__).with_name("verify_production_entry.py")
)
fixture = load("entry_fixture", ROOT / "scripts/benchmark_vocabulary_review.py")


class ReadOnlyAcceptanceTest(unittest.TestCase):
    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.db"
            with self.assertRaises(sqlite3.OperationalError):
                runner.readonly_connection(path, [])
            self.assertFalse(path.exists())

    def test_sql_write_attach_and_pragma_changes_are_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.db"
            with sqlite3.connect(path) as seed:
                seed.execute("CREATE TABLE fixture (value TEXT)")
                seed.execute("INSERT INTO fixture VALUES ('synthetic')")
            before = path.read_bytes()
            observations = []
            connection = runner.readonly_connection(path, observations)
            try:
                for sql in (
                    "INSERT INTO fixture VALUES ('bad')",
                    "UPDATE fixture SET value='bad'",
                    "DELETE FROM fixture",
                    "DROP TABLE fixture",
                    "PRAGMA query_only=OFF",
                    "ATTACH ':memory:' AS another",
                ):
                    with self.assertRaises(sqlite3.DatabaseError):
                        connection.execute(sql)
                self.assertEqual(connection.total_changes, 0)
                self.assertEqual(
                    connection.execute("SELECT value FROM fixture").fetchone()[0],
                    "synthetic",
                )
                self.assertEqual(
                    connection.execute("PRAGMA query_only").fetchone()[0], 1
                )
                self.assertEqual(observations[0]["blocked"], 6)
            finally:
                connection.close()
            self.assertEqual(before, path.read_bytes())

    def test_service_replay_succeeds_and_database_bytes_are_unchanged(self):
        from models import db

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.db"
            seed_app = fixture._make_app()
            with seed_app.app_context():
                db.create_all()
                user, task = fixture._seed(30)
                ids = user.id, task.id
                with sqlite3.connect(path) as destination:
                    db.session.connection().connection.driver_connection.backup(
                        destination
                    )
                db.session.remove()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            observations = []
            app = runner.make_readonly_app(ROOT, path, observations)
            result = runner.check_case(
                app, "synthetic_case", *ids, now=fixture.BENCHMARK_NOW
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["calls"]["preflight"]["result"]["due_count"], 30)
            self.assertEqual(result["calls"]["summary"]["result"]["due_count"], 30)
            self.assertEqual(sum(item["blocked"] for item in observations), 0)
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertFalse(
                any(name in sys.modules for name in runner.PROHIBITED_IMPORTS)
            )

    def test_result_whitelist_excludes_identifiers_tokens_and_bodies(self):
        safe = runner.safe_payload(
            dict(
                ok=True,
                task_id=7,
                student_id=8,
                active_session_id=9,
                active_session_token="synthetic-secret",
                student_name="synthetic-name",
                error="unsafe",
                message="unsafe",
                due_count=3,
            )
        )
        encoded = json.dumps(safe)
        self.assertTrue(safe["active_batch_present"])
        self.assertEqual(safe["due_count"], 3)
        for forbidden in (
            "task_id",
            "student_id",
            "session_id",
            "token",
            "synthetic-secret",
            "synthetic-name",
            "unsafe",
        ):
            self.assertNotIn(forbidden, encoded)

    def test_log_parser_uses_only_requested_time_windows(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "access.log"
            log.write_text(
                "\n".join(
                    [
                        'x [15/Nov/2026:17:12:45 +0800] "GET /api/miniprogram/student/tasks/123/vocabulary-queue HTTP/1.1" 200 1',
                        'x [16/Nov/2026:10:44:32 +0800] "GET /api/miniprogram/student/tasks/456 HTTP/1.1" 200 1',
                        'x [16/Nov/2026:10:45:32 +0800] "GET /api/miniprogram/student/tasks/999 HTTP/1.1" 200 1',
                    ]
                )
            )
            self.assertEqual(
                runner.matching_tasks(folder), {"case_a": {123}, "case_b": {456}}
            )

    def test_ambiguous_log_cases_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fixture.db"
            with sqlite3.connect(path) as seed:
                seed.execute(
                    "CREATE TABLE vocabulary_learning_flow(student_id INT, task_id INT)"
                )
                seed.execute(
                    "INSERT INTO vocabulary_learning_flow VALUES (1,123),(2,124)"
                )
            (Path(folder) / "access.log").write_text(
                "\n".join(
                    f'x [15/Nov/2026:17:12:45 +0800] "GET /api/miniprogram/student/tasks/{task_id} HTTP/1.1" 200 1'
                    for task_id in (123, 124)
                )
            )
            with self.assertRaises(RuntimeError):
                runner.select_cases(path, folder)

    def test_python_310_syntax_and_prohibited_import_guard(self):
        ast.parse(Path(runner.__file__).read_text(), feature_version=(3, 10))
        guard = runner.RejectProhibitedImports()
        for name in ("app", "config", "whisper", "torch.nn", "kokoro"):
            with self.assertRaises(ImportError):
                guard.find_spec(name)
        self.assertIsNone(guard.find_spec("collections"))


if __name__ == "__main__":
    unittest.main()
