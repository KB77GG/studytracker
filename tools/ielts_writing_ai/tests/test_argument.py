"""Task 2 argument-structure analysis: verification, scoring independence, prompts,
page/copy output and the realcheck sanity checks."""

import json
import unittest

from tools.ielts_writing_ai import argument, copytext, essay, prompts, realcheck, review
from tools.ielts_writing_ai.llm import FakeClient

from .helpers import TASK2_ESSAY, AppTestCase
from .test_review import evaluation, submission

POSITION = "I partly agree that university should be free"
BODY_1 = "free education can help poor students"
BODY_2 = "governments have limited budgets"
CONCLUSION = "governments should support only students who really need help"


def good_map(**overrides):
    value = {
        "position": {"quote": POSITION, "consistent": True, "comment": "结尾给出部分同意的立场"},
        "paragraphs": [
            {"role": "introduction", "main_point": "university should be free", "verdict": "weak"},
            {"role": "body", "main_point": BODY_1, "verdict": "supports", "comment": "c"},
            {"role": "concession", "main_point": BODY_2, "verdict": "supports"},
            {"role": "conclusion", "main_point": CONCLUSION, "verdict": "supports"},
        ],
        "problems": [
            {
                "type": "unclear_position",
                "quote": "i think this idea has advantages and disadvantages",
                "comment": "开头只说有利有弊，没有表态，和结尾的部分同意不一致。",
                "suggestion": "开头直接写出部分同意的立场。",
            },
            {
                "type": "concession_unanswered",
                "quote": BODY_2,
                "comment": "提出预算有限后没有回应，读者不知道这如何与立场相容。",
            },
        ],
    }
    value.update(overrides)
    return value


class NormalizeTest(unittest.TestCase):
    def test_verified_map_keeps_everything_with_labels(self):
        result = argument.normalize(good_map(), TASK2_ESSAY)
        self.assertEqual(result["dropped"], 0)
        self.assertEqual(result["position"]["quote"], POSITION)
        self.assertTrue(result["position"]["consistent"])
        self.assertEqual([p["role"] for p in result["paragraphs"]], list(argument.ROLES))
        self.assertEqual(result["paragraphs"][2]["role_label"], "让步段")
        self.assertEqual(result["paragraphs"][0]["verdict_label"], "与立场关联偏弱")
        self.assertEqual(
            [p["label"] for p in result["problems"]], ["立场不清或前后不一致", "让步后没有反驳"]
        )
        self.assertEqual(
            argument.problem_types(result), ["unclear_position", "concession_unanswered"]
        )

    def test_unverifiable_or_unknown_items_are_dropped_and_counted(self):
        raw = good_map()
        raw["position"]["quote"] = "Free university is a human right"  # not in the essay
        raw["paragraphs"].append({"role": "body", "main_point": "invented", "verdict": "supports"})
        raw["paragraphs"].append({"role": "rebuttal", "main_point": BODY_1, "verdict": "supports"})
        raw["paragraphs"].append({"role": "body", "main_point": BODY_1, "verdict": "great"})
        raw["paragraphs"].append("not an object")  # ignored, not counted
        raw["problems"] += [
            {"type": "logic_gap", "quote": BODY_1, "comment": "不在类型表里"},
            {"type": "circular", "quote": "an invented sentence", "comment": "引文不在原文"},
            {"type": "circular", "quote": BODY_1, "comment": ""},  # no explanation
        ]
        result = argument.normalize(raw, TASK2_ESSAY)
        self.assertIsNone(result["position"])
        self.assertEqual(len(result["paragraphs"]), 4)
        self.assertEqual(len(result["problems"]), 2)
        self.assertEqual(result["dropped"], 7)

    def test_non_bool_consistency_is_unknown(self):
        raw = good_map()
        raw["position"]["consistent"] = "yes"
        self.assertIsNone(argument.normalize(raw, TASK2_ESSAY)["position"]["consistent"])

    def test_repeated_problem_is_shown_once_and_lists_are_capped(self):
        raw = good_map()
        raw["problems"] = [raw["problems"][1]] * 3 + [
            {"type": t, "quote": BODY_1, "comment": "c"} for t in argument.PROBLEM_TYPES
        ]
        raw["paragraphs"] = raw["paragraphs"] * 3
        result = argument.normalize(raw, TASK2_ESSAY)
        self.assertEqual(len(result["problems"]), argument.MAX_PROBLEMS)
        self.assertEqual(
            sum(
                p["type"] == "concession_unanswered" and p["quote"] == BODY_2
                for p in result["problems"]
            ),
            1,
        )
        self.assertEqual(len(result["paragraphs"]), argument.MAX_PARAGRAPHS)
        self.assertEqual(result["dropped"], 0)

    def test_missing_or_unverifiable_map_is_invalid(self):
        for raw in (None, "text", [], {"paragraphs": []}):
            with self.subTest(raw=raw), self.assertRaises(argument.ArgumentInvalid):
                argument.normalize(raw, TASK2_ESSAY)
        invented = good_map(
            paragraphs=[{"role": "body", "main_point": "not in the essay", "verdict": "supports"}]
        )
        with self.assertRaises(argument.ArgumentInvalid):
            argument.normalize(invented, TASK2_ESSAY)


class EvaluationIntegrationTest(unittest.TestCase):
    def test_task2_evaluation_requires_the_map(self):
        raw = evaluation()
        del raw["argument"]
        with self.assertRaisesRegex(review.InvalidOutput, "论证结构"):
            review.normalize_evaluation(raw, submission())

    def test_dropped_items_become_a_warning(self):
        raw = evaluation()
        raw["argument"]["problems"].append(
            {"type": "circular", "quote": "never written", "comment": "x"}
        )
        result = review.normalize_evaluation(raw, submission())
        self.assertEqual(result["argument"]["dropped"], 1)
        self.assertTrue(any("论证结构分析中有 1 条" in w for w in result["warnings"]))

    def test_argument_does_not_change_any_score(self):
        with_problems = review.normalize_evaluation(evaluation(), submission())
        raw = evaluation()
        raw["argument"]["problems"] = []
        without = review.normalize_evaluation(raw, submission())
        self.assertEqual(with_problems["overall_band"], without["overall_band"])
        self.assertEqual(
            [c["band"] for c in with_problems["criteria"]], [c["band"] for c in without["criteria"]]
        )
        self.assertEqual(len(with_problems["argument"]["problems"]), 1)
        self.assertEqual(without["argument"]["problems"], [])

    def test_task1_ignores_and_does_not_need_the_map(self):
        sub = submission(task_type="task1", image_status="ready")
        self.assertIsNone(review.normalize_evaluation(evaluation(), sub)["argument"])
        raw = evaluation()
        del raw["argument"]
        self.assertIsNone(review.normalize_evaluation(raw, sub)["argument"])


class PromptTest(unittest.TestCase):
    def evaluate_prompt(self, task_type):
        sub = submission(task_type=task_type, essay_text=TASK2_ESSAY, prompt_text="p")
        messages, context = prompts.build_evaluate(sub, essay.split_sentences(TASK2_ESSAY))
        return messages[0]["content"] + messages[-1]["content"], context

    def test_task2_prompt_has_checklist_and_every_problem_type(self):
        text, context = self.evaluate_prompt("task2")
        self.assertEqual(context["task_type"], "task2")
        self.assertIn(prompts.ARGUMENT_CHECKLIST, text)
        for kind in argument.PROBLEM_TYPES:
            self.assertIn(kind, text)
        for value in list(argument.ROLES) + list(argument.VERDICTS):
            self.assertIn(value, text)
        self.assertIn("NOT a separate score", text)

    def test_output_budget_leaves_room_for_the_map(self):
        # Real evaluations without the map used up to ~1.6k completion tokens.
        self.assertGreaterEqual(prompts.MAX_TOKENS["evaluate"], 4500)

    def test_task1_prompt_has_no_argument_section(self):
        text, _ = self.evaluate_prompt("task1")
        self.assertNotIn(prompts.ARGUMENT_CHECKLIST, text)
        self.assertNotIn("concession_unanswered", text)

    def test_task2_rewrite_is_asked_to_repair_the_argument_chain(self):
        sub = submission(essay_text=TASK2_ESSAY, prompt_text="p")
        sentences = essay.split_sentences(TASK2_ESSAY)
        messages, _ = prompts.build_rewrite(sub, sentences)
        text = "".join(str(m["content"]) for m in messages)
        self.assertIn("例子未回扣论点", text)
        task1_messages, _ = prompts.build_rewrite(dict(sub, task_type="task1"), sentences)
        task1 = "".join(str(m["content"]) for m in task1_messages)
        self.assertNotIn("例子未回扣论点", task1)


class CopyTextTest(unittest.TestCase):
    def test_copy_text_lists_position_paragraphs_and_problems(self):
        raw = evaluation()
        result = review.normalize_evaluation(raw, submission())
        text = copytext.evaluation_text(result, {})
        self.assertIn("论证结构检查（AI 标注，引文均已在原文中核实；不单独计分", text)
        self.assertIn("立场：“i dont agree with it”（前后一致）", text)
        self.assertIn("主体段【与立场关联偏弱】“Governments should invest more money”", text)
        self.assertIn("✗ [论点缺少解释或支撑] “Governments should invest more money”", text)
        self.assertIn("→ 建议：补一句原因和一个具体结果。", text)

    def test_copy_text_without_problems_does_not_claim_the_argument_is_perfect(self):
        raw = evaluation()
        raw["argument"]["problems"] = []
        raw["argument"]["position"] = None
        text = copytext.evaluation_text(review.normalize_evaluation(raw, submission()), {})
        self.assertIn("立场：没有找到可核实的立场句。", text)
        self.assertIn("不代表论证没有可改进之处", text)

    def test_task1_copy_has_no_argument_section(self):
        sub = submission(task_type="task1", image_status="ready")
        text = copytext.evaluation_text(review.normalize_evaluation(evaluation(), sub), {})
        self.assertNotIn("论证结构检查", text)


class MissingArgumentFirstClient(FakeClient):
    """First evaluation is complete except for the argument map."""

    def __init__(self):
        super().__init__()
        self.evaluate_messages = []

    def complete(self, messages, **kwargs):
        result = super().complete(messages, **kwargs)
        if (kwargs.get("context") or {}).get("kind") == "evaluate":
            self.evaluate_messages.append(messages)
            if len(self.evaluate_messages) == 1:
                body = json.loads(result.text)
                body.pop("argument")
                result.text = json.dumps(body, ensure_ascii=False)
        return result


class EndToEndTest(AppTestCase):
    def evaluate(self):
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        data = client.get(f"/api/submissions/{public_id}").get_json()
        return data["submission"]["generations"]["evaluate"]

    def test_demo_task2_evaluation_carries_a_verified_map_and_copy_section(self):
        generation = self.evaluate()
        self.assertEqual(generation["status"], "ready")
        mapped = generation["result"]["argument"]
        self.assertEqual(mapped["dropped"], 0)
        self.assertGreaterEqual(len(mapped["paragraphs"]), 3)
        for paragraph in mapped["paragraphs"]:
            self.assertTrue(essay.contains_quote(TASK2_ESSAY, paragraph["main_point"]))
        self.assertIn("论证结构检查", generation["copy"]["evaluation"])

    def test_missing_map_is_retried_once_with_the_reason(self):
        self.client_llm = MissingArgumentFirstClient()
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        generation = self.evaluate()
        self.assertEqual(generation["status"], "ready")
        self.assertIsNotNone(generation["result"]["argument"])
        self.assertEqual(len(self.client_llm.evaluate_messages), 2)
        self.assertIn("缺少论证结构分析", self.client_llm.evaluate_messages[1][-1]["content"])


def sample(sample_id, mapped, expect, task_type="task2"):
    result = {"criteria": [], "overall_band": 6.0}
    if mapped is not None:
        result["argument"] = argument.normalize(mapped, TASK2_ESSAY)
    return {
        "id": sample_id,
        "task_type": task_type,
        "expect": expect,
        "generations": {"evaluate": {"status": "ready", "result": result}},
    }


STRONG = {"argument_max_problems": 1, "argument_forbid": ["off_position", "unclear_position"]}
OFF = {"argument_any_of": ["off_position", "irrelevant"]}


class RealcheckTest(unittest.TestCase):
    def outcomes(self, item):
        return {c["check"]: c["ok"] for c in realcheck._argument_checks(item, item["expect"])}

    def test_strong_sample_flags_too_many_or_position_problems(self):
        outcomes = self.outcomes(sample("t2-strong", good_map(), STRONG))
        self.assertEqual(sorted(outcomes.values()), [False, False])  # 2 problems, one unclear
        clean = good_map(problems=[{"type": "overgeneralized", "quote": BODY_1, "comment": "c"}])
        self.assertTrue(all(self.outcomes(sample("t2-strong", clean, STRONG)).values()))

    def test_weak_sample_needs_at_least_one_problem(self):
        expect = {"argument_min_problems": 1}
        self.assertTrue(all(self.outcomes(sample("t2-weak", good_map(), expect)).values()))
        empty = good_map(problems=[])
        self.assertFalse(any(self.outcomes(sample("t2-weak", empty, expect)).values()))

    def test_off_topic_sample_accepts_a_problem_type_or_an_off_position_paragraph(self):
        self.assertFalse(any(self.outcomes(sample("t2-off-topic", good_map(), OFF)).values()))
        typed = good_map(problems=[{"type": "irrelevant", "quote": BODY_1, "comment": "c"}])
        self.assertTrue(all(self.outcomes(sample("t2-off-topic", typed, OFF)).values()))
        verdict = good_map(problems=[])
        verdict["paragraphs"][1]["verdict"] = "off_position"
        self.assertTrue(all(self.outcomes(sample("t2-off-topic", verdict, OFF)).values()))

    def test_missing_map_fails_instead_of_passing_silently(self):
        item = sample("t2-strong", None, STRONG)
        self.assertEqual(self.outcomes(item), {"有论证结构分析": False})
        self.assertEqual(realcheck._argument_checks(item, {"overall_min": 7}), [])

    def test_metrics_count_verified_and_dropped_items(self):
        raw = good_map()
        raw["problems"].append({"type": "circular", "quote": "never written", "comment": "x"})
        run_data = {
            "samples": [
                sample("a", raw, {}),
                sample("b", None, {}),
                sample("t1", None, {}, task_type="task1"),
            ]
        }
        metrics = realcheck._argument_metrics(run_data)
        self.assertEqual((metrics["task2_evaluations"], metrics["with_argument"]), (2, 1))
        self.assertEqual(
            (metrics["paragraphs"], metrics["problems"], metrics["dropped"]), (4, 2, 1)
        )
        self.assertAlmostEqual(metrics["dropped_rate"], round(1 / 8, 3))
        self.assertEqual(
            metrics["problem_types"], {"unclear_position": 1, "concession_unanswered": 1}
        )
        markdown = "\n".join(realcheck._argument_markdown(metrics))
        self.assertIn("## 论证结构（Task 2，不单独计分）", markdown)
        self.assertIn("无法核实而丢弃 1 条", markdown)

    def test_builtin_samples_carry_the_argument_expectations(self):
        from tools.ielts_writing_ai import samples

        expects = {s["id"]: s["expect"] for s in samples.SAMPLES}
        self.assertEqual(expects["t2-strong"]["argument_max_problems"], 1)
        self.assertEqual(expects["t2-weak"]["argument_min_problems"], 1)
        self.assertIn("off_position", expects["t2-off-topic"]["argument_any_of"])


if __name__ == "__main__":
    unittest.main()
