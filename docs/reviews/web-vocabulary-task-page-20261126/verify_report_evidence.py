"""Reconcile persisted evidence only; does not run tests or touch products."""

import collections
import hashlib
import json
import re
from pathlib import Path

report = Path(__file__).resolve().parent
root = report.parents[2]
manifest = json.loads((report / "manifest.json").read_text())
mismatches = [
    entry["path"]
    for entry in manifest["files"]
    if hashlib.sha256((root / entry["path"]).read_bytes()).hexdigest() != entry["sha256"]
]
log = (report / "validation/full-py310.log").read_text()
counts = collections.Counter(re.findall(r"^test_\w+ \((tests\.[^.]+)\.", log, re.M))
logs = {}
for name in ("full-py313", "full-py310", "date-py313", "date-py310", "full-node"):
    path = report / "validation" / f"{name}.log"
    logs[name] = {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "tail": path.read_text().splitlines()[-8:],
    }
result = {
    "purpose": "Verify unchanged source and existing logs; not a fresh test run",
    "manifest_file_count": len(manifest["files"]),
    "mismatches": mismatches,
    "py310_test_count_by_module": dict(counts),
    "py310_total": sum(counts.values()),
    "logs": logs,
    "not_completed": [
        "Native browser 125/150 percent zoom",
        "Real keyboard long hold and OS Chinese IME candidate confirmation",
        "Browser refresh specifically while awaiting correction",
        "Player slow load / eight-second timeout test",
        "True offline / transport-level lost-response refresh",
        "Real WeChat client switching and teacher/parent UI inspection",
    ],
}
(report / "verification-recheck.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n"
)
print(f"manifest: {len(manifest['files'])} files, {len(mismatches)} mismatches")
print(f"existing Python 3.10 log: {sum(counts.values())} tests")
raise SystemExit(bool(mismatches))
