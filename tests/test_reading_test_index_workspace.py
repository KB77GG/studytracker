"""剑雅阅读目录共享工作台的路由与链接回归测试。"""

import unittest
from unittest.mock import patch

from app import _reading_test_catalog, app


class ReadingTestIndexWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_workspace_renders_catalog_and_existing_practice_links(self):
        response = self.client.get("/reading/tests")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("data-practice-workspace", html)
        self.assertIn("剑雅真题", html)
        self.assertIn('data-book-target="cambridge-20"', html)
        self.assertIn('href="/reading/test/ielts20_test1_reading"', html)
        self.assertIn('href="/reading/study/ielts20_test1_reading"', html)
        self.assertIn('href="/reading/jijing"', html)
        self.assertIn("READING", html)

    def test_every_catalog_test_keeps_flat_practice_and_study_actions(self):
        response = self.client.get("/reading/tests")
        html = response.get_data(as_text=True)
        expected_tests = sum(
            len(book.get("tests") or []) for book in _reading_test_catalog()
        )

        self.assertEqual(
            html.count(
                'class="practice-workspace__test-card practice-workspace__test-card--flat'
            ),
            expected_tests,
        )
        self.assertEqual(html.count("data-reading-study-test="), expected_tests)
        self.assertNotIn("<details", html)

    def test_legacy_library_shell_is_not_rendered(self):
        response = self.client.get("/reading/tests")
        html = response.get_data(as_text=True)

        self.assertNotIn("listening-library__header", html)
        self.assertNotIn("practice-library-nav", html)
        self.assertIn('src="/static/js/practice_workspace.js"', html)

    def test_completed_state_accuracy_and_continue_target_are_preserved(self):
        statuses = {
            "ielts20_test1_reading": {
                "accuracy": 81,
                "submitted_at": "2026-07-14T09:00:00",
            }
        }
        with patch("app._reading_practice_status_map", return_value=statuses):
            response = self.client.get("/reading/tests")
        html = response.get_data(as_text=True)

        self.assertIn("已完成 · 81%", html)
        self.assertIn("上次完成 — 剑雅 20 Test 1", html)
        self.assertIn('href="/reading/test/ielts20_test2_reading"', html)
        self.assertIn("继续下一套", html)


if __name__ == "__main__":
    unittest.main()
