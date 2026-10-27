"""Exercise real account routes against synthetic, in-memory identities only.

Load the complete app with a private config module before initialization: neither
.env nor app.db is opened, startup schema work stays in memory, uploads use a
temporary directory, and socket connections are forbidden throughout the suite.
"""

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import g
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from models import ParentStudentLink, StudentProfile, User, db

ROOT = Path(__file__).resolve().parents[1]


class AutoStudentAccountsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for target in ("socket.socket.connect", "socket.getaddrinfo"):
            guard = patch(target, side_effect=AssertionError("Network forbidden in account tests"))
            blocked = guard.start()
            cls.addClassCleanup(guard.stop)
            cls.addClassCleanup(blocked.assert_not_called)
        cls.uploads = tempfile.TemporaryDirectory(prefix="studytracker-account-tests-")
        cls.addClassCleanup(cls.uploads.cleanup)

        config = types.ModuleType("config")
        config.Config = type(
            "TestConfig",
            (),
            {
                "TESTING": True,
                "SECRET_KEY": "synthetic-account-regression-secret",
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "UPLOAD_FOLDER": cls.uploads.name,
            },
        )
        module_name = "_account_regression_app"
        spec = importlib.util.spec_from_file_location(module_name, ROOT / "app.py")
        cls.module = importlib.util.module_from_spec(spec)
        original_config = sys.modules.get("config")
        sys.modules["config"] = config
        sys.modules[module_name] = cls.module
        cls.addClassCleanup(sys.modules.pop, module_name, None)
        try:
            spec.loader.exec_module(cls.module)
        finally:
            # Restore only config; a whole sys.modules snapshot would discard
            # newly loaded blueprints and make later patches target stale copies.
            if original_config is None:
                sys.modules.pop("config", None)
            else:
                sys.modules["config"] = original_config
        cls.app = cls.module.app
        with cls.app.app_context():
            assert db.engine.url.database == ":memory:"
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.session.remove)
        # All records below are invented fixtures, never copied from a live DB.
        db.session.query(ParentStudentLink).delete()
        db.session.query(StudentProfile).delete()
        db.session.query(User).delete()
        self.admin = self._user("fixture-admin", User.ROLE_ADMIN)
        self.assistant = self._user("fixture-assistant", User.ROLE_ASSISTANT)
        self.old_student = self._user("fixture-old-student", User.ROLE_STUDENT)
        self.old_parent = self._user("fixture-old-parent", User.ROLE_PARENT)
        self.old_profile = StudentProfile(
            full_name="既有合成学生",
            user_id=self.old_student.id,
            primary_parent_id=self.old_parent.id,
            guardian_view_token="fixture-guardian-token",
        )
        db.session.add(self.old_profile)
        db.session.add(
            ParentStudentLink(
                parent_id=self.old_parent.id,
                student_name=self.old_profile.full_name,
                relation="母亲",
                is_active=True,
            )
        )
        db.session.commit()
        self.before = self._snapshot()
        self.client = self.app.test_client()
        self._login_as(self.admin)

    def _user(self, username, role, *, active=True):
        user = User(
            username=username,
            display_name=username,
            role=role,
            is_active=active,
            wechat_openid=f"fixture-openid-{username}",
            wechat_unionid=f"fixture-unionid-{username}",
            auth_token_hash=f"fixture-token-hash-{username}",
        )
        user.set_password("fixture-custom-password")
        db.session.add(user)
        db.session.flush()
        return user

    def _snapshot(self):
        # Include every persisted identity/relationship column, including hashes.
        return {
            model.__tablename__: [
                tuple(getattr(row, col.name) for col in model.__table__.columns)
                for row in model.query.order_by(model.id).all()
            ]
            for model in (User, StudentProfile, ParentStudentLink)
        }

    def _assert_old_rows_unchanged(self):
        after = self._snapshot()
        for table, rows in self.before.items():
            self.assertEqual(after[table][: len(rows)], rows, table)

    def _login_as(self, user):
        # The test deliberately holds an app context to inspect rollback before
        # teardown; clear Flask-Login's context cache when changing clients.
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(user.id)
            session["_fresh"] = True

    def _create(self, name="测试学生"):
        return self.client.post("/api/users/auto-student", json={"full_name": name})

    def test_success_creates_complete_pair_with_legacy_credentials(self):
        response = self._create("  测试学生  ")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "ok": True,
                "data": {
                    "student_username": "测试学生",
                    "student_password": "ceshixuesheng123",
                    "parent_username": "测试学生家长",
                    "parent_password": "ceshixuesheng123prt",
                },
            },
        )
        db.session.remove()  # Verify committed rows through a fresh ORM session.
        student = User.query.filter_by(username="测试学生").one()
        parent = User.query.filter_by(username="测试学生家长").one()
        profile = StudentProfile.query.filter_by(user_id=student.id).one()
        link = ParentStudentLink.query.filter_by(parent_id=parent.id).one()
        self.assertEqual(
            (User.query.count(), StudentProfile.query.count(), ParentStudentLink.query.count()),
            (6, 2, 2),
        )
        self.assertEqual((student.role, parent.role), (User.ROLE_STUDENT, User.ROLE_PARENT))
        self.assertTrue(student.is_active and parent.is_active)
        self.assertTrue(student.check_password("ceshixuesheng123"))
        self.assertTrue(parent.check_password("ceshixuesheng123prt"))
        self.assertNotEqual(student.password_hash, "ceshixuesheng123")
        self.assertEqual(profile.primary_parent_id, parent.id)
        self.assertEqual(profile.full_name, "测试学生")
        self.assertTrue(profile.guardian_view_token)
        self.assertNotEqual(profile.guardian_view_token, "fixture-guardian-token")
        self.assertEqual(
            (link.student_name, link.relation, link.is_active), ("测试学生", "家长", True)
        )
        self._assert_old_rows_unchanged()

    def test_assistant_can_create_accounts(self):
        self._login_as(self.assistant)
        self.assertEqual(self._create().status_code, 200)

    def test_empty_names_are_rejected_without_writes(self):
        for payload in ({}, {"full_name": None}, {"full_name": ""}, {"full_name": " \t "}):
            with self.subTest(payload=payload):
                response = self.client.post("/api/users/auto-student", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], "missing_full_name")
                self.assertEqual(self._snapshot(), self.before)

    def test_repeated_name_preserves_first_pair(self):
        self.assertEqual(self._create().status_code, 200)
        created = self._snapshot()
        response = self._create(" 测试学生 ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "duplicate_username")
        self.assertEqual(self._snapshot(), created)

    def test_either_username_conflict_including_inactive_users_is_rejected(self):
        for name, occupied, active in (
            ("合成甲", "合成甲", True),
            ("合成乙", "合成乙家长", True),
            ("合成丙", "合成丙", False),
            ("合成丁", "合成丁家长", False),
        ):
            with self.subTest(occupied=occupied, active=active):
                self._user(occupied, User.ROLE_PARENT, active=active)
                db.session.commit()
                before = self._snapshot()
                response = self._create(name)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], "duplicate_username")
                self.assertEqual(self._snapshot(), before)

    def test_same_name_profile_is_not_merged_or_reassigned(self):
        # Preserve the existing profile-only behavior; name-based lookup ambiguity
        # is a separate identity-design issue, not permission to merge old data.
        db.session.add(StudentProfile(full_name="测试学生", notes="synthetic standalone profile"))
        db.session.commit()
        self.before = self._snapshot()
        self.assertEqual(self._create().status_code, 200)
        self.assertEqual(StudentProfile.query.filter_by(full_name="测试学生").count(), 2)
        self._assert_old_rows_unchanged()

    def test_real_database_failures_rollback_all_rows_and_allow_retry(self):
        # Trigger actual SQLite IntegrityErrors at initial flush and at each of
        # the two association writes, after some prior INSERTs have succeeded.
        for table, condition in (
            ("user", "NEW.role = 'parent'"),
            ("student_profile", "1"),
            ("parent_student_link", "1"),
        ):
            with self.subTest(table=table):
                before = self._snapshot()
                db.session.execute(
                    text(
                        f'CREATE TEMP TRIGGER reject_account BEFORE INSERT ON "{table}" '
                        f"WHEN {condition} BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"
                    )
                )
                db.session.commit()
                try:
                    with self.assertLogs(self.app.logger, level="ERROR"):
                        response = self._create(f"合成回滚{table}")
                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(response.get_json()["error"], "db_error")
                    self.assertFalse(response.get_json()["ok"])
                    self.assertNotIn("data", response.get_json())
                    # Still in the same app context: failed sessions must have
                    # been explicitly rolled back, not rescued by teardown.
                    self.assertEqual(self._snapshot(), before)
                    self.assertFalse(db.session.new)
                    self.assertTrue(db.session.is_active)
                finally:
                    db.session.rollback()
                    db.session.execute(text("DROP TRIGGER reject_account"))
                    db.session.commit()
                self.assertEqual(self._create(f"合成回滚{table}").status_code, 200)
                self._assert_old_rows_unchanged()

    def test_commit_failure_after_all_inserts_rolls_back_and_allows_retry(self):
        def fail_commit():
            db.session.flush()
            self.assertEqual(User.query.count(), 6)
            self.assertEqual(StudentProfile.query.count(), 2)
            self.assertEqual(ParentStudentLink.query.count(), 2)
            raise SQLAlchemyError("synthetic commit failure")

        with (
            patch.object(db.session, "commit", side_effect=fail_commit),
            self.assertLogs(self.app.logger, level="ERROR"),
        ):
            response = self._create()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()["error"], "db_error")
        self.assertEqual(self._snapshot(), self.before)
        self.assertTrue(db.session.is_active)
        self.assertEqual(self._create().status_code, 200)
        self._assert_old_rows_unchanged()

    def test_anonymous_and_nonstaff_cannot_create_accounts(self):
        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.post("/api/users/auto-student", json={"full_name": "测试学生"}).status_code,
            302,
        )
        for user in (
            self.old_student,
            self.old_parent,
            self._user("fixture-teacher", User.ROLE_TEACHER),
        ):
            with self.subTest(role=user.role):
                self._login_as(user)
                before = self._snapshot()
                response = self.client.post(
                    "/api/users/auto-student",
                    json={"full_name": "测试学生"},
                    headers={"Accept": "application/json"},
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.get_json()["error"], "forbidden")
                self.assertEqual(self._snapshot(), before)

    def test_old_and_new_student_parent_web_password_login(self):
        self.assertEqual(self._create().status_code, 200)
        self._assert_old_rows_unchanged()
        for username, password in (
            ("fixture-old-student", "fixture-custom-password"),
            ("fixture-old-parent", "fixture-custom-password"),
            ("测试学生", "ceshixuesheng123"),
            ("测试学生家长", "ceshixuesheng123prt"),
        ):
            with self.subTest(username=username):
                client = self.app.test_client()
                response = client.post("/login", data={"username": username, "password": password})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location, "/")
                with client.session_transaction() as session:
                    self.assertEqual(
                        session["_user_id"], str(User.query.filter_by(username=username).one().id)
                    )
        self._assert_old_rows_unchanged()

    def test_wrong_password_and_inactive_accounts_still_cannot_log_in(self):
        self.assertEqual(self._create().status_code, 200)
        for username in ("fixture-old-student", "fixture-old-parent", "测试学生", "测试学生家长"):
            with self.subTest(username=username):
                client = self.app.test_client()
                response = client.post("/login", data={"username": username, "password": "wrong"})
                self.assertEqual(response.status_code, 200)
                with client.session_transaction() as session:
                    self.assertNotIn("_user_id", session)
        self.old_student.is_active = False
        self.old_parent.is_active = False
        db.session.commit()
        for username in ("fixture-old-student", "fixture-old-parent"):
            client = self.app.test_client()
            response = client.post(
                "/login", data={"username": username, "password": "fixture-custom-password"}
            )
            self.assertEqual(response.status_code, 200)
            with client.session_transaction() as session:
                self.assertNotIn("_user_id", session)

    def test_existing_wechat_bindings_and_parent_children_remain_usable(self):
        self.assertEqual(self._create().status_code, 200)
        self._assert_old_rows_unchanged()
        for user in (self.old_student, self.old_parent):
            with self.subTest(role=user.role):
                old_hash = user.password_hash
                old_id = user.id
                with patch(
                    "api.wechat.get_wechat_session",
                    return_value={
                        "openid": user.wechat_openid,
                        "unionid": user.wechat_unionid,
                    },
                ) as provider:
                    response = self.client.post(
                        "/api/wechat/login", json={"code": "synthetic-code"}
                    )
                provider.assert_called_once_with("synthetic-code")
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertTrue(payload["ok"])
                self.assertEqual(User.query.count(), 6)
                db.session.refresh(user)
                self.assertEqual(user.id, old_id)
                self.assertEqual(user.password_hash, old_hash)
                if user.role == User.ROLE_PARENT:
                    children = self.client.get(
                        "/api/miniprogram/parent/children",
                        headers={
                            "Authorization": f"Bearer {payload['token']}",
                        },
                    )
                    self.assertEqual(children.status_code, 200)
                    self.assertEqual(
                        children.get_json()["children"],
                        [
                            {
                                "name": "既有合成学生",
                                "relation": "母亲",
                                "student_id": self.old_profile.id,
                                "has_profile": True,
                            }
                        ],
                    )

    def test_new_parent_link_is_visible_through_authenticated_children_api(self):
        from api.auth_utils import issue_token

        self.assertEqual(self._create().status_code, 200)
        parent = User.query.filter_by(username="测试学生家长").one()
        profile = StudentProfile.query.filter_by(full_name="测试学生").one()
        _, token = issue_token(parent)
        response = self.client.get(
            "/api/miniprogram/parent/children", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["children"],
            [
                {
                    "name": "测试学生",
                    "relation": "家长",
                    "student_id": profile.id,
                    "has_profile": True,
                }
            ],
        )
        self._assert_old_rows_unchanged()


if __name__ == "__main__":
    unittest.main()
