"""听力整卷目录工作台页面的路由与链接回归测试。"""

import unittest

from app import _listening_test_catalog, app


class ListeningTestIndexWorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_workspace_renders_catalog_and_existing_practice_links(self):
        response = self.client.get("/listening/tests")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('data-listening-workspace', html)
        self.assertIn('data-book-target="cambridge-20"', html)
        self.assertIn('data-book-target="jfdr-6"', html)
        self.assertIn('href="/listening/test/ielts20_test1"', html)
        self.assertIn('href="/listening/test/ielts20_test1?section=1"', html)
        self.assertIn('href="/listening/ielts20_test1_s1"', html)
        self.assertIn('href="/listening/jijing"', html)

    def test_every_catalog_test_keeps_whole_and_section_actions(self):
        response = self.client.get("/listening/tests")
        html = response.get_data(as_text=True)
        books = _listening_test_catalog()
        expected_tests = sum(len(book["tests"]) for book in books)
        expected_parts = sum(
            test["section_count"]
            for book in books
            for test in book["tests"]
        )

        self.assertEqual(html.count('class="listening-workspace__test-card'), expected_tests)
        self.assertEqual(html.count('class="listening-workspace__full-practice"'), expected_tests)
        self.assertEqual(html.count('class="listening-workspace__part"'), expected_parts)

    def test_workspace_assets_are_served(self):
        script = self.client.get("/static/js/listening_test_index.js")
        logo = self.client.get("/static/brand/sagepath-mark.png")
        try:
            self.assertEqual(script.status_code, 200)
            self.assertEqual(logo.status_code, 200)
        finally:
            script.close()
            logo.close()


if __name__ == "__main__":
    unittest.main()
