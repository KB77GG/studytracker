import unittest

from services.practice_navigation import navigation_defaults, safe_local_target


class PracticeNavigationPolicyTest(unittest.TestCase):
    def test_safe_local_target_keeps_only_same_site_paths(self):
        self.assertEqual(
            safe_local_target("/tasks?student_name=A#today", "/practice"),
            "/tasks?student_name=A#today",
        )
        for unsafe in (
            "https://example.com/tasks",
            "//example.com/tasks",
            "javascript:alert(1)",
            "\\evil\\path",
            "/practice\nLocation:https://example.com",
        ):
            with self.subTest(unsafe=unsafe):
                self.assertEqual(safe_local_target(unsafe, "/practice"), "/practice")

    def test_identity_modes_have_distinct_stable_module_exits(self):
        student = navigation_defaults(
            authenticated=True,
            role="student",
            classroom_mode=False,
            verified_student=True,
        )
        staff = navigation_defaults(
            authenticated=True,
            role="assistant",
            classroom_mode=False,
            verified_student=False,
        )
        classroom = navigation_defaults(
            authenticated=False,
            role=None,
            classroom_mode=True,
            verified_student=False,
        )
        public_student = navigation_defaults(
            authenticated=False,
            role=None,
            classroom_mode=False,
            verified_student=True,
        )

        self.assertEqual((student.identity_mode, student.module_exit_url), ("student_account", "/student/today"))
        self.assertEqual((staff.identity_mode, staff.module_exit_url), ("staff", "/"))
        self.assertEqual((classroom.identity_mode, classroom.module_exit_url), ("classroom", "/login"))
        self.assertEqual((public_student.identity_mode, public_student.module_exit_url), ("verified_student", "/login"))


if __name__ == "__main__":
    unittest.main()
