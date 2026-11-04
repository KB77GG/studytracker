"""Regressions from the fourth real run (7 evaluate calls, prompt iwa-2026-11-04.5, all
first-attempt valid) and its manual review (docs/design/ielts-writing-ai-figures-
recheck-20261104): word-count targets were removed as unsourced figures, brief or
contextual support was still called "no support", and Task 1 explanations stated
wrong counts. The fixture holds the real deepseek-flash outputs."""

import json
import unittest
from pathlib import Path

from tools.ielts_writing_ai import argument, copytext, figures, prompts, realcheck, review
from tools.ielts_writing_ai.llm import parse_strict_json

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104d.json").read_text(encoding="utf-8")
)


def real(sample_id):
    return parse_strict_json(FX["evaluation_attempts"][sample_id][0])


def evaluate(sample_id, raw=None):
    return review.normalize_evaluation(
        raw if raw is not None else real(sample_id), FX["submissions"][sample_id]
    )


class WordTargetTest(unittest.TestCase):
    def test_real_260_word_targets_are_kept(self):
        raw = real("t2-under-length")
        texts = [i["suggestion"] for i in raw["criteria"]["task"]["issues"]] + raw["priorities"]
        targets = [t for t in texts if "260" in t]
        self.assertEqual(len(targets), 2)
        result = evaluate("t2-under-length")
        self.assertEqual(result["suggestions_removed"]["total"], 0)
        shown = [i["suggestion"] for c in result["criteria"] for i in c["issues"]]
        shown += result["priorities"]
        for target in targets:
            self.assertIn(target, shown)

    def test_target_versus_statistic(self):
        sources = figures.Sources("Buses help.", numbers=(97, 250))
        kept = [
            "使总字数达到260词以上",
            "将全文扩展到260词以上，拆分为四段",
            "写到 260-300 words",
            "字数达到 260 以上",
            "扩写到二百六十词",  # Chinese numerals carry no digits: nothing to check
        ]
        for text in kept:
            with self.subTest(text=text):
                self.assertEqual(sources.unsourced(text), [])
        rejected = {
            "公交减少260次事故": ["260"],
            "写一篇 2000 词的报告": ["2000"],
            "减排 80%": ["80%"],
        }
        for text, expected in rejected.items():
            with self.subTest(text=text):
                self.assertEqual(sources.unsourced(text), expected)

    def test_earlier_rules_still_hold(self):
        for essay_text in ("The service began in 1980.", "The city runs 180 buses."):
            self.assertEqual(figures.Sources(essay_text).unsourced("减排 80%"), ["80%"])
        self.assertEqual(figures.Sources("An 80% cut.").unsourced("减排 80%"), [])


class ChinesePercentTest(unittest.TestCase):
    def test_chinese_percentages_are_values_not_substrings(self):
        self.assertEqual(figures.Sources("No figures.").unsourced("降低百分之8"), ["百分之8"])
        self.assertEqual(figures.Sources("About 80% ride.").unsourced("降低百分之八十"), [])
        self.assertEqual(
            figures.Sources("降低百分之八十一").unsourced("降低百分之八十"), ["百分之八十"]
        )
        self.assertEqual(figures.Sources("81% of riders").unsourced("百分之八十一"), [])

    def test_chinese_numerals(self):
        for text, value in (
            ("八十", "80"),
            ("八十一", "81"),
            ("一百零五", "105"),
            ("十", "10"),
            ("五点五", "5.5"),
        ):
            self.assertEqual(figures.cn_number(text), value)


# Context the reviewer verified in the same paragraph as each real "no support" finding.
CONTEXT = {
    "t2-weak": (
        "So goverment should make it cheap and more fast.",
        "If the bus is more better, people will use it more and the traffic will be less.",
    ),
    "t2-mid": (
        "For example, after my city opened a new metro line, the main road to the city centre "
        "became much less crowded during rush hour.",
        "If buses and trains are frequent, cheap and reliable, many drivers will choose them, "
        "which will reduce traffic jams.",
    ),
    "t2-under-length": (
        "However, new roads are still useful in the countryside, where there are not many buses.",
        "where there are not many buses",
    ),
}


def with_support(sample_id, quote, support):
    raw = real(sample_id)
    problem = next(p for p in raw["argument"]["problems"] if p["quote"].startswith(quote[:40]))
    problem["support_found"] = support
    return raw, problem


class SupportFoundTest(unittest.TestCase):
    def test_real_findings_without_the_field_stay_problems(self):
        # These outputs predate support_found: nothing is reclassified by guessing.
        self.assertEqual(
            argument.problem_types(evaluate("t2-weak")["argument"]), ["unsupported", "unsupported"]
        )
        self.assertEqual(
            argument.problem_types(evaluate("t2-mid")["argument"]), ["example_not_linked"]
        )

    def test_support_quoted_from_the_same_paragraph_moves_the_finding(self):
        for sample_id, (quote, support) in CONTEXT.items():
            with self.subTest(sample=sample_id):
                raw, problem = with_support(sample_id, quote, [support])
                before = len(raw["argument"]["problems"])
                mapped = evaluate(sample_id, raw)["argument"]
                self.assertEqual(len(mapped["problems"]), before - 1)
                self.assertEqual(mapped["reclassified"], 1)
                moved = mapped["improvements"][0]
                self.assertEqual(moved["from_type"], problem["type"])
                self.assertEqual(moved["support"], [support])
                self.assertTrue(any("简短的支撑不等于没有支撑" in n for n in mapped["notes"]))
                text = "\n".join(copytext.argument_lines(mapped))
                self.assertIn(f"原判“{argument.PROBLEM_TYPES[problem['type']]}”，同段已有", text)

    def test_support_must_be_real_in_the_same_paragraph_and_not_the_quote_itself(self):
        quote, _support = CONTEXT["t2-weak"]
        other_paragraph = (
            "In conclusion, I think goverment should spend more money for public transport"
        )
        for bad in ([quote], ["Buses are always on time everywhere."], [other_paragraph], "x", [3]):
            with self.subTest(support=bad):
                raw, _problem = with_support("t2-weak", quote, bad)
                mapped = evaluate("t2-weak", raw)["argument"]
                self.assertEqual(mapped["reclassified"], 0)
                self.assertEqual(argument.problem_types(mapped), ["unsupported", "unsupported"])

    def test_other_problem_types_are_not_moved(self):
        raw = real("t2-off-topic")
        for problem in raw["argument"]["problems"]:
            problem["support_found"] = [raw["argument"]["paragraphs"][0]["main_point"]]
        mapped = evaluate("t2-off-topic", raw)["argument"]
        self.assertEqual(mapped["reclassified"], 0)

    def test_prompt_requires_support_found_and_reads_the_whole_paragraph(self):
        self.assertIn("read the WHOLE paragraph", prompts.ARGUMENT_CHECKLIST)
        self.assertIn("without any closing 'this shows' sentence", prompts.ARGUMENT_CHECKLIST)
        sub = FX["submissions"]["t2-weak"]
        from tools.ielts_writing_ai import essay

        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(sub["essay_text"]))
        self.assertIn('"support_found": [str (verbatim)]', messages[0]["content"])
        self.assertIn("an equally good alternative wording is not an issue", messages[0]["content"])
        self.assertIn('"paragraph_count": 5', messages[1]["content"])
        self.assertGreaterEqual(
            int(prompts.PROMPT_VERSION.rsplit(".", 1)[1]), 6
        )  # introduced in .6


class CountClaimTest(unittest.TestCase):
    def test_real_task1_count_errors_get_corrections(self):
        result = evaluate("t1-no-image")
        self.assertEqual(
            result["count_corrections"],
            [
                "评价中说原文是“四段式”，按换行计原文实际有 5 段，请以原文为准。",
                "评价中说“figure”多次出现，原文中只出现 1 次，请以原文为准。",
            ],
        )
        for note in result["count_corrections"]:
            self.assertIn(note, result["warnings"])
            self.assertIn(note, copytext.evaluation_text(result, {}))
        # The real output also found the built-in A/C contradiction, in Chinese.
        self.assertEqual(len(result["consistency_issues"]), 1)

    def test_correct_or_unrelated_counts_are_left_alone(self):
        essay_text = "Intro.\nOverall, A rose.\nBy 2000, it rose.\nBy 2020, it rose.\nIn summary."
        for text in (
            "全文共五段",
            "分为 5 段",
            "rose 反复出现",
            "两个主体段之间衔接自然",
            "四个国家",
        ):
            with self.subTest(text=text):
                self.assertEqual(review._count_corrections([text], essay_text), [])
        self.assertEqual(len(review._count_corrections(["三段式结构"], essay_text)), 1)

    def test_task2_real_outputs_have_no_count_corrections(self):
        for sample_id in FX["evaluation_attempts"]:
            if sample_id != "t1-no-image":
                with self.subTest(sample=sample_id):
                    self.assertEqual(evaluate(sample_id)["count_corrections"], [])


class ReportTest(unittest.TestCase):
    def run_data(self):
        samples = []
        for sample_id, sub in FX["submissions"].items():
            samples.append(
                {
                    "id": sample_id,
                    "task_type": sub["task_type"],
                    "submission": sub,
                    "generations": {"evaluate": {"status": "ready", "result": evaluate(sample_id)}},
                }
            )
        return {"samples": samples, "calls": []}

    def test_evidence_metrics_total_every_advice_path_and_count_corrections(self):
        metrics = realcheck._evidence_metrics(self.run_data())
        self.assertEqual(metrics["suggestions_removed"]["total"], 0)
        self.assertEqual(metrics["count_corrections"], 2)
        line = realcheck._removed_line({"criteria": 1, "priorities": 1, "argument": 0, "total": 2})
        self.assertIn("整份评价合计）：2 条（评分项 1、论证结构 0、提升重点 1）", line)

    def test_argument_line_says_it_is_only_the_argument_part(self):
        metrics = realcheck._argument_metrics(self.run_data())
        markdown = "\n".join(realcheck._argument_markdown(metrics))
        self.assertIn(
            "论证部分的建议因含无来源数字被删去 0 条（整份评价的合计见“证据与内容”）", markdown
        )
        self.assertIn("改列可选优化 0 条", markdown)


if __name__ == "__main__":
    unittest.main()
