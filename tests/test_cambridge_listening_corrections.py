import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_listening_test_practice as builder
from services.cambridge_content_corrections import apply_content_corrections
from services.question_type_review import derive_listening_payload

ROOT = Path(__file__).resolve().parents[1]


def questions(payload):
    return {
        question["number"]: question
        for section in payload["sections"]
        for group in section["groups"]
        for question in group["questions"]
    }


class CambridgeListeningCorrectionsTest(unittest.TestCase):
    def test_timing_fallback_cannot_select_explanation_text(self):
        source = {
            "id": 1,
            "number": 1,
            "display_answer": "Hardie",
            "ai_analyze": "The surname is confirmed by its spelling.",
            "analyze": [
                {"type": "text", "content": "Wrong excerpt for this question."},
                {
                    "type": "audio",
                    "location": {"start_time": 4000, "end_time": 6000},
                },
            ],
            "answer_sentences": {"start_time": 1000, "end_time": 2000},
        }
        normal = builder.build_question(source)
        fallback = builder.build_question(source, use_analyze_location=True)
        self.assertEqual((normal["start"], fallback["start"]), (1.0, 4.0))
        self.assertEqual(normal["analysis"], fallback["analysis"])
        self.assertEqual(fallback["analysis"], source["ai_analyze"])
        self.assertEqual(fallback["answer_sentences"]["end_time"], 6000)

    def test_source_text_remains_available_when_ai_text_is_missing(self):
        source = {"analyze": [{"type": "text", "content": "A useful explanation."}]}
        for use_location in (False, True):
            self.assertEqual(
                builder.build_question(source, use_analyze_location=use_location)["analysis"],
                "A useful explanation.",
            )

    def test_build_test_applies_reviewed_text_after_source_assembly(self):
        raw = {
            "parts": {
                "133": {
                    "values": {
                        "content": [],
                        "question": [
                            {
                                "list": [
                                    {
                                        "id": 1106,
                                        "number": 1,
                                        "display_answer": "Hardie",
                                        "ai_analyze": "obsolete imported explanation",
                                    }
                                ]
                            }
                        ],
                    }
                }
            }
        }
        report = [{"exercise_id": "ielts10_test2_s1", "part_id": 133}]
        with tempfile.TemporaryDirectory() as temp:
            raw_path, report_path = Path(temp) / "raw.json", Path(temp) / "report.json"
            raw_path.write_text(json.dumps(raw))
            report_path.write_text(json.dumps(report))
            with (
                patch.object(builder, "RAW_PATH", raw_path),
                patch.object(builder, "REPORT_PATH", report_path),
            ):
                result = questions(builder.build_test("ielts10_test2"))[1]
        self.assertIn("H-A-R-D-I-E", result["analysis"])
        self.assertNotIn("obsolete", result["analysis"])
        self.assertEqual((result["id"], result["number"], result["answer"]), (1106, 1, "Hardie"))

    def test_c18_two_answer_reviews_include_both_complete_evidence_chains(self):
        payload = json.loads((ROOT / "static/listening_tests/ielts18_test1.json").read_text())
        current = questions(derive_listening_payload(payload, static_root=ROOT / "static"))
        for number, required in [
            (14, ("enough hours", "dedication", "full energy")),
            (15, ("enough hours", "dedication", "full energy")),
            (23, ("harsh", "only first years", "lot to learn")),
            (29, ("gap in the market", "being returned", "good to know")),
            (30, ("gap in the market", "being returned", "good to know")),
        ]:
            with self.subTest(question=number):
                review = current[number]["audio_review"]
                self.assertTrue(review["available"])
                text = " ".join(row["text"] for row in review["evidence"])
                for expected in required:
                    self.assertIn(expected, text)
                self.assertEqual(
                    current[number]["answer_sentences"]["start_time"],
                    round(current[number]["start"] * 1000),
                )
                self.assertEqual(
                    current[number]["answer_sentences"]["end_time"],
                    round(current[number]["end"] * 1000),
                )

    def test_c18_two_individual_stems_do_not_merge_distinct_answers(self):
        payload = json.loads((ROOT / "static/listening_tests/ielts18_test1.json").read_text())
        items = questions(payload)
        self.assertEqual(items[33]["title"].count("【"), 1)
        self.assertIn("guide the elephants", items[33]["title"])
        self.assertNotIn("tranquilisers", items[33]["title"])
        self.assertEqual(items[34]["title"].count("【"), 1)
        self.assertIn("reduce", items[34]["title"])
        self.assertNotIn("guide the elephants", items[34]["title"])
        self.assertEqual((items[33]["answer"], items[34]["answer"]), ("helicopters", "stress"))

    def test_source_form_words_are_not_joined_in_visible_titles(self):
        for test_id, numbers, phrase, malformed in [
            ("ielts5_test3", (13, 14, 15), "the same", "thesame"),
            ("ielts15_test4", (8,), "was provided", "wasprovided"),
        ]:
            payload = json.loads((ROOT / "static/listening_tests" / f"{test_id}.json").read_text())
            items = questions(payload)
            for number in numbers:
                with self.subTest(test=test_id, question=number):
                    self.assertIn(phrase, items[number]["title"])
                    self.assertNotIn(malformed, items[number]["title"])
            if len(numbers) > 1:
                # The shared three-blank stem must still be one shared cluster.
                self.assertEqual(len({items[number]["title"] for number in numbers}), 1)
                self.assertEqual(items[numbers[0]]["title"].count("【"), len(numbers))

    def test_lights_of_new_york_title_restores_the_printed_film_name(self):
        payload = json.loads((ROOT / "static/listening_tests/ielts6_test2.json").read_text())
        question = questions(payload)[40]
        self.assertEqual(
            question["title"],
            "Subtitles were added to The Lights of New York because of its 【   】.",
        )
        self.assertEqual(question["answer"], "poor sound quality")

    def test_nine_reviewed_group_ranges_cover_every_question(self):
        manifest = json.loads(
            (ROOT / "data/cambridge_content_corrections/listening.json").read_text()
        )
        checked = 0
        for test_id, correction in manifest["tests"].items():
            payload = json.loads((ROOT / "static/listening_tests" / f"{test_id}.json").read_text())
            for group in [g for s in payload["sections"] for g in s["groups"]]:
                patch_data = correction.get("groups", {}).get(str(group["group_id"]))
                if not patch_data:
                    continue
                self.assertEqual(set(patch_data), {"desc"})
                numbers = [q["number"] for q in group["questions"]]
                self.assertEqual(numbers, list(range(numbers[0], numbers[-1] + 1)))
                self.assertTrue(group["desc"].startswith(f"Questions {numbers[0]}-{numbers[-1]}\n"))
                self.assertNotIn("Complete th notes", group["desc"])
                self.assertEqual(group["desc"], patch_data["desc"])
                group["desc"] = "obsolete imported instruction"
                apply_content_corrections(payload, subject="listening")
                self.assertEqual(group["desc"], patch_data["desc"])
                checked += 1
        self.assertEqual(checked, 9)

    def test_c4_reversed_question_range_now_plays_date_confirmation(self):
        payload = json.loads((ROOT / "static/listening_tests/ielts4_test3.json").read_text())
        question = questions(derive_listening_payload(payload, static_root=ROOT / "static"))[4]
        review = question["audio_review"]
        self.assertTrue(review["available"])
        text = " ".join(row["text"] for row in review["evidence"])
        self.assertIn("Thursday", text)
        self.assertIn("seventh of September", text)
        self.assertIn("that's right", text)
        self.assertEqual(question["answer"], "thursday")
        self.assertLess(question["start"], question["end"])

    def test_hardie_review_uses_surname_and_spelling_instead_of_old_intro(self):
        payload = json.loads((ROOT / "static/listening_tests/ielts10_test2.json").read_text())
        question = questions(derive_listening_payload(payload, static_root=ROOT / "static"))[1]
        review = question["audio_review"]
        self.assertTrue(review["available"])
        text = " ".join(row["text"] for row in review["evidence"])
        self.assertIn("Hardie", text)
        self.assertIn("H-A-R-D-I-E", text)
        self.assertNotIn("survey on transport", text)
        self.assertEqual(question["answer"], "Hardie")

    def test_all_published_corrections_match_manifest_without_answer_mutations(self):
        manifest = json.loads(
            (ROOT / "data/cambridge_content_corrections/listening.json").read_text()
        )
        allowed = {"analysis", "title", "start", "end", "answer_sentences"}
        for test_id, correction in manifest["tests"].items():
            with self.subTest(test=test_id):
                payload = json.loads(
                    (ROOT / "static/listening_tests" / f"{test_id}.json").read_text()
                )
                before = copy.deepcopy(payload)
                for edits in correction.get("questions", {}).values():
                    self.assertFalse(set(edits) - allowed)
                apply_content_corrections(payload, subject="listening")
                self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
