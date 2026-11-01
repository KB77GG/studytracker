"""Complete reading Tests remain one scheduling unit and three native tasks."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from services import task_planner_resources as resources
from services.task_planner_sequence import sequence_sources


class ReadingTestSequenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for folder in ("reading_tests", "reading_jijing"):
            (self.root / "static" / folder).mkdir(parents=True)
        app = Flask(__name__)
        app.config.update(TESTING=True, TASK_PLANNER_ROOT=str(self.root))
        self.context = app.app_context()
        self.context.push()

    def tearDown(self):
        self.context.pop()
        self.tmp.cleanup()

    def write(self, resource_id, source, folder="reading_tests"):
        path = self.root / "static" / folder / f"{resource_id}.json"
        path.write_text(json.dumps(source), encoding="utf-8")
        return path

    def reading(self, resource_id="ielts10_test1_reading", **extra):
        source = {"id": resource_id, "title": resource_id, "passages": [], **extra}
        for passage, start, end in ((1, 1, 13), (2, 14, 26), (3, 27, 40)):
            source["passages"].append({
                "passage": passage,
                "content": {"paragraphs": [{"text": "A complete passage."}]},
                "groups": [{"questions": [
                    {"id": 1000 + number, "number": number, "answer": "TRUE"}
                    for number in range(start, end + 1)
                ]}],
            })
        self.write(resource_id, source)
        return source

    def test_one_test_is_one_catalog_unit_with_three_native_selections(self):
        self.reading()
        result = sequence_sources("reading_test", {}, ["cambridge:10"])
        self.assertEqual(result["sources"], [{"id": "cambridge:10", "label": "剑雅 10", "count": 1}])
        self.assertEqual(result["items"], [{
            "id": "ielts10_test1_reading:all",
            "label": "ielts10_test1_reading · 阅读整套（Passage 1–3）",
            "task_kind": "reading_passage",
            "selections": [
                {"test_id": "ielts10_test1_reading", "passage_number": number}
                for number in (1, 2, 3)
            ],
            "question_count": 40,
        }])
        self.assertNotIn("answer", json.dumps(result))
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_books_and_tests_use_numeric_order_and_explicit_scope(self):
        for resource_id in ("ielts10_test10_reading", "ielts10_test2_reading",
                            "ielts10_test1_reading", "ielts11_test1_reading"):
            self.reading(resource_id)
        self.assertEqual(sequence_sources("reading_test", {})["items"], [])
        selected = sequence_sources("reading_test", {}, ["cambridge:10"])
        self.assertEqual([row["id"] for row in selected["items"]], [
            "ielts10_test1_reading:all", "ielts10_test2_reading:all", "ielts10_test10_reading:all",
        ])
        both = sequence_sources("reading_test", {}, ["cambridge:11", "cambridge:10"])
        self.assertEqual(both["items"][-1]["id"], "ielts11_test1_reading:all")

    def test_missing_passages_are_never_combined_across_tests(self):
        for test, missing in ((1, 3), (2, 1)):
            resource_id = f"ielts10_test{test}_reading"
            source = self.reading(resource_id)
            source["passages"] = [row for row in source["passages"] if row["passage"] != missing]
            self.write(resource_id, source)
        self.assertEqual(sequence_sources("reading_test", {}), {"sources": [], "items": []})
        with self.assertRaisesRegex(ValueError, "完整阅读套题"):
            sequence_sources("reading_test", {}, ["cambridge:10"])

    def test_incomplete_duplicate_or_non_exam_question_numbers_reject_whole_test(self):
        original = self.reading()
        for invalid in (None, 0, 41, True, "q40", 1):
            with self.subTest(invalid=invalid):
                source = copy.deepcopy(original)
                source["passages"][2]["groups"][0]["questions"][-1]["number"] = invalid
                self.write(source["id"], source)
                self.assertEqual(sequence_sources("reading_test", {})["sources"], [])
        source = copy.deepcopy(original)
        source["passages"][2]["groups"][0]["questions"].pop()
        self.write(source["id"], source)
        self.assertEqual(sequence_sources("reading_test", {})["sources"], [])

    def test_global_ids_cannot_stand_in_for_missing_exam_numbers(self):
        source = self.reading()
        for passage in source["passages"]:
            for question in passage["groups"][0]["questions"]:
                question["id"] = question.pop("number")
        self.write(source["id"], source)
        self.assertEqual(sequence_sources("reading_test", {})["sources"], [])

    def test_reordered_passages_produce_ordered_native_tasks(self):
        source = self.reading()
        source["passages"].reverse()
        self.write(source["id"], source)
        item = sequence_sources("reading_test", {}, ["cambridge:10"])["items"][0]
        self.assertEqual([choice["passage_number"] for choice in item["selections"]], [1, 2, 3])

    def test_duplicate_passage_or_malformed_group_rejects_only_bad_test(self):
        original = self.reading()
        self.reading("ielts11_test1_reading")
        for malformed in ("duplicate", "empty_group", "bad_question"):
            with self.subTest(malformed=malformed):
                source = copy.deepcopy(original)
                if malformed == "duplicate":
                    source["passages"][2]["passage"] = 2
                elif malformed == "empty_group":
                    source["passages"][2]["groups"] = []
                else:
                    source["passages"][2]["groups"][0]["questions"][0] = None
                self.write(source["id"], source)
                self.assertEqual([row["id"] for row in sequence_sources("reading_test", {})["sources"]], ["cambridge:11"])

    def test_any_native_passage_validation_failure_excludes_whole_test(self):
        self.reading()
        prepare = resources.prepare_resource

        def unavailable(kind, selection):
            if selection.get("passage_number") == 2:
                raise ValueError("unavailable")
            return prepare(kind, selection)

        with patch.object(resources, "prepare_resource", side_effect=unavailable):
            self.assertEqual(sequence_sources("reading_test", {})["sources"], [])

    def test_hidden_and_canonical_offline_alias_are_not_offered(self):
        source = self.reading()
        self.write("alias", source)
        self.write("offline_tests", {"tests": [{"id": source["id"], "status": "offline"}]})
        self.reading("ielts11_test1_reading", hidden_from_catalog=True)
        self.reading("ielts12_test1_reading")
        self.assertEqual([row["id"] for row in sequence_sources("reading_test", {})["sources"]], ["cambridge:12"])

    def test_jijing_and_standalone_scope_and_duplicate_paths_follow_existing_catalog(self):
        source = self.reading("reading_jijing_2_test_8", source="idictation_reading_jijing", book=2, test=8)
        self.write(source["id"], source, folder="reading_jijing")
        self.reading("custom_test10")
        self.reading("custom_test2")
        result = sequence_sources("reading_test", {}, ["test:custom_test10", "reading_jijing:2", "test:custom_test2"])
        self.assertEqual([row["id"] for row in result["items"]], [
            "reading_jijing_2_test_8:all", "custom_test2:all", "custom_test10:all",
        ])

    def test_whole_test_rejects_partial_options_and_invalid_scope(self):
        self.reading()
        for selection, scopes in (({"passage_number": 1}, None), ({"section_number": None}, None),
                                  ({}, "cambridge:10"), ({}, ["cambridge:10", "cambridge:10"]),
                                  ({}, ["cambridge:999"]), ([], None)):
            with self.subTest(selection=selection, scopes=scopes), self.assertRaises(ValueError):
                sequence_sources("reading_test", selection, scopes)


if __name__ == "__main__":
    unittest.main()
