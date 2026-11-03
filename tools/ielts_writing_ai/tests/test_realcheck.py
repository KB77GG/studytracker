"""The real-model check harness, exercised offline with model doubles (no network)."""

import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import realcheck, samples
from tools.ielts_writing_ai.llm import FakeClient, LLMError

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
        self.assertEqual(report["calls"], len(samples.SAMPLES) * 3)
        self.assertTrue(report["connectivity"]["ok"])
        for metrics in report["kinds"].values():
            self.assertEqual(metrics["first_attempt_json_ok"], 1.0)
            self.assertEqual(metrics["final_ready"], 1.0)
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

    def test_sample_file_errors(self):
        bad = Path(self.tmp) / "bad.jsonl"
        for content, message in (
            ("{not json", "不是合法 JSON"),
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


if __name__ == "__main__":
    unittest.main()
