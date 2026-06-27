from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.extract_toefl_answer_keys import (
    assess_candidate,
    build_choice_map,
    parse_answer_text,
)


class ExtractToeflAnswerKeysTest(unittest.TestCase):
    def test_parse_preserves_section_and_extra_namespaces(self):
        text = """
阅读
1this 2helps 3reduce 4and 5it
6b 7a 8d
加试
1reasoning 2with 3principles 4c 5a 6b

听力
1a 2d 3c
加试
1b 2c 3d

写作
1. this line must not be parsed as a choice answer
"""
        rows, _warnings = parse_answer_text(
            text,
            exam_key="2026-04-08",
            source_pdf="4.8新托福真题/4.8答案.pdf",
        )
        by_key = {row["canonical_key"]: row for row in rows}

        self.assertEqual(
            by_key["2026-04-08:reading:main:q6"]["correct_answer"],
            "B",
        )
        self.assertEqual(
            by_key["2026-04-08:reading:main:q1"]["answer_type"],
            "text",
        )
        self.assertEqual(
            by_key["2026-04-08:reading:extra:q4"]["section_question_no"],
            12,
        )
        self.assertEqual(
            by_key["2026-04-08:listening:extra:q1"]["block"],
            "extra",
        )

    def test_candidate_rejects_partial_folder_and_accepts_complete_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            complete = root / "4.8新托福真题"
            complete.mkdir()
            complete_answer = complete / "4.8答案.pdf"
            complete_answer.write_bytes(b"answer")
            (complete / "4.8阅读.pdf").write_bytes(b"reading")
            (complete / "4.8听力.pdf").write_bytes(b"listening")

            writing_only = root / "4.11-后续补充"
            writing_only.mkdir()
            writing_answer = writing_only / "4.11阅读+答案.pdf"
            writing_answer.write_bytes(b"answer")
            (writing_only / "4.11写作真题.pdf").write_bytes(b"writing")

            partial = root / "4.6新托福真题"
            partial.mkdir()
            partial_answer = partial / "4.6答案.pdf"
            partial_answer.write_bytes(b"answer")
            (partial / "4.6阅读.pdf").write_bytes(b"reading")
            (partial / "4.6听力(缺q1).pdf").write_bytes(b"listening")

            complete_row = assess_candidate(
                complete_answer,
                root,
                2026,
                {"reading", "listening"},
            )
            partial_row = assess_candidate(
                partial_answer,
                root,
                2026,
                {"reading", "listening"},
            )
            writing_only_row = assess_candidate(
                writing_answer,
                root,
                2026,
                {"reading", "listening"},
            )

        self.assertIsNotNone(complete_row)
        self.assertTrue(complete_row.complete)
        self.assertIsNotNone(partial_row)
        self.assertFalse(partial_row.complete)
        self.assertIn(
            "partial/incomplete marker present",
            partial_row.rejection_reasons,
        )
        self.assertIsNotNone(writing_only_row)
        self.assertIn(
            "missing companion sections: listening",
            writing_only_row.rejection_reasons,
        )

    def test_choice_map_excludes_text_answers(self):
        exams = [
            {
                "exam_key": "2026-04-08",
                "answers": [
                    {
                        "section": "reading",
                        "block": "main",
                        "source_question_no": 1,
                        "answer_type": "text",
                        "correct_answer": "this",
                    },
                    {
                        "section": "reading",
                        "block": "main",
                        "source_question_no": 21,
                        "answer_type": "choice",
                        "correct_answer": "B",
                    },
                ],
            }
        ]

        choice_map = build_choice_map(exams)

        self.assertEqual(
            choice_map["2026-04-08"]["reading"]["main"],
            {"21": "B"},
        )


if __name__ == "__main__":
    unittest.main()
