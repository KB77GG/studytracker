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

    def test_padded_submission_with_answer_burst_is_flagged_but_not_high(self):
        # Fills all 12 answers in 40 s after 18 quiet minutes, submits at 25 min. That is
        # also what "worked on paper, then typed it in" looks like, so it stays "medium".
        events = _answers(18 * 60, 3.5, 12)
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 25 * 60_000), question_count=12, accuracy=100.0
        )
        self.assertIn("padded_burst", _codes(result))
        self.assertEqual(result["level"], LEVEL_MEDIUM)
        burst = next(flag for flag in result["flags"] if flag["code"] == "padded_burst")
        self.assertIn("交卷总用时 25 分钟", burst["message"])
        self.assertIn("在纸上做好再统一录入", burst["message"])
        self.assertNotIn("其余时间没有作答", burst["message"])

    # ---- regressions from the Codex review (2026-11-22) ----

    def test_paper_first_entry_at_normal_typing_speed_is_medium(self):
        # Review #4: reads/works 10 minutes, then enters 12 answers 4 s apart, 80% correct.
        events = _answers(10 * 60, 4, 12)
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 11 * 60_000), question_count=12, accuracy=80.0
        )
        self.assertEqual(_codes(result), {"padded_burst"})
        self.assertEqual(result["level"], LEVEL_MEDIUM)

    def test_fast_redo_after_seeing_answers_is_not_flagged(self):
        # Review #2: redoing six wrong questions 3 s apart, submitted after 20 s.
        events = _answers(2, 3, 6)
        for mode in ("redo_wrong", "redo_all"):
            result = analyze_timeline(
                "reading_vocab",
                _timeline(events, 20_000, mode=mode),
                question_count=12,
                accuracy=100.0,
                baseline_accuracy=40.0,
            )
            self.assertEqual(result["flags"], [], mode)
            self.assertEqual(result["level"], LEVEL_NONE, mode)

    def test_redo_keeps_leave_facts_only_as_info(self):
        events = [[1000, "h"], [200_000, "s"]] + _answers(201, 1, 10)
        result = analyze_timeline(
            "cambridge_reading",
            _timeline(events, 215_000, mode="redo_wrong"),
            question_count=10,
            accuracy=100.0,
        )
        self.assertEqual(_codes(result), {"left_then_burst"})
        self.assertEqual(result["level"], LEVEL_INFO)

    def test_short_break_at_normal_vocab_speed_is_not_flagged(self):
        # Review #3: ten vocab questions 8 s apart with a 60 s break in the middle.
        events = _answers(5, 8, 5, prefix="a") + [[45_000, "h"], [105_000, "s"]]
        events += _answers(106, 8, 5, prefix="b")
        result = analyze_timeline(
            "reading_vocab", _timeline(events, 150_000), question_count=10, accuracy=80.0
        )
        self.assertEqual(result["metrics"]["returns"][0]["answered_within_60s"], 5)
        self.assertEqual(result["level"], LEVEL_NONE, result["flags"])

    def test_placeholders_then_mass_correction_is_flagged(self):
        # Review #5: 12 placeholder answers 45 s apart, all changed in the last 12 s.
        events = _answers(60, 45, 12)
        events += [[19 * 60_000 + i * 1000, "a", str(i + 1)] for i in range(12)]
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 20 * 60_000), question_count=12, accuracy=100.0
        )
        self.assertIn("revision_burst", _codes(result))
        self.assertEqual(result["level"], LEVEL_HIGH)
        self.assertEqual(result["metrics"]["revised_question_count"], 12)

    def test_a_few_spread_out_corrections_are_not_a_revision_burst(self):
        events = _answers(60, 45, 12)
        events += [[700_000, "a", "2"], [760_000, "a", "7"], [840_000, "a", "11"]]
        result = analyze_timeline(
            "cambridge_reading", _timeline(events, 20 * 60_000), question_count=12, accuracy=75.0
        )
        self.assertNotIn("revision_burst", _codes(result))
        self.assertEqual(result["level"], LEVEL_NONE)

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
