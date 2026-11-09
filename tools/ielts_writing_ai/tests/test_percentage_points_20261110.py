"""A difference between two percentages ("5 percentage points", "5 个百分点") is sourced
when it is the gap between two percentages the input gives. The .12 real run
(2026-11-09) removed a Task 1 suggestion whose "5 percentage points" followed from the
essay's own 70% -> 75%: "percentage points" was read as a percentage that had to appear
in the essay as such."""

import json
import unittest
from pathlib import Path

from tools.ielts_writing_ai import copytext, figures, review
from tools.ielts_writing_ai.llm import parse_strict_json

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261109_prompt10.json").read_text(
        encoding="utf-8"
    )
)
SUB = FX["submissions"]["t1-no-image"]  # 70% / 55% / 40% / 15% -> 75% / 65% / 80% / 35%


def with_suggestion(advice):
    raw = parse_strict_json(FX["attempts"]["t1-no-image"][0]["text"])
    lexical = raw["criteria"]["lexical"]
    lexical["issues"] = (
        [dict(lexical["issues"][0], suggestion=advice)]
        if lexical["issues"]
        else [
            {
                "quote": "Country B had grown to approximately 65%",
                "comment": "说明。",
                "suggestion": advice,
            }
        ]
    )
    result = review.normalize_evaluation(raw, SUB)
    lexical = next(c for c in result["criteria"] if c["key"] == "lexical")
    return result, lexical["issues"][0]["suggestion"]


class PercentagePointsTest(unittest.TestCase):
    def test_a_gap_between_two_essay_percentages_is_sourced(self):
        for advice in (
            "可以写明 A 国在两个年份之间上升了 5 个百分点。",
            "Add that Country A rose by 5 percentage points.",
            "Add that Country A saw a 5-percentage-point rise.",
            "Add that Country C rose by forty percentage points.",  # 40% -> nearly 80%
        ):
            with self.subTest(advice=advice):
                result, shown = with_suggestion(advice)
                self.assertEqual(shown, advice)
                self.assertEqual(result["suggestions_removed"]["total"], 0)
                self.assertIn(advice, copytext.evaluation_text(result, {}))

    def test_an_invented_gap_or_percentage_is_still_removed(self):
        for advice in (
            "可以写明 A 国上升了 7 个百分点。",  # no two figures differ by 7
            "Add that Country A rose by 7 percentage points.",
            "Add that Country A rose by 5%.",  # a percentage, not a gap: needs 5% itself
        ):
            with self.subTest(advice=advice):
                result, shown = with_suggestion(advice)
                self.assertEqual(shown, "")
                self.assertEqual(result["suggestions_removed"]["criteria"], 1)

    def test_kinds_and_spans(self):
        self.assertEqual(
            figures.figures("rose by 5 percentage points and 5 个百分点")[0][1], figures.POINTS
        )
        sources = figures.Sources("from 70% to 75%, and 12.5% to 20%")
        self.assertEqual(sources.point_spans, {"5", "7.5", "57.5", "62.5", "50", "55"})
        self.assertEqual(sources.unsourced("7.5 percentage points"), [])
        self.assertEqual(sources.unsourced("8 percentage points"), ["8 percentage points"])
        stated = figures.Sources("The gap widened by 3 percentage points.")
        self.assertEqual(stated.unsourced("a 3 percentage point gap"), [])


if __name__ == "__main__":
    unittest.main()
