"""Execution review of 2026-11-11 (docs/design/iwa-holdout-execution-review-20261111):
requests were only counted in memory, so an interrupted run was counted as 0 on
restart (189 / 184) and two launchers shared the same room (212 / 184); a failed
chart reading was retried and the two models saw different chart input; a group in
which every evaluation failed carried on. Synthetic data and the demo client only."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import batch, ledger, prompts, realcheck, samples
from tools.ielts_writing_ai.llm import FakeClient

from .helpers import PNG_BYTES, settings_for

REPO = Path(__file__).resolve().parents[3]
T1 = next(s for s in samples.SAMPLES if s["task_type"] == "task1")
T2 = next(s for s in samples.SAMPLES if s["id"] == "t2-mid")


def new_ledger(path, text_cap=10, vision_cap=0, run="r"):
    return ledger.Ledger(
        path,
        text_cap=text_cap,
        vision_cap=vision_cap,
        run=run,
        code_sha256=realcheck.code_fingerprint(),
        prompt_version=prompts.PROMPT_VERSION,
    )


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-batch-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def jsonl(self, name, rows):
        path = self.tmp / name
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        return path

    def item(self, base, **extra):
        return {
            "task_type": base["task_type"],
            "prompt": base["prompt"],
            "essay": base["essay"],
        } | extra

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--env-file", str(self.tmp / "none.env"), *argv])
        return code, out.getvalue(), err.getvalue()


class LedgerTest(Base):
    def test_a_reservation_without_a_result_still_counts(self):
        path = self.tmp / "l.jsonl"
        book = new_ledger(path, text_cap=3)
        for _ in range(3):
            book.reserve(sample="s", kind="evaluate", model="m", attempt=0)  # never completed
        with self.assertRaises(ledger.LedgerError) as caught:
            new_ledger(path, text_cap=3).reserve(sample="s", kind="evaluate", model="m", attempt=0)
        self.assertEqual(caught.exception.code, "ledger_cap")
        used = ledger.summarize(ledger.read(path))
        self.assertEqual((used["text"]["reserved"], used["text"]["unknown"]), (3, 3))
        # A torn final line (killed while writing) is ignored; nothing else is.
        with path.open("a") as f:
            f.write('{"type": "reserve", "id"')
        self.assertEqual(ledger.summarize(ledger.read(path))["text"]["reserved"], 3)

    def test_text_and_image_caps_are_separate(self):
        book = new_ledger(self.tmp / "l.jsonl", text_cap=5, vision_cap=1)
        book.reserve(sample="s", kind="describe_image", model="v", attempt=0)
        with self.assertRaises(ledger.LedgerError):
            book.reserve(sample="s", kind="describe_image", model="v", attempt=0)
        book.reserve(sample="s", kind="evaluate", model="m", attempt=0)

    def test_another_code_version_is_refused(self):
        path = self.tmp / "l.jsonl"
        new_ledger(path).check()
        other = ledger.Ledger(
            path, text_cap=5, vision_cap=0, run="r", code_sha256="0" * 64, prompt_version="x"
        )
        with self.assertRaises(ledger.LedgerError) as caught:
            other.reserve(sample="s", kind="evaluate", model="m", attempt=0)
        self.assertEqual(caught.exception.code, "ledger_code")

    def test_two_processes_never_exceed_the_cap(self):
        path = self.tmp / "l.jsonl"
        new_ledger(path).check()
        script = (
            "import sys\n"
            "from tools.ielts_writing_ai import ledger, prompts, realcheck\n"
            "book = ledger.Ledger(sys.argv[1], text_cap=30, vision_cap=0, run=sys.argv[2],\n"
            "    code_sha256=realcheck.code_fingerprint(), prompt_version=prompts.PROMPT_VERSION)\n"
            "ok = 0\n"
            "for _ in range(20):\n"
            "    try:\n"
            "        book.reserve(sample='s', kind='evaluate', model='m', attempt=0); ok += 1\n"
            "    except ledger.LedgerError:\n"
            "        pass\n"
            "print(ok)\n"
        )
        procs = [
            subprocess.Popen(
                [sys.executable, "-c", script, str(path), name],
                cwd=REPO,
                stdout=subprocess.PIPE,
                text=True,
            )
            for name in ("one", "two")
        ]
        sent = sum(int(p.communicate()[0]) for p in procs)
        self.assertEqual(sent, 30)  # 40 attempted, never more than the cap
        self.assertEqual(ledger.summarize(ledger.read(path))["text"]["reserved"], 30)

    def test_a_killed_run_leaves_its_requests_in_the_ledger(self):
        path = self.tmp / "l.jsonl"
        script = (
            "import os, sys\n"
            "from tools.ielts_writing_ai import ledger, prompts, realcheck\n"
            "from tools.ielts_writing_ai.llm import FakeClient\n"
            "class Dying(FakeClient):\n"
            "    n = 0\n"
            "    def complete(self, messages, **kw):\n"
            "        Dying.n += 1\n"
            "        if Dying.n == 4: os._exit(137)  # killed while the request is out\n"
            "        return super().complete(messages, **kw)\n"
            "book = ledger.Ledger(sys.argv[1], text_cap=20, vision_cap=0, run='dev-flash',\n"
            "    code_sha256=realcheck.code_fingerprint(), prompt_version=prompts.PROMPT_VERSION)\n"
            "rec = realcheck.Recorder(20, book)\n"
            "client = realcheck.RecordingClient(Dying(), rec)\n"
            "for n in range(6):\n"
            "    client.complete([{'role': 'user', 'content': 'x'}], json_mode=True, max_tokens=10,\n"
            "                    context={'kind': 'evaluate', 'word_count': 300})\n"
        )
        code = subprocess.run([sys.executable, "-c", script, str(path)], cwd=REPO).returncode
        self.assertEqual(code, 137)
        used = ledger.summarize(ledger.read(path))
        self.assertEqual(used["text"]["reserved"], 4)  # 3 answered + 1 sent, outcome unknown
        self.assertEqual(used["text"]["unknown"], 1)
        self.assertEqual(used["runs"]["dev-flash"]["text"], 4)


class RealcheckLedgerTest(Base):
    def test_the_run_stops_at_the_ledger_cap(self):
        items = [self.item(T2, id=f"s{n}") for n in range(3)]
        book = new_ledger(self.tmp / "l.jsonl", text_cap=2)
        data = realcheck.run(
            settings_for(str(self.tmp / "d")),
            items,
            client=FakeClient(),
            kinds=("evaluate",),
            ledger=book,
        )
        self.assertEqual(data["aborted"]["code"], "ledger_cap")
        self.assertEqual(len(data["calls"]), 2)
        used = ledger.summarize(ledger.read(self.tmp / "l.jsonl"))
        self.assertEqual((used["text"]["reserved"], used["text"]["ok"]), (2, 2))

    def test_a_failed_reading_is_frozen_for_the_repeats(self):
        image = self.tmp / "chart.png"
        image.write_bytes(PNG_BYTES)
        items = realcheck.expand_repeats(
            [self.item(T1, id="a", image=str(image)), self.item(T1, id="b", image=str(image))], 2
        )
        vision = FakeClient(model="vision-double", fail_kinds={"describe_image"})
        data = realcheck.run(
            settings_for(str(self.tmp / "d")),
            items,
            client=FakeClient(),
            vision_client=vision,
            kinds=("evaluate",),
        )
        self.assertEqual(vision.calls, ["describe_image", "describe_image"])  # not 4
        self.assertEqual({s["image_status"] for s in data["samples"]}, {"failed"})
        self.assertEqual([s["image_reused"] for s in data["samples"]], [False, True, False, True])
        out = self.tmp / "report"
        realcheck.write_report(data, realcheck.build_report(data), out)
        saved = json.loads((out / "image_descriptions.json").read_text())
        self.assertEqual(saved["images"]["a"]["status"], "failed")
        # The other model gets the same failure (no vision call) - or, when every chart
        # must be usable, nothing runs.
        later = realcheck.expand_repeats([self.item(T1, id="a", image=str(image))], 2)
        realcheck.apply_image_descriptions(later, out / "image_descriptions.json")
        self.assertEqual({i["image_frozen"]["status"] for i in later}, {"failed"})
        with self.assertRaises(realcheck.RealCheckError):
            realcheck.apply_image_descriptions(
                realcheck.expand_repeats([self.item(T1, id="a", image=str(image))], 2),
                out / "image_descriptions.json",
                require_ready=True,
            )

    def test_cli_failure_rate_and_images_only_exit_codes(self):
        image = self.tmp / "chart.png"
        image.write_bytes(PNG_BYTES)
        essays = self.jsonl("e.jsonl", [self.item(T2, id="x"), self.item(T2, id="y")])
        charts = self.jsonl("c.jsonl", [self.item(T1, id="t", image=str(image))])
        failing = FakeClient(fail_kinds={"evaluate"})
        with mock.patch.object(
            realcheck,
            "build_client",
            side_effect=lambda s, vision=False: None if vision else failing,
        ):
            code, _out, err = self.cli(
                "realcheck",
                "--samples",
                str(essays),
                "--kinds",
                "evaluate",
                "--max-failure-rate",
                "0.5",
                "--out",
                str(self.tmp / "r1"),
            )
        self.assertEqual(code, 4)
        self.assertIn("最终失败 2 / 2 篇", err)

        def clients(settings, vision=False):
            return FakeClient(fail_kinds={"describe_image"}) if vision else FakeClient()

        with mock.patch.object(realcheck, "build_client", side_effect=clients):
            code, _out, err = self.cli(
                "realcheck",
                "--samples",
                str(charts),
                "--images-only",
                "--with-vision",
                "--out",
                str(self.tmp / "r2"),
                "--ledger",
                str(self.tmp / "l.jsonl"),
                "--ledger-text-cap",
                "0",
                "--ledger-vision-cap",
                "1",
            )
        self.assertEqual(code, 5)
        used = ledger.summarize(ledger.read(self.tmp / "l.jsonl"))
        self.assertEqual((used["vision"]["reserved"], used["text"]["reserved"]), (1, 0))


class BatchTest(Base):
    def setUp(self):
        super().setUp()
        self.data = self.tmp / "cal"
        self.data.mkdir()
        image = self.data / "chart.png"
        image.write_bytes(PNG_BYTES)
        rows = [self.item(T2, id="e1"), self.item(T2, id="e2")]
        for name in ("teacher", "holdout_rated_t2", "holdout_ordering", "holdout_lowband"):
            (self.data / f"{name}.jsonl").write_text(
                "".join(json.dumps(r | {"id": f"{name}-{r['id']}"}) + "\n" for r in rows)
            )
        (self.data / "holdout_rated_t1.jsonl").write_text(
            json.dumps(self.item(T1, id="t1", image="chart.png")) + "\n"
        )
        self.out = self.tmp / "out"

    def batch(self, *extra):
        return self.cli(
            "realcheck-batch", "--dry", "--data", str(self.data), "--out", str(self.out), *extra
        )

    def test_dry_batch_runs_both_stages_and_resumes_without_new_requests(self):
        code, out, err = self.batch("--stage", "main")
        self.assertEqual(code, 0, err)
        self.assertIn("official.jsonl 不存在，这一组跳过", out)
        used = ledger.summarize(ledger.read(self.out / "ledger-main.jsonl"))
        # dev 7 × 2 + four groups of 2 essays (ordering once, the others twice), both models
        self.assertEqual(used["text"]["reserved"], 2 * (14 + 4 + 4 + 2 + 4))
        code, out, _err = self.batch("--stage", "main")
        self.assertEqual(code, 0)
        self.assertEqual(
            ledger.summarize(ledger.read(self.out / "ledger-main.jsonl"))["text"]["reserved"], 56
        )
        code, out, err = self.batch("--stage", "vision")
        self.assertEqual(code, 0, err)
        used = ledger.summarize(ledger.read(self.out / "ledger-vision.jsonl"))
        self.assertEqual((used["vision"]["reserved"], used["text"]["reserved"]), (1, 4))
        summary = (self.out / "summary.md").read_text()
        self.assertIn("识图请求（两边共用一份结果）：1", summary)
        for word in ("museum", "Museum", T2["essay"].split()[3]):
            self.assertNotIn(word, (self.out / "summary.json").read_text())

    def test_an_interrupted_run_is_counted_and_kept(self):
        # Five requests were sent by a run that never finished, then the batch restarts.
        # The stage's worst case is 112; the five unknown requests count on top of it.
        book = new_ledger(self.out / "ledger-main.jsonl", text_cap=112, run="dev-flash")
        for _ in range(5):
            book.reserve(sample="s", kind="evaluate", model="fake-flash", attempt=0)
        (self.out / "dev-flash").mkdir(parents=True)
        code, _out, err = self.batch("--stage", "main", "--cap", "112")
        self.assertEqual(code, 2)
        self.assertIn("已用 + 剩余最坏 = 117，超过授权上限 112", err)
        code, _out, err = self.batch("--stage", "main", "--cap", "117")
        self.assertEqual(code, 0, err)
        self.assertTrue(any(p.name.startswith("dev-flash.incomplete-") for p in self.out.iterdir()))
        data = json.loads((self.out / "summary.json").read_text())
        attempts = data["groups"]["dev"]["runs"]["flash"]["attempts"]
        self.assertEqual((attempts["requests"], attempts["unknown"]), (19, 5))
        self.assertTrue(attempts["cost_is_lower_bound"] or attempts["estimated_cost"] is None)

    def test_a_second_batch_on_the_same_folder_is_refused(self):
        import fcntl

        self.out.mkdir()
        fd = os.open(self.out / ".batch.lock", os.O_RDWR | os.O_CREAT)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            code, _out, err = self.batch("--stage", "main")
        finally:
            os.close(fd)
        self.assertEqual(code, 2)
        self.assertIn("另一个批次正在使用", err)
        self.assertFalse((self.out / "ledger-main.jsonl").exists())

    def test_a_failing_run_stops_the_batch_without_marking_it_done(self):
        real_run = subprocess.run

        def child(command, **kw):
            if "dev-flash" in command[command.index("--out") + 1]:
                return subprocess.CompletedProcess(command, 4)
            return real_run(command, **kw)

        with mock.patch.object(batch.subprocess, "run", side_effect=child):
            code, _out, err = self.batch("--stage", "main")
        self.assertEqual(code, 4)
        self.assertIn("最终失败超过计划篇数的一半", err)
        self.assertFalse((self.out / "dev-flash" / ".done").exists())
        self.assertFalse((self.out / "dev-pro").exists())

    def test_paid_mode_needs_explicit_config_cap_and_prices(self):
        code, _o, err = self.cli(
            "realcheck-batch", "--stage", "main", "--data", str(self.data), "--out", str(self.out)
        )
        self.assertEqual(code, 2)
        self.assertIn("单价", err)
        prices = ["--price", "flash=1,0.1,2", "--price", "pro=3,0.3,6"]
        code, _o, err = self.cli(
            "realcheck-batch",
            "--stage",
            "main",
            "--data",
            str(self.data),
            "--out",
            str(self.out),
            *prices,
        )
        self.assertEqual(code, 2)
        self.assertIn("配置文件不存在", err)
        env_file = self.tmp / "trial.env"
        env_file.write_text(
            "IWA_LLM_PROVIDER=deepseek\nIWA_LLM_BASE_URL=https://example.invalid/v1\n"
        )
        args = ["--env-file", str(env_file), "realcheck-batch", "--stage", "main"]
        args += ["--data", str(self.data), "--out", str(self.out), *prices]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err_buf:
            code = cli.main(args)
        self.assertEqual(code, 2)
        # The endpoint in the file is overridden by the official one; the key is missing.
        self.assertIn("IWA_LLM_API_KEY", err_buf.getvalue())
        self.assertFalse((self.out / "ledger-main.jsonl").exists())


class SummaryExportTest(unittest.TestCase):
    def test_only_numeric_score_fields_leave_the_machine(self):
        self.assertEqual(
            batch._scores_only({"overall": 6.5, "comment": "secret marker", "task": "7"}),
            {"overall": 6.5, "task": None},
        )


if __name__ == "__main__":
    unittest.main()
