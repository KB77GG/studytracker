"""Regressions from the judgment review of 93d47ec
(docs/design/ielts-writing-ai-judgment-review-20261104): unsourced figures must be
removed from EVERY piece of advice (not only the argument map), and numbers are
matched as whole values (1980 or 180 is not a source for 80%)."""

import json
import unittest
from pathlib import Path

from tools.ielts_writing_ai import argument, copytext, figures, review
from tools.ielts_writing_ai.llm import parse_strict_json

from .test_argument_recheck_20261104 import chinese
from .test_review import evaluation, submission

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104c.json").read_text(encoding="utf-8")
)
ADVICE = "补充一个数字例子：公交使排放降低 80%。"


class WholeValueTest(unittest.TestCase):
    def test_reviewer_table(self):
        cases = [
            ("The city supports buses.", True),
            ("The city began its bus service in 1980.", True),
            ("The city operates 180 buses.", True),
            ("The city reports an 80% reduction in emissions.", False),
        ]
        for essay_text, removed in cases:
            with self.subTest(essay=essay_text):
                self.assertEqual(bool(argument.unsourced_figures(ADVICE, essay_text)), removed)
                raw = {
                    "paragraphs": [
                        {"role": "body", "verdict": "supports", "main_point": essay_text}
                    ],
                    "problems": [
                        {
                            "type": "unsupported",
                            "quote": essay_text,
                            "comment": "需要说明。",
                            "suggestion": ADVICE,
                        }
                    ],
                }
                item = argument.normalize(raw, essay_text)["problems"][0]
                self.assertIs(item["suggestion_removed"], removed)
                self.assertEqual(item["suggestion"], "" if removed else ADVICE)

    def test_percentage_needs_a_percentage_but_a_plain_number_needs_only_the_value(self):
        sources = figures.Sources("We counted 80 buses and 75% of riders.")
        self.assertEqual(sources.unsourced("排放降低 80%"), ["80%"])
        self.assertEqual(sources.unsourced("约 80 辆公交"), [])
        self.assertEqual(sources.unsourced("75 per cent 的乘客"), [])
        self.assertEqual(sources.unsourced("75 percent"), [])

    def test_value_forms(self):
        sources = figures.Sources("Spending rose to 1,500 million, about 7.50 per head.")
        self.assertEqual(sources.unsourced("写成 1500 million"), [])
        self.assertEqual(sources.unsourced("约 7.5 per head"), [])
        self.assertEqual(sources.unsourced("改成 15 million"), ["15 million"])
        self.assertEqual(sources.unsourced("用 2.5% 的增长"), ["2.5%"])
        self.assertEqual(sources.unsourced("补 1 个例子，放在第 2 段"), [])
        self.assertEqual(sources.unsourced("可以写百分之八十"), ["百分之八十"])

    def test_number_never_matches_inside_a_longer_number(self):
        self.assertEqual([v for v, _p, _s in figures.figures("1980 180 80")], ["1980", "180", "80"])


class SourcesTest(unittest.TestCase):
    def test_question_chart_word_count_and_minimum_are_sources(self):
        sub = {
            "task_type": "task1",
            "essay_text": "Car ownership rose.",
            "prompt_text": "The chart shows car ownership in 2000 and 2020.",
            "image_status": "ready",
            "image_description": "Country C: 42% in 2000, 79% in 2020.",
            "word_count": 133,
        }
        sources = figures.for_submission(sub)
        self.assertEqual(sources.unsourced("补上 2000 年和 2020 年的对比"), [])
        self.assertEqual(sources.unsourced("C 从 42% 升到 79%"), [])
        self.assertEqual(sources.unsourced("现在 133 词，至少写到 150 词"), [])
        self.assertEqual(sources.unsourced("C 升到 85%"), ["85%"])

    def test_chart_reading_is_a_source_only_when_it_was_usable(self):
        sub = {
            "task_type": "task1",
            "essay_text": "x",
            "prompt_text": "",
            "image_status": "failed",
            "image_description": "Country C: 79% in 2020.",
            "word_count": 1,
        }
        self.assertEqual(figures.for_submission(sub).unsourced("C 升到 79%"), ["79%"])


class AdvicePathTest(unittest.TestCase):
    def test_criterion_suggestions_and_priorities_follow_the_same_rule(self):
        raw = evaluation()
        raw["criteria"]["task"]["issues"][0]["suggestion"] = ADVICE
        raw["priorities"] = [
            "补充数据，例如 90% 的通勤者",
            "每个例子后补一句回扣论点",
            "写到 250 词以上",
        ]
        result = review.normalize_evaluation(raw, submission())
        issue = result["criteria"][0]["issues"][0]
        self.assertEqual((issue["suggestion"], issue["suggestion_removed"]), ("", True))
        self.assertEqual(result["priorities"], ["每个例子后补一句回扣论点", "写到 250 词以上"])
        self.assertEqual(
            result["suggestions_removed"],
            {"criteria": 1, "priorities": 1, "argument": 0, "total": 2},
        )
        self.assertTrue(any("评分项 1 条、提升重点 1 条" in w for w in result["warnings"]))
        copied = copytext.evaluation_text(result, {})
        self.assertNotIn("80%", copied)
        self.assertNotIn("90%", copied)
        self.assertIn("（建议含原文和题目都没有的具体数字，已删去）", copied)

    def test_corrections_that_reuse_the_essay_figures_are_kept(self):
        sub = FX["submissions"]["t1-no-image"]
        raw = chinese(parse_strict_json(FX["evaluation_attempts"]["t1-no-image"][0]))
        raw["criteria"]["coherence"]["issues"][0][
            "suggestion"
        ] = "By 2020, Country C had nearly 80%, overtaking Country A at about 75%."
        result = review.normalize_evaluation(raw, sub)
        self.assertFalse(result["criteria"][1]["issues"][0]["suggestion_removed"])
        self.assertEqual(result["suggestions_removed"]["total"], 0)

    def test_no_real_output_keeps_an_unsourced_figure_in_any_advice(self):
        for sample_id, texts in FX["evaluation_attempts"].items():
            raw = parse_strict_json(texts[-1])
            if sample_id == "t1-no-image":
                continue  # rejected for language before any advice is shown
            sub = FX["submissions"][sample_id]
            sources = figures.for_submission(sub)
            result = review.normalize_evaluation(raw, sub)
            advice = [i["suggestion"] for c in result["criteria"] for i in c["issues"]]
            advice += result["priorities"]
            mapped = result["argument"] or {}
            advice += [p["suggestion"] for p in mapped.get("problems") or []]
            advice += [i["suggestion"] for i in mapped.get("improvements") or []]
            with self.subTest(sample=sample_id):
                self.assertEqual([a for a in advice if sources.unsourced(a)], [])


if __name__ == "__main__":
    unittest.main()
