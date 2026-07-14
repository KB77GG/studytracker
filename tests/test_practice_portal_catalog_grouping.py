"""刷题门户按题库分组后的入口与非 IELTS 区域回归测试。"""

import unittest
from unittest.mock import patch

from app import app


class PracticePortalCatalogGroupingTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_ielts_catalogs_keep_all_five_direct_entries(self):
        response = self.client.get("/practice")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertEqual(html.count('class="practice-subject"'), 3)
        self.assertIn('class="practice-subject__name">剑雅真题</h3>', html)
        self.assertIn('class="practice-subject__tag">含 9 分达人</span>', html)
        self.assertIn('class="practice-subject__name">机经</h3>', html)
        self.assertIn('class="practice-subject__name">精听</h3>', html)

        for path in (
            "/listening/tests",
            "/reading/tests",
            "/listening/jijing",
            "/reading/jijing",
            "/listening",
        ):
            self.assertEqual(html.count(f'href="{path}"'), 1)

    def test_toefl_tasks_and_identity_sections_remain_available(self):
        response = self.client.get("/practice")
        html = response.get_data(as_text=True)

        self.assertIn('id="practiceAssignedTasks"', html)
        self.assertIn('id="practiceIdentityForm"', html)
        self.assertIn('id="toeflPractice"', html)
        self.assertIn('href="/toefl/tests"', html)

    def test_guest_identity_gate_remains_enabled(self):
        response = self.client.get("/practice")
        html = response.get_data(as_text=True)

        self.assertIn('data-practice-staff-mode="0"', html)
        self.assertIn('id="practiceIdentityForm"', html)
        self.assertIn("请先输入学生姓名，再进入刷题。", html)

    def test_classroom_mode_still_bypasses_student_binding(self):
        with (
            patch("app._practice_staff_mode", return_value=True),
            patch("app._practice_staff_label", return_value="课堂讲题"),
            patch("app._practice_staff_hint", return_value="只做本地判分"),
        ):
            response = self.client.get("/practice")
        html = response.get_data(as_text=True)

        self.assertIn('data-practice-staff-mode="1"', html)
        self.assertIn('data-staff-name="课堂讲题"', html)
        self.assertIn('data-staff-hint="只做本地判分"', html)
        self.assertIn('id="practiceIdentityForm" hidden', html)


if __name__ == "__main__":
    unittest.main()
