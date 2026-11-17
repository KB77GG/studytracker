import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.select_vocabulary_pilot import choose, connect_readonly, save_private, select


class PilotSelectionTests(unittest.TestCase):
    def test_balanced_stable_distinct_and_not_enough(self):
        rows = [{"student_id": i, "errors": i, "answers": 10} for i in range(1, 9)]
        groups = choose(list(reversed(rows)))
        self.assertEqual([row["student_id"] for row in groups["lower_error"]], [1, 2, 3])
        self.assertEqual([row["student_id"] for row in groups["higher_error"]], [8, 7, 6])
        with self.assertRaises(ValueError):
            choose(rows[:3], 4)

    def test_private_manifest_no_overwrite_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "selection.json"
            save_private(path, {"student_ids": [3]})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                save_private(path, {"student_ids": [4]})
            self.assertEqual(json.loads(path.read_text())["student_ids"], [3])

    def test_filters_formal_activity_pending_enrollment_assignment_and_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.db"
            connection = sqlite3.connect(path)
            connection.executescript("""
                CREATE TABLE user(id INTEGER,role TEXT,is_active INTEGER,username TEXT);
                CREATE TABLE student_profile(id INTEGER,user_id INTEGER,is_deleted INTEGER,primary_teacher_id INTEGER);
                CREATE TABLE teacher_student_link(teacher_id INTEGER,student_id INTEGER);
                CREATE TABLE vocabulary_learning_question(student_id INTEGER,task_id INTEGER,sense_id INTEGER,dimension TEXT,first_attempt_id TEXT,score_eligible INTEGER,remediation_kind TEXT,first_is_correct INTEGER);
                CREATE TABLE dictation_record(student_id INTEGER,task_id INTEGER,attempt_id TEXT,created_at TEXT,is_first_attempt INTEGER,is_correct INTEGER,response_kind TEXT);
                CREATE TABLE vocabulary_review_session(student_id INTEGER,status TEXT);
                CREATE TABLE vocabulary_review_policy_enrollment(student_id INTEGER);
            """)
            connection.execute("INSERT INTO user VALUES(90,'teacher',1,'secret-teacher')")
            for student in range(1, 10):
                connection.execute(
                    "INSERT INTO user VALUES(?,'student',1,'secret-name')", (student,)
                )
                connection.execute(
                    "INSERT INTO student_profile VALUES(?,?,0,?)",
                    (student + 100, student, 90 if student != 9 else None),
                )
                for answer in range(30):
                    args = (
                        student,
                        answer // 10,
                        answer,
                        "meaning_recall",
                        str(answer),
                        1,
                        None,
                        int(answer >= student),
                    )
                    connection.execute(
                        "INSERT INTO vocabulary_learning_question VALUES(?,?,?,?,?,?,?,?)", args
                    )
                    connection.execute(
                        "INSERT INTO dictation_record VALUES(?,?,?,?,?,?,?)",
                        (
                            student,
                            answer // 10,
                            str(answer),
                            "2026-11-16 10:00:00",
                            1,
                            int(answer >= student),
                            "answer",
                        ),
                    )
            connection.execute("INSERT INTO vocabulary_review_session VALUES(7,'active')")
            connection.execute("INSERT INTO vocabulary_review_policy_enrollment VALUES(8)")
            connection.commit()
            connection.close()
            conn = connect_readonly(path)
            try:
                output, manifest = select(conn, datetime(2026, 11, 17), size=6)
                self.assertEqual(manifest["student_ids"], [1, 2, 3, 4, 5, 6])
                self.assertEqual(output["eligible_students"], 6)
                self.assertEqual(output["database_changes"], 0)
                self.assertNotIn("student_ids", json.dumps(output))
                self.assertNotIn("secret", json.dumps(output))
                for sql in (
                    "SELECT username FROM user",
                    "UPDATE user SET is_active=0",
                    "PRAGMA journal_mode=WAL",
                ):
                    with self.assertRaises(sqlite3.DatabaseError):
                        conn.execute(sql)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
