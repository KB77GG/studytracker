"""阅读机经目录共享工作台的路由、折叠与学习入口回归测试。"""

import unittest
from unittest.mock import patch

from app import _reading_jijing_catalog, app


class ReadingJijingIndexWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_workspace_keeps_every_flat_practice_and_study_link(self):
        books = _reading_jijing_catalog()
        tests = [test for book in books for test in book.get("tests") or []]

        response = self.client.get("/reading/jijing")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("data-practice-workspace", html)
        self.assertIn('href="/listening/jijing"', html)
        self.assertIn('href="/reading/tests"', html)
        self.assertEqual(html.count("data-book-target="), len(books))
        self.assertEqual(
            html.count(
                'class="practice-workspace__test-card practice-workspace__test-card--flat'
            ),
            len(tests),
        )
        self.assertEqual(html.count("data-reading-study-test="), len(tests))
        for test in tests:
            self.assertIn(f'href="/reading/jijing/{test["id"]}"', html)

    def test_only_first_ten_groups_show_before_expanding_more(self):
        books = _reading_jijing_catalog()
        html = self.client.get("/reading/jijing").get_data(as_text=True)

        self.assertEqual(html.count("data-older-book hidden"), max(0, len(books) - 10))
        self.assertIn('data-collapsed-label="更多机经组"', html)
        self.assertIn('data-expanded-label="收起机经组"', html)

    def test_completed_state_accuracy_and_progress_are_preserved(self):
        first_test = _reading_jijing_catalog()[0]["tests"][0]
        statuses = {
            first_test["id"]: {
                "accuracy": 87,
                "submitted_at": "2026-07-14T10:00:00",
            }
        }

        with patch("app._reading_practice_status_map", return_value=statuses):
            response = self.client.get("/reading/jijing")
        html = response.get_data(as_text=True)

        self.assertIn("已完成 · 87%", html)
        self.assertIn("1/1", html)

    def test_legacy_library_shell_is_not_rendered(self):
        html = self.client.get("/reading/jijing").get_data(as_text=True)

        self.assertNotIn("listening-library__header", html)
        self.assertNotIn("practice-library-nav", html)
        self.assertIn('src="/static/js/practice_workspace.js"', html)


if __name__ == "__main__":
    unittest.main()
