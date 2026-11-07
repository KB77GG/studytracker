import copy
import json
import unittest
from pathlib import Path

from scripts.build_reading_test_practice import build_passage_content, build_tests
from services.cambridge_content_corrections import apply_content_corrections

ROOT = Path(__file__).resolve().parents[1]
READING = ROOT / "static/reading_tests"
INTRODUCTIONS = {
    ("ielts4_test3_reading", 2): "When Mount Pinatubo suddenly erupted",
    ("ielts6_test2_reading", 1): "A new study conducted for the World Bank",
    ("ielts6_test3_reading", 2): "It is a great deal easier to motivate employees",
    ("ielts9_test1_reading", 2): "The question of whether we are alone",
    ("ielts20_test4_reading", 3): "Livestock guard dogs",
}


def load_test(test_id):
    return json.loads((READING / f"{test_id}.json").read_text())


def find_question(payload, number):
    for passage in payload["passages"]:
        for group in passage["groups"]:
            for question in group["questions"]:
                if question["number"] == number:
                    return question, passage
    raise AssertionError(f"Missing question: {number}")


class CambridgeReadingCorrectionsTests(unittest.TestCase):
    def test_import_preserves_introduction_and_original_letter_labels(self):
        content = build_passage_content(
            {
                "content": {
                    "title": "Example",
                    "pre-A": "<p>Opening paragraph.</p>",
                    "A": "First labelled paragraph.",
                    "C": "Third labelled paragraph.",
                }
            }
        )
        self.assertEqual(
            content["paragraphs"],
            [
                {"label": "pre-A", "text": "Opening paragraph."},
                {"label": "A", "text": "First labelled paragraph."},
                {"label": "C", "text": "Third labelled paragraph."},
            ],
        )

    def test_import_without_introduction_keeps_existing_array_labels(self):
        content = build_passage_content(
            {"content": {"pre-A": " ", "paragraph": ["First.", "Second."]}}
        )
        self.assertEqual(
            content["paragraphs"],
            [{"label": "A", "text": "First."}, {"label": "B", "text": "Second."}],
        )

    def test_all_five_published_introductions_are_restored(self):
        for (test_id, passage_no), opening in INTRODUCTIONS.items():
            with self.subTest(test=test_id, passage=passage_no):
                passage = next(
                    p for p in load_test(test_id)["passages"] if p["passage"] == passage_no
                )
                paragraphs = passage["content"]["paragraphs"]
                self.assertEqual(paragraphs[0]["label"], "pre-A")
                self.assertTrue(paragraphs[0]["text"].startswith(opening))
                self.assertEqual(paragraphs[1]["label"], "A")
                self.assertEqual(sum(p["label"] == "pre-A" for p in paragraphs), 1)

    def test_seven_direct_evidence_sentences_are_back_in_reading_body(self):
        for test_id, numbers in [
            ("ielts6_test2_reading", (6, 7, 9, 10, 11, 12)),
            ("ielts6_test3_reading", (19,)),
        ]:
            payload = load_test(test_id)
            for number in numbers:
                with self.subTest(test=test_id, number=number):
                    question, passage = find_question(payload, number)
                    intro = passage["content"]["paragraphs"][0]["text"]
                    for evidence in question["central_sentences"]:
                        if evidence.get("target_para") == "pre-A":
                            self.assertIn(evidence["sentence"], intro)

    def test_three_wrong_explanations_retain_correct_scoring_keys(self):
        cases = [
            ("ielts4_test3_reading", 5, "sudan and india", "Sudan and India"),
            ("ielts7_test4_reading", 34, "B", "因此选 B（unexpected）"),
            ("ielts12_test5_reading", 29, "ii", "标题 ii"),
        ]
        for test_id, number, answer, conclusion in cases:
            with self.subTest(test=test_id, number=number):
                question, _ = find_question(load_test(test_id), number)
                self.assertEqual(question["answer"], answer)
                self.assertIn(conclusion, question["analysis"])
                # The old synonym records pointed to another question/paragraph.
                self.assertEqual(question["locating_words"], [])

    def test_each_corrected_quote_is_exact_and_its_offsets_match(self):
        manifest = json.loads(
            (ROOT / "data/cambridge_content_corrections/reading.json").read_text()
        )
        for test_id, correction in manifest["tests"].items():
            payload = load_test(test_id)
            for number, patch in correction.get("questions", {}).items():
                if "central_sentences" not in patch:
                    continue
                question, passage = find_question(payload, int(number))
                with self.subTest(test=test_id, number=number):
                    self.assertEqual(question["central_sentences"], patch["central_sentences"])
                    paragraphs = passage["content"]["paragraphs"]
                    for evidence in question["central_sentences"]:
                        target = evidence["target_para"]
                        paragraph = (
                            paragraphs[target]
                            if isinstance(target, int)
                            else next(p for p in paragraphs if p["label"] == target)
                        )
                        start = evidence["index"]
                        end = start + evidence["length"]
                        self.assertEqual(paragraph["text"][start:end], evidence["sentence"])

    def test_transcription_errors_are_replaced_with_actual_source_words(self):
        cases = [
            ("ielts14_test1_reading", 34, "reduction of dissatisfaction", "is satisfaction"),
            ("ielts9_test2_reading", 31, "do not fall into", "do not fail into"),
            ("ielts9_test2_reading", 32, "never encountered before", "never encouraged before"),
        ]
        for test_id, number, correct, incorrect in cases:
            with self.subTest(test=test_id, number=number):
                question, _ = find_question(load_test(test_id), number)
                evidence = json.dumps(question["central_sentences"])
                self.assertIn(correct, evidence)
                self.assertNotIn(incorrect, evidence)
                self.assertNotIn(incorrect, json.dumps(question["locating_words"]))

    def test_legacy_intro_repair_is_idempotent_and_preserves_existing_paragraphs(self):
        for test_id, passage_no in INTRODUCTIONS:
            with self.subTest(test=test_id):
                payload = load_test(test_id)
                passage = next(p for p in payload["passages"] if p["passage"] == passage_no)
                expected = copy.deepcopy(passage["content"]["paragraphs"])
                passage["content"]["paragraphs"] = expected[1:]
                apply_content_corrections(payload, "reading")
                apply_content_corrections(payload, "reading")
                self.assertEqual(passage["content"]["paragraphs"], expected)

    def test_future_import_does_not_reintroduce_the_old_cross_question_explanation(self):
        raw = {
            "entries": [{"source": "academic", "part_id": 1, "book": 7, "test": 4, "passage": 3}],
            "parts": {
                "academic": {
                    "1": {
                        "title": "Passage 3",
                        "test_name": "Test 4",
                        "content": {"paragraph": ["A.", "B.", "C.", "D."]},
                        "question": [
                            {
                                "type": 10,
                                "list": [
                                    {
                                        "id": 1863,
                                        "number": 34,
                                        "display_answer": "B",
                                        "ai_analyze": "正确答案是 I: made more mistakes than。",
                                        "central_sentences": [],
                                    }
                                ],
                            }
                        ],
                    }
                }
            },
        }
        payload = build_tests(raw, "academic")["ielts7_test4_reading"]
        question, _ = find_question(payload, 34)
        self.assertEqual(question["answer"], "B")
        self.assertEqual(question["id"], 1863)
        self.assertIn("因此选 B（unexpected）", question["analysis"])
        self.assertIn("unpredictable noise", question["central_sentences"][0]["sentence"])


if __name__ == "__main__":
    unittest.main()
