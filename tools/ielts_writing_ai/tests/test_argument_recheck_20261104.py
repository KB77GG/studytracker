"""Regressions from the third real run (argument structure, 8 evaluate calls, prompt
iwa-2026-11-04.4) and its manual review (docs/design/ielts-writing-ai-argument-recheck-
20261104). The texts in the fixture are the real deepseek-flash outputs for the built-in
synthetic samples; old outputs are replayed through the new rules (prompt .5)."""

import json
import unittest
from pathlib import Path

from tools.ielts_writing_ai import argument, copytext, essay, prompts, realcheck, review, samples
from tools.ielts_writing_ai.llm import parse_strict_json

from .helpers import TASK2_ESSAY
from .test_argument import FORBID_CHECK, STRONG, good_map, sample
from .test_review import REASON

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104c.json").read_text(encoding="utf-8")
)
EXPECT = {s["id"]: s["expect"] for s in samples.SAMPLES}


def real(sample_id, attempt=-1):
    return parse_strict_json(FX["evaluation_attempts"][sample_id][attempt])


def evaluate(sample_id, raw=None):
    return review.checked(
        review.normalize_evaluation,
        raw if raw is not None else real(sample_id),
        FX["submissions"][sample_id],
    )


def checks(sample_id, result):
    item = {
        "id": sample_id,
        "task_type": FX["submissions"][sample_id]["task_type"],
        "expect": EXPECT[sample_id],
        "generations": {"evaluate": {"status": "ready", "result": result}},
    }
    return {c["check"].split("（")[0]: c for c in realcheck._argument_checks(item, item["expect"])}


class RealOutputTest(unittest.TestCase):
    def test_weak_first_attempt_stays_rejected_and_its_nesting_is_named_on_retry(self):
        text = FX["evaluation_attempts"]["t2-weak"][0]
        self.assertIsNone(parse_strict_json(text))  # unclosed brace: no lenient repair
        nested = json.loads(text + "}")  # only to show what the structure check says
        self.assertEqual(list(nested), ["criteria"])
        with self.assertRaisesRegex(review.InvalidOutput, "放错了位置"):
            evaluate("t2-weak", nested)

    def test_weak_partial_agreement_is_not_adopted_as_a_contradiction(self):
        mapped = evaluate("t2-weak")["argument"]
        # "public transport first, roads when necessary": the model said inconsistent
        # and conclusion_inconsistent, but never quoted two passages that conflict.
        self.assertIsNone(mapped["position"]["consistent"])
        self.assertNotIn("conclusion_inconsistent", argument.problem_types(mapped))
        self.assertTrue(any("限定条件" in n for n in mapped["notes"]))
        self.assertEqual(mapped["self_conflicts"], 1)
        self.assertTrue(checks("t2-weak", evaluate("t2-weak"))["论证问题 ≥ 1 条"]["ok"])

    def test_strong_self_contradiction_and_unsourced_case_are_removed(self):
        result = evaluate("t2-strong")
        mapped = result["argument"]
        self.assertTrue(mapped["position"]["consistent"])
        self.assertNotIn("conclusion_inconsistent", argument.problem_types(mapped))
        self.assertEqual(mapped["suggestions_removed"], 1)  # "405 号公路" is not in the essay
        removed = [p for p in mapped["problems"] if p["suggestion_removed"]]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["suggestion"], "")
        outcome = checks("t2-strong", result)
        self.assertTrue(outcome[FORBID_CHECK]["ok"])
        self.assertTrue(outcome["找到可核实的立场句"]["ok"])
        # Still two over-prescriptive "unsupported" findings (reasons present but brief):
        # only the new prompt rules can change that, so the strict check keeps failing on
        # this old output instead of being relaxed.
        self.assertEqual(argument.problem_types(mapped), ["unsupported", "unsupported"])
        self.assertFalse(outcome["论证问题 ≤ 1 条"]["ok"])

    def test_mid_unsourced_percentage_is_removed_from_every_advice_path(self):
        # Judgment review of 93d47ec: the same "over 80%" advice also came back in the
        # TR issue suggestion and so reached the page and the copied evaluation.
        raw = real("t2-mid")
        raw_text = json.dumps(raw, ensure_ascii=False)
        self.assertEqual(raw_text.count("80%"), 2)  # argument problem + TR issue
        result = evaluate("t2-mid")
        self.assertEqual(
            result["suggestions_removed"],
            {"criteria": 1, "priorities": 0, "argument": 1, "total": 2},
        )
        tr_issue = next(i for i in result["criteria"][0]["issues"] if i["suggestion_removed"])
        self.assertEqual(tr_issue["suggestion"], "")
        problem = next(p for p in result["argument"]["problems"] if p["suggestion_removed"])
        self.assertEqual(problem["type"], "unsupported")
        # Nothing the page renders (the stored result) or the copy text carries has it.
        self.assertNotIn("80%", json.dumps(result, ensure_ascii=False))
        copied = copytext.evaluation_text(result, {})
        self.assertNotIn("80%", copied)
        self.assertEqual(copied.count("（建议含原文和题目都没有的具体数字，已删去）"), 2)
        self.assertTrue(
            any("2 条建议" in w and "评分项 1 条、论证结构 1 条" in w for w in result["warnings"])
        )
        self.assertNotIn("80", FX["submissions"]["t2-mid"]["essay_text"])

    def test_one_paragraph_essay_gets_one_paragraph_entry(self):
        mapped = evaluate("t2-under-length")["argument"]
        self.assertEqual(len(real("t2-under-length")["argument"]["paragraphs"]), 5)
        self.assertEqual([(p["p"], p["role"]) for p in mapped["paragraphs"]], [(1, "introduction")])
        self.assertEqual((mapped["duplicates"], mapped["real_paragraphs"]), (4, 1))
        self.assertTrue(any("只有 1 段" in n for n in mapped["notes"]))

    def test_off_topic_essay_is_still_flagged(self):
        result = evaluate("t2-off-topic")
        self.assertTrue(checks("t2-off-topic", result)["应标出 off_position / irrelevant"]["ok"])
        self.assertEqual({p["verdict"] for p in result["argument"]["paragraphs"]}, {"off_position"})

    def test_five_paragraph_essays_keep_one_entry_per_real_paragraph(self):
        for sample_id in ("t2-weak", "t2-mid", "t2-good", "t2-strong", "t2-off-topic"):
            with self.subTest(sample=sample_id):
                mapped = evaluate(sample_id)["argument"]
                self.assertEqual([p["p"] for p in mapped["paragraphs"]], [1, 2, 3, 4, 5])

    def test_english_task1_evaluation_is_rejected_and_retried(self):
        with self.assertRaisesRegex(review.InvalidOutput, "简体中文"):
            evaluate("t1-no-image")
        raw = chinese(real("t1-no-image"))
        result = evaluate("t1-no-image", raw)
        # The real output also missed the built-in contradiction (consistency_issues []).
        self.assertEqual(result["consistency_issues"], [])
        item = {
            "id": "t1-no-image",
            "task_type": "task1",
            "expect": EXPECT["t1-no-image"],
            "generations": {"evaluate": {"status": "ready", "result": result}},
        }
        found = [c for c in realcheck._sanity({"samples": [dict(item, submission={})]})["checks"]]
        self.assertFalse(next(c for c in found if c["check"].startswith("指出文内数据矛盾"))["ok"])


def chinese(raw):
    """The real Task 1 output with its explanations replaced by Chinese ones (to test
    what comes after the language check)."""
    for item in raw["criteria"].values():
        if isinstance(item, dict):
            item["summary"] = REASON
            for entry in item.get("strengths", []) + item.get("issues", []):
                entry["comment"] = "说明。"
    raw["overall_comment"] = "整体结构清楚，但比较说法需要与文中数字一致。"
    raw["priorities"] = ["核对比较说法", "减少重复"]
    return raw


T1_CLAIM = "Country A had the highest level of ownership in both years"


class Task1ComparisonTest(unittest.TestCase):
    def evaluate(self, **fields):
        raw = chinese(real("t1-no-image"))
        raw.pop("consistency_issues", None)
        raw.update(fields)
        return evaluate("t1-no-image", raw)

    def test_contradicted_claim_with_its_figures_is_reported(self):
        result = self.evaluate(
            comparisons=[
                {
                    "claim": T1_CLAIM,
                    "figures": ["about 75%", "nearly 80%", "invented 99%"],
                    "holds": False,
                    "comment": "2020 年 C 约 80%，高于 A 的约 75%。",
                },
                {"claim": "Country D had by far the lowest figure", "figures": [], "holds": True},
            ]
        )
        self.assertEqual(result["comparisons_checked"], 2)
        issue = result["consistency_issues"][0]
        self.assertEqual(issue["quote"], T1_CLAIM)
        self.assertEqual(issue["figures"], ["about 75%", "nearly 80%"])
        self.assertTrue(any("引文已在原文中核实" in w for w in result["warnings"]))
        text = copytext.evaluation_text(result, {})
        self.assertIn("对照：“about 75%”；“nearly 80%”", text)

    def test_contradiction_without_figures_or_claim_is_dropped(self):
        result = self.evaluate(
            comparisons=[
                {"claim": T1_CLAIM, "figures": [], "holds": False, "comment": "矛盾。"},
                {"claim": T1_CLAIM, "figures": [T1_CLAIM], "holds": False, "comment": "矛盾。"},
                {
                    "claim": "An invented claim",
                    "figures": ["about 75%"],
                    "holds": False,
                    "comment": "x",
                },
                "not an object",
            ]
        )
        self.assertEqual(result["consistency_issues"], [])
        self.assertEqual(result["comparisons_checked"], 2)
        self.assertTrue(any("另提出 4 条" in w for w in result["warnings"]))

    def test_older_free_list_is_still_read_and_merged(self):
        result = self.evaluate(
            comparisons=[
                {"claim": T1_CLAIM, "figures": ["nearly 80%"], "holds": False, "comment": "矛盾。"}
            ],
            consistency_issues=[{"quote": T1_CLAIM, "comment": "同一条"}],
        )
        self.assertEqual(len(result["consistency_issues"]), 1)

    def test_prompt_asks_for_every_comparison_and_a_chinese_reply(self):
        sub = FX["submissions"]["t1-no-image"]
        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(sub["essay_text"]))
        self.assertIn(prompts.COMPARISON_RULE, messages[0]["content"])
        self.assertIn('"comparisons": [K, ...]', messages[0]["content"])
        self.assertNotIn('"argument": A', messages[0]["content"])
        self.assertTrue(messages[1]["content"].endswith(prompts.CHINESE_REMINDER))


class ChineseExplanationTest(unittest.TestCase):
    def raw(self):
        from .test_review import evaluation

        return evaluation()

    def normalize(self, raw):
        from .test_review import submission

        return review.normalize_evaluation(raw, submission())

    def test_chinese_reasons_with_english_quotes_pass(self):
        raw = self.raw()
        raw["criteria"]["grammar"]["summary"] = "句子“I don't agree”使用正确，但复杂句较少。"
        raw["criteria"]["grammar"]["issues"][0]["comment"] = "Missing apostrophe."
        self.assertIsNotNone(self.normalize(raw)["overall_band"])

    def test_an_english_reason_or_overall_comment_is_rejected(self):
        for path in (("criteria", "task", "summary"), ("overall_comment",)):
            with self.subTest(path=path):
                raw = self.raw()
                target = raw
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = "The position is clear but the ideas are not developed enough."
                with self.assertRaisesRegex(review.InvalidOutput, "简体中文"):
                    self.normalize(raw)

    def test_mostly_english_comments_are_rejected(self):
        raw = self.raw()
        for item in raw["criteria"].values():
            for entry in item["strengths"] + item["issues"]:
                entry["comment"] = "Good point."
        with self.assertRaisesRegex(review.InvalidOutput, "简体中文"):
            self.normalize(raw)


class PairedClaimTest(unittest.TestCase):
    PAIR = {
        "type": "inconsistent_position",
        "quote": "i think this idea has advantages and disadvantages",
        "conflicts_with": "I partly agree that university should be free",
        "comment": "开头只说有利有弊，结尾才表态。",
    }

    def normalize(self, problems, **position):
        mapped = good_map(problems=problems)
        mapped["position"].update(position)
        return argument.normalize(mapped, TASK2_ESSAY)

    def test_contradiction_needs_two_distinct_verified_passages(self):
        one_sided = dict(self.PAIR, conflicts_with=None)
        same = dict(self.PAIR, conflicts_with=self.PAIR["quote"])
        invented = dict(self.PAIR, conflicts_with="I strongly disagree with free tuition")
        mapped = self.normalize([one_sided, same, invented], consistent=False)
        self.assertEqual(mapped["problems"], [])
        self.assertEqual(mapped["dropped"], 3)
        mapped = self.normalize([self.PAIR], consistent=False)
        self.assertEqual(mapped["problems"][0]["conflicts_with"], self.PAIR["conflicts_with"])
        self.assertFalse(mapped["position"]["consistent"])  # backed by a verified pair
        self.assertEqual(mapped["self_conflicts"], 0)

    def test_consistent_position_next_to_a_contradiction_is_surfaced(self):
        mapped = self.normalize([self.PAIR], consistent=True)
        self.assertIsNone(mapped["position"]["consistent"])
        self.assertTrue(mapped["problems"][0]["needs_review"])
        self.assertEqual(mapped["self_conflicts"], 1)
        text = "\n".join(copytext.argument_lines(mapped))
        self.assertIn("[立场前后矛盾]（需人工确认）", text)
        self.assertIn("↔ 与之矛盾：“I partly agree that university should be free”", text)

    def test_off_position_problem_in_a_supporting_paragraph_is_surfaced(self):
        problem = {
            "type": "off_position",
            "quote": "free education can help poor students",
            "comment": "偏离",
        }
        mapped = self.normalize([problem])
        self.assertEqual(mapped["problems"][0]["p"], 2)
        self.assertTrue(mapped["problems"][0]["needs_review"])
        self.assertTrue(any("第 2 段" in n for n in mapped["notes"]))

    def test_strong_check_counts_problems_not_improvements(self):
        mapped = good_map(
            problems=[],
            improvements=[{"quote": "free education", "suggestion": "可以举一个假设的例子"}] * 3,
        )
        outcome = {
            c["check"].split("（")[0]: c["ok"]
            for c in realcheck._argument_checks(sample("t2-strong", mapped, STRONG), STRONG)
        }
        self.assertTrue(outcome["论证问题 ≤ 1 条"])
        normalized = argument.normalize(mapped, TASK2_ESSAY)
        self.assertEqual(len(normalized["improvements"]), 3)
        self.assertIn("可选优化（不是错误", "\n".join(copytext.argument_lines(normalized)))


class ParagraphBindingTest(unittest.TestCase):
    ESSAY = "We agree. Buses help.\nBuses help.\nIn conclusion, we agree."

    def entry(self, **fields):
        return {"role": "body", "verdict": "supports", "main_point": "Buses help.", **fields}

    def test_model_number_only_chooses_between_paragraphs_that_contain_the_quote(self):
        mapped = argument.normalize({"paragraphs": [self.entry(p=2)]}, self.ESSAY)
        self.assertEqual(mapped["paragraphs"][0]["p"], 2)
        mapped = argument.normalize(
            {"paragraphs": [self.entry(p=3), self.entry(p=True)]}, self.ESSAY
        )
        self.assertEqual([p["p"] for p in mapped["paragraphs"]], [1])  # location wins
        self.assertEqual(mapped["duplicates"], 1)

    def test_quote_spanning_two_paragraphs_is_not_a_paragraph_centre(self):
        raw = {"paragraphs": [self.entry(main_point="Buses help. Buses help.")]}
        with self.assertRaises(argument.ArgumentInvalid):
            argument.normalize(raw, self.ESSAY)

    def test_task2_prompt_numbers_the_real_paragraphs(self):
        sub = FX["submissions"]["t2-weak"]
        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(sub["essay_text"]))
        payload = json.loads(messages[1]["content"].split("\n", 1)[1].rsplit("\n", 1)[0])
        self.assertEqual([p["p"] for p in payload["essay_paragraphs"]], [1, 2, 3, 4, 5])
        self.assertNotIn("essay", payload)
        self.assertIn('"argument": A', messages[0]["content"])
        self.assertIn("never inside a criterion", messages[0]["content"])
        self.assertEqual(prompts.PROMPT_VERSION, "iwa-2026-11-04.6")

    def test_prompt_states_the_reviewed_judgment_rules(self):
        for phrase in (
            "A qualified position is ONE position",
            "quote BOTH",
            "A named city, study or statistic is NEVER required",
            "A concession that sets the scope of the position needs no rebuttal",
            "go in 'improvements', never in 'problems'",
            "Never invent facts",
        ):
            self.assertIn(phrase, prompts.ARGUMENT_CHECKLIST)


class FigureTest(unittest.TestCase):
    def test_unsourced_figures(self):
        essay_text = "About 75% of people use buses, compared with 40 in 2010."
        cases = {
            "补充数据，如人均排放降低 80% 以上": ["80%"],
            "可以写百分之八十": ["百分之八十"],
            "举洛杉矶 405 号公路为例": ["405"],
            "In 2015, London introduced a charge": ["2015"],
            "第 2 段可以补 1 个例子": [],
            "约 75% 的人": [],
            "2010 年的数字": [],
            "补一个假设的例子": [],
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(argument.unsourced_figures(text, essay_text), expected)

    def test_improvement_with_only_an_unsourced_figure_is_dropped(self):
        mapped = good_map(
            improvements=[{"quote": "free education", "suggestion": "写上 90% 的学生受益"}]
        )
        normalized = argument.normalize(mapped, TASK2_ESSAY)
        self.assertEqual(normalized["improvements"], [])
        self.assertEqual(normalized["suggestions_removed"], 1)


class ReportTest(unittest.TestCase):
    def test_off_topic_rewrite_check_is_skipped_when_rewrite_did_not_run(self):
        item = {"id": "t2-off-topic", "generations": {}, "submission": {}}
        self.assertIsNone(realcheck._off_topic_rewrite_check(item)["ok"])
        failed = {"id": "t2-off-topic", "generations": {"rewrite": {"status": "failed"}}}
        self.assertIsNone(realcheck._off_topic_rewrite_check(failed)["ok"])

    def test_skipped_checks_are_not_counted_as_passed(self):
        result = evaluate("t2-off-topic")
        item = {
            "id": "t2-off-topic",
            "task_type": "task2",
            "expect": EXPECT["t2-off-topic"],
            "submission": FX["submissions"]["t2-off-topic"],
            "generations": {"evaluate": {"status": "ready", "result": result}},
        }
        sanity = realcheck._sanity({"samples": [item]})
        skipped = [c for c in sanity["checks"] if c["ok"] is None]
        self.assertEqual([c["detail"] for c in skipped], ["本批未运行改写"])
        self.assertEqual((sanity["skipped"], sanity["total"]), (1, len(sanity["checks"]) - 1))
        self.assertEqual(sanity["passed"], sum(1 for c in sanity["checks"] if c["ok"] is True))

    def test_argument_section_is_shown_even_when_every_task2_attempt_was_rejected(self):
        metrics = {
            "task2_evaluations": 0,
            "evaluate_attempts": 2,
            "attempts_rejected_for_argument": 2,
            "with_argument": 0,
            "with_position": 0,
            "paragraphs": 0,
            "problems": 0,
            "improvements": 0,
            "self_conflicts": 0,
            "suggestions_removed": 0,
            "returned": 0,
            "kept": 0,
            "dropped": 0,
            "duplicates": 0,
            "over_limit": 0,
            "dropped_rate": None,
            "problem_types": {},
            "paragraph_verdicts": {},
        }
        markdown = "\n".join(realcheck._argument_markdown(metrics))
        self.assertIn("其中 2 次因缺少论证结构", markdown)


if __name__ == "__main__":
    unittest.main()
