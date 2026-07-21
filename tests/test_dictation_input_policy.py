import time
import unittest
from datetime import timedelta
from pathlib import Path

import jwt
from flask import Flask
from flask_login import LoginManager

from api.dictation import dictation_bp
from api.dictation_input import dictation_input_bp
from models import (
    DictationBook,
    DictationInputGrant,
    DictationRecord,
    DictationWord,
    StudentProfile,
    User,
    db,
)


class DictationInputPolicyApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="input-policy-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(dictation_bp)
        self.app.register_blueprint(dictation_input_bp)

        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="input_policy_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            unrelated_teacher = User(
                username="unrelated_input_policy_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            assistant = User(
                username="input_policy_assistant",
                password_hash="test",
                role=User.ROLE_ASSISTANT,
                is_active=True,
            )
            student = User(
                username="input_policy_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, unrelated_teacher, assistant, student])
            db.session.flush()
            profile = StudentProfile(
                user_id=student.id,
                full_name="输入策略学生",
                primary_teacher_id=teacher.id,
            )
            book = DictationBook(
                title="输入策略词库",
                word_count=2,
                created_by=teacher.id,
                is_active=True,
            )
            db.session.add_all([profile, book])
            db.session.flush()
            words = [
                DictationWord(
                    book_id=book.id,
                    sequence=1,
                    word="alpha",
                    translation="甲",
                ),
                DictationWord(
                    book_id=book.id,
                    sequence=2,
                    word="bravo",
                    translation="乙",
                ),
            ]
            db.session.add_all(words)
            db.session.commit()
            self.teacher_id = teacher.id
            self.unrelated_teacher_id = unrelated_teacher.id
            self.assistant_id = assistant.id
            self.student_id = student.id
            self.profile_id = profile.id
            self.book_id = book.id
            self.word_ids = [word.id for word in words]

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def headers(self, user_id, role):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": str(user_id),
                "role": role,
                "iat": now,
                "exp": now + int(timedelta(hours=1).total_seconds()),
            },
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def login_session(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def submit(self, word_id, answer, input_mode, attempt_id):
        return self.client.post(
            "/api/dictation/submit",
            headers=self.headers(self.student_id, User.ROLE_STUDENT),
            json={
                "word_id": word_id,
                "book_id": self.book_id,
                "answer": answer,
                "mode": "zh_to_en",
                "input_mode": input_mode,
                "attempt_id": attempt_id,
            },
        )

    def test_strict_is_default_and_chinese_input_is_native(self):
        strict = self.client.get(
            "/api/dictation/input-policy?mode=zh_to_en",
            headers=self.headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(strict.status_code, 200)
        self.assertEqual(strict.get_json()["policy"]["default_input_mode"], "strict")
        self.assertFalse(strict.get_json()["policy"]["compatible_allowed"])

        native = self.client.get(
            "/api/dictation/input-policy?mode=en_to_zh",
            headers=self.headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertEqual(native.status_code, 200)
        self.assertEqual(native.get_json()["policy"]["default_input_mode"], "native")
        self.assertFalse(native.get_json()["policy"]["is_english_spelling"])

        submitted = self.client.post(
            "/api/dictation/submit",
            headers=self.headers(self.student_id, User.ROLE_STUDENT),
            json={
                "word_id": self.word_ids[0],
                "book_id": self.book_id,
                "answer": "甲",
                "mode": "en_to_zh",
                "input_mode": "compatible",
                "attempt_id": "native-chinese-path",
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.get_json())
        self.assertEqual(submitted.get_json()["input_mode"], "native")

    def test_student_cannot_self_authorize_and_compatible_submission_is_rejected(self):
        self.assertEqual(
            self.client.post(
                "/api/dictation/input-grants",
                headers=self.headers(self.student_id, User.ROLE_STUDENT),
                json={"student_profile_id": self.profile_id, "duration_days": 7},
            ).status_code,
            403,
        )
        rejected = self.submit(
            self.word_ids[0],
            "alpha",
            "compatible",
            "unauthorized-compatible",
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.get_json()["error"], "compatible_input_not_authorized")
        with self.app.app_context():
            self.assertEqual(DictationRecord.query.count(), 0)

    def test_teacher_grant_is_server_checked_recorded_and_revoke_takes_effect(self):
        created = self.client.post(
            "/api/dictation/input-grants",
            headers=self.headers(self.teacher_id, User.ROLE_TEACHER),
            json={
                "student_profile_id": self.profile_id,
                "duration_days": 7,
                "reason": "测试授权",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        grant_id = created.get_json()["grant"]["id"]

        policy = self.client.get(
            "/api/dictation/input-policy?mode=audio_to_en",
            headers=self.headers(self.student_id, User.ROLE_STUDENT),
        )
        self.assertTrue(policy.get_json()["policy"]["compatible_allowed"])
        self.assertEqual(policy.get_json()["policy"]["grant"]["id"], grant_id)

        accepted = self.submit(
            self.word_ids[0],
            "alpha",
            "compatible",
            "authorized-compatible",
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assertEqual(accepted.get_json()["input_mode"], "compatible")
        with self.app.app_context():
            record = DictationRecord.query.one()
            self.assertEqual(record.input_mode, "compatible")
            self.assertEqual(record.input_grant_id, grant_id)

        revoked = self.client.post(
            f"/api/dictation/input-grants/{grant_id}/revoke",
            headers=self.headers(self.teacher_id, User.ROLE_TEACHER),
        )
        self.assertEqual(revoked.status_code, 200, revoked.get_json())
        rejected = self.submit(
            self.word_ids[1],
            "bravo",
            "compatible",
            "revoked-compatible",
        )
        self.assertEqual(rejected.status_code, 403)

        strict = self.submit(
            self.word_ids[1],
            "bravo",
            "strict",
            "strict-after-revoke",
        )
        self.assertEqual(strict.status_code, 200, strict.get_json())
        self.assertEqual(strict.get_json()["input_mode"], "strict")

        with self.app.app_context():
            grant = db.session.get(DictationInputGrant, grant_id)
            self.assertIsNotNone(grant.revoked_at)

    def test_assistant_back_office_can_replace_and_revoke_shared_student_grant(self):
        self.login_session(self.assistant_id)
        initial = self.client.get(
            f"/api/dictation/staff/input-grants?student_profile_id={self.profile_id}"
        )
        self.assertEqual(initial.status_code, 200, initial.get_json())
        self.assertTrue(initial.get_json()["student_has_login"])
        self.assertIsNone(initial.get_json()["active_grant"])

        seven_days = self.client.post(
            "/api/dictation/staff/input-grants",
            json={"student_profile_id": self.profile_id, "duration_days": 7},
        )
        self.assertEqual(seven_days.status_code, 201, seven_days.get_json())
        first_grant_id = seven_days.get_json()["grant"]["id"]

        thirty_days = self.client.post(
            "/api/dictation/staff/input-grants",
            json={"student_profile_id": self.profile_id, "duration_days": 30},
        )
        self.assertEqual(thirty_days.status_code, 201, thirty_days.get_json())
        second_grant_id = thirty_days.get_json()["grant"]["id"]

        listed = self.client.get(
            f"/api/dictation/staff/input-grants?student_profile_id={self.profile_id}"
        )
        self.assertEqual(listed.get_json()["active_grant"]["id"], second_grant_id)
        with self.app.app_context():
            first_grant = db.session.get(DictationInputGrant, first_grant_id)
            self.assertIsNotNone(first_grant.revoked_at)

        revoked = self.client.post(
            f"/api/dictation/staff/input-grants/{second_grant_id}/revoke"
        )
        self.assertEqual(revoked.status_code, 200, revoked.get_json())
        after_revoke = self.client.get(
            f"/api/dictation/staff/input-grants?student_profile_id={self.profile_id}"
        )
        self.assertIsNone(after_revoke.get_json()["active_grant"])

    def test_back_office_requires_staff_and_keeps_teachers_student_scoped(self):
        anonymous = self.client.get(
            f"/api/dictation/staff/input-grants?student_profile_id={self.profile_id}"
        )
        self.assertEqual(anonymous.status_code, 401)

        self.login_session(self.student_id)
        student_attempt = self.client.post(
            "/api/dictation/staff/input-grants",
            json={"student_profile_id": self.profile_id, "duration_days": 7},
        )
        self.assertEqual(student_attempt.status_code, 403)

        self.login_session(self.unrelated_teacher_id)
        unrelated_teacher = self.client.post(
            "/api/dictation/staff/input-grants",
            json={"student_profile_id": self.profile_id, "duration_days": 7},
        )
        self.assertEqual(unrelated_teacher.status_code, 403)


class DictationInputBackOfficeMarkupTest(unittest.TestCase):
    def test_tasks_page_exposes_staff_grant_status_duration_and_revoke_controls(self):
        markup = (
            Path(__file__).resolve().parents[1] / "templates/tasks.html"
        ).read_text(encoding="utf-8")
        self.assertIn("单词任务输入授权", markup)
        self.assertIn('data-input-grant-days="7"', markup)
        self.assertIn('data-input-grant-days="30"', markup)
        self.assertIn("inputGrantRevoke", markup)
        self.assertIn("/api/dictation/staff/input-grants", markup)
        self.assertIn("授权只影响单词任务", markup)
        self.assertIn("不影响听力、阅读或其他刷题", markup)


if __name__ == "__main__":
    unittest.main()
