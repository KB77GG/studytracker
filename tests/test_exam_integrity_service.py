"""Integrity regressions use a disposable SQLite file, never the production DB."""

import os
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from models import ExamIntegrityEvent, ExamIntegrityPolicy, ExamIntegrityState, MockExam, db
from scripts.create_exam_integrity_tables import create_tables
from services import exam_integrity as service
from services.exam_integrity_rules import maybe_lock


class IntegrityServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.database = Path(self.tmp.name) / "integrity.db"
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{self.database}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        self.assertTrue(service.ensure_schema())
        self.now = datetime(2026, 11, 14, 9)
        service.set_policy(1, "enforce", now=self.now)

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()
        self.tmp.cleanup()

    def send(self, kind, at=0, page="page-a", section="reading", session="1", **extra):
        payload = dict(
            type=kind,
            device_id="device-first",
            page_id=page,
            section=section,
            client_ts=1_000_000 + at * 1000,
        )
        payload.update(extra)
        return service.record_event(1, session, payload, now=self.now + timedelta(seconds=at))

    def leave(self, start, duration=2, **extra):
        self.send("hidden", start, **extra)
        return self.send("visible", start + duration, **extra)

    def state(self):
        return service.student_state(1, "1", "device-first", "reading", now=self.now)

    def events(self):
        return service.event_timeline("1", limit=2000)

    def test_no_policy_is_off_and_creates_nothing(self):
        self.assertEqual(service.read_policy(2)["mode"], "off")
        result = service.record_event(2, "2", {"type": "hello"})
        self.assertFalse(result["enabled"])
        with Session(db.engine) as session:
            self.assertEqual(session.query(ExamIntegrityState).count(), 0)

    def test_two_second_grace_boundary(self):
        self.send("hello")
        self.assertEqual(self.leave(1, 1.999)["leave_count"], 0)
        result = self.leave(4, 2)
        self.assertEqual(result["leave_count"], 1)
        self.assertEqual(result["hidden_seconds"], 2)

    def test_three_leaves_lock_reading_and_writing(self):
        for section in ("reading", "writing"):
            with self.subTest(section=section):
                session = section
                self.send("hello", section=section, session=session)
                self.leave(1, section=section, session=session)
                self.leave(5, section=section, session=session)
                result = self.leave(9, section=section, session=session)
                self.assertTrue(result["is_locked"])
                self.assertEqual(result["locked_section"], section)

    def test_sixty_seconds_locks_once(self):
        self.send("hello")
        result = self.leave(1, 60)
        self.assertTrue(result["is_locked"])
        self.assertEqual(result["leave_count"], 1)

    def test_listening_never_locks(self):
        self.send("hello", section="listening")
        for at in (1, 70, 140):
            result = self.leave(at, 60, section="listening")
        self.assertFalse(result["is_locked"])
        self.assertEqual(result["leave_count"], 3)
        self.assertEqual(result["hidden_seconds"], 180)

    def test_listening_does_not_inherit_existing_overlay(self):
        self.send("hello")
        self.leave(1, 60)
        result = service.student_state(1, "1", "device-first", "listening")
        self.assertFalse(result["is_locked"])

    def test_teacher_sees_stored_lock_when_student_returns_to_process_page(self):
        self.send("hello")
        self.leave(1, 60)
        student = self.send("hello", 70, page="process-page", section="process")
        self.assertFalse(student["is_locked"])
        self.assertTrue(service.admin_states(1, ["1"])["1"]["is_locked"])

    def test_same_section_refresh_ten_second_boundary(self):
        self.send("hello")
        self.send("hidden", 1)
        short = self.send("hello", 10.99, page="page-b")
        self.assertEqual(short["leave_count"], 0)
        self.send("hidden", 11, page="page-b")
        long = self.send("hello", 21, page="page-c")
        self.assertEqual(long["leave_count"], 1)
        self.assertEqual(long["hidden_seconds"], 10)

    def test_process_and_cross_section_navigation_drop_pending_departure(self):
        for section in ("process", "intro", "writing", "listening"):
            with self.subTest(section=section):
                session = section
                self.send("hello", session=session)
                self.send("hidden", 1, session=session)
                result = self.send("hello", 90, page="next-page", section=section, session=session)
                self.assertEqual(result["leave_count"], 0)
                self.assertIsNone(result["hidden_at"])

    def test_submitted_section_refresh_does_not_count(self):
        self.send("hello")
        self.send("hidden", 1)
        result = service.record_event(
            1,
            "1",
            dict(type="hello", section="reading", page_id="page-b", device_id="device-first"),
            current_section="writing",
            submitted_sections=("reading",),
            now=self.now + timedelta(seconds=99),
        )
        self.assertEqual(result["leave_count"], 0)

    def test_stale_page_hidden_does_not_open_new_departure(self):
        self.send("hello")
        self.send("hello", 5, page="new-page", section="writing")
        self.send("hidden", 10)
        self.assertIsNone(self.state()["hidden_at"])

    def test_duplicate_hidden_does_not_reset_start(self):
        self.send("hello")
        self.send("hidden", 1)
        self.send("hidden", 2)
        result = self.send("visible", 3)
        self.assertEqual(result["hidden_seconds"], 2)

    def test_visible_retries_do_not_double_count_client_fallback(self):
        self.send("hello")
        first = self.send("visible", 10, client_hidden_ms=3000)
        second = self.send("visible", 10, client_hidden_ms=3000)
        self.assertEqual(first["leave_count"], 1)
        self.assertEqual(second["leave_count"], 1)

    def test_fallback_uses_no_untrusted_duration_when_hidden_exists(self):
        self.send("hello")
        self.send("hidden", 1)
        result = self.send("visible", 3, client_hidden_ms=999999)
        self.assertEqual(result["hidden_seconds"], 2)

    def test_late_beacon_after_visible_does_not_reopen_departure(self):
        self.send("hello")
        self.send("visible", 3, client_hidden_ms=2000)
        self.send("hidden", 4, client_ts=1_001_000)
        self.assertIsNone(self.state()["hidden_at"])

    def test_heartbeat_gap_is_soft_and_logged(self):
        self.send("hello")
        result = self.send("heartbeat", 61)
        self.assertFalse(result["is_locked"])
        self.assertEqual(result["leave_count"], 0)
        self.assertIn("heartbeat_gap", {e["type"] for e in self.events()})

    def test_soft_signals_never_count_as_leaves(self):
        self.send("hello")
        for kind in ("blur", "viewport", "copy_blocked", "paste_blocked"):
            for at in range(1, 5):
                result = self.send(kind, at, detail={"blocked": True})
        self.assertEqual(result["leave_count"], 0)
        self.assertFalse(result["is_locked"])
        self.assertEqual(result["blur_count"], 4)
        self.assertEqual(result["copy_blocked_count"], 4)
        self.assertEqual(result["paste_blocked_count"], 4)

    def test_monitor_neither_locks_nor_binds_devices(self):
        service.set_policy(1, "monitor")
        self.send("hello")
        result = self.leave(1, 120)
        self.assertFalse(result["is_locked"])
        self.assertFalse(result["device_bound"])
        result = self.send("hello", 130, device_id="device-second")
        self.assertFalse(result["device_conflict"])
        self.assertEqual(result["device_conflict_count"], 0)

    def test_device_conflict_only_affects_new_device(self):
        self.send("hello")
        conflict = self.send("hello", 10, device_id="device-second")
        self.assertTrue(conflict["device_conflict"])
        self.assertFalse(self.state()["device_conflict"])
        self.assertEqual(self.state()["current_section"], "reading")
        self.assertTrue(self.state()["has_device_conflict"])
        self.assertEqual(self.events()[0]["type"], "device_conflict")

    def test_reset_device_allows_new_hello(self):
        self.send("hello")
        self.send("hello", 1, device_id="device-second")
        service.admin_action(1, "1", "reset-device", actor=99)
        result = self.send("hello", 2, device_id="device-second")
        self.assertFalse(result["device_conflict"])
        self.assertTrue(result["device_bound"])
        self.assertFalse(result["has_device_conflict"])

    def test_unlock_keeps_counters_and_next_leave_locks(self):
        self.send("hello")
        self.leave(1, 60)
        result = service.admin_action(
            1, "1", "unlock", actor=99, now=self.now + timedelta(seconds=62)
        )
        self.assertEqual(result["leave_count"], 1)
        self.assertEqual(result["hidden_seconds"], 60)
        self.assertFalse(result["is_locked"])
        self.assertFalse(self.send("heartbeat", 63)["is_locked"])
        self.assertFalse(self.leave(64, 1)["is_locked"])
        self.assertTrue(self.leave(66, 2)["is_locked"])

    def test_unlock_drops_open_interval_to_prevent_immediate_relock(self):
        self.send("hello")
        self.leave(1, 60)
        self.send("hidden", 62)
        service.admin_action(1, "1", "unlock", actor=99, now=self.now + timedelta(seconds=70))
        self.assertIsNone(self.state()["hidden_at"])
        self.assertFalse(self.send("heartbeat", 71)["is_locked"])

    def test_visible_after_teacher_unlock_does_not_recount_old_interval(self):
        self.send("hello")
        self.leave(1, 60)
        self.send("hidden", 62)
        service.admin_action(1, "1", "unlock", now=self.now + timedelta(seconds=120))
        result = self.send("visible", 121, client_hidden_ms=59000)
        self.assertFalse(result["is_locked"])
        self.assertEqual(result["leave_count"], 1)
        self.assertTrue(self.leave(125, 2)["is_locked"])

    def test_unlock_on_healthy_student_does_not_lower_initial_threshold(self):
        self.send("hello")
        result = service.admin_action(1, "1", "unlock", now=self.now)
        self.assertEqual(result["unlock_count"], 0)
        self.assertFalse(self.leave(1, 2)["is_locked"])
        self.assertFalse(self.leave(5, 2)["is_locked"])
        self.assertTrue(self.leave(9, 2)["is_locked"])

    def test_repeated_unlock_is_idempotent(self):
        self.send("hello")
        self.leave(1, 60)
        first = service.admin_action(1, "1", "unlock", now=self.now + timedelta(seconds=65))
        second = service.admin_action(1, "1", "unlock", now=self.now + timedelta(seconds=70))
        self.assertEqual(first["unlock_count"], second["unlock_count"])
        self.assertEqual(first["unlocked_at"], second["unlocked_at"])

    def test_relock_duration_uses_unlock_baseline_not_lifetime_total(self):
        self.send("hello")
        self.leave(1, 60)
        service.admin_action(1, "1", "unlock", now=self.now + timedelta(seconds=62))
        with Session(db.engine) as session:
            state = session.scalar(select(ExamIntegrityState))
            state.hidden_seconds = 89.999
            self.assertFalse(maybe_lock(state, service.read_policy(1), "reading", self.now))
            state.hidden_seconds = 90
            self.assertTrue(maybe_lock(state, service.read_policy(1), "reading", self.now))

    def test_concurrent_duplicate_returns_only_count_one_departure(self):
        self.send("hello")
        self.send("hidden", 1)

        def return_to_page(_):
            with self.app.app_context():
                return self.send("visible", 3, client_hidden_ms=2000)

        with ThreadPoolExecutor(max_workers=6) as workers:
            results = list(workers.map(return_to_page, range(12)))
        self.assertTrue(all(result["leave_count"] == 1 for result in results))
        self.assertEqual(self.state()["hidden_seconds"], 2)

    def test_exemption_releases_and_never_locks_or_conflicts(self):
        self.send("hello")
        self.leave(1, 60)
        service.admin_action(1, "1", "exempt", actor=99)
        result = self.send("hello", 65, device_id="device-second")
        self.assertFalse(result["device_conflict"])
        self.assertFalse(result["is_locked"])
        self.assertTrue(result["exempt"])

    def test_global_disabled_switch_is_immediate(self):
        self.send("hello")
        self.leave(1, 60)
        with patch.dict(os.environ, {"EXAM_INTEGRITY_DISABLED": "1"}):
            self.assertEqual(self.state()["mode"], "off")
            self.assertFalse(self.send("hello")["is_locked"])

    def test_emergency_off_and_monitor_remove_stored_lock_and_binding(self):
        self.send("hello")
        self.leave(1, 60)
        service.set_policy(1, "off")
        self.assertEqual(self.state()["mode"], "off")
        service.set_policy(1, "monitor")
        self.assertFalse(self.state()["is_locked"])
        self.assertFalse(self.state()["device_bound"])

    def test_missing_tables_fail_open_without_ddl(self):
        for model in (ExamIntegrityEvent, ExamIntegrityState, ExamIntegrityPolicy):
            model.__table__.drop(db.engine)
        self.assertEqual(self.state()["mode"], "off")
        self.assertEqual(self.send("hello")["mode"], "off")
        self.assertEqual(inspect(db.engine).get_table_names(), [])

    def test_missing_state_table_with_valid_policy_fails_open(self):
        ExamIntegrityState.__table__.drop(db.engine)
        self.assertEqual(self.state()["mode"], "off")
        self.assertEqual(self.send("hello")["mode"], "off")
        self.assertNotIn("exam_integrity_state", inspect(db.engine).get_table_names())

    def test_policy_failure_does_not_rollback_pending_existing_exam_write(self):
        MockExam.__table__.create(db.engine)
        ExamIntegrityPolicy.__table__.drop(db.engine)
        exam = MockExam(name="Pending", listening_test_id="l", reading_test_id="r", pincode="123")
        db.session.add(exam)
        db.session.flush()
        self.assertEqual(service.read_policy(1)["mode"], "off")
        self.assertTrue(db.session.is_active)
        db.session.commit()
        with Session(db.engine) as session:
            self.assertEqual(session.scalar(select(MockExam.name)), "Pending")

    def test_event_cap_is_per_exam_across_students_and_counts_continue(self):
        self.send("hello")
        with Session(db.engine) as session, session.begin():
            state = session.scalar(select(ExamIntegrityState))
            session.add_all(
                ExamIntegrityEvent(
                    state_id=state.id,
                    exam_kind="ielts_mock",
                    exam_ref="1",
                    type="viewport",
                    created_at=self.now,
                )
                for _ in range(1999)
            )
        result = self.send("copy_blocked", 1, session="other-student", detail={"blocked": True})
        self.assertEqual(result["copy_blocked_count"], 1)
        with Session(db.engine) as session:
            self.assertEqual(session.query(ExamIntegrityEvent).count(), 2000)

    def test_detail_whitelist_never_records_clipboard_contents(self):
        self.send("hello")
        self.send(
            "paste_blocked",
            1,
            detail={
                "length": 100,
                "text": "private essay",
                "blocked": True,
                "signal": "paste",
                "width": float("nan"),
            },
        )
        detail = self.events()[0]["detail_json"]
        self.assertNotIn("private", detail)
        self.assertNotIn("NaN", detail)
        self.assertIn('"length":100', detail)
        self.assertLessEqual(len(detail.encode()), 1024)

    def test_monitor_paste_attempt_is_not_a_block_or_high_risk(self):
        service.set_policy(1, "monitor")
        self.send("hello")
        result = self.send("paste_blocked", 1, detail={"blocked": False, "length": 50})
        self.assertEqual(result["paste_attempt_count"], 1)
        self.assertEqual(result["paste_blocked_count"], 0)
        self.assertEqual(result["risk"], "low")
        # The server policy, not an untrusted client flag, owns enforcement mode.
        result = self.send("paste_blocked", 2, detail={"blocked": True, "length": 50})
        self.assertEqual(result["paste_blocked_count"], 0)
        self.assertEqual(result["risk"], "low")

    def test_actual_enforce_paste_block_is_high_risk_and_survives_mode_change(self):
        self.send("hello")
        result = self.send("paste_blocked", 1, detail={"blocked": True, "length": 50})
        self.assertEqual(result["paste_attempt_count"], 1)
        self.assertEqual(result["paste_blocked_count"], 1)
        self.assertEqual(result["risk"], "high")
        service.set_policy(1, "monitor")
        self.assertEqual(self.state()["risk"], "high")

    def test_exempt_paste_attempt_is_not_a_block(self):
        self.send("hello")
        service.admin_action(1, "1", "exempt")
        result = self.send("paste_blocked", 1, detail={"blocked": True, "length": 50})
        self.assertEqual(result["paste_attempt_count"], 1)
        self.assertEqual(result["paste_blocked_count"], 0)
        self.assertEqual(result["risk"], "low")

    def test_old_return_cannot_close_a_newer_hidden_interval(self):
        self.send("hello")
        self.send("hidden", 20, client_ts=20000)
        result = self.send("visible", 30, client_ts=11000, client_hidden_ms=1000)
        self.assertEqual(result["leave_count"], 0)
        self.assertIsNotNone(result["hidden_at"])
        self.assertEqual(self.state()["hidden_seconds"], 0)

    def test_device_id_only_saved_as_hash(self):
        self.send("hello")
        with Session(db.engine) as session:
            state = session.scalar(select(ExamIntegrityState))
            self.assertEqual(len(state.device_hash), 64)
            self.assertNotEqual(state.device_hash, "device-first")
        self.assertNotIn("device-first", str(self.events()))

    def test_unknown_events_and_missing_page_fail_open(self):
        self.assertEqual(self.send("not-a-type")["mode"], "off")
        self.assertEqual(self.send("hello", page="")["mode"], "off")

    def test_invalid_thresholds_are_rejected(self):
        for value in (0, 101, True, "3"):
            with self.assertRaises(ValueError):
                service.set_policy(1, "enforce", max_leaves=value)
        for value in (1, 3601, True, "60"):
            with self.assertRaises(ValueError):
                service.set_policy(1, "enforce", max_hidden_seconds=value)

    def test_schema_creates_only_three_tables_without_foreign_keys(self):
        inspector = inspect(db.engine)
        self.assertEqual(
            set(inspector.get_table_names()),
            {"exam_integrity_policy", "exam_integrity_state", "exam_integrity_event"},
        )
        for table in inspector.get_table_names():
            self.assertEqual(inspector.get_foreign_keys(table), [])

    def test_script_schema_exactly_matches_models_and_is_idempotent(self):
        path = Path(self.tmp.name) / "script.db"
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute("CREATE TABLE existing_exam (id INTEGER PRIMARY KEY, answer TEXT)")
            conn.execute("INSERT INTO existing_exam VALUES (1, 'kept')")
        create_tables(path)
        create_tables(path)
        with (
            closing(sqlite3.connect(path)) as scripted,
            closing(sqlite3.connect(self.database)) as modeled,
        ):
            for model in (ExamIntegrityPolicy, ExamIntegrityState, ExamIntegrityEvent):
                name = model.__tablename__
                self.assertEqual(
                    scripted.execute(f"PRAGMA table_info({name})").fetchall(),
                    modeled.execute(f"PRAGMA table_info({name})").fetchall(),
                )
                script_indexes = scripted.execute(f"PRAGMA index_list({name})").fetchall()
                model_indexes = modeled.execute(f"PRAGMA index_list({name})").fetchall()
                self.assertEqual(
                    sorted(row[1:] for row in script_indexes),
                    sorted(row[1:] for row in model_indexes),
                )
            self.assertEqual(
                scripted.execute("SELECT answer FROM existing_exam").fetchone(), ("kept",)
            )

    def test_script_dry_run_does_not_create_database(self):
        missing = Path(self.tmp.name) / "missing.db"
        self.assertTrue(create_tables(missing, dry_run=True))
        self.assertFalse(missing.exists())
        with self.assertRaises(ValueError):
            create_tables(missing)


if __name__ == "__main__":
    unittest.main()
