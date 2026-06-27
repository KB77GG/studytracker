"""统计聚合纯函数单测（零 DB，只 import api.stats_utils）。"""

import unittest
from datetime import date, timedelta

from api.stats_utils import (
    average_accuracy,
    compute_badges,
    compute_streak,
    percent,
    study_level,
    summarize_subjects,
    summarize_today_status,
    summarize_weekly,
)


class PercentTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(percent(1, 2), 50)
        self.assertEqual(percent(1, 3), 33)   # round(33.33)
        self.assertEqual(percent(2, 3), 67)   # round(66.66)
        self.assertEqual(percent(3, 3), 100)

    def test_zero_whole_is_zero(self):
        self.assertEqual(percent(0, 0), 0)
        self.assertEqual(percent(5, 0), 0)
        self.assertEqual(percent(1, -1), 0)


class TodayStatusTests(unittest.TestCase):
    def test_empty(self):
        r = summarize_today_status([])
        self.assertEqual(r["total"], 0)
        self.assertEqual(r["completed_count"], 0)
        self.assertEqual(r["rate"], 0)
        self.assertEqual(r["not_started"], 0)

    def test_mixed(self):
        r = summarize_today_status(
            ["completed", "not_started", "in_progress", "completed", "pending_review"]
        )
        self.assertEqual(r["total"], 5)
        self.assertEqual(r["completed"], 2)
        self.assertEqual(r["completed_count"], 2)
        self.assertEqual(r["not_started"], 1)
        self.assertEqual(r["in_progress"], 1)
        self.assertEqual(r["pending_review"], 1)
        self.assertEqual(r["rate"], 40)  # 2/5

    def test_unknown_state_ignored(self):
        r = summarize_today_status(["completed", "bogus"])
        self.assertEqual(r["completed"], 1)
        self.assertEqual(r["total"], 2)  # total 仍按全部计


class WeeklyTests(unittest.TestCase):
    def test_adds_rate_and_preserves_fields(self):
        rows = [
            {"date": "06-20", "total": 4, "completed": 2},
            {"date": "06-21", "total": 0, "completed": 0},
        ]
        out = summarize_weekly(rows)
        self.assertEqual(out[0], {"date": "06-20", "total": 4, "completed": 2, "rate": 50})
        self.assertEqual(out[1]["rate"], 0)  # total 0 不除零

    def test_does_not_mutate_input(self):
        rows = [{"date": "06-20", "total": 4, "completed": 2}]
        summarize_weekly(rows)
        self.assertNotIn("rate", rows[0])


class SubjectsTests(unittest.TestCase):
    def test_count_percent_and_sorted_desc(self):
        out = summarize_subjects(["语法", "词汇", "语法"])
        self.assertEqual(out[0], {"subject": "语法", "count": 2, "percent": 67})
        self.assertEqual(out[1], {"subject": "词汇", "count": 1, "percent": 33})

    def test_none_and_blank_go_to_default(self):
        out = summarize_subjects([None, "", "数学"])
        by_subject = {item["subject"]: item["count"] for item in out}
        self.assertEqual(by_subject["其他"], 2)
        self.assertEqual(by_subject["数学"], 1)

    def test_empty(self):
        self.assertEqual(summarize_subjects([]), [])


class AverageAccuracyAndLevelTests(unittest.TestCase):
    def test_average(self):
        self.assertIsNone(average_accuracy([]))
        self.assertEqual(average_accuracy([90, 80]), 85.0)
        self.assertEqual(average_accuracy([1, 2, 2]), 1.7)  # round(1.666,1)

    def test_level(self):
        self.assertEqual(study_level(0), 1)
        self.assertEqual(study_level(4.9), 1)
        self.assertEqual(study_level(5), 2)
        self.assertEqual(study_level(12), 3)


class StreakTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 6, 27)

    def _d(self, days_ago):
        return (self.today - timedelta(days=days_ago)).isoformat()

    def test_empty(self):
        self.assertEqual(compute_streak([], self.today), 0)

    def test_today_only(self):
        self.assertEqual(compute_streak([self._d(0)], self.today), 1)

    def test_yesterday_only_still_counts(self):
        self.assertEqual(compute_streak([self._d(1)], self.today), 1)

    def test_two_days_ago_breaks(self):
        self.assertEqual(compute_streak([self._d(2)], self.today), 0)

    def test_consecutive_three(self):
        self.assertEqual(
            compute_streak([self._d(0), self._d(1), self._d(2)], self.today), 3
        )

    def test_stops_at_gap(self):
        # 今天、昨天连续，然后跳到4天前 → streak=2
        self.assertEqual(
            compute_streak([self._d(0), self._d(1), self._d(4)], self.today), 2
        )

    def test_malformed_date_does_not_crash(self):
        self.assertEqual(compute_streak(["not-a-date"], self.today), 0)


class BadgesTests(unittest.TestCase):
    @staticmethod
    def _ids(badges):
        return {b["id"] for b in badges}

    def test_streak_thresholds(self):
        self.assertIn("streak_3", self._ids(compute_badges(3, 0, None)))
        self.assertNotIn("streak_7", self._ids(compute_badges(3, 0, None)))
        ids7 = self._ids(compute_badges(7, 0, None))
        self.assertIn("streak_3", ids7)
        self.assertIn("streak_7", ids7)

    def test_hours_and_accuracy(self):
        self.assertIn("hours_10", self._ids(compute_badges(0, 10, None)))
        self.assertIn("accuracy_90", self._ids(compute_badges(0, 0, 90)))
        self.assertNotIn("accuracy_90", self._ids(compute_badges(0, 0, 89)))
        self.assertNotIn("accuracy_90", self._ids(compute_badges(0, 0, None)))

    def test_newbie_when_nothing(self):
        self.assertEqual(self._ids(compute_badges(0, 0, None)), {"newbie"})


if __name__ == "__main__":
    unittest.main()
