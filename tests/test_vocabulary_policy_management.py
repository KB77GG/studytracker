"""The enrollment tool defaults to private, read-only, bounded previews."""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from models import User, VocabularyReviewSession, db
from scripts import manage_vocabulary_error_pilot as manager


class VocabularyPolicyManagementTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "synthetic.db"
        self.now = datetime(2026, 11, 17, 4, 0)
        app = Flask(__name__)
        app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///" + str(self.database),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(app)
        with app.app_context():
            db.create_all()
            db.session.add_all(
                User(id=index, username=name, password_hash="test", role=role, is_active=active)
                for index, name, role, active in (
                    (1, "SENSITIVE_STUDENT_A", "student", True),
                    (2, "SENSITIVE_STUDENT_B", "student", True),
                    (3, "SENSITIVE_TEACHER", "teacher", True),
                    (4, "SENSITIVE_INACTIVE", "student", False),
                )
            )
            db.session.commit()
            db.session.remove()
            db.engine.dispose()

    def tearDown(self):
        self.temp.cleanup()

    def preview(self, ids=(1,), **kwargs):
        with manager.readonly(self.database) as connection:
            return manager.preview(
                connection, student_ids=ids, starts_at=self.now, now=self.now, **kwargs
            )

    def counts(self):
        with sqlite3.connect(self.database) as connection:
            return [
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in manager.TABLES
            ]

    def apply(self, ids=(1,), digest=None, **kwargs):
        return manager.apply_enrollment(
            self.database,
            student_ids=ids,
            starts_at=self.now,
            expected_digest=digest or self.preview(ids)["preview_digest"],
            now=self.now,
            **kwargs,
        )

    def test_preview_is_byte_identical_and_exports_no_identities(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        result = self.preview((1, 2, 3, 4, 999))
        self.assertEqual(result["eligible_new_enrollment_count"], 2)
        self.assertEqual(result["invalid_or_inactive_count"], 3)
        self.assertEqual(result["historical_error_rows_to_import"], 0)
        self.assertEqual(result["initial_mandatory_rows_to_create"], 0)
        self.assertNotIn("SENSITIVE", json.dumps(result))
        self.assertNotIn("selection_ids", result)
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).hexdigest())

    def test_readonly_authorizer_denies_identity_and_writes(self):
        with manager.readonly(self.database) as connection:
            for statement in (
                "SELECT username FROM user",
                "SELECT password_hash FROM user",
                "DELETE FROM user",
                "PRAGMA query_only=OFF",
            ):
                with self.assertRaises(sqlite3.DatabaseError):
                    connection.execute(statement)
            self.assertEqual(connection.total_changes, 0)

    def test_cli_without_apply_only_previews(self):
        result = subprocess.run(
            [
                sys.executable,
                manager.__file__,
                "--database",
                str(self.database),
                "--student-id",
                "1",
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertTrue(json.loads(result.stdout)["read_only_preview"])
        self.assertEqual(self.counts(), [0] * 5)

    def test_explicit_apply_only_enrolls_never_imports_history(self):
        result = self.apply((1, 2))
        self.assertEqual(result["enrolled_count"], 2)
        self.assertTrue(result["global_switch_unchanged"])
        self.assertEqual(self.counts(), [2, 0, 0, 0, 0])
        self.assertEqual(self.preview((1, 2))["already_enrolled_count"], 2)

    def test_digest_binds_selection_and_state(self):
        digest = self.preview((1,))["preview_digest"]
        with self.assertRaisesRegex(manager.ManagementError, "preview_changed"):
            self.apply((2,), digest=digest)
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE user SET is_active=0 WHERE id=1")
        with self.assertRaisesRegex(manager.ManagementError, "preview_changed"):
            self.apply((1,), digest=digest)
        self.assertEqual(self.counts(), [0] * 5)

    def test_active_review_prevents_activation(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO vocabulary_review_session(student_id,review_date,status,session_token,queue_token,batch_limit,started_at,created_at,updated_at) VALUES (1,'2026-11-17','active','synthetic-session','synthetic-queue',20,'2026-11-17 04:00:00','2026-11-17 04:00:00','2026-11-17 04:00:00')"
            )
        result = self.preview()
        self.assertEqual(result["unfinished_review_count"], 1)
        self.assertEqual(result["eligible_new_enrollment_count"], 0)
        with self.assertRaisesRegex(manager.ManagementError, "not_ready"):
            self.apply()
        self.assertEqual(self.counts(), [0] * 5)

    def test_missing_tables_preview_is_safe_and_apply_rejects(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TABLE vocabulary_policy_event")
        self.assertEqual(self.preview()["missing_table_count"], 1)
        with self.assertRaisesRegex(manager.ManagementError, "not_ready"):
            self.apply()

    def test_failed_second_enrollment_rolls_back_first(self):
        from services import vocabulary_error_queue as policy

        original = policy.enroll_student

        def fail_second(user, **kwargs):
            if user.id == 2:
                raise ValueError("synthetic failure")
            return original(user, **kwargs)

        with patch.object(policy, "enroll_student", side_effect=fail_second):
            with self.assertRaisesRegex(ValueError, "synthetic failure"):
                self.apply((1, 2))
        self.assertEqual(self.counts(), [0] * 5)

    def test_apply_requires_explicit_selection_and_fresh_start(self):
        for ids, start, digest in (
            ((), self.now, "x"),
            ((1,), self.now, ""),
            ((1,), self.now - timedelta(minutes=11), "x"),
        ):
            with self.assertRaises(manager.ManagementError):
                manager.apply_enrollment(
                    self.database,
                    student_ids=ids,
                    starts_at=start,
                    expected_digest=digest,
                    now=self.now,
                )
        self.assertEqual(self.counts(), [0] * 5)

    def test_cli_errors_do_not_print_sql_or_private_values(self):
        result = subprocess.run(
            [
                sys.executable,
                manager.__file__,
                "--database",
                str(self.database),
                "--apply",
                "--student-id",
                "1",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "reviewed_start_time_required")
        self.assertEqual(result.stderr, "")
        self.assertNotIn("SENSITIVE", result.stdout)

    def test_invalid_runtime_parameters_reject_before_enrolling(self):
        with patch.dict("os.environ", {"VOCABULARY_ERROR_REVIEW_DAILY_LIMIT": "0"}):
            with self.assertRaisesRegex(ValueError, "invalid_policy_config"):
                self.apply()
        self.assertEqual(self.counts(), [0] * 5)

    def test_defaults_and_validation_match_core_without_loading_config(self):
        from services.vocabulary_error_queue import policy_settings

        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("VOCABULARY_ERROR_REVIEW_")
        }
        with (
            patch.dict(os.environ, environment, clear=True),
            Flask("policy-defaults").app_context(),
        ):
            self.assertEqual(manager.effective_policy_parameters(self.database), policy_settings())
        for key, value in (
            ("DAILY_LIMIT", "0"),
            ("SAMPLE_LIMIT", "-1"),
            ("SAMPLE_LIMIT", "21"),
            ("PAUSE_DAYS", "1.5"),
        ):
            env_key = f"VOCABULARY_ERROR_REVIEW_{key}"
            with patch.dict(os.environ, {env_key: value}):
                with self.assertRaises(ValueError):
                    self.preview()
        self.assertEqual(self.counts(), [0] * 5)

    def test_dotenv_first_value_environment_override_and_only_public_knobs(self):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("VOCABULARY_ERROR_REVIEW_")
        }
        (self.database.parent / ".env").write_text(
            "# synthetic configuration\n"
            "VOCABULARY_ERROR_REVIEW_DAILY_LIMIT='24'\n"
            "VOCABULARY_ERROR_REVIEW_DAILY_LIMIT=99\n"
            'VOCABULARY_ERROR_REVIEW_SAMPLE_LIMIT="3"\n'
            "VOCABULARY_ERROR_REVIEW_ENABLED=1\n"
            "UNRELATED_PRIVATE_VALUE=DO_NOT_EXPORT\n",
            encoding="utf-8",
        )
        with patch.dict(os.environ, environment, clear=True):
            result = self.preview()
            self.assertEqual(result["policy_parameters"]["daily_limit"], 24)
            self.assertEqual(result["policy_parameters"]["sample_limit"], 3)
            self.assertNotIn("enabled", result["policy_parameters"])
            self.assertNotIn("DO_NOT_EXPORT", json.dumps(result))
            self.assertNotIn("UNRELATED_PRIVATE_VALUE", os.environ)
            with patch.dict(os.environ, {"VOCABULARY_ERROR_REVIEW_DAILY_LIMIT": "27"}):
                self.assertEqual(self.preview()["policy_parameters"]["daily_limit"], 27)
        self.assertEqual(self.counts(), [0] * 5)

    def test_digest_rejects_other_database_and_same_path_replacement(self):
        digest = self.preview()["preview_digest"]
        other = self.database.parent / "different.db"
        shutil.copy2(self.database, other)
        with manager.readonly(other) as connection:
            different = manager.preview(
                connection, student_ids=(1,), starts_at=self.now, now=self.now
            )
        self.assertNotEqual(different["preview_digest"], digest)
        self.assertNotIn(str(self.database.parent), json.dumps(different))
        with self.assertRaisesRegex(manager.ManagementError, "preview_changed"):
            manager.apply_enrollment(
                other, student_ids=(1,), starts_at=self.now, expected_digest=digest, now=self.now
            )
        os.replace(other, self.database)
        with self.assertRaisesRegex(manager.ManagementError, "preview_changed"):
            self.apply(digest=digest)
        self.assertEqual(self.counts(), [0] * 5)

    def test_digest_rejects_valid_parameter_change_in_file_or_environment(self):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("VOCABULARY_ERROR_REVIEW_")
        }
        with patch.dict(os.environ, environment, clear=True):
            digest = self.preview()["preview_digest"]
            (self.database.parent / ".env").write_text(
                "VOCABULARY_ERROR_REVIEW_DAILY_LIMIT=40\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(manager.ManagementError, "preview_changed"):
                self.apply(digest=digest)
            digest = self.preview()["preview_digest"]
            with patch.dict(os.environ, {"VOCABULARY_ERROR_REVIEW_FAILURE_LIMIT": "4"}):
                with self.assertRaisesRegex(manager.ManagementError, "preview_changed"):
                    self.apply(digest=digest)
        self.assertEqual(self.counts(), [0] * 5)

    def test_apply_reuses_reviewed_parameters_and_never_enables_global_switch(self):
        from flask import current_app

        from services import vocabulary_error_queue as policy

        original = policy.enroll_student
        observed = []

        def record_configuration(user, **kwargs):
            observed.append((current_app.config[policy.FEATURE_FLAG], policy.policy_settings()))
            return original(user, **kwargs)

        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("VOCABULARY_ERROR_REVIEW_")
        }
        with patch.dict(os.environ, environment, clear=True):
            (self.database.parent / ".env").write_text(
                "VOCABULARY_ERROR_REVIEW_DAILY_LIMIT=23\nVOCABULARY_ERROR_REVIEW_ENABLED=1\n",
                encoding="utf-8",
            )
            reviewed = self.preview()
            with patch.object(policy, "enroll_student", side_effect=record_configuration):
                self.apply(digest=reviewed["preview_digest"])
        self.assertEqual(observed, [(False, reviewed["policy_parameters"])])
        self.assertEqual(self.counts(), [1, 0, 0, 0, 0])


if __name__ == "__main__":
    unittest.main()
