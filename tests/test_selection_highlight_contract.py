import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SelectionHighlightContractTest(unittest.TestCase):
    def test_dynamic_option_feedback_does_not_change_highlight_fingerprint(self):
        highlighter = (ROOT / "static/js/selection-highlight.js").read_text()
        match = re.search(
            r"var EXCLUDE_SELECTOR = \[(?P<selectors>.*?)\]\.join\(','\);",
            highlighter,
            re.DOTALL,
        )

        self.assertIsNotNone(match, "highlight exclusion list must remain explicit")
        selectors = match.group("selectors")
        self.assertIn("'.option-feedback'", selectors)

        listening = (ROOT / "templates/listening/test_practice.html").read_text()
        self.assertIn('data-hl-root="listening-questions"', listening)
        self.assertIn('class="option-feedback"', listening)
        self.assertIn("feedbackNode.textContent = state.label", listening)


if __name__ == "__main__":
    unittest.main()
