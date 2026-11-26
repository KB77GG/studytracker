"""Resolve only synthetic practice identities in an isolated request/session."""

import unittest

from flask import Flask, g, session
from flask_login import LoginManager

from models import StudentProfile, User, db
from services.practice_student_identity import PracticeIdentityError, resolve_practice_student


class PracticeStudentIdentityTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="synthetic-identity-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)
        login_manager.user_loader(lambda user_id: db.session.get(User, int(user_id)))
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.a, self.pa = self._student("a", "合成甲")
        self.b, self.pb = self._student("b", "合成乙")
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def _student(self, suffix, name, active=True):
        user = User(
            username=f"identity-{suffix}", password_hash="test", role="student", is_active=active
        )
        db.session.add(user)
        db.session.flush()
        profile = StudentProfile(user_id=user.id, full_name=name)
        db.session.add(profile)
        db.session.flush()
        return user, profile

    def _resolve(self, *, user=None, name=None, classroom=False, cookie=False):
        headers = {"Cookie": "classroom_unlocked=1"} if cookie else {}
        with self.app.test_request_context("/", headers=headers):
            g.pop("_login_user", None)
            if user:
                session["_user_id"] = str(user.id)
                session["_fresh"] = True
            if name is not None:
                session["practice_student_name"] = name
            if classroom:
                session["classroom_unlocked"] = True
            return resolve_practice_student()

    def assert_error(self, code, **kw):
        with self.assertRaises(PracticeIdentityError) as raised:
            self._resolve(**kw)
        self.assertEqual(raised.exception.code, code)
        return raised.exception

    def test_account_wins_over_other_name_and_same_name_profiles(self):
        db.session.add(StudentProfile(full_name=self.pa.full_name))
        db.session.commit()
        result = self._resolve(user=self.a, name=self.pb.full_name)
        self.assertEqual(
            (result.user.id, result.profile.id, result.via), (self.a.id, self.pa.id, "account")
        )

    def test_name_identity_key_matches_account_and_changes_with_student(self):
        a = self._resolve(name=self.pa.full_name)
        self.assertEqual(a.via, "name_session")
        self.assertEqual(a.identity_key, self._resolve(user=self.a).identity_key)
        self.assertNotEqual(a.identity_key, self._resolve(name=self.pb.full_name).identity_key)
        self.assertEqual(len(a.identity_key), 20)
        self.assertEqual((User.query.count(), StudentProfile.query.count()), (2, 2))
        self.assertFalse(db.session.new or db.session.dirty)

    def test_missing_or_deleted_name_is_removed(self):
        self.pa.is_deleted = True
        db.session.commit()
        with self.app.test_request_context("/"):
            session["practice_student_name"] = self.pa.full_name
            with self.assertRaises(PracticeIdentityError) as raised:
                resolve_practice_student()
            self.assertEqual(
                (raised.exception.code, raised.exception.status), ("identity_missing", 401)
            )
            self.assertNotIn("practice_student_name", session)

    def test_duplicate_live_name_is_rejected_without_guessing(self):
        db.session.add(StudentProfile(full_name=self.pa.full_name))
        db.session.commit()
        self.assertEqual(
            self.assert_error("ambiguous_student_name", name=self.pa.full_name).status, 409
        )

    def test_deleted_duplicate_does_not_block_unique_identity(self):
        db.session.add(StudentProfile(full_name=self.pa.full_name, is_deleted=True))
        db.session.commit()
        self.assertEqual(self._resolve(name=self.pa.full_name).user.id, self.a.id)

    def test_unlinked_account_never_falls_back_to_display_or_name_session(self):
        self.pa.user_id = None
        self.a.display_name = self.pb.full_name
        db.session.commit()
        self.assert_error("student_account_unlinked", user=self.a, name=self.pb.full_name)
        self.assert_error("student_account_missing", name=self.pa.full_name)

    def test_inactive_account_and_linked_nonstudent_are_rejected(self):
        self.a.is_active = False
        db.session.commit()
        self.assert_error("student_account_missing", user=self.a, name=self.pb.full_name)
        self.assert_error("student_account_missing", name=self.pa.full_name)
        self.a.is_active = True
        self.a.role = User.ROLE_PARENT
        db.session.commit()
        self.assert_error("student_account_missing", name=self.pa.full_name)

    def test_staff_and_classroom_modes_cannot_use_name_session(self):
        for role in (User.ROLE_TEACHER, User.ROLE_ASSISTANT, User.ROLE_ADMIN):
            self.a.role = role
            db.session.commit()
            self.assert_error("staff_mode", user=self.a, name=self.pb.full_name)
        self.assert_error("staff_mode", name=self.pb.full_name, classroom=True)
        self.assert_error("staff_mode", name=self.pb.full_name, cookie=True)

    def test_no_identity_has_explicit_unauthenticated_status(self):
        self.assertEqual(self.assert_error("identity_missing").status, 401)
