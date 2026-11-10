"""Comparison-tool gaps named by review 47ccd24 (2026-11-10,
docs/design/ielts-writing-ai-percentage-review-20261110/model_review.md): one price pair
was applied to both models and cache hits were not priced separately; the run
conditions outside the messages (output budget, timeout, code, the model name the
provider returns) were not shown; the review sheet left out the overall comment and the
priorities. No real model, synthetic essays only."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.ielts_writing_ai import realcheck, realcheck_compare
from tools.ielts_writing_ai.llm import FakeClient

from .helpers import settings_for


class MeteredClient(FakeClient):
    """The demo client with usage as a provider reports it."""

    def __init__(self, model, usage, served=None):
        super().__init__(model=model)
        self.usage, self.served = usage, served or model

    def complete(self, messages, **kwargs):
        result = super().complete(messages, **kwargs)
        result.usage = dict(self.usage)
        result.model = self.served
        return result


DEEPSEEK = {"prompt_tokens": 1000, "completion_tokens": 2000, "prompt_cache_hit_tokens": 800}
OPENAI = {
    "prompt_tokens": 1000,
    "completion_tokens": 2000,
    "prompt_tokens_details": {"cached_tokens": 800},
}
PLAIN = {"prompt_tokens": 1000, "completion_tokens": 2000}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-cmp-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_dir(self, name, model="model-alpha", usage=DEEPSEEK, prices=None, **settings):
        data = realcheck.run(
            settings_for(str(self.tmp / f"data-{name}"), llm_model=model, **settings),
            realcheck.load_samples("builtin")[:1],
            client=MeteredClient(model, usage, served=f"{model}-0601"),
            kinds=("evaluate",),
        )
        report = realcheck.build_report(data, **(prices or {}))
        realcheck.write_report(data, report, self.tmp / name)
        return self.tmp / name, report


class CostTest(Base):
    def test_cache_hits_are_priced_separately(self):
        for usage in (DEEPSEEK, OPENAI):
            with self.subTest(usage=usage):
                _dir, report = self.run_dir(
                    "a",
                    usage=usage,
                    prices={"price_in": 3, "price_cached_in": 0.25, "price_out": 6},
                )
                self.assertEqual(report["usage"]["text"]["cache_hit_tokens"], 800)
                # 200 miss * 3 + 800 hit * 0.25 + 2000 out * 6, per million
                self.assertEqual(report["estimated_cost"], 0.0128)
                self.assertEqual(report["cost_estimate"]["basis"], "cache_split")
                self.assertIn("输入按缓存命中 800 token", realcheck.render_markdown(report))

    def test_without_a_cache_price_or_reported_hits_the_input_is_charged_in_full(self):
        cases = (
            (DEEPSEEK, {"price_in": 3, "price_out": 6}),  # no cache-hit price
            (PLAIN, {"price_in": 3, "price_cached_in": 0.25, "price_out": 6}),  # hits unknown
        )
        for n, (usage, prices) in enumerate(cases):
            with self.subTest(usage=usage):
                _dir, report = self.run_dir(f"r{n}", usage=usage, prices=prices)
                self.assertEqual(report["estimated_cost"], 0.015)
                self.assertEqual(report["cost_estimate"]["basis"], "input_at_full_price")
                self.assertIn("有缓存命中时会偏高", realcheck.render_markdown(report))
        _dir, unknown = self.run_dir("none", usage=PLAIN)
        self.assertIsNone(unknown["estimated_cost"])
        self.assertIsNone(unknown["usage"]["text"]["cache_hit_tokens"])

    def test_each_model_is_priced_with_its_own_prices(self):
        a, _ = self.run_dir("a", "model-alpha", prices={"price_in": 1, "price_out": 2})
        b, _ = self.run_dir("b", "model-beta", prices={"price_in": 3, "price_out": 6})
        # One pair for two models would price both runs alike: refused.
        with self.assertRaises(realcheck_compare.CompareError) as caught:
            realcheck_compare.compare(a, b, price_in=3, price_out=6, allow_model_change=True)
        self.assertIn("--price-in-a", str(caught.exception))
        # Without options each run keeps the prices its own realcheck was given.
        cmp = realcheck_compare.compare(a, b, allow_model_change=True)
        self.assertEqual(cmp["summary"]["a"]["estimated_cost"], 0.005)
        self.assertEqual(cmp["summary"]["b"]["estimated_cost"], 0.015)
        # Per-run options override them, with the cache split.
        cmp = realcheck_compare.compare(
            a,
            b,
            prices_a={"in": 1, "cached_in": 0.1, "out": 2},
            prices_b={"in": 3, "cached_in": 0.25, "out": 6},
            allow_model_change=True,
        )
        self.assertEqual(cmp["summary"]["a"]["estimated_cost"], 0.00428)
        self.assertEqual(cmp["summary"]["b"]["estimated_cost"], 0.0128)
        markdown = realcheck_compare.render_markdown(cmp)
        self.assertIn("A：输入 1（缓存命中 0.1）、输出 2", markdown)
        self.assertIn("B：输入 3（缓存命中 0.25）、输出 6", markdown)
        self.assertIn("思考 token 已含在输出 token 里，不另加", markdown)

    def test_one_pair_still_serves_two_runs_of_the_same_model(self):
        a, _ = self.run_dir("a", evaluate_thinking="off")
        b, _ = self.run_dir("b", evaluate_thinking="high")
        cmp = realcheck_compare.compare(a, b, price_in=3, price_out=6)
        self.assertEqual(cmp["summary"]["a"]["estimated_cost"], 0.015)
        self.assertEqual(cmp["summary"]["b"]["estimated_cost"], 0.015)
        none = realcheck_compare.compare(a, b)
        self.assertIsNone(none["summary"]["a"]["estimated_cost"])
        self.assertIn("A：没有单价或用量不完整，费用未知", realcheck_compare.render_markdown(none))


class ConditionsTest(Base):
    def test_the_report_records_the_served_model_and_the_code(self):
        _dir, report = self.run_dir("a")
        self.assertEqual(report["served_models"], ["model-alpha-0601"])
        self.assertEqual(report["code_sha256"], realcheck.code_fingerprint())
        self.assertRegex(report["code_sha256"], r"^[0-9a-f]{64}$")
        markdown = realcheck.render_markdown(report)
        self.assertIn("服务商返回的模型名：model-alpha-0601", markdown)
        self.assertIn(report["code_sha256"][:16], markdown)

    def test_conditions_outside_the_messages_are_listed_and_differences_named(self):
        a, _ = self.run_dir("a", "model-alpha", evaluate_thinking="high")
        b, _ = self.run_dir(
            "b",
            "model-beta",
            evaluate_thinking="high",
            evaluate_thinking_max_tokens=16000,
            evaluate_thinking_timeout=120,
        )
        cmp = realcheck_compare.compare(a, b, allow_model_change=True)
        joined = "\n".join(cmp["warnings"])
        self.assertIn("两个模型的输出上限不同（32000 vs 16000）", joined)
        self.assertIn("两个模型的超时不同（300 vs 120）", joined)
        self.assertNotIn("源码", joined)  # same code
        markdown = realcheck_compare.render_markdown(cmp)
        self.assertIn("## 运行条件", markdown)
        self.assertIn("| 服务商返回的模型名 | model-alpha-0601 | model-beta-0601 |", markdown)
        self.assertIn("| 评价输出上限 | 32000 | 16000 |", markdown)
        self.assertIn("| 评价超时（秒） | 300 | 120 |", markdown)

    def test_runs_made_by_different_code_are_named(self):
        a, _ = self.run_dir("a", evaluate_thinking="off")
        b, _ = self.run_dir("b", evaluate_thinking="high")
        self.assertFalse(any("源码" in w for w in realcheck_compare.compare(a, b)["warnings"]))
        path = b / "report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["code_sha256"] = "0" * 64
        path.write_text(json.dumps(report), encoding="utf-8")
        self.assertTrue(
            any("工具源码不同" in w for w in realcheck_compare.compare(a, b)["warnings"])
        )
        # A report written before the fingerprint existed is not called different.
        report.pop("code_sha256")
        path.write_text(json.dumps(report), encoding="utf-8")
        self.assertFalse(any("源码" in w for w in realcheck_compare.compare(a, b)["warnings"]))


class BlindSheetTest(Base):
    def test_the_sheet_carries_every_part_of_the_feedback_and_no_model_name(self):
        a, _ = self.run_dir("a", "model-alpha", prices={"price_in": 1, "price_out": 2})
        b, _ = self.run_dir("b", "model-beta", prices={"price_in": 3, "price_out": 6})
        cmp = realcheck_compare.compare(a, b, allow_model_change=True)
        sheet, _key = realcheck_compare.render_blind_review(cmp, seed=3)
        result = json.loads((a / "run_data.json").read_text(encoding="utf-8"))["samples"][0][
            "generations"
        ]["evaluate"]["result"]
        self.assertTrue(result["overall_comment"] and result["priorities"])
        self.assertEqual(sheet.count("| 总评 |"), 2)
        self.assertIn(result["overall_comment"].replace("\n", " "), sheet)
        for n, text in enumerate(result["priorities"], 1):
            self.assertIn(f"| 提升重点 {n} | — | — | {text.replace('|', '／')}", sheet)
        for improvement in (result.get("argument") or {}).get("improvements") or []:
            self.assertIn(improvement["suggestion"], sheet)
        for hidden in ("model-alpha", "model-beta", "0601", "32000", "单价"):
            self.assertNotIn(hidden, sheet)


if __name__ == "__main__":
    unittest.main()
