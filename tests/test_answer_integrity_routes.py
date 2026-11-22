"""Answer timelines are stored beside homework submissions and shown only to staff."""

import json
import unittest
from datetime import datetime
from unittest.mock import patch

import jwt
from flask import Flask
from flask_login import LoginManager

import app as app_module
from api.answer_integrity import answer_integrity_bp
from api.miniprogram import mp_bp
from models import (
    AnswerIntegrityLog,
    MaterialBank,
    Question,
    QuestionOption,
    ReadingTestSubmission,
    StudentAnswer,
    StudentProfile,
    Task,
    User,
    db,
)
from services.task_date_gate import beijing_today

STUDENT_NAME = "过程记录测试学生"


def _burst_timeline(question_keys, *, start_s=18 * 60, gap_s=3, end_s=25 * 60):
    events = [
        [int((start_s + i * gap_s) * 1000), "a", str(key)] for i, key in enumerate(question_keys)
    ]
    return {"v": 1, "mode": "practice", "submitted_offset_ms": end_s * 1000, "events": events}


class AnswerIntegrityRoutesTest(unittest.TestCase):
    def setUp(self):
        self.original_app = app_module.app
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="answer-integrity-test-only",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(mp_bp)
        self.app.register_blueprint(answer_integrity_bp)
        app_module.app = self.app
        with self.app.app_context():
            db.create_all()
            admin = User(
                username="ai_admin", password_hash="x", role=User.ROLE_ADMIN, is_active=True
            )
            owner = User(
                username="ai_owner", password_hash="x", role=User.ROLE_TEACHER, is_active=True
            )
            other = User(
                username="ai_other", password_hash="x", role=User.ROLE_TEACHER, is_active=True
            )
            student = User(
                username="ai_student", password_hash="x", role=User.ROLE_STUDENT, is_active=True
            )
            db.session.add_all([admin, owner, other, student])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name=STUDENT_NAME))
            db.session.commit()
            self.ids = {
                "admin": admin.id,
                "owner": owner.id,
                "other": other.id,
                "student": student.id,
            }

    def tearDown(self):
        try:
            with self.app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
        finally:
            app_module.app = self.original_app

    # ---- fixtures ----

    def _reading_task(self):
        with self.app.app_context():
            task = Task(
                date=beijing_today().isoformat(),
                student_name=STUDENT_NAME,
                category="雅思刷题",
                detail="Cambridge reading",
                status="pending",
                created_by=self.ids["owner"],
                reading_test_id="ai_reading",
                reading_access_token="reading-token",
                reading_passage_number=1,
            )
            db.session.add(task)
            db.session.commit()
            return task.id

    def _choice_task(self, material_type="ielts_reading_practice", count=6):
        with self.app.app_context():
            material = MaterialBank(
                title="阅读题", type=material_type, created_by=self.ids["owner"]
            )
            db.session.add(material)
            db.session.flush()
            question_ids = []
            for index in range(count):
                question = Question(
                    material_id=material.id,
                    sequence=index + 1,
                    question_type="choice",
                    content=f"Question {index + 1}",
                    reference_answer="A",
                )
                db.session.add(question)
                db.session.flush()
                for key in ("A", "B", "C"):
                    db.session.add(
                        QuestionOption(question_id=question.id, option_key=key, option_text=key)
                    )
                question_ids.append(question.id)
            task = Task(
                date=beijing_today().isoformat(),
                student_name=STUDENT_NAME,
                category="阅读",
                detail="材料阅读",
                status="pending",
                created_by=self.ids["owner"],
                material_id=material.id,
            )
            db.session.add(task)
            db.session.commit()
            return task.id, question_ids

    def _staff_client(self, role):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.ids[role])
            session["_fresh"] = True
        return client

    def _student_headers(self):
        token = jwt.encode(
            {"sub": str(self.ids["student"]), "role": User.ROLE_STUDENT},
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def _submit_reading(self, task_id, integrity):
        grade = {
            "correct": 12,
            "total": 12,
            "accuracy": 100.0,
            "ielts_score": None,
            "wrong_numbers": [],
            "results": [],
        }
        body = {
            "task_id": task_id,
            "token": "reading-token",
            "answers": {str(i): "A" for i in range(1, 13)},
            "duration_seconds": 25 * 60,
        }
        if integrity is not None:
            body["integrity"] = integrity
        with (
            patch.object(
                app_module,
                "_load_reading_test_payload",
                return_value=({"title": "R"}, None, "ai_reading"),
            ),
            patch.object(app_module, "_grade_reading_test_answers", return_value=grade),
            patch.object(app_module, "_sync_reading_test_score_record"),
            self.app.test_request_context(
                "/api/reading/test/ai_reading/submit", method="POST", json=body
            ),
        ):
            return self.app.make_response(app_module.api_reading_test_submit("ai_reading"))

    # ---- submission recording ----

    def test_cambridge_submit_records_padded_burst(self):
        task_id = self._reading_task()
        response = self._submit_reading(task_id, _burst_timeline(range(1, 13)))
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

        with self.app.app_context():
            row = AnswerIntegrityLog.query.filter_by(task_id=task_id).one()
            self.assertEqual(row.source, "cambridge_reading")
            self.assertTrue(row.has_timeline)
            self.assertEqual(row.level, "medium")
            self.assertEqual(row.duration_seconds, 25 * 60)
            self.assertEqual(row.question_count, 12)
            self.assertIn("padded_burst", {flag["code"] for flag in json.loads(row.flags_json)})
            # Grading and task status are unchanged by the timeline.
            task = db.session.get(Task, task_id)
            self.assertEqual(task.status, "done")
            self.assertEqual(task.accuracy, 100.0)

    def test_cambridge_submit_without_timeline_still_succeeds(self):
        task_id = self._reading_task()
        response = self._submit_reading(task_id, None)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            row = AnswerIntegrityLog.query.filter_by(task_id=task_id).one()
            self.assertFalse(row.has_timeline)
            self.assertEqual(row.level, "info")
            self.assertIsNone(row.events_json)

    def test_garbage_timeline_never_blocks_submission(self):
        task_id = self._reading_task()
        response = self._submit_reading(
            task_id, {"v": 1, "events": [["x"], None, [1, "a", {"k": 1}]]}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(AnswerIntegrityLog.query.filter_by(task_id=task_id).count(), 1)

    def test_choice_practice_submit_records_material_source_and_redo_mode(self):
        task_id, question_ids = self._choice_task()
        client = self.app.test_client()
        timeline = {
            "v": 1,
            "mode": "practice",
            "submitted_offset_ms": 8000,
            "events": [[1000 + i * 1000, "a", str(qid)] for i, qid in enumerate(question_ids)],
        }
        payload = {
            "answers": [{"question_id": qid, "answer_key": "A"} for qid in question_ids],
            "duration_seconds": 8,
            "integrity": timeline,
        }
        response = client.post(
            f"/api/miniprogram/student/tasks/{task_id}/reading-vocab-practice/submit",
            json=payload,
            headers=self._student_headers(),
        )
        self.assertEqual(response.status_code, 200, response.get_json())

        with self.app.app_context():
            # Reopen the task so the existing date/completion gate allows a redo.
            task = db.session.get(Task, task_id)
            task.status, task.student_submitted, task.submitted_at = "pending", False, None
            db.session.commit()
        redo = dict(payload, mode="redo_all")
        response = client.post(
            f"/api/miniprogram/student/tasks/{task_id}/reading-vocab-practice/submit",
            json=redo,
            headers=self._student_headers(),
        )
        self.assertEqual(response.status_code, 200, response.get_json())

        with self.app.app_context():
            rows = (
                AnswerIntegrityLog.query.filter_by(task_id=task_id)
                .order_by(AnswerIntegrityLog.id)
                .all()
            )
            self.assertEqual([row.source for row in rows], ["material_reading", "material_reading"])
            self.assertEqual([row.mode for row in rows], ["practice", "redo_all"])
            self.assertEqual(rows[0].level, "high")
            self.assertEqual(
                StudentAnswer.query.filter_by(task_id=task_id).count(), len(question_ids)
            )

    def _break_log_inserts(self):
        """Make only the log INSERT fail (Codex review #1): drop the log table."""
        with self.app.app_context():
            AnswerIntegrityLog.__table__.drop(db.engine)
        return patch("services.answer_integrity._baseline_accuracy", return_value=None)

    def test_log_insert_failure_never_rolls_back_a_reading_submission(self):
        for integrity in (_burst_timeline(range(1, 13)), None):
            with self.subTest(integrity=bool(integrity)):
                task_id = self._reading_task()
                with self.app.app_context():
                    AnswerIntegrityLog.__table__.create(db.engine, checkfirst=True)
                with self._break_log_inserts():
                    response = self._submit_reading(task_id, integrity)
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                self.assertTrue(response.get_json()["synced"])
                with self.app.app_context():
                    task = db.session.get(Task, task_id)
                    self.assertEqual(task.status, "done")
                    self.assertTrue(task.student_submitted)
                    self.assertEqual(task.accuracy, 100.0)
                    self.assertEqual(
                        ReadingTestSubmission.query.filter_by(task_id=task_id).count(), 1
                    )

    def test_log_insert_failure_never_rolls_back_a_choice_submission(self):
        for with_timeline in (True, False):
            with self.subTest(with_timeline=with_timeline):
                task_id, question_ids = self._choice_task()
                with self.app.app_context():
                    AnswerIntegrityLog.__table__.create(db.engine, checkfirst=True)
                payload = {
                    "answers": [{"question_id": qid, "answer_key": "A"} for qid in question_ids],
                    "duration_seconds": 60,
                }
                if with_timeline:
                    payload["integrity"] = {
                        "v": 1,
                        "submitted_offset_ms": 60_000,
                        "events": [[i * 9000, "a", str(qid)] for i, qid in enumerate(question_ids)],
                    }
                with self._break_log_inserts():
                    response = self.app.test_client().post(
                        f"/api/miniprogram/student/tasks/{task_id}/reading-vocab-practice/submit",
                        json=payload,
                        headers=self._student_headers(),
                    )
                self.assertEqual(response.status_code, 200, response.get_json())
                with self.app.app_context():
                    task = db.session.get(Task, task_id)
                    self.assertEqual(task.status, "done")
                    self.assertEqual(task.accuracy, 100.0)
                    self.assertEqual(
                        StudentAnswer.query.filter_by(task_id=task_id).count(), len(question_ids)
                    )

    def test_summary_ignores_non_ascii_and_oversized_ids(self):
        task_id = self._reading_task()
        self._submit_reading(task_id, _burst_timeline(range(1, 13)))
        client = self._staff_client("admin")
        for raw in ("²", "9223372036854775808", "1" * 40, "٣", f"{task_id},²,-1, ,{task_id}"):
            with self.subTest(raw=raw):
                response = client.get(f"/api/staff/answer-integrity/summary?task_ids={raw}")
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        items = client.get(
            f"/api/staff/answer-integrity/summary?task_ids={task_id},²,99999999999999999999"
        ).get_json()["items"]
        self.assertEqual(list(items), [str(task_id)])

    # ---- staff read endpoints ----

    def test_staff_detail_respects_teacher_ownership(self):
        task_id = self._reading_task()
        self._submit_reading(task_id, _burst_timeline(range(1, 13)))
        path = f"/api/staff/tasks/{task_id}/answer-integrity"

        owner = self._staff_client("owner").get(path)
        self.assertEqual(owner.status_code, 200)
        log = owner.get_json()["logs"][0]
        self.assertEqual(log["level_label"], "需关注")
        self.assertEqual(len(log["events"]), 12)
        self.assertEqual(log["source_label"], "剑雅阅读")

        self.assertEqual(self._staff_client("admin").get(path).status_code, 200)
        self.assertEqual(self._staff_client("other").get(path).status_code, 403)
        self.assertEqual(self._staff_client("student").get(path).status_code, 403)
        self.assertEqual(self.app.test_client().get(path).status_code, 401)
        self.assertEqual(
            self._staff_client("admin").get("/api/staff/tasks/999/answer-integrity").status_code,
            404,
        )

    def test_summary_returns_latest_level_and_filters_other_teachers(self):
        flagged = self._reading_task()
        self._submit_reading(flagged, None)
        self._submit_reading(flagged, _burst_timeline(range(1, 13)))
        quiet = self._reading_task()
        path = f"/api/staff/answer-integrity/summary?task_ids={flagged},{quiet},abc"

        owner = self._staff_client("owner").get(path).get_json()
        self.assertEqual(
            owner["items"],
            {str(flagged): {"level": "medium", "level_label": "需关注", "has_timeline": True}},
        )
        self.assertEqual(self._staff_client("other").get(path).get_json()["items"], {})
        self.assertIn(str(flagged), self._staff_client("admin").get(path).get_json()["items"])
        self.assertEqual(self._staff_client("student").get(path).status_code, 403)

    def test_accuracy_jump_uses_previous_practice_attempts(self):
        with self.app.app_context():
            for accuracy in (40.0, 50.0, 45.0):
                task = Task(
                    date="2026-11-01", student_name=STUDENT_NAME, category="雅思刷题", detail="old"
                )
                db.session.add(task)
                db.session.flush()
                db.session.add(
                    AnswerIntegrityLog(
                        task_id=task.id,
                        student_name=STUDENT_NAME,
                        source="cambridge_reading",
                        mode="practice",
                        accuracy=accuracy,
                        submitted_at=datetime(2026, 11, 1),
                    )
                )
            db.session.commit()
        task_id = self._reading_task()
        steady = {
            "v": 1,
            "submitted_offset_ms": 20 * 60_000,
            "events": [[300_000 + i * 60_000, "a", str(i + 1)] for i in range(12)],
        }
        self._submit_reading(task_id, steady)
        with self.app.app_context():
            row = AnswerIntegrityLog.query.filter_by(task_id=task_id).one()
            codes = {flag["code"] for flag in json.loads(row.flags_json)}
            self.assertIn("above_baseline", codes)
            self.assertEqual(row.level, "medium")


if __name__ == "__main__":
    unittest.main()
