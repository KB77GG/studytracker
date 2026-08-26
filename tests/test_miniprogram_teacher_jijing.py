import time
import unittest
from datetime import date
from pathlib import Path

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from api.teacher_practice_access import subject_definition, teacher_practice_bp
from models import StudentProfile, Task, User, db


class MiniprogramTeacherJijingTest(unittest.TestCase):
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
                username="jijing_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            teacher = User(
                username="jijing_teacher",
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
                    full_name="机经学生",
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

    def _common(self):
        return {
            "student_id": 101,
            "student_name": "机经学生",
            "teacher_id": 17,
            "date": date.today().isoformat(),
        }

    def test_quick_practice_permissions_include_both_jijing_sources(self):
        self.assertIn(
            "listening_jijing",
            subject_definition("listening")["allowed_sources"],
        )
        self.assertIn(
            "reading_jijing",
            subject_definition("reading")["allowed_sources"],
        )

    def test_catalog_exposes_xiahuar_and_zyz_picker_options(self):
        response = self.client.get(
            "/api/miniprogram/practice/catalog",
            headers=self._headers(self.teacher_id),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        listening = payload["listening_jijing"]
        self.assertEqual(len(listening), 12)
        self.assertTrue(all(book["collection"] == "xiahuar" for book in listening))
        listening_parts = [
            part for book in listening for test in book["tests"] for part in test["parts"]
        ]
        self.assertEqual(len(listening_parts), 113)
        self.assertEqual(listening_parts[0]["id"], "xiahuar_001_p1")

        reading = payload["reading_jijing"]
        self.assertEqual(len(reading), 57)
        self.assertEqual(reading[0]["label"], "ZYZ 5")
        self.assertEqual(reading[0]["tests"][0]["id"], "reading_jijing_5_test_59")
        self.assertEqual(len(reading[0]["tests"][0]["passages"]), 3)

    def test_create_and_edit_xiahuar_task_uses_jijing_url(self):
        request_payload = {
            **self._common(),
            "source_type": "listening_jijing",
            "practice_exercise_id": "xiahuar_001_p1",
        }
        response = self.client.post(
            "/api/miniprogram/teacher/homework",
            json=request_payload,
            headers=self._headers(self.teacher_id),
        )

        self.assertEqual(response.status_code, 200)
        task_payload = response.get_json()["task"]
        self.assertEqual(task_payload["source_type"], "listening_jijing")
        self.assertEqual(task_payload["listening_resource_type"], "jijing")
        self.assertIn("/listening/jijing/xiahuar_001_p1", task_payload["listening_url"])
        self.assertTrue(task_payload["can_edit"])

        with self.app.app_context():
            task = db.session.get(Task, task_payload["id"])
            first_token = task.listening_access_token
            self.assertEqual(task.listening_resource_type, "jijing")
            self.assertEqual(task.listening_exercise_id, "xiahuar_001_p1")
            self.assertIn("Asia-Pacific Tours", task.detail)

        updated = self.client.patch(
            f"/api/miniprogram/teacher/homework/{task_payload['id']}",
            json={**request_payload, "detail": "虾滑听力修改后"},
            headers=self._headers(self.teacher_id),
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["task"]["source_type"], "listening_jijing")
        with self.app.app_context():
            task = db.session.get(Task, task_payload["id"])
            self.assertEqual(task.listening_access_token, first_token)

        student_tasks = self.client.get(
            "/api/miniprogram/student/tasks/today",
            query_string={"date": date.today().isoformat()},
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        student_task = student_tasks.get_json()["tasks"][0]
        self.assertEqual(student_task["listening_resource_type"], "jijing")
        self.assertIn("/listening/jijing/xiahuar_001_p1", student_task["listening_url"])

    def test_create_zyz_passage_keeps_reading_choices_available(self):
        response = self.client.post(
            "/api/miniprogram/teacher/homework",
            json={
                **self._common(),
                "source_type": "reading_jijing",
                "practice_test_id": "reading_jijing_5_test_59",
                "practice_scope": "passage",
                "practice_passage_number": 1,
            },
            headers=self._headers(self.teacher_id),
        )

        self.assertEqual(response.status_code, 200)
        task_payload = response.get_json()["task"]
        self.assertEqual(task_payload["source_type"], "reading_jijing")
        self.assertEqual(task_payload["reading_test_id"], "reading_jijing_5_test_59")
        self.assertEqual(task_payload["reading_passage_number"], 1)
        self.assertTrue(task_payload["can_edit"])

        with self.app.app_context():
            task = db.session.get(Task, task_payload["id"])
            token = task.reading_access_token
            self.assertEqual(task.category, "雅思-阅读-ZYZ")

        practice = self.client.get(
            f"/api/miniprogram/student/reading/cambridge/{task_payload['id']}",
            query_string={"token": token},
            headers=self._headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(practice.status_code, 200)
        question = practice.get_json()["test"]["passages"][0]["groups"][0]["questions"][0]
        self.assertEqual(question["input_mode"], "choice")
        self.assertGreaterEqual(len(question["options"]), 3)

    def test_jijing_source_rejects_ids_from_another_catalog(self):
        cases = (
            ("listening_jijing", "practice_exercise_id", "jfdr6_test1_s1"),
            ("reading_jijing", "practice_test_id", "ielts18_test1_reading"),
            ("reading_jijing", "practice_test_id", "../reading_jijing_5_test_59"),
        )
        for source_type, field, resource_id in cases:
            response = self.client.post(
                "/api/miniprogram/teacher/homework",
                json={
                    **self._common(),
                    "source_type": source_type,
                    field: resource_id,
                },
                headers=self._headers(self.teacher_id),
            )
            self.assertEqual(response.status_code, 404, resource_id)
            self.assertEqual(response.get_json()["error"], "practice_not_found")


if __name__ == "__main__":
    unittest.main()
