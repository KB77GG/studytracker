import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DictationGroupingMarkupTest(unittest.TestCase):
    def test_group_selection_and_between_group_summary_are_wired(self):
        markup = (
            ROOT / "miniprogram/pages/student/dictation/practice/index.wxml"
        ).read_text(encoding="utf-8")
        logic = (
            ROOT / "miniprogram/pages/student/dictation/practice/index.js"
        ).read_text(encoding="utf-8")

        self.assertIn("这次想怎么分组", markup)
        self.assertIn("selectedGroupPlanKey", markup)
        self.assertIn("phase === 'group_summary'", markup)
        self.assertIn('bindtap="continueNextGroup"', markup)
        self.assertIn('wx:if="{{!finished}}"', markup)
        self.assertIn('loading="{{isSubmitting || isAdvancingWord}}"', markup)
        self.assertIn("startSelectedGroupPlan()", logic)
        self.assertIn("finishCurrentGroup(", logic)
        self.assertIn("awaitingNextGroup", logic)
        self.assertIn("!this.data.finished", logic)
        self.assertIn("isFinalPracticeWord()", logic)
        self.assertIn("this.finishPractice();", logic)
        self.assertIn("wordAdvanceLocked", logic)
        self.assertIn("recoverMissingTaskWords", logic)
        self.assertIn("recoveryMissingWordIds", logic)

    def test_spelling_drill_guards_navigation_and_recovers_missing_queue_items(self):
        markup = (
            ROOT / "miniprogram/pages/student/dictation/spell/index.wxml"
        ).read_text(encoding="utf-8")
        logic = (
            ROOT / "miniprogram/pages/student/dictation/spell/index.js"
        ).read_text(encoding="utf-8")

        self.assertIn("isAdvancingWord", markup)
        self.assertIn("wordAdvanceLocked", logic)
        self.assertIn("recoverMissingTaskWords", logic)
        self.assertIn("missingQueueItems", logic)

    def test_english_pages_use_shared_keyboard_and_compatibility_input_only(self):
        practice_markup = (
            ROOT / "miniprogram/pages/student/dictation/practice/index.wxml"
        ).read_text(encoding="utf-8")
        practice_logic = (
            ROOT / "miniprogram/pages/student/dictation/practice/index.js"
        ).read_text(encoding="utf-8")
        spell_markup = (
            ROOT / "miniprogram/pages/student/dictation/spell/index.wxml"
        ).read_text(encoding="utf-8")
        spell_logic = (
            ROOT / "miniprogram/pages/student/dictation/spell/index.js"
        ).read_text(encoding="utf-8")

        self.assertIn('maxlength="-1"', practice_markup)
        self.assertIn("english-keyboard", practice_markup)
        self.assertIn("!isEnglishSpelling || inputMode === 'compatible'", practice_markup)
        self.assertIn("refocusAnswerInput", practice_logic)
        self.assertIn("inputFocus: false", practice_logic)
        self.assertIn("english-keyboard", spell_markup)
        self.assertIn("inputMode === 'compatible'", spell_markup)
        self.assertNotIn("refocusHiddenInput", spell_logic)
        self.assertNotIn("hidden-input", spell_markup)


if __name__ == "__main__":
    unittest.main()
