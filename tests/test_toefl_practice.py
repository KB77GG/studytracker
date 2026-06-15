import unittest
import json
from types import SimpleNamespace

from toefl_practice import (
    _evaluate_listen_repeat,
    _evaluate_listen_repeat_soe,
    _manifest_is_published,
    _listening_question_is_publishable,
    _question_is_displayable,
    _question_is_gradable,
    _question_task_type,
    _submission_result_bundle,
    catalog_summary,
    exam_catalog,
    grade_exam_payload,
    public_exam_payload,
)


class ToeflPracticeTest(unittest.TestCase):
    def test_publish_gate_requires_clear_published_manifest(self):
        self.assertFalse(_manifest_is_published({}))
        self.assertFalse(_manifest_is_published({
            "publish_status": "published",
            "duplicate_status": "review_required",
        }))
        self.assertTrue(_manifest_is_published({
            "publish_status": "published",
            "duplicate_status": "clear",
        }))

    def test_catalog_contains_sample_exam(self):
        catalog = exam_catalog()
        self.assertTrue(catalog)
        sample = next(item for item in catalog if item["id"] == "2026-01-21_A")
        self.assertTrue({
            "reading",
            "listening",
            "writing",
        }.issubset({item["id"] for item in sample["subjects"]}))
        self.assertGreater(catalog_summary()["question_count"], 0)

    def test_catalog_contains_audited_official_samples(self):
        catalog = {item["id"]: item for item in exam_catalog()}
        self.assertIn("ets-practice-1", catalog)
        self.assertIn("ets-og-chapter-6", catalog)
        self.assertEqual(catalog["ets-practice-1"]["subjects"][0]["item_count"], 40)
        self.assertEqual(catalog["ets-og-chapter-6"]["subjects"][0]["item_count"], 50)

    def test_official_payload_exposes_module_timing_without_answers(self):
        payload = public_exam_payload("ets-og-chapter-6", "reading")
        self.assertEqual(payload["module_durations"], {"m1": 1200, "m2": 540})
        self.assertEqual(payload["item_count"], 50)
        self.assertTrue(all("answer" not in question for question in payload["questions"]))

    def test_public_payload_does_not_expose_answers(self):
        payload = public_exam_payload("2026-01-21_A", "reading")
        self.assertIsNotNone(payload)
        self.assertTrue(all("answer" not in question for question in payload["questions"]))
        self.assertTrue(all(question.get("options") for question in payload["questions"] if question["response_type"] == "mc"))

    def test_listening_payload_only_exposes_four_option_questions(self):
        payload = public_exam_payload("2026-04-15_S1", "listening")
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["questions"]), 47)
        self.assertTrue(all(
            len(question.get("options") or []) == 4
            for question in payload["questions"]
            if question["response_type"] == "mc"
        ))

    def test_listening_publish_gate_rejects_ocr_navigation_pollution(self):
        question = {
            "response_type": "mc",
            "options": [
                {"key": "A", "text": "A complete answer."},
                {"key": "B", "text": "Another complete answer."},
                {"key": "C", "text": "Listening Question 6 of 27 Review Back"},
                {"key": "D", "text": "The final complete answer."},
            ],
        }
        self.assertFalse(_listening_question_is_publishable(question))

    def test_objective_report_contains_type_accuracy_and_wrong_answers(self):
        payload = public_exam_payload("2026-04-15_S1", "listening")
        first = payload["questions"][0]
        result = grade_exam_payload(
            "2026-04-15_S1",
            "listening",
            {first["id"]: "A"},
        )
        self.assertGreaterEqual(result["report"]["wrong_count"], 1)
        self.assertEqual(
            result["report"]["type_breakdown"][0]["task_type"],
            "listen_and_choose",
        )
        wrong = next(
            item
            for item in result["report"]["wrong_answers"]
            if item["id"] == first["id"]
        )
        self.assertEqual(wrong["selected_answer"], "A")
        self.assertEqual(wrong["correct_answer"], "C")

    def test_old_submission_results_remain_readable(self):
        submission = SimpleNamespace(
            results_json=json.dumps([{
                "id": "legacy-q1",
                "status": "incorrect",
                "correct_items": 0,
                "total_items": 1,
                "task_type": "mc",
                "task_label": "Multiple Choice",
            }]),
            correct_count=0,
            auto_total=1,
            accuracy=0.0,
        )
        bundle = _submission_result_bundle(submission)
        self.assertEqual(len(bundle["results"]), 1)
        self.assertEqual(bundle["report"]["wrong_count"], 1)

    def test_grading_accepts_known_correct_answer(self):
        payload = public_exam_payload("2026-01-21_A", "listening")
        first = payload["questions"][0]
        result = grade_exam_payload(
            "2026-01-21_A",
            "listening",
            {first["id"]: "B"},
        )
        first_result = next(item for item in result["results"] if item["id"] == first["id"])
        self.assertEqual(first_result["status"], "correct")

    def test_grading_accepts_ordered_writing_tokens(self):
        result = grade_exam_payload(
            "2026-01-21_A",
            "writing",
            {
                "writing_2026-01-21_A_m1_q1": [
                    "do",
                    "you",
                    "know",
                    "if",
                    "the",
                    "due",
                    "dates",
                    "have",
                    "been",
                    "updated",
                    "?",
                ]
            },
        )
        first_result = next(
            item for item in result["results"]
            if item["id"] == "writing_2026-01-21_A_m1_q1"
        )
        self.assertEqual(first_result["status"], "correct")

    def test_order_questions_with_repairable_content_remain_visible(self):
        payload = public_exam_payload("2026-01-21_A", "writing")
        ids = {question["id"] for question in payload["questions"]}
        self.assertTrue(ids)

    def test_displayability_is_separate_from_gradability(self):
        question = {
            "response_type": "mc",
            "options": [{"key": "A", "text": "One"}, {"key": "B", "text": "Two"}],
            "answer": None,
        }
        self.assertTrue(_question_is_displayable(question))
        self.assertFalse(_question_is_gradable(question))

    def test_mc_answer_key_must_exist_in_visible_options(self):
        question = {
            "response_type": "mc",
            "options": [{"key": "A", "text": "One"}, {"key": "B", "text": "Two"}],
            "answer": {"keys": ["C"]},
        }
        self.assertTrue(_question_is_displayable(question))
        self.assertFalse(_question_is_gradable(question))

    def test_recording_questions_are_manual_review(self):
        question = {
            "response_type": "record",
            "directive": "Record your response.",
            "prompt": "Tell me about your hometown.",
            "answer": None,
        }
        self.assertTrue(_question_is_displayable(question))
        self.assertFalse(_question_is_gradable(question))

    def test_speaking_task_types_are_kept_separate(self):
        self.assertEqual(
            _question_task_type(
                "speaking",
                {"directive": "Listen and repeat.", "response_type": "record"},
            ),
            "listen_repeat",
        )
        self.assertEqual(
            _question_task_type(
                "speaking",
                {
                    "directive": "Answer the interviewer's question.",
                    "response_type": "record",
                },
            ),
            "interview",
        )

    def test_listen_repeat_exact_transcript_scores_five(self):
        result = _evaluate_listen_repeat(
            "Use your email address to log in.",
            "Use your email address to log in.",
            {"evidence": "test"},
        )
        self.assertEqual(result["score"], 5)
        self.assertEqual(result["alignment"]["content_recall"], 100.0)

    def test_listen_repeat_partial_transcript_is_not_over_scored(self):
        result = _evaluate_listen_repeat(
            "When you have finished, be sure to clean up the kitchen.",
            "When you have finished",
            {"evidence": "test"},
        )
        self.assertLessEqual(result["score"], 3)
        self.assertGreater(result["score"], 0)

    def test_listen_repeat_soe_uses_completion_and_accuracy(self):
        result = _evaluate_listen_repeat_soe(
            {
                "pron_accuracy": 92,
                "pron_fluency": 84,
                "pron_completion": 99,
                "suggested_score_100": 94,
                "words": [],
                "engine": "test_soe",
            },
            3.2,
        )
        self.assertEqual(result["score"], 5)
        self.assertEqual(result["grading_engine"], "test_soe")

    def test_invalid_exam_is_rejected(self):
        self.assertIsNone(public_exam_payload("../secret", "reading"))
        self.assertIsNone(public_exam_payload("2026-01-21_A", "unknown"))

    def test_fill_questions_are_scored_per_blank(self):
        payload = public_exam_payload("ets-practice-1", "reading")
        first = payload["questions"][0]
        result = grade_exam_payload(
            "ets-practice-1",
            "reading",
            {first["id"]: ["might", "wrong", "people", "only", "basic", "However", "is", "from", "record", "dancing"]},
        )
        first_result = next(item for item in result["results"] if item["id"] == first["id"])
        self.assertEqual(first_result["correct_items"], 9)
        self.assertEqual(first_result["total_items"], 10)


if __name__ == "__main__":
    unittest.main()
