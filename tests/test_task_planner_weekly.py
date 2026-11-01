"""Weekly calendars preserve native tasks, atomicity, and old line contracts."""

import copy
import json
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from models import DictationWord, Task, db
from models_task_planner import TaskPlannerEntry, TaskPlannerSeries
from services import task_planner as planner
from services import task_planner_resources as resources
from services import task_planner_series as series
from services.task_planner_weekly import weekly_definition
from tests import test_task_planner_series as series_tests
from tests.test_task_planner import NOW, PlannerFixture


class TaskPlannerWeeklyTest(PlannerFixture):
    def setUp(self):
        super().setUp()
        (Path(self.directory.name) / "static").mkdir(exist_ok=True)
        series_tests.TaskPlannerSeriesTest.seed_sequence_resources(self)
        root = Path(self.directory.name) / "static/reading_tests"
        root.mkdir(exist_ok=True)
        for volume, test in ((10, 1), (10, 2), (10, 10), (11, 1), (11, 2), (11, 3)):
            test_id = f"ielts{volume}_test{test}_reading"
            passages = []
            for number, (start, end) in enumerate(((1, 13), (14, 26), (27, 40)), 1):
                passages.append({"passage": number,
                                 "content": {"paragraphs": [{"text": "The tree is green."}]},
                                 "groups": [{"group_id": f"g{number}", "type": 1,
                                             "desc": "TRUE FALSE NOT GIVEN",
                                             "questions": [{"id": f"q{i}", "number": i,
                                                            "title": "The tree is green.", "answer": "TRUE",
                                                            "options": [{"key": key, "text": key}
                                                                        for key in ("TRUE", "FALSE", "NOT GIVEN")]}
                                                           for i in range(start, end + 1)]}]})
            (root / f"{test_id}.json").write_text(json.dumps({
                "id": test_id, "title": f"Cambridge {volume} Test {test}", "passages": passages,
            }), encoding="utf-8")
        db.session.add_all([DictationWord(book_id=self.book_id, sequence=i, word=f"word{i}")
                            for i in range(9, 81)])
        db.session.commit()
        resources._cached_groups.cache_clear()

    def tearDown(self):
        resources._cached_groups.cache_clear()
        super().tearDown()

    def activity(self, key, kind, selection, start):
        return {"id": key, "name": key, "kind": kind, "selection": selection,
                "source_scopes": ["cambridge:10", "cambridge:11"], "start_resource_id": start,
                "planned_minutes": 25, "note": "合成练习说明"}

    def payload(self, **changes):
        activities = [
            self.activity("listen-part", "listening_test", {"section_number": 1}, "ielts10_test1:1"),
            self.activity("read-part", "reading_passage", {"passage_number": 1}, "ielts10_test1_reading:1"),
            self.activity("listen-all", "listening_test", {"section_number": None}, "ielts10_test1:all"),
            self.activity("read-all", "reading_test", {}, "ielts10_test1_reading:all"),
        ]
        days = [[] for _ in range(7)]
        for weekday, key in ((0, "listen-part"), (3, "read-part"), (5, "listen-all"), (6, "read-all")):
            days[weekday] = [{"activity_id": key, "quantity": 1}]
        data = {"name": "合成听阅周安排", "kind": "weekly", "student_id": self.student_id,
                "start_date": "2026-11-02", "end_date": "2026-11-15", "cycle_weeks": 1,
                "activities": activities, "week_rules": [days], "skip_assigned": True,
                "planned_minutes": 20, "note": "", "wait_for_previous": False,
                "request_key": str(uuid.uuid4())}
        data.update(changes)
        return data

    def save(self, data):
        data = copy.deepcopy(data)
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        return series.create_series(data, self.staff_id, now=NOW)

    def entries(self, row):
        return [db.session.get(TaskPlannerEntry, item.entry_id) for item in series._items(row.id)]

    def test_one_week_uses_calendar_days_and_independent_progress(self):
        preview = series.preview_series(self.payload(), self.staff_id, now=NOW)
        self.assertEqual(preview["cycle_anchor"], "2026-11-02")
        self.assertEqual(preview["totals"]["days"], 8)
        self.assertEqual(len(preview["rows"]), 12)
        self.assertEqual(preview["totals"]["units"], 8)
        monday = [r for r in preview["rows"] if r["target_date"] in {"2026-11-02", "2026-11-09"}]
        self.assertEqual([r["selection"]["test_id"] for r in monday], ["ielts10_test1", "ielts10_test10"])
        saturday = next(r for r in preview["rows"] if r["target_date"] == "2026-11-07")
        self.assertEqual(saturday["selection"], {"test_id": "ielts10_test2", "section_number": None})
        sunday = [r for r in preview["rows"] if r["target_date"] == "2026-11-08"]
        self.assertEqual([r["selection"]["passage_number"] for r in sunday], [1, 2, 3])
        self.assertEqual({r["selection"]["test_id"] for r in sunday}, {"ielts10_test2_reading"})
        self.assertTrue(preview["skipped"])
        self.assertEqual(TaskPlannerEntry.query.count(), 0)
        self.assertEqual(Task.query.count(), 0)

    def test_two_week_rotation_is_anchored_to_start_week_monday(self):
        data = self.payload(start_date="2026-11-05", end_date="2026-11-16", cycle_weeks=2)
        week_two = copy.deepcopy(data["week_rules"][0])
        week_two[0], week_two[3] = week_two[3], week_two[0]
        week_two[5], week_two[6] = week_two[6], week_two[5]
        data["week_rules"].append(week_two)
        _profile, definition, requests = weekly_definition(data, self.staff_id, NOW)
        self.assertEqual(definition["cycle_anchor"], "2026-11-02")
        actual = {r["target_date"].isoformat(): r["activity_id"] for r in requests}
        self.assertEqual(actual["2026-11-05"], "read-part")
        self.assertEqual(actual["2026-11-09"], "read-part")
        self.assertEqual(actual["2026-11-12"], "listen-part")
        self.assertEqual(actual["2026-11-14"], "read-all")
        self.assertEqual(actual["2026-11-15"], "listen-all")
        self.assertEqual(actual["2026-11-16"], "listen-part")

    def test_save_confirm_cancel_keeps_native_entries_and_replay(self):
        data = self.payload(end_date="2026-11-08", wait_for_previous=True)
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        row = series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual(series.create_series(data, self.staff_id, now=NOW).id, row.id)
        entries = self.entries(row)
        self.assertEqual([e.kind for e in entries], ["listening_test", "reading_passage", "listening_test",
                                                   "reading_passage", "reading_passage", "reading_passage"])
        self.assertTrue(all(e.planned_minutes == 25 and e.note == "合成练习说明" for e in entries))
        self.assertEqual([i.previous_entry_id for i in series._items(row.id)],
                         [None, entries[0].id, entries[1].id, entries[2].id, entries[2].id, entries[2].id])
        series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        self.assertEqual({e.status for e in entries}, {"ready"})
        public = series.series_payload(row)
        self.assertEqual(public["cycle_weeks"], 1)
        self.assertTrue(public["skip_assigned"])
        self.assertEqual(public["activities"][3]["kind"], "reading_test")
        series.cancel_series(row.id, row.version, self.staff_id, now=NOW)
        self.assertEqual({e.status for e in entries}, {"cancelled"})
        self.assertEqual(Task.query.count(), 0)

    def test_changed_rules_or_skip_policy_cannot_reuse_request_key(self):
        data = self.payload(end_date="2026-11-08")
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        row = series.create_series(data, self.staff_id, now=NOW)
        for change in ({"skip_assigned": False}, {"cycle_weeks": 2}, {"week_rules": [[]]}):
            with self.subTest(change=change), self.assertRaises(planner.TaskPlannerError) as raised:
                series.create_series({**data, **change}, self.staff_id, now=NOW)
            self.assertEqual(raised.exception.code, "idempotency_conflict")
        self.assertEqual(TaskPlannerSeries.query.count(), 1)
        self.assertEqual(row.kind, "weekly")

    def test_invalid_weekly_definition_rejected_before_writes(self):
        for change in (
            {"cycle_weeks": True}, {"cycle_weeks": 3}, {"week_rules": [[]]},
            {"skip_assigned": "true"}, {"wait_for_previous": 1}, {"activities": []},
            {"end_date": "2026-12-03"}, {"start_date": "2026-10-28"},
        ):
            with self.subTest(change=change), self.assertRaises(planner.TaskPlannerError):
                series.preview_series(self.payload(**change), self.staff_id, now=NOW)
        for alter in ("duplicate", "unknown", "quantity", "student", "unused", "nested"):
            data = self.payload()
            if alter == "duplicate":
                data["activities"][1]["id"] = data["activities"][0]["id"]
            elif alter == "unknown":
                data["week_rules"][0][0][0]["activity_id"] = "missing"
            elif alter == "quantity":
                data["week_rules"][0][0][0]["quantity"] = 21
            elif alter == "student":
                data["activities"][0]["student_id"] = self.student_id + 1
            elif alter == "unused":
                data["week_rules"][0][0] = []
            else:
                data["activities"][0]["kind"] = "weekly"
            with self.subTest(alter=alter), self.assertRaises(planner.TaskPlannerError):
                series.preview_series(data, self.staff_id, now=NOW)
        self.assertEqual(TaskPlannerSeries.query.count(), 0)
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_duplicate_same_day_activity_and_empty_selected_window_rejected(self):
        data = self.payload()
        data["week_rules"][0][0] *= 2
        with self.assertRaises(planner.TaskPlannerError):
            weekly_definition(data, self.staff_id, NOW)
        with self.assertRaises(planner.TaskPlannerError):
            weekly_definition(self.payload(start_date="2026-11-03", end_date="2026-11-04"), self.staff_id, NOW)

    def test_failed_batch_create_rolls_back_all_entries(self):
        data = self.payload(end_date="2026-11-08")
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        original = planner._event
        count = 0

        def fail_after_first(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError("synthetic late failure")
            return original(*args, **kwargs)

        with patch.object(planner, "_event", side_effect=fail_after_first), self.assertRaises(RuntimeError):
            series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual(TaskPlannerSeries.query.count(), 0)
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_reading_full_single_line_also_creates_native_passages(self):
        data = {**self.payload()["activities"][3], "student_id": self.student_id,
                "start_date": "2026-11-01", "end_date": "2026-11-08", "weekday_counts": [0, 0, 0, 0, 0, 0, 1],
                "wait_for_previous": False, "request_key": str(uuid.uuid4())}
        preview = series.preview_series(data, self.staff_id, now=NOW)
        self.assertEqual(preview["quota_unit"], "套")
        self.assertEqual(preview["totals"]["units"], 2)
        self.assertEqual(len(preview["rows"]), 6)
        row = self.save(data)
        self.assertEqual({entry.kind for entry in self.entries(row)}, {"reading_passage"})

    def test_skip_flag_invalid_type_is_rejected_on_ordinary_line(self):
        data = {**self.payload()["activities"][0], "student_id": self.student_id,
                "start_date": "2026-11-02", "end_date": "2026-11-02", "weekday_counts": [1] * 7,
                "skip_assigned": "true"}
        with self.assertRaises(planner.TaskPlannerError):
            series.preview_series(data, self.staff_id, now=NOW)

    def test_history_change_between_preview_and_save_requires_new_preview(self):
        data = self.payload(end_date="2026-11-08")
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        self.ready(kind="listening_test", selection={"test_id": "ielts10_test1", "section_number": 1})
        with self.assertRaises(planner.TaskPlannerError) as raised:
            series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual(raised.exception.code, "preview_changed")
        self.assertEqual(TaskPlannerSeries.query.count(), 0)
        self.assertEqual(TaskPlannerEntry.query.count(), 1)

    def test_confirm_conflict_keeps_entire_weekly_batch_as_draft(self):
        row = self.save(self.payload(end_date="2026-11-08"))
        self.ready(kind="listening_test", selection={"test_id": "ielts10_test1", "section_number": 1})
        with self.assertRaises(planner.TaskPlannerError):
            series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        self.assertEqual(row.status, "draft")
        self.assertEqual({e.status for e in self.entries(row)}, {"draft"})
        self.assertEqual(Task.query.count(), 0)

    def test_mixed_activities_wait_for_entire_previous_learning_day(self):
        data = self.payload(start_date="2026-10-29", end_date="2026-10-30", wait_for_previous=True)
        data["activities"] = data["activities"][:2]
        pair = [{"activity_id": activity["id"], "quantity": 1} for activity in data["activities"]]
        data["week_rules"] = [[[], [], [], pair, copy.deepcopy(pair), [], []]]
        row = self.save(data)
        series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        first, second, third, fourth = self.entries(row)
        for entry in (first, second):
            self.assertEqual(planner.publish_entry(entry.id, self.staff_id, entry.version, now=NOW).status, "published")
        task = db.session.get(Task, second.published_task_id)
        task.student_submitted = True
        task.submitted_at = NOW.replace(tzinfo=None)
        task.plan_item.student_status = "submitted"
        db.session.commit()
        self.assertEqual(planner.publish_entry(third.id, self.staff_id, third.version,
                                              now=NOW + timedelta(days=1)).status, "blocked")
        task = db.session.get(Task, first.published_task_id)
        task.student_submitted = True
        task.submitted_at = NOW.replace(tzinfo=None)
        task.plan_item.student_status = "submitted"
        db.session.commit()
        self.assertEqual(planner.publish_entry(fourth.id, self.staff_id, fourth.version,
                                              now=NOW + timedelta(days=1)).status, "published")
        self.assertEqual(Task.query.count(), 3)
        self.assertEqual(third.target_date.isoformat(), "2026-10-30")

    def test_weekly_api_permissions_csrf_preview_create_and_details(self):
        endpoint = "/api/task-planner/series/preview"
        data = self.payload(end_date="2026-11-08")
        self.assertEqual(self.client.post(endpoint, json=data).status_code, 401)
        self.login(self.user_id)
        self.assertEqual(self.client.post(endpoint, json=data).status_code, 403)
        self.login()
        self.assertEqual(self.client.post(endpoint, json=data).status_code, 403)
        headers = self.csrf_headers()
        with patch.object(planner, "beijing_now", return_value=NOW):
            response = self.client.post(endpoint, json=data, headers=headers)
            self.assertEqual(response.status_code, 200)
            data["preview_hash"] = response.get_json()["preview"]["preview_hash"]
            result = self.client.post("/api/task-planner/series", json=data, headers=headers)
            self.assertEqual(result.status_code, 201)
            row = result.get_json()["series"]
            details = self.client.get(f"/api/task-planner/series/{row['id']}").get_json()
            self.assertEqual(details["series"]["week_rules"], data["week_rules"])
            self.assertEqual(details["series"]["cycle_anchor"], "2026-11-02")
            self.assertEqual(len(details["entries"]), 6)
        self.assertFalse(self.network_mock.called)
