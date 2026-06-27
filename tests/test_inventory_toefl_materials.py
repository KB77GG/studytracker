from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.inventory_toefl_materials import (
    build_inventory,
    classify_file,
    extract_date,
    extract_variant,
)


class InventoryToeflMaterialsTest(unittest.TestCase):
    def test_extract_date_and_variant(self):
        self.assertEqual(extract_date("2026.2.1新托福真题"), "2026-02-01")
        self.assertEqual(extract_date("3.29-国内线下"), "2026-03-29")
        self.assertEqual(extract_variant("1.21新托福真题C卷"), "C")
        self.assertEqual(extract_variant("4.5 套二 听力"), "S2")
        self.assertEqual(extract_variant("3.14-国内线下-合集"), "OFFLINE-CN")
        self.assertIsNone(extract_variant("ListeningModule2"))

    def test_full_paper_infers_all_sections(self):
        row = classify_file(Path("1.21新托福真题A卷/新托福真题01.pdf"))
        self.assertTrue(row["is_full_paper"])
        self.assertEqual(set(row["sections"]), {"reading", "listening", "speaking", "writing"})
        self.assertEqual(row["section_evidence"], "inferred_full_paper")

    def test_inventory_groups_duplicates_and_marks_complete_exam(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "1.21新托福真题A卷"
            duplicate = root / "备份" / "1.21新托福真题A卷"
            first.mkdir(parents=True)
            duplicate.mkdir(parents=True)

            paper_bytes = b"sample full paper"
            (first / "新托福真题01.pdf").write_bytes(paper_bytes)
            (duplicate / "新托福真题01.pdf").write_bytes(paper_bytes)
            (first / "新托福真题01ListeningModule1.mp3").write_bytes(b"audio-listening")
            (first / "新托福真题01Speaking.mp3").write_bytes(b"audio-speaking")
            (first / "新托福真题01参考答案.pdf").write_bytes(b"answers")

            inventory = build_inventory(
                root,
                probe_pdfs=False,
                probe_media_files=False,
                workers=1,
            )

        self.assertEqual(inventory["summary"]["unique_exam_count"], 1)
        self.assertEqual(inventory["summary"]["duplicate_group_count"], 1)
        exam = inventory["exams"][0]
        self.assertEqual(exam["exam_key"], "2026-01-21-A")
        self.assertEqual(exam["source_dir_count"], 2)
        self.assertEqual(exam["duplicate_copy_count"], 1)
        self.assertEqual(exam["sections"]["reading"]["status"], "ready")
        self.assertEqual(exam["sections"]["listening"]["status"], "ready")
        self.assertEqual(exam["sections"]["speaking"]["status"], "ready")
        self.assertEqual(exam["sections"]["writing"]["status"], "ready")
        self.assertEqual(exam["answer_files"], 1)

    def test_repeated_date_subdirectories_collapse_and_question_ranges_are_not_dates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            exam_root = root / "3.25"
            repeated = exam_root / "3.25 套一 听力"
            repeated.mkdir(parents=True)
            (exam_root / "3.25 套一 阅读.docx").write_bytes(b"reading")
            (repeated / "Listening_Questions_9-10.mp3").write_bytes(b"audio")

            official = root / "Teacher Practice Test"
            official.mkdir()
            (official / "Conversation_Questions_11-12.ogg").write_bytes(b"official")

            inventory = build_inventory(
                root,
                probe_pdfs=False,
                probe_media_files=False,
                workers=1,
            )

        self.assertEqual(inventory["summary"]["unique_exam_count"], 1)
        exam = inventory["exams"][0]
        self.assertEqual(exam["exam_key"], "2026-03-25-S1")
        self.assertEqual(exam["source_dir_count"], 1)
        self.assertIn(
            "Teacher Practice Test/Conversation_Questions_11-12.ogg",
            inventory["unmatched_relevant_files"],
        )

    def test_generated_dated_collections_remain_unmatched(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            generated = root / "wechat_toefl" / "data" / "2026-04-18"
            generated.mkdir(parents=True)
            (generated / "口语整理.md").write_text("sample", encoding="utf-8")

            inventory = build_inventory(
                root,
                probe_pdfs=False,
                probe_media_files=False,
                workers=1,
            )

        self.assertEqual(inventory["summary"]["unique_exam_count"], 0)
        self.assertIn(
            "wechat_toefl/data/2026-04-18/口语整理.md",
            inventory["unmatched_relevant_files"],
        )


if __name__ == "__main__":
    unittest.main()
