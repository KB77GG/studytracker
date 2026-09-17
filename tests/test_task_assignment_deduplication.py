import unittest
from types import SimpleNamespace

from services.task_assignment_duplicates import (
    check_duplicate_assignments,
    resource_identity_from_payload,
    validate_publish_conflicts,
)


def task(student_name, *, status="pending", date="2026-09-01", payload=None, **fields):
    values = {
        "id": fields.pop("id", 1),
        "student_name": student_name,
        "status": status,
        "date": date,
        "student_submitted": fields.pop("student_submitted", False),
        "submitted_at": fields.pop("submitted_at", None),
        "actual_seconds": fields.pop("actual_seconds", 0),
        "review_status": fields.pop("review_status", None),
        "plan_item": fields.pop("plan_item", None),
        "category": fields.pop("category", "雅思-听力-题型专项"),
        "detail": fields.pop("detail", "题型专项"),
        "grading_mode": fields.pop("grading_mode", None),
        "question_ids": payload,
        "listening_exercise_id": fields.pop("listening_exercise_id", None),
        "listening_resource_type": fields.pop("listening_resource_type", None),
        "reading_test_id": fields.pop("reading_test_id", None),
        "reading_passage_number": fields.pop("reading_passage_number", None),
        "dictation_book_id": fields.pop("dictation_book_id", None),
        "dictation_word_start": fields.pop("dictation_word_start", 1),
        "dictation_word_end": fields.pop("dictation_word_end", None),
        "speaking_book_id": fields.pop("speaking_book_id", None),
        "speaking_phrase_start": fields.pop("speaking_phrase_start", 1),
        "speaking_phrase_end": fields.pop("speaking_phrase_end", None),
        "material_id": fields.pop("material_id", None),
    }
    values.update(fields)
    return SimpleNamespace(**values)


class TaskAssignmentDuplicateServiceTest(unittest.TestCase):
    def qtype(
        self,
        student="学生甲",
        groups=None,
        status="pending",
        task_id=1,
        task_date="2026-09-01",
        **fields,
    ):
        payload = {
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": groups or ["reading:test-1:passage-1:judgment:1-2"],
        }
        return task(
            student,
            status=status,
            payload=__import__("json").dumps(payload, ensure_ascii=False),
            grading_mode="question_type_practice",
            id=task_id,
            date=task_date,
            **fields,
        )

    def test_completed_same_group_is_warning_and_requires_explicit_reason(self):
        existing = self.qtype(status="done")
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": ["reading:test-1:passage-1:judgment:1-2"],
        }
        preview = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
        self.assertEqual(preview["students"][0]["status_label"], "已布置")
        self.assertEqual(preview["students"][0]["matches"][0]["overlap_type"], "exact")
        self.assertTrue(preview["requires_confirmation"])
        blocked = validate_publish_conflicts(["学生甲"], request, tasks=[existing])
        self.assertFalse(blocked["can_publish"])

        allowed = validate_publish_conflicts(
            ["学生甲"], request, force_repeat=True, confirmed=True, force_reason="错题复训", tasks=[existing]
        )
        self.assertTrue(allowed["can_publish"])

    def test_in_progress_exact_group_is_blocking(self):
        existing = self.qtype(status="progress")
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": ["reading:test-1:passage-1:judgment:1-2"],
        }
        preview = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
        self.assertTrue(preview["blocking"])
        self.assertFalse(preview["can_publish"])

    def test_earlier_unfinished_question_group_is_visible_but_directly_reassignable(self):
        group_id = "reading:test-1:passage-1:judgment:1-2"
        existing = self.qtype(
            status="progress",
            task_date="2026-09-16",
            groups=[group_id],
        )
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": [group_id],
            "due_date": "2026-09-17",
        }

        preview = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
        match = preview["students"][0]["matches"][0]
        self.assertTrue(preview["has_history"])
        self.assertFalse(preview["blocking"])
        self.assertFalse(preview["requires_confirmation"])
        self.assertTrue(preview["can_publish"])
        self.assertTrue(match["reassignable"])
        self.assertEqual(match["status_label"], "进行中")
        self.assertEqual(match["assignment_date_relation"], "earlier")
        self.assertEqual(match["view_url"], "/tasks/question-types/1/result")
        self.assertEqual(preview["excluded_group_ids"], [])
        self.assertTrue(validate_publish_conflicts(["学生甲"], request, tasks=[existing])["can_publish"])

        auto_selection = check_duplicate_assignments(
            ["学生甲"],
            {
                "source": "question_type",
                "subject": "reading",
                "standard_type": "judgment",
                "due_date": "2026-09-17",
            },
            tasks=[existing],
        )
        self.assertEqual(auto_selection["excluded_group_ids"], [])
        self.assertEqual(
            auto_selection["students"][0]["matches"][0]["overlap_units"],
            [group_id],
        )

    def test_same_later_missing_and_invalid_dates_keep_unfinished_group_protected(self):
        group_id = "reading:test-1:passage-1:judgment:1-2"
        existing = self.qtype(
            status="progress",
            task_date="2026-09-17",
            groups=[group_id],
        )
        base = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": [group_id],
        }
        for due_date in ("2026-09-17", "2026-09-16", "", "not-a-date"):
            request = {**base, "due_date": due_date}
            result = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
            self.assertTrue(result["blocking"], due_date)
            self.assertTrue(result["requires_confirmation"], due_date)
            self.assertEqual(result["excluded_group_ids"], [group_id], due_date)

        auto_selection = check_duplicate_assignments(
            ["学生甲"],
            {
                "source": "question_type",
                "subject": "reading",
                "standard_type": "judgment",
                "due_date": "2026-09-17",
            },
            tasks=[existing],
        )
        self.assertEqual(auto_selection["excluded_group_ids"], [group_id])

        allowed = validate_publish_conflicts(
            ["学生甲"],
            {**base, "due_date": "2026-09-17"},
            force_repeat=True,
            confirmed=True,
            force_reason="人工确认复训",
            tasks=[existing],
        )
        self.assertTrue(allowed["can_publish"])
        self.assertTrue(allowed["forced"])

    def test_submitted_signal_is_not_misclassified_as_unfinished_cross_day(self):
        group_id = "reading:test-1:passage-1:judgment:1-2"
        existing = self.qtype(
            status="progress",
            task_date="2026-09-16",
            groups=[group_id],
            student_submitted=True,
        )
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": [group_id],
            "due_date": "2026-09-17",
        }
        result = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
        match = result["students"][0]["matches"][0]
        self.assertEqual(match["status"], "submitted")
        self.assertFalse(match["reassignable"])
        self.assertFalse(result["blocking"])
        self.assertTrue(result["requires_confirmation"])
        self.assertFalse(validate_publish_conflicts(["学生甲"], request, tasks=[existing])["can_publish"])

    def test_question_type_matrix_keeps_all_matching_task_records(self):
        group_id = "reading:test-1:passage-1:judgment:1-2"
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": [group_id],
            "due_date": "2026-09-18",
        }
        result = check_duplicate_assignments(
            ["学生甲"],
            request,
            tasks=[
                self.qtype(task_id=2, task_date="2026-09-17", groups=[group_id]),
                self.qtype(task_id=1, task_date="2026-09-16", groups=[group_id]),
            ],
        )
        row = result["matrix_rows"][0]
        self.assertEqual([match["task_id"] for match in row["matches"]], [2, 1])
        self.assertEqual(row["match"]["task_id"], 2)
        self.assertFalse(row["blocking"])

    def test_non_question_type_force_repeat_policy_is_unchanged(self):
        existing = task(
            "学生甲",
            status="pending",
            date="2026-09-17",
            dictation_book_id=3,
            dictation_word_start=1,
            dictation_word_end=20,
        )
        request = {
            "dictation_book_id": 3,
            "dictation_word_start": 1,
            "dictation_word_end": 20,
            "due_date": "2026-09-18",
        }
        blocked = validate_publish_conflicts(["学生甲"], request, tasks=[existing])
        self.assertFalse(blocked["can_publish"])
        allowed = validate_publish_conflicts(
            ["学生甲"],
            request,
            force_repeat=True,
            confirmed=True,
            force_reason="人工确认",
            tasks=[existing],
        )
        self.assertTrue(allowed["can_publish"])

    def test_different_group_ids_are_not_duplicates(self):
        existing = self.qtype(groups=["reading:test-1:passage-1:judgment:3-4"])
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": ["reading:test-1:passage-1:judgment:1-2"],
        }
        result = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
        self.assertEqual(result["students"][0]["status"], "not_assigned")
        self.assertFalse(result["has_history"])

    def test_multiple_students_show_only_the_student_with_history(self):
        existing = self.qtype(student="学生甲", status="done")
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": ["reading:test-1:passage-1:judgment:1-2"],
        }
        result = check_duplicate_assignments(["学生甲", "学生乙"], request, tasks=[existing])
        self.assertEqual([row["status"] for row in result["students"]], ["assigned", "not_assigned"])
        self.assertEqual(result["students"][0]["matches"][0]["task_id"], 1)

    def test_question_type_returns_complete_student_by_group_matrix(self):
        group_one = "reading:test-1:passage-1:judgment:1-2"
        group_two = "reading:test-1:passage-1:judgment:3-4"
        result = check_duplicate_assignments(
            ["学生甲", "学生乙"],
            {
                "source": "question_type",
                "subject": "reading",
                "standard_type": "judgment",
                "group_ids": [group_one, group_two],
                "unit_labels": {group_one: "剑雅 Test 1 · Passage 1 · G1", group_two: "剑雅 Test 1 · Passage 1 · G2"},
            },
            tasks=[self.qtype(student="学生甲", groups=[group_one], status="done")],
        )
        self.assertEqual(
            [unit["id"] for unit in result["resource"]["units"]], [group_one, group_two]
        )
        self.assertEqual(len(result["matrix_rows"]), 4)
        matrix = {
            (row["student_name"], row["unit_id"]): row for row in result["matrix_rows"]
        }
        self.assertEqual(result["students"][0]["matches"][0]["overlap_type"], "partial")
        self.assertEqual(matrix[("学生甲", group_one)]["status_label"], "已完成")
        self.assertEqual(matrix[("学生甲", group_one)]["overlap_type"], "exact")
        self.assertEqual(matrix[("学生甲", group_one)]["match"]["task_id"], 1)
        self.assertEqual(matrix[("学生甲", group_two)]["status_label"], "未布置")
        self.assertEqual(matrix[("学生乙", group_one)]["status_label"], "未布置")
        self.assertEqual(matrix[("学生乙", group_two)]["status_label"], "未布置")
        self.assertEqual(matrix[("学生甲", group_one)]["unit_label"], "剑雅 Test 1 · Passage 1 · G1")

    def test_partial_group_overlap_lists_only_the_intersection(self):
        existing = self.qtype(groups=["group-a", "group-b"], status="done")
        request = {
            "source": "question_type",
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": ["group-b", "group-c"],
        }
        result = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
        match = result["students"][0]["matches"][0]
        self.assertEqual(match["overlap_type"], "partial")
        self.assertEqual(match["overlap_units"], ["group-b"])

    def test_listening_reading_material_and_dictation_ranges(self):
        cases = [
            (
                {"listening_exercise_id": "ielts10_test1", "listening_resource_type": "cambridge_test", "listening_section_number": 2},
                task("学生甲", listening_exercise_id="ielts10_test1", listening_resource_type="cambridge_test", payload='{"listening_section_number": 2}', id=2),
                "exact",
            ),
            (
                {"reading_test_id": "reading-21-1", "reading_passage_number": 1, "question_ids": ["1", "2"]},
                task("学生甲", reading_test_id="reading-21-1", reading_passage_number=1, payload='["2", "3"]', id=3),
                "partial",
            ),
            (
                {"material_id": 9, "question_ids": ["7", "8"]},
                task("学生甲", material_id=9, payload='["8", "9"]', id=4),
                "partial",
            ),
            (
                {"dictation_book_id": 3, "dictation_word_start": 10, "dictation_word_end": 20},
                task("学生甲", dictation_book_id=3, dictation_word_start=18, dictation_word_end=25, id=5),
                "partial",
            ),
        ]
        for request, existing, expected in cases:
            result = check_duplicate_assignments(["学生甲"], request, tasks=[existing])
            self.assertEqual(result["students"][0]["matches"][0]["overlap_type"], expected)

    def test_freeform_is_never_labelled_as_not_assigned(self):
        identity = resource_identity_from_payload({"source": "custom"})
        self.assertFalse(identity["certain"])
        result = check_duplicate_assignments(["学生甲"], {"source": "custom"}, tasks=[])
        self.assertEqual(result["students"][0]["status_label"], "无法自动判断")
