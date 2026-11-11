"""Transport-level probe of `realcheck-batch` for the three runner scenarios of review
7b222c8 (docs/design/iwa-holdout-execution-review-20261111/runner_review.md).

The reviewer's runner_probe.py replaced the whole realcheck child with a stand-in, which
fits the old shell launcher. The new launcher counts requests inside realcheck, just
before the transport, so this probe keeps realcheck and replaces only the transport:
a sitecustomize.py on PYTHONPATH wraps the demo client's complete() and appends one line
per request to an independent counter file (fsync'd *before* the request "goes out").
It can kill the process at the Nth request or answer every evaluation with invalid JSON.

Scenarios, each with synthetic essays (built-in samples) and no network:
1. killed after 5 requests in dev-flash, then the same command again;
2. two batches started at the same moment on one result folder;
3. every evaluation invalid.
Usage: python batch_probe.py --repo <tree> --out <result.json>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SITE = r"""
import fcntl, json, os, signal
from tools.ielts_writing_ai import llm
_original = llm.FakeClient.complete
def complete(self, messages, **kw):
    kind = (kw.get("context") or {}).get("kind", "")
    path = os.environ["PROBE_COUNTER"]
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps({"pid": os.getpid(), "kind": kind}) + "\n"); f.flush(); os.fsync(f.fileno())
        n = sum(1 for _ in open(path))
    kill_at = int(os.environ.get("PROBE_KILL_AT") or 0)
    if kill_at and n >= kill_at:
        os.kill(os.getpid(), signal.SIGKILL)
    if os.environ.get("PROBE_INVALID") and kind == "evaluate":
        return llm.LLMResult("not json", self.model, 5, {"prompt_tokens": 1, "completion_tokens": 1})
    return _original(self, messages, **kw)
llm.FakeClient.complete = complete
"""


def make_data(repo: Path, folder: Path) -> None:
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai import samples

    t2 = [s for s in samples.SAMPLES if s["task_type"] == "task2"][:2]
    rows = [{"task_type": "task2", "prompt": s["prompt"], "essay": s["essay"]} for s in t2]
    folder.mkdir(parents=True)
    for name in ("teacher", "holdout_rated_t2", "holdout_ordering", "holdout_lowband"):
        with (folder / f"{name}.jsonl").open("w") as f:
            for n, row in enumerate(rows):
                f.write(json.dumps(row | {"id": f"{name}-{n}"}) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    repo = args.repo.resolve()
    with tempfile.TemporaryDirectory(prefix="iwa-batch-probe-") as td:
        root = Path(td)
        site = root / "site"
        site.mkdir()
        (site / "sitecustomize.py").write_text(SITE)
        data = root / "data"
        make_data(repo, data)
        base = {k: v for k, v in os.environ.items() if not k.startswith(("IWA_", "PROBE_"))}
        base["PYTHONPATH"] = f"{site}{os.pathsep}{repo}"

        def batch(out, counter, *, cap, extra_env=None, background=False):
            env = base | {"PROBE_COUNTER": str(counter)} | (extra_env or {})
            command = [sys.executable, "-m", "tools.ielts_writing_ai", "realcheck-batch"]
            command += ["--stage", "main", "--dry", "--data", str(data), "--out", str(out)]
            command += ["--cap", str(cap)]
            kw = dict(cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return subprocess.Popen(command, **kw) if background else subprocess.run(command, **kw)

        def sent(counter):
            return len(counter.read_text().splitlines()) if counter.exists() else 0

        def ledger_used(out):
            from tools.ielts_writing_ai import ledger

            return ledger.summarize(ledger.read(out / "ledger-main.jsonl"))["text"]

        # Worst case of the plan: dev 7×2 + 4 groups of 2 essays (ordering once), ×2 tries,
        # ×2 models = 112.
        worst = 112

        # 1. killed while the 5th request is out, then the same command again
        out, counter = root / "killed", root / "killed.jsonl"
        first = batch(out, counter, cap=worst, extra_env={"PROBE_KILL_AT": "5"})
        after_kill = sent(counter)
        ledger_after_kill = ledger_used(out)
        refused = batch(out, counter, cap=worst)
        after_refusal = sent(counter)
        resumed = batch(out, counter, cap=worst + after_kill)
        killed = {
            "first_exit": first.returncode,
            "first_message": first.stderr.strip().splitlines()[-1:],
            "sent_before_kill": after_kill,
            "ledger_after_kill": ledger_after_kill,
            "restart_with_same_cap_exit": refused.returncode,
            "restart_with_same_cap_message": refused.stderr.strip().splitlines()[-1:],
            "sent_by_refused_restart": after_refusal - after_kill,
            "restart_with_cap_plus_used_exit": resumed.returncode,
            "total_sent": sent(counter),
            "ledger_total": ledger_used(out)["reserved"],
            "cap_respected": sent(counter) <= worst + after_kill,
        }

        # 2. two batches at the same moment
        out, counter = root / "concurrent", root / "concurrent.jsonl"
        procs = [batch(out, counter, cap=worst, background=True) for _ in range(2)]
        outputs = [p.communicate(timeout=300) for p in procs]
        concurrent = {
            "exits": sorted(p.returncode for p in procs),
            "refusal": [
                o[1].strip().splitlines()[-1]
                for o, p in zip(outputs, procs, strict=True)
                if p.returncode
            ],
            "total_sent": sent(counter),
            "cap": worst,
            "cap_respected": sent(counter) <= worst,
        }

        # 3. every evaluation invalid
        out, counter = root / "invalid", root / "invalid.jsonl"
        failed = batch(out, counter, cap=worst, extra_env={"PROBE_INVALID": "1"})
        runs = sorted(p.name for p in out.iterdir() if p.is_dir() and p.name != "data")
        invalid = {
            "exit": failed.returncode,
            "message": failed.stderr.strip().splitlines()[-1:],
            "run_dirs": runs,
            "done_markers": sorted(p.parent.name for p in out.glob("*/.done")),
            "total_sent": sent(counter),
        }

    result = {
        "network_calls": 0,
        "private_files_read": False,
        "killed_and_resumed": killed,
        "concurrent_launch": concurrent,
        "all_invalid": invalid,
        "checks": {
            "kill_counted_on_restart": killed["ledger_after_kill"]["reserved"]
            == killed["sent_before_kill"]
            and killed["ledger_after_kill"]["unknown"] == 1
            and killed["restart_with_same_cap_exit"] == 2
            and killed["sent_by_refused_restart"] == 0
            and killed["ledger_total"] == killed["total_sent"],
            "killed_child_stops_batch": killed["first_exit"] == 3,
            "resume_within_cap_plus_used": killed["restart_with_cap_plus_used_exit"] == 0
            and killed["cap_respected"],
            "second_batch_refused": concurrent["exits"] == [0, 2] and concurrent["cap_respected"],
            "invalid_stops_first_run": invalid["exit"] == 4 and invalid["done_markers"] == [],
        },
    }
    result["passed"] = all(result["checks"].values())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["checks"] | {"passed": result["passed"]}, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
