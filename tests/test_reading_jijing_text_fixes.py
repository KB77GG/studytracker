"""Tests for the manual jijing passage text fixes (stdlib only).

Run standalone:
    python -m unittest tests.test_reading_jijing_text_fixes -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import reading_jijing_text_fixes as fixes_mod  # noqa: E402

FIX = {"passage_id": "p1", "paragraph_label": "A", "find": 'these."Manu', "replace": 'these." Manu'}


class ApplyFixTest(unittest.TestCase):
    def test_single_occurrence_is_replaced(self):
        text, changed = fixes_mod.apply_fix('such as these."Manufacturers are', FIX)
        self.assertEqual(text, 'such as these." Manufacturers are')
        self.assertTrue(changed)

    def test_already_applied_is_skipped(self):
        text, changed = fixes_mod.apply_fix('such as these." Manufacturers are', FIX)
        self.assertEqual(text, 'such as these." Manufacturers are')
        self.assertFalse(changed)

    def test_missing_text_raises(self):
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_fix("completely different text", FIX)

    def test_multiple_occurrences_raise(self):
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_fix('these."Manu and these."Manu', FIX)

    def test_unknown_paragraph_raises(self):
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_passage_fixes("p1", [{"label": "B", "text": "x"}], {"p1": [FIX]})

    def test_passage_fixes_apply_in_place(self):
        paragraphs = [{"label": "A", "text": 'as these."Manufacturers'}]
        changed = fixes_mod.apply_passage_fixes("p1", paragraphs, {"p1": [FIX]})
        self.assertEqual(changed, 1)
        self.assertEqual(paragraphs[0]["text"], 'as these." Manufacturers')


class RepositoryStateTest(unittest.TestCase):
    def test_every_fix_is_applied_to_static_files(self):
        fixes = fixes_mod.load_fixes()
        self.assertTrue(fixes)
        self.assertEqual(fixes_mod.patch_static_files(fixes, write=False), 0)

    def test_fix_reasons_are_known(self):
        reasons = {
            "missing_space_between_sentences",
            "missing_space",
            "stray_leading_period",
            "typo",
        }
        for passage_fixes in fixes_mod.load_fixes().values():
            for fix in passage_fixes:
                with self.subTest(fix=fix["find"]):
                    self.assertIn(fix["reason"], reasons)
                    self.assertNotEqual(fix["find"], fix["replace"])
                    # Otherwise an applied fix still matches and a rerun applies it twice.
                    self.assertNotIn(fix["find"], fix["replace"])


if __name__ == "__main__":
    unittest.main()
