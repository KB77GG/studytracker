import unittest

from flask import Flask

from api.mock_exam_student import mock_exam_student_bp
from models import MockExam, MockExamSession, db


class MockExamRuntimeRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="runtime-route-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)

        @self.app.get("/exam/<int:exam_id>/session/<token>")
        def mock_exam_process(exam_id, token):
            return f"process:{exam_id}:{token}"

        self.app.register_blueprint(mock_exam_student_bp)
        with self.app.app_context():
            db.create_all()
            exam = MockExam(
                name="Runtime test",
                listening_test_id="listening-test",
                reading_test_id="reading-test",
                pincode="12345",
                listening_minutes=30,
            )
            db.session.add(exam)
            db.session.flush()
            session = MockExamSession(
                exam_id=exam.id,
                student_name="Student",
                access_token="runtime-token",
                status=MockExamSession.STATUS_IN_PROGRESS,
                current_section=MockExamSession.SECTION_INTRO,
            )
            db.session.add(session)
            db.session.commit()
            self.exam_id = exam.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_preflight_start_is_idempotent_and_server_owned(self):
        url = f"/api/exam/{self.exam_id}/session/runtime-token/start-listening"
        first = self.client.post(url, json={}).get_json()
        second = self.client.post(url, json={}).get_json()
        self.assertTrue(first["ok"])
        self.assertEqual(first["started_at"], second["started_at"])
        self.assertEqual(first["deadline_at"], second["deadline_at"])

        with self.app.app_context():
            session = MockExamSession.query.filter_by(access_token="runtime-token").one()
            self.assertEqual(session.current_section, MockExamSession.SECTION_LISTENING)
            self.assertEqual(
                int((session.listening_deadline_at - session.listening_started_at).total_seconds()),
                32 * 60,
            )

    def test_verified_audio_duration_sets_runtime_and_completion_is_idempotent(self):
        start_url = f"/api/exam/{self.exam_id}/session/runtime-token/start-listening"
        complete_url = f"/api/exam/{self.exam_id}/session/runtime-token/complete-listening-audio"
        started = self.client.post(start_url, json={"audio_duration_seconds": 1519.2}).get_json()
        self.assertTrue(started["ok"])
        with self.app.app_context():
            session = MockExamSession.query.filter_by(access_token="runtime-token").one()
            self.assertEqual(
                int((session.listening_deadline_at - session.listening_started_at).total_seconds()),
                1640,
            )

        first = self.client.post(complete_url, json={}).get_json()
        second = self.client.post(complete_url, json={}).get_json()
        self.assertTrue(first["ok"])
        self.assertEqual(first["deadline_at"], second["deadline_at"])

    def test_draft_round_trip_returns_only_student_answers_and_clock(self):
        start_url = f"/api/exam/{self.exam_id}/session/runtime-token/start-listening"
        draft_url = f"/api/exam/{self.exam_id}/session/runtime-token/draft/listening"
        self.client.post(start_url, json={})
        saved = self.client.put(draft_url, json={"answers": {"1": "alpha"}})
        loaded = self.client.get(draft_url)

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(loaded.status_code, 200)
        body = loaded.get_json()
        self.assertEqual(body["answers"], {"1": "alpha"})
        self.assertIsNotNone(body["started_at"])
        self.assertIsNotNone(body["deadline_at"])
        for forbidden in ("result", "results", "answer", "correct", "score"):
            self.assertNotIn(forbidden, body)

    def test_unknown_token_cannot_start_or_read_draft(self):
        base = f"/api/exam/{self.exam_id}/session/wrong-token"
        self.assertEqual(self.client.post(f"{base}/start-listening", json={}).status_code, 404)
        self.assertEqual(self.client.get(f"{base}/draft/listening").status_code, 404)


if __name__ == "__main__":
    unittest.main()
