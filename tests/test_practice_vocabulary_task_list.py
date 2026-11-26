"""Exercise the real practice list with isolated, synthetic database records."""

import hashlib
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from flask import g
from sqlalchemy import event

from models import DictationBook, StudentProfile, Task, User, VocabularyLearningFlow, db
from services.practice_vocabulary_web import task_metadata
from services.task_date_gate import SHANGHAI
from services.web_practice_tasks import web_practice_required
from tests import test_auto_student_accounts as account_tests

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class PracticeTaskListHistoricalBaselineTest(unittest.TestCase):
    """The expected response was executed from a real pre-change Git archive.

    CI needs only the committed fixture/snapshot, not Git history or network.
    Current off/on responses each come from a fresh subprocess and private DB.
    """

    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(
            (FIXTURES / "practice_task_list_f81a5e4.json").read_text(encoding="utf-8")
        )

    def test_historical_snapshot_provenance_and_coverage(self):
        self.assertEqual(
            self.snapshot["baseline_commit"], "f81a5e4a4d81282eb67b994a4cfcc5574fb78747"
        )
        for key, name in (
            ("fixture_sha256", "practice_task_list_a02.json"),
            ("capture_script_sha256", "practice_task_list_baseline.py"),
        ):
            with self.subTest(source=name):
                self.assertEqual(
                    self.snapshot[key], hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
                )
        groups = self.snapshot["response"]["groups"]
        rows = groups["assistant"] + groups["teacher"]
        self.assertEqual({row["id"] for row in rows}, {101, 102, 201, 202, 301, 302, 401, 402})
        self.assertEqual(
            {row["task_date_state"] for row in rows}, {"today", "future", "expired", "completed"}
        )
        self.assertEqual(
            {row["status"] for row in rows}, {"pending", "in_progress", "submitted", "done"}
        )
        self.assertEqual(
            {row["category"] for row in rows},
            {"精听", "听力整套", "阅读", "题型专项", "写作真题", "写作母题"},
        )

    def _assert_current_matches_history(self, flag):
        result = subprocess.run(
            [
                sys.executable,
                str(FIXTURES / "practice_task_list_baseline.py"),
                "capture",
                "--repo",
                str(ROOT),
                "--flag",
                flag,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        expected = self.snapshot["response"]
        self.assertEqual(actual.keys(), expected.keys())
        for key in expected.keys() - {"groups"}:
            self.assertEqual(actual[key], expected[key], key)
        self.assertEqual(actual["groups"].keys(), expected["groups"].keys())
        for group, expected_rows in expected["groups"].items():
            actual_rows = actual["groups"][group]
            self.assertEqual(len(actual_rows), len(expected_rows), group)
            for actual_row, expected_row in zip(actual_rows, expected_rows, strict=True):
                with self.subTest(flag=flag, group=group, task_id=expected_row["id"]):
                    # Preserve row order and compare every key/value, including
                    # URLs, score rounding, labels and the complete date gate.
                    self.assertEqual(actual_row.keys(), expected_row.keys())
                    for key, value in expected_row.items():
                        self.assertEqual(actual_row[key], value, key)
        self.assertEqual(actual, expected)  # No omitted fields or normalization.

    def test_current_flag_off_matches_real_historical_response(self):
        self._assert_current_matches_history("off")

    def test_current_flag_on_matches_real_historical_response(self):
        self._assert_current_matches_history("on")


class PracticeVocabularyTaskListTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        account_tests.AutoStudentAccountsTest.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        account_tests.AutoStudentAccountsTest.tearDownClass.__func__(cls)

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.session.remove)
        db.drop_all()
        db.create_all()
        self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = True
        self.addCleanup(self.app.config.pop, "PRACTICE_VOCABULARY_WEB_ENABLED", None)
        self.clock = patch(
            "services.task_date_gate._local_now",
            return_value=datetime(2026, 11, 26, 12, tzinfo=SHANGHAI),
        )
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.student = self.user("fixture-vocab-student", User.ROLE_STUDENT)
        self.assistant = self.user("fixture-vocab-assistant", User.ROLE_ASSISTANT)
        self.teacher = self.user("fixture-vocab-teacher", User.ROLE_TEACHER)
        self.profile = StudentProfile(full_name="网页合成学生", user_id=self.student.id)
        self.book = DictationBook(title="合成词书", created_by=self.teacher.id, word_count=8)
        db.session.add_all([self.profile, self.book])
        db.session.commit()
        self.client = self.app.test_client()
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session["practice_student_name"] = self.profile.full_name

    def user(self, name, role):
        user = User(username=name, role=role, password_hash="synthetic", is_active=True)
        db.session.add(user)
        db.session.flush()
        return user

    def task(self, **kwargs):
        fields = dict(
            student_name=self.profile.full_name,
            created_by=self.assistant.id,
            date="2026-11-26",
            category="词汇",
            dictation_book_id=self.book.id,
            vocabulary_goal="reading",
            dictation_word_start=2,
            dictation_word_end=7,
        )
        fields.update(kwargs)
        task = Task(**fields)
        db.session.add(task)
        db.session.commit()
        return task

    def groups(self):
        response = self.client.get("/api/practice/tasks")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["groups"]

    def test_assistant_and_teacher_tasks_keep_the_existing_groups(self):
        first = self.task()
        second = self.task(created_by=self.teacher.id, vocabulary_goal="comprehensive")
        groups = self.groups()
        for group, task, label in (
            ("assistant", first, "阅读词汇"),
            ("teacher", second, "综合训练"),
        ):
            self.assertEqual(len(groups[group]), 1)
            item = groups[group][0]
            self.assertEqual(item["id"], task.id)
            self.assertEqual(item["source_label"], label)
            self.assertEqual(item["url"], f"/practice/vocabulary/tasks/{task.id}")
            self.assertIn("合成词书", item["title"])
            self.assertIn("2", item["title"])
            self.assertIn("7", item["title"])
            self.assertIsNone(web_practice_required(task))
        self.assertEqual(VocabularyLearningFlow.query.count(), 0)

    def test_off_and_legacy_dictation_are_excluded(self):
        self.task()
        self.task(vocabulary_goal=None)
        self.task(vocabulary_goal="spelling_drill")
        self.task(vocabulary_goal="reading", cancelled_at=datetime(2026, 11, 26))
        self.assertEqual(len(self.groups()["assistant"]), 1)
        self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = False
        self.assertEqual(self.groups(), {"assistant": [], "teacher": []})

    def flow(self, task):
        db.session.add(
            VocabularyLearningFlow(
                student_id=self.student.id,
                task_id=task.id,
                book_id=self.book.id,
                vocabulary_goal="reading",
                group_size=10,
                total_word_count=6,
                total_group_count=1,
                groups_json="[[2,3,4,5,6,7]]",
                queue_token="synthetic",
                status="active",
                started_at=datetime(2026, 11, 26),
            )
        )
        db.session.commit()

    def test_active_flow_is_displayed_without_writing_task_status(self):
        task = self.task()
        self.flow(task)
        item = self.groups()["assistant"][0]
        self.assertEqual((item["status"], item["status_label"]), ("in_progress", "进行中"))
        self.assertEqual(item["task_status"], "in_progress")
        db.session.refresh(task)
        self.assertEqual(task.status, "pending")

    def test_active_vocabulary_sorts_with_existing_progress_before_pending(self):
        pending = self.task(date="2026-11-24")
        legacy = self.task(
            date="2026-11-25",
            status="progress",
            dictation_book_id=None,
            vocabulary_goal=None,
            listening_exercise_id="synthetic-progress",
            listening_access_token="synthetic-progress-token",
        )
        active = self.task()
        second_active = self.task()
        done = self.task(status="done", accuracy=81.24, completion_rate=99.96)
        self.flow(active)
        self.flow(second_active)
        items = self.groups()["assistant"]
        self.assertEqual(
            [row["id"] for row in items],
            [legacy.id, active.id, second_active.id, pending.id, done.id],
        )
        self.assertEqual((items[-1]["accuracy"], items[-1]["completion_rate"]), (81.2, 100.0))
        db.session.refresh(active)
        db.session.refresh(second_active)
        self.assertEqual((active.status, second_active.status), ("pending", "pending"))

    def test_batch_books_and_shared_detail_titles_do_not_scale_with_task_count(self):
        tasks = [
            self.task(detail="  老师指定标题  "),
            self.task(detail="  ", dictation_word_end=None),
        ]
        for index in range(8):
            book = DictationBook(
                title=f"合成词书{index}", created_by=self.teacher.id, word_count=20
            )
            db.session.add(book)
            db.session.flush()
            tasks.append(self.task(dictation_book_id=book.id))
        tasks.append(self.task(dictation_book_id=999999, detail=" ", dictation_word_start=None))
        self.flow(tasks[0])
        statements = []

        def track(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lower())

        event.listen(db.engine, "before_cursor_execute", track)
        try:
            items = self.groups()["assistant"]
        finally:
            event.remove(db.engine, "before_cursor_execute", track)
        self.assertEqual(len(items), 11)
        self.assertEqual(sum("from dictation_book" in sql for sql in statements), 1)
        self.assertEqual(sum("from vocabulary_learning_flow" in sql for sql in statements), 1)
        self.assertFalse(
            any(sql.lstrip().startswith(("insert", "update", "delete")) for sql in statements)
        )
        titles = {row["id"]: row["title"] for row in items}
        for task in tasks:
            self.assertEqual(titles[task.id], task_metadata(task)["title"])
        self.assertEqual(titles[tasks[0].id], "老师指定标题")
        self.assertEqual(titles[tasks[1].id], "合成词书 · 第2词起")
        self.assertEqual(titles[tasks[-1].id], "词汇学习 · 第1–7词")

    def test_mixed_legacy_fields_keep_old_task_kind_priority(self):
        tasks = [
            self.task(listening_exercise_id="mixed-audio", listening_access_token="fixture-token"),
            self.task(reading_test_id="mixed-reading", reading_access_token="fixture-token"),
            self.task(
                grading_mode="question_type_practice",
                listening_access_token="fixture-token",
                question_ids=json.dumps(
                    {
                        "task_type": "question_type_practice",
                        "payload": {},
                        "standard_type_label": "合成专项",
                    }
                ),
            ),
            self.task(
                grading_mode="writing_practice",
                question_ids=json.dumps(
                    {
                        "writing_resource_type": "exercise",
                        "writing_resource_id": "mixed-writing",
                        "title": "合成写作",
                    }
                ),
            ),
        ]
        for task in tasks:
            self.flow(task)
        items = self.groups()["assistant"]
        self.assertEqual(
            [row["category"] for row in items], ["精听", "阅读", "题型专项", "写作真题"]
        )
        self.assertEqual(
            [row["source_label"] for row in items],
            ["精听", "剑雅阅读", "IELTS 题型专项", "IELTS 写作真题"],
        )
        self.assertTrue(all(row["status"] == "pending" for row in items))
        self.assertTrue(all("/practice/vocabulary/" not in row["url"] for row in items))

    def test_future_expired_and_done_labels_follow_shared_date_gate(self):
        self.task(date="2026-11-27")
        self.task(date="2026-11-24")
        self.task(date="2026-11-24", status="done", accuracy=75)
        items = self.groups()["assistant"]
        by_state = {item["task_date_state"]: item for item in items}
        self.assertEqual(by_state["future"]["status_label"], "尚未开放")
        self.assertEqual(by_state["expired"]["status_label"], "未完成·已截止")
        self.assertEqual(by_state["completed"]["status_label"], "已完成")
        self.assertEqual(by_state["completed"]["accuracy"], 75)
        self.assertTrue(all(item["read_only"] for item in items))

    def test_existing_four_task_payloads_are_unchanged_by_flag(self):
        tasks = [
            self.task(
                dictation_book_id=None, vocabulary_goal=None, listening_exercise_id="fixture-audio"
            ),
            self.task(
                dictation_book_id=None, vocabulary_goal=None, reading_test_id="fixture-reading"
            ),
            self.task(
                dictation_book_id=None, vocabulary_goal=None, grading_mode="question_type_practice"
            ),
            self.task(
                dictation_book_id=None, vocabulary_goal=None, grading_mode="writing_practice"
            ),
        ]
        with (
            patch.object(self.module, "_task_listening_url", return_value="/listening/fixture"),
            patch.object(self.module, "_task_reading_url", return_value="/reading/fixture"),
            patch(
                "services.question_type_assignments.assignment_url",
                return_value="/question-type/fixture",
            ),
            patch(
                "services.question_type_practice.snapshot_from_task",
                return_value={"standard_type_label": "选择题"},
            ),
            patch.object(self.module, "writing_assignment_url", return_value="/writing/fixture"),
            patch.object(
                self.module,
                "writing_snapshot_from_task",
                return_value={"writing_resource_type": "exercise", "title": "合成写作"},
            ),
        ):
            self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = False
            before = [self.module._practice_task_payload(task) for task in tasks]
            self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = True
            after = [
                self.module._practice_task_payload(task, vocabulary_payloads={}) for task in tasks
            ]
        self.assertTrue(all(before))
        self.assertEqual(before, after)
        self.assertEqual(
            [item["category"] for item in after], ["精听", "阅读", "题型专项", "写作真题"]
        )


if __name__ == "__main__":
    unittest.main()
