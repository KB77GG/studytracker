import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import cambridge_content_corrections as corrections
from services.ielts_practice_scoring import grade_listening_test_answers
from services.question_type_practice import (
    LibraryRoots,
    build_group_index,
    build_snapshot,
    public_snapshot,
)
from services.question_type_review import review_snapshot

ROOT = Path(__file__).resolve().parents[1]


class CambridgeContentCorrectionsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.directory = self.root / "data" / "cambridge_content_corrections"
        self.directory.mkdir(parents=True)
        self.root_patch = patch.object(corrections, "_ROOT", self.root)
        self.root_patch.start()
        corrections._load_corrections.cache_clear()
        self._write(
            "reading",
            {
                "ielts6_test2_reading": {
                    "questions": {
                        "6": {
                            "analysis": "Correct explanation.",
                            "central_sentences": [{"sentence": "Restored evidence."}],
                        }
                    },
                    "passages": {"1": {"introduction": "Restored evidence."}},
                }
            },
        )
        self._write("listening", {})

    def tearDown(self):
        corrections._load_corrections.cache_clear()
        self.root_patch.stop()
        self.temp.cleanup()

    def _write(self, subject, tests):
        (self.directory / f"{subject}.json").write_text(json.dumps({"tests": tests}))

    def _payload(self):
        return {
            "id": "question_type_reading_saved",
            "passages": [
                {
                    "source_test_id": "ielts6_test2_reading",
                    "passage": 1,
                    "content": {"paragraphs": [{"label": "A", "text": "Original A."}]},
                    "groups": [
                        {
                            "questions": [
                                {
                                    "id": 9000000001,
                                    "number": 1,
                                    "source_number": 6,
                                    "answer": "TRUE",
                                    "answers": ["TRUE"],
                                    "analysis": "Old explanation.",
                                }
                            ]
                        }
                    ],
                }
            ],
        }

    def test_original_identity_and_grading_fields_survive_renumbering(self):
        payload = self._payload()
        original = copy.deepcopy(payload)
        self.assertIs(corrections.apply_content_corrections(payload, "reading"), payload)
        unit = payload["passages"][0]
        question = unit["groups"][0]["questions"][0]
        for key in ("id", "number", "source_number", "answer", "answers"):
            self.assertEqual(
                question[key], original["passages"][0]["groups"][0]["questions"][0][key]
            )
        self.assertEqual(question["analysis"], "Correct explanation.")
        self.assertEqual(unit["content"]["paragraphs"][1], {"label": "A", "text": "Original A."})
        once = copy.deepcopy(payload)
        corrections.apply_content_corrections(payload, "reading")
        self.assertEqual(payload, once)

    def test_pre_submission_copy_restores_article_without_solution_leak(self):
        frozen = {
            "subject": "reading",
            "pace": "simulation",
            "snapshot_hash": "original-hash",
            "payload": self._payload(),
        }
        original = copy.deepcopy(frozen)
        public = public_snapshot(frozen)
        self.assertEqual(frozen, original)
        self.assertEqual(public["snapshot_hash"], "original-hash")
        unit = public["payload"]["passages"][0]
        self.assertEqual(unit["content"]["paragraphs"][0]["text"], "Restored evidence.")
        question = unit["groups"][0]["questions"][0]
        for key in ("answer", "answers", "analysis", "central_sentences", "locating_words"):
            self.assertNotIn(key, question)

    def test_unknown_tests_are_untouched(self):
        payload = self._payload()
        payload["passages"][0]["source_test_id"] = "reading_jijing_1_test_1"
        original = copy.deepcopy(payload)
        corrections.apply_content_corrections(payload, "reading")
        self.assertEqual(payload, original)

    def test_real_legacy_cambridge18_snapshot_updates_original_numbers_without_leaks(self):
        manifest = json.loads(
            (ROOT / "data/cambridge_content_corrections/listening.json").read_text()
        )
        self._write("listening", manifest["tests"])
        corrections._load_corrections.cache_clear()
        source = json.loads((ROOT / "static/listening_tests/ielts18_test1.json").read_text())
        shared_old_title = (
            "·vets and park staff made use of 【   】 to help guide the elephants into an open plain "
            "·elephants were immobilised with tranquilisers− this process had to be completed quickly to reduce 【   】"
        )
        for section in source["sections"]:
            for group in section["groups"]:
                for question in group["questions"]:
                    if question["number"] in (14, 15):
                        question.update(start=168.02, end=181.33)
                        question["answer_sentences"] = {
                            "start_time": 168020,
                            "end_time": 181330,
                            "lyc_index": [13, 14],
                        }
                    if question["number"] in (29, 30):
                        question.update(start=334.4, end=342.18)
                        question["answer_sentences"] = {
                            "start_time": 334400,
                            "end_time": 342180,
                            "lyc_index": [45, 46],
                        }
                    if question["number"] in (33, 34):
                        question["title"] = shared_old_title
        listening = self.root / "listening"
        reading = self.root / "reading"
        listening.mkdir()
        reading.mkdir()
        (listening / "ielts18_test1.json").write_text(json.dumps(source))
        roots = LibraryRoots(listening=listening, reading=reading)
        rows = build_group_index(roots)
        selected = [
            row
            for row in rows
            if row["unit_index"] == 3 or row["original_question_range"] in {"14-15", "29-30"}
        ]
        self.assertEqual(len(selected), 3)
        frozen = build_snapshot(selected, pace="training", standard_type="all", roots=roots)
        before = copy.deepcopy(frozen)
        saved_json = json.dumps(frozen, sort_keys=True)
        old_grade = grade_listening_test_answers(frozen["payload"], {})
        reviewed = review_snapshot(
            frozen,
            static_root=ROOT / "static",
            audio_root=ROOT / "static/listening",
            project_root=ROOT,
        )
        questions = {
            question["source_number"]: question
            for section in reviewed["payload"]["sections"]
            for group in section["groups"]
            for question in group["questions"]
        }
        self.assertEqual(questions[14]["number"], 1)
        self.assertEqual(questions[29]["number"], 3)
        # Displayed Q14 is original Q40, not the source Q14 timing correction.
        self.assertEqual(questions[40]["number"], 14)
        self.assertNotEqual(questions[40]["start"], questions[14]["start"])
        for number, expected in (
            (14, "dedication"),
            (15, "dedication"),
            (29, "returned"),
            (30, "returned"),
        ):
            evidence = " ".join(
                row["text"] for row in questions[number]["audio_review"]["evidence"]
            )
            self.assertIn(expected, evidence)
        self.assertEqual(questions[33]["title"].count("【"), 1)
        self.assertEqual(questions[34]["title"].count("【"), 1)
        self.assertNotEqual(questions[33]["title"], questions[34]["title"])
        self.assertEqual(grade_listening_test_answers(reviewed["payload"], {}), old_grade)
        forbidden = {
            "answer",
            "answers",
            "analysis",
            "central_sentences",
            "locating_words",
            "answer_sentences",
            "transcript",
            "audio_review",
        }

        def assert_redacted(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    assert_redacted(child)
            elif isinstance(value, list):
                for child in value:
                    assert_redacted(child)

        for pace in ("training", "exam"):
            candidate = copy.deepcopy(frozen)
            candidate["pace"] = pace
            candidate_before = copy.deepcopy(candidate)
            public = public_snapshot(
                candidate,
                static_root=ROOT / "static",
                audio_root=ROOT / "static/listening",
                project_root=ROOT,
            )
            assert_redacted(public["payload"])
            self.assertEqual(candidate, candidate_before)
            self.assertEqual(public["snapshot_hash"], frozen["snapshot_hash"])
            if pace == "exam":
                self.assertNotIn('"practice_audio"', json.dumps(public))
                self.assertNotIn('"audio_timeline"', json.dumps(public))
        self.assertEqual(frozen, before)
        self.assertEqual(json.dumps(frozen, sort_keys=True), saved_json)

    def test_manifest_cannot_override_answer_or_identity(self):
        for field in ("answer", "answers", "id", "number", "awarded", "marks"):
            with self.subTest(field=field):
                self._write(
                    "reading", {"ielts6_test2_reading": {"questions": {"6": {field: "changed"}}}}
                )
                corrections._load_corrections.cache_clear()
                with self.assertRaisesRegex(ValueError, "Non-editorial"):
                    corrections.apply_content_corrections(self._payload(), "reading")

    def test_legacy_group_and_source_figures_are_restored_on_the_public_copy(self):
        figure = {
            "url": "reading_tests/images/figure1.png",
            "alt": "Figure 1",
            "after_paragraph": 0,
        }
        self._write(
            "reading",
            {
                "ielts6_test2_reading": {
                    "groups": {"99": {"desc": "Questions 6-10. Reading Passage 1."}},
                    "passages": {"1": {"images": [figure]}},
                }
            },
        )
        corrections._load_corrections.cache_clear()
        payload = self._payload()
        group = payload["passages"][0]["groups"][0]
        group.update(
            group_id=99, desc="Wrong passage.", source_meta={"test_id": "ielts6_test2_reading"}
        )
        frozen = {
            "subject": "reading",
            "pace": "exam",
            "payload": payload,
            "snapshot_hash": "unchanged",
        }
        original = copy.deepcopy(frozen)
        public = public_snapshot(frozen)
        unit = public["payload"]["passages"][0]
        self.assertEqual(unit["content"]["images"], [figure])
        self.assertEqual(unit["groups"][0]["desc"], "Questions 6-10. Reading Passage 1.")
        self.assertNotIn("answer", unit["groups"][0]["questions"][0])
        unit["content"]["images"][0]["alt"] = "changed copy"
        self.assertEqual(frozen, original)

    def test_group_scoring_fields_and_nonlocal_figure_paths_are_rejected(self):
        invalid = [
            {"groups": {"99": {"answer": "B"}}},
            {
                "passages": {
                    "1": {
                        "images": [{"url": "../private.png", "alt": "Figure", "after_paragraph": 0}]
                    }
                }
            },
            {
                "passages": {
                    "1": {
                        "images": [
                            {
                                "url": "https://example.com/figure.png",
                                "alt": "Figure",
                                "after_paragraph": 0,
                            }
                        ]
                    }
                }
            },
        ]
        for correction in invalid:
            with self.subTest(correction=correction):
                self._write("reading", {"ielts6_test2_reading": correction})
                corrections._load_corrections.cache_clear()
                with self.assertRaises(ValueError):
                    corrections.apply_content_corrections(self._payload(), "reading")


if __name__ == "__main__":
    unittest.main()
