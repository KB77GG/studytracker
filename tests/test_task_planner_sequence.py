"""File-only catalogs for explicit whole-resource sequences; no production app."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from services import task_planner_resources as resources
from services.task_planner_sequence import sequence_sources


class TaskPlannerSequenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for directory in ("listening", "listening_tests", "reading_tests", "reading_jijing"):
            (self.root / "static" / directory).mkdir(parents=True)
        app = Flask(__name__)
        app.config.update(TESTING=True, TASK_PLANNER_ROOT=str(self.root))
        self.context = app.app_context()
        self.context.push()
        for test_id in (
            "ielts10_test10",
            "ielts10_test2",
            "ielts10_test1",
            "ielts11_test1",
            "jfdr6_test1",
        ):
            self.listening(test_id)
        for test_id in (
            "ielts10_test10_reading",
            "ielts10_test2_reading",
            "ielts10_test1_reading",
            "ielts11_test1_reading",
        ):
            self.reading(test_id)

    def tearDown(self):
        self.context.pop()
        self.tmp.cleanup()

    def write(self, directory, resource_id, payload):
        path = self.root / "static" / directory / f"{resource_id}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def listening(self, test_id):
        source = {"id": test_id, "title": f"Test {test_id}", "sections": []}
        for section in range(1, 5):
            exercise_id = f"{test_id}_s{section}"
            audio = f"{exercise_id}.mp3"
            (self.root / "static/listening" / audio).write_bytes(b"test audio")
            source["sections"].append(
                {
                    "section": section,
                    "audio": audio,
                    "groups": [
                        {
                            "group_id": f"g{section}",
                            "type": 4,
                            "desc": "Complete the sentences.",
                            "questions": [
                                {
                                    "id": f"q{i}",
                                    "number": i,
                                    "title": "The name is ____.",
                                    "answer": "Alex",
                                    "start": 0,
                                }
                                for i in range((section - 1) * 10 + 1, section * 10 + 1)
                            ],
                        }
                    ],
                }
            )
            self.write(
                "listening",
                exercise_id,
                {
                    "id": exercise_id,
                    "title": f"Intensive {exercise_id}",
                    "audio": audio,
                    "parts": [{"segments": [{"id": 1, "text": "Hello", "start": 0, "end": 1}]}],
                },
            )
        self.write("listening_tests", test_id, source)
        return source

    def reading(self, test_id, *, directory="reading_tests", **extra):
        source = {
            "id": test_id,
            "title": f"Reading {test_id}",
            "passages": [
                {
                    "passage": i,
                    "content": {"paragraphs": [{"text": "A complete passage."}]},
                    "groups": [{"questions": [{"id": f"q{i}", "number": i, "answer": "TRUE"}]}],
                }
                for i in range(1, 4)
            ],
            **extra,
        }
        self.write(directory, test_id, source)
        return source

    def test_without_scope_only_returns_all_explicit_book_choices(self):
        result = sequence_sources("listening_test", {"section_number": 1})
        self.assertEqual(result["items"], [])
        self.assertEqual(
            result["sources"],
            [
                {"id": "cambridge:10", "label": "剑雅 10", "count": 3},
                {"id": "cambridge:11", "label": "剑雅 11", "count": 1},
                {"id": "jfdr:6", "label": "9分达人 6", "count": 1},
            ],
        )
        self.assertEqual(sequence_sources("listening_test", {}, [])["items"], [])

    def test_multiple_books_have_natural_order_and_never_include_an_unselected_book(self):
        result = sequence_sources(
            "listening_test", {"section_number": 1}, ["jfdr:6", "cambridge:10"]
        )
        self.assertEqual(
            [row["id"] for row in result["items"]],
            [
                "ielts10_test1:1",
                "ielts10_test2:1",
                "ielts10_test10:1",
                "jfdr6_test1:1",
            ],
        )
        self.assertEqual(len(result["sources"]), 3)
        self.assertTrue(all(row["selection"]["section_number"] == 1 for row in result["items"]))
        self.assertTrue(all(row["question_count"] == 10 for row in result["items"]))

    def test_whole_listening_has_stable_ids_and_forty_question_selections(self):
        result = sequence_sources("listening_test", {"section_number": None}, ["cambridge:10"])
        self.assertEqual(
            [row["id"] for row in result["items"]],
            [
                "ielts10_test1:all",
                "ielts10_test2:all",
                "ielts10_test10:all",
            ],
        )
        self.assertTrue(all(row["question_count"] == 40 for row in result["items"]))
        self.assertTrue(all(row["selection"]["section_number"] is None for row in result["items"]))

    def test_reading_all_passages_or_fixed_passage_follow_test_then_passage_order(self):
        result = sequence_sources("reading_passage", {}, ["cambridge:10"])
        self.assertEqual(len(result["items"]), 9)
        self.assertEqual(
            [row["id"] for row in result["items"][:4]],
            [
                "ielts10_test1_reading:1",
                "ielts10_test1_reading:2",
                "ielts10_test1_reading:3",
                "ielts10_test2_reading:1",
            ],
        )
        fixed = sequence_sources("reading_passage", {"passage_number": "2"}, ["cambridge:10"])
        self.assertEqual(len(fixed["items"]), 3)
        self.assertTrue(all(row["selection"]["passage_number"] == 2 for row in fixed["items"]))
        self.assertTrue(all(row["question_count"] == 1 for row in fixed["items"]))

    def test_intensive_uses_registered_book_section_order_and_preserves_training_mode(self):
        result = sequence_sources(
            "intensive", {"section_number": 1, "training_mode": "challenge"}, ["cambridge:10"]
        )
        self.assertEqual(
            [row["id"] for row in result["items"]],
            [
                "ielts10_test1_s1",
                "ielts10_test2_s1",
                "ielts10_test10_s1",
            ],
        )
        self.assertTrue(
            all(row["selection"]["training_mode"] == "challenge" for row in result["items"])
        )
        self.assertTrue(all(row["segment_count"] == 1 for row in result["items"]))
        self.assertTrue(result["training_modes"])
        full = sequence_sources("intensive", {}, ["cambridge:10"])
        self.assertEqual(len(full["items"]), 12)
        self.assertEqual(
            [row["id"] for row in full["items"][:5]],
            [
                "ielts10_test1_s1",
                "ielts10_test1_s2",
                "ielts10_test1_s3",
                "ielts10_test1_s4",
                "ielts10_test2_s1",
            ],
        )

    def test_recognized_jijing_books_and_unknown_sources_are_bounded(self):
        self.reading(
            "reading_jijing_10_test_78",
            directory="reading_jijing",
            source="idictation_reading_jijing",
            book=10,
            test=78,
        )
        self.reading(
            "reading_jijing_2_test_8",
            directory="reading_jijing",
            source="idictation_reading_jijing",
            book=2,
            test=8,
        )
        self.reading("custom_test10")
        self.reading("custom_test2")
        result = sequence_sources(
            "reading_passage",
            {"passage_number": 1},
            ["reading_jijing:10", "reading_jijing:2", "test:custom_test10", "test:custom_test2"],
        )
        self.assertEqual(
            [row["id"] for row in result["items"]],
            [
                "reading_jijing_2_test_8:1",
                "reading_jijing_10_test_78:1",
                "custom_test2:1",
                "custom_test10:1",
            ],
        )
        self.assertNotIn("all", [source["id"] for source in result["sources"]])

    def test_options_and_scope_lists_are_strict(self):
        for kind, selection, scopes in (
            ("question_type", {}, None),
            ("listening_test", [], None),
            ("listening_test", {"section_number": True}, None),
            ("listening_test", {"section_number": 0}, None),
            ("listening_test", {"section_number": 5}, None),
            ("listening_test", {"section_number": ""}, None),
            ("reading_passage", {"passage_number": 4}, None),
            ("intensive", {"section_number": 1.5}, None),
            ("intensive", {"training_mode": "unknown"}, None),
            ("intensive", {"training_mode": None}, None),
            ("listening_test", {"passage_number": 1}, None),
            ("listening_test", {}, "cambridge:10"),
            ("listening_test", {}, ["cambridge:10", "cambridge:10"]),
            ("listening_test", {}, [None]),
            ("listening_test", {}, ["all"]),
            ("listening_test", {}, ["cambridge:10", "cambridge:999"]),
        ):
            with (
                self.subTest(kind=kind, selection=selection, scopes=scopes),
                self.assertRaises(ValueError),
            ):
                sequence_sources(kind, selection, scopes)

    def test_missing_audio_or_incomplete_test_is_skipped_and_unmatched_scope_errors(self):
        (self.root / "static/listening/ielts11_test1_s2.mp3").unlink()
        self.assertNotIn(
            "cambridge:11", [row["id"] for row in sequence_sources("listening_test", {})["sources"]]
        )
        self.assertEqual(
            len(
                sequence_sources("listening_test", {"section_number": 1}, ["cambridge:11"])["items"]
            ),
            1,
        )
        with self.assertRaisesRegex(ValueError, "部分所选教材"):
            sequence_sources("listening_test", {}, ["cambridge:10", "cambridge:11"])
        self.assertEqual(len(sequence_sources("intensive", {}, ["cambridge:11"])["items"]), 3)

    def test_hidden_offline_and_malformed_resources_do_not_break_other_books(self):
        source = self.listening("ielts11_test1")
        source["hidden_from_catalog"] = True
        self.write("listening_tests", "ielts11_test1", source)
        self.write(
            "listening_tests",
            "offline_tests",
            {"tests": [{"id": "jfdr6_test1", "status": "offline"}]},
        )
        (self.root / "static/listening_tests/broken.json").write_text("bad json")
        sources = sequence_sources("listening_test", {})["sources"]
        self.assertEqual([row["id"] for row in sources], ["cambridge:10"])
        self.assertNotIn(
            "jfdr:6", [row["id"] for row in sequence_sources("intensive", {})["sources"]]
        )
        self.write("reading_tests", "bad_passages", {"passages": [None]})
        self.assertEqual(len(sequence_sources("reading_passage", {}, ["cambridge:10"])["items"]), 9)

    def test_duplicate_paths_are_not_repeated_and_each_candidate_is_prepared_once(self):
        source = self.reading("ielts10_test1_reading")
        self.write("reading_jijing", "ielts10_test1_reading", copy.deepcopy(source))
        with patch.object(
            resources, "prepare_resource", wraps=resources.prepare_resource
        ) as prepare:
            result = sequence_sources("reading_passage", {}, ["cambridge:10"])
        self.assertEqual(len(result["items"]), 9)
        self.assertEqual(prepare.call_count, 12)
        self.assertEqual(len({row["id"] for row in result["items"]}), 9)
        self.assertNotIn("answer", json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))


if __name__ == "__main__":
    unittest.main()
