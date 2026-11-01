"""Automatic allocation consumes fresh work without changing frozen plans."""

import copy
import json
import unittest
import uuid
from datetime import timedelta

from models import StudentProfile, Task, db
from models_task_planner import TaskPlannerEntry, TaskPlannerSeries
from services import task_planner as planner
from services import task_planner_resources as resources
from services import task_planner_series as series
from tests import test_task_planner_weekly as weekly_tests
from tests.test_task_planner import NOW


class TaskPlannerAutoSkipTest(unittest.TestCase):
    def setUp(self):
        self.fx = weekly_tests.TaskPlannerWeeklyTest()
        self.fx.setUp()
        self.profile = db.session.get(StudentProfile, self.fx.student_id)

    def tearDown(self):
        self.fx.tearDown()

    def payload(self, kind="dictation", **changes):
        data = {"student_id": self.fx.student_id, "name": "自动排除测试", "kind": kind,
                "start_date": NOW.date().isoformat(), "end_date": NOW.date().isoformat(),
                "weekday_counts": [1] * 7, "wait_for_previous": False, "skip_assigned": True,
                "planned_minutes": 20, "note": "", "request_key": str(uuid.uuid4()),
                "selection": {"book_id": self.fx.book_id, "word_start": 1, "vocabulary_goal": "reading"}}
        if kind != "dictation":
            data.update(source_scopes=["cambridge:10"], start_resource_id="ielts10_test1_reading:1",
                        selection={"passage_number": 1})
        data.update(changes)
        return data

    def preview(self, data):
        return series.preview_series(data, self.fx.staff_id, now=NOW)

    def task(self, **changes):
        data = {"student_name": self.profile.full_name, "date": (NOW - timedelta(days=1)).date().isoformat(),
                "category": "基础-翻译句子练习", "detail": "历史合成任务", "status": "done",
                "created_by": self.fx.staff_id}
        data.update(changes)
        task = Task(**data)
        db.session.add(task)
        db.session.commit()
        return task

    def group_request(self):
        groups = series._source_groups("reading", "all")
        first = groups[0]["question_group_id"]
        return self.payload("question_type", selection={"subject": "reading", "standard_type": "all"},
                            source_scope="cambridge:10", start_group_id=first), groups

    def group_task(self, group_id, **changes):
        prepared = resources.prepare_resource("question_type", {
            "subject": "reading", "standard_type": "all", "group_ids": [group_id], "pace": "training",
        })
        return self.task(grading_mode="question_type_practice", question_ids=json.dumps(prepared["snapshot"]),
                         status="pending", **changes)

    def test_words_skip_history_and_ready_ranges_but_keep_drafts_and_other_students(self):
        self.task(dictation_book_id=self.fx.book_id, dictation_word_start=2, dictation_word_end=3)
        self.task(student_name="合成学生乙", dictation_book_id=self.fx.book_id,
                  dictation_word_start=1, dictation_word_end=1)
        self.fx.ready(selection={"book_id": self.fx.book_id, "word_start": 5, "word_end": 5,
                                 "vocabulary_goal": "reading"})
        self.fx.draft(selection={"book_id": self.fx.book_id, "word_start": 1, "word_end": 1,
                                 "vocabulary_goal": "reading"})
        before = (Task.query.count(), TaskPlannerEntry.query.count())
        preview = self.preview(self.payload(weekday_counts=[3] * 7))
        self.assertEqual([(r["selection"]["word_start"], r["selection"]["word_end"]) for r in preview["rows"]],
                         [(1, 1), (4, 4), (6, 6)])
        self.assertEqual(preview["totals"]["units"], 3)
        self.assertEqual(len(preview["skipped"]), 3)
        self.assertEqual((Task.query.count(), TaskPlannerEntry.query.count()), before)

    def test_cancelled_task_and_cancelled_arrangement_release_content(self):
        task = self.task(dictation_book_id=self.fx.book_id, dictation_word_start=1, dictation_word_end=2)
        task.cancelled_at = NOW.replace(tzinfo=None)
        task.status = Task.STATUS_CANCELLED
        db.session.commit()
        entry = self.fx.ready()
        planner.cancel_entry(entry.id, entry.version, self.fx.staff_id)
        db.session.commit()
        preview = self.preview(self.payload(weekday_counts=[2] * 7))
        self.assertEqual(preview["rows"][0]["selection"]["word_start"], 1)
        self.assertEqual(preview["rows"][0]["selection"]["word_end"], 2)
        self.assertFalse(preview["skipped"])

    def test_blocked_and_failed_arrangements_still_occupy_content(self):
        for state, number in (("blocked", 1), ("failed", 2)):
            entry = self.fx.draft(selection={"book_id": self.fx.book_id, "word_start": number,
                                            "word_end": number, "vocabulary_goal": "reading"})
            entry.status = state
            db.session.commit()
        self.assertEqual(self.preview(self.payload())["rows"][0]["selection"]["word_start"], 3)

    def test_earlier_unfinished_question_groups_are_strictly_skipped(self):
        request, groups = self.group_request()
        self.group_task(groups[0]["question_group_id"])
        preview = self.preview(request)
        self.assertEqual(preview["rows"][0]["selection"]["group_ids"], [groups[1]["question_group_id"]])
        self.assertEqual(len(preview["skipped"]), 1)
        # The old explicit reassignment route remains unchanged without the flag.
        request.pop("skip_assigned")
        self.assertEqual(self.preview(request)["rows"][0]["selection"]["group_ids"], [groups[0]["question_group_id"]])

    def test_group_identity_survives_changed_type_label(self):
        request, groups = self.group_request()
        task = self.group_task(groups[0]["question_group_id"])
        snapshot = json.loads(task.question_ids)
        snapshot["standard_type"] = "legacy-label"
        snapshot.pop("group_refs", None)
        task.question_ids = json.dumps(snapshot)
        db.session.commit()
        self.assertEqual(self.preview(request)["rows"][0]["selection"]["group_ids"], [groups[1]["question_group_id"]])

    def test_partial_reading_history_skips_entire_same_passage(self):
        self.task(reading_test_id="ielts10_test1_reading", reading_passage_number=1,
                  question_ids=json.dumps(["q1"]))
        preview = self.preview(self.payload("reading_passage"))
        self.assertEqual(preview["rows"][0]["selection"]["test_id"], "ielts10_test2_reading")

    def test_reading_whole_test_skips_any_previously_assigned_passage(self):
        self.task(reading_test_id="ielts10_test1_reading", reading_passage_number=2)
        preview = self.preview(self.payload("reading_test", selection={}, start_resource_id="ielts10_test1_reading:all"))
        self.assertEqual({r["kind"] for r in preview["rows"]}, {"reading_passage"})
        self.assertEqual({r["selection"]["test_id"] for r in preview["rows"]}, {"ielts10_test2_reading"})
        self.assertEqual([r["selection"]["passage_number"] for r in preview["rows"]], [1, 2, 3])
        self.assertEqual(preview["totals"], {"days": 1, "units": 1, "questions": 40, "tasks": 3})

    def test_completed_whole_listening_excludes_fixed_part(self):
        self.task(listening_resource_type="cambridge_test", listening_exercise_id="ielts10_test1")
        preview = self.preview(self.payload("listening_test", selection={"section_number": 1},
                                            start_resource_id="ielts10_test1:1"))
        self.assertEqual(preview["rows"][0]["selection"], {"test_id": "ielts10_test2", "section_number": 1})

    def test_insufficient_fresh_content_does_not_save_partial_plan(self):
        self.task(dictation_book_id=self.fx.book_id, dictation_word_start=1, dictation_word_end=80)
        with self.assertRaisesRegex(planner.TaskPlannerError, "剩余可用内容不足"):
            self.preview(self.payload())
        self.assertEqual(TaskPlannerEntry.query.count(), 0)
        self.assertEqual(TaskPlannerSeries.query.count(), 0)

    def test_new_history_between_preview_and_save_requires_fresh_preview(self):
        data = self.payload()
        data["preview_hash"] = self.preview(data)["preview_hash"]
        self.task(dictation_book_id=self.fx.book_id, dictation_word_start=1, dictation_word_end=1)
        with self.assertRaises(planner.TaskPlannerError) as error:
            series.create_series(data, self.fx.staff_id, now=NOW)
        self.assertEqual(error.exception.code, "preview_changed")
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_confirm_rechecks_strict_history_without_replacing_frozen_questions(self):
        data, groups = self.group_request()
        row = self.fx.save(data)
        self.group_task(groups[0]["question_group_id"])
        with self.assertRaises(planner.TaskPlannerError):
            series.confirm_series(row.id, row.version, self.fx.staff_id, now=NOW)
        self.assertEqual({entry.status for entry in self.fx.entries(row)}, {"draft"})
        self.assertEqual(json.loads(self.fx.entries(row)[0].selection_json)["group_ids"], [groups[0]["question_group_id"]])

    def test_publish_rechecks_strict_history_and_blocks_without_replacing(self):
        data, groups = self.group_request()
        row = self.fx.save(data)
        series.confirm_series(row.id, row.version, self.fx.staff_id, now=NOW)
        self.group_task(groups[0]["question_group_id"])
        entry = self.fx.entries(row)[0]
        result = planner.publish_entry(entry.id, self.fx.staff_id, entry.version, now=NOW)
        self.assertEqual(result.status, "blocked")
        self.assertIsNone(result.published_task_id)
        self.assertEqual(json.loads(result.selection_json)["group_ids"], [groups[0]["question_group_id"]])

    def test_within_batch_whole_and_partial_keep_native_units(self):
        data = self.fx.payload(end_date="2026-11-08")
        preview = self.preview(data)
        self.assertEqual([r["unit_count"] for r in preview["rows"]], [1, 1, 1, 1, 0, 0])
        self.assertEqual({r["reason"] for r in preview["skipped"]}, {"本批安排已使用"})
        row = self.fx.save(data)
        series.confirm_series(row.id, row.version, self.fx.staff_id, now=NOW)
        self.assertEqual({entry.status for entry in self.fx.entries(row)}, {"ready"})

    def test_disable_skip_keeps_duplicate_protection(self):
        self.task(dictation_book_id=self.fx.book_id, dictation_word_start=1, dictation_word_end=1)
        with self.assertRaises(planner.TaskPlannerError):
            self.preview(self.payload(skip_assigned=False))
        data = copy.deepcopy(self.fx.payload(end_date="2026-11-08"))
        data["skip_assigned"] = False
        with self.assertRaises(planner.TaskPlannerError):
            self.preview(data)
