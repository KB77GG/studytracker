import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SelectionHighlightContractTest(unittest.TestCase):
    def test_dynamic_grading_ui_does_not_change_highlight_fingerprint(self):
        highlighter = (ROOT / "static/js/selection-highlight.js").read_text()
        match = re.search(
            r"var EXCLUDE_SELECTOR = \[(?P<selectors>.*?)\]\.join\(','\);",
            highlighter,
            re.DOTALL,
        )

        self.assertIsNotNone(match, "highlight exclusion list must remain explicit")
        selectors = match.group("selectors")
        for selector in (
            ".option-feedback",
            ".selection-hint",
            ".review-chrome",
            ".review-card",
            ".review-summary",
            ".review-controls",
        ):
            self.assertIn(repr(selector), selectors)

        listening = (ROOT / "templates/listening/test_practice.html").read_text()
        reading = (ROOT / "templates/reading/test_practice.html").read_text()
        renderers = (ROOT / "static/js/practice_renderers.js").read_text()

        self.assertIn('data-hl-root="listening-questions"', listening)
        self.assertIn('class="option-feedback"', listening)
        self.assertIn("feedbackNode.textContent = state.label", listening)
        self.assertIn('class="selection-hint"', listening)
        self.assertIn('class="review-summary"', listening)
        self.assertIn('class="review-controls"', listening)

        self.assertIn('data-hl-root="reading-questions"', reading)
        self.assertIn('class="selection-hint"', reading)
        self.assertIn('class="review-summary"', reading)
        self.assertIn('class="review-controls"', reading)
        self.assertIn('class="review-card"', renderers)
        self.assertIn(
            'class="review-chrome" data-capability="canShowCorrectness"',
            reading,
        )
        self.assertNotIn(
            '${experienceCapabilities.canShowCorrectness ? `<section class="review-summary"',
            reading,
        )

        question_markup = re.search(
            r'document\.getElementById\("questionPanel"\)\.innerHTML = `(?P<markup>.*?)`;',
            reading,
            re.DOTALL,
        ).group("markup")
        self.assertTrue(question_markup.startswith('\n    <div class="review-chrome"'))
        self.assertIn(
            '\n    </div>\n    ${(passage.groups || []).map(renderGroup).join("")}',
            question_markup,
        )

    def test_mobile_selection_uses_a_cached_range_and_touch_retries(self):
        highlighter = (ROOT / "static/js/selection-highlight.js").read_text()

        self.assertIn("document.addEventListener('touchend'", highlighter)
        self.assertIn("document.addEventListener('selectionchange'", highlighter)
        self.assertIn("var pendingSelection = null", highlighter)
        self.assertIn("SELECTION_SNAPSHOT_TTL_MS = 1500", highlighter)
        self.assertIn("[0, 120, 320, 600].forEach", highlighter)
        self.assertIn("if (!captured) return;", highlighter)
        self.assertIn("toolbarForSelection(ready.anchor, ready.spans)", highlighter)
        self.assertIn("element.addEventListener('touchend', activate", highlighter)
        self.assertIn("event.preventDefault();\n      event.stopPropagation();", highlighter)
        self.assertIn("ex-hl-toolbar--mobile", highlighter)
        self.assertIn("-webkit-user-select: text", highlighter)

    def test_question_type_review_shares_the_live_task_highlight_scope(self):
        highlighter = (ROOT / "static/js/selection-highlight.js").read_text()
        listening = (ROOT / "templates/listening/test_practice.html").read_text()
        reading = (ROOT / "templates/reading/test_practice.html").read_text()
        routes = (ROOT / "api/question_type_practice.py").read_text()

        self.assertIn("window.__SELECTION_HIGHLIGHT_PATH__", highlighter)
        for source in (listening, reading):
            self.assertIn("practiceContext?.highlight_path", source)
            self.assertIn("practiceContext?.initial_review", source)
            self.assertIn("已加载题型专项原题与作答记录", source)
            self.assertIn("function lockReadOnlyReviewControls()", source)
            self.assertIn("practiceContext?.read_only", source)
        self.assertIn('"highlight_path": url_for(', routes)
        self.assertIn('context["initial_review"]', routes)
        self.assertIn('test=public_snapshot(snapshot)["payload"]', routes)


if __name__ == "__main__":
    unittest.main()
