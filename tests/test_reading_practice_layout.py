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
        self.assertIn(
            ".choice-stack { display: grid; gap: 8px; width: 100%; min-width: 0; }",
            self.template,
        )


if __name__ == "__main__":
    unittest.main()
