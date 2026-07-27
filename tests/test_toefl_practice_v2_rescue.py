import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/toefl_practice_v2/2026-01-21_A"
SCHEMA = ROOT / "schemas/toefl_practice_v2.schema.json"
SOURCE_ROOT = Path("/Users/zhouxin/Desktop/新托福资料")
Q33_ID = "toefl:2026-01-21-a:reading:m1:g06:q33"


def load_validator():
    path = ROOT / "scripts/validate_toefl_practice_v2.py"
    spec = importlib.util.spec_from_file_location("validate_toefl_practice_v2", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class ToeflPracticeV2RescueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = json.loads((PACKAGE / "content.json").read_text(encoding="utf-8"))
        cls.answer_key = json.loads(
            (PACKAGE / "answer_key.json").read_text(encoding="utf-8")
        )
        cls.manifest = json.loads(
            (PACKAGE / "manifest.json").read_text(encoding="utf-8")
        )
        cls.validator = load_validator()

    def test_reading_q33_matches_paper_page_7(self):
        question = next(
            item for item in self.content["questions"] if item["id"] == Q33_ID
        )
        self.assertEqual(
            question["prompt"],
            "What can be inferred to be the purpose of electrical signals that plants release?",
        )
        self.assertEqual(
            [item["text"] for item in question["options"]],
            [
                "To attract beneficial animals to the plants",
                "To prevent attack by caterpillars on the plants",
                "To help the plants make the best use of available resources",
                "To communicate with other plants across long distances",
            ],
        )
        self.assertEqual(
            question["source_refs"],
            [
                {
                    "path": "1.21新托福真题A卷/新托福真题01.pdf",
                    "sha256": "f88605f3f38e1f92f8d2026c7bee5e397c93b6f6fb1084c299efbd4231ca96b9",
                    "confidence": "visually_recovered",
                    "page": 7,
                    "module": "m1",
                    "question_number": 33,
                }
            ],
        )

    def test_reading_q33_answer_is_private_and_page_traced(self):
        answer = next(
            item
            for item in self.answer_key["answers"]
            if item["question_id"] == Q33_ID
        )
        self.assertEqual(answer["correct_option_keys"], ["C"])
        self.assertEqual(
            [(item["path"], item["page"]) for item in answer["evidence"]],
            [
                ("1.21新托福真题A卷/新托福真题01.pdf", 7),
                ("1.21新托福真题A卷/新托福真题01参考答案.pdf", 1),
            ],
        )
        self.assertEqual(self.validator.find_forbidden_keys(self.content), [])

    def test_staging_package_is_structurally_valid(self):
        errors, summary = self.validator.validate_package(
            PACKAGE, SCHEMA, SOURCE_ROOT
        )
        self.assertEqual(errors, [])
        self.assertEqual(summary["questions"], 120)
        self.assertEqual(summary["blocked"], 4)

    def test_release_gate_keeps_blocked_pilot_out_of_publication(self):
        errors, summary = self.validator.validate_package(PACKAGE, SCHEMA)
        self.assertEqual(errors, [])
        blockers = self.validator.release_blockers(
            self.content, self.answer_key, self.manifest, summary
        )
        self.assertIn("4 question(s) remain blocked", blockers)
        self.assertTrue(any("availability_status" in item for item in blockers))
        self.assertTrue(any("publish_status" in item for item in blockers))
        self.assertTrue(any("subject source review" in item for item in blockers))

    def test_validation_report_uses_portable_package_path(self):
        self.assertEqual(
            self.validator.portable_package_path(PACKAGE),
            "data/toefl_practice_v2/2026-01-21_A",
        )


if __name__ == "__main__":
    unittest.main()
