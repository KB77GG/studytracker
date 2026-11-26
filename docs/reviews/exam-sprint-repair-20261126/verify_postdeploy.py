"""Read-only deployed commit/snapshot/service/public-list verification."""

import hashlib
import json
import subprocess
from pathlib import Path
from urllib.request import urlopen

ROOT = Path("/root/apps/studytracker")
EXPECTED = "7bde8d672d8067b3b8b62236b299d7f9bafa53d7"
SNAPSHOT = "eaea443d63fa4775caad5f070ff838f90ba971e07ff12b08c0d03824c82b8e79"
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
clean = not subprocess.check_output(
    ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
).strip()
service = subprocess.check_output(
    [
        "systemctl",
        "show",
        "studytracker",
        "-p",
        "ActiveState",
        "-p",
        "SubState",
        "-p",
        "NRestarts",
        "-p",
        "MainPID",
    ],
    text=True,
)
properties = dict(x.split("=", 1) for x in service.splitlines() if "=" in x)
worker_ids = subprocess.check_output(["pgrep", "-P", properties["MainPID"]], text=True).split()
raw = (ROOT / "instance/exam_sprint/current.json").read_bytes()
status = {}
for subject in ("reading", "listening"):
    with urlopen("http://127.0.0.1:5002/practice/sprint/" + subject, timeout=20) as response:
        body = response.read().decode()
        status[subject] = {
            "http": response.status,
            "fresh_date": "2026-11-26 20:27" in body,
            "stale_notice": "本周热榜暂未更新" in body,
        }
result = {
    "head": head,
    "tracked_clean": clean,
    "service": properties,
    "workers": len(worker_ids),
    "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
    "pages": status,
}
result["ok"] = (
    head == EXPECTED
    and clean
    and result["snapshot_sha256"] == SNAPSHOT
    and properties["ActiveState"] == "active"
    and properties["SubState"] == "running"
    and len(worker_ids) == 1
    and all(x["http"] == 200 and x["fresh_date"] and not x["stale_notice"] for x in status.values())
)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["ok"] else 1)
