"""Read-only release acceptance: files/systemd/anonymous HTTP; no app or DB."""

import argparse
import ast
import base64
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True).strip()


def fetch(base, path):
    request = Request(base + path, headers={"User-Agent": "StudyTracker release verification"})
    try:
        response = build_opener(NoRedirect()).open(request, timeout=25)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        return {
            "status": response.code,
            "location": response.headers.get("Location"),
            "sha256": hashlib.sha256(body).hexdigest(),
        }


def inspect(root, expected_head, manifest):
    state = dict(
        line.split("=", 1)
        for line in command(
            root,
            "systemctl",
            "show",
            "studytracker.service",
            "-p",
            "ActiveState",
            "-p",
            "SubState",
            "-p",
            "NRestarts",
            "-p",
            "ExecMainStartTimestamp",
        ).splitlines()
    )
    config = {}
    for node in ast.parse((root / "gunicorn.conf.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {
                    "bind",
                    "workers",
                    "worker_class",
                    "threads",
                }:
                    config[target.id] = ast.literal_eval(node.value)
    head = command(root, "git", "rev-parse", "HEAD")
    files = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
        for name, expected in manifest.items()
    }
    pages = {
        path: fetch("http://127.0.0.1:5002", path)
        for path in ("/materials/classroom-vocabulary", "/materials", "/login")
    }
    assets = {
        name: fetch("https://studytracker.xin", "/" + name)
        for name in manifest
        if name.startswith("static/")
    }
    logs = command(
        root,
        "journalctl",
        "-u",
        "studytracker",
        "--since",
        state["ExecMainStartTimestamp"],
        "-p",
        "warning",
        "--no-pager",
        "-o",
        "cat",
    )
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Read-only files, systemd, anonymous GET; no app/config import or DB access",
        "head": head,
        "expected_head": expected_head,
        "tracked_clean": not command(root, "git", "status", "--porcelain", "--untracked-files=no"),
        "untracked_count": len(
            command(root, "git", "ls-files", "--others", "--exclude-standard").splitlines()
        ),
        "service": state,
        "gunicorn": config,
        "files_match": files,
        "pages": pages,
        "public_assets": assets,
        "warning_lines_since_restart": sum(
            bool(line.strip()) and line != "-- No entries --" for line in logs.splitlines()
        ),
    }
    result["ok"] = (
        head == expected_head
        and result["tracked_clean"]
        and all(files.values())
        and state["ActiveState"] == "active"
        and state["SubState"] == "running"
        and config
        == {"bind": "127.0.0.1:5002", "workers": 1, "worker_class": "gthread", "threads": 6}
        and pages["/login"]["status"] == 200
        and all(
            pages[path]["status"] == 302 and pages[path]["location"].startswith("/login")
            for path in ("/materials/classroom-vocabulary", "/materials")
        )
        and all(
            value["status"] == 200 and value["sha256"] == manifest[name]
            for name, value in assets.items()
        )
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--manifest-b64", required=True)
    args = parser.parse_args()
    result = inspect(args.root, args.expected_head, json.loads(base64.b64decode(args.manifest_b64)))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
