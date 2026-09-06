import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QuestionTypeCatalogUiContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            ROOT / "templates/question_type_practice/student_index.html"
        ).read_text(encoding="utf-8")

    def test_start_action_lives_once_in_the_persistent_selection_bar(self):
        self.assertEqual(self.source.count('id="qtStart"'), 1)
        bar_start = self.source.index('<div class="qt-selection-bar"')
        panel_end = self.source.index("</section>", bar_start)
        bar_markup = self.source[bar_start:panel_end]
        self.assertIn('id="qtSelectionSummary"', bar_markup)
        self.assertIn('id="qtClear"', bar_markup)
        self.assertIn('id="qtStart"', bar_markup)
        self.assertIn(".qt-selection-bar{position:fixed", self.source)

    def test_catalog_auto_refresh_has_only_an_error_retry_control(self):
        self.assertNotIn('id="qtPreview"', self.source)
        self.assertIn('id="qtRetry" type="button" hidden', self.source)
        self.assertIn("retryButton.addEventListener('click',loadCatalog)", self.source)
        self.assertIn("scope.addEventListener('change',loadCatalog)", self.source)
        self.assertIn("setStatus('无法读取题库：'+error.message,{retry:true})", self.source)

    def test_bottom_bar_reserves_content_space_and_honors_mobile_safe_area(self):
        self.assertIn("env(safe-area-inset-bottom)", self.source)
        self.assertIn(
            ".qt-preview{padding:16px 18px calc(104px + env(safe-area-inset-bottom))}",
            self.source,
        )
        self.assertIn(
            ".qt-preview{padding:14px 14px calc(132px + env(safe-area-inset-bottom))}",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
