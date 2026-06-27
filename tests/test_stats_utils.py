"""统计聚合纯函数单测（零 DB，只 import api.stats_utils）。"""

import unittest

from api.stats_utils import (
    percent,
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


if __name__ == "__main__":
    unittest.main()
