"""Recovery may act only after the source assignment's Beijing 03:00 cutoff.

These contracts bridge the recovery inbox and the existing task-date gate.
They reuse synthetic fixture builders, but do not inherit or rerun the existing
recovery test methods. No production app, database, or external service loads.
"""

import json
import unittest
import uuid
from datetime import timedelta, timezone
from unittest.mock import patch

from models import PlanItem, Task
from models_task_planner import TaskPlannerEntry, TaskPlannerRecoveryDecision
from services import task_planner as planner
from services import task_planner_recovery as recovery
from services.task_date_gate import task_date_access
from tests import test_task_planner_recovery as recovery_tests
from tests.test_task_planner import NOW

UTC = timezone.utc  # noqa: UP017 -- production also runs Python 3.10.


class RecoveryCutoffTest(unittest.TestCase):
    def setUp(self):
        self.fixture = recovery_tests.TaskPlannerRecoveryTest(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.line, self.entries = self.fixture.line()
        self.cutoff = (NOW + timedelta(days=1)).replace(hour=3, minute=0)
        self.grace = self.cutoff - timedelta(seconds=1)

    def payload(self, action):
        return {
            "series_id": self.line.id,
            "source_date": NOW.date().isoformat(),
            "action": action,
        }

    def state(self):
        return {
            "tasks": [(row.id, row.date, row.status, row.plan_item_id)
                      for row in Task.query.order_by(Task.id)],
            "plan_items": [(row.id, row.student_status, row.review_status)
                           for row in PlanItem.query.order_by(PlanItem.id)],
            "entries": [(row.id, str(row.target_date), row.status, row.version)
                        for row in TaskPlannerEntry.query.order_by(TaskPlannerEntry.id)],
            "decisions": TaskPlannerRecoveryDecision.query.count(),
            "definition": json.loads(self.line.definition_json),
        }

    def apply_payload(self, action, now=None):
        payload = self.payload(action)
        preview = recovery.preview_recovery(
            payload, self.fixture.staff_id, now=now or self.cutoff,
        )
        self.assertTrue(preview["can_apply"], preview["blockers"])
        return {
            **payload,
            "preview_hash": preview["preview_hash"],
            "request_key": str(uuid.uuid4()),
        }

    def test_pending_inbox_waits_for_cutoff_even_across_beijing_midnight(self):
        before = self.state()
        original = Task.query.one()
        for instant in (self.cutoff.replace(hour=0), self.grace,
                        self.grace.astimezone(UTC)):
            with self.subTest(instant=instant.isoformat()):
                self.assertTrue(task_date_access(original, now=instant).can_write)
                self.assertEqual(recovery.list_inbox(now=instant), [])
        self.assertEqual(self.state(), before)

    def test_pending_inbox_opens_at_exact_cutoff_in_local_utc_and_naive_utc(self):
        original = Task.query.one()
        utc_cutoff = self.cutoff.astimezone(UTC)
        for instant in (self.cutoff, utc_cutoff, utc_cutoff.replace(tzinfo=None)):
            with self.subTest(instant=instant.isoformat()):
                self.assertFalse(task_date_access(original, now=instant).can_write)
                items = recovery.list_inbox(now=instant)
                self.assertEqual(len(items), 1)
                self.assertEqual([row["id"] for row in items[0]["tasks"]], [original.id])

    def test_direct_previews_reject_both_actions_during_grace(self):
        before = self.state()
        for action in ("makeup", "continue"):
            with self.subTest(action=action):
                with self.assertRaises(planner.TaskPlannerError) as raised:
                    recovery.preview_recovery(
                        self.payload(action), self.fixture.staff_id, now=self.grace,
                    )
                self.assertEqual(raised.exception.code, "source_still_open")
                self.assertEqual(raised.exception.status, 409)
                self.assertIn("03:00", raised.exception.message)
        self.assertEqual(self.state(), before)

    def assert_apply_rejected_during_grace(self, action):
        # A same-calendar-day preview obtained at cutoff must not bypass the
        # server guard if the apply endpoint receives it while the source is open.
        payload = self.apply_payload(action)
        before = self.state()
        with self.assertRaises(planner.TaskPlannerError) as raised:
            recovery.apply_recovery(payload, self.fixture.staff_id, now=self.grace)
        self.assertEqual(raised.exception.code, "source_still_open")
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(self.state(), before)

    def test_direct_makeup_apply_cannot_bypass_cutoff(self):
        self.assert_apply_rejected_during_grace("makeup")

    def test_direct_continue_apply_cannot_bypass_cutoff(self):
        self.assert_apply_rejected_during_grace("continue")

    def test_api_inbox_and_previews_enforce_cutoff_with_staff_and_csrf(self):
        self.fixture.login()
        before = self.state()
        with patch("services.task_date_gate._local_now", return_value=self.grace):
            headers = self.fixture.csrf_headers()
            response = self.fixture.client.get("/api/task-planner/inbox")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["items"], [])
            for action in ("makeup", "continue"):
                with self.subTest(action=action):
                    response = self.fixture.client.post(
                        "/api/task-planner/inbox/preview",
                        json=self.payload(action), headers=headers,
                    )
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.get_json()["error"], "source_still_open")
        self.assertEqual(self.state(), before)

    def test_api_apply_returns_recoverable_conflict_without_writes(self):
        payload = self.apply_payload("makeup")
        self.fixture.login()
        before = self.state()
        with patch("services.task_date_gate._local_now", return_value=self.grace):
            response = self.fixture.client.post(
                "/api/task-planner/inbox/apply", json=payload,
                headers=self.fixture.csrf_headers(),
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "source_still_open")
        self.assertEqual(self.state(), before)

    def assert_action_available_at_cutoff(self, action):
        payload = self.apply_payload(action)
        original = Task.query.one()
        old_values = (original.id, original.date, original.status, original.plan_item_id)
        result = recovery.apply_recovery(payload, self.fixture.staff_id, now=self.cutoff)
        self.assertEqual(result["action"], action)
        self.assertEqual(len(result["created_task_ids"]), 1)
        self.assertEqual((original.id, original.date, original.status, original.plan_item_id), old_values)
        self.assertFalse(task_date_access(original, now=self.cutoff).can_write)

    def test_makeup_is_available_at_exact_cutoff(self):
        self.assert_action_available_at_cutoff("makeup")

    def test_continue_is_available_at_exact_cutoff(self):
        self.assert_action_available_at_cutoff("continue")

    def test_older_backlog_remains_recoverable_before_todays_cutoff(self):
        instant = self.grace + timedelta(days=1)
        self.assertEqual(len(recovery.list_inbox(now=instant)), 1)
        payload = self.apply_payload("makeup", now=instant)
        result = recovery.apply_recovery(payload, self.fixture.staff_id, now=instant)
        self.assertEqual(result["applied_date"], instant.date().isoformat())
        self.assertEqual(len(result["created_task_ids"]), 1)
        self.assertEqual(self.entries[1].target_date, instant.date() + timedelta(days=1))

    def test_committed_request_replays_across_midnight_without_duplicate_tasks(self):
        payload = self.apply_payload("makeup")
        original = recovery.apply_recovery(payload, self.fixture.staff_id, now=self.cutoff)
        before = self.state()
        replay = recovery.apply_recovery(
            payload, self.fixture.staff_id, now=self.grace + timedelta(days=1),
        )
        self.assertEqual(replay, original)
        self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main()
