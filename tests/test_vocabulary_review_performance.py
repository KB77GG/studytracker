import importlib.util
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
