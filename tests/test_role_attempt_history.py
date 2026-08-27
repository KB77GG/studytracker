"""Role-safe assistant and parent attempt-history integration tests."""

import json
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import jwt
from flask import Flask
from flask_login import LoginManager

from api.miniprogram import mp_bp
from api.practice_history import practice_history_bp
from models import (
    ListeningTestSubmission,
    ParentStudentLink,
    PracticeSubmissionAttempt,
    Task,
    User,
    db,
)

ROOT = Path(__file__).resolve().parents[1]


class RoleAttemptHistoryApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="role-attempt-history-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def _load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(practice_history_bp)
        self.app.register_blueprint(mp_bp)

        with self.app.app_context():
            db.create_all()
            users = {
                role: User(
                    username=f"history_{role}",
                    password_hash="test",
                    role=role,
                    is_active=True,
                )
                for role in (
                    User.ROLE_ADMIN,
                    User.ROLE_ASSISTANT,
                    User.ROLE_TEACHER,
                    User.ROLE_STUDENT,
                    User.ROLE_PARENT,
                )
            }
            other_teacher = User(
                username="history_other_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            other_parent = User(
                username="history_other_parent",
                password_hash="test",
                role=User.ROLE_PARENT,
                is_active=True,
            )
            db.session.add_all([*users.values(), other_teacher, other_parent])
            db.session.flush()
            db.session.add(
                ParentStudentLink(
                    parent_id=users[User.ROLE_PARENT].id,
                    student_name="学生甲",
                    is_active=True,
                )
            )

            task = Task(
                date="2026-08-27",
                student_name="学生甲",
                category="雅思听力",
                detail="Cambridge IELTS 17 Test 1 Listening",
                status="done",
                created_by=users[User.ROLE_TEACHER].id,
                listening_resource_type="cambridge_test",
                listening_exercise_id="ielts17_test1",
            )
            db.session.add(task)
            db.session.flush()
            for number, correct, student_answer, submitted_at in (
                (1, 4, "library", datetime(2026, 8, 27, 1, 0)),
                (2, 7, "librarys", datetime(2026, 8, 27, 1, 15)),
            ):
                db.session.add(
                    PracticeSubmissionAttempt(
                        task_id=task.id,
                        student_name="学生甲",
                        kind="listening",
                        test_id="ielts17_test1",
                        test_title=task.detail,
                        attempt_number=number,
                        correct_count=correct,
                        total_count=10,
                        accuracy=correct * 10,
                        results_json=self._results(student_answer),
                        wrong_numbers_json="[3]",
                        submitted_at=submitted_at,
                    )
                )
            db.session.add(
                ListeningTestSubmission(
                    task_id=task.id,
                    student_name="学生甲",
                    test_id="ielts17_test1",
                    test_title=task.detail,
                    correct_count=9,
                    total_count=10,
                    accuracy=90,
                    attempt_count=3,
                    results_json=self._results("library"),
                    wrong_numbers_json="[3]",
                    submitted_at=datetime(2026, 8, 27, 1, 30),
                )
            )
            db.session.commit()

            self.user_ids = {role: user.id for role, user in users.items()}
            self.other_teacher_id = other_teacher.id
            self.other_parent_id = other_parent.id
            self.task_id = task.id

        self.client = self.app.test_client()

    @staticmethod
    def _results(student_answer):
        return json.dumps(
            [
                {
                    "numbers": [3],
                    "value": student_answer,
                    "answer": "libraries",
                    "status": "incorrect",
                    "awarded": 0,
                    "marks": 1,
                }
            ]
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def _parent_headers(self, user_id):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": str(user_id),
                "role": User.ROLE_PARENT,
                "iat": now,
                "exp": now + int(timedelta(hours=1).total_seconds()),
            },
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def test_assistant_sees_first_latest_and_wrong_answers(self):
        self._login(self.user_ids[User.ROLE_ASSISTANT])
        response = self.client.get(f"/api/staff/tasks/{self.task_id}/attempt-history")

        self.assertEqual(response.status_code, 200)
        overview = response.get_json()["attempt_overview"]
        self.assertEqual(overview["attempt_count"], 3)
        self.assertEqual(overview["first_attempt"]["accuracy"], 40.0)
        self.assertEqual(overview["latest_attempt"]["accuracy"], 90.0)
        self.assertEqual(overview["score_delta"], 50.0)
        self.assertEqual(
            [attempt["attempt_number"] for attempt in overview["attempts"]],
            [1, 2, 3],
        )
        self.assertEqual(
            overview["attempts"][-1]["wrong_details"][0]["student_answer"],
            "library",
        )

    def test_staff_permissions_are_role_and_owner_scoped(self):
        for user_id, expected_status in (
            (self.user_ids[User.ROLE_ADMIN], 200),
            (self.user_ids[User.ROLE_TEACHER], 200),
            (self.other_teacher_id, 403),
            (self.user_ids[User.ROLE_STUDENT], 403),
            (self.user_ids[User.ROLE_PARENT], 403),
        ):
            with self.subTest(user_id=user_id):
                self._login(user_id)
                response = self.client.get(
                    f"/api/staff/tasks/{self.task_id}/attempt-history"
                )
                self.assertEqual(response.status_code, expected_status)

    def test_only_linked_parent_can_read_same_attempt_history(self):
        linked = self.client.get(
            f"/api/miniprogram/parent/tasks/{self.task_id}",
            headers=self._parent_headers(self.user_ids[User.ROLE_PARENT]),
        )
        unlinked = self.client.get(
            f"/api/miniprogram/parent/tasks/{self.task_id}",
            headers=self._parent_headers(self.other_parent_id),
        )

        self.assertEqual(linked.status_code, 200)
        overview = linked.get_json()["detail"]["attempt_overview"]
        self.assertEqual(overview["first_attempt"]["accuracy"], 40.0)
        self.assertEqual(overview["latest_attempt"]["accuracy"], 90.0)
        self.assertEqual(unlinked.status_code, 403)
        self.assertEqual(unlinked.get_json()["error"], "student_not_bound")


class RoleAttemptHistoryMarkupTest(unittest.TestCase):
    def test_assistant_and_parent_surfaces_have_requested_copy(self):
        assistant = (ROOT / "templates/tasks.html").read_text(encoding="utf-8")
        parent = (
            ROOT / "miniprogram/pages/parent/task-detail/index.wxml"
        ).read_text(encoding="utf-8")
        combined = assistant + parent

        self.assertIn("查看学习轨迹", assistant)
        self.assertIn("首答正确率", combined)
        self.assertIn("查看历次提交、错题与答案", parent)
        self.assertIn("旧版未留存", assistant)
        self.assertIn("成绩变化用于观察学习过程", combined)
        self.assertNotIn("不能单凭高分直接认定作弊", combined)


if __name__ == "__main__":
    unittest.main()
