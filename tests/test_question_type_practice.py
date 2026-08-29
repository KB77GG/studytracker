import json
import unittest
from pathlib import Path

from services.question_type_practice import (
    PRACTICE_TYPE_ORDER,
    TYPE_DISPLAY_LABELS,
    TYPE_LABELS,
    LibraryRoots,
    broad_practice_type,
    build_group_index,
    build_snapshot,
    cambridge_test_numbers,
    catalog_unit_groups,
    filter_groups,
    filter_unit_groups,
    practice_type_members,
    public_snapshot,
    question_type_display_label,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIO_ROOT = Path("/Users/zhouxin/Desktop/studytracker/static/listening")


class QuestionTypePracticeServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = LibraryRoots(
            listening=ROOT / "static/listening_tests",
            reading=ROOT / "static/reading_tests",
            static=ROOT / "static",
            audio=AUDIO_ROOT if AUDIO_ROOT.exists() else ROOT / "static/listening",
        )
        cls.rows = build_group_index(cls.roots)

    def test_chinese_display_labels_cover_canonical_types_without_changing_codes(self):
        self.assertEqual(set(TYPE_LABELS), set(TYPE_DISPLAY_LABELS))
        self.assertEqual(question_type_display_label("multiple_choice_single"), "单项选择题")
        self.assertEqual(
            question_type_display_label("true_false_not_given"),
            "事实判断题（T / F / NG）",
        )
        self.assertEqual(
            question_type_display_label("yes_no_not_given"),
            "观点判断题（Y / N / NG）",
        )
        self.assertEqual(TYPE_LABELS["true_false_not_given"], "True / False / Not Given")

    def test_student_taxonomy_matches_six_broad_types_per_subject(self):
        self.assertEqual(
            PRACTICE_TYPE_ORDER["listening"],
            (
                "all",
                "completion",
                "single_choice",
                "multiple_choice",
                "map_group",
                "matching_group",
            ),
        )
        self.assertEqual(
            PRACTICE_TYPE_ORDER["reading"],
            (
                "all",
                "completion",
                "single_choice",
                "multiple_choice",
                "matching_group",
                "judgment",
            ),
        )
        self.assertEqual(question_type_display_label("completion"), "填空题")
        self.assertEqual(question_type_display_label("judgment"), "判断题")
        self.assertEqual(
            practice_type_members("reading", "judgment"),
            {"true_false_not_given", "yes_no_not_given"},
        )
        self.assertEqual(
            broad_practice_type("listening", "diagram_labelling"),
            "map_group",
        )

    def test_broad_completion_snapshot_can_keep_multiple_canonical_groups(self):
        rows = filter_groups(
            self.rows,
            subject="listening",
            standard_type="completion",
            count=20,
        )
        first_by_type = {}
        for row in rows:
            first_by_type.setdefault(row["standard_type"], row)
        selected = list(first_by_type.values())[:2]
        self.assertEqual(len(selected), 2)
        self.assertEqual(len({row["standard_type"] for row in selected}), 2)
        snapshot = build_snapshot(
            selected,
            pace="training",
            standard_type="completion",
            roots=self.roots,
        )
        self.assertEqual(snapshot["standard_type"], "completion")
        self.assertEqual(snapshot["standard_type_display_label"], "填空题")
        self.assertEqual(
            {row["standard_type"] for row in snapshot["group_refs"]},
            {row["standard_type"] for row in selected},
        )

    def test_unit_filter_keeps_every_matching_group_from_each_selected_unit(self):
        selected = filter_unit_groups(
            self.rows,
            subject="listening",
            standard_type="completion",
            scope="ielts10_test1",
            unit_count=1,
        )
        self.assertTrue(selected)
        self.assertEqual(
            len({(row["test_id"], row["unit_index"]) for row in selected}),
            1,
        )
        unit = selected[0]
        expected_ids = {
            row["question_group_id"]
            for row in self.rows
            if row["test_id"] == unit["test_id"]
            and row["unit_index"] == unit["unit_index"]
            and row["standard_type"] in practice_type_members("listening", "completion")
            and row["safety_status"] == "publishable"
        }
        self.assertEqual({row["question_group_id"] for row in selected}, expected_ids)

    def test_cambridge_catalog_is_not_capped_at_the_first_volume(self):
        selected = catalog_unit_groups(
            self.rows,
            subject="listening",
            standard_type="completion",
            scope="cambridge:all",
        )
        volumes = {
            numbers[0] for row in selected if (numbers := cambridge_test_numbers(row)) is not None
        }
        self.assertGreaterEqual(len(volumes), 10)
        self.assertIn(10, volumes)
        self.assertIn(21, volumes)
        self.assertTrue(all(row["test_id"].startswith("ielts") for row in selected))
        self.assertEqual(cambridge_test_numbers(selected[0])[0], max(volumes))

    def test_cambridge_volume_scope_returns_all_units_in_that_book(self):
        selected = catalog_unit_groups(
            self.rows,
            subject="reading",
            standard_type="all",
            scope="cambridge:21",
        )
        self.assertTrue(selected)
        self.assertEqual(
            {cambridge_test_numbers(row)[0] for row in selected},
            {21},
        )
        self.assertGreater(
            len({(row["test_id"], row["unit_index"]) for row in selected}),
            6,
        )

    def test_fixed_form_regressions_are_publishable_and_keep_semantic_structure(self):
        cases = {
            ("ielts21_test3", 1): "1-10",
            ("ielts7_test2", 1): "1-10",
        }
        for (test_id, unit_number), expected_range in cases.items():
            with self.subTest(test_id=test_id):
                row = next(
                    item
                    for item in self.rows
                    if item["test_id"] == test_id
                    and item["unit_number"] == unit_number
                    and item["original_question_range"] == expected_range
                )
                self.assertEqual(row["safety_status"], "publishable")
                self.assertIn(row["standard_type"], {"form_completion", "note_completion"})
                self.assertIn("renderForm", row["renderer"])

                snapshot = build_snapshot(
                    [row],
                    pace="training",
                    standard_type=row["standard_type"],
                    roots=self.roots,
                )
                group = snapshot["payload"]["sections"][0]["groups"][0]
                self.assertEqual(len(group["questions"]), 10)
                self.assertIn("$9000000001$", group["collect"])
                self.assertNotIn("Question 2", group["collect"])

    def test_every_detected_standard_type_has_a_representative_and_renderer(self):
        detected = {
            row["standard_type"] for row in self.rows if row["safety_status"] == "publishable"
        }
        required = {
            "form_completion",
            "note_completion",
            "table_completion",
            "flow_chart_completion",
            "sentence_completion",
            "summary_completion",
            "multiple_choice_single",
            "multiple_choice_multiple",
            "matching",
            "classification",
            "map_labelling",
            "plan_labelling",
            "diagram_labelling",
            "short_answer",
            "true_false_not_given",
            "yes_no_not_given",
            "matching_headings",
            "matching_information",
            "matching_features",
            "matching_sentence_endings",
        }
        self.assertTrue(required <= detected, required - detected)
        self.assertNotIn("unknown", detected)
        self.assertTrue(all(row["renderer"] for row in self.rows))

    def test_default_selection_excludes_manual_review_and_blocked_groups(self):
        selected = filter_groups(
            self.rows,
            subject="reading",
            standard_type="summary_completion",
            count=20,
        )
        self.assertTrue(selected)
        self.assertTrue(all(row["safety_status"] == "publishable" for row in selected))

    def test_public_snapshot_removes_solutions_but_keeps_response_shape(self):
        row = next(
            item
            for item in self.rows
            if item["subject"] == "listening"
            and item["standard_type"] == "multiple_choice_multiple"
            and item["safety_status"] == "publishable"
        )
        snapshot = build_snapshot(
            [row],
            pace="exam",
            standard_type=row["standard_type"],
            roots=self.roots,
        )
        private_text = json.dumps(snapshot["payload"], ensure_ascii=False)
        public = public_snapshot(snapshot)
        public_text = json.dumps(public["payload"], ensure_ascii=False)
        self.assertIn('"answer"', private_text)
        self.assertNotIn('"answer"', public_text)
        group = public["payload"]["sections"][0]["groups"][0]
        self.assertEqual(group.get("response_layout"), "combined_multi")
        self.assertGreaterEqual(group.get("max_selections", 0), 2)


if __name__ == "__main__":
    unittest.main()
