"""Independent real-process test of killed-parent completion and failure recovery.

Synthetic inputs, real batch/realcheck/ledger, FakeClient only. Network is denied in
every spawned Python process. The successful case keeps the original cap of 112.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SITE = r"""
import fcntl, json, os, sys, time
from pathlib import Path
def deny_network(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo'}:
        raise RuntimeError('offline lifecycle probe forbids network')
sys.addaudithook(deny_network)
from tools.ielts_writing_ai import llm
original = llm.FakeClient.complete
def complete(self, messages, **kw):
    counter = Path(os.environ['RUNNER_COUNTER'])
    with counter.open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps({'pid': os.getpid(), 'model': self.model}) + '\n')
        f.flush(); os.fsync(f.fileno())
    deadline = time.monotonic() + 30
    while self.model == 'fake-pro' and not Path(os.environ['RUNNER_RELEASE']).exists():
        if time.monotonic() > deadline:
            raise RuntimeError('probe release timeout')
        time.sleep(.01)
    if self.model == 'fake-pro' and os.environ.get('RUNNER_FAIL_PRO') == '1':
        return llm.LLMResult('invalid JSON', self.model, 1,
                             {'prompt_tokens': 1, 'completion_tokens': 1})
    return original(self, messages, **kw)
llm.FakeClient.complete = complete
"""


def lock_free(path: Path) -> bool:
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False
    finally:
        os.close(fd)


def wait_for(predicate, message):
    deadline = time.monotonic() + 30
    while not predicate():
        if time.monotonic() > deadline:
            raise RuntimeError(message)
        time.sleep(0.01)


def scenario(repo, root, ledger, essays, *, failure=False):
    data, site, out = root / "data", root / "site", root / "out"
    data.mkdir(parents=True)
    site.mkdir()
    (site / "sitecustomize.py").write_text(SITE)
    for name in ("teacher", "holdout_rated_t2", "holdout_ordering", "holdout_lowband"):
        rows = [
            {"id": f"{name}-{i}", "task_type": "task2", "prompt": s["prompt"], "essay": s["essay"]}
            for i, s in enumerate(essays)
        ]
        (data / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    counter, release = root / "counter.jsonl", root / "release"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("IWA_", "RUNNER_"))}
    env |= {
        "PYTHONPATH": str(site) + os.pathsep + str(repo),
        "RUNNER_COUNTER": str(counter),
        "RUNNER_RELEASE": str(release),
        "RUNNER_FAIL_PRO": "1" if failure else "0",
    }
    command = [
        sys.executable,
        "-m",
        "tools.ielts_writing_ai",
        "realcheck-batch",
        "--dry",
        "--stage",
        "main",
        "--data",
        str(data),
        "--out",
        str(out),
        "--cap",
        "112",
    ]

    def events():
        return [json.loads(s) for s in counter.read_text().splitlines()] if counter.exists() else []

    def run():
        return subprocess.run(
            command, cwd=repo, env=env, capture_output=True, text=True, timeout=30
        )

    with (root / "parent.log").open("w") as log:
        parent = subprocess.Popen(command, cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            wait_for(lambda: any(r["model"] == "fake-pro" for r in events()), "Pro never started")
            parent.kill()
            parent.wait(timeout=5)
            at_kill = len(events())
            child_lock = not lock_free(out / ".batch.lock")
            refused = run()
            after_refusal = len(events())
            release.touch()
            wait_for(lambda: lock_free(out / ".batch.lock"), "orphan realcheck did not exit")
            orphan_calls = len(events())
            child_status = json.loads((out / "dev-pro" / "exit_status.json").read_text())["code"]
            done_before = (out / "dev-pro" / ".done").exists()
            resumed = run()
            resumed_calls = len(events())
            per_run = ledger.summarize(ledger.read(out / "ledger-main.jsonl"))
            result = {
                "parent_exit": parent.returncode,
                "at_kill_calls": at_kill,
                "child_keeps_lock": child_lock,
                "concurrent_exit": refused.returncode,
                "concurrent_added_calls": after_refusal - at_kill,
                "orphan_final_calls": orphan_calls,
                "orphan_status": child_status,
                "done_before_resume": done_before,
                "resume_exit": resumed.returncode,
                "resume_added_calls": resumed_calls - orphan_calls,
                "total_calls": resumed_calls,
                "ledger_reserved": per_run["text"]["reserved"],
                "cap": 112,
                "dev_pro_requests": per_run["runs"]["dev-pro"]["text"],
                "dev_pro_archived": any(out.glob("dev-pro.incomplete-*")),
                "done_after_resume": (out / "dev-pro" / ".done").exists(),
                "resume_adopts_orphan": "dev-pro 在上一个批次退出后自行完成，沿用其结果"
                in resumed.stdout,
            }
            checks = {
                "parent_killed": parent.returncode == -9,
                "child_keeps_lock": child_lock,
                "concurrent_refused_without_requests": refused.returncode == 2
                and after_refusal == at_kill,
                "orphan_not_marked_by_dead_parent": not done_before,
                "ledger_matches_transport": per_run["text"]["reserved"] == resumed_calls,
                "original_cap_respected": resumed_calls <= 112,
            }
            if failure:
                checks |= {
                    "failure_recorded_not_adopted": child_status == 4
                    and not result["done_after_resume"],
                    "same_cap_refuses_incomplete_retry": resumed.returncode == 2
                    and resumed_calls == 42,
                    "no_later_group_launched": set(per_run["runs"]) == {"dev-flash", "dev-pro"},
                }
            else:
                checks |= {
                    "successful_orphan_adopted": child_status == 0
                    and result["resume_adopts_orphan"],
                    "done_repaired": result["done_after_resume"],
                    "no_duplicate_or_archive": result["dev_pro_requests"] == 14
                    and not result["dev_pro_archived"],
                    "complete_normal_plan": resumed.returncode == 0 and resumed_calls == 56,
                }
                again = run()
                result["complete_resume_exit"] = again.returncode
                result["complete_resume_added_calls"] = len(events()) - resumed_calls
                checks["complete_resume_sends_nothing"] = (
                    again.returncode == 0 and len(events()) == resumed_calls
                )
            result["checks"] = checks
            result["passed"] = all(checks.values())
            return result
        finally:
            release.touch()
            if parent.poll() is None:
                parent.kill()
                parent.wait()
            if (out / ".batch.lock").exists():
                wait_for(lambda: lock_free(out / ".batch.lock"), "cleanup waited for orphan")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai import ledger, samples

    essays = [s for s in samples.SAMPLES if s["task_type"] == "task2"][:2]
    with tempfile.TemporaryDirectory(prefix="iwa-lifecycle-review-") as tmp:
        root = Path(tmp)
        cases = {
            "successful_orphan": scenario(repo, root / "success", ledger, essays),
            "failed_orphan": scenario(repo, root / "failure", ledger, essays, failure=True),
        }
    report = {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "network_calls": 0,
        "private_material_read": False,
        "cases": cases,
        "passed": all(r["passed"] for r in cases.values()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
