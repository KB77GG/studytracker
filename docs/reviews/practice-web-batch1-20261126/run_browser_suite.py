"""Run preserved Claude scripts against one local synthetic fixture server."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("label", choices=("before", "after"))
parser.add_argument("port", type=int)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
report = Path(__file__).resolve().parent
out = Path("/private/tmp") / f"practice-web-batch1-{args.label}"
env = os.environ.copy()
records = []
for name in ("crawl", "flows", "dialog", "probe", "probe2"):
    command = ["node", str(report / "rerun_audit.js"), name, str(args.port), str(out)]
    start = time.monotonic()
    log = report / "validation" / f"{args.label}-{name}.log"
    with log.open("w") as stream:
        try:
            result = subprocess.run(command, cwd=root, env=env, stdout=stream,
                                    stderr=subprocess.STDOUT, timeout=420)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    record = {"name": name, "argv": command, "cwd": str(root), "exit": code,
              "seconds": round(time.monotonic() - start, 3), "log": str(log.relative_to(root))}
    records.append(record)
    print(json.dumps(record), flush=True)
    (report / "validation" / f"{args.label}-commands.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n")
