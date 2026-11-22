import unittest

from services.answer_timeline_rules import (
    LEVEL_HIGH,
    LEVEL_INFO,
    LEVEL_MEDIUM,
    LEVEL_NONE,
    analyze_timeline,
    sanitize_timeline,
)


def _timeline(events, end_ms, mode="practice"):
    return sanitize_timeline(
        {"v": 1, "mode": mode, "submitted_offset_ms": end_ms, "events": events},
    )


def _answers(start_s, gap_s, count, prefix=""):
    return [[int((start_s + i * gap_s) * 1000), "a", f"{prefix}{i + 1}"] for i in range(count)]


def _codes(result):
    return {flag["code"] for flag in result["flags"]}


class SanitizeTimelineTest(unittest.TestCase):
    def test_rejects_unusable_payloads(self):
        self.assertIsNone(sanitize_timeline(None))
        self.assertIsNone(sanitize_timeline("x"))
        self.assertIsNone(sanitize_timeline({"v": 2, "events": []}))
        self.assertIsNone(sanitize_timeline({"v": 1, "events": "nope"}))

    def test_drops_bad_rows_and_clamps_offsets(self):
        cleaned = sanitize_timeline(
            {
                "v": 1,
                "mode": "hack",
                "submitted_offset_ms": 10_000,
                "events": [
                    [5000, "a", "2"],
                    [-50, "a", "1"],
                    [99_999, "a", "3"],
                    ["x", "a", "4"],
                    [1000, "zz"],
                    [2000, "a", ""],
                    [3000, "a"],
                    [float("nan"), "h"],
                    [True, "h"],
                    "garbage",
                    [4000, "h"],
                    [4500, "s"],
                ],
            }
        )
        self.assertEqual(cleaned["mode"], "practice")
        self.assertEqual(
            cleaned["events"],
            [[0, "a", "1"], [4000, "h"], [4500, "s"], [5000, "a", "2"], [10_000, "a", "3"]],
        )
        self.assertEqual(cleaned["submitted_offset_ms"], 10_000)

    def test_falls_back_to_reported_duration_and_caps_events(self):
        events = [[i, "a", str(i)] for i in range(5000)]
        cleaned = sanitize_timeline({"v": 1, "events": events}, duration_seconds=3)
        self.assertEqual(len(cleaned["events"]), 800)
        self.assertEqual(cleaned["submitted_offset_ms"], 3000)


class AnalyzeTimelineTest(unittest.TestCase):
    def test_steady_honest_reading_is_not_flagged(self):
        # Reads ~6 minutes, then answers 13 questions about 45 s apart.
        events = _answers(360, 45, 13)
        result = analyze_timeline(
            "cambridge_reading",
            _timeline(events, 1000_000),
            question_count=13,
            accuracy=69.0,
        )
        self.assertEqual(result["level"], LEVEL_NONE, result["flags"])
        self.assertEqual(result["metrics"]["answered_count"], 13)

    def test_whole_test_in_seconds_is_too_fast(self):
        # 12 questions answered in 13 seconds, submitted right away.
        events = _answers(1, 1, 12)
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 13_000), question_count=12, accuracy=100.0
        )
        self.assertIn("too_fast", _codes(result))
        self.assertEqual(result["level"], LEVEL_HIGH)

    def test_padded_submission_with_answer_burst_is_flagged(self):
        # Waits 18 minutes doing nothing, fills all 12 answers in 40 s, waits, submits at 25 min.
        events = _answers(18 * 60, 3.5, 12)
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 25 * 60_000), question_count=12, accuracy=100.0
        )
        self.assertIn("padded_burst", _codes(result))
        self.assertEqual(result["level"], LEVEL_HIGH)
        burst = next(flag for flag in result["flags"] if flag["code"] == "padded_burst")
        self.assertIn("交卷总用时 25 分钟", burst["message"])

    def test_leaving_then_answering_in_a_burst_is_flagged(self):
        events = [[30_000, "a", "1"], [60_000, "h"], [300_000, "s"]]
        events += _answers(305, 6, 9, prefix="q")
        events += [[int(305_000 + 9 * 6_000 + 400_000), "a", "last"]]
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 1_200_000), question_count=11, accuracy=90.0
        )
        self.assertIn("left_then_burst", _codes(result))
        self.assertEqual(result["metrics"]["leave_count"], 1)
        self.assertEqual(result["metrics"]["hidden_seconds"], 240.0)

    def test_hidden_time_does_not_count_as_active_answering(self):
        # 10 questions, 5 min total, but 4 min 40 s of it outside the app.
        events = [[1000, "h"], [281_000, "s"]] + _answers(282, 1.5, 10)
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 300_000), question_count=10, accuracy=100.0
        )
        self.assertIn("too_fast", _codes(result))
        # The single long absence is already explained by the return burst.
        self.assertIn("left_then_burst", _codes(result))
        self.assertNotIn("frequent_leave", _codes(result))

    def test_long_absence_without_burst_and_repeated_leaves_are_flagged(self):
        honest = _answers(60, 50, 10)
        absent = analyze_timeline(
            "cambridge_reading",
            _timeline([[30_000, "h"], [400_000, "s"]] + _answers(420, 50, 10), 1_000_000),
            question_count=10,
            accuracy=60.0,
        )
        self.assertEqual(_codes(absent), {"frequent_leave"})
        leaves = []
        for at in (100_000, 150_000, 200_000):
            leaves += [[at, "h"], [at + 5000, "s"]]
        repeated = analyze_timeline(
            "cambridge_reading",
            _timeline(honest + leaves, 1_000_000),
            question_count=10,
            accuracy=60.0,
        )
        self.assertEqual(repeated["metrics"]["leave_count"], 3)
        self.assertIn("frequent_leave", _codes(repeated))

    def test_vocab_thresholds_are_looser_than_reading(self):
        events = _answers(2, 4, 12)
        vocab = analyze_timeline(
            "reading_vocab", _timeline(events, 60_000), question_count=12, accuracy=80.0
        )
        self.assertEqual(vocab["level"], LEVEL_NONE, vocab["flags"])
        reading = analyze_timeline(
            "cambridge_reading", _timeline(events, 60_000), question_count=12, accuracy=80.0
        )
        self.assertEqual(reading["level"], LEVEL_HIGH)

    def test_accuracy_jump_over_baseline_is_medium_only_in_practice_mode(self):
        events = _answers(300, 60, 10)
        practice = analyze_timeline(
            "cambridge_reading",
            _timeline(events, 1_000_000),
            question_count=10,
            accuracy=100.0,
            baseline_accuracy=50.0,
        )
        self.assertIn("above_baseline", _codes(practice))
        self.assertEqual(practice["level"], LEVEL_MEDIUM)
        redo = analyze_timeline(
            "cambridge_reading",
            _timeline(events, 1_000_000, mode="redo_wrong"),
            question_count=10,
            accuracy=100.0,
            baseline_accuracy=50.0,
        )
        self.assertNotIn("above_baseline", _codes(redo))

    def test_revisions_count_and_perfect_without_revision_is_info(self):
        events = _answers(300, 60, 10)
        perfect = analyze_timeline(
            "cambridge_reading", _timeline(events, 1_000_000), question_count=10, accuracy=100.0
        )
        self.assertEqual(perfect["level"], LEVEL_INFO)
        revised = analyze_timeline(
            "cambridge_reading",
            _timeline(events + [[950_000, "a", "3"]], 1_000_000),
            question_count=10,
            accuracy=100.0,
        )
        self.assertEqual(revised["metrics"]["revisit_count"], 1)
        self.assertEqual(revised["level"], LEVEL_NONE)

    def test_missing_timeline_is_reported_without_metrics(self):
        result = analyze_timeline("cambridge_reading", None, question_count=13, accuracy=50.0)
        self.assertIsNone(result["metrics"])
        self.assertEqual(_codes(result), {"no_timeline"})
        self.assertEqual(result["level"], LEVEL_INFO)

    def test_few_questions_never_get_pace_flags(self):
        events = _answers(1, 0.5, 3)
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 3000), question_count=3, accuracy=100.0
        )
        self.assertNotIn("too_fast", _codes(result))
        self.assertNotIn("padded_burst", _codes(result))


if __name__ == "__main__":
    unittest.main()
