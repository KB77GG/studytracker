import unittest
from pathlib import Path

from scripts.audit_toefl_official_materials import (
    OfficialSource,
    classify_file_duplicate,
    extract_question_blocks,
    normalize_content,
    slice_source_text,
)


class AuditToeflOfficialMaterialsTest(unittest.TestCase):
    def test_normalize_removes_question_number_and_option_labels(self):
        normalized = normalize_content(
            "11. What is the purpose?\n(A) First answer\n(B) Second answer"
        )
        self.assertEqual(
            normalized,
            "what is the purpose first answer second answer",
        )

    def test_extracts_numbered_question_blocks(self):
        source = OfficialSource(
            source_id="sample",
            label="Sample",
            kind="student_practice",
            pdf_path=Path("/tmp/sample.pdf"),
        )
        text = (
            "Reading Section, Module 1\n"
            "11. What is the main purpose of the notice?\n"
            "(A) To invite students to a workshop\n"
            "(B) To announce a schedule change\n"
            "(C) To collect a payment\n"
            "(D) To describe a new course\n"
            "12. What should students bring to the event?\n"
            "(A) A notebook\n(B) A payment\n(C) A coat\n(D) An identification card\n"
        )
        blocks = extract_question_blocks(source, text)
        self.assertEqual([block["question_no"] for block in blocks], ["11", "12"])
        self.assertEqual(blocks[0]["section"], "reading")
        self.assertEqual(blocks[0]["module"], "m1")

    def test_classifies_shared_direction_audio(self):
        rows = [
            {
                "source_id": "practice-1",
                "path": "a/Directions.ogg",
                "relative_name": "Directions.ogg",
            },
            {
                "source_id": "practice-2",
                "path": "b/Listening_Directions.ogg",
                "relative_name": "Listening_Directions.ogg",
            },
        ]
        self.assertEqual(classify_file_duplicate(rows), "shared_direction_asset")

    def test_classifies_duplicate_zip_copy(self):
        rows = [
            {
                "source_id": "practice-1",
                "path": "audio.zip",
                "relative_name": "audio.zip",
            },
            {
                "source_id": "practice-1",
                "path": "audio (1).zip",
                "relative_name": "audio (1).zip",
            },
        ]
        self.assertEqual(classify_file_duplicate(rows), "duplicate_copy")

    def test_slices_source_text_with_flexible_markers(self):
        source = OfficialSource(
            source_id="og",
            label="OG",
            kind="official_guide",
            pdf_path=Path("/tmp/og.pdf"),
            text_start_pattern=(
                r"(?im)^\s*CHAPTER 6\s*$[\s\S]{0,200}?"
                r"^\s*TOEFL iBT®?\s*$[\s\S]{0,80}?^\s*Practice Test\s*$"
            ),
            text_end_pattern=r"(?im)^\s*Answers, Explanations, and Scripts\s*$",
        )
        text = (
            "Earlier content\f\n"
            " CHAPTER 6 \n\nTOEFL iBT®\nPractice Test\n"
            "Reading Section\n11. A sufficiently long question body for extraction.\n"
            "Answers, Explanations, and Scripts\nLater content"
        )
        sliced = slice_source_text(source, text)
        self.assertIn("Reading Section", sliced)
        self.assertNotIn("Earlier content", sliced)
        self.assertNotIn("Later content", sliced)

    def test_missing_source_marker_fails_closed(self):
        source = OfficialSource(
            source_id="og",
            label="OG",
            kind="official_guide",
            pdf_path=Path("/tmp/og.pdf"),
            text_start_pattern=r"missing marker",
        )
        with self.assertRaises(RuntimeError):
            slice_source_text(source, "whole book")


if __name__ == "__main__":
    unittest.main()
