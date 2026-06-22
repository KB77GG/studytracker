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
        self.assertIn("startSelectedGroupPlan()", logic)
        self.assertIn("finishCurrentGroup()", logic)
        self.assertIn("awaitingNextGroup", logic)


if __name__ == "__main__":
    unittest.main()
