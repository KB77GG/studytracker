import importlib.util
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from models import DictationWord, StudentVocabularyMastery, db
from services import vocabulary_autonomous_review as review
from services import vocabulary_context as context

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "scripts" / "benchmark_vocabulary_review.py"


def load_benchmark_module():
    spec = importlib.util.spec_from_file_location("vocabulary_review_benchmark", BENCHMARK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VocabularyReviewPerformanceRegressionTest(unittest.TestCase):
    """Stable workload assertions; elapsed milliseconds are intentionally not gated."""

    def test_due_and_claim_work_are_bounded_as_history_grows(self):
        benchmark = load_benchmark_module()
        app = benchmark._make_app()
        with app.app_context():
            results = [benchmark._run_scale(app, scale) for scale in benchmark.SCALES]

        by_scale = {result["scale"]: result for result in results}
        for scale, result in by_scale.items():
            expected_batch = min(scale, benchmark.MAX_REVIEW_BATCH)
            self.assertEqual(result["due_candidate_count"], scale)
            self.assertEqual(result["due_count"], scale)
            self.assertEqual(result["actual_batch_count"], expected_batch)
            self.assertEqual(result["remaining_due_count"], max(0, scale - expected_batch))
            self.assertLessEqual(result["actual_batch_count"], benchmark.MAX_REVIEW_BATCH)

        # The work is now a fixed batch plus bounded metadata lookups. Keep a
        # generous upper bound so this test catches an accidental N+1 without
        # becoming a machine-speed benchmark.
        for scale in (20, 50, 100, 300, 1000):
            self.assertLessEqual(by_scale[scale]["due_candidates"]["query_count"], 8)
            self.assertLessEqual(by_scale[scale]["claim"]["query_count"], 60)

        self.assertLessEqual(
            by_scale[1000]["claim"]["query_count"],
            by_scale[20]["claim"]["query_count"] + 24,
        )

    def test_choice_only_context_preflight_does_not_build_every_due_question(self):
        benchmark = load_benchmark_module()
        app = benchmark._make_app()
        with app.app_context():
            db.create_all()
            user, task = benchmark._seed(1000)
            StudentVocabularyMastery.query.update(
                {
                    "meaning_recall_next_due_at": benchmark.BENCHMARK_NOW + timedelta(days=1),
                    "context_use_next_due_at": benchmark.BENCHMARK_NOW - timedelta(days=1),
                }
            )
            DictationWord.query.update(
                {
                    "example_en": "A classroom sentence without the target word.",
                    "usage_pattern": "",
                }
            )
            db.session.commit()
            with patch.object(review, "_question_for", side_effect=AssertionError("count built a question")), patch.object(
                context, "parse_vocabulary_word_variants", wraps=context.parse_vocabulary_word_variants
            ) as parse:
                result, _elapsed, query_count, _sql = benchmark._timed_call(
                    lambda: review.review_preflight(user, task.id, now=benchmark.BENCHMARK_NOW)
                )
            self.assertEqual(result["due_count"], 1000)
            self.assertTrue(result["required"])
            # The cached numeric count is not gate authority: the fresh,
            # paged gate adds a fixed metadata/mastery/word lookup (3 SQL).
            self.assertLessEqual(query_count, 16)
            # Candidate text is parsed once per catalog, not 1,000 times per
            # due word. Keep a generous linear bound for target field checks.
            self.assertLessEqual(parse.call_count, 12000)


if __name__ == "__main__":
    unittest.main()
