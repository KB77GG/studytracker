"""Full-reading publication is all-or-none, including late conflicts/retries."""

import json
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from models import PlanItem, Task, db
from models_task_planner import TaskPlannerEntry, TaskPlannerEvent
from services import task_planner as planner
from services import task_planner_resources as resources
from services import task_planner_series as series
from tests.test_task_planner import NOW, PlannerFixture


class TaskPlannerBundlesTest(PlannerFixture):
    def setUp(self):
        super().setUp()
        root = Path(self.directory.name) / "static/reading_tests"
        root.mkdir(parents=True)
        for test in (1, 2):
            test_id = f"ielts10_test{test}_reading"
            passages = []
            for number, (start, end) in enumerate(((1, 13), (14, 26), (27, 40)), 1):
                passages.append({"passage": number, "content": {"paragraphs": [{"text": "Synthetic text."}]},
                                 "groups": [{"group_id": f"g{number}", "type": 1,
                                             "desc": "TRUE FALSE NOT GIVEN",
                                             "questions": [{"id": f"q{i}", "number": i, "title": "Synthetic question.",
                                                            "answer": "TRUE", "options": [
                                                                {"key": key, "text": key}
                                                                for key in ("TRUE", "FALSE", "NOT GIVEN")]}
                                                           for i in range(start, end + 1)]}]})
            (root / f"{test_id}.json").write_text(json.dumps({
                "id": test_id, "title": f"Cambridge 10 Test {test}", "passages": passages,
            }), encoding="utf-8")

    def create_bundle(self, **changes):
        data = {"name": "合成整套阅读", "kind": "reading_test", "student_id": self.student_id,
                "start_date": NOW.date().isoformat(), "end_date": NOW.date().isoformat(),
                "selection": {}, "source_scopes": ["cambridge:10"], "start_resource_id": "ielts10_test1_reading:all",
                "weekday_counts": [1] * 7, "skip_assigned": True, "planned_minutes": 20,
                "note": "", "wait_for_previous": False, "request_key": str(uuid.uuid4())}
        data.update(changes)
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        row = series.create_series(data, self.staff_id, now=NOW)
        series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        entries = [db.session.get(TaskPlannerEntry, item.entry_id) for item in series._items(row.id)]
        return row, entries

    def test_any_member_publishes_complete_bundle_and_all_retries_are_idempotent(self):
        _row, entries = self.create_bundle()
        original_versions = [entry.version for entry in entries]
        result = planner.publish_entry(entries[1].id, self.staff_id, entries[1].version, now=NOW)
        self.assertEqual(result.id, entries[1].id)
        self.assertEqual({entry.status for entry in entries}, {"published"})
        self.assertEqual(Task.query.count(), 3)
        self.assertEqual(PlanItem.query.count(), 3)
        ids = [entry.published_task_id for entry in entries]
        self.assertEqual([task.reading_passage_number for task in Task.query.order_by(Task.id)], [1, 2, 3])
        for entry, version in zip(entries, original_versions, strict=True):
            self.assertEqual(planner.publish_entry(entry.id, self.staff_id, version, now=NOW).published_task_id,
                             entry.published_task_id)
        self.assertEqual([entry.published_task_id for entry in entries], ids)
        self.assertEqual(Task.query.count(), 3)
        self.assertEqual(TaskPlannerEvent.query.filter_by(action="publish").count(), 3)

    def test_late_p2_conflict_blocks_all_three_without_creating_tasks(self):
        _row, entries = self.create_bundle()
        # Synthetic concurrent confirmation after the full-Test preview.
        other = self.draft(kind="reading_passage", selection={"test_id": "ielts10_test1_reading", "passage_number": 2})
        other.status = "ready"
        other.confirmed_at = NOW.replace(tzinfo=None)
        other.confirmed_by = self.staff_id
        db.session.commit()
        result = planner.publish_entry(entries[0].id, self.staff_id, entries[0].version, now=NOW)
        self.assertEqual(result.status, "blocked")
        self.assertEqual({entry.status for entry in entries}, {"blocked"})
        self.assertTrue(all("整套阅读" in entry.last_error for entry in entries))
        self.assertEqual(other.status, "ready")
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(PlanItem.query.count(), 0)

    def test_late_p2_resource_change_blocks_p1_and_p3_too(self):
        _row, entries = self.create_bundle()
        path = Path(self.directory.name) / "static/reading_tests/ielts10_test1_reading.json"
        payload = json.loads(path.read_text())
        payload["passages"][1]["groups"] = []
        path.write_text(json.dumps(payload))
        planner.publish_entry(entries[0].id, self.staff_id, entries[0].version, now=NOW)
        self.assertEqual({entry.status for entry in entries}, {"blocked"})
        self.assertEqual(Task.query.count(), 0)

    def test_second_task_write_failure_rolls_back_entire_bundle_then_retries(self):
        _row, entries = self.create_bundle()
        original = resources.create_resource_task
        count = 0

        def fail_second(*args, **kwargs):
            nonlocal count
            task = original(*args, **kwargs)
            count += 1
            if count == 2:
                raise RuntimeError("synthetic second write failure")
            return task

        with patch.object(resources, "create_resource_task", side_effect=fail_second):
            result = planner.publish_entry(entries[0].id, self.staff_id, entries[0].version, now=NOW)
        self.assertEqual(result.status, "failed")
        self.assertEqual({entry.status for entry in entries}, {"failed"})
        self.assertEqual({entry.published_task_id for entry in entries}, {None})
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(PlanItem.query.count(), 0)
        self.assertEqual(TaskPlannerEvent.query.filter_by(action="publish").count(), 0)
        self.assertEqual(TaskPlannerEvent.query.filter_by(action="failed").count(), 3)
        planner.publish_entry(entries[2].id, self.staff_id, entries[2].version, now=NOW)
        self.assertEqual({entry.status for entry in entries}, {"published"})
        self.assertEqual(Task.query.count(), 3)

    def test_automatic_gates_and_wrong_date_leave_bundle_ready(self):
        _row, entries = self.create_bundle()
        for kwargs, code in (({"automatic": True}, "not_enabled"),
                             ({"actor_id": self.staff_id, "expected_version": entries[0].version,
                               "now": NOW + timedelta(days=1)}, "wrong_date")):
            with self.subTest(code=code), self.assertRaises(planner.TaskPlannerError) as raised:
                planner.publish_entry(entries[0].id, **{"now": NOW, **kwargs})
            self.assertEqual(raised.exception.code, code)
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        with self.assertRaises(planner.TaskPlannerError) as raised:
            planner.publish_entry(entries[0].id, automatic=True, now=NOW.replace(hour=9))
        self.assertEqual(raised.exception.code, "outside_window")
        self.assertEqual({entry.status for entry in entries}, {"ready"})
        self.assertEqual(Task.query.count(), 0)

    def test_runner_counts_bundle_entries_once_and_does_not_retry_failure_in_same_run(self):
        _row, entries = self.create_bundle()
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        with patch.object(resources, "create_resource_task", side_effect=RuntimeError("synthetic failure")) as create:
            report = planner.run_due(now=NOW)
        self.assertEqual(create.call_count, 1)
        self.assertEqual((report["eligible"], report["failed"], report["skipped"]), (3, 3, 0))
        self.assertEqual(Task.query.count(), 0)
        report = planner.run_due(now=NOW)
        self.assertEqual((report["eligible"], report["published"]), (3, 3))
        self.assertEqual(Task.query.count(), 3)
        self.assertEqual(planner.run_due(now=NOW)["eligible"], 0)

    def test_old_unmarked_three_passages_still_publish_independently(self):
        _row, entries = self.create_bundle(kind="reading_passage", selection={"passage_number": None},
                                           start_resource_id="ielts10_test1_reading:1", weekday_counts=[3] * 7,
                                           skip_assigned=False)
        planner.publish_entry(entries[0].id, self.staff_id, entries[0].version, now=NOW)
        self.assertEqual([entry.status for entry in entries], ["published", "ready", "ready"])
        self.assertEqual(Task.query.count(), 1)

    def test_two_full_tests_same_day_are_separate_atomic_bundles(self):
        _row, entries = self.create_bundle(weekday_counts=[2] * 7)
        planner.publish_entry(entries[1].id, self.staff_id, entries[1].version, now=NOW)
        self.assertEqual([entry.status for entry in entries], ["published"] * 3 + ["ready"] * 3)
        planner.publish_entry(entries[4].id, self.staff_id, entries[4].version, now=NOW)
        self.assertEqual({entry.status for entry in entries}, {"published"})
        self.assertEqual(Task.query.count(), 6)

    def test_missing_member_fails_closed_without_publishing_remaining_passages(self):
        _row, entries = self.create_bundle()
        entries[1].status = "cancelled"
        db.session.commit()
        planner.publish_entry(entries[0].id, self.staff_id, entries[0].version, now=NOW)
        self.assertEqual([entry.status for entry in entries], ["blocked", "cancelled", "blocked"])
        self.assertEqual(Task.query.count(), 0)
