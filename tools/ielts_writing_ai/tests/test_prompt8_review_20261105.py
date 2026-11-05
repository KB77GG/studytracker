"""Regressions from the review of 1c865eb (docs/design/ielts-writing-ai-prompt8-review-
20261105): coordinated number words were summed ("forty and fifty" = 90); quantities
of 2000 and 2020 were taken as years; teacher-annotation coverage left failed
evaluations out of the denominator, called shared words "the same place", and paired
A/B annotations by list position."""

import unittest

from tools.ielts_writing_ai import copytext, figures, realcheck, realcheck_compare, review
from tools.ielts_writing_ai.essay import count_words

SOURCE = "Each bus carried forty and fifty passengers respectively."
ESSAY = (
    "Public transport is important.\n"
    f"{SOURCE} This shows that buses are efficient.\n"
    "In conclusion, governments should invest in buses."
)


def raw_with_suggestion(suggestion):
    criterion = {
        "band": 6,
        "summary": "论点清楚但展开不足，例子与观点之间缺少解释。",
        "strengths": [{"quote": "Public transport is important.", "comment": "立场明确"}],
        "issues": [{"quote": SOURCE, "comment": "需要说明数字的含义。", "suggestion": suggestion}],
    }
    return {
        "criteria": {k: dict(criterion) for k in ("task", "coherence", "lexical", "grammar")},
        "argument": {
            "position": None,
            "paragraphs": [
                {"role": "body", "main_point": SOURCE, "verdict": "supports", "comment": "c"}
            ],
            "problems": [],
        },
        "overall_comment": "整体结构完整，例子需要更好地回扣论点。",
        "priorities": ["补充解释"],
    }


def normalize(suggestion):
    sub = {
        "task_type": "task2",
        "essay_text": ESSAY,
        "prompt_text": "Do you agree?",
        "word_count": count_words(ESSAY),
        "target_band": 7.0,
        "image_status": "none",
    }
    return review.normalize_evaluation(raw_with_suggestion(suggestion), sub)


class CoordinatedNumbersTest(unittest.TestCase):
    def test_forty_and_fifty_are_two_numbers(self):
        self.assertEqual(
            [(v, shown) for v, _kind, shown in figures.figures(SOURCE)],
            [("40", "forty"), ("50", "fifty")],
        )
        self.assertEqual(
            figures.split_en_numbers("forty and fifty"), [(0, 5, "40"), (10, 15, "50")]
        )
        self.assertEqual(figures.split_en_numbers("forty fifty"), [(0, 5, "40"), (6, 11, "50")])

    def test_one_number_forms_still_combine(self):
        for text, value in (
            ("one hundred and twenty", "120"),
            ("two thousand and twenty", "2020"),
            ("forty-two", "42"),
            ("three hundred thousand", "300000"),
            ("a hundred", "100"),
        ):
            with self.subTest(text=text):
                self.assertEqual([v for _s, _e, v in figures.split_en_numbers(text)], [value])

    def test_reviewer_case_through_normalize_and_copy(self):
        kept = normalize("用原文的 forty and fifty 两个数字说明效率。")
        self.assertEqual(kept["suggestions_removed"]["total"], 0)
        self.assertIn("forty and fifty", copytext.evaluation_text(kept, {}))
        wrong = normalize("改成每辆车载客 90 人。")
        self.assertEqual(wrong["suggestions_removed"]["criteria"], 4)
        self.assertNotIn("90 人", copytext.evaluation_text(wrong, {}))

    def test_arabic_source_and_word_advice(self):
        sources = figures.Sources("Each bus carried 40 and 50 passengers.")
        self.assertEqual(sources.unsourced("forty and fifty passengers"), [])
        self.assertEqual(sources.unsourced("ninety passengers"), ["ninety"])
        self.assertEqual(
            figures.figures("forty and fifty percent"),
            [("40", figures.PERCENT, "forty"), ("50", figures.PERCENT, "fifty percent")],
        )


class YearContextTest(unittest.TestCase):
    def test_quantities_are_not_years(self):
        buses = "The city has 2000 buses and the suburbs have 2020 buses."
        self.assertEqual(figures.confirmed_years(buses), set())
        self.assertEqual(figures.Sources(buses).unsourced("Twenty years later"), ["Twenty years"])
        for text in ("2000 and 2020 buses", "the 2000 figure", "2200 and 2220 buses"):
            with self.subTest(text=text):
                self.assertEqual(figures.confirmed_years(text), set())

    def test_years_with_context_still_give_spans(self):
        cases = {
            "Ownership in 2000 and 2020.": {2000, 2020},
            "from 1800 to 1900": {1800, 1900},
            "between 2000 and 2020": {2000, 2020},
            "In 2000, the figure rose; by 2020 it fell.": {2000, 2020},
            "2000年和2020年": {2000, 2020},
            "2000-2020": {2000, 2020},
        }
        for text, years in cases.items():
            with self.subTest(text=text):
                self.assertEqual(figures.confirmed_years(text), years)
        sources = figures.Sources("Ownership in 2000 and 2020.")
        self.assertEqual(sources.unsourced("Twenty years later"), [])
        self.assertEqual(sources.unsourced("thirty years later"), ["thirty years"])


SCHOOL = "The school is in the city and it needs repairs."
HOSPITAL = "The hospital is in the village and it needs doctors."


def sample(sample_id, essay, findings, issues, status="ready"):
    result = {"criteria": [{"key": "task", "issues": [{"quote": q} for q in issues]}]}
    return {
        "id": sample_id,
        "task_type": "task2",
        "submission": {"essay_text": essay},
        "teacher_findings": findings,
        "generations": {
            "evaluate": {"status": status, "result": result if status == "ready" else None}
        },
    }


class PositionTest(unittest.TestCase):
    essay = SCHOOL + "\n\n" + HOSPITAL

    def test_shared_words_in_another_paragraph_are_not_the_same_place(self):
        self.assertEqual(realcheck.span_relation(self.essay, SCHOOL, HOSPITAL), "no")
        coverage = realcheck.teacher_coverage(
            sample("x", self.essay, [{"quote": SCHOOL, "note": "n"}], [HOSPITAL])
        )
        self.assertEqual((coverage["covered"], coverage["findings"][0]["coverage"]), (0, "no"))
        self.assertFalse(realcheck.spans_overlap(SCHOOL, HOSPITAL))

    def test_intersecting_ranges_are_the_same_place(self):
        self.assertEqual(realcheck.span_relation(self.essay, SCHOOL, "it needs repairs"), "yes")
        self.assertEqual(
            realcheck.span_relation(self.essay, SCHOOL, "city and it needs repairs. The hospital"),
            "yes",
        )
        self.assertTrue(realcheck.spans_overlap(SCHOOL, "it needs repairs"))

    def test_repeated_quote_is_uncertain_not_covered(self):
        essay = "It is good. Buses help.\nTrains are fast. It is good."
        coverage = realcheck.teacher_coverage(
            sample("x", essay, [{"quote": "It is good.", "note": "n"}], ["It is good. Buses help."])
        )
        self.assertEqual(coverage["findings"][0]["coverage"], "uncertain")
        self.assertEqual((coverage["covered"], coverage["uncertain"]), (0, 1))


class DenominatorTest(unittest.TestCase):
    def test_failed_evaluation_stays_in_the_count(self):
        finding = [{"quote": SCHOOL, "note": "n"}]
        run_data = {
            "samples": [
                sample("success", SCHOOL, finding, [SCHOOL]),
                sample("failed", SCHOOL, finding, [], status="failed"),
            ]
        }
        metrics = realcheck._teacher_findings_metrics(run_data)
        self.assertEqual((metrics["covered"], metrics["total"], metrics["rate"]), (1, 2, 0.5))
        self.assertEqual((metrics["evaluated_total"], metrics["rate_evaluated"]), (1, 1.0))
        self.assertEqual(metrics["failed_samples"], ["failed"])
        self.assertEqual(metrics["samples"]["failed"]["findings"][0]["coverage"], "not_evaluated")
        lines = realcheck._teacher_markdown(metrics)
        self.assertTrue(any("1 篇评价没有成功" in line and "占全部 50%" in line for line in lines))
        self.assertTrue(any("评价未成功（failed）" in line for line in lines))
        self.assertTrue(any("只看评价成功的作文为 1/1（100%）" in line for line in lines))


class AlignmentTest(unittest.TestCase):
    findings = [{"quote": SCHOOL, "note": "第一处"}, {"quote": HOSPITAL, "note": "第二处"}]
    essay = SCHOOL + "\n\n" + HOSPITAL

    def view(self, findings):
        return realcheck_compare.sample_view(
            {"calls": []}, sample("x", self.essay, findings, ["it needs repairs"])
        )

    def sheet(self, a, b):
        cmp = {
            "conditions": {"a": {"evaluate_thinking": "off"}, "b": {"evaluate_thinking": "high"}},
            "samples": [{"a": a, "b": b}],
        }
        return realcheck_compare.render_manual_review(cmp)

    def test_reordered_annotations_are_paired_by_identity(self):
        sheet = self.sheet(self.view(self.findings), self.view(list(reversed(self.findings))))
        self.assertIn(f"| 老师批注 | A 覆盖：是 / B 覆盖：是 | — | {SCHOOL} | 第一处 |", sheet)
        self.assertIn(f"| 老师批注 | A 覆盖：否 / B 覆盖：否 | — | {HOSPITAL} | 第二处 |", sheet)

    def test_missing_annotation_is_shown_and_warned(self):
        sheet = self.sheet(self.view(self.findings), self.view(self.findings[:1]))
        self.assertIn("A 覆盖：否 / B 覆盖：无此批注", sheet)

        def condition(findings):
            return {
                "provider": "p",
                "model": "m",
                "prompt_version": "v",
                "kinds": ["evaluate"],
                "evaluate_thinking": "off",
                "samples": {"x": "same"},
                "evaluate_inputs": {"x": "sha"},
                "teacher_findings": {
                    "x": sorted(realcheck_compare.finding_key(f) for f in findings)
                },
            }

        errors, warnings = realcheck_compare.check_same_conditions(
            condition(self.findings), dict(condition(self.findings[:1]), evaluate_thinking="high")
        )
        self.assertEqual(errors, [])
        self.assertTrue(any("老师批注不同" in w for w in warnings))
        _errors, warnings = realcheck_compare.check_same_conditions(
            condition(self.findings),
            dict(condition(list(reversed(self.findings))), evaluate_thinking="high"),
        )
        self.assertFalse(any("老师批注不同" in w for w in warnings))  # order does not matter


if __name__ == "__main__":
    unittest.main()
