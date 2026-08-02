import importlib.util
import io
import sqlite3
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory


def _load_migration():
    path = Path(__file__).resolve().parents[1] / "scripts" / "migrate_mock_exam_review.py"
    spec = importlib.util.spec_from_file_location("migrate_mock_exam_review_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MockExamReviewMigrationTest(unittest.TestCase):
    def test_sqlite_migration_is_idempotent_and_only_binds_one_active_profile(self):
        migration = _load_migration()
        with TemporaryDirectory() as tmp:
            database = str(Path(tmp) / "review.db")
            conn = sqlite3.connect(database)
            conn.executescript(
                """
                CREATE TABLE student_profile (
                    id INTEGER PRIMARY KEY,
                    full_name VARCHAR(64) NOT NULL,
                    is_deleted BOOLEAN NOT NULL DEFAULT 0
                );
                CREATE TABLE mock_exam_session (
                    id INTEGER PRIMARY KEY,
                    student_name VARCHAR(64) NOT NULL,
                    student_profile_id INTEGER
                );
                INSERT INTO student_profile (id, full_name, is_deleted) VALUES
                    (1, '唯一学生', 0),
                    (2, '已删除学生', 1),
                    (3, '歧义学生', 0),
                    (4, '歧义学生', 0),
                    (5, '歧义学生', 1);
                INSERT INTO mock_exam_session (id, student_name) VALUES
                    (1, '唯一学生'),
                    (2, '已删除学生'),
                    (3, '歧义学生'),
                    (4, '不存在学生');
                """
            )
            conn.commit()
            conn.close()

            first_output = io.StringIO()
            with redirect_stdout(first_output):
                self.assertEqual(migration.main(["--database", database]), 0)
            second_output = io.StringIO()
            with redirect_stdout(second_output):
                self.assertEqual(migration.main(["--database", database]), 0)

            conn = sqlite3.connect(database)
            rows = dict(
                conn.execute(
                    "SELECT id, student_profile_id FROM mock_exam_session ORDER BY id"
                ).fetchall()
            )
            self.assertEqual(rows, {1: 1, 2: None, 3: None, 4: None})
            session_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(mock_exam_session)")
            }
            review_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(mock_exam_review)")
            }
            edit_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(mock_exam_review_edit_session)")
            }
            self.assertIn("student_profile_id", session_columns)
            self.assertIn("annotations_json", review_columns)
            self.assertIn("link_version", review_columns)
            self.assertIn("token_hash", edit_columns)
            self.assertIn(
                "ix_mock_exam_session_student_profile_id",
                {row[1] for row in conn.execute("PRAGMA index_list(mock_exam_session)")},
            )
            conn.close()

            self.assertIn("backfilled=1", first_output.getvalue())
            self.assertIn("ambiguous_active_names=1", first_output.getvalue())
            self.assertIn("missing_active_profiles=2", first_output.getvalue())
            self.assertIn("backfilled=0", second_output.getvalue())
            for private_name in ("唯一学生", "已删除学生", "歧义学生", "不存在学生"):
                self.assertNotIn(private_name, first_output.getvalue())
                self.assertNotIn(private_name, second_output.getvalue())


if __name__ == "__main__":
    unittest.main()
