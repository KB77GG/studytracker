import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

import app as app_module
from models import (
    ListeningTestSubmission,
    PracticeSubmissionAttempt,
    ReadingTestSubmission,
    StudentProfile,
    Task,
    User,
    db,
)
from services.task_date_gate import beijing_today


class CambridgeSameDayRetryTest(unittest.TestCase):
    def setUp(self):
        self.original_app = app_module.app
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="cambridge-retry-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        app_module.app = self.app
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        try:
            with self.app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
        finally:
            app_module.app = self.original_app

    def _seed_completed_attempt(self, kind, test_id=None, task_date=None):
        task_date = task_date or beijing_today().isoformat()
        test_id = test_id or f"retry_{kind}"
        task = Task(
            date=task_date,
            student_name="同日重练测试",
            category="雅思刷题",
            detail=f"{kind} retry",
            status="done",
            student_submitted=True,
            submitted_at=datetime.utcnow(),
            accuracy=40,
            completion_rate=100,
        )
        if kind == "listening":
            task.listening_resource_type = "cambridge_test"
            task.listening_exercise_id = "retry_listening"
            task.listening_access_token = "listening-token"
            task.question_ids = json.dumps({"listening_section_number": 1})
        else:
            task.reading_test_id = test_id
            task.reading_access_token = "reading-token"
            task.reading_passage_number = 1
        db.session.add(task)
        db.session.flush()

        model = ListeningTestSubmission if kind == "listening" else ReadingTestSubmission
        submission = model(
            task_id=task.id,
            student_name=task.student_name,
            test_id=test_id,
            test_title=f"{kind} retry",
            correct_count=4,
            total_count=10,
            accuracy=40,
            completion_rate=100,
            answers_json=json.dumps({"1": "first"}),
            results_json=json.dumps([]),
            wrong_numbers_json=json.dumps([1]),
            attempt_count=1,
            submitted_at=datetime.utcnow(),
        )
        db.session.add(submission)
        db.session.flush()
        db.session.add(
            PracticeSubmissionAttempt(
                task_id=task.id,
                student_name=task.student_name,
                kind=kind,
                test_id=test_id,
                test_title=f"{kind} retry",
                scope_number=1,
                attempt_number=1,
                correct_count=4,
                total_count=10,
                accuracy=40,
                completion_rate=100,
                answers_json=json.dumps({"1": "first"}),
                results_json=json.dumps([]),
                wrong_numbers_json=json.dumps([1]),
                submitted_at=submission.submitted_at,
            )
        )
        db.session.commit()
        return task.id

    @staticmethod
    def _second_grade():
        return {
            "correct": 8,
            "total": 10,
            "accuracy": 80.0,
            "ielts_score": 6.5,
            "wrong_numbers": [9, 10],
            "results": [],
        }

    def _assert_attempts_preserved(self, task_id, kind, model):
        submission = model.query.filter_by(task_id=task_id).one()
        self.assertEqual(submission.attempt_count, 2)
        self.assertEqual(submission.accuracy, 80.0)
        attempts = (
            PracticeSubmissionAttempt.query.filter_by(task_id=task_id, kind=kind)
            .order_by(PracticeSubmissionAttempt.attempt_number)
            .all()
        )
        self.assertEqual([row.attempt_number for row in attempts], [1, 2])
        self.assertEqual([row.accuracy for row in attempts], [40.0, 80.0])

    def test_listening_same_day_retry_appends_second_attempt(self):
        with self.app.app_context():
            task_id = self._seed_completed_attempt("listening")

        payload = {"title": "Listening retry"}
        with (
            patch.object(
                app_module,
                "_load_listening_test_payload",
                return_value=(payload, None, "retry_listening"),
            ),
            patch.object(
                app_module,
                "_grade_listening_test_answers",
                return_value=self._second_grade(),
            ),
            patch.object(app_module, "_sync_listening_test_score_record"),
            self.app.test_request_context(
                "/api/listening/test/retry_listening/submit",
                method="POST",
                json={
                    "task_id": task_id,
                    "token": "listening-token",
                    "section_number": 1,
                    "answers": {"1": "second"},
                },
            ),
        ):
            response = self.app.make_response(
                app_module.api_listening_test_submit("retry_listening")
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertFalse(response.get_json()["task"]["read_only"])
        with self.app.app_context():
            self._assert_attempts_preserved(
                task_id,
                "listening",
                ListeningTestSubmission,
            )

    def test_reading_same_day_retry_appends_second_attempt(self):
        with self.app.app_context():
            task_id = self._seed_completed_attempt("reading")

        payload = {"title": "Reading retry"}
        with (
            patch.object(
                app_module,
                "_load_reading_test_payload",
                return_value=(payload, None, "retry_reading"),
            ),
            patch.object(
                app_module,
                "_grade_reading_test_answers",
                return_value=self._second_grade(),
            ),
            patch.object(app_module, "_sync_reading_test_score_record"),
            self.app.test_request_context(
                "/api/reading/test/retry_reading/submit",
                method="POST",
                json={
                    "task_id": task_id,
                    "token": "reading-token",
                    "passage_number": 1,
                    "answers": {"1": "second"},
                },
            ),
        ):
            response = self.app.make_response(
                app_module.api_reading_test_submit("retry_reading")
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertFalse(response.get_json()["task"]["read_only"])
        with self.app.app_context():
            self._assert_attempts_preserved(
                task_id,
                "reading",
                ReadingTestSubmission,
            )

    def test_reading_jijing_same_day_retry_preserves_both_attempts(self):
        with self.app.app_context():
            task_id = self._seed_completed_attempt(
                "reading",
                test_id="reading_jijing_5_test_59",
            )

        with (
            patch.object(
                app_module,
                "_load_reading_test_payload",
                return_value=(
                    {"title": "Reading machine questions"},
                    None,
                    "reading_jijing_5_test_59",
                ),
            ),
            patch.object(
                app_module,
                "_grade_reading_test_answers",
                return_value=self._second_grade(),
            ),
            patch.object(app_module, "_sync_reading_test_score_record"),
            self.app.test_request_context(
                "/api/reading/test/reading_jijing_5_test_59/submit",
                method="POST",
                json={
                    "task_id": task_id,
                    "token": "reading-token",
                    "passage_number": 1,
                    "answers": {"1": "second"},
                },
            ),
        ):
            response = self.app.make_response(
                app_module.api_reading_test_submit("reading_jijing_5_test_59")
            )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertFalse(response.get_json()["task"]["read_only"])
        with self.app.app_context():
            self._assert_attempts_preserved(
                task_id,
                "reading",
                ReadingTestSubmission,
            )

    def test_historical_cambridge_retry_remains_locked(self):
        yesterday = (beijing_today() - timedelta(days=1)).isoformat()
        with self.app.app_context():
            task_id = self._seed_completed_attempt(
                "listening",
                task_date=yesterday,
            )

        with (
            patch.object(
                app_module,
                "_load_listening_test_payload",
                return_value=({"title": "Historical listening"}, None, "retry_listening"),
            ),
            self.app.test_request_context(
                "/api/listening/test/retry_listening/submit",
                method="POST",
                json={
                    "task_id": task_id,
                    "token": "listening-token",
                    "section_number": 1,
                    "answers": {"1": "late retry"},
                },
            ),
        ):
            response = self.app.make_response(
                app_module.api_listening_test_submit("retry_listening")
            )

        self.assertEqual(response.status_code, 403, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["error"], "task_completed_read_only")
        with self.app.app_context():
            self.assertEqual(
                PracticeSubmissionAttempt.query.filter_by(task_id=task_id).count(),
                1,
            )

    def test_completed_generic_task_does_not_gain_reading_retry_access(self):
        with self.app.app_context():
            user = User(
                username="generic-task-student",
                display_name="普通任务学生",
                password_hash="unused",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()
            user_id = user.id
            student_name = user.display_name
            db.session.add(StudentProfile(user_id=user_id, full_name=student_name))
            task = Task(
                date=beijing_today().isoformat(),
                student_name=student_name,
                category="词汇",
                detail="legacy generic task",
                status="done",
                student_submitted=True,
                submitted_at=datetime.utcnow(),
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        student = SimpleNamespace(
            is_authenticated=True,
            role=User.ROLE_STUDENT,
            id=user_id,
            display_name=student_name,
            username="generic-task-student",
        )
        with (
            patch.object(app_module, "current_user", student),
            patch.object(
                app_module,
                "_load_reading_test_payload",
                return_value=({"title": "Reading"}, None, "ielts11_test2_reading"),
            ),
            self.app.test_request_context(
                "/api/reading/test/ielts11_test2_reading/submit",
                method="POST",
                json={"task_id": task_id, "answers": {"1": "x"}},
            ),
        ):
            response = self.app.make_response(
                app_module.api_reading_test_submit("ielts11_test2_reading")
            )

        self.assertEqual(response.status_code, 403, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["error"], "task_completed_read_only")
        with self.app.app_context():
            self.assertIsNone(
                ReadingTestSubmission.query.filter_by(task_id=task_id).one_or_none()
            )

    def test_staff_date_gate_exemption_is_unchanged(self):
        historical_task = SimpleNamespace(
            date=(beijing_today() - timedelta(days=1)).isoformat(),
            status="done",
        )
        staff = SimpleNamespace(
            is_authenticated=True,
            role=User.ROLE_ASSISTANT,
        )

        with patch.object(app_module, "current_user", staff):
            self.assertIsNone(
                app_module._student_task_gate_response(
                    historical_task,
                    allow_completed_today=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
