"""Independent regression probes for reordered delivery and optional-feature boundaries."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from models import ExamIntegrityState, db
from services import exam_integrity as service


class IntegrityAdversarialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///" + str(Path(self.tmp.name) / "probe.sqlite"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        service.ensure_schema()
        self.now = datetime(2026, 11, 14, 9)
        service.set_policy(1, "enforce", now=self.now)

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()
        self.tmp.cleanup()

    def send(self, kind, received, client=None, page="page-first", section="reading", **extra):
        payload = {
            "type": kind,
            "page_id": page,
            "section": section,
            "device_id": "synthetic-device",
            "client_ts": (received if client is None else client) * 1000,
        }
        payload.update(extra)
        return service.record_event(
            1, 1, payload, current_section=section, now=self.now + timedelta(seconds=received)
        )

    def test_delayed_old_visible_cannot_close_newer_hidden(self):
        self.send("hello", 0)
        # The prior one-second return's request arrives after the next departure.
        # Its hidden beacon was lost. Only the second, ten-second absence counts.
        self.send("hidden", 20)
        old_return = self.send("visible", 30, client=11, client_hidden_ms=1000)
        self.assertEqual(old_return["leave_count"], 0)
        self.assertIsNotNone(old_return["hidden_at"])
        current_return = self.send("visible", 31, client=30, client_hidden_ms=10000)
        self.assertEqual(current_return["leave_count"], 1)
        self.assertEqual(current_return["hidden_seconds"], 11)

    def test_delayed_old_visible_cannot_trigger_an_extra_threshold_lock(self):
        self.send("hello", 0)
        self.send("hidden", 1)
        self.send("visible", 3)
        self.send("hidden", 20)
        self.send("visible", 30, client=11, client_hidden_ms=1000)
        result = self.send("visible", 31, client=30, client_hidden_ms=10000)
        self.assertEqual(result["leave_count"], 2)
        self.assertFalse(result["is_locked"])

    def test_monitor_paste_is_recorded_without_high_risk_or_block_count(self):
        service.set_policy(1, "monitor", now=self.now)
        self.send("hello", 0)
        result = self.send(
            "paste_blocked", 1, detail={"blocked": False, "length": 20, "signal": "paste"}
        )
        self.assertEqual(result["risk"], "low")
        self.assertEqual(result["paste_blocked_count"], 0)
        self.assertEqual(result["paste_attempt_count"], 1)

    def test_exempt_paste_cannot_be_claimed_as_actual_block(self):
        self.send("hello", 0)
        service.admin_action(1, 1, "exempt", now=self.now)
        result = self.send(
            "paste_blocked", 1, detail={"blocked": True, "length": 20, "signal": "paste"}
        )
        self.assertEqual(result["paste_blocked_count"], 0)
        self.assertEqual(result["risk"], "low")

    def test_discarded_interval_does_not_reappear_after_off_on(self):
        self.send("hello", 0)
        self.send("hidden", 1)
        service.set_policy(1, "off", now=self.now + timedelta(seconds=2))
        service.set_policy(1, "enforce", now=self.now + timedelta(seconds=3))
        self.send("hello", 4)
        result = self.send("visible", 70, client_hidden_ms=69000)
        self.assertEqual(result["leave_count"], 0)
        self.assertFalse(result["is_locked"])

    def test_old_page_return_does_not_consume_new_page_interval(self):
        self.send("hello", 0, page="old-page")
        self.send("hidden", 1, page="old-page")
        self.send("hello", 3, page="current-page")
        self.send("hidden", 4, page="current-page")
        old = self.send("visible", 5, page="old-page", client=2, client_hidden_ms=1000)
        self.assertEqual(old["leave_count"], 0)
        self.assertIsNotNone(old["hidden_at"])
        result = self.send("visible", 6, page="current-page", client_hidden_ms=2000)
        self.assertEqual(result["leave_count"], 1)

    def test_wrong_device_cannot_mutate_departure_or_ack(self):
        self.send("hello", 0)
        self.send("hidden", 1)
        result = self.send("ack", 2, device_id="foreign-device")
        self.assertTrue(result["device_conflict"])
        self.assertFalse(result["acked"])
        self.assertIsNotNone(result["hidden_at"])
        returned = self.send("visible", 3, client_hidden_ms=2000)
        self.assertEqual(returned["leave_count"], 1)

    def test_unlocking_a_normal_student_does_not_lower_their_threshold(self):
        self.send("hello", 0)
        before = service.admin_action(1, 1, "unlock", now=self.now)
        self.assertEqual(before["unlock_count"], 0)
        self.send("hidden", 1)
        result = self.send("visible", 3)
        self.assertEqual(result["leave_count"], 1)
        self.assertFalse(result["is_locked"])

    def test_only_event_table_missing_aborts_whole_integrity_write(self):
        self.send("hello", 0)
        with db.engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE exam_integrity_event")
        result = self.send("hidden", 1)
        self.assertFalse(result["ok"])
        self.assertNotIn("mode", result)
        with Session(db.engine) as session:
            state = session.scalar(select(ExamIntegrityState))
            self.assertIsNone(state.hidden_at)
        self.assertNotIn("exam_integrity_event", inspect(db.engine).get_table_names())


if __name__ == "__main__":
    unittest.main()
