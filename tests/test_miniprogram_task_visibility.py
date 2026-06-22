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
        self.d1 = self.today - timedelta(days=1)
        self.d2 = self.today - timedelta(days=2)
        # 首页 carryover 窗口为 3 天：d3 在窗口内、d4 已超出。
        self.d3 = self.today - timedelta(days=3)
        self.d4 = self.today - timedelta(days=4)
        # 「未完成作业」页窗口为 5 天：d5 在窗口内、d6 已超出。
        self.d5 = self.today - timedelta(days=5)
        self.d6 = self.today - timedelta(days=6)

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
            db.session.add_all([
                self._task(self.today, "today", "pending", teacher.id),
                self._task(self.today, "today assistant", "pending", assistant.id),
                self._task(self.d1, "d1 pending", "pending", teacher.id),
                self._task(
                    self.d1,
                    "d1 done",
                    "done",
                    teacher.id,
                    accuracy=88,
                    actual_seconds=1200,
                ),
                self._task(self.d1, "d1 other", "pending", other_teacher.id),
                self._task(self.d2, "d2 progress", "progress", teacher.id),
                self._task(self.d3, "d3 pending", "pending", teacher.id),
                self._task(self.d4, "d4 pending", "pending", teacher.id),
                self._task(self.d5, "d5 pending", "pending", teacher.id),
                self._task(self.d6, "d6 pending", "pending", teacher.id),
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

    def _today_tasks(self):
        response = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.today.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def test_today_includes_recent_unfinished_but_not_completed_or_too_old(self):
        payload = self._today_tasks()
        details = {task["task_name"]: task for task in payload["tasks"]}
        # 今天 + 3 天 carryover 窗口内的未完成任务
        self.assertIn("课后作业 - today", details)
        self.assertIn("课后作业 - d1 pending", details)
        self.assertIn("课后作业 - d2 progress", details)
        self.assertIn("课后作业 - d3 pending", details)
        # 已完成的历史任务不再 carryover
        self.assertNotIn("课后作业 - d1 done", details)
        # 超出 3 天窗口的未完成任务不进今天页
        self.assertNotIn("课后作业 - d4 pending", details)
        self.assertNotIn("课后作业 - d5 pending", details)
        self.assertNotIn("课后作业 - d6 pending", details)
        self.assertTrue(details["课后作业 - d1 pending"]["is_carryover"])
        self.assertFalse(details["课后作业 - today"]["is_carryover"])

    def test_today_tasks_expose_assigning_role(self):
        details = {task["task_name"]: task for task in self._today_tasks()["tasks"]}
        self.assertEqual(details["课后作业 - today"]["assigned_by_role"], "teacher")
        self.assertEqual(
            details["课后作业 - today assistant"]["assigned_by_role"], "assistant"
        )

    def test_carryover_window_boundary_is_three_days(self):
        details = [task["task_name"] for task in self._today_tasks()["tasks"]]
        # d3 在窗口内，d4 刚好超出
        self.assertIn("课后作业 - d3 pending", details)
        self.assertNotIn("课后作业 - d4 pending", details)

        # 精确查 d4 那天，任务仍然可见（只是不再 carryover 到今天页）
        history = self.client.get(
            f"/api/miniprogram/student/tasks/today?date={self.d4.isoformat()}",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        history_details = [task["task_name"] for task in history.get_json()["tasks"]]
        self.assertIn("课后作业 - d4 pending", history_details)

    def test_today_reports_outstanding_count(self):
        payload = self._today_tasks()
        # 过去 5 天（d1..d5）仍未完成的任务数：
        # d1 pending / d1 other / d2 progress / d3 pending / d4 pending / d5 pending = 6
        # 不含已完成的 d1 done，也不含窗口外的 d6。
        self.assertEqual(payload["outstanding_count"], 6)

    def test_outstanding_endpoint_lists_recent_unfinished_by_day(self):
        response = self.client.get(
            "/api/miniprogram/student/tasks/outstanding",
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        items = payload["items"]
        names = [item["task_name"] for item in items]

        self.assertEqual(len(items), 6)
        self.assertIn("课后作业 - d5 pending", names)
        self.assertNotIn("课后作业 - d6 pending", names)   # 超出 5 天窗口
        self.assertNotIn("课后作业 - d1 done", names)       # 已完成
        self.assertNotIn("课后作业 - today", names)         # 只回溯过去
        # 按日期倒序：最近的 d1 排在最前
        self.assertEqual(items[0]["date"], self.d1.isoformat())
        self.assertEqual(payload["window_days"], 5)

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


if __name__ == "__main__":
    unittest.main()
