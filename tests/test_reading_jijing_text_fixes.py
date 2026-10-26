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


class QuestionFixTest(unittest.TestCase):
    """Fixes marked "questions" also edit the passage's quoted question data."""

    FIX = {**FIX, "find": "(\x001.9", "replace": "($1.9", "questions": True}

    def groups(self):
        return [
            {"title": "t (\x001.9 trillion)", "questions": [{"central_sentences": ["(\x001.9 x"]}]}
        ]

    def test_paragraph_and_question_copies_are_fixed(self):
        paragraphs, groups = [{"label": "A", "text": "yuan (\x001.9 trillion)"}], self.groups()
        changed = fixes_mod.apply_passage_fixes("p1", paragraphs, {"p1": [self.FIX]}, groups)
        self.assertEqual(changed, 1)
        self.assertEqual(paragraphs[0]["text"], "yuan ($1.9 trillion)")
        self.assertEqual(groups[0]["title"], "t ($1.9 trillion)")
        self.assertEqual(groups[0]["questions"][0]["central_sentences"], ["($1.9 x"])
        again = fixes_mod.apply_passage_fixes("p1", paragraphs, {"p1": [self.FIX]}, groups)
        self.assertEqual(again, 0)

    def test_question_only_fix(self):
        fix = {**self.FIX, "paragraph_label": None}
        groups = self.groups()
        self.assertEqual(fixes_mod.apply_passage_fixes("p1", [], {"p1": [fix]}, groups), 1)
        self.assertEqual(fixes_mod.apply_passage_fixes("p1", [], {"p1": [fix]}, groups), 0)
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_passage_fixes("p1", [], {"p1": [fix]}, [{"title": "unrelated"}])

    def test_fix_without_questions_flag_leaves_question_data(self):
        paragraphs, groups = [{"label": "A", "text": "yuan (\x001.9 trillion)"}], self.groups()
        fix = {key: value for key, value in self.FIX.items() if key != "questions"}
        fixes_mod.apply_passage_fixes("p1", paragraphs, {"p1": [fix]}, groups)
        self.assertEqual(groups, self.groups())

    def test_question_data_matches_whole_words_only(self):
        groups = [{"title": "out side and the out sidecar"}]
        self.assertEqual(fixes_mod.replace_in_place(groups, "out side", "outside"), (1, True))
        self.assertEqual(groups[0]["title"], "outside and the out sidecar")
        groups = [{"analysis": "根据Pridcaux的模型"}]
        fixes_mod.replace_in_place(groups, "Pridcaux", "Prideaux")
        self.assertEqual(groups[0]["analysis"], "根据Prideaux的模型")

    def test_curly_apostrophe_copy_is_fixed(self):
        fix = {**FIX, "find": "China's the rise", "replace": "China's rise", "questions": True}
        paragraphs = [{"label": "A", "text": "in China's the rise"}]
        groups = [{"title": "(China’s the rise"}, {"title": "China's the rise"}]
        fixes_mod.apply_passage_fixes("p1", paragraphs, {"p1": [fix]}, groups)
        self.assertEqual([g["title"] for g in groups], ["(China’s rise", "China's rise"])

    def test_exact_fix_replaces_whole_strings_only(self):
        fix = {**FIX, "paragraph_label": None, "find": "catching", "replace": "caching"}
        fix.update(questions=True, exact=True)
        groups = [{"synonym": "catching", "sentence": "seed catching behaviour"}]
        self.assertEqual(fixes_mod.apply_passage_fixes("p1", [], {"p1": [fix]}, groups), 1)
        self.assertEqual(groups, [{"synonym": "caching", "sentence": "seed catching behaviour"}])
        self.assertEqual(fixes_mod.apply_passage_fixes("p1", [], {"p1": [fix]}, groups), 0)
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_passage_fixes("p1", [], {"p1": [{**fix, "paragraph_label": "A"}]}, [])


class SummaryFixTest(unittest.TestCase):
    """summary fixes edit the paragraph's Chinese summary, not its text."""

    FIX = {**FIX, "find": "中的CO浓度", "replace": "中的二氧化碳浓度", "summary": True}

    def test_summary_is_fixed_and_paragraph_kept(self):
        content = {"summary": "{'A': '大气中的CO浓度将增加'}", "paragraphs": []}
        content["paragraphs"].append({"label": "A", "text": "CO2 levels"})
        fixes = {"p1": [self.FIX]}
        changed = fixes_mod.apply_passage_fixes("p1", content["paragraphs"], fixes, [], content)
        self.assertEqual(changed, 1)
        self.assertEqual(content["summary"], "{'A': '大气中的二氧化碳浓度将增加'}")
        self.assertEqual(content["paragraphs"][0]["text"], "CO2 levels")
        self.assertEqual(fixes_mod.apply_passage_fixes("p1", [], fixes, [], content), 0)
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_passage_fixes("p1", [], fixes, [], {"summary": "无关"})

    def test_summary_fix_cannot_edit_question_data(self):
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_passage_fixes("p1", [], {"p1": [{**self.FIX, "questions": True}]}, [])


class AtEndFixTest(unittest.TestCase):
    """at_end fixes add a missing final full stop, where find is part of replace."""

    FIX = {**FIX, "find": "own good", "replace": "own good.", "at_end": True}

    def test_appends_once(self):
        text, changed = fixes_mod.apply_fix("too posh for its own good", self.FIX)
        self.assertEqual((text, changed), ("too posh for its own good.", True))
        self.assertEqual(fixes_mod.apply_fix(text, self.FIX), (text, False))

    def test_only_matches_the_paragraph_end(self):
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_fix("its own good is here", self.FIX)

    def test_cannot_edit_question_data(self):
        paragraphs = [{"label": "A", "text": "its own good"}]
        with self.assertRaises(fixes_mod.TextFixError):
            fixes_mod.apply_passage_fixes(
                "p1", paragraphs, {"p1": [{**self.FIX, "questions": True}]}, []
            )


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
            "lost_character",
            "punctuation",
            "typo",
        }
        for passage_fixes in fixes_mod.load_fixes().values():
            for fix in passage_fixes:
                with self.subTest(fix=fix["find"]):
                    self.assertIn(fix["reason"], reasons)
                    self.assertNotEqual(fix["find"], fix["replace"])
                    if fix.get("at_end"):
                        self.assertFalse(fix.get("questions"))
                        self.assertTrue(fix["replace"].startswith(fix["find"]))
                        continue
                    # Otherwise an applied fix still matches and a rerun applies it twice.
                    self.assertNotIn(fix["find"], fix["replace"])


if __name__ == "__main__":
    unittest.main()
