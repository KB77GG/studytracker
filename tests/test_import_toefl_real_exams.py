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

    def test_listening_parser_recovers_common_ocr_markers(self):
        prompt, options = MODULE.parse_listening_candidate([
            "Choose the best response.",
            "O My door is always open.",
            "= 6 oO There should be enough storage space.",
            "> ©) Ineed to look up the hours online.",
            "© The campus bookstore has great reviews.",
            "1",
        ])
        self.assertEqual(prompt, "")
        self.assertEqual(options, [
            "My door is always open.",
            "There should be enough storage space.",
            "I need to look up the hours online.",
            "The campus bookstore has great reviews.",
        ])

    def test_listening_parser_recovers_missing_radio_marker(self):
        _, options = MODULE.parse_listening_candidate([
            "What topic will most likely be discussed at a symposium?",
            "© Designing club T-shirts",
            "© Installing additional recycling bins",
            "后 Creating a club webpage",
            "© What refreshments to offer",
        ])
        self.assertEqual(options, [
            "Designing club T-shirts",
            "Installing additional recycling bins",
            "Creating a club webpage",
            "What refreshments to offer",
        ])

    def test_listening_parser_removes_navigation_suffixes(self):
        _, options = MODULE.parse_listening_candidate([
            "Choose the best response.",
            "O I have a group study session then.",
            "O They work well together.",
            "O Probably on the weekend.",
            "O Last week was quite eventful. Review A Module1 - Router",
        ])
        self.assertEqual(options[-1], "Last week was quite eventful.")

        _, options = MODULE.parse_listening_candidate([
            "What is the woman looking for?",
            "O A new cookbook",
            "O A food item",
            "O A gift for her brother",
            "O A recipe for a meal Listening | Questions of 15 00:00:17",
        ])
        self.assertEqual(options[-1], "A recipe for a meal")


if __name__ == "__main__":
    unittest.main()
