"""统一工作台的访客空状态、公开路由与目录能力回归。"""

import unittest
from unittest.mock import patch

from app import app


class PracticeWorkspaceRegressionTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_public_catalog_routes_are_unchanged(self):
        expected = {
            "/practice": "practice_library",
            "/listening/tests": "listening_test_index",
            "/reading/tests": "reading_test_index",
            "/listening/jijing": "listening_jijing_index",
            "/reading/jijing": "reading_jijing_index",
        }
        rules = {rule.rule: rule.endpoint for rule in app.url_map.iter_rules()}

        for path, endpoint in expected.items():
            self.assertEqual(rules.get(path), endpoint)

    def test_unbound_student_has_no_continue_strip_or_route_error(self):
        with patch("app._current_practice_student_profile", return_value=None):
            for path in (
                "/listening/tests",
                "/reading/tests",
                "/listening/jijing",
                "/reading/jijing",
            ):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn(
                        '<section class="practice-workspace__continue"',
                        response.get_data(as_text=True),
                    )

    def test_workspace_keeps_hash_study_and_nine_score_catalog_hooks(self):
        listening = self.client.get("/listening/tests").get_data(as_text=True)
        reading = self.client.get("/reading/tests").get_data(as_text=True)

        self.assertIn('data-book-target="cambridge-12"', listening)
        self.assertIn('data-book-target="jfdr-6"', listening)
        self.assertIn('data-book-target="cambridge-12"', reading)
        self.assertIn("data-reading-study-test=", reading)
        self.assertIn('src="/static/js/practice_workspace.js"', listening)
        self.assertIn('src="/static/js/practice_workspace.js"', reading)


if __name__ == "__main__":
    unittest.main()
