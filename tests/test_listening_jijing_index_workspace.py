"""听力机经目录共享工作台的路由、Part 链接与进度回归测试。"""

import json
import unittest
from unittest.mock import patch

from app import _listening_jijing_root, app


def _catalog():
    return json.loads((_listening_jijing_root() / "catalog.json").read_text(encoding="utf-8"))


class ListeningJijingIndexWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_workspace_groups_every_book_and_keeps_every_part_link(self):
        catalog = _catalog()
        books = catalog["books"]
        parts = [
            part
            for book in books
            for test in book.get("tests") or []
            for part in test.get("parts") or []
        ]

        response = self.client.get("/listening/jijing")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn("data-practice-workspace", html)
        self.assertIn('href="/reading/jijing"', html)
        self.assertIn('href="/listening/tests"', html)
        self.assertIn('data-book-target="xiahuar-1"', html)
        self.assertIn("虾滑听力", html)
        self.assertEqual(html.count("data-book-target="), len(books))
        self.assertEqual(
            html.count(
                'class="practice-workspace__test-card practice-workspace__test-card--jijing'
            ),
            sum(len(book.get("tests") or []) for book in books),
        )
        for part in parts:
            self.assertIn(f'href="/listening/jijing/{part["id"]}"', html)

    def test_completed_part_keeps_status_accuracy_and_book_progress(self):
        first_part = _catalog()["books"][0]["tests"][0]["parts"][0]
        statuses = {
            first_part["id"]: {
                "accuracy": 91,
                "submitted_at": "2026-07-14T10:00:00",
            }
        }

        with patch("app._listening_jijing_status_map", return_value=statuses):
            response = self.client.get("/listening/jijing")
        html = response.get_data(as_text=True)

        self.assertIn("已刷 · 91%", html)
        self.assertIn("1/4", html)

    def test_legacy_shell_and_inline_style_are_removed(self):
        html = self.client.get("/listening/jijing").get_data(as_text=True)

        self.assertNotIn("listening-library__header", html)
        self.assertNotIn("listening-collection-nav", html)
        self.assertNotIn("<style>\n.page", html)
        self.assertIn('src="/static/js/practice_workspace.js"', html)


if __name__ == "__main__":
    unittest.main()
