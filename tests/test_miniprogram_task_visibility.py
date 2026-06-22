import time
import unittest
from datetime import date, timedelta

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from models import StudentProfile, Task, User, db


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
        self.yesterday = self.today - timedelta(days=1)
        self.older_day = self.today - timedelta(days=2)

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
            db.session.add_all([student, teacher, other_teacher])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="可见性学生"))
            db.session.add_all([
                self._task(self.today, "today", "pending", teacher.id),
                self._task(self.yesterday, "yesterday pending", "pending", teacher.id),
                self._task(
                    self.yesterday,
                    "yesterday done",
                    "done",
                    teacher.id,
                    accuracy=88,
                    actual_seconds=1200,
                ),
                self._task(self.older_day, "older progress", "progress", teacher.id),
                self._task(self.yesterday, "other teacher", "pending", other_teacher.id),
            ])
            db.session.commit()
            self.student_id = student.id
            self.teacher_id = teacher.id

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

    def test_today_includes_unfinished_past_tasks_but_not_completed_past_tasks(self):
        response = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.today.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )

        self.assertEqual(response.status_code, 200)
        tasks = response.get_json()["tasks"]
        details = {task["task_name"]: task for task in tasks}
        self.assertIn("课后作业 - today", details)
        self.assertIn("课后作业 - yesterday pending", details)
        self.assertIn("课后作业 - older progress", details)
        self.assertNotIn("课后作业 - yesterday done", details)
        self.assertTrue(details["课后作业 - yesterday pending"]["is_carryover"])
        self.assertFalse(details["课后作业 - today"]["is_carryover"])

    def test_historical_date_remains_an_exact_date_view(self):
        response = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.yesterday.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )

        self.assertEqual(response.status_code, 200)
        details = [task["task_name"] for task in response.get_json()["tasks"]]
        self.assertIn("课后作业 - yesterday pending", details)
        self.assertIn("课后作业 - yesterday done", details)
        self.assertNotIn("课后作业 - older progress", details)

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
        self.assertIn("yesterday pending", details)
        self.assertIn("older progress", details)
        self.assertNotIn("other teacher", details)

    def test_student_history_keeps_completed_tasks_available_for_review(self):
        response = self.client.get(
            "/api/miniprogram/student/task-history",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        details = [item["title"] for item in payload["items"]]
        self.assertIn("课后作业 - yesterday done", details)
        self.assertNotIn("课后作业 - yesterday pending", details)
        self.assertEqual(payload["summary"]["completed"], 1)
        self.assertEqual(payload["summary"]["total_minutes"], 20.0)
        self.assertEqual(payload["summary"]["average_accuracy"], 88.0)


if __name__ == "__main__":
    unittest.main()
