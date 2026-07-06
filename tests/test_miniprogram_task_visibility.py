import json
import time
import unittest
from datetime import date, timedelta

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from models import ListeningTestSubmission, StudentProfile, Task, User, db


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
            db.session.add_all([
                self._task(self.today, "today", "pending", teacher.id),
                self._task(self.today, "today assistant", "pending", assistant.id),
                random_dictation,
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


if __name__ == "__main__":
    unittest.main()
