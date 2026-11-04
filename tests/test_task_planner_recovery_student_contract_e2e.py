"""Recovery through the real miniprogram API; synthetic identities and data only.

This verifies the server contract used by the shipped client. It does not claim
that a native WeChat device or WebView was exercised.
"""

import unittest
from unittest.mock import patch

from tests.recovery_e2e_support import RecoverySandbox


class RecoveryStudentContractE2E(unittest.TestCase):
    def setUp(self):
        self.sandbox = RecoverySandbox()
        self.addCleanup(self.sandbox.close)
        from api import miniprogram
        from api.auth_utils import issue_token
        from models import User, db

        original_root = miniprogram._static_root
        resource_patch = patch.object(
            miniprogram,
            "_static_root",
            lambda name: (
                self.sandbox.root / "static" / name
                if name in {"reading_tests", "reading_jijing"}
                else original_root(name)
            ),
        )
        resource_patch.start()
        self.addCleanup(resource_patch.stop)
        self.headers = {}
        # Seed authentication for synthetic accounts only. The actual WeChat
        # credential exchange needs a device; API JWT validation remains real.
        with self.sandbox.app.app_context():
            for role in ("student", "other"):
                user = db.session.get(User, self.sandbox.users[role])
                _raw, token = issue_token(user)
                self.headers[role] = {"Authorization": "Bearer " + token}

    def mp_get(self, path, role="student", status=200):
        response = self.sandbox.clients[role].get(
            "/api/miniprogram/student/" + path, headers=self.headers[role]
        )
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def test_reading_bundle_makeup_is_visible_and_bound_to_fresh_tasks(self):
        s = self.sandbox
        line_id, entries = s.create_line(kind="reading_test", days=2)
        originals = [
            entry["published_task_id"] for entry in entries if entry["status"] == "published"
        ]
        self.assertEqual(len(originals), 3)
        old_details = {task_id: self.mp_get(f"tasks/{task_id}")["task"] for task_id in originals}
        s.set_time("2026-11-02T10:00:00+08:00")
        _preview, result = s.recover(line_id, "2026-11-01")
        created = result["created_task_ids"]
        self.assertEqual(len(created), 3)
        listed = self.mp_get("tasks/today?date=2026-11-02")
        self.assertEqual({row["id"] for row in listed["tasks"]}, set(created))
        new_tokens = set()
        total_questions = 0
        for task_id in created:
            detail = self.mp_get(f"tasks/{task_id}")["task"]
            passage = detail["reading_passage_number"]
            token = detail["reading_token"]
            new_tokens.add(token)
            old = next(
                row for row in old_details.values() if row["reading_passage_number"] == passage
            )
            self.assertNotEqual(token, old["reading_token"])
            self.assertTrue(detail["can_write"])
            self.assertIn("补做2026-11-01作业", detail["instructions"])
            self.assertIsNone(detail["reading_test_result"])
            data = self.mp_get(f"reading/cambridge/{task_id}?token={token}")
            self.assertEqual(data["task"]["id"], task_id)
            self.assertEqual(data["passage_number"], passage)
            self.assertEqual(len(data["test"]["passages"]), 1)
            self.assertIsNone(data["submission"])
            total_questions += sum(
                len(group["questions"])
                for item in data["test"]["passages"]
                for group in item["groups"]
            )
            self.mp_get(f"reading/cambridge/{task_id}?token={old['reading_token']}", status=403)
            self.mp_get(f"tasks/{task_id}", role="other", status=403)
            self.mp_get(f"reading/cambridge/{task_id}?token={token}", role="other", status=404)
            response = s.clients["student"].post(
                f"/api/reading/test/{detail['reading_test_id']}/submit",
                json={"task_id": task_id, "token": old["reading_token"], "answers": {"1": "TRUE"}},
            )
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.get_json()["error"], "invalid_token")
        self.assertEqual(len(new_tokens), 3)
        self.assertEqual(total_questions, 40)
        self.assertEqual(self.mp_get("tasks/today?date=2026-11-02", role="other")["tasks"], [])
        self.assertEqual(s.outbound_attempts, [])

    def test_makeup_grace_window_agrees_between_miniprogram_and_web(self):
        s = self.sandbox
        line_id, _entries = s.create_line(days=2)
        s.set_time("2026-11-02T10:00:00+08:00")
        _preview, result = s.recover(line_id, "2026-11-01")
        task_id = result["created_task_ids"][0]
        s.set_time("2026-11-03T02:59:59+08:00")
        before = self.mp_get("tasks/today?date=2026-11-02")
        self.assertTrue(before["grace_period"]["active"])
        self.assertEqual(before["grace_period"]["pending_count"], 1)
        self.assertTrue(before["tasks"][0]["can_write"])
        self.assertTrue(self.mp_get(f"tasks/{task_id}")["task"]["can_write"])
        self.assertTrue(next(row for row in s.tasks() if row["id"] == task_id)["can_write"])
        s.set_time("2026-11-03T03:00:00+08:00")
        after = self.mp_get("tasks/today?date=2026-11-02")
        self.assertFalse(after["grace_period"]["active"])
        self.assertFalse(after["tasks"][0]["can_write"])
        self.assertTrue(self.mp_get(f"tasks/{task_id}")["task"]["read_only"])
        self.assertFalse(next(row for row in s.tasks() if row["id"] == task_id)["can_write"])
        result = s.submit(task_id, expected=403)
        self.assertEqual(result["error"], "task_expired")
        self.assertEqual(s.outbound_attempts, [])


if __name__ == "__main__":
    unittest.main()
