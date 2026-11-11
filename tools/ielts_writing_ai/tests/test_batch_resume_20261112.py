"""Second review of the batch (76276d9, docs/design/iwa-batch-recheck-20261111): a run
outliving a killed batch did not hold the lock (56 requests became 70); a resume did
not check the data (requests spent before the comparison noticed, or old reports
reused); a cut-off blind sheet was reported complete; a reclassified suggestion was
counted twice; a resume overwrote a filled blind sheet; a frozen failed reading lost
its diagnostic text. Synthetic essays and the demo client only."""

from __future__ import annotations

import fcntl
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import batch, blindtally, ledger, realcheck, realcheck_compare, samples
from tools.ielts_writing_ai.llm import FakeClient, LLMResult

from .helpers import PNG_BYTES, settings_for

REPO = Path(__file__).resolve().parents[3]
T1 = next(s for s in samples.SAMPLES if s["task_type"] == "task1")
T2 = [s for s in samples.SAMPLES if s["task_type"] == "task2"][:2]

# Holds the first Pro evaluation until a file disappears, and counts every request.
HOLD = r"""
import fcntl, json, os, time
from tools.ielts_writing_ai import llm
_original = llm.FakeClient.complete
def complete(self, messages, **kw):
    with open(os.environ["PROBE_COUNTER"], "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX); f.write(self.model + "\n"); f.flush(); os.fsync(f.fileno())
    hold = os.environ.get("PROBE_HOLD")
    if hold and self.model == "fake-pro" and os.path.exists(hold):
        open(hold + ".waiting", "w").close()
        while os.path.exists(hold):
            time.sleep(0.05)
    return _original(self, messages, **kw)
llm.FakeClient.complete = complete
"""


def item(base, **extra):
    return {
        "task_type": base["task_type"],
        "prompt": base["prompt"],
        "essay": base["essay"],
    } | extra


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-resume-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "cal"
        self.data.mkdir()
        for name in ("teacher", "holdout_rated_t2", "holdout_ordering", "holdout_lowband"):
            self.write_group(name, [item(s, id=f"{name}-{n}") for n, s in enumerate(T2)])
        (self.data / "chart.png").write_bytes(PNG_BYTES)
        self.write_group("holdout_rated_t1", [item(T1, id="t1", image="chart.png")])
        self.out = self.tmp / "out"

    def write_group(self, name, rows):
        (self.data / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))

    def batch(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(
                ["--env-file", str(self.tmp / "none.env"), "realcheck-batch", "--dry"]
                + ["--data", str(self.data), "--out", str(self.out), *extra]
            )
        return code, out.getvalue(), err.getvalue()

    def reserved(self, stage="main"):
        return ledger.summarize(ledger.read(self.out / f"ledger-{stage}.jsonl"))["text"]["reserved"]


class ParentKilledTest(Base):
    def lock_free(self) -> bool:
        fd = os.open(self.out / ".batch.lock", os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False
        finally:
            os.close(fd)

    def test_a_run_outliving_its_batch_keeps_the_lock_and_is_not_repeated(self):
        site = self.tmp / "site"
        site.mkdir()
        (site / "sitecustomize.py").write_text(HOLD)
        counter, hold = self.tmp / "sent.txt", self.tmp / "hold"
        hold.touch()
        env = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
        env |= {"PYTHONPATH": f"{site}{os.pathsep}{REPO}", "PROBE_COUNTER": str(counter)}
        env["PROBE_HOLD"] = str(hold)
        command = [sys.executable, "-m", "tools.ielts_writing_ai", "realcheck-batch", "--stage"]
        command += ["main", "--dry", "--data", str(self.data), "--out", str(self.out)]
        parent = subprocess.Popen(
            command, cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        deadline = time.monotonic() + 120
        while not Path(str(hold) + ".waiting").exists():
            self.assertLess(time.monotonic(), deadline, "the Pro run never started")
            time.sleep(0.05)
        os.kill(parent.pid, signal.SIGKILL)  # the batch dies; its dev-pro run goes on
        parent.wait()
        sent_before = len(counter.read_text().splitlines())
        try:
            self.assertFalse(self.lock_free())  # held by the surviving child
            code, _out, err = self.batch("--stage", "main")
            self.assertEqual(code, 2)
            self.assertIn("另一个批次正在使用", err)
            self.assertEqual(len(counter.read_text().splitlines()), sent_before)
        finally:
            hold.unlink()  # let the surviving run finish
        while not self.lock_free():
            self.assertLess(time.monotonic(), deadline, "the surviving run never ended")
            time.sleep(0.05)
        code, out, err = self.batch("--stage", "main")
        self.assertEqual(code, 0, err)
        self.assertIn("dev-pro 在上一个批次退出后自行完成，沿用其结果", out)
        self.assertFalse(any(p.name.startswith("dev-pro.incomplete") for p in self.out.iterdir()))
        # The normal plan: dev 7×2 + four groups of 2 essays (ordering once), two models.
        self.assertEqual(self.reserved(), 56)


class DataPinTest(Base):
    def test_changed_data_is_refused_before_anything_is_reused_or_sent(self):
        code, _out, err = self.batch("--stage", "main")
        self.assertEqual(code, 0, err)
        pinned = json.loads((self.out / "batch-main.json").read_text())["inputs"]
        self.assertEqual(set(pinned), {"dev", "teacher", "rated_t2", "ordering", "lowband"})
        before = self.reserved()
        rows = [item(s, id=f"teacher-{n}") for n, s in enumerate(T2)]
        rows[0]["essay"] += " One more sentence."
        self.write_group("teacher", rows)
        code, _out, err = self.batch("--stage", "main")
        self.assertEqual(code, 2)
        self.assertIn("teacher（数据已改动）", err)
        self.assertEqual(self.reserved(), before)
        # Reference data counts as data too (a teacher's score changed).
        rows = [item(s, id=f"teacher-{n}") for n, s in enumerate(T2)]
        self.write_group("teacher", rows)
        self.assertEqual(self.batch("--stage", "main")[0], 0)
        rows[1]["teacher"] = {"overall": 6.5}
        self.write_group("teacher", rows)
        self.assertEqual(self.batch("--stage", "main")[0], 2)

    def test_a_partial_stage_with_changed_data_sends_nothing(self):
        real_run = subprocess.run

        def child(command, **kw):
            if "dev-pro" in command[command.index("--out") + 1]:
                return subprocess.CompletedProcess(command, 4)  # stops after dev-flash
            return real_run(command, **kw)

        with mock.patch.object(batch.subprocess, "run", side_effect=child):
            self.assertEqual(self.batch("--stage", "main")[0], 4)
        before = self.reserved()
        self.write_group("holdout_lowband", [item(T2[0], id="other")])
        with mock.patch.object(batch.subprocess, "run", side_effect=AssertionError("sent")):
            code, _out, err = self.batch("--stage", "main")
        self.assertEqual(code, 2)
        self.assertEqual(self.reserved(), before)

    def test_a_changed_image_or_frozen_reading_is_refused(self):
        self.assertEqual(self.batch("--stage", "vision")[0], 0)
        readings = self.out / "rated_t1-images" / "image_descriptions.json"
        data = json.loads(readings.read_text())
        data["images"]["t1"]["description"] += " edited"
        original = readings.read_text()
        readings.write_text(json.dumps(data))
        code, _out, err = self.batch("--stage", "vision")
        self.assertEqual(code, 2)
        self.assertIn("frozen_images.rated_t1", err)
        readings.write_text(original)
        self.assertEqual(self.batch("--stage", "vision")[0], 0)
        (self.data / "chart.png").write_bytes(PNG_BYTES + b"x")  # same path, other picture
        self.assertEqual(self.batch("--stage", "vision")[0], 2)


class BlindSheetResumeTest(Base):
    def fill(self, folder: Path) -> None:
        key = json.loads((folder / "blind_key.json").read_text())
        kinds = {r["id"]: r["kind"] for r in key["rows"]}
        lines = []
        for line in (folder / "blind_review.md").read_text().splitlines():
            cells = line.split("|")
            if len(cells) > 7 and cells[1].strip() in kinds:
                kind = kinds[cells[1].strip()]
                if kind != "context":
                    cells[6] = " 0 " if kind == "count" else " 正确 "
                    cells[7] = " reviewer note "
                line = "|".join(cells)
            lines.append(line)
        (folder / "blind_review.md").write_text("\n".join(lines) + "\n")

    def test_a_filled_sheet_survives_a_resume_and_a_later_edit_makes_the_tally_stale(self):
        self.assertEqual(self.batch("--stage", "main")[0], 0)
        folder = self.out / "compare-teacher"
        self.fill(folder)
        filled = (folder / "blind_review.md").read_text()
        result = blindtally.run(folder)
        self.assertTrue(result["complete"], result["problems"])
        code, out, _err = self.batch("--stage", "main")
        self.assertEqual(code, 0)
        self.assertIn("保留已有的对照与盲评表：compare-teacher", out)
        self.assertEqual((folder / "blind_review.md").read_text(), filled)
        summary = json.loads((self.out / "summary.json").read_text())
        self.assertTrue(summary["groups"]["teacher"]["blind_tally"]["current"])
        (folder / "blind_review.md").write_text(filled.replace(" reviewer note ", " changed ", 1))
        batch.write_summary(self.out)
        self.assertIn("已过期", (self.out / "summary.md").read_text())
        # The compare command refuses to overwrite it too.
        with self.assertRaises(realcheck_compare.CompareError):
            realcheck_compare.write({"conditions": {}}, folder, blind_seed=1)


class ReclassifiedOnceTest(unittest.TestCase):
    def test_a_reclassified_suggestion_is_one_judged_row(self):
        def view(from_type):
            improvement = {"quote": "Support quote.", "comment": "C", "suggestion": "SAME-ADVICE"}
            if from_type:
                improvement |= {"from_type": "unsupported", "support": ["SUPPORT"]}
            result = {
                "overall_band": 7,
                "criteria": [
                    {"key": k, "band": 7, "summary": "", "issues": []}
                    for k in realcheck.CRITERION_KEYS
                ],
                "argument": {"improvements": [improvement]},
            }
            sample = {
                "id": "s",
                "task_type": "task2",
                "submission": {"essay_text": "Support quote."},
                "generations": {"evaluate": {"status": "ready", "result": result}},
            }
            return realcheck_compare.sample_view({"calls": []}, sample)

        for reclassified in (True, False):
            rows = [
                r
                for r in realcheck_compare.feedback_rows(view(reclassified))
                if r[0] == realcheck_compare.JUDGED and "SAME-ADVICE" in r[4]
            ]
            with self.subTest(reclassified=reclassified):
                self.assertEqual(len(rows), 1)
        rows = realcheck_compare.feedback_rows(view(True))
        self.assertIn("SUPPORT", next(r for r in rows if "SAME-ADVICE" in r[4])[3])


class UnreadableImage(FakeClient):
    def complete(self, messages, **kw):
        if (kw.get("context") or {}).get("kind") == "describe_image":
            self.calls.append("describe_image")
            return LLMResult("The uploaded image is unreadable.", self.model, 5, {})
        return super().complete(messages, **kw)


class FrozenFailureTextTest(unittest.TestCase):
    def test_every_run_exports_the_same_failed_reading(self):
        tmp = Path(tempfile.mkdtemp(prefix="iwa-frozen-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        image = tmp / "chart.png"
        image.write_bytes(PNG_BYTES)
        dirs = []
        for name in ("a", "b"):
            items = realcheck.expand_repeats([item(T1, id="t", image=str(image))], 2)
            data = realcheck.run(
                settings_for(str(tmp / f"d{name}")),
                items,
                client=FakeClient(),
                vision_client=UnreadableImage(),
                kinds=("evaluate",),
            )
            texts = {s["submission"]["image_description"] for s in data["samples"]}
            self.assertEqual(len(texts), 1)
            self.assertIn("unreadable", texts.pop() or "")
            realcheck.write_report(data, realcheck.build_report(data), tmp / name)
            dirs.append(tmp / name)
        cmp = realcheck_compare.compare(*dirs)  # the same failed input on both sides
        self.assertEqual(len(cmp["samples"]), 2)


if __name__ == "__main__":
    unittest.main()
