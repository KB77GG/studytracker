"""Real route/Jinja coverage for batch-two navigation, using synthetic identities.

Run through the private SQLite runner; these assertions do not execute browser JS
or claim browser layout/back-history verification.
"""

import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app import app
from models import StudentProfile, User, db
from tests.test_practice_center_batch1 import Elements


class PracticeNavigationBatch2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.student_name = "导航回归合成学生"
        cls.parent_name = "导航回归合成家长"
        with app.app_context():
            student = User(
                username="navigation_batch2_synthetic_student",
                display_name=cls.student_name,
                password_hash="synthetic-unused-hash",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            teacher = User(
                username="navigation_batch2_synthetic_teacher",
                display_name="导航回归合成教师",
                password_hash="synthetic-unused-hash",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            parent = User(
                username="navigation_batch2_synthetic_parent",
                display_name=cls.parent_name,
                password_hash="synthetic-unused-hash",
                role=User.ROLE_PARENT,
                is_active=True,
            )
            db.session.add_all([student, teacher, parent])
            db.session.flush()
            profile = StudentProfile(user_id=student.id, full_name=cls.student_name)
            db.session.add(profile)
            db.session.commit()
            cls.student_id, cls.teacher_id, cls.profile_id = student.id, teacher.id, profile.id
            cls.parent_id = parent.id

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            StudentProfile.query.filter_by(id=cls.profile_id).delete()
            User.query.filter(User.id.in_([cls.student_id, cls.teacher_id, cls.parent_id])).delete(
                synchronize_session=False
            )
            db.session.commit()

    def setUp(self):
        self.client = app.test_client()

    def account(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def verified(self):
        with self.client.session_transaction() as session:
            session["practice_student_name"] = self.student_name

    def page(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get_data(as_text=True)

    def shared_header(self, html, *, back=True):
        headers = re.findall(
            r'<header[^>]*data-practice-workspace-header[^>]*>(.*?)</header>',
            html,
            re.S,
        )
        self.assertEqual(len(headers), 1)
        header = headers[0]
        elements = Elements(header)
        self.assertEqual(len(elements.with_attr("data-practice-module-back")), int(back))
        self.assertEqual(len(elements.with_attr("data-practice-module-exit")), 1)
        brand = elements.with_attr("data-practice-home")
        self.assertEqual(len(brand), 1)
        self.assertEqual(brand[0]["href"], "/practice")
        self.assertNotIn("data-practice-module-back", brand[0])
        self.assertIn('brand/sagepath-mark.png', header)
        self.assertIn("Sage Path</span>", header)
        nav = re.search(r'<nav[^>]*>(.*?)</nav>', header, re.S).group(1)
        self.assertEqual(
            re.findall(r'>([^<>]+)</a>', nav),
            ["练习中心", "听力", "阅读", "写作", "题型专项"],
        )
        return header

    def test_guest_center_has_one_brand_and_no_self_back(self):
        html = self.page("/practice")
        header = self.shared_header(html, back=False)
        self.assertIn("未确认身份", header)
        self.assertIn("<title>练习中心 · Sage Path</title>", html)
        self.assertEqual(re.findall(r'<h1[^>]*>(.*?)</h1>', html), ["练习中心"])
        self.assertIn('id="practiceIdentityForm"', html)
        self.assertIn('id="practiceAssignedTasks"', html)
        self.assertFalse(Elements(html).with_class("practice-suite-preview"))

    def test_verified_name_survives_catalog_render_and_navigation_defaults(self):
        self.verified()
        html = self.page("/reading/tests")
        header = self.shared_header(html)
        self.assertIn("学生：" + self.student_name, header)
        self.assertIn('"identity_mode": "verified_student"', html)
        self.assertEqual(
            Elements(header).with_attr("data-practice-module-exit")[0]["href"],
            "/login",
        )

    def test_parent_without_verified_student_never_appears_as_student_identity(self):
        self.account(self.parent_id)
        for path in ("/practice", "/listening/tests", "/reading/tests", "/practices"):
            with self.subTest(path=path):
                html = self.page(path)
                header = self.shared_header(html, back=path != "/practice")
                self.assertIn("未确认身份", header)
                self.assertNotIn(self.parent_name, header)
                self.assertNotIn("学生：", header)
                self.assertIn('"identity_mode": "guest"', html)

    def test_parent_verified_session_displays_child_instead_of_parent_account(self):
        self.account(self.parent_id)
        self.verified()
        for path in ("/practice", "/listening/tests", "/reading/tests", "/practices"):
            with self.subTest(path=path):
                html = self.page(path)
                header = self.shared_header(html, back=path != "/practice")
                self.assertIn("学生：" + self.student_name, header)
                self.assertNotIn(self.parent_name, header)
                self.assertIn('"identity_mode": "verified_student"', html)

    def test_classroom_keeps_browsing_and_hides_student_gate_and_management(self):
        with self.client.session_transaction() as session:
            session["classroom_unlocked"] = True
        html = self.page("/practices")
        header = self.shared_header(html)
        self.assertIn("课堂模式", header)
        self.assertIn("退出课堂刷题", header)
        self.assertIn("员工登录", header)
        self.assertNotIn('id="loginGate"', html)
        self.assertFalse(Elements(html).with_class("js-delete-exercise"))
        self.assertFalse(Elements(html).with_class("action-assign"))
        self.assertNotIn('href="/listening/upload"', html)

    def test_student_account_uses_shared_center_and_question_type_header(self):
        self.account(self.student_id)
        for path in ("/practice", "/practice/question-types"):
            with self.subTest(path=path):
                html = self.page(path)
                header = self.shared_header(html, back=path != "/practice")
                self.assertIn("学生：" + self.student_name, header)
                self.assertIn('"identity_mode": "student_account"', html)
                self.assertEqual(
                    Elements(header).with_attr("data-practice-module-exit")[0]["href"],
                    "/student/today",
                )
                self.assertFalse(Elements(html).with_class("app-shell"))
                self.assertEqual(len(re.findall(r'<h1(?:\s|>)', html)), 1)

    def test_teacher_center_retains_staff_shell_and_assignment_tools(self):
        self.account(self.teacher_id)
        html = self.page("/practice")
        elements = Elements(html)
        self.assertFalse(elements.with_attr("data-practice-workspace-header"))
        self.assertTrue(elements.with_class("admin-suite-v2"))
        self.assertTrue(elements.with_class("practice-suite-preview"))
        self.assertTrue(elements.with_class("practice-suite-filters"))
        self.assertEqual(len(elements.with_attr("data-practice-target-index")), 4)
        self.assertIn("查看学生练习记录", html)
        self.assertIn("布置给学生", html)

    def test_teacher_intensive_catalog_keeps_management_and_staff_exit(self):
        self.account(self.teacher_id)
        html = self.page("/practices")
        header = self.shared_header(html)
        elements = Elements(html)
        self.assertIn("教师 · 导航回归合成教师", header)
        self.assertIn("返回工作台", header)
        self.assertIn("退出登录", header)
        self.assertNotIn('id="loginGate"', html)
        self.assertIn('href="/listening/upload"', html)
        self.assertTrue(elements.with_class("js-delete-exercise"))
        self.assertTrue(elements.with_class("action-assign"))

    def test_all_workbench_catalogs_have_one_back_brand_and_page_h1(self):
        self.verified()
        for path, title in (
            ("/listening/tests", "剑雅听力"),
            ("/reading/tests", "剑雅阅读"),
            ("/listening/jijing", "听力机经"),
            ("/reading/jijing", "阅读机经"),
            ("/writing/", "写作范文与打字训练"),
            ("/writing/topics", "大作文母题库"),
            ("/practice/sprint/listening", "听力考前冲刺"),
            ("/practice/sprint/reading", "阅读考前冲刺"),
        ):
            with self.subTest(path=path):
                html = self.page(path)
                self.shared_header(html)
                self.assertEqual(re.findall(r'<h1[^>]*>(.*?)</h1>', html), [title])
                self.assertRegex(html, r'<title>[^<]+ · Sage Path</title>')

    def test_empty_catalogs_still_have_page_titles_and_one_return(self):
        for path, loader, title in (
            ("/listening/tests", "app._listening_test_catalog", "剑雅听力"),
            ("/reading/tests", "app._reading_test_catalog", "剑雅阅读"),
            ("/reading/jijing", "app._reading_jijing_catalog", "阅读机经"),
        ):
            with self.subTest(path=path), patch(loader, return_value=[]):
                html = self.page(path)
                self.shared_header(html)
                self.assertEqual(re.findall(r'<h1[^>]*>(.*?)</h1>', html), [title])
                self.assertFalse(Elements(html).with_attr("data-book-panel"))
        with TemporaryDirectory(prefix="navigation-empty-catalog-") as empty:
            with patch("app._listening_jijing_root", return_value=Path(empty)):
                html = self.page("/listening/jijing")
        self.shared_header(html)
        self.assertEqual(re.findall(r'<h1[^>]*>(.*?)</h1>', html), ["听力机经"])
        self.assertFalse(Elements(html).with_attr("data-book-panel"))

    def test_intensive_aliases_have_one_header_identity_gate_and_no_overview(self):
        for path in ("/practices", "/listening"):
            with self.subTest(path=path):
                html = self.page(path)
                self.shared_header(html)
                elements = Elements(html)
                self.assertFalse(elements.with_class("auth-entry__brandbar"))
                self.assertIn('id="studentVerifyForm"', html)
                self.assertIn('action="/api/listening/verify"', html)
                self.assertIn('id="practiceIntensiveIdentitySwitch"', html)
                self.assertNotIn('id="newTasksList"', html)
                self.assertNotIn('id="practiceHistoryList"', html)
                self.assertNotIn("loadPracticeOverview", html)
                self.assertNotIn("/api/practice/tasks", html)
                self.assertNotIn("/api/practice/history", html)
                self.assertIn("/practice#practiceAssignedTasks", html)

    def test_regular_login_retains_its_original_brand_header(self):
        html = self.page("/login")
        elements = Elements(html)
        self.assertEqual(len(elements.with_class("auth-entry__brandbar")), 1)
        self.assertFalse(elements.with_attr("data-practice-workspace-header"))
        self.assertIn('action="/login"', html)


if __name__ == "__main__":
    unittest.main()
