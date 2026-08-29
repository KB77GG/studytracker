import unittest

from app import app


class PracticeNavigationRouteTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_public_catalogs_return_to_practice_without_staff_login_guard(self):
        for path in (
            "/listening/tests",
            "/reading/tests",
            "/listening/jijing",
            "/reading/jijing",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.get_data(as_text=True)
                self.assertIn('data-practice-module-back', html)
                self.assertIn('href="/practice"', html)
                self.assertNotIn('>返回首页</a>', html)

    def test_practice_root_exposes_guest_and_verified_student_identity_modes(self):
        guest_html = self.client.get("/practice").get_data(as_text=True)
        self.assertIn('data-practice-hub="root"', guest_html)
        self.assertIn('"identity_mode": "guest"', guest_html)

        with self.client.session_transaction() as browser_session:
            browser_session["practice_student_name"] = "Navigation Test Student"
        student_html = self.client.get("/practice").get_data(as_text=True)
        self.assertIn('"identity_mode": "verified_student"', student_html)

    def test_login_keeps_only_a_local_return_target(self):
        safe_html = self.client.get("/login?next=/student/today").get_data(as_text=True)
        self.assertIn('name="next" value="/student/today"', safe_html)

        unsafe_html = self.client.get(
            "/login?next=https://example.com/steal"
        ).get_data(as_text=True)
        self.assertNotIn('name="next"', unsafe_html)


if __name__ == "__main__":
    unittest.main()
