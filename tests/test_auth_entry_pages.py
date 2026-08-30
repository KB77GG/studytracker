import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import app


class AuthEntryPageTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_login_page_keeps_compatible_form_and_entry_links(self):
        response = self.client.get("/login?next=/practices")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('action="/login"', page)
        self.assertIn('name="username"', page)
        self.assertIn('name="password"', page)
        self.assertIn('name="next" value="/practices"', page)
        self.assertIn('aria-label="显示密码"', page)
        self.assertIn('href="/practices"', page)
        self.assertIn('href="/classroom"', page)
        self.assertIn('brand/auth-staircase-hero.png', page)

    def test_login_error_remains_visible_and_accessible(self):
        with patch("app.User") as user:
            user.query.filter_by.return_value.first.return_value = None
            response = self.client.post(
                "/login",
                data={"username": "__invalid__", "password": "__invalid__"},
            )

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('role="alert"', page)
        self.assertIn("用户名或密码不正确，或账号已被停用。", page)

    def test_practices_gate_keeps_name_verification_contract(self):
        with patch("app._listening_exercise_usage_map", return_value={}):
            response = self.client.get("/practices")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn('action="/api/listening/verify"', page)
        self.assertIn('id="studentVerifyForm"', page)
        self.assertIn('name="name"', page)
        self.assertIn('placeholder="请输入姓名"', page)
        self.assertIn('id="mainContent" style="display:none"', page)
        self.assertIn('role="alert"', page)
        self.assertIn('href="/login?next=/practices"', page)
        self.assertIn('brand/auth-staircase-hero.png', page)
        self.assertIn('data-practice-hub="section"', page)
        self.assertIn('practice_shell.js', page)

    def test_practices_verify_rejects_a_missing_name(self):
        response = self.client.post("/api/listening/verify", json={"name": ""})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "missing_name")

    def test_practices_verify_keeps_success_session_contract(self):
        profile = SimpleNamespace(full_name="测试学员")
        with patch("app.StudentProfile") as student_profile, patch(
            "app.Task"
        ) as task, patch("app.or_", return_value=True):
            student_profile.query.filter_by.return_value.first.return_value = profile
            task.query.filter.return_value.count.return_value = 3

            response = self.client.post(
                "/api/listening/verify",
                json={"name": " 测试学员 "},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"ok": True, "name": "测试学员", "task_count": 3},
        )
        with self.client.session_transaction() as session:
            self.assertEqual(session["practice_student_name"], "测试学员")


if __name__ == "__main__":
    unittest.main()
