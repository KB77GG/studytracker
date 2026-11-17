"""Local synthetic checks only; never connects to production."""

import ast
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load("stage1_readonly_audit", Path(__file__).with_name("verify_stage1.py"))
base = runner.helper(ROOT)
fixture = load(
    "synthetic_entry_fixture", ROOT / "scripts/benchmark_vocabulary_review.py"
)


class StageOneAuditTest(unittest.TestCase):
    def test_read_only_sql_fences_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.db"
            with self.assertRaises(sqlite3.OperationalError):
                base.readonly_connection(path, [])
            self.assertFalse(path.exists())
            with sqlite3.connect(path) as seed:
                seed.execute("CREATE TABLE fixture(value TEXT)")
                seed.execute("INSERT INTO fixture VALUES ('synthetic')")
            before = path.read_bytes()
            observations = []
            connection = base.readonly_connection(path, observations)
            try:
                for sql in (
                    "INSERT INTO fixture VALUES ('no')",
                    "UPDATE fixture SET value='no'",
                    "DELETE FROM fixture",
                    "DROP TABLE fixture",
                    "ATTACH ':memory:' AS another",
                    "PRAGMA query_only=OFF",
                ):
                    with self.assertRaises(sqlite3.DatabaseError):
                        connection.execute(sql)
                self.assertEqual(connection.total_changes, 0)
                self.assertEqual(
                    connection.execute("PRAGMA query_only").fetchone()[0], 1
                )
                self.assertEqual(observations[0]["blocked"], 6)
            finally:
                connection.close()
            self.assertEqual(before, path.read_bytes())

    def test_real_gate_code_skips_scan_and_keeps_synthetic_file_unchanged(self):
        from models import VocabularyLearningFlow, db

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.db"
            seed_app = fixture._make_app()
            with seed_app.app_context():
                db.create_all()
                user, task = fixture._seed(30)
                ids = user.id, task.id
                db.session.add(
                    VocabularyLearningFlow(
                        student_id=user.id,
                        task_id=task.id,
                        book_id=task.dictation_book_id,
                        vocabulary_goal="reading",
                        group_size=5,
                        total_word_count=30,
                        total_group_count=6,
                        groups_json="[]",
                        queue_token="synthetic-only",
                        started_at=fixture.BENCHMARK_NOW,
                    )
                )
                db.session.commit()
                with sqlite3.connect(path) as destination:
                    db.session.connection().connection.driver_connection.backup(
                        destination
                    )
                db.session.remove()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            observations = []
            app = base.make_readonly_app(ROOT, path, observations)
            result = runner.probe_gate(
                base, app, "synthetic_case", *ids, now=fixture.BENCHMARK_NOW
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["backlog_scan_calls"], 0)
            self.assertEqual(sum(item["blocked"] for item in observations), 0)
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())
            encoded = json.dumps(result)
            for forbidden in (
                "task_id",
                "student_id",
                "queue_token",
                "synthetic-only",
                "full_name",
            ):
                self.assertNotIn(forbidden, encoded)

    def test_log_windows_boundaries_mixed_submit_and_redaction(self):
        instant = datetime.fromisoformat("2026-11-17T07:41:05+08:00")
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "access.log").write_text(
                "\n".join(
                    [
                        'private [17/Nov/2026:07:21:04 +0800] "GET /api/miniprogram/student/tasks/123/vocabulary-queue HTTP/1.1" 500 1',
                        'private [17/Nov/2026:07:21:05 +0800] "GET /api/miniprogram/student/tasks/123/vocabulary-queue?token=SECRET HTTP/1.1" 499 1',
                        'private [17/Nov/2026:07:41:04 +0800] "POST /api/dictation/submit HTTP/1.1" 200 1',
                        'private [17/Nov/2026:07:41:05 +0800] "GET /api/miniprogram/student/tasks/456/vocabulary-queue HTTP/1.1" 200 1',
                        'private [17/Nov/2026:08:01:04 +0800] "POST /api/dictation/submit HTTP/1.1" 499 1',
                        'private [17/Nov/2026:08:01:05 +0800] "POST /api/dictation/submit HTTP/1.1" 500 1',
                    ]
                )
            )
            result = runner.summarize_logs(Path(folder), instant)
        windows = result["windows"]
        self.assertEqual(
            windows["before"]["endpoints"]["vocabulary_queue"]["status_counts"],
            {"499": 1},
        )
        self.assertEqual(
            windows["after"]["endpoints"]["vocabulary_queue"]["status_counts"],
            {"200": 1},
        )
        self.assertEqual(
            windows["after"]["endpoints"]["dictation_submit_mixed"]["status_counts"],
            {"499": 1},
        )
        for forbidden in ("SECRET", "private", "123", "456", "/api/", "token"):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_python310_syntax(self):
        ast.parse(Path(runner.__file__).read_text(), feature_version=(3, 10))


if __name__ == "__main__":
    unittest.main()
