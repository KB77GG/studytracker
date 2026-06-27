from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.organize_toefl_materials import (
    build_library,
    canonical_rank,
    imported_exam_ids,
    support_category,
)


class OrganizeToeflMaterialsTest(unittest.TestCase):
    def test_canonical_rank_prefers_top_level_over_nested_copy(self):
        top = "3.17新托福真题/3.17阅读.pdf"
        nested = "1.21新托福真题C卷/3.17新托福真题/3.17阅读.pdf"
        self.assertLess(canonical_rank(top), canonical_rank(nested))

    def test_support_categories_exclude_temp_but_keep_official_unassigned(self):
        self.assertEqual(support_category("tmp/pdfs/a.pdf")[0], "excluded")
        self.assertEqual(
            support_category("wechat_toefl/data/2026-03-21/summary.md")[0],
            "06_采集归档",
        )
        self.assertEqual(
            support_category("test 4/teacher-practice-test-2-audio-file.zip")[0],
            "07_官方待对应素材",
        )
        self.assertEqual(
            support_category(
                "新版托福考试官方指南（OG）/Audio_Video Files/"
                "Chapter 3_Audio/Chapter 3 - Track 01.mp3"
            )[0],
            "08_官方指南章节素材",
        )

    def test_imported_exam_ids_prefers_inventory_key_and_normalizes_separators(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            practice_root = Path(temp_dir)
            exam_dir = practice_root / "2026-01-21_A"
            exam_dir.mkdir()
            (exam_dir / "manifest.json").write_text(
                '{"source_kind":"real_exam","id":"2026-01-21_A",'
                '"inventory_exam_key":"2026-01-21-A"}',
                encoding="utf-8",
            )
            self.assertEqual(imported_exam_ids(practice_root), {"2026-01-21-A"})

    def test_build_library_creates_links_and_omits_duplicate_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            output = root / "organized"
            source.mkdir()
            exam_dir = source / "3.17新托福真题"
            nested_dir = source / "1.21新托福真题C卷" / "3.17新托福真题"
            exam_dir.mkdir()
            nested_dir.mkdir(parents=True)
            (exam_dir / "3.17阅读.pdf").write_bytes(b"same")
            (nested_dir / "3.17阅读.pdf").write_bytes(b"same")
            (source / "评分标准").mkdir()
            (source / "评分标准" / "rubric.pdf").write_bytes(b"rubric")

            inventory = {
                "exams": [{
                    "exam_key": "2026-03-17",
                    "exam_date": "2026-03-17",
                    "variant": "default",
                    "source_dirs": ["3.17新托福真题", "1.21新托福真题C卷/3.17新托福真题"],
                    "sections": {
                        "reading": {"status": "ready"},
                        "listening": {"status": "missing"},
                        "speaking": {"status": "missing"},
                        "writing": {"status": "missing"},
                    },
                    "asset_complete": False,
                    "has_ocr_blocker": False,
                    "import_candidate": False,
                    "partial_markers": [],
                }],
                "files": [
                    {
                        "exam_key": "2026-03-17",
                        "path": "3.17新托福真题/3.17阅读.pdf",
                        "name": "3.17阅读.pdf",
                        "sha256": "0967115f2813a3541eaef77de9d9d5776d0381c63a523b92763e29b5d34418e0",
                        "kind": "document",
                        "sections": ["reading"],
                        "is_answer": False,
                        "is_transcript": False,
                        "is_full_paper": False,
                    },
                    {
                        "exam_key": "2026-03-17",
                        "path": "1.21新托福真题C卷/3.17新托福真题/3.17阅读.pdf",
                        "name": "3.17阅读.pdf",
                        "sha256": "0967115f2813a3541eaef77de9d9d5776d0381c63a523b92763e29b5d34418e0",
                        "kind": "document",
                        "sections": ["reading"],
                        "is_answer": False,
                        "is_transcript": False,
                        "is_full_paper": False,
                    },
                ],
                "duplicates": [{
                    "sha256": "0967115f2813a3541eaef77de9d9d5776d0381c63a523b92763e29b5d34418e0",
                    "copy_count": 2,
                    "reclaimable_bytes": 4,
                    "exam_keys": ["2026-03-17"],
                    "paths": [
                        "1.21新托福真题C卷/3.17新托福真题/3.17阅读.pdf",
                        "3.17新托福真题/3.17阅读.pdf",
                    ],
                }],
                "unclassified_dated_collections": [],
                "unmatched_relevant_files": ["评分标准/rubric.pdf"],
            }
            result = build_library(
                source,
                output,
                inventory,
                {"sources": [], "file_records": [], "file_duplicate_groups": []},
                {},
                set(),
            )

            link = output / "01_真题套卷" / "2026-03-17" / "01_阅读" / "3.17阅读.pdf"
            self.assertTrue(link.is_symlink())
            self.assertEqual(
                result["catalog"]["summary"]["duplicate_omitted_count"],
                1,
            )
            support_links = list((output / "03_辅助资料" / "03_评分标准").rglob("rubric.pdf"))
            self.assertEqual(len(support_links), 1)
            self.assertTrue(support_links[0].is_symlink())


if __name__ == "__main__":
    unittest.main()
