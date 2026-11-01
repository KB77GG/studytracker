"""Multi-volume vocabulary scheduling against synthetic books and students."""

import copy
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from models import DictationBook, DictationWord, Task, VocabularyTaskSettlement, db
from models_task_planner import TaskPlannerEntry, TaskPlannerEvent, TaskPlannerSeries
from services import task_planner as planner
from services import task_planner_series as series
from services.task_planner_vocabulary import book_sort_key
from tests.test_task_planner import NOW, PlannerFixture


class TaskPlannerVocabularyTest(PlannerFixture):
    def setUp(self):
        super().setUp()
        self.day10 = self.book("四级单词 Day10", [1, 2, 3, 4])
        self.day2 = self.book("四级单词 Day2", [1, 3, 7, 9])
        self.day1 = self.book("四级单词 Day1", [1, 2, 3])
        self.ids = [self.day10, self.day1, self.day2]

    def book(self, title, sequences):
        book = DictationBook(title=title, created_by=self.staff_id, word_count=999)
        db.session.add(book)
        db.session.flush()
        db.session.add_all([
            DictationWord(book_id=book.id, sequence=value, word=f"word{value}", translation=f"含义{value}")
            for value in sequences
        ])
        db.session.commit()
        return book.id

    def data(self, **changes):
        payload = {
            "name": "四级分册连续安排", "student_id": self.student_id,
            "kind": "dictation", "start_date": NOW.date().isoformat(),
            "end_date": (NOW + timedelta(days=1)).date().isoformat(),
            "weekday_counts": [3] * 7,
            "selection": {"book_ids": self.ids, "book_id": self.day1,
                          "word_start": 2, "vocabulary_goal": "reading"},
            "planned_minutes": 15, "wait_for_previous": False,
            "request_key": str(uuid.uuid4()),
        }
        payload.update(changes)
        return payload

    def create(self, data=None):
        data = copy.deepcopy(data or self.data())
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        return series.create_series(data, self.staff_id, now=NOW)

    def entries(self, line):
        return [db.session.get(TaskPlannerEntry, item.entry_id) for item in series._items(line.id)]

    def test_daily_quota_crosses_volumes_and_uses_actual_rows_with_gaps(self):
        result = series.preview_series(self.data(), self.staff_id, now=NOW)
        self.assertEqual(result["ordered_book_ids"], [self.day1, self.day2, self.day10])
        self.assertEqual(result["totals"], {"days": 2, "units": 6, "questions": 0})
        self.assertEqual(result["quota_unit"], "词")
        self.assertEqual([
            (row["target_date"], row["selection"]["book_id"], row["selection"]["word_start"],
             row["selection"]["word_end"], row["unit_count"])
            for row in result["rows"]
        ], [("2026-10-29", self.day1, 2, 3, 2), ("2026-10-29", self.day2, 1, 1, 1),
            ("2026-10-30", self.day2, 3, 9, 3)])
        self.assertEqual((TaskPlannerSeries.query.count(), TaskPlannerEntry.query.count(), Task.query.count()), (0, 0, 0))
        self.assertTrue(all("book_ids" not in row["selection"] for row in result["rows"]))

    def test_start_volume_and_explicit_selection_do_not_pick_unselected_books(self):
        data = self.data(selection={"book_ids": [self.day10, self.day1], "book_id": self.day1,
                                    "word_start": 3}, end_date="2026-10-29")
        rows = series.preview_series(data, self.staff_id, now=NOW)["rows"]
        self.assertEqual([row["selection"]["book_id"] for row in rows], [self.day1, self.day10])
        data["selection"] = {"book_ids": self.ids, "book_id": self.day2, "word_start": 3}
        rows = series.preview_series(data, self.staff_id, now=NOW)["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["selection"]["book_id"], self.day2)
        self.assertEqual((rows[0]["selection"]["word_start"], rows[0]["selection"]["word_end"]), (3, 9))

    def test_book_titles_have_numeric_case_insensitive_order_and_stable_ties(self):
        ids = [self.book(title, [1]) for title in ("wl库 1-10", "WL库 1-2", "wl库 1-1", "WL库 1-2")]
        books = DictationBook.query.filter(DictationBook.id.in_(ids)).all()
        self.assertEqual([book.id for book in sorted(books, key=book_sort_key)], [ids[2], ids[1], ids[3], ids[0]])

    def test_rest_days_weekend_quota_share_one_cross_volume_cursor(self):
        data = self.data(end_date="2026-11-01", weekday_counts=[0, 0, 0, 1, 0, 3, 4])
        result = series.preview_series(data, self.staff_id, now=NOW)
        self.assertEqual(result["totals"]["days"], 3)
        self.assertEqual(result["totals"]["units"], 8)
        totals = {}
        for row in result["rows"]:
            totals[row["target_date"]] = totals.get(row["target_date"], 0) + row["unit_count"]
        self.assertEqual(totals, {"2026-10-29": 1, "2026-10-31": 3, "2026-11-01": 4})
        self.assertEqual(result["rows"][-1]["selection"]["book_id"], self.day10)

    def test_invalid_book_choices_and_missing_start_do_not_write(self):
        invalid = [None, [], "1,2", [self.day1, self.day1], [self.day1, str(self.day1)],
                   [True], [1.5], [0], [999999], list(range(1, 102))]
        for ids in invalid:
            data = self.data(selection={"book_ids": ids, "book_id": self.day1, "word_start": 1})
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                series.preview_series(data, self.staff_id, now=NOW)
        for selection in (
            {"book_ids": [self.day1], "book_id": self.day2, "word_start": 1},
            {"book_ids": [self.day2], "book_id": self.day2, "word_start": 2},
            {"book_ids": [self.day1], "book_id": self.day1, "word_start": True},
        ):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                series.preview_series(self.data(selection=selection), self.staff_id, now=NOW)
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_empty_deleted_disabled_and_duplicate_sequence_books_are_rejected(self):
        empty = self.book("空分册", [])
        duplicate = self.book("重复词序", [1, 1, 2])
        invalid_sequence = self.book("无效词序", [0, 1, 2])
        disabled = self.book("停用分册", [1, 2, 3])
        deleted = self.book("删除分册", [1, 2, 3])
        db.session.get(DictationBook, disabled).is_active = False
        db.session.get(DictationBook, deleted).is_deleted = True
        db.session.commit()
        for book_id in (empty, duplicate, invalid_sequence, disabled, deleted):
            selection = {"book_ids": [self.day1, book_id], "book_id": self.day1, "word_start": 1}
            with self.subTest(book_id=book_id), self.assertRaises(ValueError):
                series.preview_series(self.data(selection=selection), self.staff_id, now=NOW)
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_insufficient_total_rejects_instead_of_using_cached_count_or_partial_save(self):
        data = self.data(weekday_counts=[6] * 7)
        with self.assertRaisesRegex(ValueError, "仅有10词.*需要12词.*缺少2词"):
            series.preview_series(data, self.staff_id, now=NOW)
        with self.assertRaises(ValueError):
            series.create_series(dict(data, preview_hash="stale"), self.staff_id, now=NOW)
        self.assertEqual((TaskPlannerSeries.query.count(), TaskPlannerEntry.query.count()), (0, 0))

    def test_full_month_can_continue_through_small_daily_volumes(self):
        ids = [self.book(f"Upper Intermediate Day{day}", list(range(1, 51))) for day in range(1, 22)]
        result = series.preview_series(self.data(
            selection={"book_ids": ids[::-1], "book_id": ids[0], "word_start": 1},
            weekday_counts=[30] * 7, end_date="2026-11-27",
        ), self.staff_id, now=NOW)
        self.assertEqual(result["totals"], {"days": 30, "units": 900, "questions": 0})
        self.assertEqual(result["rows"][-1]["selection"]["book_id"], ids[17])
        self.assertEqual(result["rows"][-1]["selection"]["word_end"], 50)

    def test_legacy_single_book_payload_and_request_hash_are_unchanged(self):
        data = self.data(selection={"book_id": self.book_id, "word_start": 1})
        preview = series.preview_series(data, self.staff_id, now=NOW)
        self.assertNotIn("ordered_book_ids", preview)
        self.assertEqual(len(preview["rows"]), 2)
        data["preview_hash"] = preview["preview_hash"]
        row = series.create_series(data, self.staff_id, now=NOW)
        legacy_fields = [key for key in series.REQUEST_FIELDS if key not in series.NEW_REQUEST_FIELDS]
        self.assertEqual(row.request_hash, series._digest({"actor_id": self.staff_id,
                         "data": {key: data.get(key) for key in legacy_fields}}))
        self.assertEqual(series.create_series(data, self.staff_id, now=NOW).id, row.id)

    def test_replay_and_cross_volume_native_task_contract_and_cancel(self):
        data = self.data()
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        line = series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual(series.create_series(data, self.staff_id, now=NOW).id, line.id)
        with self.assertRaisesRegex(ValueError, "请求标识"):
            series.create_series(dict(data, selection=dict(data["selection"], book_ids=[self.day1, self.day2])),
                                 self.staff_id, now=NOW)
        series.confirm_series(line.id, line.version, self.staff_id, now=NOW)
        first, second, third = self.entries(line)
        for entry in (first, second):
            self.assertEqual(planner.publish_entry(entry.id, self.staff_id, entry.version, now=NOW).status, "published")
        tasks = Task.query.order_by(Task.id).all()
        self.assertEqual([(task.dictation_book_id, task.dictation_word_start, task.dictation_word_end) for task in tasks],
                         [(self.day1, 2, 3), (self.day2, 1, 1)])
        self.assertTrue(all(task.plan_item for task in tasks))
        self.assertNotEqual(planner.entry_payload(first)["content_labels"], planner.entry_payload(second)["content_labels"])
        series.cancel_series(line.id, line.version, self.staff_id, now=NOW)
        self.assertEqual([entry.status for entry in self.entries(line)], ["published", "published", "cancelled"])
        self.assertTrue(all(task.cancelled_at is None for task in tasks))
        self.assertEqual(third.published_task_id, None)
        self.assertFalse(self.network_mock.called)

    def test_same_day_volumes_do_not_wait_but_next_day_requires_both_settlements(self):
        line = self.create(self.data(wait_for_previous=True))
        series.confirm_series(line.id, line.version, self.staff_id, now=NOW)
        first, second, third = self.entries(line)
        for entry in (first, second):
            self.assertEqual(planner.publish_entry(entry.id, self.staff_id, entry.version, now=NOW).status, "published")
        db.session.add(VocabularyTaskSettlement(student_id=self.user_id, task_id=first.published_task_id,
                       queue_token="volume-first", result_json="{}", settled_at=NOW.replace(tzinfo=None)))
        db.session.commit()
        with self.assertRaisesRegex(ValueError, "上一学习日.*未完成"):
            planner._series_prerequisite(third, planner._student(self.student_id))
        db.session.add(VocabularyTaskSettlement(student_id=self.user_id, task_id=second.published_task_id,
                       queue_token="volume-second", result_json="{}", settled_at=NOW.replace(tzinfo=None)))
        db.session.commit()
        self.assertEqual(planner.publish_entry(third.id, self.staff_id, third.version,
                         now=NOW + timedelta(days=1)).status, "published")

    def test_scope_or_resource_change_invalidates_preview_and_confirmation(self):
        data = self.data()
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        data["selection"]["book_ids"] = [self.day1, self.day2]
        with self.assertRaisesRegex(ValueError, "重新预览"):
            series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual(TaskPlannerSeries.query.count(), 0)
        line = self.create()
        db.session.get(DictationBook, self.day2).is_active = False
        db.session.commit()
        with self.assertRaises(ValueError):
            series.confirm_series(line.id, line.version, self.staff_id, now=NOW)
        self.assertEqual({entry.status for entry in self.entries(line)}, {"draft"})
        self.assertEqual(TaskPlannerEvent.query.filter_by(action="confirm").count(), 0)

    def test_split_creation_rolls_back_all_volumes_on_failure(self):
        data = self.data()
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        original, calls = planner._event, []

        def fail_second(*args, **kwargs):
            calls.append(args)
            if len(calls) == 2:
                raise RuntimeError("synthetic split failure")
            return original(*args, **kwargs)

        with patch.object(planner, "_event", side_effect=fail_second), self.assertRaises(RuntimeError):
            series.create_series(data, self.staff_id, now=NOW)
        self.assertEqual((TaskPlannerSeries.query.count(), TaskPlannerEntry.query.count(), TaskPlannerEvent.query.count()), (0, 0, 0))

    def test_api_preserves_auth_and_saves_frozen_single_book_selections(self):
        url = "/api/task-planner/series/preview"
        self.assertEqual(self.client.post(url, json=self.data()).status_code, 401)
        self.login()
        headers = self.csrf_headers()
        with patch.object(planner, "beijing_now", return_value=NOW):
            data = self.data()
            response = self.client.post(url, json=data, headers=headers)
            self.assertEqual(response.status_code, 200)
            data["preview_hash"] = response.get_json()["preview"]["preview_hash"]
            saved = self.client.post("/api/task-planner/series", json=data, headers=headers)
            self.assertEqual(saved.status_code, 201)
            line_id = saved.get_json()["series"]["id"]
            result = self.client.get(f"/api/task-planner/series/{line_id}").get_json()
            self.assertEqual(len(result["entries"]), 3)
            self.assertTrue(all("book_ids" not in entry["selection"] for entry in result["entries"]))
            definition = json.loads(db.session.get(TaskPlannerSeries, line_id).definition_json)
            self.assertEqual(definition["ordered_book_ids"], [self.day1, self.day2, self.day10])
