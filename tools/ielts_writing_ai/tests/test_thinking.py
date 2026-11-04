"""Evaluation thinking mode (IWA_EVALUATE_THINKING) and the same-condition comparison
tool. Thinking is for the original-essay evaluation only; refine and rewrite keep the
tested behaviour. No network: the real client talks to a local stub server."""

import io
import json
import shutil
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import HTTPServer
from pathlib import Path

from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import copytext, realcheck, realcheck_compare
from tools.ielts_writing_ai.config import ConfigError, load_settings
from tools.ielts_writing_ai.llm import ChatClient, FakeClient, LLMError, reasoning_tokens

from .helpers import AppTestCase, settings_for
from .test_llm import StubHandler, ok


class SettingsTest(unittest.TestCase):
    def settings(self, **env):
        return load_settings(env={f"IWA_{k}": v for k, v in env.items()}, env_file="/nonexistent")

    def test_default_is_off_with_its_own_provisional_budget(self):
        s = self.settings()
        self.assertEqual(s.evaluate_thinking, "off")
        self.assertEqual(
            (s.evaluate_thinking_max_tokens, s.evaluate_thinking_timeout), (16000, 300.0)
        )
        s = self.settings(EVALUATE_THINKING="HIGH", EVALUATE_THINKING_MAX_TOKENS="20000")
        self.assertEqual((s.evaluate_thinking, s.evaluate_thinking_max_tokens), ("high", 20000))
        summary = s.public_summary()
        self.assertEqual(summary["evaluate_thinking"], "high")
        self.assertNotIn("llm_api_key", summary)

    def test_unknown_mode_or_provider_is_rejected(self):
        with self.assertRaisesRegex(ConfigError, "IWA_EVALUATE_THINKING"):
            self.settings(EVALUATE_THINKING="medium").validate()
        qwen = self.settings(
            EVALUATE_THINKING="high", LLM_PROVIDER="qwen", LLM_API_KEY="k", LLM_MODEL="m"
        )
        with self.assertRaisesRegex(ConfigError, "只支持 DeepSeek"):
            qwen.validate()
        self.settings(EVALUATE_THINKING="high", LLM_PROVIDER="deepseek", LLM_API_KEY="k").validate()


class ClientTest(unittest.TestCase):
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

    def setUp(self):
        StubHandler.responses = []
        StubHandler.requests = []
        self.client = ChatClient(
            provider="deepseek", base_url=self.url, api_key="secret", model="m", timeout=5
        )

    def test_off_keeps_the_tested_request(self):
        StubHandler.responses = [ok('{"a": 1}')]
        self.client.complete([], json_mode=True, max_tokens=50)
        body = StubHandler.requests[0]["body"]
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertNotIn("reasoning_effort", body)

    def test_high_enables_thinking_and_reads_reasoning_separately(self):
        status, payload = ok('{"a": 1}')
        payload["choices"][0]["message"]["reasoning_content"] = "先看整段……"
        payload["usage"] = {
            "prompt_tokens": 10,
            "completion_tokens": 900,
            "completion_tokens_details": {"reasoning_tokens": 700},
        }
        StubHandler.responses = [(status, payload)]
        result = self.client.complete(
            [], json_mode=True, max_tokens=16000, thinking="high", timeout=30
        )
        body = StubHandler.requests[0]["body"]
        self.assertEqual(body["thinking"], {"type": "enabled"})
        self.assertEqual(body["reasoning_effort"], "high")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["max_tokens"], 16000)
        self.assertEqual(result.json(), {"a": 1})  # only the content is parsed
        self.assertEqual(result.reasoning, "先看整段……")
        self.assertEqual(reasoning_tokens(result.usage), 700)

    def test_reasoning_tokens_unknown_is_not_zero(self):
        self.assertIsNone(reasoning_tokens({"completion_tokens": 5}))
        self.assertIsNone(reasoning_tokens(None))
        self.assertIsNone(
            reasoning_tokens({"completion_tokens_details": {"reasoning_tokens": True}})
        )

    def test_truncated_thinking_answer_is_reported_as_truncated(self):
        StubHandler.responses = [ok('{"a":', finish="length")]
        with self.assertRaises(LLMError) as caught:
            self.client.complete([], json_mode=True, max_tokens=10, thinking="high")
        self.assertEqual(caught.exception.code, "truncated")

    def test_other_providers_refuse_thinking(self):
        self.client.provider = "qwen"
        with self.assertRaises(LLMError) as caught:
            self.client.complete([], json_mode=True, max_tokens=10, thinking="high")
        self.assertEqual(caught.exception.code, "unsupported")
        self.assertEqual(StubHandler.requests, [])


class KwargsClient(FakeClient):
    """Records the options each generation kind was called with."""

    def __init__(self):
        super().__init__()
        self.options = []

    def complete(self, messages, **kwargs):
        context = kwargs.get("context") or {}
        self.options.append(
            {
                "kind": context.get("kind"),
                "thinking": kwargs.get("thinking", "off"),
                "max_tokens": kwargs.get("max_tokens"),
                "timeout": kwargs.get("timeout"),
            }
        )
        return super().complete(messages, **kwargs)


class GeneratorTest(AppTestCase):
    settings_overrides = {"evaluate_thinking": "high", "evaluate_thinking_max_tokens": 12345}

    def setUp(self):
        super().setUp()
        self.client_llm = KwargsClient()
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage

    def test_only_the_evaluation_thinks_with_its_own_budget(self):
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        options = {o["kind"]: o for o in self.client_llm.options}
        self.assertEqual(
            options["evaluate"],
            {"kind": "evaluate", "thinking": "high", "max_tokens": 12345, "timeout": 300.0},
        )
        for kind in ("refine", "rewrite"):
            self.assertEqual(options[kind]["thinking"], "off")
            self.assertIsNone(options[kind]["timeout"])
            self.assertNotEqual(options[kind]["max_tokens"], 12345)
        sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        evaluation = sub["generations"]["evaluate"]
        self.assertEqual(evaluation["result"]["thinking"], "high")
        self.assertIn("思考模式 high", evaluation["copy"]["evaluation"])
        self.assertNotIn("thinking", sub["generations"]["refine"]["result"])


class OffGeneratorTest(AppTestCase):
    def test_off_sends_no_thinking_options(self):
        self.client_llm = KwargsClient()
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        self.assertTrue(all(o["thinking"] == "off" for o in self.client_llm.options))
        self.assertTrue(all(o["timeout"] is None for o in self.client_llm.options))
        sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        self.assertEqual(sub["generations"]["evaluate"]["result"]["thinking"], "off")
        text = copytext.evaluation_text({"criteria": [], "thinking": "off"}, {"model": "m"})
        self.assertNotIn("思考模式", text)


class ThinkingUsageClient(FakeClient):
    provider = "deepseek"

    def complete(self, messages, **kwargs):
        result = super().complete(messages, **kwargs)
        if kwargs.get("thinking", "off") != "off":
            result.reasoning = "思考过程"
            result.usage = {
                "prompt_tokens": 100,
                "completion_tokens": 3000,
                "completion_tokens_details": {"reasoning_tokens": 2000},
            }
        else:
            result.usage = {"prompt_tokens": 100, "completion_tokens": 1000}
        return result


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-thinking-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_check(self, name, thinking, items=None):
        settings = settings_for(str(self.tmp / f"data-{name}"), evaluate_thinking=thinking)
        items = items or realcheck.load_samples("builtin")[:3]
        data = realcheck.run(
            settings, items, client=ThinkingUsageClient(), kinds=("evaluate",), max_calls=6
        )
        report = realcheck.build_report(data)
        realcheck.write_report(data, report, self.tmp / name)
        return data, report

    def test_report_records_thinking_budget_and_reasoning(self):
        data, report = self.run_check("high", "high")
        call = data["calls"][0]
        self.assertEqual((call["thinking"], call["max_tokens"]), ("high", 16000))
        self.assertEqual((call["reasoning_tokens"], call["reasoning"]), (2000, "思考过程"))
        evaluate = report["kinds"]["evaluate"]
        self.assertEqual(evaluate["thinking"], ["high"])
        self.assertEqual(evaluate["max_tokens"], [16000])
        self.assertEqual(
            (evaluate["completion_tokens_max"], evaluate["reasoning_tokens"]), (3000, 6000)
        )
        markdown = (self.tmp / "high" / "report.md").read_text(encoding="utf-8")
        self.assertIn("评价思考模式 high", markdown)
        self.assertIn("思考 token 合计 6000，单次最多 2000", markdown)
        self.assertTrue((self.tmp / "high" / "run_data.json").is_file())
        _data, off = self.run_check("off", "off")
        self.assertIsNone(off["kinds"]["evaluate"]["reasoning_tokens"])
        self.assertIn(
            "思考 token 未报告", (self.tmp / "off" / "report.md").read_text(encoding="utf-8")
        )

    def test_same_conditions_compare_side_by_side_with_a_review_sheet(self):
        self.run_check("off", "off")
        self.run_check("high", "high")
        cmp = realcheck_compare.compare(
            self.tmp / "off", self.tmp / "high", price_in=1, price_out=2
        )
        self.assertEqual(cmp["warnings"], [])
        a, b = cmp["summary"]["a"], cmp["summary"]["b"]
        self.assertEqual((a["completion_tokens"], b["completion_tokens"]), (3000, 9000))
        self.assertEqual((a["reasoning_tokens"], b["reasoning_tokens"]), (None, 6000))
        self.assertEqual(b["estimated_cost"], round(300 / 1e6 * 1 + 9000 / 1e6 * 2, 6))
        path = realcheck_compare.write(cmp, self.tmp / "cmp")
        markdown = path.read_text(encoding="utf-8")
        self.assertIn("| 其中思考 token（评价；— 为未报告） | — | 6000 |", markdown)
        self.assertIn("判断是否更准，看下面的人工复核表", markdown)
        sheet = (self.tmp / "cmp" / "manual_review.md").read_text(encoding="utf-8")
        self.assertIn("同段引文存在，不等于它真的构成有效支撑", sheet)
        self.assertEqual(sheet.count("| 两次都漏报 |"), 3)
        self.assertIn("| A 思考 off | 论证问题 |", sheet)
        self.assertIn("| B 思考 high | 论证问题 |", sheet)

    def test_different_conditions_are_refused(self):
        self.run_check("off", "off")
        self.run_check("high", "high")
        report_path = self.tmp / "high" / "report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["prompt_version"] = "iwa-other"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(realcheck_compare.CompareError, "提示词版本不同"):
            realcheck_compare.compare(self.tmp / "off", self.tmp / "high")

    def test_changed_essay_is_refused_and_same_mode_is_a_warning(self):
        self.run_check("off", "off")
        items = realcheck.load_samples("builtin")[:3]
        items[1] = dict(items[1], essay=items[1]["essay"] + " Extra sentence.")
        self.run_check("off2", "off", items)
        with self.assertRaisesRegex(realcheck_compare.CompareError, "题目或作文不同：t2-mid"):
            realcheck_compare.compare(self.tmp / "off", self.tmp / "off2")
        self.run_check("off3", "off")
        cmp = realcheck_compare.compare(self.tmp / "off", self.tmp / "off3")
        self.assertTrue(any("重复性对照" in w for w in cmp["warnings"]))

    def test_cli(self):
        self.run_check("off", "off")
        self.run_check("high", "high")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["realcheck-compare", str(self.tmp / "off"), str(self.tmp / "high")])
        self.assertEqual(code, 0, err.getvalue())
        self.assertTrue((self.tmp / "high" / "compare" / "compare.md").is_file())
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = cli.main(["realcheck-compare", str(self.tmp / "off"), str(self.tmp / "missing")])
        self.assertEqual(code, 2)
        self.assertIn("不能对照", err.getvalue())


if __name__ == "__main__":
    unittest.main()
