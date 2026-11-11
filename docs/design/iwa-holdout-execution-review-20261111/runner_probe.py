"""Offline safety probes for the comparison launcher; no models, keys or private data.

Runs the committed shell launcher with an explicit Python stand-in. A JSONL file
acts as the independent transport counter; the stand-in never imports an HTTP client.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

STUB = r"""#!{python}
import fcntl,json,os,signal,sys,time
from pathlib import Path
a=sys.argv[1:]
if a and a[0]=='-c':
    os.execv(sys.executable,[sys.executable]+a)
if '-m' not in a or 'realcheck' not in a:
    sys.exit(0)
def option(k): return a[a.index(k)+1]
out=Path(option('--out'))
cap=int(option('--max-calls'))
event=Path(os.environ['PROBE_EVENTS'])
mode=os.environ['PROBE_MODE']
if mode=='concurrent':
    barrier=Path(os.environ['PROBE_BARRIER'])
    with barrier.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX); f.write(str(os.getpid())+'\n'); f.flush()
    deadline=time.monotonic()+8
    while len(barrier.read_text().splitlines())<2:
        if time.monotonic()>deadline: sys.exit(98)
        time.sleep(.01)
count=5 if mode=='killed' else cap
with event.open('a') as f:
    fcntl.flock(f,fcntl.LOCK_EX)
    f.write(json.dumps({{'out':out.name,'calls':count,'pid':os.getpid(),'mode':mode}})+'\n')
    f.flush(); os.fsync(f.fileno())
if mode=='killed':
    os.kill(os.getpid(),signal.SIGKILL)
out.mkdir(parents=True,exist_ok=True)
report={{'calls':cap,'samples':cap//2,'kinds':{{'evaluate':{{'requested':cap//2,'generated':0,'final_success':0}}}},'aborted':None}}
tmp=out/('report.'+str(os.getpid())+'.tmp');tmp.write_text(json.dumps(report));tmp.replace(out/'report.json')
sys.exit(3 if mode=='concurrent' else 0)
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    repo = args.repo.resolve()
    script = repo / "docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh"
    with tempfile.TemporaryDirectory(prefix="iwa-runner-probe-") as td:
        root = Path(td)
        fake = root / "python-double"
        fake.write_text(STUB.format(python=sys.executable))
        fake.chmod(0o700)
        data = root / "synthetic-data"
        data.mkdir()
        # Only path existence is needed by the shell; no essay content is used.
        for f in [
            "teacher.jsonl",
            "holdout_rated_t2.jsonl",
            "holdout_ordering.jsonl",
            "holdout_lowband.jsonl",
        ]:
            (data / f).write_text("{}\n")
        clean = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("IWA_", "PROBE_", "PRICE_"))
            and k not in ("DRY", "STAGE", "CONFIRM_CAP", "PY")
        }
        clean.update(
            PY=str(fake), IWA_CALIBRATION=str(data), STAGE="main", DRY="0", CONFIRM_CAP="184"
        )
        for m in ("FLASH", "PRO"):
            for k in ("IN", "CACHED", "OUT"):
                clean[f"PRICE_{m}_{k}"] = "0"

        def env_at(out, mode, events):
            return {
                **clean,
                "IWA_COMPARE_OUT": str(out),
                "PROBE_MODE": mode,
                "PROBE_EVENTS": str(events),
            }

        def run(out, mode, events):
            return subprocess.run(
                ["/bin/bash", str(script)],
                cwd=repo,
                env=env_at(out, mode, events),
                capture_output=True,
                text=True,
                errors="backslashreplace",
                timeout=30,
            )

        out = root / "interrupted"
        events = root / "interrupted-calls.jsonl"
        first = run(out, "killed", events)
        first_report_exists = (out / "dev-flash" / "report.json").exists()
        second = run(out, "full", events)
        rows = [json.loads(x) for x in events.read_text().splitlines()]
        interrupted = dict(
            first_exit=first.returncode,
            restart_exit=second.returncode,
            reported_budget_at_restart=second.stdout.splitlines()[0],
            independent_calls=sum(r["calls"] for r in rows),
            authorized_cap=184,
            over_cap=sum(r["calls"] for r in rows) > 184,
            report_survived_first=first_report_exists,
            first_invocations=len([r for r in rows if r["mode"] == "killed"]),
        )

        out = root / "concurrent"
        out.mkdir()
        events = root / "concurrent-calls.jsonl"
        caps = {
            "dev-pro": 28,
            "teacher-flash": 4,
            "teacher-pro": 4,
            "rated_t2-flash": 16,
            "rated_t2-pro": 16,
            "ordering-flash": 20,
            "ordering-pro": 20,
            "lowband-flash": 24,
            "lowband-pro": 24,
        }
        for name, cap in caps.items():
            d = out / name
            d.mkdir()
            (d / "report.json").write_text(json.dumps({"calls": cap}))
            (d / ".done").touch()
        env = env_at(out, "concurrent", events)
        env["PROBE_BARRIER"] = str(root / "barrier")
        processes = [
            subprocess.Popen(
                ["/bin/bash", str(script)],
                cwd=repo,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="backslashreplace",
            )
            for _ in range(2)
        ]
        outputs = [p.communicate(timeout=30) for p in processes]
        rows = [json.loads(x) for x in events.read_text().splitlines()]
        concurrent = dict(
            exits=[p.returncode for p in processes],
            budget_lines=[o[0].splitlines()[0] for o in outputs],
            prior_calls=sum(caps.values()),
            new_independent_calls=sum(r["calls"] for r in rows),
            combined_calls=sum(caps.values()) + sum(r["calls"] for r in rows),
            authorized_cap=184,
            both_launched=len(rows) == 2,
            over_cap=sum(caps.values()) + sum(r["calls"] for r in rows) > 184,
        )

        out = root / "all-failed"
        events = root / "all-failed-calls.jsonl"
        failed = run(out, "full", events)
        rows = [json.loads(x) for x in events.read_text().splitlines()]
        cutoff = dict(
            exit=failed.returncode,
            groups_launched=len(rows),
            done_markers=len(list(out.glob("*/.done"))),
            all_runs_generated_zero=all(
                json.loads(p.read_text())["kinds"]["evaluate"]["generated"] == 0
                for p in out.glob("*/report.json")
            ),
            continued_after_first_failed_group=len(rows) > 1,
        )
        result = {
            "source_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True
            ).strip(),
            "network_calls": 0,
            "private_files_read": False,
            "interrupted_resume": interrupted,
            "concurrent_launch": concurrent,
            "failure_cutoff": cutoff,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
