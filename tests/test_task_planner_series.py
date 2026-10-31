"""Finite learning-line contracts using synthetic SQLite and local resources."""

import copy
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect

from models import DictationWord, PlanItem, Task, VocabularyTaskSettlement, db
from models_task_planner import (
    TaskPlannerEntry,
    TaskPlannerEvent,
    TaskPlannerSeries,
    TaskPlannerSeriesItem,
    ensure_schema,
)
from services import task_planner as planner
from services import task_planner_resources as resources
from services import task_planner_series as series
from tests.test_task_planner import NOW, PlannerFixture


class TaskPlannerSeriesTest(PlannerFixture):
    def setUp(self):
        super().setUp()
        db.session.add_all([
            DictationWord(book_id=self.book_id, sequence=i, word=f"word{i}", translation=f"释义{i}")
            for i in range(9, 81)
        ])
        db.session.commit()
        self.reading_root = Path(self.directory.name) / "static/reading_tests"
        self.reading_root.mkdir(parents=True)
        for test_no in (10, 2, 1):
            test_id = f"ielts10_test{test_no}_reading"
            payload = {
                "id": test_id, "title": f"Cambridge 10 Test {test_no}",
                "passages": [{
                    "passage": i,
                    "content": {"paragraphs": [{"text": "The tree is green."}]},
                    "groups": [{
                        "group_id": f"g{i}", "type": 1, "desc": "TRUE FALSE NOT GIVEN",
                        "questions": [{"id": f"q{i}", "number": i, "title": "The tree is green.",
                                       "answer": "TRUE", "options": [
                                           {"key": key, "text": key} for key in ("TRUE", "FALSE", "NOT GIVEN")
                                       ]}],
                    }],
                } for i in (1, 2, 3)],
            }
            (self.reading_root / f"{test_id}.json").write_text(json.dumps(payload), encoding="utf-8")
        resources._cached_groups.cache_clear()

    def tearDown(self):
        resources._cached_groups.cache_clear()
        super().tearDown()

    def series_data(self, **changes):
        payload = {
            "name": "词汇学习线", "student_id": self.student_id,
            "kind": "dictation", "start_date": NOW.date().isoformat(),
            "end_date": (NOW + timedelta(days=6)).date().isoformat(),
            "weekday_counts": [1, 1, 1, 1, 1, 2, 2],
            "selection": {"book_id": self.book_id, "word_start": 1, "vocabulary_goal": "reading"},
            "planned_minutes": 15, "note": "合成安排", "wait_for_previous": False,
            "request_key": str(uuid.uuid4()),
        }
        payload.update(changes)
        return payload

    def create(self, **changes):
        data = self.series_data(**changes)
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        return series.create_series(data, self.staff_id, now=NOW)

    def entries(self, row):
        return [db.session.get(TaskPlannerEntry, item.entry_id) for item in series._items(row.id)]

    def test_weekday_weekend_share_one_sequence_and_preview_has_no_writes(self):
        preview = series.preview_series(self.series_data(), self.staff_id, now=NOW)
        self.assertEqual([row["unit_count"] for row in preview["rows"]], [1, 1, 2, 2, 1, 1, 1])
        self.assertEqual([row["selection"]["word_start"] for row in preview["rows"]], [1, 2, 3, 5, 7, 8, 9])
        self.assertEqual(preview["totals"], {"days": 7, "units": 9, "questions": 0})
        self.assertEqual(TaskPlannerEntry.query.count(), 0)
        self.assertEqual(Task.query.count(), 0)

    def test_rest_days_and_actual_word_sequence_gaps(self):
        DictationWord.query.filter_by(book_id=self.book_id, sequence=2).delete()
        db.session.commit()
        preview = series.preview_series(self.series_data(weekday_counts=[0, 0, 0, 2, 0, 0, 2]), self.staff_id, now=NOW)
        self.assertEqual([row["target_date"] for row in preview["rows"]], ["2026-10-29", "2026-11-01"])
        self.assertEqual([(row["selection"]["word_start"], row["selection"]["word_end"])
                          for row in preview["rows"]], [(1, 3), (4, 5)])

    def test_explicit_book_and_start_groups_use_natural_order(self):
        choices = series.series_sources("reading", "judgment", "cambridge:10")
        self.assertEqual(len(choices["groups"]), 9)
        self.assertEqual(len(choices["sources"]), 4)
        ids = [group["id"] for group in choices["groups"]]
        self.assertIn("test2", ids[3])
        self.assertIn("test10", ids[6])
        data = self.series_data(kind="question_type", selection={"subject": "reading", "standard_type": "judgment"},
                                source_scope="cambridge:10", start_group_id=ids[1],
                                end_date="2026-10-31", weekday_counts=[1, 1, 1, 1, 1, 2, 2])
        preview = series.preview_series(data, self.staff_id, now=NOW)
        self.assertEqual([row["selection"]["group_ids"] for row in preview["rows"]],
                         [[ids[1]], [ids[2]], ids[3:5]])
        self.assertEqual(preview["totals"]["questions"], 4)
        self.assertIn("Cambridge 10 Test 2", preview["rows"][-1]["content_labels"][0])
        data["source_scope"] = "test:ielts10_test1_reading"
        with self.assertRaisesRegex(ValueError, "缺少2组"):
            series.preview_series(data, self.staff_id, now=NOW)
        self.assertEqual(series.series_sources("reading", "judgment")["groups"], [])

    def test_invalid_ranges_quotas_scope_and_insufficient_content_fail_before_write(self):
        invalid = [
            {"end_date": "2026-11-29"}, {"end_date": "2026-10-28"},
            {"weekday_counts": [0] * 7}, {"weekday_counts": [1] * 6},
            {"weekday_counts": [True] * 7}, {"weekday_counts": [1201] * 7},
            {"weekday_counts": [12] * 7}, {"wait_for_previous": "false"},
            {"kind": "reading_passage"}, {"name": ""},
            {"selection": {"book_id": self.book_id, "word_start": 100}},
            {"kind": "question_type", "selection": {"subject": "reading"}},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                series.preview_series(self.series_data(**changes), self.staff_id, now=NOW)
        self.assertEqual(TaskPlannerSeries.query.count(), 0)
        self.assertEqual(TaskPlannerEntry.query.count(), 0)
        # Inclusive 31-day boundary is supported; vocabulary quotas can exceed 20.
        self.assertEqual(len(series.preview_series(self.series_data(end_date="2026-11-28", weekday_counts=[1]*7),
                                                  self.staff_id, now=NOW)["rows"]), 31)
        preview = series.preview_series(self.series_data(end_date="2026-10-29", weekday_counts=[25]*7),
                                        self.staff_id, now=NOW)
        self.assertEqual(preview["totals"]["units"], 25)

    def test_create_is_idempotent_and_preview_is_frozen(self):
        data = self.series_data()
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        row = series.create_series(data, self.staff_id, now=NOW)
        same = series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual(same.id, row.id)
        self.assertEqual(TaskPlannerEntry.query.count(), 7)
        changed = dict(data, name="Different")
        with self.assertRaises(planner.TaskPlannerError) as error:
            series.create_series(changed, self.staff_id, now=NOW)
        self.assertEqual(error.exception.code, "idempotency_conflict")
        changed = dict(changed, request_key=str(uuid.uuid4()))
        with self.assertRaises(planner.TaskPlannerError) as error:
            series.create_series(changed, self.staff_id, now=NOW)
        self.assertEqual(error.exception.code, "preview_changed")
        self.assertEqual((TaskPlannerSeries.query.count(), TaskPlannerEntry.query.count()), (1, 7))
        payload = series.series_payload(row)
        self.assertEqual(payload["status_counts"], {"draft": 7})
        self.assertEqual(payload["published_count"], 0)
        self.assertTrue(payload["student_name"])

    def test_resource_changes_between_preview_create_and_confirm_are_rejected(self):
        data = self.series_data()
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        word = DictationWord.query.filter_by(book_id=self.book_id, sequence=1).one()
        word.word = "changed"
        db.session.commit()
        with self.assertRaisesRegex(ValueError, "重新预览"):
            series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual(TaskPlannerSeries.query.count(), 0)
        row = self.create()
        word = DictationWord.query.filter_by(book_id=self.book_id, sequence=9).one()
        word.word = "changed-again"
        db.session.commit()
        with self.assertRaises(ValueError):
            series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        self.assertEqual({entry.status for entry in self.entries(row)}, {"draft"})
        self.assertEqual(TaskPlannerEvent.query.filter_by(action="confirm").count(), 0)

    def test_create_rolls_back_the_entire_batch_when_later_write_fails(self):
        data = self.series_data()
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        original = planner._event
        count = 0

        def fail_later(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 4:
                raise RuntimeError("synthetic write failure")
            return original(*args, **kwargs)

        with patch.object(planner, "_event", side_effect=fail_later), self.assertRaises(RuntimeError):
            series.create_series(data, self.staff_id, now=NOW)
        for model in (TaskPlannerSeries, TaskPlannerSeriesItem, TaskPlannerEntry, TaskPlannerEvent):
            self.assertEqual(model.query.count(), 0)

    def test_late_conflict_rolls_back_confirmation_and_different_lines_are_independent(self):
        line = self.create()
        other = self.create(name="第二学习线", selection={"book_id": self.book_id, "word_start": 20})
        series.confirm_series(other.id, other.version, self.teacher_id, now=NOW)
        self.ready(target_date="2026-11-04", selection={"book_id": self.book_id, "word_start": 9,
                                                       "word_end": 9, "vocabulary_goal": "reading"})
        with self.assertRaises(planner.TaskPlannerError):
            series.confirm_series(line.id, line.version, self.staff_id, now=NOW)
        self.assertEqual({entry.status for entry in self.entries(line)}, {"draft"})
        self.assertEqual({entry.status for entry in self.entries(other)}, {"ready"})
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(PlanItem.query.count(), 0)

    def test_managed_entries_require_whole_line_operations(self):
        row = self.create(wait_for_previous=True)
        entry = self.entries(row)[0]
        for action in (
            lambda: planner.confirm_entry(entry.id, entry.version, self.staff_id, now=NOW),
            lambda: planner.cancel_entry(entry.id, entry.version, self.staff_id),
            lambda: planner.save_entry(self.data(), self.staff_id, entry.id, entry.version, now=NOW),
        ):
            with self.assertRaisesRegex(ValueError, "学习线"):
                action()
        payload = planner.entry_payload(entry)
        self.assertEqual((payload["series_id"], payload["series_name"], payload["series_managed"]),
                         (row.id, row.name, True))
        self.assertTrue(payload["series_wait_for_previous"])
        with patch.object(planner, "beijing_now", return_value=NOW + timedelta(days=1)):
            self.assertIn("取消学习线未布置部分后重新安排", planner.entry_payload(entry)["error"])

    def test_expired_confirmation_fails_atomically_but_cancel_still_works(self):
        row = self.create()
        with self.assertRaises(ValueError):
            series.confirm_series(row.id, row.version, self.staff_id, now=NOW + timedelta(days=1))
        self.assertEqual({entry.status for entry in self.entries(row)}, {"draft"})
        series.cancel_series(row.id, row.version, self.staff_id, now=NOW + timedelta(days=40))
        self.assertEqual({entry.status for entry in self.entries(row)}, {"cancelled"})

    def test_default_schedule_proceeds_if_previous_was_not_published(self):
        row = self.create()
        series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        entry = self.entries(row)[1]
        self.assertFalse(planner.entry_payload(entry)["series_wait_for_previous"])
        self.assertEqual(planner.publish_entry(entry.id, self.staff_id, entry.version,
                                              now=NOW + timedelta(days=1)).status, "published")
        self.assertEqual(self.entries(row)[0].status, "ready")

    def test_wait_previous_blocks_unpublished_and_does_not_shift(self):
        row = self.create(wait_for_previous=True)
        series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        entry = self.entries(row)[1]
        target = entry.target_date
        result = planner.publish_entry(entry.id, self.staff_id, entry.version, now=NOW + timedelta(days=1))
        self.assertEqual((result.status, result.target_date), ("blocked", target))
        self.assertIn("不会自动顺延", result.last_error)
        self.assertEqual(Task.query.count(), 0)

    def test_wait_previous_requires_matching_settlement_and_honors_returned_review(self):
        for settled, review, expected in ((False, "pending", "blocked"),
                                           (True, "rejected", "blocked"), (True, "pending", "published")):
            with self.subTest(settled=settled, review=review):
                start = 1 if not settled else 20 if review == "rejected" else 40
                row = self.create(wait_for_previous=True, end_date="2026-10-30",
                                  selection={"book_id": self.book_id, "word_start": start})
                series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
                first, second = self.entries(row)
                first = planner.publish_entry(first.id, self.staff_id, first.version, now=NOW)
                task = db.session.get(Task, first.published_task_id)
                task.plan_item.review_status = review
                if settled:
                    db.session.add(VocabularyTaskSettlement(
                        student_id=self.user_id, task_id=task.id, queue_token=f"series-{row.id}",
                        result_json="{}", settled_at=NOW.replace(tzinfo=None),
                    ))
                db.session.commit()
                result = planner.publish_entry(second.id, self.staff_id, second.version, now=NOW + timedelta(days=1))
                self.assertEqual(result.status, expected)

    def test_cancel_preserves_published_task_and_cancels_only_future_entries(self):
        row = self.create()
        series.confirm_series(row.id, row.version, self.staff_id, now=NOW)
        first = self.entries(row)[0]
        planner.publish_entry(first.id, self.staff_id, first.version, now=NOW)
        task_id = first.published_task_id
        series.cancel_series(row.id, row.version, self.staff_id, now=NOW)
        self.assertEqual([entry.status for entry in self.entries(row)], ["published"] + ["cancelled"] * 6)
        self.assertIsNone(db.session.get(Task, task_id).cancelled_at)
        self.assertEqual(series.series_payload(row)["published_count"], 1)

    def test_simultaneous_replays_create_exactly_one_line(self):
        data = self.series_data()
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        barrier = threading.Barrier(2)
        db.session.remove()

        def worker():
            with self.app.app_context():
                barrier.wait(timeout=5)
                result = series.create_series(copy.deepcopy(data), self.staff_id, now=NOW).id
                db.session.remove()
                return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual((TaskPlannerSeries.query.count(), TaskPlannerEntry.query.count()), (1, 7))

    def test_schema_setup_keeps_deployed_entry_columns_unchanged(self):
        before = [column["name"] for column in inspect(db.engine).get_columns("task_planner_entry")]
        ensure_schema()
        ensure_schema()
        self.assertEqual(before, [column["name"] for column in inspect(db.engine).get_columns("task_planner_entry")])
        self.assertIn("task_planner_series_item", inspect(db.engine).get_table_names())

    def test_api_permissions_csrf_and_complete_series_flow(self):
        routes = ("/api/task-planner/series", "/api/task-planner/series/preview",
                  "/api/task-planner/series/1/confirm", "/api/task-planner/series/1/cancel")
        for route in routes:
            self.assertEqual(self.client.post(route, json={}).status_code, 401)
        for user in (self.user_id, self.parent_id):
            self.login(user)
            self.assertEqual(self.client.get("/api/task-planner/series").status_code, 403)
            for route in routes:
                self.assertEqual(self.client.post(route, json={}).status_code, 403)
        self.login()
        for route in routes:
            self.assertEqual(self.client.post(route, json={}).status_code, 403)
        headers = self.csrf_headers()
        with patch.object(planner, "beijing_now", return_value=NOW):
            data = self.series_data()
            response = self.client.post("/api/task-planner/series/preview", json=data, headers=headers)
            self.assertEqual(response.status_code, 200)
            data["preview_hash"] = response.get_json()["preview"]["preview_hash"]
            response = self.client.post("/api/task-planner/series", json=data, headers=headers)
            self.assertEqual(response.status_code, 201)
            created = response.get_json()["series"]
            response = self.client.post("/api/task-planner/series", json=data, headers=headers)
            self.assertEqual(response.get_json()["series"]["id"], created["id"])
            line_url = f"/api/task-planner/series/{created['id']}"
            self.assertEqual(len(self.client.get(line_url).get_json()["entries"]), 7)
            self.assertEqual(len(self.client.get(f"/api/task-planner/entries?from=2026-10-29&to=2026-11-04&series_id={created['id']}").get_json()["entries"]), 7)
            response = self.client.post(line_url + "/confirm", json={"version": created["version"]}, headers=headers)
            self.assertEqual(response.status_code, 200)
            confirmed = response.get_json()["series"]
            self.assertEqual(confirmed["status_counts"], {"ready": 7})
            self.assertEqual(self.client.post(line_url + "/cancel", json={"version": created["version"]}, headers=headers).status_code, 409)
            self.assertEqual(self.client.post(line_url + "/cancel", json={"version": confirmed["version"]}, headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/task-planner/series-sources?subject=reading&source_scope=cambridge:10").status_code, 200)
        self.assertEqual(Task.query.count(), 0)
        self.assertFalse(self.network_mock.called)
