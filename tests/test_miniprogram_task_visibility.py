import json
import time
import unittest
from datetime import date, datetime, timedelta

import jwt
from flask import Flask
from sqlalchemy import select

from api.miniprogram import mp_bp
from models import (
    ListeningTestSubmission,
    PracticeSubmissionAttempt,
    ReadingTestSubmission,
    StudentProfile,
    Task,
    User,
    db,
)


class MiniprogramTaskVisibilityApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(mp_bp)

        self.today = date.today()
        self.d1 = self.today - timedelta(days=1)
        self.d2 = self.today - timedelta(days=2)
        # 首页固定窗口：前两天、今天、后两天。
        self.d3 = self.today - timedelta(days=3)
        self.p1 = self.today + timedelta(days=1)
        self.p2 = self.today + timedelta(days=2)
        self.p3 = self.today + timedelta(days=3)

        with self.app.app_context():
            db.create_all()
            student = User(
                username="visibility_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            teacher = User(
                username="visibility_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            other_teacher = User(
                username="other_visibility_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            assistant = User(
                username="visibility_assistant",
                password_hash="test",
                role=User.ROLE_ASSISTANT,
                is_active=True,
            )
            db.session.add_all([student, teacher, other_teacher, assistant])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="可见性学生"))
            completed_listening = self._task(
                self.d1,
                "d1 done",
                "done",
                teacher.id,
                accuracy=88,
                actual_seconds=1200,
            )
            completed_listening.listening_resource_type = "cambridge_test"
            completed_listening.listening_exercise_id = "ielts11_test1"
            random_dictation = self._task(
                self.today,
                "random dictation",
                "pending",
                teacher.id,
            )
            random_dictation.category = "词汇"
            random_dictation.dictation_book_id = 42
            random_dictation.dictation_mode = "audio_to_en"
            random_dictation.dictation_order = "random"
            random_dictation.dictation_word_start = 1
            random_dictation.dictation_word_end = 50
            malformed_listening = self._task(
                self.today,
                "listening with stray vocabulary goal",
                "pending",
                teacher.id,
            )
            malformed_listening.category = "雅思-听力-精听"
            malformed_listening.listening_resource_type = "intensive"
            malformed_listening.listening_exercise_id = "ielts18_test1_s1"
            malformed_listening.listening_access_token = "listening-token"
            malformed_listening.vocabulary_goal = "reading"
            db.session.add_all([
                self._task(self.today, "today", "pending", teacher.id),
                self._task(self.today, "today assistant", "pending", assistant.id),
                random_dictation,
                malformed_listening,
                self._task(self.d1, "d1 pending", "pending", teacher.id),
                completed_listening,
                self._task(self.d1, "d1 other", "pending", other_teacher.id),
                self._task(self.d2, "d2 progress", "progress", teacher.id),
                self._task(self.d3, "d3 pending", "pending", teacher.id),
                self._task(self.p1, "p1 pending", "pending", teacher.id),
                self._task(self.p2, "p2 pending", "pending", teacher.id),
                self._task(self.p3, "p3 pending", "pending", teacher.id),
            ])
            db.session.flush()
            db.session.add(ListeningTestSubmission(
                task_id=completed_listening.id,
                student_name="可见性学生",
                test_id="ielts11_test1",
                test_title="IELTS 11 Test 1 Listening",
                correct_count=8,
                total_count=10,
                accuracy=80,
                completion_rate=100,
                answers_json=json.dumps({"943": "150", "948": ""}),
                results_json=json.dumps([
                    {
                        "ids": ["943"],
                        "numbers": [2],
                        "q": "2",
                        "answer": "115",
                        "value": "150",
                        "marks": 1,
                        "awarded": 0,
                        "correct": False,
                        "section": 0,
                    },
                    {
                        "ids": ["948"],
                        "numbers": [7],
                        "q": "7",
                        "answer": "door",
                        "value": "",
                        "marks": 1,
                        "awarded": 0,
                        "correct": False,
                        "section": 0,
                    },
                ]),
                wrong_numbers_json=json.dumps([2, 7]),
            ))
            db.session.commit()
            self.student_id = student.id
            self.teacher_id = teacher.id
            self.other_teacher_id = other_teacher.id
            self.completed_listening_id = completed_listening.id
            self.random_dictation_id = random_dictation.id
            self.malformed_listening_id = malformed_listening.id

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @staticmethod
    def _task(task_date, detail, status, teacher_id, accuracy=None, actual_seconds=0):
        return Task(
            date=task_date.isoformat(),
            student_name="可见性学生",
            category="课后作业",
            detail=detail,
            status=status,
            created_by=teacher_id,
            accuracy=accuracy,
            actual_seconds=actual_seconds,
        )

    @staticmethod
    def _headers(user_id, role):
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "role": role,
            "iat": now,
            "exp": now + 3600,
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def _today_tasks(self):
        response = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.today.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_today_contains_only_tasks_assigned_to_today(self):
        payload = self._today_tasks()
        details = {task["task_name"]: task for task in payload["tasks"]}
        self.assertIn("课后作业 - today", details)
        self.assertIn("课后作业 - today assistant", details)
        self.assertNotIn("课后作业 - d1 pending", details)
        self.assertNotIn("课后作业 - d1 done", details)
        self.assertNotIn("课后作业 - d2 progress", details)
        self.assertNotIn("课后作业 - p1 pending", details)
        self.assertFalse(details["课后作业 - today"]["is_carryover"])
        self.assertFalse(payload["outside_home_window"])

    def test_today_tasks_expose_assigning_role(self):
        details = {task["task_name"]: task for task in self._today_tasks()["tasks"]}
        self.assertEqual(details["课后作业 - today"]["assigned_by_role"], "teacher")
        self.assertEqual(
            details["课后作业 - today assistant"]["assigned_by_role"], "assistant"
        )

    def test_completed_ielts_test_remains_retryable_only_on_assignment_day(self):
        with self.app.app_context():
            task = self._task(
                self.today,
                "today completed Cambridge",
                "done",
                self.teacher_id,
                accuracy=70,
            )
            task.listening_resource_type = "cambridge_test"
            task.listening_exercise_id = "ielts11_test2"
            task.listening_access_token = "same-day-token"
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        today = next(
            item
            for item in self._today_tasks()["tasks"]
            if item["id"] == task_id
        )
        self.assertEqual(today["status"], "completed")
        self.assertEqual(today["status_label"], "已完成")
        self.assertTrue(today["can_write"])
        self.assertFalse(today["read_only"])

        detail = self.client.get(
            f"/api/miniprogram/student/tasks/{task_id}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.get_json()["task"]["can_write"])
        self.assertFalse(detail.get_json()["task"]["read_only"])

        history = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.d1.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        historical = next(
            item
            for item in history.get_json()["tasks"]
            if item["id"] == self.completed_listening_id
        )
        self.assertFalse(historical["can_write"])
        self.assertTrue(historical["read_only"])

    def test_completed_cambridge_reading_remains_retryable_on_assignment_day(self):
        with self.app.app_context():
            task = self._task(
                self.today,
                "today completed Cambridge reading",
                "done",
                self.teacher_id,
                accuracy=70,
            )
            task.reading_test_id = "ielts11_test2_reading"
            task.reading_access_token = "reading-token"
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        today = next(
            item
            for item in self._today_tasks()["tasks"]
            if item["id"] == task_id
        )
        self.assertEqual(today["status"], "completed")
        self.assertTrue(today["can_write"])
        self.assertFalse(today["read_only"])

    def test_completed_reading_jijing_keeps_attempt_retaining_retry_access(self):
        with self.app.app_context():
            task = self._task(
                self.today,
                "today completed reading jijing",
                "done",
                self.teacher_id,
                accuracy=70,
            )
            task.reading_test_id = "reading_jijing_5_test_59"
            task.reading_access_token = "jijing-token"
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        today = next(
            item
            for item in self._today_tasks()["tasks"]
            if item["id"] == task_id
        )
        self.assertTrue(today["can_write"])
        self.assertFalse(today["read_only"])

    def test_teacher_delete_soft_cancels_fresh_task_and_hides_it_from_students(self):
        with self.app.app_context():
            task = self._task(
                self.today,
                "mistaken assignment",
                "pending",
                self.teacher_id,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        response = self.client.delete(
            f"/api/miniprogram/teacher/homework/{task_id}",
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.get_json()["ok"])
        with self.app.app_context():
            self.assertIsNone(db.session.get(Task, task_id))
            tombstone = db.session.execute(
                select(Task)
                .where(Task.id == task_id)
                .execution_options(include_cancelled_tasks=True)
            ).scalar_one()
            self.assertEqual(tombstone.status, Task.STATUS_CANCELLED)
            self.assertIsNotNone(tombstone.cancelled_at)
        task_names = {item["task_name"] for item in self._today_tasks()["tasks"]}
        self.assertNotIn("课后作业 - mistaken assignment", task_names)

    def test_teacher_delete_preserves_completed_task_history(self):
        response = self.client.delete(
            f"/api/miniprogram/teacher/homework/{self.completed_listening_id}",
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["error"], "task_has_activity")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Task, self.completed_listening_id))

    def test_dictation_task_exposes_order_in_list_and_detail(self):
        details = {task["task_name"]: task for task in self._today_tasks()["tasks"]}
        summary = details["词汇 - random dictation"]
        self.assertEqual(summary["dictation_order"], "random")

        response = self.client.get(
            f"/api/miniprogram/student/tasks/{self.random_dictation_id}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )

        self.assertEqual(response.status_code, 200)
        task = response.get_json()["task"]
        self.assertEqual(task["dictation_order"], "random")

    def test_listening_task_hides_stray_vocabulary_goal_in_list_and_detail(self):
        details = {task["task_name"]: task for task in self._today_tasks()["tasks"]}
        summary = details[
            "雅思-听力-精听 - listening with stray vocabulary goal"
        ]
        self.assertIsNone(summary["vocabulary_goal"])
        self.assertIsNone(summary["learning_goal"])
        self.assertEqual(summary["listening_exercise_id"], "ielts18_test1_s1")

        response = self.client.get(
            f"/api/miniprogram/student/tasks/{self.malformed_listening_id}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(response.status_code, 200)
        task = response.get_json()["task"]
        self.assertIsNone(task["vocabulary_goal"])
        self.assertIsNone(task["learning_goal"])
        self.assertEqual(task["listening_exercise_id"], "ielts18_test1_s1")

    def test_each_visible_date_is_an_exact_date_view(self):
        history = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.d1.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        history_details = [task["task_name"] for task in history.get_json()["tasks"]]
        self.assertIn("课后作业 - d1 pending", history_details)
        self.assertIn("课后作业 - d1 done", history_details)
        self.assertNotIn("课后作业 - today", history_details)
        self.assertNotIn("课后作业 - d2 progress", history_details)

        future = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.p2.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        future_details = [task["task_name"] for task in future.get_json()["tasks"]]
        self.assertEqual(future_details, ["课后作业 - p2 pending"])

    def test_dates_outside_five_day_window_require_reassignment(self):
        for task_date in (self.d3, self.p3):
            response = self.client.get(
                f"/api/miniprogram/student/tasks/today?date={task_date.isoformat()}",
                headers=self._headers(self.student_id, User.ROLE_STUDENT),
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertEqual(payload["tasks"], [])
            self.assertTrue(payload["outside_home_window"])
            self.assertIn("重新布置", payload["message"])

    def test_outstanding_summary_endpoint_has_been_removed(self):
        response = self.client.get(
            "/api/miniprogram/student/tasks/outstanding",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(response.status_code, 404)

    def test_historical_date_remains_an_exact_date_view(self):
        response = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.d1.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )

        self.assertEqual(response.status_code, 200)
        details = [task["task_name"] for task in response.get_json()["tasks"]]
        self.assertIn("课后作业 - d1 pending", details)
        self.assertIn("课后作业 - d1 done", details)
        self.assertNotIn("课后作业 - d2 progress", details)

    def test_teacher_recent_scope_is_not_limited_to_selected_task_date(self):
        response = self.client.get(
            "/api/miniprogram/teacher/homework",
            query_string={
                "student_name": "可见性学生",
                "date": self.today.isoformat(),
                "scope": "recent",
            },
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        details = [task["detail"] for task in payload["tasks"]]
        self.assertEqual(payload["scope"], "recent")
        self.assertIn("today", details)
        self.assertIn("d1 pending", details)
        self.assertIn("d2 progress", details)
        self.assertNotIn("d1 other", details)  # 其他老师布置的不属于当前老师
        completed = next(task for task in payload["tasks"] if task["detail"] == "d1 done")
        self.assertEqual(completed["practice_result"]["kind"], "listening")
        self.assertEqual(completed["practice_result"]["correct_count"], 8)
        self.assertEqual(completed["practice_result"]["wrong_numbers"], [2, 7])

    def test_student_history_keeps_completed_tasks_available_for_review(self):
        response = self.client.get(
            "/api/miniprogram/student/task-history",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        details = [item["title"] for item in payload["items"]]
        self.assertIn("课后作业 - d1 done", details)
        self.assertNotIn("课后作业 - d1 pending", details)
        self.assertEqual(payload["summary"]["completed"], 1)
        self.assertEqual(payload["summary"]["total_minutes"], 20.0)
        self.assertEqual(payload["summary"]["average_accuracy"], 88.0)
        self.assertEqual(payload["summary"]["wrong_tasks"], 1)
        completed = next(item for item in payload["items"] if item["title"] == "课后作业 - d1 done")
        self.assertEqual(completed["wrong_count"], 2)
        self.assertEqual(completed["wrong_numbers"], [2, 7])

    def test_student_status_label_preserves_submitted_semantics_across_date_gate(self):
        with self.app.app_context():
            historical = self._task(
                self.d1,
                "d1 submitted",
                "submitted",
                self.teacher_id,
            )
            today = self._task(
                self.today,
                "today submitted flag",
                "progress",
                self.teacher_id,
            )
            today.student_submitted = True
            db.session.add_all([historical, today])
            db.session.commit()
            historical_id = historical.id

        history = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.d1.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        historical_payload = next(
            item
            for item in history.get_json()["tasks"]
            if item["task_name"].endswith(" - d1 submitted")
        )
        self.assertEqual(historical_payload["status"], "submitted")
        self.assertEqual(historical_payload["status_label"], "已提交，待批改")
        self.assertEqual(historical_payload["task_status_label"], "已提交，待批改")
        self.assertEqual(historical_payload["availability_label"], "已截止")
        self.assertTrue(historical_payload["read_only"])

        today_tasks = self._today_tasks()
        today_payload = next(
            item
            for item in today_tasks["tasks"]
            if item["task_name"].endswith(" - today submitted flag")
        )
        self.assertEqual(today_payload["status"], "submitted")
        self.assertEqual(today_payload["status_label"], "已提交，待批改")
        self.assertEqual(today_payload["task_status_label"], "已提交，待批改")
        self.assertFalse(today_payload["read_only"])

        review_center = self.client.get(
            "/api/miniprogram/student/task-history",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(review_center.status_code, 200)
        submitted_history = next(
            item
            for item in review_center.get_json()["items"]
            if item["title"] == "课后作业 - d1 submitted"
        )
        self.assertEqual(submitted_history["state_label"], "已提交，待批改")
        self.assertEqual(submitted_history["display_state_label"], "已提交，待批改")

        detail = self.client.get(
            f"/api/miniprogram/student/tasks/{historical_id}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["task"]["status_label"], "已提交，待批改")

    def test_teacher_can_view_each_wrong_answer_and_correct_answer(self):
        response = self.client.get(
            f"/api/miniprogram/teacher/homework/{self.completed_listening_id}/result",
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        details = payload["practice_result"]["wrong_details"]
        self.assertEqual(len(details), 2)
        self.assertEqual(details[0]["question_label"], "Q2")
        self.assertEqual(details[0]["student_answer"], "150")
        self.assertEqual(details[0]["correct_answer"], "115")
        self.assertEqual(details[1]["student_answer"], "未作答")

        forbidden = self.client.get(
            f"/api/miniprogram/teacher/homework/{self.completed_listening_id}/result",
            headers=self._headers(self.other_teacher_id, User.ROLE_TEACHER),
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_teacher_sees_first_latest_and_each_retained_attempt(self):
        with self.app.app_context():
            row = ListeningTestSubmission.query.filter_by(task_id=self.completed_listening_id).one()
            row.attempt_count = 3
            row.correct_count = 9
            row.total_count = 10
            row.accuracy = 90
            row.wrong_numbers_json = json.dumps([10])
            row.results_json = json.dumps(
                [
                    {
                        "ids": ["10"],
                        "numbers": [10],
                        "answer": "library",
                        "value": "libary",
                        "marks": 1,
                        "awarded": 0,
                        "correct": False,
                    }
                ]
            )
            row.submitted_at = datetime(2026, 8, 26, 3, 0)
            db.session.add_all(
                [
                    PracticeSubmissionAttempt(
                        task_id=self.completed_listening_id,
                        student_name="可见性学生",
                        kind="listening",
                        test_id="ielts11_test1",
                        attempt_number=1,
                        correct_count=4,
                        total_count=10,
                        accuracy=40,
                        answers_json=json.dumps({"1": "wrong"}),
                        results_json=json.dumps(
                            [
                                {
                                    "ids": ["1"],
                                    "numbers": [1],
                                    "answer": "answer",
                                    "value": "wrong",
                                    "marks": 1,
                                    "awarded": 0,
                                    "correct": False,
                                }
                            ]
                        ),
                        wrong_numbers_json=json.dumps([1]),
                        submitted_at=datetime(2026, 8, 26, 1, 0),
                    ),
                    PracticeSubmissionAttempt(
                        task_id=self.completed_listening_id,
                        student_name="可见性学生",
                        kind="listening",
                        test_id="ielts11_test1",
                        attempt_number=2,
                        correct_count=7,
                        total_count=10,
                        accuracy=70,
                        answers_json=json.dumps({"2": "wrong"}),
                        results_json=json.dumps(
                            [
                                {
                                    "ids": ["2"],
                                    "numbers": [2],
                                    "answer": "answer",
                                    "value": "wrong",
                                    "marks": 1,
                                    "awarded": 0,
                                    "correct": False,
                                }
                            ]
                        ),
                        wrong_numbers_json=json.dumps([2]),
                        submitted_at=datetime(2026, 8, 26, 2, 0),
                    ),
                ]
            )
            db.session.commit()

        listing = self.client.get(
            "/api/miniprogram/teacher/homework",
            query_string={
                "student_name": "可见性学生",
                "date": self.today.isoformat(),
                "scope": "recent",
            },
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )
        completed = next(
            task
            for task in listing.get_json()["tasks"]
            if task["id"] == self.completed_listening_id
        )
        overview = completed["practice_result"]["attempt_overview"]
        self.assertEqual(overview["attempt_count"], 3)
        self.assertEqual(overview["first_attempt"]["accuracy"], 40.0)
        self.assertEqual(overview["latest_attempt"]["accuracy"], 90.0)
        self.assertEqual(overview["score_delta"], 50.0)
        self.assertEqual(overview["legacy_missing_attempts"], 0)

        detail = self.client.get(
            f"/api/miniprogram/teacher/homework/{self.completed_listening_id}/result",
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        ).get_json()
        attempts = detail["attempt_history"]["attempts"]
        self.assertEqual(
            [attempt["attempt_number"] for attempt in attempts],
            [1, 2, 3],
        )
        self.assertTrue(attempts[0]["is_first"])
        self.assertTrue(attempts[-1]["is_latest"])
        self.assertEqual(attempts[0]["wrong_details"][0]["question_label"], "Q1")

    def test_teacher_discloses_legacy_attempts_that_cannot_be_restored(self):
        with self.app.app_context():
            row = ListeningTestSubmission.query.filter_by(task_id=self.completed_listening_id).one()
            row.attempt_count = 3
            db.session.commit()

        response = self.client.get(
            "/api/miniprogram/teacher/homework",
            query_string={
                "student_name": "可见性学生",
                "date": self.today.isoformat(),
                "scope": "recent",
            },
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )
        completed = next(
            task
            for task in response.get_json()["tasks"]
            if task["id"] == self.completed_listening_id
        )
        overview = completed["practice_result"]["attempt_overview"]
        self.assertIsNone(overview["first_attempt"])
        self.assertEqual(overview["legacy_missing_attempts"], 2)
        self.assertEqual(
            [attempt["attempt_number"] for attempt in overview["attempts"]],
            [3],
        )

    def test_teacher_attempt_history_also_supports_reading(self):
        with self.app.app_context():
            task = self._task(
                self.today,
                "reading done",
                "done",
                self.teacher_id,
                accuracy=85,
            )
            task.reading_test_id = "ielts11_test1"
            db.session.add(task)
            db.session.flush()
            db.session.add_all([
                ReadingTestSubmission(
                    task_id=task.id,
                    student_name="可见性学生",
                    test_id="ielts11_test1",
                    correct_count=17,
                    total_count=20,
                    accuracy=85,
                    attempt_count=2,
                    results_json=json.dumps([]),
                    wrong_numbers_json=json.dumps([18, 19, 20]),
                    submitted_at=datetime(2026, 8, 26, 4, 0),
                ),
                PracticeSubmissionAttempt(
                    task_id=task.id,
                    student_name="可见性学生",
                    kind="reading",
                    test_id="ielts11_test1",
                    attempt_number=1,
                    correct_count=12,
                    total_count=20,
                    accuracy=60,
                    results_json=json.dumps([]),
                    wrong_numbers_json=json.dumps(list(range(13, 21))),
                    submitted_at=datetime(2026, 8, 26, 3, 0),
                ),
            ])
            db.session.commit()
            reading_task_id = task.id

        response = self.client.get(
            "/api/miniprogram/teacher/homework",
            query_string={
                "student_name": "可见性学生",
                "date": self.today.isoformat(),
                "scope": "recent",
            },
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )
        reading = next(
            task for task in response.get_json()["tasks"] if task["id"] == reading_task_id
        )
        overview = reading["practice_result"]["attempt_overview"]
        self.assertEqual(reading["practice_result"]["kind"], "reading")
        self.assertEqual(overview["first_attempt"]["accuracy"], 60.0)
        self.assertEqual(overview["latest_attempt"]["accuracy"], 85.0)
        self.assertEqual(overview["score_delta"], 25.0)

    def test_partial_group_uses_score_difference_for_wrong_count_and_detail(self):
        with self.app.app_context():
            row = ListeningTestSubmission.query.filter_by(task_id=self.completed_listening_id).first()
            row.correct_count = 1
            row.total_count = 2
            row.wrong_numbers_json = json.dumps([1, 2])
            row.results_json = json.dumps([{
                "ids": ["1", "2"],
                "numbers": [1, 2],
                "q": "1,2",
                "answer": "B,C",
                "value": "B,D",
                "marks": 2,
                "awarded": 1,
                "correct": False,
                "status": "partial",
                "status_label": "部分正确 1/2",
            }], ensure_ascii=False)
            db.session.commit()

        response = self.client.get(
            f"/api/miniprogram/teacher/homework/{self.completed_listening_id}/result",
            headers=self._headers(self.teacher_id, User.ROLE_TEACHER),
        )
        self.assertEqual(response.status_code, 200)
        result = response.get_json()["practice_result"]
        self.assertEqual(result["wrong_count"], 1)
        self.assertEqual(result["wrong_details"][0]["awarded"], 1)
        self.assertEqual(result["wrong_details"][0]["marks"], 2)
        self.assertEqual(result["wrong_details"][0]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
