"""Measurement fixes from the execution review of 2026-11-11
(docs/design/iwa-holdout-execution-review-20261111/metrics_blind_review.md): the rater
yardstick and the AI's error used different essays; the ordering spread silently used
middle levels when an end level had no score; the blind sheet left out evidence; the
blind tally truncated "0.5" and "1–2". Synthetic data only."""

from __future__ import annotations

import unittest

from tools.ielts_writing_ai import blindtally, realcheck, realcheck_compare


def sample(sample_id, overall, *, teachers=(), group=None, nominal=None):
    result = {"overall_band": overall, "criteria": []} if overall is not None else None
    return {
        "id": sample_id,
        "teachers": [{"overall": t} for t in teachers],
        "group": group,
        "nominal_band": nominal,
        "generations": {"evaluate": {"status": "ready" if result else "failed", "result": result}},
    }


class RaterYardstickTest(unittest.TestCase):
    def test_the_comparison_uses_the_essays_the_ai_scored(self):
        # The reviewer's minimal case: on the scored essay the raters agree (gap 0) and the
        # AI is 0.5 off; the failed essay's split raters must not widen the yardstick.
        m = realcheck.rater_agreement(
            [sample("ok", 7.5, teachers=(7, 7)), sample("bad", None, teachers=(6, 8))]
        )
        overall = m["overall"]
        self.assertEqual((overall["essays"], overall["scored"], overall["failed"]), (2, 1, 1))
        self.assertEqual((overall["rater_gap"], overall["ai_gap"]), (0.0, 0.5))
        self.assertEqual(overall["rater_gap_all"], 1.0)  # kept, but not the comparison
        markdown = realcheck.render_markdown(
            realcheck.build_report(
                {
                    "started_at": "x",
                    "settings": {"llm_provider": "fake", "llm_model": "m"},
                    "kinds": ["evaluate"],
                    "max_calls": 1,
                    "aborted": None,
                    "samples": [],
                    "calls": [],
                }
            )
            | {"rater_agreement": m}
        )
        self.assertIn("| 总分 | 2 | 1 | 1 | 0.0 | 0.5 |", markdown)

    def test_two_runs_are_compared_on_the_essays_both_scored(self):
        a = {"samples": [sample("x", 7.0, teachers=(7, 7)), sample("y", 6.0, teachers=(6, 8))]}
        b = {"samples": [sample("x", 7.5, teachers=(7, 7)), sample("y", None, teachers=(6, 8))]}
        common = realcheck_compare.common_rater_agreement(a, b)
        self.assertEqual(common["essays"], 1)
        self.assertEqual(
            (common["a"]["overall"]["ai_gap"], common["b"]["overall"]["ai_gap"]), (0.0, 0.5)
        )


class OrderingEndpointTest(unittest.TestCase):
    def ordering(self, scores):
        rows = [sample(f"s{n}", ai, group="g", nominal=n) for n, ai in scores]
        return realcheck._ordering({"samples": rows})["g"]

    def test_a_missing_end_level_gives_no_spread(self):
        full = self.ordering([(9, 8), (8, 7), (7, 6)])
        self.assertEqual((full["spread"], full["highest"], full["lowest"]), (2.0, 9.0, 7.0))
        top_missing = self.ordering([(9, None), (8, 7), (7, 6)])
        self.assertIsNone(top_missing["spread"])  # not 8 → 7 presented as the full spread
        self.assertEqual(top_missing["missing"], 1)
        only_one = self.ordering([(9, 8), (7, None)])
        self.assertIsNone(only_one["spread"])
        self.assertEqual(only_one["pairs"], 0)


def view(**extra):
    base = {
        "id": "s1",
        "task_type": "task2",
        "status": "ready",
        "overall": 6.5,
        "bands": {"task": 6, "coherence": 6, "lexical": 7, "grammar": 6},
        "criteria": {
            k: {"summary": "", "issues": []} for k in ("task", "coherence", "lexical", "grammar")
        },
        "overall_comment": "",
        "priorities": [],
        "optional": [],
        "position_consistent": None,
        "argument_notes": [],
        "problems": [],
        "reclassified": [],
        "consistency_issues": [],
        "comparisons_checked": None,
        "count_corrections": [],
        "suggestions_removed": 0,
        "teacher_coverage": None,
    }
    return base | extra


class BlindSheetEvidenceTest(unittest.TestCase):
    def test_every_piece_of_evidence_is_on_the_sheet(self):
        rich = view(
            position_consistent=False,
            argument_notes=["NOTE-MARK"],
            problems=[
                {
                    "type": "contradiction",
                    "label": "前后矛盾",
                    "quote": "FIRST-HALF",
                    "conflicts_with": "OTHER-HALF",
                    "needs_review": True,
                    "p": 3,
                    "comment": "PROBLEM-COMMENT",
                    "suggestion": "PROBLEM-FIX",
                }
            ],
            reclassified=[
                {
                    "from_type": "unsupported",
                    "quote": "RECLASS-QUOTE",
                    "support": ["SUPPORT-MARK"],
                    "suggestion": "R-FIX",
                }
            ],
            count_corrections=["COUNT-MARK"],
            suggestions_removed=2,
            teacher_coverage={
                "findings": [{"quote": "TEACHER-QUOTE", "note": "TEACHER-NOTE", "coverage": "no"}]
            },
        )
        sheet, _key = realcheck_compare.render_blind_review(
            {"samples": [{"a": rich, "b": view()}]}, seed=1
        )
        for marker in (
            "前后不一致",
            "NOTE-MARK",
            "OTHER-HALF",
            "需人工确认",
            "第 3 段",
            "SUPPORT-MARK",
            "COUNT-MARK",
            "删掉了 2 条",
            "TEACHER-QUOTE",
            "TEACHER-NOTE",
        ):
            self.assertIn(marker, sheet)
        # Evidence rows are pre-marked 参考 and are not counted as verdicts.
        evidence = [line for line in sheet.splitlines() if "COUNT-MARK" in line]
        self.assertIn("| 参考 |", evidence[0])


class TallyTest(unittest.TestCase):
    """Rows carry ids; the key lists every expected row and its kind (review 76276d9)."""

    def build(self, rows_a, rows_b, *, drop=(), extra=()):
        key = {"samples": {"s1": {"甲": "a", "乙": "b"}}, "rows": []}
        lines = ["## s1", ""]
        for name, rows in (("甲", rows_a), ("乙", rows_b)):
            lines += [
                f"### {name}（总分 6.5）",
                "",
                "| 编号 | 位置 | 引文 | 说明 | 建议 | 判断 | 备注 |",
                "|---|---|---|---|---|---|---|",
            ]
            for n, (kind, position, verdict) in enumerate(rows, 1):
                row_id = f"s1/{name}/{n:02d}"
                key["rows"].append({"id": row_id, "sample": "s1", "side": name, "kind": kind})
                if row_id not in drop:
                    lines.append(f"| {row_id} | {position} | — | — | — | {verdict} |  |")
        lines += list(extra)
        return "\n".join(lines) + "\n", key

    GOOD = [
        ("judged", "GRA 问题", "① 误读原文"),
        ("context", "计数更正（程序已改）", "参考"),
        ("count", "④ 漏掉评委都指出的明确错误", "2"),
        ("count", "其他漏报", "0"),
    ]

    def test_a_complete_sheet_counts(self):
        sheet, key = self.build(self.GOOD, self.GOOD)
        result = blindtally.tally(sheet, key)
        self.assertTrue(result["complete"], result["problems"])
        self.assertEqual(
            (result["models"]["a"]["misread"], result["models"]["a"]["missed_both_raters"]), (1, 2)
        )

    def test_counts_must_be_whole_non_negative_numbers(self):
        for bad in ("0.5", "1–2", "-1", "两条", "参考"):
            rows = [
                ("judged", "GRA 问题", "正确"),
                ("count", "④ 漏掉评委都指出的明确错误", bad),
                ("count", "其他漏报", "0"),
            ]
            sheet, key = self.build(rows, self.GOOD)
            result = blindtally.tally(sheet, key)
            with self.subTest(value=bad):
                self.assertFalse(result["complete"])
                self.assertEqual(result["models"]["a"]["missed_both_raters"], 0)

    def test_missing_rows_sides_or_an_empty_sheet_are_incomplete(self):
        _sheet, key = self.build(self.GOOD, self.GOOD)
        self.assertFalse(blindtally.tally("", key)["complete"])  # empty sheet
        cut, key = self.build(self.GOOD, self.GOOD, drop={f"s1/乙/{n:02d}" for n in range(1, 5)})
        result = blindtally.tally(cut, key)  # the whole 乙 side removed
        self.assertFalse(result["complete"])
        self.assertEqual(result["missing_rows"], 4)
        dup, key = self.build(
            self.GOOD, self.GOOD, extra=["| s1/甲/01 | GRA 问题 | — | — | — | 正确 |  |"]
        )
        self.assertFalse(blindtally.tally(dup, key)["complete"])  # duplicated row
        # A judged row may not be turned into evidence.
        sheet, key = self.build([("judged", "GRA 问题", "参考")] + self.GOOD[2:], self.GOOD)
        self.assertFalse(blindtally.tally(sheet, key)["complete"])
        # An old key without a row list cannot prove completeness.
        self.assertFalse(blindtally.tally(sheet, {"samples": key["samples"]})["complete"])

    def test_blank_or_ambiguous_verdicts_make_it_incomplete(self):
        for verdict in ("", "①②"):
            sheet, key = self.build([("judged", "GRA 问题", verdict)] + self.GOOD[2:], self.GOOD)
            with self.subTest(verdict=verdict):
                result = blindtally.tally(sheet, key)
                self.assertFalse(result["complete"])
                self.assertTrue(result["problems"])

    def test_later_repeats_may_stay_blank(self):
        key = {
            "samples": {"s1#r2": {"甲": "a", "乙": "b"}},
            "rows": [{"id": "s1#r2/甲/01", "sample": "s1#r2", "side": "甲", "kind": "judged"}],
        }
        self.assertTrue(blindtally.tally("", key)["complete"])
        self.assertFalse(blindtally.tally("", key, all_repeats=True)["complete"])


if __name__ == "__main__":
    unittest.main()
