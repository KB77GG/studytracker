"""Kill only the batch parent; check whether its realcheck child keeps the batch lock.

Synthetic input and FakeClient only. An independent counter is written by the fake
transport. No HTTP, private configuration, or user data is read.
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
import json,os,sys,time,fcntl
from pathlib import Path
def deny_network(event,args):
    if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo'}:
        raise RuntimeError('offline probe forbids network')
sys.addaudithook(deny_network)
from tools.ielts_writing_ai import llm
old=llm.FakeClient.complete
def complete(self,messages,**kw):
    event=Path(os.environ['RUNNER_COUNTER'])
    with event.open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        f.write(json.dumps({'pid':os.getpid(),'kind':(kw.get('context') or {}).get('kind'),'model':self.model})+'\n')
        f.flush();os.fsync(f.fileno())
    release=Path(os.environ['RUNNER_RELEASE'])
    deadline=time.monotonic()+30
    while self.model == 'fake-pro' and not release.exists():
        if time.monotonic()>deadline: raise RuntimeError('probe release timeout')
        time.sleep(.01)
    return old(self,messages,**kw)
llm.FakeClient.complete=complete
"""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai import ledger, samples

    with tempfile.TemporaryDirectory(prefix="iwa-parent-lock-probe-") as tmp:
        root = Path(tmp)
        data, site, out = root / "data", root / "site", root / "results"
        data.mkdir()
        site.mkdir()
        (site / "sitecustomize.py").write_text(SITE)
        essays = [s for s in samples.SAMPLES if s["task_type"] == "task2"][:2]
        for name in ("teacher", "holdout_rated_t2", "holdout_ordering", "holdout_lowband"):
            rows = [
                {
                    "id": f"{name}-{i}",
                    "task_type": "task2",
                    "prompt": s["prompt"],
                    "essay": s["essay"],
                }
                for i, s in enumerate(essays)
            ]
            (data / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        counter, release = root / "counter.jsonl", root / "release"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("IWA_", "RUNNER_"))}
        env.update(
            PYTHONPATH=str(site) + os.pathsep + str(repo),
            RUNNER_COUNTER=str(counter),
            RUNNER_RELEASE=str(release),
        )
        cmd = [
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

        def sent():
            return (
                [json.loads(x) for x in counter.read_text().splitlines()]
                if counter.exists()
                else []
            )

        log1 = (root / "first.log").open("w")
        log2 = (root / "second.log").open("w")
        first = subprocess.Popen(cmd, cwd=repo, env=env, stdout=log1, stderr=subprocess.STDOUT)
        second = None
        try:
            deadline = time.monotonic() + 10
            while not any(r["model"] == "fake-pro" for r in sent()):
                if time.monotonic() > deadline:
                    raise RuntimeError("first request not reached")
                time.sleep(0.01)
            child_pid = next(r["pid"] for r in sent() if r["model"] == "fake-pro")
            first.kill()
            first.wait(timeout=5)
            child_alive = alive(child_pid)
            fd = os.open(out / ".batch.lock", os.O_RDWR)
            lock_free = False
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_free = True
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                pass
            finally:
                os.close(fd)
            second = subprocess.Popen(cmd, cwd=repo, env=env, stdout=log2, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 5
            while (
                len({r["pid"] for r in sent() if r["model"] == "fake-pro"}) < 2
                and second.poll() is None
            ):
                if time.monotonic() > deadline:
                    break
                time.sleep(0.01)
            before_release = sent()
            overlap = len(
                {r["pid"] for r in before_release if r["model"] == "fake-pro"}
            ) >= 2 and alive(child_pid)
            second_live = second.poll() is None
            release.touch()
            second.wait(timeout=30)
            deadline = time.monotonic() + 5
            while alive(child_pid) and time.monotonic() < deadline:
                time.sleep(0.01)
            used = ledger.summarize(ledger.read(out / "ledger-main.jsonl"))
            result = {
                "source_head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=repo, text=True
                ).strip(),
                "network_calls": 0,
                "private_material_read": False,
                "first_parent_exit": first.returncode,
                "first_child_alive_after_parent_kill": child_alive,
                "lock_free_while_first_child_alive": lock_free,
                "second_parent_running_before_release": second_live,
                "two_transport_children_overlap": overlap,
                "requests_before_release": len(before_release),
                "second_exit": second.returncode,
                "total_transport_calls": len(sent()),
                "ledger_reserved": used["text"]["reserved"],
                "cap": 112,
                "cap_still_respected": len(sent()) <= 112,
                "first_child_alive_at_end": alive(child_pid),
                "expected_normal_transport_calls": 56,
                "duplicate_dev_pro_calls": used["runs"]["dev-pro"]["text"],
            }
        finally:
            release.touch()
            for process in (first, second):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
            log1.close()
            log2.close()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
