import time
import unittest
from datetime import date
from unittest.mock import patch

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from api.teacher_practice_access import (
    aggregate_practice_students,
    normalize_course_subject,
    teacher_practice_bp,
)
from models import StudentProfile, Task, User, db


class TeacherPracticeAccessTest(unittest.TestCase):
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
        self.app.register_blueprint(teacher_practice_bp)

        self.month = date.today().strftime("%Y-%m")
        day = date.today().replace(day=5).isoformat()
        self.scheduler_rows = [
            {
                "id": "listen-1",
                "student_id": 101,
                "teacher_id": 17,
                "student_name": "排课名-贺学生",
                "teacher_name": "贺老师",
                "course_name": "雅思听力",
                "schedule_date": day,
                "start_time": "10:00",
                "end_time": "11:00",
            },
            {
                "id": "listen-2",
                "student_id": 101,
                "teacher_id": 17,
                "student_name": "排课名-贺学生",
                "teacher_name": "贺老师",
                "course_name": "IELTS Listening 课",
                "schedule_date": day,
                "start_time": "14:00",
                "end_time": "15:00",
            },
            {
                "id": "other-teacher-reading",
                "student_id": 101,
                "teacher_id": 18,
                "student_name": "排课名-贺学生",
                "teacher_name": "其他老师",
                "course_name": "雅思阅读",
                "schedule_date": day,
                "start_time": "16:00",
                "end_time": "17:00",
            },
        ]

        with self.app.app_context():
            db.create_all()
            student_user = User(
                username="practice_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            teacher = User(
                username="practice_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
                scheduler_teacher_id=17,
            )
            other_teacher = User(
                username="other_practice_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
                scheduler_teacher_id=18,
            )
            db.session.add_all([student_user, teacher, other_teacher])
            db.session.flush()
            db.session.add(
                StudentProfile(
                    user_id=student_user.id,
                    full_name="贺学生",
                    scheduler_student_id=101,
                )
            )
            db.session.commit()
            self.teacher_id = teacher.id
            self.other_teacher_id = other_teacher.id

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

    def _scheduler_fetch(self, start, end, teacher_id=None):
        return {"schedules": self.scheduler_rows}, None

    def test_subject_normalization_and_teacher_owned_aggregation(self):
        self.assertEqual(normalize_course_subject(" 雅思-听力课 "), "listening")
        self.assertEqual(normalize_course_subject("IELTS Reading"), "reading")
        self.assertIsNone(normalize_course_subject("托福听力"))

        students = aggregate_practice_students(
            self.scheduler_rows,
            scheduler_teacher_id=17,
        )
        self.assertEqual(len(students), 1)
        self.assertEqual(students[0]["student_id"], 101)
        self.assertEqual(
            [subject["subject_key"] for subject in students[0]["subjects"]],
            ["listening"],
        )

    def test_endpoint_uses_teacher_scope_and_unique_student_count(self):
        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._scheduler_fetch,
        ) as fetch:
            response = self.client.get(
                f"/api/miniprogram/teacher/practice-students?month={self.month}",
                headers=self._headers(self.teacher_id),
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["student_count"], 1)
        self.assertEqual(len(payload["students"]), 1)
        self.assertEqual(
            [item["subject_key"] for item in payload["students"][0]["subjects"]],
            ["listening"],
        )
        self.assertEqual(payload["students"][0]["subjects"][0]["allowed_source"], "cambridge_listening")
        self.assertTrue(payload["students"][0]["subjects"][0]["practice_context_token"])
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.kwargs["teacher_id"], 17)

    def test_quick_listening_creation_succeeds_and_forged_reading_is_forbidden(self):
        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._scheduler_fetch,
        ):
            list_response = self.client.get(
                f"/api/miniprogram/teacher/practice-students?month={self.month}",
                headers=self._headers(self.teacher_id),
            )
        subject = list_response.get_json()["students"][0]["subjects"][0]
        common = {
            "student_id": 101,
            "student_name": "贺学生",
            "teacher_id": 17,
            "date": date.today().isoformat(),
            "detail": "剑雅听力练习",
            "category": "雅思-听力",
            "practice_test_id": "ielts1_test1",
            "practice_scope": "test",
            "quick_practice": 1,
            "subject_key": "listening",
            "allowed_source": "cambridge_listening",
            "practice_context_token": subject["practice_context_token"],
        }
        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._scheduler_fetch,
        ), patch(
            "api.miniprogram._load_cambridge_listening_test",
            return_value=(({"sections": [{"section": 1}]}, "ielts1_test1")),
        ):
            created = self.client.post(
                "/api/miniprogram/teacher/homework/quick-practice",
                json={**common, "source_type": "cambridge_listening"},
                headers=self._headers(self.teacher_id),
            )
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.get_json()["ok"])
        self.assertEqual(created.get_json()["task"]["student_name"], "贺学生")

        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._scheduler_fetch,
        ), patch(
            "api.miniprogram._load_cambridge_listening_test",
            return_value=(({"sections": [{"section": 1}]}, "ielts1_test1")),
        ):
            updated = self.client.patch(
                f"/api/miniprogram/teacher/homework/quick-practice/{created.get_json()['task']['id']}",
                json={
                    **common,
                    "source_type": "cambridge_listening",
                    "detail": "剑雅听力练习（修改）",
                },
                headers=self._headers(self.teacher_id),
            )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.get_json()["ok"])
        self.assertEqual(updated.get_json()["task"]["student_name"], "贺学生")

        without_quick_flag = dict(common)
        without_quick_flag.pop("quick_practice")
        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._scheduler_fetch,
        ), patch(
            "api.miniprogram._load_cambridge_listening_test",
            return_value=(({"sections": [{"section": 1}]}, "ielts1_test1")),
        ):
            still_valid = self.client.post(
                "/api/miniprogram/teacher/homework/quick-practice",
                json={**without_quick_flag, "source_type": "cambridge_listening"},
                headers=self._headers(self.teacher_id),
            )
        self.assertEqual(still_valid.status_code, 200)

        without_shortcut_context = dict(without_quick_flag)
        for field in ("subject_key", "allowed_source", "practice_context_token"):
            without_shortcut_context.pop(field)
        stripped = self.client.post(
            "/api/miniprogram/teacher/homework/quick-practice",
            json={**without_shortcut_context, "source_type": "cambridge_listening"},
            headers=self._headers(self.teacher_id),
        )
        self.assertEqual(stripped.status_code, 403)
        self.assertEqual(stripped.get_json()["error"], "forbidden_subject")

        with patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._scheduler_fetch,
        ):
            forged = self.client.post(
                "/api/miniprogram/teacher/homework/quick-practice",
                json={
                    **common,
                    "source_type": "cambridge_reading",
                    "allowed_source": "cambridge_reading",
                },
                headers=self._headers(self.teacher_id),
            )
        self.assertEqual(forged.status_code, 403)
        self.assertEqual(forged.get_json()["error"], "forbidden_subject")

        with self.app.app_context():
            self.assertEqual(Task.query.filter_by(created_by=self.teacher_id).count(), 2)

    def test_generic_homework_keeps_existing_custom_source_flow(self):
        response = self.client.post(
            "/api/miniprogram/teacher/homework",
            json={
                "student_id": 101,
                "student_name": "贺学生",
                "teacher_id": 17,
                "source_type": "custom",
                "date": date.today().isoformat(),
                "detail": "自定义作业",
                "category": "课后作业",
            },
            headers=self._headers(self.teacher_id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["ok"])


if __name__ == "__main__":
    unittest.main()
