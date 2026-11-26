"""Read-only production probe. No app/model import, credentials, DB, or write requests."""

import argparse
import ast
import base64
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

FLAG = "PRACTICE_VOCABULARY_WEB_ENABLED"
EXPECTED_GUNICORN = {
    "bind": "127.0.0.1:5002", "workers": 1, "worker_class": "gthread", "threads": 6,
}
MAX_BODY = 8 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()


def enabled(value):
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def configured_flag(root, pid):
    # Read exactly one key into the result. Never emit the process environment or .env.
    prefix = (FLAG + "=").encode()
    process_value = next(
        (entry[len(prefix):].decode("utf-8", "replace")
         for entry in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
         if entry.startswith(prefix)), None,
    )
    if process_value is not None:
        return {"enabled": enabled(process_value), "source": "process_environment"}
    dotenv = root / ".env"
    if dotenv.exists():
        for raw in dotenv.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == FLAG:
                value = value.strip().strip("'").strip('"')
                return {"enabled": enabled(value), "source": "dotenv_fallback"}
    return {"enabled": False, "source": "default_false"}


def fetch(base, path):
    # Fixed anonymous GETs only; no cookie jar, credentials, redirects, or environment proxy.
    request = Request(base + path, method="GET", headers={"User-Agent": "StudyTracker read-only release probe"})
    try:
        response = build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=25)
    except HTTPError as error:
        response = error
    with response:
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("response_too_large")
        location = response.headers.get("Location", "")
        # A redirect URL can contain tokens; only return whether it points to login.
        info = {
            "status": response.code,
            "sha256": hashlib.sha256(body).hexdigest(),
            "redirects_to_login": urlsplit(location).path.startswith("/login"),
            "no_store": "no-store" in response.headers.get("Cache-Control", ""),
        }
        return info, body


def file_manifest(raw):
    data = json.loads(base64.b64decode(raw, validate=True)) if raw else {}
    if not isinstance(data, dict):
        raise ValueError("manifest_must_be_path_hash_mapping")
    for name, digest in data.items():
        if not isinstance(name, str) or not isinstance(digest, str):
            raise ValueError("invalid_manifest_entry")
        path = Path(name)
        if path.is_absolute() or ".." in path.parts or ".env" in path.parts or ".git" in path.parts:
            raise ValueError("invalid_manifest_path")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid_manifest_digest")
    return data


def inspect(args):
    root = args.root.resolve()
    state = dict(line.split("=", 1) for line in command(
        root, "systemctl", "show", "studytracker.service", "-p", "ActiveState", "-p", "SubState",
        "-p", "NRestarts", "-p", "MainPID", "-p", "ExecMainStartTimestamp",
    ).splitlines())
    pid = state["MainPID"]
    children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
    config = {}
    for node in ast.parse((root / "gunicorn.conf.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in EXPECTED_GUNICORN:
                    config[target.id] = ast.literal_eval(node.value)
    flag = configured_flag(root, children[0] if len(children) == 1 else pid)
    manifest = file_manifest(args.manifest_b64)
    head = command(root, "git", "rev-parse", "HEAD")
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - production is Python 3.10
        "mode": "preflight" if args.preflight else "postdeploy",
        "scope": "Read-only files/systemd/proc and anonymous GET; no app/model import, DB, POST, or student session.",
        "head": head, "expected_head": args.expected_head,
        "tracked_clean": not command(root, "git", "status", "--porcelain", "--untracked-files=no"),
        "service": state, "gunicorn_file_config": config,
        "runtime_worker_count": len(children), "configured_vocabulary_flag": flag,
        "files_match": {}, "loopback_pages": {}, "public_pages": {}, "public_assets": {},
        "checks": {},
        "limitations": [
            "Anonymous HTTP checks do not validate a real student's assigned-task list or browser rendering.",
            "gunicorn settings are read from the tracked config; process worker count and loopback port are checked independently.",
            "Process environment may omit values appended by dotenv after exec; disabled HTTP responses are the postdeploy runtime evidence.",
            "No new write endpoint is called, even with the feature disabled.",
        ],
    }
    checks = result["checks"]
    checks["head_matches"] = not args.expected_head or head == args.expected_head
    checks["tracked_clean"] = result["tracked_clean"]
    checks["service_active"] = state["ActiveState"] == "active" and state["SubState"] == "running"
    checks["gunicorn_config_expected"] = config == EXPECTED_GUNICORN
    checks["one_worker_running"] = len(children) == 1
    checks["configured_flag_disabled"] = not flag["enabled"]

    for path in ("/login", "/practice", "/tasks", "/materials"):
        info, body = fetch("http://127.0.0.1:5002", path)
        result["loopback_pages"][path] = info
        checks["loopback_" + path] = (
            info["status"] == 200 if path in {"/login", "/practice"}
            else info["status"] == 302 and info["redirects_to_login"]
        )
        if path == "/practice" and not args.preflight:
            markers = [b'id="practiceAssignedTasks"', b'id="practiceIdentitySubmit"', b'data-practice-hub="root"']
            info["batch1_markers_present"] = all(marker in body for marker in markers)
            checks["practice_batch1_markup"] = info["batch1_markers_present"]
    if args.preflight:
        result["ok"] = all(checks.values())
        return result

    for name, expected in manifest.items():
        result["files_match"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
        if name.startswith("static/"):
            info, _ = fetch(args.public_base, "/" + name)
            result["public_assets"][name] = info
            checks["public_asset_" + name] = info["status"] == 200 and info["sha256"] == expected
    checks["source_manifest_matches"] = bool(manifest) and all(result["files_match"].values())
    required_assets = {"static/js/practice_shell.js", "static/js/practice_modes.js", "static/js/practice_vocabulary_render.js"}
    checks["required_assets_in_manifest"] = required_assets.issubset(manifest)

    for label, base in [("loopback", "http://127.0.0.1:5002"), ("public", args.public_base)]:
        pages = result[label + "_pages"]
        page_path = "/practice/vocabulary/tasks/0"
        info, body = fetch(base, page_path)
        match = re.search(rb'<script[^>]*id="pv-boot"[^>]*>(.*?)</script>', body, re.S)
        boot = json.loads(match.group(1)) if match else {}
        info["boot_blocked"] = boot.get("stage") == "blocked"
        info["boot_feature_disabled"] = boot.get("error") == "feature_disabled"
        info["boot_has_no_student_or_csrf"] = not any(k in boot for k in ("identity_key", "csrf_token", "task"))
        pages[page_path] = info
        checks[label + "_vocabulary_page_disabled"] = (
            info["status"] == 403 and info["boot_blocked"] and info["boot_feature_disabled"]
            and info["boot_has_no_student_or_csrf"] and info["no_store"]
        )
        api_path = "/api/practice/vocabulary/tasks/0/state"
        info, body = fetch(base, api_path)
        data = json.loads(body)
        info["feature_disabled"] = data.get("error") == "feature_disabled"
        pages[api_path] = info
        checks[label + "_vocabulary_state_disabled"] = (
            info["status"] == 403 and info["feature_disabled"] and data.get("ok") is False and info["no_store"]
        )
    render_text = (root / "static/js/practice_vocabulary_render.js").read_text()
    checks["disabled_ui_copy_shipped"] = "网页版背单词暂未开放，请在小程序完成。" in render_text
    info, body = fetch(args.public_base, "/practice")
    result["public_pages"]["/practice"] = info
    checks["public_practice_healthy"] = info["status"] == 200 and b'id="practiceAssignedTasks"' in body
    result["ok"] = all(checks.values())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--expected-head")
    parser.add_argument("--manifest-b64")
    parser.add_argument("--public-base", default="https://studytracker.xin")
    args = parser.parse_args()
    if not args.preflight and (not args.expected_head or not args.manifest_b64):
        parser.error("postdeploy requires --expected-head and --manifest-b64")
    if args.expected_head and not re.fullmatch(r"[0-9a-f]{40}", args.expected_head):
        parser.error("--expected-head must be a full commit hash")
    if args.public_base != "https://studytracker.xin":
        parser.error("only the known StudyTracker production origin is allowed")
    try:
        result = inspect(args)
    except Exception as error:
        # Never emit exception values that could contain config, body, or student data.
        result = {"ok": False, "mode": "preflight" if args.preflight else "postdeploy", "error_type": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
