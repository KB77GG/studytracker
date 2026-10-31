"""Synthetic integration tests for planner resource validation and Task creation."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from models import (
    DictationBook,
    DictationWord,
    PlanItem,
    StudentProfile,
    StudyPlan,
    Task,
    User,
    db,
)
from services import task_planner_resources as resources
from services.question_type_practice import snapshot_from_task


class TaskPlannerResourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in ("reading_tests", "reading_jijing", "listening_tests", "listening"):
            (self.root / "static" / name).mkdir(parents=True)
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="planner-synthetic",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TASK_PLANNER_ROOT=str(self.root),
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.staff = User(
            username="resource-staff", password_hash="test", role="assistant"
        )
        self.student = StudentProfile(full_name="Synthetic Student")
        db.session.add_all([self.staff, self.student])
        db.session.flush()
        self.book = DictationBook(title="Synthetic Words", created_by=self.staff.id)
        db.session.add(self.book)
        db.session.flush()
        for sequence in (1, 2, 4, 5):
            db.session.add(
                DictationWord(
                    book_id=self.book.id,
                    sequence=sequence,
                    word=f"word{sequence}",
                    translation=f"meaning{sequence}",
                )
            )
        db.session.commit()
        self.reading = {
            "id": "ielts10_test1_reading",
            "title": "Reading Sample",
            "passages": [],
        }
        for number in (1, 2):
            self.reading["passages"].append(
                {
                    "passage": number,
                    "content": {
                        "paragraphs": [
                            {"text": "The tree is green and grows beside a lake."}
                        ]
                    },
                    "groups": [self.group(f"g{number}", number)],
                }
            )
        self.reading_path = (
            self.root / "static/reading_tests/ielts10_test1_reading.json"
        )
        self.write(self.reading_path, self.reading)
        listening = {
            "id": "ielts10_test1",
            "title": "Listening Sample",
            "sections": [
                {
                    "section": 1,
                    "audio": "sample.mp3",
                    "groups": [
                        {
                            "group_id": "l1",
                            "type": 4,
                            "desc": "Complete the sentences.",
                            "questions": [
                                {
                                    "id": "l1",
                                    "number": 1,
                                    "title": "The name is ____.",
                                    "answer": "Alex",
                                    "start": 0,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        self.write(self.root / "static/listening_tests/ielts10_test1.json", listening)
        (self.root / "static/listening/sample.mp3").write_bytes(b"synthetic-audio")
        self.intensive_path = self.root / "static/listening/ielts10_test1_s1.json"
        self.write(
            self.intensive_path,
            {
                "id": "ielts10_test1_s1",
                "title": "Intensive Sample",
                "audio": "sample.mp3",
                "parts": [
                    {
                        "name": "Part 1",
                        "segments": [
                            {"id": 1, "start": 0, "end": 2, "text": "Hello world."}
                        ],
                    }
                ],
            },
        )
        resources._cached_groups.cache_clear()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.tmp.cleanup()

    @staticmethod
    def write(path, payload):
        path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def group(group_id, number):
        return {
            "group_id": group_id,
            "type": 1,
            "desc": "TRUE FALSE NOT GIVEN",
            "questions": [
                {
                    "id": f"q{number}",
                    "number": number,
                    "title": "The tree is green.",
                    "answer": "TRUE",
                    "options": [
                        {"key": key, "text": key}
                        for key in ("TRUE", "FALSE", "NOT GIVEN")
                    ],
                }
            ],
        }

    def words(self, start=1, end=2):
        return {
            "book_id": self.book.id,
            "word_start": start,
            "word_end": end,
            "vocabulary_goal": "reading",
            "dictation_mode": "audio_to_en",
            "dictation_order": "sequence",
        }

    def specialty(self, passage=1, subject="reading"):
        return {
            "subject": subject,
            "standard_type": "judgment" if subject == "reading" else "completion",
            "group_ids": (
                [f"reading:ielts10_test1_reading:{passage}:g{passage}"]
                if subject == "reading"
                else ["listening:ielts10_test1:1:l1"]
            ),
            "pace": "training",
        }

    def create(self, kind, selection, key="task-test"):
        prepared = resources.prepare_resource(kind, selection)
        task = resources.create_resource_task(
            self.student, prepared, self.staff.id, "2026-11-01", 20, "Practice", key
        )
        return prepared, task

    def test_catalog_is_bounded_answer_free_and_types_are_available(self):
        result = resources.catalog("question_type", {"subject": "reading", "limit": 1})
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["items"]), 1)
        self.assertIn("judgment", [row["id"] for row in result["types"]])
        self.assertNotIn("answer", json.dumps(result))
        second = resources.catalog(
            "question_type", {"subject": "reading", "limit": 1, "offset": 1}
        )
        self.assertNotEqual(result["items"][0]["id"], second["items"][0]["id"])
        self.assertEqual(
            resources.catalog("question_type", {"query": "missing"})["total"], 0
        )

    def test_question_selection_must_be_explicit_complete_and_correct_type(self):
        for changes in (
            {"group_ids": []},
            {"group_ids": ["missing"]},
            {"standard_type": "completion"},
            {"group_ids": [self.specialty()["group_ids"][0]] * 2},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                resources.prepare_resource(
                    "question_type", {**self.specialty(), **changes}
                )

    def test_question_snapshot_ignores_client_forgery_and_creates_matching_task(self):
        selection = {**self.specialty(), "snapshot": {"answer": "forged"}}
        prepared, task = self.create("question_type", selection)
        snapshot = snapshot_from_task(task)
        self.assertEqual(snapshot["group_ids"], selection["group_ids"])
        self.assertEqual(
            snapshot["snapshot_hash"], prepared["snapshot"]["snapshot_hash"]
        )
        self.assertEqual(task.plan_item.resource_type, "question_type_practice")
        self.assertEqual(task.plan_item.plan.student_id, self.student.id)
        self.assertEqual(task.plan_item.plan.plan_date.isoformat(), "2026-11-01")
        self.assertNotIn("forged", task.question_ids)

    def test_listening_specialty_requires_available_audio_even_after_cached_catalog(
        self,
    ):
        resources.catalog("question_type", {"subject": "listening"})
        prepared = resources.prepare_resource(
            "question_type", self.specialty(subject="listening")
        )
        self.assertEqual(prepared["snapshot"]["subject"], "listening")
        (self.root / "static/listening/sample.mp3").unlink()
        with self.assertRaises(ValueError):
            resources.revalidate_resource(prepared)

    def test_resource_changes_and_tampered_prepared_are_rejected(self):
        prepared = resources.prepare_resource("question_type", self.specialty())
        damaged = copy.deepcopy(prepared)
        damaged["snapshot"]["question_count"] = 999
        with self.assertRaisesRegex(ValueError, "快照损坏"):
            resources.revalidate_resource(damaged)
        self.reading["passages"][0]["groups"][0]["questions"][0]["answer"] = "FALSE"
        self.write(self.reading_path, self.reading)
        with self.assertRaisesRegex(ValueError, "已变化"):
            resources.revalidate_resource(prepared)

    def test_specialty_hidden_or_offline_sources_cannot_be_selected(self):
        prepared = resources.prepare_resource("question_type", self.specialty())
        self.reading["hidden_from_catalog"] = True
        self.write(self.reading_path, self.reading)
        self.assertEqual(resources.catalog("question_type")["total"], 0)
        with self.assertRaises(ValueError):
            resources.revalidate_resource(prepared)
        self.reading.pop("hidden_from_catalog")
        self.write(self.reading_path, self.reading)
        self.write(
            self.reading_path.parent / "offline_tests.json",
            {
                "tests": [{"id": "ielts10_test1_reading", "status": "offline"}],
            },
        )
        self.assertEqual(resources.catalog("question_type")["total"], 0)
        with self.assertRaises(ValueError):
            resources.revalidate_resource(prepared)

    def test_reading_passage_creation_has_live_consumer_fields(self):
        prepared, task = self.create(
            "reading_passage", {"test_id": "ielts10_test1_reading", "passage_number": 2}
        )
        self.assertEqual(task.reading_test_id, "ielts10_test1_reading")
        self.assertEqual(task.reading_passage_number, 2)
        self.assertEqual(task.grading_mode, "reading_test")
        self.assertTrue(task.reading_access_token)
        metadata = json.loads(task.plan_item.resource_metadata)
        self.assertEqual(metadata["reading_passage_number"], 2)
        self.assertEqual(task.plan_item.access_token, task.reading_access_token)
        self.assertEqual(prepared["coverage_units"][0]["unit_number"], 2)

    def test_reading_rejects_bad_path_unknown_passage_hidden_and_offline(self):
        for selection in (
            {"test_id": "../private", "passage_number": 1},
            {"test_id": "ielts10_test1_reading", "passage_number": 99},
        ):
            with self.assertRaises(ValueError):
                resources.prepare_resource("reading_passage", selection)
        self.reading["hidden_from_catalog"] = True
        self.write(self.reading_path, self.reading)
        self.assertEqual(resources.catalog("reading_passage")["total"], 0)
        with self.assertRaises(ValueError):
            resources.prepare_resource(
                "reading_passage",
                {"test_id": "ielts10_test1_reading", "passage_number": 1},
            )
        self.reading.pop("hidden_from_catalog")
        self.write(self.reading_path, self.reading)
        self.write(
            self.reading_path.parent / "offline_tests.json",
            {"tests": [{"id": "ielts10_test1_reading", "status": "offline"}]},
        )
        self.assertEqual(resources.catalog("reading_passage")["total"], 0)

    def test_jijing_reading_has_existing_category_and_offline_policy(self):
        source = copy.deepcopy(self.reading)
        source.update(id="reading_jijing_1_test_1", source="idictation_reading_jijing")
        self.write(
            self.root / "static/reading_jijing/reading_jijing_1_test_1.json", source
        )
        _, task = self.create(
            "reading_passage", {"test_id": source["id"], "passage_number": 1}
        )
        self.assertEqual(task.category, "雅思-阅读-ZYZ")

    def test_dictation_range_uses_real_words_and_preserves_metadata(self):
        prepared, task = self.create("dictation", self.words(2, 4))
        self.assertEqual(prepared["metadata"]["word_count"], 2)
        self.assertEqual(task.dictation_word_start, 2)
        self.assertEqual(task.dictation_word_end, 4)
        self.assertEqual(task.vocabulary_goal, "reading")
        self.assertEqual(task.plan_item.resource_id, f"dictation_book:{self.book.id}")
        meta = json.loads(task.plan_item.resource_metadata)
        self.assertEqual(meta["dictation_word_start"], 2)
        self.assertEqual(meta["vocabulary_goal"], "reading")
        self.assertIsNone(task.reading_access_token)
        self.assertIsNone(task.listening_access_token)

    def test_dictation_rejects_inactive_out_of_range_empty_range_and_invalid_modes(
        self,
    ):
        for values in (
            self.words(1, 6),
            self.words(3, 3),
            self.words(4, 2),
            {**self.words(), "word_start": True},
            {**self.words(), "word_end": 2.5},
            {**self.words(), "vocabulary_goal": "fake"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                resources.prepare_resource("dictation", values)
        prepared = resources.prepare_resource("dictation", self.words())
        self.book.is_active = False
        db.session.flush()
        self.assertEqual(resources.catalog("dictation")["items"], [])
        with self.assertRaises(ValueError):
            resources.revalidate_resource(prepared)

    def test_dictation_changed_word_contents_rejected(self):
        prepared = resources.prepare_resource("dictation", self.words())
        word = DictationWord.query.filter_by(book_id=self.book.id, sequence=1).one()
        word.translation = "changed"
        db.session.flush()
        with self.assertRaisesRegex(ValueError, "已变化"):
            resources.revalidate_resource(prepared)

    def test_intensive_requires_registered_resource_and_audio(self):
        prepared, task = self.create(
            "intensive",
            {"exercise_id": "ielts10_test1_s1", "training_mode": "challenge"},
        )
        self.assertEqual(task.listening_training_mode, "challenge")
        self.assertEqual(task.listening_resource_type, "intensive")
        self.assertEqual(task.plan_item.resource_type, "intensive_listening")
        self.assertEqual(
            json.loads(task.plan_item.resource_metadata)["listening_training_mode"],
            "challenge",
        )
        self.assertTrue(task.listening_access_token)
        self.assertEqual(resources.catalog("intensive")["total"], 1)
        with self.assertRaises(ValueError):
            resources.prepare_resource(
                "intensive",
                {"exercise_id": "ielts10_test1_s1", "training_mode": "free"},
            )
        (self.root / "static/listening/sample.mp3").unlink()
        with self.assertRaises(ValueError):
            resources.revalidate_resource(prepared)
        self.assertEqual(resources.catalog("intensive")["total"], 0)

    def test_create_only_flushes_and_no_network_or_notifications(self):
        with patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("network forbidden"),
        ):
            self.create("dictation", self.words())
            self.assertEqual(Task.query.count(), 1)
            self.assertEqual(PlanItem.query.count(), 1)
            db.session.rollback()
            self.assertEqual(Task.query.count(), 0)
            self.assertEqual(PlanItem.query.count(), 0)
            self.assertEqual(StudyPlan.query.count(), 0)

    def test_existing_locked_plan_and_bad_date_are_rejected_without_tasks(self):
        from datetime import date

        db.session.add(
            StudyPlan(
                student_id=self.student.id,
                plan_date=date(2026, 11, 1),
                status=StudyPlan.STATUS_LOCKED,
                created_by=self.staff.id,
            )
        )
        db.session.commit()
        with self.assertRaises(ValueError):
            self.create("question_type", self.specialty())
        with self.assertRaises(ValueError):
            self.create("dictation", self.words())
        self.assertEqual(Task.query.count(), 0)

    def test_overlap_planner_same_kind_and_whole_vs_question_group(self):
        whole1 = resources.prepare_resource(
            "reading_passage", {"test_id": "ielts10_test1_reading", "passage_number": 1}
        )
        whole2 = resources.prepare_resource(
            "reading_passage", {"test_id": "ielts10_test1_reading", "passage_number": 2}
        )
        group1 = resources.prepare_resource("question_type", self.specialty(1))
        group2 = resources.prepare_resource("question_type", self.specialty(2))
        self.assertTrue(resources.resource_overlap(whole1, group1))
        self.assertTrue(resources.resource_overlap(group1, whole1))
        self.assertFalse(resources.resource_overlap(whole1, group2))
        self.assertFalse(resources.resource_overlap(whole1, whole2))
        self.assertTrue(resources.resource_overlap(group1, group1))
        self.assertFalse(resources.resource_overlap(group1, group2))
        words1 = resources.prepare_resource("dictation", self.words(1, 2))
        words2 = resources.prepare_resource("dictation", self.words(2, 4))
        words3 = resources.prepare_resource("dictation", self.words(4, 5))
        self.assertTrue(resources.resource_overlap(words1, words2))
        self.assertFalse(resources.resource_overlap(words1, words3))

    def test_cross_kind_overlap_against_formal_tasks_and_cancellation(self):
        whole, whole_task = self.create(
            "reading_passage",
            {"test_id": "ielts10_test1_reading", "passage_number": 1},
            "whole",
        )
        group, group_task = self.create("question_type", self.specialty(), "group")
        self.assertTrue(resources.overlaps_task(group, whole_task))
        self.assertTrue(resources.overlaps_task(whole, group_task))
        other = resources.prepare_resource("question_type", self.specialty(2))
        self.assertFalse(resources.overlaps_task(other, whole_task))
        whole_task.status = Task.STATUS_CANCELLED
        self.assertFalse(resources.overlaps_task(group, whole_task))
        # Same-kind policy belongs to validate_publish_conflicts, not this adapter.
        self.assertFalse(resources.overlaps_task(group, group_task))

    def test_publish_idempotency_constraint_and_schema_consistency(self):
        from sqlalchemy.exc import IntegrityError

        self.create("dictation", self.words(), "stable-key")
        db.session.commit()
        with self.assertRaises(IntegrityError):
            self.create("dictation", self.words(4, 5), "stable-key")
        db.session.rollback()
        self.assertEqual(Task.query.count(), 1)
        self.assertEqual(PlanItem.query.count(), 1)

    def test_cache_reuses_index_but_changed_file_is_not_cached(self):
        with patch.object(
            resources, "build_group_index", wraps=resources.build_group_index
        ) as build:
            resources.catalog("question_type")
            prepared = resources.prepare_resource("question_type", self.specialty())
            resources.revalidate_resource(prepared)
            self.assertEqual(build.call_count, 1)
            self.reading["title"] = "New title"
            self.write(self.reading_path, self.reading)
            with self.assertRaises(ValueError):
                resources.revalidate_resource(prepared)
            self.assertEqual(build.call_count, 2)


if __name__ == "__main__":
    unittest.main()
