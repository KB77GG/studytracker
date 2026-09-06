import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READING_PRACTICE_TEMPLATE = ROOT / "templates/reading/test_practice.html"


class ReadingPracticeLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = READING_PRACTICE_TEMPLATE.read_text(encoding="utf-8")

    def test_answer_column_cannot_consume_the_question_column(self):
        self.assertIn(
            "grid-template-columns: minmax(0, 1fr) minmax(180px, 42%);",
            self.template,
        )
        self.assertIn(".question-row > * { min-width: 0; }", self.template)
        self.assertNotIn(
            "grid-template-columns: minmax(0, 1fr) minmax(180px, auto);",
            self.template,
        )

    def test_choice_questions_stack_below_the_question_text(self):
        self.assertIn(
            ".question-row:has(.choice-stack) { grid-template-columns: minmax(0, 1fr); }",
            self.template,
        )

    def test_desktop_splitter_is_accessible_resizable_and_hidden_for_exam(self):
        css = (ROOT / "static/css/practice_shell.css").read_text(encoding="utf-8")
        self.assertIn('id="readingSplitter"', self.template)
        self.assertIn('role="separator"', self.template)
        self.assertIn('aria-orientation="vertical"', self.template)
        self.assertIn('aria-valuemin="38"', self.template)
        self.assertIn('aria-valuemax="62"', self.template)
        self.assertIn("function initReadingSplitter()", self.template)
        self.assertIn('["ArrowLeft", "ArrowRight", "Home"]', self.template)
        self.assertIn("body.practice-reading-page.exam-mode .reading-splitter { display: none; }", css)
        self.assertIn(".reading-splitter { display: none; }", css)

    def test_question_navigation_is_grouped_and_focuses_each_control_kind(self):
        self.assertIn('class="question-nav__group"', self.template)
        self.assertIn('class="question-nav__chips"', self.template)
        self.assertIn("let questionNavigationRevision = 0;", self.template)
        self.assertIn("if (navigationRevision !== questionNavigationRevision) return;", self.template)
        self.assertIn("questionNavigationRevision += 1;", self.template)
        self.assertIn("function focusQuestionControl(id)", self.template)
        self.assertIn('answerRoot.matches("input, select, textarea, button")', self.template)
        self.assertIn('answerRoot.querySelector("input:not(:disabled), select:not(:disabled)', self.template)
        self.assertIn(
            ".choice-stack { display: grid; gap: 8px; width: 100%; min-width: 0; }",
            self.template,
        )

    def test_filtered_passage_keeps_its_source_number_in_bottom_navigation(self):
        self.assertIn("const passageNumber = passage.passage ?? index + 1;", self.template)
        self.assertIn("const passageLabel = `Passage ${passageNumber}`;", self.template)
        self.assertIn("P${escapeHtml(passageNumber)}", self.template)


if __name__ == "__main__":
    unittest.main()
