"""Heading targets transcribed from source sub_essay_code, including examples."""

import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_reading_test_practice import build_group, build_passage_content
from services.cambridge_content_corrections import apply_content_corrections

ROOT = Path(__file__).resolve().parents[1]
# book, test, first question, explicit source paragraph sequence.
HEADING_TARGETS = [
    (4, 3, 14, "ABCD"),
    (4, 4, 28, "ACDE"),
    (5, 3, 14, "BDEF"),
    (5, 4, 1, "ABC"),
    (6, 1, 27, "BCDEFG"),
    (6, 2, 1, "ABCDE"),
    (6, 3, 14, "BCDEF"),
    (6, 4, 1, "ABCDEFG"),
    (6, 4, 27, "ABCD"),
    (7, 1, 14, "ACDEFGH"),
    (7, 2, 27, "BCEF"),
    (7, 3, 14, "ABCDEF"),
    (8, 1, 14, "ACDEFG"),
    (8, 2, 14, "BDEF"),
    (8, 2, 27, "ABCDEF"),
    (8, 3, 27, "BCDEFG"),
    (8, 4, 1, "BCDEF"),
    (9, 1, 14, "BCDE"),
    (9, 4, 27, "BCDE"),
    (10, 1, 14, "ABCDEGHI"),
    (10, 2, 1, "ABCDEFG"),
    (10, 3, 1, "BCDE"),
    (11, 2, 14, "ABCDEFG"),
    (11, 4, 27, "ABCDEF"),
    (12, 5, 27, "ABCDEF"),
    (12, 6, 14, "ABCDEFG"),
    (12, 7, 1, "ABCDEFG"),
    (12, 8, 27, "ABCDEFG"),
    (13, 1, 14, "ABCDEF"),
    (14, 2, 27, "ABCDEFGH"),
    (15, 3, 14, "ABCDEFG"),
    (16, 1, 14, "ABCDEFG"),
    (16, 4, 27, "ABCDEF"),
    (18, 3, 14, "ABCDEFG"),
    (20, 3, 14, "ABCDEF"),
]


class CambridgeReadingStemsTests(unittest.TestCase):
    def test_six_instruction_corrections_reference_the_current_passage_and_heading_range(self):
        for test_id, group_id, required, forbidden in [
            ("ielts14_test2_reading", 153, "Reading Passage 3", "Reading Passage 1"),
            ("ielts9_test4_reading", 331, "Reading Passage 1", "Reading Passage 2"),
            ("ielts12_test5_reading", 204, "Reading Passage 1", "Reading Passage 3"),
            ("ielts13_test2_reading", 181, "Reading Passage 1", "Reading Passage 3"),
            ("ielts5_test3_reading", 464, "Reading Passage 3", "Reading Passage 1"),
            ("ielts10_test3_reading", 285, "paragraphs B-E", "paragraphs S -E"),
        ]:
            payload = json.loads((ROOT / "static/reading_tests" / f"{test_id}.json").read_text())
            group = next(
                g for p in payload["passages"] for g in p["groups"] if g["group_id"] == group_id
            )
            with self.subTest(test=test_id):
                self.assertIn(required, group["desc"])
                self.assertNotIn(forbidden, group["desc"])
                if group_id == 285:
                    self.assertIn("i-viii", group["desc"])

    def test_four_figures_preserve_source_bytes_and_explicit_positions(self):
        for test_id, expected in [
            (
                "ielts4_test1_reading",
                [
                    (1, "b127cd430e07ace8bcde8af97f478b2b225c64c94649af02e2fac86c365bdeee"),
                    (9, "703003baafe78a850caecf10ce3c48567bd82eee317fe93ab5e4b174819c289c"),
                ],
            ),
            (
                "ielts7_test4_reading",
                [(3, "730424b44d7e625a10f2d9bce6774f4d9b2aa878b1f8287aa88b6658841c019c")],
            ),
            (
                "ielts10_test3_reading",
                [(2, "2f5474337470470fbe03f16a3d14bb7d521d22d5280cc59ab0d34de04e7bb10c")],
            ),
        ]:
            payload = json.loads((ROOT / "static/reading_tests" / f"{test_id}.json").read_text())
            images = payload["passages"][2]["content"]["images"]
            self.assertEqual(len(images), len(expected))
            for image, (position, digest) in zip(images, expected, strict=True):
                self.assertEqual(image["after_paragraph"], position)
                self.assertEqual(
                    hashlib.sha256((ROOT / "static" / image["url"]).read_bytes()).hexdigest(),
                    digest,
                )
                self.assertTrue(image["alt"])

    def test_builder_preserves_source_figure_position_separately_from_intro(self):
        with patch(
            "scripts.build_reading_test_practice.localize_image",
            return_value="reading_tests/images/figure.png",
        ):
            content = build_passage_content(
                {
                    "content": {
                        "pre-A": "Introduction.",
                        "A": "Body.",
                        "paragraph_img": [
                            {"img_url": "https://example.org/figure.png", "paragraph": 0}
                        ],
                    }
                },
                "example",
            )
        self.assertEqual(content["paragraphs"][0]["label"], "pre-A")
        self.assertEqual(content["images"][0]["after_paragraph"], 0)
        self.assertEqual(content["images"][0]["url"], "reading_tests/images/figure.png")

    def test_all_200_heading_prompts_use_source_targets_including_skipped_examples(self):
        count = 0
        for book, test_no, first, letters in HEADING_TARGETS:
            test_id = f"ielts{book}_test{test_no}_reading"
            payload = json.loads((ROOT / "static/reading_tests" / f"{test_id}.json").read_text())
            questions = {
                q["number"]: q
                for p in payload["passages"]
                for g in p["groups"]
                for q in g["questions"]
            }
            for offset, letter in enumerate(letters):
                with self.subTest(test=test_id, number=first + offset):
                    title = questions[first + offset]["title"]
                    self.assertTrue(
                        title == f"Paragraph {letter}" or title.startswith(f"Paragraph {letter} (")
                    )
                    count += 1
        self.assertEqual(count, 200)

    def test_builder_uses_explicit_source_code_and_keeps_named_key_points(self):
        group = {
            "type": 6,
            "desc": "Choose headings for Key Points Two to Six. Key Point One is an example.",
            "list": [
                {
                    "id": 200,
                    "number": 14,
                    "title": "",
                    "sub_essay_code": "B",
                    "display_answer": "vii",
                }
            ],
        }
        built = build_group(group, "example", {"B": "KEY POINT TWO"})["questions"][0]
        self.assertEqual(built["title"], "Paragraph B (Key Point Two)")
        self.assertEqual(built["answer"], "vii")
        self.assertEqual(built["id"], 200)

    def test_missing_source_code_does_not_invent_a_paragraph_from_position(self):
        group = {
            "type": 6,
            "list": [{"id": 200, "number": 14, "title": "", "display_answer": "ii"}],
        }
        self.assertEqual(build_group(group, "example")["questions"][0]["title"], "")
        group["list"][0].update(title="Paragraph D", sub_essay_code="B")
        self.assertEqual(build_group(group, "example")["questions"][0]["title"], "Paragraph D")

    def test_legacy_specialty_snapshot_uses_source_number_and_preserves_identity_and_grade(self):
        payload = {
            "id": "specialty-session",
            "passages": [
                {
                    "source_test_id": "ielts10_test1_reading",
                    "groups": [
                        {
                            "source_meta": {"test_id": "ielts10_test1_reading"},
                            "questions": [
                                {
                                    "id": "assignment-7",
                                    "number": 1,
                                    "source_number": 19,
                                    "title": "",
                                    "answer": "x",
                                    "answers": ["x"],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        before = copy.deepcopy(payload)
        apply_content_corrections(payload, "reading")
        question = payload["passages"][0]["groups"][0]["questions"][0]
        self.assertEqual(question["title"], "Paragraph G")
        question["title"] = ""
        self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
