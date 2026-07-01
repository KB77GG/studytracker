import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import (
    PLAN_RESOURCE_DICTATION,
    _plan_category_for_resource,
    _plan_item_review_task_name,
    can_review_student_submission,
)
from models import User


class TaskReviewPermissionTest(unittest.TestCase):
    def test_dictation_shadow_task_uses_word_dictation_label(self):
        self.assertEqual(
            _plan_category_for_resource(
                "材料练习",
                PLAN_RESOURCE_DICTATION,
                "dictation_book:7",
            ),
            ("词汇", "词汇", "单词默写"),
        )
        item = SimpleNamespace(
            resource_type=PLAN_RESOURCE_DICTATION,
            resource_id="dictation_book:7",
            task_name="材料练习",
        )

        self.assertEqual(_plan_item_review_task_name(item), "单词默写")

    def test_assistant_can_review_any_student_in_shared_queue(self):
        assistant = SimpleNamespace(role=User.ROLE_ASSISTANT)

        self.assertTrue(can_review_student_submission(assistant, student_id=999))

    def test_admin_can_review_any_student(self):
        admin = SimpleNamespace(role=User.ROLE_ADMIN)

        self.assertTrue(can_review_student_submission(admin, student_id=999))

    def test_teacher_remains_limited_to_linked_students(self):
        teacher = SimpleNamespace(role=User.ROLE_TEACHER)

        with patch("app.get_accessible_student_ids", return_value={7, 8}):
            self.assertTrue(can_review_student_submission(teacher, student_id=7))
            self.assertFalse(can_review_student_submission(teacher, student_id=999))


if __name__ == "__main__":
    unittest.main()
