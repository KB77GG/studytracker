import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MockExamTemplateIsolationTest(unittest.TestCase):
    def test_listening_draft_is_scoped_to_exam_session(self):
        template = (ROOT / "templates/listening/test_practice.html").read_text(encoding="utf-8")
        self.assertIn("${examContext.session_token}_listening_", template)
        self.assertIn("if (examContext) return;", template)
        self.assertIn("localStorage.removeItem(storageKey);", template)

    def test_reading_skips_practice_history_and_restores_only_session_draft(self):
        template = (ROOT / "templates/reading/test_practice.html").read_text(encoding="utf-8")
        self.assertIn("${examContext.session_token}_reading_", template)
        self.assertIn("if (examContext) return;", template)
        self.assertIn("restoreExamDraft();", template)
        self.assertIn("localStorage.removeItem(examDraftStorageKey);", template)

    def test_review_template_renders_question_and_source_context(self):
        template = (ROOT / "templates/admin/mock_exam_session_detail.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("题干：", template)
        self.assertIn("对应原文", template)
        self.assertIn("完整听力原文", template)
        self.assertIn("完整原文", template)

    def test_review_template_renders_writing_task_image(self):
        template = (ROOT / "templates/admin/mock_exam_session_detail.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("writing_tasks[index].image_src", template)
        self.assertIn("题目图表 · 点击查看原图", template)


if __name__ == "__main__":
    unittest.main()
