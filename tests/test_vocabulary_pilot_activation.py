"""Private first-pilot activation, failure recovery and transaction boundaries."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from models import User, db
from scripts import activate_vocabulary_pilot as activation
from scripts import manage_vocabulary_error_pilot as manager


class PilotActivationTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.database = self.root / "fixture.sqlite"
        self.manifest = self.root / "private.json"
        self.ids = [10101, 20202, 30303, 40404]
        self.now = datetime(2026, 11, 17, 9)
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("VOCABULARY_ERROR_REVIEW_")
        }
        self.env_patch = patch.dict(os.environ, self.environment, clear=True)
        self.env_patch.start()
        app = Flask(__name__)
        app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///" + str(self.database),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(app)
        with app.app_context():
            db.create_all()
            db.session.add_all(
                User(
                    id=value,
                    username=f"SENSITIVE_{value}",
                    password_hash="test",
                    role="student",
                    is_active=True,
                )
                for value in self.ids + [50505, 60606, 70707]
            )
            db.session.commit()
            db.session.remove()
            db.engine.dispose()
        self.save(
            {"version": 1, "student_ids": self.ids, "selected_at_utc": self.now.isoformat() + "Z"}
        )

    def tearDown(self):
        self.env_patch.stop()
        self.folder.cleanup()

    def save(self, manifest):
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        self.manifest.chmod(0o600)

    def run_activation(self, **kwargs):
        return activation.activate(self.database, self.manifest, now=self.now, **kwargs)

    def counts(self):
        with sqlite3.connect(self.database) as connection:
            return [
                connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in manager.TABLES
            ]

    def insert_enrollment(self, student=70707, start=None):
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "INSERT INTO vocabulary_review_policy_enrollment(student_id,enabled,starts_at,state_version,created_at,updated_at) VALUES (?,1,?,0,?,?)",
                (
                    student,
                    (start or self.now).isoformat(" "),
                    self.now.isoformat(" "),
                    self.now.isoformat(" "),
                ),
            )

    def assert_private_output(self, result):
        text = json.dumps(result)
        self.assertNotIn("student_ids", text)
        self.assertNotIn("SENSITIVE", text)
        for value in self.ids:
            self.assertNotIn(str(value), text)

    def test_default_preview_is_readonly_and_requires_only_stdlib(self):
        before = (
            hashlib.sha256(self.database.read_bytes()).hexdigest(),
            self.manifest.read_bytes(),
        )
        result = self.run_activation()
        self.assertTrue(result["read_only_preview"])
        self.assertEqual(result["selected_count"], 4)
        self.assert_private_output(result)
        self.assertEqual(
            before,
            (hashlib.sha256(self.database.read_bytes()).hexdigest(), self.manifest.read_bytes()),
        )
        self.assertFalse(Path(str(self.manifest) + ".lock").exists())
        command = "import sys;from scripts import activate_vocabulary_pilot as a;a.activate(sys.argv[1],sys.argv[2]);assert not any(n in sys.modules for n in ('app','config','flask','models'))"
        subprocess.run(
            [sys.executable, "-c", command, str(self.database), str(self.manifest)],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
        )

    def test_apply_enrolls_exact_four_and_writes_only_private_start_facts(self):
        result = self.run_activation(apply=True)
        self.assertEqual(self.counts(), [4, 0, 0, 0, 0])
        self.assertEqual(result["enrollment_rows_created"], 4)
        self.assert_private_output(result)
        data = json.loads(self.manifest.read_text())
        self.assertEqual(data["activation"]["state"], "enrolled")
        self.assertEqual(data["activation"]["starts_at_utc"], self.now.isoformat() + "Z")
        self.assertEqual(self.manifest.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / ".env").exists())

    def test_six_students_are_supported_without_changing_parameters(self):
        self.save({"version": 1, "student_ids": self.ids + [50505, 60606]})
        result = self.run_activation(apply=True)
        self.assertEqual(result["selected_count"], 6)
        self.assertEqual(self.counts(), [6, 0, 0, 0, 0])
        self.assertEqual(result["policy_parameters"], activation.APPROVED)

    def test_invalid_size_duplicates_types_and_identity_roles_reject(self):
        for ids in (
            [],
            self.ids[:3],
            self.ids + [50505],
            [*self.ids[:3], self.ids[0]],
            [*self.ids[:3], "SENSITIVE"],
            [*self.ids[:3], True],
        ):
            self.save({"version": 1, "student_ids": ids})
            with self.assertRaises(activation.ActivationError):
                self.run_activation(apply=True)
        self.save({"version": 1, "student_ids": self.ids})
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE user SET role='teacher' WHERE id=?", (self.ids[0],))
        with self.assertRaisesRegex(activation.ActivationError, "not_ready"):
            self.run_activation(apply=True)
        self.assertEqual(self.counts(), [0] * 5)

    def test_public_permissions_symlinks_and_hardlinks_reject(self):
        self.manifest.chmod(0o644)
        with self.assertRaises(activation.ActivationError):
            self.run_activation()
        self.manifest.chmod(0o600)
        link = self.root / "link.json"
        link.symlink_to(self.manifest)
        with self.assertRaises(OSError):
            activation.activate(self.database, link, now=self.now)
        link.unlink()
        os.link(self.manifest, link)
        with self.assertRaises(activation.ActivationError):
            self.run_activation()

    def test_effective_flag_and_all_seven_parameters_are_rechecked(self):
        (self.root / ".env").write_text("VOCABULARY_ERROR_REVIEW_ENABLED=true\n")
        with self.assertRaisesRegex(activation.ActivationError, "must_be_off"):
            self.run_activation()
        with patch.dict(os.environ, {activation.FLAG: "0"}):
            self.assertTrue(self.run_activation()["ok"])
        (self.root / ".env").write_text("VOCABULARY_ERROR_REVIEW_ENABLED=0\n")
        with patch.dict(os.environ, {activation.FLAG: "yes"}):
            with self.assertRaisesRegex(activation.ActivationError, "must_be_off"):
                self.run_activation(apply=True)
        for key, value in activation.APPROVED.items():
            with patch.dict(os.environ, {"VOCABULARY_ERROR_REVIEW_" + key.upper(): str(value + 1)}):
                with self.assertRaisesRegex(activation.ActivationError, "approved_policy"):
                    self.run_activation(apply=True)
        self.assertEqual(self.counts(), [0] * 5)

    def test_schema_and_global_unselected_policy_rows_reject(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP INDEX ix_vocab_checkpoint_select")
        with self.assertRaisesRegex(activation.ActivationError, "schema_not_ready"):
            self.run_activation(apply=True)
        with sqlite3.connect(self.database) as connection:
            connection.execute(activation.migration.INDEX_SQL["ix_vocab_checkpoint_select"])
        self.insert_enrollment()
        with self.assertRaisesRegex(activation.ActivationError, "existing_pilot"):
            self.run_activation(apply=True)
        self.assertEqual(self.counts(), [1, 0, 0, 0, 0])

    def test_locked_global_recheck_prevents_enrollment_race(self):
        original = manager.apply_enrollment

        def race(*args, **kwargs):
            self.insert_enrollment()
            return original(*args, **kwargs)

        with patch.object(manager, "apply_enrollment", side_effect=race):
            with self.assertRaisesRegex(activation.ActivationError, "existing_pilot"):
                self.run_activation(apply=True)
        self.assertEqual(self.counts(), [1, 0, 0, 0, 0])

    def test_locked_global_switch_change_rejects_without_enrollment(self):
        original = manager.apply_enrollment

        def race(*args, **kwargs):
            (self.root / ".env").write_text("VOCABULARY_ERROR_REVIEW_ENABLED=1\n")
            return original(*args, **kwargs)

        with patch.object(manager, "apply_enrollment", side_effect=race):
            with self.assertRaisesRegex(activation.ActivationError, "must_be_off"):
                self.run_activation(apply=True)
        self.assertEqual(self.counts(), [0] * 5)

    def test_active_legacy_batch_is_rechecked_under_writer(self):
        original = manager.apply_enrollment

        def race(*args, **kwargs):
            with sqlite3.connect(self.database) as connection:
                connection.execute(
                    "INSERT INTO vocabulary_review_session(student_id,review_date,status,session_token,queue_token,batch_limit,started_at,created_at,updated_at) VALUES (?,'2026-11-17','active','test','test',20,'2026-11-17','2026-11-17','2026-11-17')",
                    (self.ids[0],),
                )
            return original(*args, **kwargs)

        with patch.object(manager, "apply_enrollment", side_effect=race):
            with self.assertRaisesRegex(activation.ActivationError, "not_ready"):
                self.run_activation(apply=True)
        self.assertEqual(self.counts(), [0] * 5)

    def test_mid_enrollment_failure_rolls_back_every_student_and_can_retry(self):
        from services import vocabulary_error_queue as policy

        original = policy.enroll_student

        def fail(user, **kwargs):
            if user.id == self.ids[1]:
                raise RuntimeError("SENSITIVE_FAILURE")
            return original(user, **kwargs)

        with patch.object(policy, "enroll_student", side_effect=fail):
            with self.assertRaises(RuntimeError):
                self.run_activation(apply=True)
        self.assertEqual(self.counts(), [0] * 5)
        self.assertEqual(json.loads(self.manifest.read_text())["activation"]["state"], "pending")
        self.run_activation(apply=True)
        self.assertEqual(self.counts(), [4, 0, 0, 0, 0])

    def test_commit_then_manifest_failure_is_verified_not_reenrolled_on_retry(self):
        original = activation._write_private
        calls = []

        def fail_final(*args):
            calls.append(1)
            if len(calls) == 2:
                raise OSError("SENSITIVE_PATH")
            return original(*args)

        with patch.object(activation, "_write_private", side_effect=fail_final):
            with self.assertRaisesRegex(activation.ActivationError, "retry_safe"):
                self.run_activation(apply=True)
        self.assertEqual(self.counts(), [4, 0, 0, 0, 0])
        self.assertEqual(json.loads(self.manifest.read_text())["activation"]["state"], "pending")
        self.now += timedelta(hours=1)
        before = self.database.read_bytes()
        with patch.object(
            manager, "apply_enrollment", side_effect=AssertionError("must not re-enroll")
        ):
            result = self.run_activation(apply=True)
        self.assertTrue(result["already_applied"])
        self.assertEqual(result["enrollment_rows_created"], 0)
        self.assertEqual(before, self.database.read_bytes())

    def test_retry_rejects_changed_selection_database_cohort_and_extra_student(self):
        self.run_activation(apply=True)
        original = json.loads(self.manifest.read_text())
        other_database = self.root / "other.sqlite"
        other_database.write_bytes(self.database.read_bytes())
        with self.assertRaisesRegex(activation.ActivationError, "intent_mismatch"):
            activation.activate(other_database, self.manifest, apply=True, now=self.now)
        changed = json.loads(json.dumps(original))
        changed["student_ids"][-1] = 50505
        self.save(changed)
        with self.assertRaisesRegex(activation.ActivationError, "intent_mismatch"):
            self.run_activation(apply=True)
        self.save(original)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "UPDATE vocabulary_review_policy_enrollment SET starts_at='2026-11-16 00:00:00' WHERE student_id=?",
                (self.ids[0],),
            )
        with self.assertRaisesRegex(activation.ActivationError, "does_not_match"):
            self.run_activation(apply=True)
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                "UPDATE vocabulary_review_policy_enrollment SET starts_at=?",
                (self.now.isoformat(" "),),
            )
        self.insert_enrollment()
        with self.assertRaisesRegex(activation.ActivationError, "does_not_match"):
            self.run_activation(apply=True)

    def test_pending_intent_expires_after_ten_minutes_if_no_commit(self):
        with patch.object(manager, "apply_enrollment", side_effect=RuntimeError("injected")):
            with self.assertRaises(RuntimeError):
                self.run_activation(apply=True)
        self.now += timedelta(minutes=11)
        with self.assertRaisesRegex(activation.ActivationError, "preview_expired"):
            self.run_activation(apply=True)
        self.assertEqual(self.counts(), [0] * 5)

    def test_cli_success_and_failure_never_export_identities(self):
        command = [
            sys.executable,
            activation.__file__,
            "--database",
            str(self.database),
            "--selection",
            str(self.manifest),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assert_private_output(json.loads(result.stdout))
        self.assertEqual(result.stderr, "")
        result = subprocess.run(
            [*command, "--SENSITIVE_ARGUMENT", "10101"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1)
        self.assert_private_output(json.loads(result.stdout))
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
