"""Student Practices route-to-rendering contract regression tests."""

import unittest
from pathlib import Path

from app import app

ROOT = Path(__file__).resolve().parents[1]


class PracticeInteractionE2ETest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_student_route_chain_uses_one_return_and_save_contract(self):
        pages = {
            "/practice": "PracticeShell.installListContext",
            "/listening/tests": "PracticeShell.installListContext",
            "/listening/test/ielts7_test2?section=1": "data-practice-back",
            "/listening/ielts7_test2_s1": "data-practice-save-status",
            "/reading/test/ielts7_test2_reading": "data-reading-pane-button",
            "/listening/jijing/jijing_5_test_24_part_1_1671": "data-practice-back",
        }
        for path, marker in pages.items():
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(marker, response.get_data(as_text=True))

    def test_practice_pages_share_renderer_shell_and_review_controls(self):
        for path in (
            "/listening/test/ielts7_test2?section=1",
            "/reading/test/ielts7_test2_reading",
        ):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn('js/practice_shell.js', html)
                self.assertIn('js/practice_renderers.js', html)
                self.assertIn('data-review-action="expand"', html)
                self.assertIn('data-review-action="wrong"', html)
                self.assertIn('id="questionNav"', html)
                self.assertIn('id="toggleQuestionFlag"', html)

    def test_intensive_listening_declares_the_central_mode(self):
        html = self.client.get("/listening/ielts17_test1_s1").get_data(as_text=True)
        self.assertIn("js/practice_modes.js", html)
        self.assertIn("intensiveListeningMode: true", html)

    def test_layout_contract_has_independent_reading_panes_and_non_absolute_form_fields(self):
        css = (ROOT / "static/css/practice_shell.css").read_text(encoding="utf-8")
        renderers = (ROOT / "static/js/practice_renderers.js").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: minmax(0, 56fr) minmax(420px, 44fr);", css)
        self.assertIn("overflow: auto;", css)
        self.assertIn("object-fit: contain;", css)
        self.assertIn('data-renderer="form-completion"', renderers)
        self.assertNotIn("position: absolute", css[css.index(".practice-form {"):css.index(".matching-workspace {")])

    def test_return_contract_does_not_depend_on_history_back(self):
        source = (ROOT / "static/js/practice_shell.js").read_text(encoding="utf-8")
        for field in (
            "sourcePath",
            "sourceSearchParams",
            "studentId",
            "activeTab",
            "filters",
            "page",
            "scrollPosition",
            "sourceMode",
        ):
            self.assertIn(field, source)
        self.assertNotIn("history.back(", source)
        self.assertIn('assign(win, targetKind === "module" ? moduleExitUrl(context, win.location.origin) : contextUrl(context, win.location.origin))', source)
        self.assertIn('practice_return', source)
        self.assertIn('practice_exit', source)


if __name__ == "__main__":
    unittest.main()
