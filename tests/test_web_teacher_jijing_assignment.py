import unittest
from pathlib import Path

from api.teacher_practice_catalog import (
    build_listening_jijing_assignment,
    build_listening_jijing_options,
    build_reading_jijing_catalog,
)

ROOT = Path(__file__).resolve().parents[1]


class WebTeacherJijingAssignmentTest(unittest.TestCase):
    def test_xiahuar_web_picker_exposes_all_assignable_parts(self):
        listening_root = ROOT / "static" / "listening_jijing"

        options = build_listening_jijing_options(listening_root)

        self.assertEqual(len(options), 113)
        self.assertTrue(all(option["resource_type"] == "jijing" for option in options))
        self.assertEqual(options[0]["id"], "xiahuar_001_p1")
        self.assertIn("虾滑听力", options[0]["title"])
        self.assertIn("Asia-Pacific Tours", options[0]["title"])

    def test_xiahuar_assignment_metadata_is_canonical_and_safe(self):
        listening_root = ROOT / "static" / "listening_jijing"

        assignment = build_listening_jijing_assignment(
            listening_root,
            "xiahuar_001_p1",
        )

        self.assertEqual(assignment["id"], "xiahuar_001_p1")
        self.assertEqual(assignment["category"], "雅思-听力-虾滑")
        self.assertEqual(assignment["planned_minutes"], 15)
        self.assertIn("Asia-Pacific Tours", assignment["detail"])
        self.assertIsNone(
            build_listening_jijing_assignment(
                listening_root,
                "../xiahuar_001_p1",
            )
        )
        self.assertIsNone(
            build_listening_jijing_assignment(
                listening_root,
                "jijing_005_p1",
            )
        )

    def test_zyz_catalog_and_web_template_are_visible(self):
        reading = build_reading_jijing_catalog(ROOT / "static" / "reading_jijing")
        template = (ROOT / "templates" / "tasks.html").read_text(encoding="utf-8")

        self.assertEqual(len(reading), 57)
        self.assertIn('data-listening-filter="jijing">虾滑刷题', template)
        self.assertIn('<optgroup label="虾滑听力">', template)
        self.assertIn('<optgroup label="ZYZ 阅读">', template)
        self.assertIn("resourceType === 'jijing'", template)
        self.assertIn("学生进入虾滑网页题目完成练习", template)


if __name__ == "__main__":
    unittest.main()
