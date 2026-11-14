"""Read-only production check. Run over SSH via stdin; never import the app."""

import ast
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/apps/studytracker")
FILES = [
    "api/__init__.py",
    "api/miniprogram.py",
    "api/teacher_group_homework.py",
    "services/teacher_homework_recipients.py",
    "miniprogram/pages/teacher/homework/index.js",
    "miniprogram/pages/teacher/homework/index.wxml",
    "miniprogram/pages/teacher/homework/index.wxss",
    "miniprogram/utils/teacher-group-homework.js",
    "gunicorn.conf.py",
]


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def http(url, expected):
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            code, raw = response.status, response.read(1024)
    except urllib.error.HTTPError as error:
        code, raw = error.code, error.read(1024)
    return {
        "url": url,
        "status": code,
        "expected_status": expected,
        "ok": code == expected,
        "auth_error": json.loads(raw).get("error") if code == 401 else None,
    }


def main():
    expected = sys.argv[1]
    # Keep this verifier compatible with production Python 3.10.
    checked_at = datetime.now(timezone.utc).isoformat()  # noqa: UP017
    service = dict(
        line.split("=", 1)
        for line in command(
            "systemctl",
            "show",
            "studytracker",
            "--property=ActiveState,SubState,MainPID,NRestarts,ActiveEnterTimestamp",
        ).splitlines()
    )
    config = {}
    for node in ast.parse((ROOT / "gunicorn.conf.py").read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"bind", "workers", "worker_class", "threads"}:
                config[name] = ast.literal_eval(node.value)
    checks = [
        http(base + route, status)
        for base in ("http://127.0.0.1:5002", "https://studytracker.xin")
        for route, status in (
            ("/login", 200),
            ("/api/miniprogram/teacher/homework/recipients", 401),
            ("/api/miniprogram/teacher/homework/group", 401),
        )
    ]
    status = command("git", "status", "--porcelain")
    head = command("git", "rev-parse", "HEAD")
    tracked = [line for line in status.splitlines() if not line.startswith("??")]
    warnings = command(
        "journalctl",
        "-u",
        "studytracker",
        "--since",
        service["ActiveEnterTimestamp"],
        "-p",
        "warning",
        "--no-pager",
        "--output=json",
    )
    children = Path(f"/proc/{service['MainPID']}/task/{service['MainPID']}/children")
    worker_count = len(children.read_text().split())
    result = {
        "checked_at": checked_at,
        "head": head,
        "expected_head": expected,
        "tracked_changes": len(tracked),
        "untracked_entries": sum(line.startswith("??") for line in status.splitlines()),
        "service": service,
        "gunicorn": config,
        "worker_children": worker_count,
        "warning_entries_since_start": len(warnings.splitlines()),
        "file_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES
        },
        "http": checks,
    }
    result["passed"] = (
        head == expected
        and not tracked
        and service["ActiveState"] == "active"
        and service["SubState"] == "running"
        and config
        == {"bind": "127.0.0.1:5002", "workers": 1, "worker_class": "gthread", "threads": 6}
        and worker_count == 1
        and all(item["ok"] for item in checks)
        and all(item["auth_error"] == "missing_token" for item in checks if item["status"] == 401)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
