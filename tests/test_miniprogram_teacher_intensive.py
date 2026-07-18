import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from api.teacher_practice_access import teacher_practice_bp
from models import StudentProfile, Task, User, db


class MiniprogramTeacherIntensiveTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.static_folder = str(Path(__file__).resolve().parents[1] / "static")
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(mp_bp)
        self.app.register_blueprint(teacher_practice_bp)

        with self.app.app_context():
            db.create_all()
            student = User(
                username="intensive_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            teacher = User(
                username="intensive_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
                scheduler_teacher_id=17,
            )
            db.session.add_all([student, teacher])
            db.session.flush()
            db.session.add(
                StudentProfile(
                    user_id=student.id,
                    full_name="精听学生",
                    scheduler_student_id=101,
                )
            )
            db.session.commit()
            self.student_id = student.id
            self.teacher_id = teacher.id

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @staticmethod
    def _headers(user_id, role=User.ROLE_TEACHER):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "iat": now,
                "exp": now + 3600,
            },
            "test-secret",
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def _schedule_rows(self, *args, **kwargs):
        return {
            "schedules": [
                {
                    "id": "listen-1",
                    "student_id": 101,
                    "teacher_id": 17,
                    "student_name": "精听学生",
                    "teacher_name": "精听老师",
                    "course_name": "雅思听力",
                    "schedule_date": date.today().isoformat(),
                    "start_time": "10:00",
                    "end_time": "11:00",
                }
            ]
        }, None

    def _common(self):
        return {
            "student_id": 101,
            "student_name": "精听学生",
            "teacher_id": 17,
            "date": date.today().isoformat(),
            "category": "雅思-听力-精听",
            "detail": "9分达人听力6 Test 1 Part 2",
            "planned_minutes": 20,
            "source_type": "listening_intensive",
            "practice_exercise_id": "jfdr6_test1_s2",
        }

    def test_catalog_endpoint_contains_ielts_and_jfdr_parts(self):
        response = self.client.get(
            "/api/miniprogram/practice/catalog",
            headers=self._headers(self.teacher_id),
        )

        self.assertEqual(response.status_code, 200)
        books = response.get_json()["listening_intensive"]
        self.assertTrue(any(book["series"] == "cambridge" for book in books))
        jfdr6 = next(book for book in books if book["series"] == "jfdr" and book["book"] == 6)
        part = jfdr6["tests"][0]["parts"][1]
        self.assertEqual(part["id"], "jfdr6_test1_s2")
        self.assertGreater(part["segment_count"], 0)

    def test_create_and_edit_intensive_task_reuses_token_and_serializes_source(self):
        response = self.client.post(
            "/api/miniprogram/teacher/homework",
            json=self._common(),
            headers=self._headers(self.teacher_id),
        )
        self.assertEqual(response.status_code, 200)
        task_payload = response.get_json()["task"]
        self.assertEqual(task_payload["source_type"], "listening_intensive")
        self.assertTrue(task_payload["can_edit"])

        with self.app.app_context():
            task = Task.query.get(task_payload["id"])
            self.assertEqual(task.listening_resource_type, "intensive")
            self.assertEqual(task.listening_exercise_id, "jfdr6_test1_s2")
            first_token = task.listening_access_token
            self.assertIsNone(task.reading_test_id)
            self.assertIsNone(task.question_ids)

        updated = self.client.patch(
            f"/api/miniprogram/teacher/homework/{task_payload['id']}",
            json={**self._common(), "detail": "修改后的精听 Part 2"},
            headers=self._headers(self.teacher_id),
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["task"]["source_type"], "listening_intensive")
        with self.app.app_context():
            task = Task.query.get(task_payload["id"])
            self.assertEqual(task.listening_access_token, first_token)
            self.assertEqual(task.detail, "修改后的精听 Part 2")

        student_tasks = self.client.get(
            "/api/miniprogram/student/tasks/today",
            query_string={"date": date.today().isoformat()},
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(student_tasks.status_code, 200)
        student_task = student_tasks.get_json()["tasks"][0]
        self.assertEqual(student_task["listening_resource_type"], "intensive")
        self.assertEqual(student_task["listening_exercise_id"], "jfdr6_test1_s2")
        self.assertTrue(student_task["listening_token"])
        self.assertIn("/listening/jfdr6_test1_s2", student_task["listening_url"])

        listed = self.client.get(
            "/api/miniprogram/teacher/homework",
            query_string={"student_id": 101, "date": date.today().isoformat()},
            headers=self._headers(self.teacher_id),
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["tasks"][0]["source_type"], "listening_intensive")

    def test_invalid_intensive_ids_are_rejected(self):
        for exercise_id in ("jfdr6_test1", "jfdr6_test1_s9", "not_registered_s1"):
            response = self.client.post(
                "/api/miniprogram/teacher/homework",
                json={**self._common(), "practice_exercise_id": exercise_id},
                headers=self._headers(self.teacher_id),
            )
            self.assertEqual(response.status_code, 404, exercise_id)
            self.assertEqual(response.get_json()["error"], "practice_not_found")

    def test_quick_listening_allows_intensive_but_not_reading_or_unknown_source(self):
        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._schedule_rows,
        ):
            listing = self.client.get(
                "/api/miniprogram/teacher/practice-students",
                query_string={"month": date.today().strftime("%Y-%m")},
                headers=self._headers(self.teacher_id),
            )
        subject = listing.get_json()["students"][0]["subjects"][0]
        self.assertEqual(
            subject["allowed_sources"],
            ["cambridge_listening", "listening_intensive"],
        )
        common = {
            **self._common(),
            "quick_practice": 1,
            "subject_key": "listening",
            "allowed_source": "cambridge_listening",
            "practice_context_token": subject["practice_context_token"],
        }
        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._schedule_rows,
        ):
            created = self.client.post(
                "/api/miniprogram/teacher/homework/quick-practice",
                json=common,
                headers=self._headers(self.teacher_id),
            )
        self.assertEqual(created.status_code, 200)

        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._schedule_rows,
        ):
            forbidden_reading = self.client.post(
                "/api/miniprogram/teacher/homework/quick-practice",
                json={**common, "source_type": "cambridge_reading"},
                headers=self._headers(self.teacher_id),
            )
        self.assertEqual(forbidden_reading.status_code, 403)
        self.assertEqual(forbidden_reading.get_json()["error"], "forbidden_subject")

        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._schedule_rows,
        ):
            forbidden_unknown = self.client.post(
                "/api/miniprogram/teacher/homework/quick-practice",
                json={**common, "source_type": "unknown_source"},
                headers=self._headers(self.teacher_id),
            )
        self.assertEqual(forbidden_unknown.status_code, 403)
        self.assertEqual(forbidden_unknown.get_json()["error"], "forbidden_subject")


if __name__ == "__main__":
    unittest.main()
