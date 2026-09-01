"""Route-level regression coverage for the unified legacy assignment form."""

import json
import unittest
from datetime import date
from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from sqlalchemy import inspect, text

import app as app_module
from models import MaterialBank, Question, StudentProfile, Task, User, db


class LegacyTaskAssignmentRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates", static_folder="../static")
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="legacy-task-route-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.add_url_rule("/tasks", endpoint="tasks_page", view_func=app_module.tasks_page, methods=["GET", "POST"])
        self.original_app = app_module.app
        app_module.app = self.app
        with self.app.app_context():
            db.create_all()
            staff = User(username="legacy-route-staff", password_hash="test", role=User.ROLE_ASSISTANT)
            student_user = User(username="legacy-route-student", password_hash="test", role=User.ROLE_STUDENT)
            db.session.add_all([staff, student_user])
            db.session.flush()
            self.student_name = "路由学生A"
            db.session.add(StudentProfile(full_name=self.student_name, user_id=student_user.id))
            material = MaterialBank(title="路由材料", type="translation", created_by=staff.id)
            db.session.add(material)
            db.session.flush()
            question = Question(material_id=material.id, sequence=1, question_type="text", content="Translate", reference_answer="answer")
            db.session.add(question)
            db.session.commit()
            self.staff_id = staff.id
            self.material_id = material.id
            self.question_id = question.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        app_module.app = self.original_app

    def _login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.staff_id)
            session["_fresh"] = True

    def _post(self, **values):
        self._login()
        idempotency_key = values.pop("idempotency_key", "route-key-1")
        payload = {
            "date": date.today().isoformat(),
            "student_name": self.student_name,
            "category": "基础-翻译句子练习",
            "detail": "路由回归任务",
            "status": "pending",
            "planned_minutes": "15",
            "task_source": "custom",
        }
        if idempotency_key is not None:
            payload["idempotency_key"] = idempotency_key
        payload.update(values)
        return self.client.post("/tasks", data=payload, headers={"Accept": "application/json"})

    def test_ordinary_publish_is_idempotent_and_returns_staff_safe_payload(self):
        first = self._post()
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        second = self._post()
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertTrue(second.get_json()["idempotent"])
        body = second.get_json()["task"]
        self.assertEqual(set(body), {"id", "student_name", "status", "review_url"})
        self.assertNotIn("token=", second.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 1)

    def test_legacy_sources_without_or_with_same_key_do_not_create_two_batches(self):
        no_key_first = self._post(idempotency_key=None)
        no_key_second = self._post(idempotency_key=None)
        self.assertEqual(no_key_first.status_code, 200, no_key_first.get_data(as_text=True))
        self.assertEqual(no_key_second.status_code, 200, no_key_second.get_data(as_text=True))
        self.assertTrue(no_key_second.get_json()["idempotent"])
        for source, fields in (
            (
                "material",
                {
                    "material_id": str(self.material_id),
                    "question_ids": json.dumps([self.question_id]),
                    "category": "材料练习",
                    "detail": "",
                },
            ),
            (
                "listening",
                {
                    "category": "雅思-听力-整套",
                    "detail": "",
                    "listening_exercise_id": "ielts10_test1",
                    "listening_resource_type": "cambridge_test",
                    "listening_section_number": "2",
                },
            ),
            (
                "reading",
                {
                    "category": "雅思-阅读-整套",
                    "detail": "",
                    "reading_test_id": "ielts14_test4_reading",
                    "reading_passage_number": "1",
                },
            ),
        ):
            first = self._post(task_source=source, idempotency_key=f"{source}-same", **fields)
            second = self._post(task_source=source, idempotency_key=f"{source}-same", **fields)
            self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
            self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
            self.assertTrue(second.get_json()["idempotent"])
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 4)

    def test_material_listening_and_reading_contracts_publish(self):
        material = self._post(
            idempotency_key="material-key",
            task_source="material",
            material_id=str(self.material_id),
            question_ids=json.dumps([self.question_id]),
            category="材料练习",
            detail="",
        )
        self.assertEqual(material.status_code, 200, material.get_data(as_text=True))

        listening = self._post(
            idempotency_key="listening-key",
            task_source="listening",
            category="雅思-听力-整套",
            detail="",
            listening_exercise_id="ielts10_test1",
            listening_resource_type="cambridge_test",
            listening_section_number="2",
        )
        self.assertEqual(listening.status_code, 200, listening.get_data(as_text=True))

        reading = self._post(
            idempotency_key="reading-key",
            task_source="reading",
            category="雅思-阅读-整套",
            detail="",
            reading_test_id="ielts14_test4_reading",
            reading_passage_number="1",
        )
        self.assertEqual(reading.status_code, 200, reading.get_data(as_text=True))
        with self.app.app_context():
            rows = Task.query.order_by(Task.id).all()
            self.assertEqual(rows[0].question_ids, json.dumps([self.question_id]))
            self.assertEqual(json.loads(rows[1].question_ids)["listening_section_number"], 2)
            self.assertEqual(rows[2].reading_passage_number, 1)

    def test_material_duplicate_returns_json_409_with_match_details_and_is_atomic(self):
        first = self._post(
            idempotency_key="material-first",
            task_source="material",
            material_id=str(self.material_id),
            question_ids=json.dumps([self.question_id]),
            category="材料练习",
            detail="",
        )
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        conflict = self._post(
            idempotency_key="material-second",
            task_source="material",
            material_id=str(self.material_id),
            question_ids=json.dumps([self.question_id]),
            category="材料练习",
            detail="",
        )
        self.assertEqual(conflict.status_code, 409, conflict.get_data(as_text=True))
        payload = conflict.get_json()
        self.assertEqual(payload["error"], "duplicate_assignment_conflict")
        self.assertEqual(payload["students"][0]["matches"][0]["overlap_type"], "exact")
        self.assertIn("view_url", payload["students"][0]["matches"][0])
        self.assertNotIn("token=", conflict.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 1)

    def test_listening_section_and_reading_passage_duplicates_return_409(self):
        for source, fields in (
            (
                "listening",
                {
                    "category": "雅思-听力-整套",
                    "detail": "",
                    "listening_exercise_id": "ielts10_test1",
                    "listening_resource_type": "cambridge_test",
                    "listening_section_number": "2",
                },
            ),
            (
                "reading",
                {
                    "category": "雅思-阅读-整套",
                    "detail": "",
                    "reading_test_id": "ielts14_test4_reading",
                    "reading_passage_number": "1",
                },
            ),
        ):
            first = self._post(task_source=source, idempotency_key=f"{source}-first", **fields)
            self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
            second = self._post(task_source=source, idempotency_key=f"{source}-second", **fields)
            self.assertEqual(second.status_code, 409, second.get_data(as_text=True))
            self.assertEqual(second.get_json()["error"], "duplicate_assignment_conflict")
            self.assertEqual(second.get_json()["students"][0]["matches"][0]["overlap_type"], "exact")

    def test_legacy_schema_ensures_idempotency_column_and_unique_index(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.session.execute(text("CREATE TABLE task (id INTEGER PRIMARY KEY)"))
            db.session.commit()
            app_module.ensure_legacy_schema()
            inspector = inspect(db.engine)
            columns = {column["name"] for column in inspector.get_columns("task")}
            indexes = {index["name"] for index in inspector.get_indexes("task")}
            self.assertIn("assignment_idempotency_key", columns)
            self.assertIn("ix_task_assignment_idempotency_key", indexes)


if __name__ == "__main__":
    unittest.main()
