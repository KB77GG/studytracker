import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_toefl_real_exams.py"
SPEC = importlib.util.spec_from_file_location("import_toefl_real_exams", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class ImportToeflRealExamsTest(unittest.TestCase):
    def test_online_exam_id_preserves_variant(self):
        self.assertEqual(MODULE.online_exam_id("2026-03-23-s1"), "2026-03-23_S1")
        self.assertEqual(
            MODULE.online_exam_id("2026-03-21-offline-cn"),
            "2026-03-21_OFFLINE_CN",
        )

    def test_repair_scramble_adds_missing_answer_tokens(self):
        repaired, changed = MODULE.repair_scramble(
            ["you", "going"],
            ["Are", "you", "going", "?"],
        )
        self.assertTrue(changed)
        self.assertIn("Are", repaired)

    def test_interview_questions_keeps_question_prompts(self):
        prompts = MODULE.interview_questions(
            ["Welcome. What do you study? Why did you choose it?"]
        )
        self.assertEqual(len(prompts), 2)


if __name__ == "__main__":
    unittest.main()
