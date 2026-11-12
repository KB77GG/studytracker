"""Independent synthetic manifest/frozen-artifact audit; no network or private data."""
from __future__ import annotations

import argparse
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    sys.path.insert(0, str(args.repo))
    sys.dont_write_bytecode = True

    def offline(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("network forbidden by offline source review")

    sys.addaudithook(offline)
    from tools.ielts_writing_ai import __main__ as cli
    from tools.ielts_writing_ai import batch, ledger, realcheck
    from tools.ielts_writing_ai.llm import FakeClient
    from tools.ielts_writing_ai.tests.helpers import PNG_BYTES

    checks = []

    def check(name, actual, expected):
        checks.append(dict(name=name, actual=actual, expected=expected, ok=actual == expected))

    class Spy(FakeClient):
        def __init__(self, model):
            super().__init__(model=model)
            self.sent = 0

        def complete(self, *a, **kw):
            self.sent += 1
            return super().complete(*a, **kw)

    with tempfile.TemporaryDirectory(prefix="iwa-source-manifest-") as td:
        tmp = Path(td)
        data = tmp / "data"
        data.mkdir()
        image = data / "chart.png"
        image.write_bytes(PNG_BYTES)
        source = data / "holdout_rated_t1.jsonl"
        env_file = tmp / "intentionally-absent.env"
        quote = "The chart compares four museums."
        essay = quote + " Museum C has the greatest number of visitors, while Museum D has the fewest. Museum A is ahead of Museum B."
        base = dict(id="synthetic-t1", task_type="task1", prompt="Describe the chart.", essay=essay, image="chart.png", target_band=7, teacher={"overall": 5.5}, teachers=[{"rater": "A", "overall": 5.5}], teacher_findings=[{"quote": quote, "note": "Synthetic reference note."}], group="synthetic-group")

        def write(path, item):
            path.write_text(json.dumps(item, ensure_ascii=False) + "\n")

        def totals(out, stage):
            used = ledger.summarize(ledger.read(out / f"ledger-{stage}.jsonl"))
            return [used["text"]["reserved"], used["vision"]["reserved"]]

        def stage(out, name="vision", stop_pro=False, groups=None):
            launched, spies = [], []
            def client(conf, vision=False):
                spy = Spy("fake-vision" if vision else conf.llm_model)
                spies.append(spy)
                return spy
            def child(cmd, **kw):
                run_name = Path(cmd[cmd.index("--out") + 1]).name
                launched.append(run_name)
                if stop_pro and run_name.endswith("-pro"):
                    return subprocess.CompletedProcess(cmd, -15)
                with mock.patch.dict(os.environ, kw["env"], clear=True):
                    code = cli.main(["--env-file", kw["env"]["IWA_ENV_FILE"], *cmd[3:]])
                return subprocess.CompletedProcess(cmd, code)
            argv = SimpleNamespace(stage=name, data=str(data), out=str(out), dry=True, cap=16, price=None, env_file=str(env_file))
            before = totals(out, name)
            stdout, stderr = io.StringIO(), io.StringIO()
            stages = dict(batch.STAGES)
            if groups:
                stages[name] = groups
            with mock.patch.object(batch, "STAGES", stages), mock.patch.object(batch.subprocess, "run", side_effect=child), mock.patch.object(realcheck, "build_client", side_effect=client), redirect_stdout(stdout), redirect_stderr(stderr):
                code = batch.run_stage(argv)
            after = totals(out, name)
            return dict(exit=code, launched=launched, dispatched=sum(s.sent for s in spies), ledger_delta=[a-b for a,b in zip(after,before)], stderr=stderr.getvalue())

        write(source, base)
        out = tmp / "partial"
        initial = stage(out, stop_pro=True)
        check("baseline_images_and_flash_complete", [initial["exit"], totals(out,"vision")], [3, [2,1]])
        image_results = out / "rated_t1-images/image_descriptions.json"
        frozen_before = image_results.read_bytes()
        manifest_before = (out / "batch-vision.json").read_bytes()

        mutations = {
            "prompt": lambda i: i.update(prompt="Compare the visitor numbers in the chart."),
            "essay": lambda i: i.update(essay=i["essay"] + " The exhibition is open on weekends."),
            "teacher_overall": lambda i: i["teacher"].update(overall=6.5),
            "rater_overall": lambda i: i["teachers"][0].update(overall=6.5),
            "annotation_note": lambda i: i["teacher_findings"][0].update(note="Changed synthetic reference."),
            "annotation_quote": lambda i: i["teacher_findings"][0].update(quote="Museum A is ahead of Museum B."),
            "target_band": lambda i: i.update(target_band=8),
            "group": lambda i: i.update(group="another-synthetic-group"),
        }
        for name, mutate in mutations.items():
            item = copy.deepcopy(base)
            mutate(item)
            write(source, item)
            result = stage(out)
            check(f"changed_{name}_refused_before_any_dispatch", [result["exit"], result["launched"], result["dispatched"], result["ledger_delta"]], [2, [], 0, [0,0]])
            check(f"changed_{name}_does_not_repin_manifest", (out / "batch-vision.json").read_bytes() == manifest_before, True)
        write(source, base)

        image.write_bytes(PNG_BYTES + b"changed synthetic pixels")
        result = stage(out)
        check("changed_image_bytes_refused_before_dispatch", [result["exit"], result["launched"], result["dispatched"], result["ledger_delta"]], [2, [], 0, [0,0]])
        image.write_bytes(PNG_BYTES)

        frozen = json.loads(frozen_before)
        frozen["images"][base["id"]]["description"] += " Changed chart description."
        image_results.write_text(json.dumps(frozen))
        result = stage(out)
        check("changed_frozen_reading_refused_before_dispatch", [result["exit"], result["dispatched"], result["ledger_delta"]], [2, 0, [0,0]])
        image_results.write_bytes(frozen_before)

        stamp = out / "rated_t1-flash/inputs.sha256"
        saved_stamp = stamp.read_bytes()
        stamp.write_text("0" * 64 + "\n")
        result = stage(out)
        check("wrong_done_fingerprint_refused_before_dispatch", [result["exit"], result["dispatched"], result["ledger_delta"]], [2, 0, [0,0]])
        stamp.unlink()
        result = stage(out)
        check("missing_done_fingerprint_refused_before_dispatch", [result["exit"], result["dispatched"], result["ledger_delta"]], [2, 0, [0,0]])
        stamp.write_bytes(saved_stamp)

        # A different location containing exactly the same source bytes is allowed.
        copied = data / "same-chart-other-location.png"
        copied.write_bytes(PNG_BYTES)
        same = dict(base, image=copied.name)
        before = batch.manifest(realcheck.load_samples(str(source)))
        write(source, same)
        after = batch.manifest(realcheck.load_samples(str(source)))
        check("same_image_bytes_other_path_same_manifest", after, before)
        result = stage(out)
        check("unchanged_semantics_can_resume", [result["exit"], result["dispatched"], result["ledger_delta"]], [0, 2, [2,0]])
        result = stage(out)
        check("fully_completed_resume_zero_dispatch", [result["exit"], result["dispatched"], result["ledger_delta"]], [0, 0, [0,0]])

        # Optional group support is additive; it cannot weaken pinned prior groups.
        groups = (batch.Group("teacher", "Synthetic teacher", "teacher.jsonl", 2, "flash"), batch.Group("official", "Synthetic official", "official.jsonl", 2, "pro", optional=True))
        t2 = dict(id="synthetic-teacher", task_type="task2", prompt="Should education be publicly funded?", essay="Public funding can give more people access to education. I support aid for families who need it because they may be unable to pay the fees. Governments have limited resources, so they should make their priorities clear.", teacher={"overall":6})
        teacher_file = data / "teacher.jsonl"
        official_file = data / "official.jsonl"
        write(teacher_file, t2)
        main_out = tmp / "optional"
        first = stage(main_out, name="main", groups=groups)
        check("optional_absent_initial_group_runs", [first["exit"], totals(main_out,"main")], [0,[4,0]])
        write(official_file, dict(t2, id="synthetic-official"))
        write(teacher_file, dict(t2, essay=t2["essay"] + " New sentence."))
        result = stage(main_out, name="main", groups=groups)
        check("adding_optional_does_not_allow_old_data_change", [result["exit"], result["launched"], result["ledger_delta"]], [2,[],[0,0]])
        write(teacher_file, t2)
        result = stage(main_out, name="main", groups=groups)
        check("new_optional_group_only_new_calls", [result["exit"], result["launched"], result["ledger_delta"]], [0,["official-pro","official-flash"],[4,0]])
        saved_official = official_file.read_bytes()
        write(official_file, dict(t2, id="synthetic-official", teacher={"overall":7}))
        result = stage(main_out, name="main", groups=groups)
        check("newly_pinned_official_cannot_change", [result["exit"], result["launched"], result["ledger_delta"]], [2,[],[0,0]])
        official_file.unlink()
        result = stage(main_out, name="main", groups=groups)
        check("pinned_optional_cannot_disappear", [result["exit"], result["launched"], result["ledger_delta"]], [2,[],[0,0]])
        official_file.write_bytes(saved_official)
        result = stage(main_out, name="main", groups=groups)
        check("restored_optional_resume_zero_calls", [result["exit"], result["dispatched"], result["ledger_delta"]], [0,0,[0,0]])

    result = dict(paid_calls=0, network_forbidden=True, checks=checks, passed=sum(c["ok"] for c in checks), total=len(checks))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2) + "\n")
    print(json.dumps({"passed":result["passed"],"total":result["total"],"failures":[c for c in checks if not c["ok"]]},ensure_ascii=False))
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
