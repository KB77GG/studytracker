"""Cross-module acceptance: real assistant and student HTTP routes + scheduler.

Unlike recovery unit fixtures, this suite never marks a student's task done or
inserts settlements to stand in for completion: reading is submitted and graded
by the real app.py route. Synthetic identities/resources and a controlled clock
are the only data used; no production config, database or service is opened.
"""

import unittest
import uuid

from models import PlanItem, Task, db
from models_task_planner import TaskPlannerRecoveryDecision
from tests.recovery_e2e_support import RecoverySandbox


class RecoveryJourneyE2ETest(unittest.TestCase):
    def setUp(self):
        self.s = RecoverySandbox()
        self.addCleanup(self.s.close)

    def test_makeup_student_submits_and_next_0305_resumes_only_its_line(self):
        s = self.s
        line, original_entries = s.create_line()
        other_line, _ = s.create_line(passage=2, wait=False, name="独立学习线")
        old_id = original_entries[0]["published_task_id"]
        s.set_time("2026-11-02T03:05:00+08:00")
        first_run = s.run_due()
        self.assertEqual((first_run["published"], first_run["blocked"]), (1, 1))
        old = s.original_snapshot([old_id])
        other_entries = s.entries(other_line)
        other_tasks = [
            entry["published_task_id"] for entry in other_entries if entry["published_task_id"]
        ]
        other = s.original_snapshot(other_tasks)
        inbox = s.inbox()
        self.assertIn(line, [item["series_id"] for item in inbox])
        with s.app.app_context():
            before = (
                Task.query.count(),
                PlanItem.query.count(),
                TaskPlannerRecoveryDecision.query.count(),
            )
        request_data = {"series_id": line, "source_date": "2026-11-01", "action": "makeup"}
        preview = s.staff("/api/task-planner/inbox/preview", request_data)["preview"]
        with s.app.app_context():
            self.assertEqual(
                before,
                (
                    Task.query.count(),
                    PlanItem.query.count(),
                    TaskPlannerRecoveryDecision.query.count(),
                ),
            )
        self.assertEqual(
            [change["to"] for change in preview["changes"]], ["2026-11-03", "2026-11-04"]
        )
        request_data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        applied = s.staff("/api/task-planner/inbox/apply", request_data)["result"]
        self.assertEqual(s.staff("/api/task-planner/inbox/apply", request_data)["result"], applied)
        self.assertEqual(s.original_snapshot([old_id]), old)
        self.assertEqual(s.entries(other_line), other_entries)
        self.assertEqual(s.original_snapshot(other_tasks), other)
        new_id = applied["created_task_ids"][0]
        rows = {row["id"]: row for row in s.tasks()}
        self.assertEqual((rows[old_id]["can_write"], rows[new_id]["can_write"]), (False, True))
        self.assertEqual(rows[new_id]["date"], "2026-11-02")
        result = s.submit(new_id)
        self.assertTrue(result["synced"])
        self.assertEqual((result["task"]["status"], result["result"]["correct"]), ("done", 13))
        self.assertEqual(s.original_snapshot([old_id]), old)
        s.set_time("2026-11-03T03:04:59+08:00")
        self.assertTrue(s.run_due()["outside_window"])
        s.set_time("2026-11-03T03:05:00+08:00")
        resumed = s.run_due()
        self.assertEqual((resumed["published"], resumed["blocked"]), (2, 0))
        self.assertEqual(s.run_due()["published"], 0)
        entries = s.entries(line)
        next_task = next(entry for entry in entries if entry["target_date"] == "2026-11-03")
        self.assertEqual(next_task["status"], "published")
        self.assertIn(
            next_task["published_task_id"], [row["id"] for row in s.tasks() if row["can_write"]]
        )
        self.assertFalse(s.outbound_attempts)

    def test_reading_full_bundle_requires_three_real_submissions_then_resumes(self):
        s = self.s
        line, entries = s.create_line(kind="reading_test", days=2)
        old_ids = [entry["published_task_id"] for entry in entries[:3]]
        old = s.original_snapshot(old_ids)
        s.set_time("2026-11-02T10:00:00+08:00")
        _, result = s.recover(line, "2026-11-01")
        self.assertEqual(len(result["created_task_ids"]), 3)
        counts = [
            s.submit(task_id)["result"]["total"] for task_id in result["created_task_ids"][:2]
        ]
        self.assertEqual(counts, [13, 13])
        s.set_time("2026-11-03T02:59:59+08:00")
        third = s.submit(result["created_task_ids"][2])
        self.assertEqual(third["result"]["total"], 14)
        self.assertEqual(s.original_snapshot(old_ids), old)
        s.set_time("2026-11-03T03:05:00+08:00")
        report = s.run_due()
        self.assertEqual((report["published"], report["blocked"]), (3, 0))
        current = [row for row in s.tasks() if row["date"] == "2026-11-03"]
        self.assertEqual(len(current), 3)
        self.assertTrue(all(row["can_write"] for row in current))
        with s.app.app_context():
            self.assertEqual(
                {db.session.get(Task, row["id"]).reading_test_id for row in current},
                {"ielts10_test2_reading"},
            )

    def test_reading_makeup_two_of_three_submitted_still_blocks_then_last_passage_recovers(self):
        s = self.s
        line, _ = s.create_line(kind="reading_test", days=2)
        s.set_time("2026-11-02T10:00:00+08:00")
        _, first = s.recover(line, "2026-11-01")
        makeup_ids = first["created_task_ids"]
        s.submit(makeup_ids[0])
        s.submit(makeup_ids[1])
        submitted_originals = s.original_snapshot(makeup_ids[:2])
        s.set_time("2026-11-03T03:05:00+08:00")
        blocked = s.run_due()
        self.assertEqual((blocked["published"], blocked["blocked"]), (0, 3))
        self.assertEqual([task["id"] for task in s.inbox()[0]["tasks"]], [makeup_ids[2]])
        _, last = s.recover(line, "2026-11-02")
        self.assertEqual(len(last["created_task_ids"]), 1)
        completion = s.submit(last["created_task_ids"][0])
        self.assertEqual((completion["result"]["correct"], completion["result"]["total"]), (14, 14))
        s.set_time("2026-11-04T03:05:00+08:00")
        self.assertEqual(s.run_due()["published"], 3)
        self.assertEqual(s.original_snapshot(makeup_ids[:2]), submitted_originals)

    def test_partial_reading_only_p2_makeup_preserves_original_scores_and_attempts(self):
        s = self.s
        line, entries = s.create_line(kind="reading_test", days=2)
        old_ids = [entry["published_task_id"] for entry in entries[:3]]
        s.submit(old_ids[0], correct=False)
        s.submit(old_ids[2])
        old = s.original_snapshot(old_ids)
        s.set_time("2026-11-02T10:00:00+08:00")
        self.assertEqual([task["id"] for task in s.inbox()[0]["tasks"]], [old_ids[1]])
        _, result = s.recover(line, "2026-11-01")
        self.assertEqual(len(result["created_task_ids"]), 1)
        new_id = result["created_task_ids"][0]
        with s.app.app_context():
            self.assertEqual(db.session.get(Task, new_id).reading_passage_number, 2)
        s.submit(new_id)
        self.assertEqual(s.original_snapshot(old_ids), old)
        s.set_time("2026-11-03T03:05:00+08:00")
        self.assertEqual(s.run_due()["published"], 3)
        self.assertEqual(s.original_snapshot(old_ids), old)

    def test_consecutive_unfinished_makeups_reappear_and_only_latest_completion_resumes(self):
        s = self.s
        line, entries = s.create_line(days=3)
        all_old = [entries[0]["published_task_id"]]
        for day in (2, 3, 4):
            s.set_time(f"2026-11-{day:02d}T03:05:00+08:00")
            blocked = s.run_due()
            self.assertEqual(blocked["published"], 0)
            inbox = s.inbox()
            self.assertEqual(len(inbox), 1)
            self.assertEqual(inbox[0]["tasks"][0]["id"], all_old[-1])
            _, result = s.recover(line, f"2026-11-{day - 1:02d}")
            self.assertEqual(result["task_mappings"][0]["source_task_id"], all_old[-1])
            all_old.append(result["created_task_ids"][0])
        old = s.original_snapshot(all_old[:-1])
        s.submit(all_old[-1])
        s.set_time("2026-11-05T03:05:00+08:00")
        self.assertEqual((s.run_due()["published"], len(s.inbox())), (1, 0))
        self.assertEqual(s.original_snapshot(all_old[:-1]), old)

    def test_continue_releases_only_selected_old_day_and_keeps_future_wait_rule(self):
        s = self.s
        line, entries = s.create_line()
        old_id = entries[0]["published_task_id"]
        original = s.original_snapshot([old_id])
        s.set_time("2026-11-02T03:05:00+08:00")
        self.assertEqual(s.run_due()["blocked"], 1)
        _, result = s.recover(line, "2026-11-01", action="continue")
        self.assertEqual(s.original_snapshot([old_id]), original)
        today = next(entry for entry in s.entries(line) if entry["target_date"] == "2026-11-02")
        self.assertEqual(today["status"], "published")
        self.assertEqual(len(result["published_entry_ids"]), 1)
        s.set_time("2026-11-03T03:05:00+08:00")
        self.assertEqual(s.run_due()["blocked"], 1)
        self.assertEqual([item["source_date"] for item in s.inbox()], ["2026-11-02"])

    def test_today_published_task_blocks_makeup_without_changing_student_work(self):
        s = self.s
        line, _ = s.create_line(wait=False)
        s.set_time("2026-11-02T03:05:00+08:00")
        self.assertEqual(s.run_due()["published"], 1)
        old_tasks = s.tasks()
        preview = s.staff(
            "/api/task-planner/inbox/preview",
            {"series_id": line, "source_date": "2026-11-01", "action": "makeup"},
        )["preview"]
        self.assertFalse(preview["can_apply"])
        self.assertTrue(any("不能撤回" in blocker for blocker in preview["blockers"]))
        self.assertEqual(s.tasks(), old_tasks)
        today_id = next(row["id"] for row in old_tasks if row["date"] == "2026-11-02")
        self.assertEqual(s.submit(today_id)["task"]["status"], "done")

    def test_grace_period_completion_prevents_recovery_and_0300_opens_it(self):
        s = self.s
        line, entries = s.create_line()
        old_id = entries[0]["published_task_id"]
        s.set_time("2026-11-02T02:59:59+08:00")
        self.assertTrue(next(row for row in s.tasks() if row["id"] == old_id)["can_write"])
        self.assertEqual(s.inbox(), [])
        for action in ("makeup", "continue"):
            data = {"series_id": line, "source_date": "2026-11-01", "action": action}
            response = s.clients["assistant"].post(
                "/api/task-planner/inbox/preview", json=data, headers={"X-CSRF-Token": s.csrf}
            )
            self.assertEqual(response.status_code, 409, response.get_json())
            self.assertEqual(response.get_json()["error"], "source_still_open")
        s.set_time("2026-11-02T03:00:00+08:00")
        self.assertFalse(next(row for row in s.tasks() if row["id"] == old_id)["can_write"])
        rejected = s.submit(old_id, expected=403)
        self.assertEqual(rejected["error"], "task_expired")
        self.assertEqual(len(s.inbox()), 1)
        _, result = s.recover(line, "2026-11-01")
        self.assertEqual(len(result["created_task_ids"]), 1)

    def test_grace_student_real_submission_resumes_without_makeup_and_old_backlog_allowed(self):
        s = self.s
        line, entries = s.create_line()
        s.set_time("2026-11-02T02:59:59+08:00")
        self.assertEqual(s.submit(entries[0]["published_task_id"])["task"]["status"], "done")
        s.set_time("2026-11-02T03:05:00+08:00")
        self.assertEqual(s.run_due()["published"], 1)
        s.set_time("2026-11-04T02:59:00+08:00")
        _, result = s.recover(line, "2026-11-02")
        self.assertEqual(len(result["created_task_ids"]), 1)


if __name__ == "__main__":
    unittest.main()
