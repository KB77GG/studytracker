import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask
from flask_login import LoginManager

from api.entrance import entrance_bp
from models import (
    EntranceTestAnswer,
    EntranceTestAttempt,
    EntranceTestDraft,
    EntranceTestInvitation,
    EntranceTestPaper,
    EntranceTestQuestion,
    EntranceTestSection,
    User,
    db,
)


class EntranceSessionRouteTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        database_path = Path(self.tempdir.name) / "entrance.db"
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{database_path}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(entrance_bp)

        login_manager = LoginManager()
        login_manager.init_app(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        with self.app.app_context():
            db.create_all()
            self.teacher = User(
                username="entrance_teacher",
                email="entrance@example.com",
                password_hash="not-used",
                role="teacher",
            )
            db.session.add(self.teacher)
            db.session.flush()

            self.paper = EntranceTestPaper(
                title="Entrance session test paper",
                exam_type="ielts",
                level="ielts_45_55",
                description="test",
                is_active=True,
                created_by=self.teacher.id,
            )
            db.session.add(self.paper)
            db.session.flush()
            self.section = EntranceTestSection(
                paper_id=self.paper.id,
                section_type="listening",
                sequence=1,
                title="Listening",
                instructions="Listen once",
                audio_url="/static/test.mp3",
                duration_minutes=30,
            )
            db.session.add(self.section)
            db.session.flush()
            self.question = EntranceTestQuestion(
                section_id=self.section.id,
                sequence=1,
                question_type="single_choice",
                stem="Choose A",
                options_json=json.dumps(
                    [{"key": "A", "text": "A"}, {"key": "B", "text": "B"}]
                ),
                correct_answer="A",
                points=1,
            )
            db.session.add(self.question)
            db.session.flush()
            self.invitation = EntranceTestInvitation(
                token="entrance-session-token",
                paper_id=self.paper.id,
                student_name="测试学生",
                student_grade="准高一",
                has_studied_target=False,
                target_exam="ielts",
                created_by=self.teacher.id,
                status="pending",
            )
            db.session.add(self.invitation)
            db.session.commit()
            self.teacher_id = self.teacher.id
            self.invitation_id = self.invitation.id
            self.question_id = self.question.id
            self.section_id = self.section.id

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.tempdir.cleanup()

    @property
    def token(self):
        return "entrance-session-token"

    def start(self, device="device-aaaaaaaa"):
        return self.client.post(
            f"/api/entrance/session/{self.token}/start",
            json={"device_id": device},
        )

    def login_teacher(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.teacher_id)
            session["_fresh"] = True

    def test_invitation_metadata_does_not_start_timer(self):
        response = self.client.get(f"/api/entrance/invitation/{self.token}")
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            invitation = db.session.get(EntranceTestInvitation, self.invitation_id)
            self.assertEqual(invitation.status, "pending")
            self.assertIsNone(invitation.started_at)
            self.assertIsNone(invitation.draft)

    def test_autosave_and_same_device_restore(self):
        started = self.start()
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.get_json()["session"]["answers"], {})

        saved = self.client.post(
            f"/api/entrance/session/{self.token}/save",
            json={
                "device_id": "device-aaaaaaaa",
                "answers": [{"question_id": self.question_id, "answer_text": "A"}],
            },
        )
        self.assertEqual(saved.status_code, 200)
        restored = self.start()
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(
            restored.get_json()["session"]["answers"][str(self.question_id)],
            "A",
        )

    def test_short_exit_resumes_but_long_exit_locks(self):
        self.assertEqual(self.start().status_code, 200)
        hidden = self.client.post(
            f"/api/entrance/session/{self.token}/event",
            json={"device_id": "device-aaaaaaaa", "event": "hidden"},
        )
        self.assertEqual(hidden.status_code, 200)
        with self.app.app_context():
            draft = EntranceTestDraft.query.filter_by(invitation_id=self.invitation_id).one()
            draft.hidden_at = datetime.utcnow() - timedelta(seconds=30)
            db.session.commit()
        visible = self.client.post(
            f"/api/entrance/session/{self.token}/event",
            json={"device_id": "device-aaaaaaaa", "event": "visible"},
        )
        self.assertEqual(visible.status_code, 200)
        self.assertGreaterEqual(visible.get_json()["session"]["total_hidden_seconds"], 29)

        self.client.post(
            f"/api/entrance/session/{self.token}/event",
            json={"device_id": "device-aaaaaaaa", "event": "hidden"},
        )
        with self.app.app_context():
            draft = EntranceTestDraft.query.filter_by(invitation_id=self.invitation_id).one()
            draft.hidden_at = datetime.utcnow() - timedelta(seconds=180)
            db.session.commit()
        locked = self.client.post(
            f"/api/entrance/session/{self.token}/event",
            json={"device_id": "device-aaaaaaaa", "event": "visible"},
        )
        self.assertEqual(locked.status_code, 423)
        self.assertEqual(locked.get_json()["error"], "left_too_long")
        with self.app.app_context():
            draft = EntranceTestDraft.query.filter_by(invitation_id=self.invitation_id).one()
            self.assertTrue(draft.is_locked)

    def test_different_device_locks_session(self):
        self.assertEqual(self.start("device-aaaaaaaa").status_code, 200)
        switched = self.start("device-bbbbbbbb")
        self.assertEqual(switched.status_code, 423)
        self.assertEqual(switched.get_json()["error"], "device_changed")
        with self.app.app_context():
            draft = EntranceTestDraft.query.filter_by(invitation_id=self.invitation_id).one()
            self.assertTrue(draft.is_locked)
            self.assertEqual(draft.device_switch_count, 1)

    def test_audio_start_is_enforced_on_server(self):
        self.assertEqual(self.start().status_code, 200)
        path = f"/api/entrance/session/{self.token}/audio/{self.section_id}/start"
        first = self.client.post(path, json={"device_id": "device-aaaaaaaa"})
        second = self.client.post(path, json={"device_id": "device-aaaaaaaa"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.get_json()["error"], "audio_already_started")

    def test_expired_submit_uses_latest_payload_and_finalizes(self):
        self.assertEqual(self.start().status_code, 200)
        with self.app.app_context():
            draft = EntranceTestDraft.query.filter_by(invitation_id=self.invitation_id).one()
            draft.deadline_at = datetime.utcnow() - timedelta(seconds=1)
            db.session.commit()
        response = self.client.post(
            f"/api/entrance/submit/{self.token}",
            json={
                "device_id": "device-aaaaaaaa",
                "answers": [{"question_id": self.question_id, "answer_text": "A"}],
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "time_expired")
        with self.app.app_context():
            invitation = db.session.get(EntranceTestInvitation, self.invitation_id)
            attempt = EntranceTestAttempt.query.filter_by(invitation_id=self.invitation_id).one()
            answer = EntranceTestAnswer.query.filter_by(attempt_id=attempt.id).one()
            self.assertEqual(invitation.status, "submitted")
            self.assertEqual(attempt.auto_score_listening, 1)
            self.assertEqual(answer.answer_text, "A")

    def test_teacher_can_unlock_reset_device_and_extend_time(self):
        self.assertEqual(self.start("device-aaaaaaaa").status_code, 200)
        self.assertEqual(self.start("device-bbbbbbbb").status_code, 423)
        self.login_teacher()
        response = self.client.post(
            f"/api/entrance/admin/invitations/{self.invitation_id}/unlock",
            json={"extra_minutes": 10, "reset_device": True, "reset_audio": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["session"]["is_locked"])
        resumed = self.start("device-bbbbbbbb")
        self.assertEqual(resumed.status_code, 200)


if __name__ == "__main__":
    unittest.main()
