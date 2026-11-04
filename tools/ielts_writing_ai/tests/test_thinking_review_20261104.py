"""Regressions from the review of 90194f0 / bd93e1c
(docs/design/ielts-writing-ai-thinking-review-20261104):
1. a removed unsourced "80%" came back through a reclassified improvement;
2. thinking that used up the budget (empty answer, finish_reason=length) was counted
   as "empty", and failed calls' reasoning tokens were left out of the totals;
3. the manual-review sheet lost paired conflicts, "needs review" and Task 1 evidence;
4. same-condition checks did not look at what actually reached the model."""

import json
import shutil
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path
from unittest import mock

from tools.ielts_writing_ai import copytext, realcheck, realcheck_compare, review
from tools.ielts_writing_ai.llm import ChatClient, FakeClient, LLMError, parse_strict_json

from .helpers import settings_for
from .test_llm import StubHandler

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104d.json").read_text(encoding="utf-8")
)
QUOTE = "So goverment should make it cheap and more fast."
SUPPORT = "If the bus is more better, people will use it more and the traffic will be less."
FIGURE = "补一句：这样能减少80%排放。"


def weak_with(comment, suggestion):
    raw = parse_strict_json(FX["evaluation_attempts"]["t2-weak"][0])
    problem = next(p for p in raw["argument"]["problems"] if p["quote"] == QUOTE)
    problem.update(support_found=[SUPPORT], comment=comment, suggestion=suggestion)
    return raw


def evaluate(raw):
    return review.normalize_evaluation(raw, FX["submissions"]["t2-weak"])


def visible(result) -> str:
    """Everything the page renders (stored result) and the copy text carries."""
    return json.dumps(result, ensure_ascii=False) + copytext.evaluation_text(result, {})


class ReclassifiedAdviceTest(unittest.TestCase):
    def moved(self, result):
        return next(i for i in result["argument"]["improvements"] if i.get("from_type"))

    def test_reviewer_case_comment_and_suggestion_both_with_80_percent(self):
        result = evaluate(weak_with(FIGURE, FIGURE))
        moved = self.moved(result)
        self.assertEqual((moved["suggestion"], moved["suggestion_removed"]), ("", True))
        self.assertEqual(moved["support"], [SUPPORT])  # the reclassification is kept
        self.assertNotIn("80%", visible(result))
        self.assertEqual(result["suggestions_removed"]["argument"], 1)
        self.assertIn(
            "（建议含原文和题目都没有的具体数字，已删去）", copytext.evaluation_text(result, {})
        )

    def test_every_combination_keeps_80_percent_out(self):
        clean = "补一句因果，说明票价降低如何让人改坐公交。"
        cases = {
            "suggestion only": ("没有说明理由。", FIGURE, True),
            "comment fills an empty suggestion": (FIGURE, "", True),
            "comment with figure, clean suggestion": (FIGURE, clean, False),
        }
        for name, (comment, suggestion, removed) in cases.items():
            with self.subTest(case=name):
                result = evaluate(weak_with(comment, suggestion))
                moved = self.moved(result)
                self.assertIs(moved["suggestion_removed"], removed)
                self.assertNotIn(
                    "80%", json.dumps(result["argument"]["improvements"], ensure_ascii=False)
                )
                self.assertEqual(result["suggestions_removed"]["argument"], 1 if removed else 0)

    def test_clean_comment_and_word_targets_still_fill_the_advice(self):
        result = evaluate(weak_with("可以扩写到260词以上，并说明票价如何影响选择。", ""))
        self.assertEqual(
            self.moved(result)["suggestion"], "可以扩写到260词以上，并说明票价如何影响选择。"
        )
        self.assertEqual(result["suggestions_removed"]["total"], 0)

    def test_final_sweep_catches_a_path_that_skipped_the_filter(self):
        real = review.argument_lib.normalize

        def leaky(raw, essay, sources=None):
            mapped = real(raw, essay, sources)
            mapped["improvements"].append({"quote": QUOTE, "suggestion": FIGURE})
            return mapped

        raw = parse_strict_json(FX["evaluation_attempts"]["t2-weak"][0])
        with (
            mock.patch.object(review.argument_lib, "normalize", side_effect=leaky),
            self.assertLogs("iwa.review", "WARNING") as logs,
        ):
            result = evaluate(raw)
        self.assertIn("final advice sweep", "\n".join(logs.output))
        self.assertNotIn("80%", visible(result))
        self.assertEqual(result["suggestions_removed"]["argument"], 1)


class StubServerMixin:
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), StubHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/v1/chat/completions"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


USAGE = {
    "prompt_tokens": 3000,
    "completion_tokens": 16000,
    "completion_tokens_details": {"reasoning_tokens": 15900},
}


def response(content, finish):
    return 200, {
        "model": "deepseek-flash",
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": USAGE,
    }


class TruncationTest(StubServerMixin, unittest.TestCase):
    def setUp(self):
        StubHandler.responses, StubHandler.requests = [], []
        self.client = ChatClient(
            provider="deepseek", base_url=self.url, api_key="k", model="deepseek-flash", timeout=5
        )

    def test_budget_used_up_while_thinking_is_a_truncation_with_its_usage(self):
        for content in ("", '{"criteria": '):
            with self.subTest(content=content):
                StubHandler.responses = [response(content, "length")]
                with self.assertRaises(LLMError) as caught:
                    self.client.complete([], json_mode=True, max_tokens=16000, thinking="high")
                self.assertEqual(caught.exception.code, "truncated")
                self.assertEqual(caught.exception.usage, USAGE)

    def test_empty_answer_that_finished_normally_is_still_empty(self):
        StubHandler.responses = [response("", "stop")]
        with self.assertRaises(LLMError) as caught:
            self.client.complete([], json_mode=True, max_tokens=50)
        self.assertEqual(caught.exception.code, "empty")


class ScriptedClient(FakeClient):
    """Per evaluation call: 'trunc' raises a truncation carrying usage, 'ok' answers with
    usage, 'silent' answers without reasoning tokens."""

    provider = "deepseek"

    def __init__(self, script):
        super().__init__()
        self.script = list(script)

    def complete(self, messages, **kwargs):
        step = (
            self.script.pop(0) if (kwargs.get("context") or {}).get("kind") == "evaluate" else "ok"
        )
        if step == "trunc":
            raise LLMError("truncated", "模型输出被截断", usage=dict(USAGE), response_received=True)
        result = super().complete(messages, **kwargs)
        result.usage = (
            {"prompt_tokens": 3000, "completion_tokens": 1200} if step == "silent" else dict(USAGE)
        )
        return result


class ReasoningTotalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iwa-reasoning-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_check(self, script, n=1):
        settings = settings_for(self.tmp, evaluate_thinking="high")
        items = realcheck.load_samples("builtin")[:n]
        data = realcheck.run(
            settings, items, client=ScriptedClient(script), kinds=("evaluate",), max_calls=4
        )
        return data, realcheck.build_report(data)

    def test_failed_call_reasoning_counts_in_the_total(self):
        data, report = self.run_check(["trunc", "ok"], n=2)  # sample 1 fails, sample 2 answers
        self.assertEqual([c["error"] for c in data["calls"]], ["truncated", None])
        self.assertEqual([c["reasoning_tokens"] for c in data["calls"]], [15900, 15900])
        evaluate = report["kinds"]["evaluate"]
        self.assertEqual(
            (evaluate["reasoning_tokens"], evaluate["reasoning_tokens_known"]), (31800, 31800)
        )
        self.assertEqual((evaluate["truncated"], evaluate["reasoning_unreported_calls"]), (1, 0))
        self.assertEqual(evaluate["tokens"]["completion_tokens"], 32000)
        # A truncation is not retried as invalid output: the generation fails.
        self.assertEqual(data["samples"][0]["generations"]["evaluate"]["status"], "failed")

    def test_a_call_without_reasoning_tokens_makes_the_total_a_subtotal(self):
        _data, report = self.run_check(["ok", "silent"], n=2)
        evaluate = report["kinds"]["evaluate"]
        self.assertIsNone(evaluate["reasoning_tokens"])
        self.assertEqual(
            (evaluate["reasoning_tokens_known"], evaluate["reasoning_unreported_calls"]), (15900, 1)
        )
        self.assertIn(
            "已知小计 15900（另有 1 次思考调用没有报告，合计不完整）",
            realcheck.render_markdown(report),
        )
        summary = {
            "reasoning_tokens_known": evaluate["reasoning_tokens_known"],
            "reasoning_unreported_calls": evaluate["reasoning_unreported_calls"],
        }
        self.assertEqual(
            realcheck_compare._reasoning_cell(summary), "已知 15900（1 次未报告，不完整）"
        )


def t2_view(**problem):
    return {
        "id": "t2-x",
        "task_type": "task2",
        "overall": 6.0,
        "position_consistent": None,
        "argument_notes": ["AI 一方面判断立场前后一致，另一方面又指出了前后矛盾……"],
        "problems": [
            {
                "type": "conclusion_inconsistent",
                "label": "结尾与立场矛盾",
                "quote": "QUOTE_MARKER",
                "conflicts_with": "PAIRED_CONFLICT_MARKER",
                "needs_review": True,
                "p": 5,
                "comment": "c",
                **problem,
            }
        ],
        "reclassified": [],
        "criteria": {k: {"issues": []} for k in realcheck_compare.CRITERIA},
        "consistency_issues": [],
        "comparisons_checked": None,
        "count_corrections": [],
    }


def t1_view():
    view = t2_view()
    view.update(
        id="t1-x",
        task_type="task1",
        problems=[],
        argument_notes=[],
        consistency_issues=[
            {
                "quote": "CLAIM_MARKER",
                "figures": ["FIGURE_A_MARKER", "FIGURE_C_MARKER"],
                "comment": "COMMENT_MARKER",
            }
        ],
        comparisons_checked=5,
    )
    return view


class ManualReviewTest(unittest.TestCase):
    def sheet(self, view):
        cmp = {
            "conditions": {"a": {"evaluate_thinking": "off"}, "b": {"evaluate_thinking": "high"}},
            "samples": [{"a": view, "b": view}],
        }
        return realcheck_compare.render_manual_review(cmp)

    def test_paired_conflict_review_flag_paragraph_and_notes_are_shown(self):
        sheet = self.sheet(t2_view())
        self.assertIn("结尾与立场矛盾（需人工确认）", sheet)
        self.assertIn("QUOTE_MARKER ↔ 与之矛盾：PAIRED_CONFLICT_MARKER", sheet)
        self.assertIn("论证问题（第 5 段）", sheet)
        self.assertIn("| 立场判断 | — | — | 不下结论 / 未判断 |", sheet)
        self.assertIn("论证提示", sheet)

    def test_task1_contradiction_with_figures_and_comment_is_shown(self):
        sheet = self.sheet(t1_view())
        self.assertIn(
            "| Task 1 文内矛盾 | — | CLAIM_MARKER | 对照：FIGURE_A_MARKER；FIGURE_C_MARKER。COMMENT_MARKER |",
            sheet,
        )
        self.assertIn("核对了 5 条比较说法，指出矛盾 1 条", sheet)
        self.assertNotIn("立场判断", sheet)

    def test_sample_view_keeps_the_evidence_from_a_stored_result(self):
        sample = {
            "id": "t1-no-image",
            "task_type": "task1",
            "generations": {
                "evaluate": {
                    "status": "ready",
                    "result": {
                        "criteria": [],
                        "consistency_issues": [
                            {"quote": "A was highest", "figures": ["75%", "80%"], "comment": "c"}
                        ],
                        "comparisons_checked": 5,
                        "argument": None,
                    },
                }
            },
        }
        view = realcheck_compare.sample_view({"calls": []}, sample)
        self.assertEqual(view["consistency_issues"][0]["figures"], ["75%", "80%"])
        self.assertEqual(view["comparisons_checked"], 5)


def condition(**overrides):
    value = {
        "dir": "x",
        "provider": "deepseek",
        "model": "deepseek-flash",
        "prompt_version": "iwa-2026-11-04.6",
        "kinds": ["evaluate"],
        "evaluate_thinking": "off",
        "evaluate_max_tokens": [4500],
        "samples": {"t1": "same"},
        "evaluate_inputs": {"t1": "sha-a"},
        "started_at": "t",
    }
    value.update(overrides)
    return value


class InputFingerprintTest(unittest.TestCase):
    def test_different_model_input_is_refused_even_with_identical_exports(self):
        errors, _ = realcheck_compare.check_same_conditions(
            condition(), condition(evaluate_thinking="high", evaluate_inputs={"t1": "sha-b"})
        )
        self.assertEqual(errors, ["实际发送给评价模型的输入不同：t1"])

    def test_thinking_budget_and_timeout_are_the_only_allowed_differences(self):
        errors, warnings = realcheck_compare.check_same_conditions(
            condition(), condition(evaluate_thinking="high", evaluate_max_tokens=[16000])
        )
        self.assertEqual((errors, warnings), ([], []))

    def test_missing_input_fingerprint_is_a_warning(self):
        errors, warnings = realcheck_compare.check_same_conditions(
            condition(evaluate_inputs={"t1": None}), condition(evaluate_thinking="high")
        )
        self.assertEqual(errors, [])
        self.assertIn("缺少实际输入的指纹", warnings[0])

    def test_chart_reading_is_part_of_the_exported_input(self):
        base = {"submission": {"task_type": "task1", "essay_text": "e", "image_status": "ready"}}
        a = dict(base, submission=dict(base["submission"], image_description="Museum A = 140"))
        b = dict(base, submission=dict(base["submission"], image_description="Museum A = 141"))
        self.assertNotEqual(realcheck_compare._fingerprint(a), realcheck_compare._fingerprint(b))

    def test_realcheck_records_the_input_of_every_call(self):
        tmp = tempfile.mkdtemp(prefix="iwa-input-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        items = realcheck.load_samples("builtin")[:1]
        runs = [
            realcheck.run(
                settings_for(tmp, evaluate_thinking=mode),
                items,
                client=FakeClient(),
                kinds=("evaluate",),
                max_calls=2,
            )
            for mode in ("off", "high")
        ]
        shas = [run["calls"][0]["input_sha256"] for run in runs]
        self.assertEqual(len(shas[0]), 64)
        self.assertEqual(shas[0], shas[1])  # thinking is an option, not part of the input
        self.assertIn("image_description", runs[0]["samples"][0]["submission"])


if __name__ == "__main__":
    unittest.main()
