"""The real-model check harness, exercised offline with model doubles (no network)."""

import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import realcheck, samples
from tools.ielts_writing_ai.llm import ChatClient, FakeClient, LLMError

from .helpers import PNG_BYTES, settings_for

SECRET = "sk-test-secret-should-never-appear"


class DisclaimerFirstClient(FakeClient):
    """First attempt of every generation wraps valid JSON in a disclaimer."""

    def complete(self, messages, **kwargs):
        result = super().complete(messages, **kwargs)
        if (kwargs.get("context") or {}).get("attempt") == 0:
            result.text = "以下仅为示例：\n" + result.text
        return result


class AuthFailClient(FakeClient):
    provider = "deepseek"

    def complete(self, messages, **kwargs):
        self.calls.append((kwargs.get("context") or {}).get("kind"))
        raise LLMError("http_401", "模型服务返回 HTTP 401")


class UsageClient(FakeClient):
    def complete(self, messages, **kwargs):
        result = super().complete(messages, **kwargs)
        vision = (kwargs.get("context") or {}).get("kind") == "describe_image"
        result.usage = {
            "prompt_tokens": 1000 if vision else 100,
            "completion_tokens": 100 if vision else 10,
        }
        return result


class RealCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iwa-rc-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.settings = settings_for(self.tmp, llm_api_key=SECRET)

    def run_check(self, items=None, **kwargs):
        items = items if items is not None else realcheck.load_samples("builtin")
        client = kwargs.pop("client", FakeClient())
        data = realcheck.run(self.settings, items, client=client, **kwargs)
        return data, realcheck.build_report(data)

    def test_builtin_demo_run_produces_a_complete_report(self):
        data, report = self.run_check()
        self.assertEqual(report["samples"], len(samples.SAMPLES))
        # The demo rewrite of the 97-word essay stays under 250 words and the off-topic
        # rewrite stays off-topic: each triggers exactly one quality retry.
        self.assertEqual(report["calls"], len(samples.SAMPLES) * 3 + 2)
        retried = {c["sample"] for c in data["calls"] if c["attempt"] == 1}
        self.assertEqual(retried, {"t2-under-length", "t2-off-topic"})
        self.assertTrue(report["connectivity"]["ok"])
        for metrics in report["kinds"].values():
            self.assertEqual(metrics["first_attempt_json_ok"], 1.0)
            self.assertEqual(metrics["final_ready"], 1.0)
        rewrite = report["refine_rewrite"]
        self.assertEqual(rewrite["rewrite_quality_issues"], {"below_min": 1, "off_prompt": 1})
        self.assertAlmostEqual(rewrite["rewrite_quality_passed"], round(5 / 7, 3))
        self.assertIn("质量检查", "".join(report["kinds"]["rewrite"]["first_attempt_rejections"]))
        self.assertEqual(report["evidence"]["quotes_verified"], 1.0)
        checks = {(c["sample"], c["check"]): c["ok"] for c in report["sanity"]["checks"]}
        self.assertTrue(checks[("t1-no-image", "缺图 TA / 总分不可评")])
        self.assertTrue(checks[("t2-under-length", "有字数不足提示")])
        # The demo model scores by length only, so the spread check must catch it.
        self.assertFalse(checks[("分级样本", "最强与最弱相差 ≥ 1.5")])

        out = Path(self.tmp) / "report"
        md = realcheck.write_report(data, report, out)
        self.assertIn("演示模式（fake）", md.read_text(encoding="utf-8"))
        for name in ("report.md", "report.json", "raw_calls.jsonl"):
            self.assertNotIn(SECRET, (out / name).read_text(encoding="utf-8"))
        self.assertEqual(len((out / "raw_calls.jsonl").read_text().splitlines()), report["calls"])

    def test_first_attempt_rejections_are_measured_separately_from_final_success(self):
        _data, report = self.run_check(client=DisclaimerFirstClient())
        for metrics in report["kinds"].values():
            self.assertEqual(metrics["first_attempt_json_ok"], 0.0)
            self.assertEqual(metrics["first_attempt_valid"], 0.0)
            self.assertEqual(metrics["final_ready"], 1.0)
            self.assertIn("JSON 之外有文字或不是 JSON 对象", metrics["first_attempt_rejections"])
        self.assertEqual(report["calls"], len(samples.SAMPLES) * 6)

    def test_auth_failure_on_the_first_call_stops_everything(self):
        client = AuthFailClient()
        _data, report = self.run_check(client=client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(report["calls"], 1)
        self.assertFalse(report["connectivity"]["ok"])
        self.assertEqual(report["connectivity"]["error"], "http_401")
        self.assertEqual(report["aborted"]["code"], "http_401")

    def test_call_budget_is_a_hard_cap(self):
        _data, report = self.run_check(max_calls=4)
        self.assertEqual(report["calls"], 4)
        failures = sum(sum(k["final_failures"].values()) for k in report["kinds"].values())
        self.assertGreater(failures, 0)

    def http_client(self):
        return ChatClient(
            provider="deepseek",
            base_url="https://api.deepseek.com/chat/completions",
            api_key=SECRET,
            model="synthetic-model",
            timeout=1,
        )

    def response(self, *, content="{}", finish="stop", usage=None):
        payload = {
            "model": "synthetic-model",
            "choices": [{"message": {"content": content}, "finish_reason": finish}],
        }
        if usage is not None:
            payload["usage"] = usage
        return io.BytesIO(json.dumps(payload).encode())

    def test_network_failure_is_one_transport_attempt_without_hidden_retry(self):
        client = self.http_client()
        with mock.patch.object(
            client, "_open", side_effect=urllib.error.URLError("injected offline failure")
        ) as transport:
            data, report = self.run_check(client=client, max_calls=2)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(len(data["calls"]), 1)
        self.assertEqual(report["aborted"]["code"], "network")
        self.assertFalse(report["connectivity"]["response_received"])
        self.assertIsNone(report["connectivity"]["authenticated"])
        priced = realcheck.build_report(data, price_in=1, price_out=1)
        self.assertIsNone(priced["estimated_cost"])
        self.assertEqual(priced["tokens"], {"prompt": None, "completion": None})
        self.assertIn("未知（不能视为零费用）", realcheck.render_markdown(priced))

    def test_validation_retry_shares_the_transport_budget(self):
        for budget in (1, 2):
            with self.subTest(budget=budget):
                client = self.http_client()
                with mock.patch.object(
                    client, "_open", side_effect=lambda _request: self.response()
                ) as transport:
                    data, report = self.run_check(
                        items=realcheck.load_samples("builtin", 1),
                        client=client,
                        kinds=("evaluate",),
                        max_calls=budget,
                    )
                self.assertEqual(transport.call_count, budget)
                self.assertEqual(report["calls"], budget)
                self.assertEqual(data["samples"][0]["generations"]["evaluate"]["status"], "failed")

    def test_invalid_budgets_are_rejected_before_dispatch(self):
        for budget in (0, -1, 1.5, True):
            client = FakeClient()
            with (
                self.subTest(budget=budget),
                self.assertRaisesRegex(realcheck.RealCheckError, "正整数"),
            ):
                self.run_check(client=client, max_calls=budget)
            self.assertEqual(client.calls, [])

    def test_truncated_response_preserves_usage_and_is_not_a_connection_failure(self):
        client = self.http_client()
        with mock.patch.object(
            client,
            "_open",
            side_effect=lambda _request: self.response(
                finish="length", usage={"prompt_tokens": 100, "completion_tokens": 2800}
            ),
        ) as transport:
            data, _report = self.run_check(
                items=realcheck.load_samples("builtin", 1), client=client, kinds=("evaluate",)
            )
        self.assertEqual(transport.call_count, 1)
        report = realcheck.build_report(data, price_in=1, price_out=1)
        self.assertTrue(report["connectivity"]["ok"])
        self.assertTrue(report["connectivity"]["authenticated"])
        self.assertFalse(report["connectivity"]["generation_ok"])
        self.assertEqual(report["connectivity"]["generation_error"], "truncated")
        self.assertEqual(report["tokens"], {"prompt": 100, "completion": 2800})
        self.assertEqual(report["estimated_cost"], 0.0029)
        self.assertEqual(report["per_sample"][0]["statuses"]["evaluate"], "failed")

    def test_trial_database_is_never_touched(self):
        trial_db = Path(self.tmp) / "iwa.sqlite3"
        trial_db.write_bytes(b"trial database placeholder")
        before = hashlib.sha256(trial_db.read_bytes()).hexdigest()
        self.run_check(items=realcheck.load_samples("builtin", limit=1))
        self.assertEqual(hashlib.sha256(trial_db.read_bytes()).hexdigest(), before)
        self.assertEqual(sorted(p.name for p in Path(self.tmp).iterdir()), ["iwa.sqlite3"])

    def test_calibration_against_teacher_scores(self):
        jsonl = Path(self.tmp) / "teacher.jsonl"
        rows = [
            {
                "id": "a",
                "task_type": "task2",
                "prompt": samples.TRANSPORT_PROMPT,
                "essay": samples.MID,
                "teacher": {"overall": 6.5, "grammar": 5.5},
            },
            {
                "id": "b",
                "task_type": "task2",
                "prompt": samples.TRANSPORT_PROMPT,
                "essay": samples.GOOD,
                "teacher": {"overall": 7.0, "grammar": 6.5},
            },
        ]
        jsonl.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        _data, report = self.run_check(items=realcheck.load_samples(str(jsonl)))
        # FakeClient gives these essays overall 6.0 and GRA 5.5.
        overall = report["calibration"]["overall"]
        self.assertEqual(overall["n"], 2)
        self.assertEqual(overall["mae"], 0.75)
        self.assertEqual(overall["bias"], -0.75)
        self.assertEqual(overall["within_0_5"], 0.5)
        grammar = report["calibration"]["grammar"]
        self.assertEqual((grammar["mae"], grammar["exact"]), (0.5, 0.5))
        self.assertIn("与老师评分对比", realcheck.render_markdown(report))

    def test_image_samples_only_call_vision_when_asked(self):
        image = Path(self.tmp) / "chart.png"
        image.write_bytes(PNG_BYTES)
        jsonl = Path(self.tmp) / "t1.jsonl"
        jsonl.write_text(
            json.dumps(
                {
                    "id": "img",
                    "task_type": "task1",
                    "prompt": samples.TASK1_PROMPT,
                    "essay": samples.TASK1_NO_IMAGE,
                    "image": "chart.png",
                }
            ),
            encoding="utf-8",
        )
        items = realcheck.load_samples(str(jsonl))
        data, _report = self.run_check(items=items)  # vision_provider none
        self.assertEqual(data["samples"][0]["image_status"], "skipped")
        vision = FakeClient(model="vision-double")
        data, report = self.run_check(items=items, vision_client=vision)
        self.assertEqual(data["samples"][0]["image_status"], "ready")
        self.assertEqual(report["vision_calls"], 1)

    def test_vision_usage_is_included_but_text_price_does_not_price_another_model(self):
        image = Path(self.tmp) / "chart.png"
        image.write_bytes(PNG_BYTES)
        item = dict(samples.SAMPLES[-1], image=str(image))
        data, _report = self.run_check(
            items=[item],
            client=UsageClient(model="text-double"),
            vision_client=UsageClient(model="vision-double"),
            kinds=("evaluate",),
        )
        report = realcheck.build_report(data, price_in=1, price_out=1)
        self.assertEqual(report["tokens"], {"prompt": 1100, "completion": 110})
        self.assertEqual(report["usage"]["text"]["tokens"], {"prompt": 100, "completion": 10})
        self.assertEqual(report["usage"]["vision"]["tokens"], {"prompt": 1000, "completion": 100})
        self.assertEqual(len(report["usage"]["by_model"]), 2)
        self.assertIsNone(report["estimated_cost"])
        self.assertEqual(report["cost_estimate"]["covered_cost"], 0.00011)
        self.assertEqual(report["cost_estimate"]["coverage"], "text_only")
        markdown = realcheck.render_markdown(report)
        self.assertIn("总 token（含识图）：输入 1100 · 输出 110", markdown)
        self.assertIn("识图费用未估算", markdown)

    def test_duplicate_sample_ids_are_rejected_before_sampling_or_running(self):
        rows = [dict(item, id="same-id") for item in samples.SAMPLES[:2]]
        path = Path(self.tmp) / "duplicates.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        with self.assertRaisesRegex(realcheck.RealCheckError, "id 重复"):
            realcheck.load_samples(str(path), limit=1)
        client = FakeClient()
        with self.assertRaisesRegex(realcheck.RealCheckError, "id 重复"):
            self.run_check(items=rows, client=client)
        self.assertEqual(client.calls, [])

    def test_sample_file_errors(self):
        bad = Path(self.tmp) / "bad.jsonl"
        for content, message in (
            ("{not json", "不是合法 JSON"),
            ("[]", "必须是 JSON 对象"),
            (json.dumps({"task_type": "task2", "prompt": "p"}), "缺少 essay"),
            (json.dumps({"task_type": "task3", "prompt": "p", "essay": "e"}), "task_type"),
            (
                json.dumps({"task_type": "task1", "prompt": "p", "essay": "e", "image": "x.png"}),
                "题图不存在",
            ),
        ):
            bad.write_text(content, encoding="utf-8")
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(realcheck.RealCheckError, message),
            ):
                realcheck.load_samples(str(bad))


class RealCheckCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iwa-rc-cli-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        clean = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
        patcher = mock.patch.dict(os.environ, clean, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def cli(self, env_lines, *args):
        env_file = Path(self.tmp) / ".env"
        env_file.write_text("\n".join([f"IWA_DATA_DIR={self.tmp}/data", *env_lines]) + "\n")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--env-file", str(env_file), "realcheck", *args])
        return code, out.getvalue(), err.getvalue()

    def test_paid_model_requires_explicit_confirmation(self):
        with mock.patch("tools.ielts_writing_ai.realcheck.run") as run:
            code, out, err = self.cli(
                ["IWA_LLM_PROVIDER=deepseek", f"IWA_LLM_API_KEY={SECRET}"], "--limit", "1"
            )
        self.assertEqual(code, 2)
        self.assertIn("--confirm-paid", err)
        run.assert_not_called()
        self.assertNotIn(SECRET, out + err)
        self.assertFalse((Path(self.tmp) / "data" / "realcheck").exists())

    def test_demo_run_via_cli_writes_report(self):
        report_dir = Path(self.tmp) / "out"
        code, out, _err = self.cli([], "--limit", "2", "--out", str(report_dir))
        self.assertEqual(code, 0, out)
        self.assertTrue((report_dir / "report.md").is_file())
        self.assertIn("最多 12 次调用", out)

    def test_bad_kinds_are_rejected(self):
        code, _out, err = self.cli([], "--kinds", "evaluate,score")
        self.assertEqual(code, 2)
        self.assertIn("--kinds", err)

    def test_nonpositive_call_budget_is_rejected_by_cli(self):
        for budget in ("0", "-1"):
            with (
                self.subTest(budget=budget),
                mock.patch("tools.ielts_writing_ai.realcheck.run") as run,
            ):
                code, _out, err = self.cli([], "--max-calls", budget)
            self.assertEqual(code, 2)
            self.assertIn("正整数", err)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
