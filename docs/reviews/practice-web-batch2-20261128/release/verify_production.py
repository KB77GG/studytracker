"""Read-only batch-two release probe; never import app/models or read credentials/DB.

Run on the server through SSH stdin. Output is allowlisted metadata and booleans;
no response body, cookie, identity, environment value or raw redirect is emitted.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

EXPECTED_GUNICORN = {
    "bind": "127.0.0.1:5002", "workers": 1, "worker_class": "gthread", "threads": 6,
}
PRODUCTS = {
    "static/js/practice_shell.js",
    "templates/auth/_entrance_shell.html", "templates/base.html",
    "templates/listening/index.html", "templates/listening/jijing_index.html",
    "templates/listening/test_index.html", "templates/practice/_workspace_header.html",
    "templates/practice/_workspace_styles.html", "templates/practice/exam_sprint.html",
    "templates/practice/index_content.html", "templates/question_type_practice/student_index.html",
    "templates/reading/jijing_index.html", "templates/reading/test_index.html",
    "templates/writing/index.html", "templates/writing/topics.html",
}
PUBLIC_CATALOGS = {
    "/practice": "练习中心",
    "/practices": "精听练习",
    "/listening": "精听练习",
    "/listening/tests": "剑雅听力",
    "/reading/tests": "剑雅阅读",
    "/listening/jijing": "听力机经",
    "/reading/jijing": "阅读机经",
    "/practice/sprint/listening": "听力考前冲刺",
    "/practice/sprint/reading": "阅读考前冲刺",
    "/practice/question-types": "IELTS 题型专项",
}
MAX_BODY = 8 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.rows = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.rows.append((tag, dict(attrs)))

    def with_attr(self, name):
        return [attrs for _, attrs in self.rows if name in attrs]


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()


def fetch(base, path):
    request = Request(
        base + path, method="GET",
        headers={"User-Agent": "StudyTracker read-only batch2 release probe"},
    )
    try:
        response = build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("response_too_large")
        redirect = urlsplit(response.headers.get("Location", ""))
        local_redirect = not redirect.netloc or redirect.netloc == urlsplit(base).netloc
        info = {
            "status": response.code,
            "sha256": hashlib.sha256(body).hexdigest(),
            "redirects_to_login": local_redirect and redirect.path == "/login",
            "redirects_to_practice": local_redirect and redirect.path == "/practice",
            "no_store": "no-store" in response.headers.get("Cache-Control", ""),
        }
        return info, body


def file_manifest(raw):
    data = json.loads(base64.b64decode(raw, validate=True)) if raw else {}
    if not isinstance(data, dict) or set(data) != PRODUCTS:
        raise ValueError("manifest_requires_exactly_15_batch2_product_files")
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in data.values()):
        raise ValueError("invalid_manifest_digest")
    return data


def catalog_structure(body, path):
    html = body.decode("utf-8", errors="replace")
    headers = re.findall(r"<header[^>]*data-practice-workspace-header[^>]*>(.*?)</header>", html, re.S)
    if len(headers) != 1:
        return {"shared_header_count": len(headers), "ok": False}
    header = headers[0]
    all_elements, elements = Elements(html), Elements(header)
    brands = elements.with_attr("data-practice-home")
    expected_back_count = 0 if path == "/practice" else 1
    nav = re.search(r"<nav[^>]*>(.*?)</nav>", header, re.S)
    labels = re.findall(r">([^<>]+)</a>", nav.group(1)) if nav else []
    headings = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    checks = {
        "brand_intact": len(brands) == 1 and "data-practice-module-back" not in brands[0]
            and brands[0].get("href") == "/practice" and "Sage Path</span>" in header
            and 'brand/sagepath-mark.png' in header,
        "five_navigation_items": labels == ["练习中心", "听力", "阅读", "写作", "题型专项"],
        "one_context_back_or_none_at_root": len(elements.with_attr("data-practice-module-back")) == expected_back_count
            and len(all_elements.with_attr("data-practice-module-back")) == expected_back_count,
        "one_module_exit": len(elements.with_attr("data-practice-module-exit")) == 1,
        "guest_identity_label": len(elements.with_attr("data-practice-identity-label")) == 1
            and "未确认身份" in header,
        "one_expected_h1": headings == [PUBLIC_CATALOGS[path]],
        "branded_title": bool(re.search(r"<title>[^<]+ · Sage Path</title>", html)),
    }
    if path in {"/practices", "/listening"}:
        checks["identity_gate_preserved"] = 'id="studentVerifyForm"' in html and 'id="practiceIntensiveIdentitySwitch"' in html
        checks["duplicate_overview_removed"] = all(marker not in html for marker in (
            'id="newTasksList"', 'id="practiceHistoryList"', 'class="auth-entry__brandbar"',
        ))
    if path == "/practice":
        checks["batch1_identity_tasks_preserved"] = all(marker in html for marker in (
            'id="practiceIdentityForm"', 'id="practiceAssignedTasks"', 'data-practice-hub="root"',
        ))
    return {"shared_header_count": 1, "checks": checks, "ok": all(checks.values())}


def inspect(args):
    root = args.root.resolve()
    state = dict(line.split("=", 1) for line in command(
        root, "systemctl", "show", "studytracker.service", "-p", "ActiveState", "-p", "SubState",
        "-p", "NRestarts", "-p", "MainPID", "-p", "ExecMainStartTimestamp",
    ).splitlines())
    pid = state["MainPID"]
    children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split() if pid.isdigit() and pid != "0" else []
    config = {}
    for node in ast.parse((root / "gunicorn.conf.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in EXPECTED_GUNICORN:
                    config[target.id] = ast.literal_eval(node.value)
    head = command(root, "git", "rev-parse", "HEAD")
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - production Python3.10
        "mode": "preflight" if args.preflight else "postdeploy",
        "scope": "Read-only git/files/systemd/proc metadata and anonymous GET; no app/models import, DB, secrets/environment, cookies or write requests.",
        "head": head, "expected_head": args.expected_head,
        "tracked_clean": not command(root, "git", "status", "--porcelain", "--untracked-files=no"),
        "service": state, "gunicorn_file_config": config, "runtime_worker_count": len(children),
        "files_match": {}, "loopback_pages": {}, "public_pages": {}, "public_assets": {}, "checks": {},
        "limitations": [
            "Anonymous HTML structure checks do not execute JS, render a browser or prove signed-in/student/teacher journeys.",
            "Writing catalogs retain their existing anonymous redirect; their authenticated HTML is not checked here.",
            "Gunicorn class/thread/bind values are read from config; worker count and loopback health are independent runtime checks.",
            "Vocabulary feature remains enabled by requiring existing identity_missing responses; no .env or process environment is read or changed.",
        ],
    }
    checks = result["checks"]
    checks["head_matches"] = not args.expected_head or head == args.expected_head
    checks["tracked_clean"] = result["tracked_clean"]
    checks["service_active"] = state["ActiveState"] == "active" and state["SubState"] == "running"
    checks["gunicorn_config_expected"] = config == EXPECTED_GUNICORN
    checks["one_worker_running"] = len(children) == 1
    for label, base in (("loopback", "http://127.0.0.1:5002"), ("public", args.public_base)):
        pages = result[label + "_pages"]
        for path in ("/login", "/practice", "/tasks", "/materials"):
            try:
                info, body = fetch(base, path)
                pages[path] = info
                checks[label + path + "_health"] = (
                    info["status"] == 200 if path in {"/login", "/practice"}
                    else info["status"] == 302 and info["redirects_to_login"]
                )
            except Exception as error:
                pages[path] = {"error_type": type(error).__name__}
                checks[label + path + "_health"] = False
        for path in ("/practice/vocabulary/tasks/0", "/api/practice/vocabulary/tasks/0/state"):
            try:
                info, body = fetch(base, path)
                if path.startswith("/api/"):
                    data = json.loads(body)
                else:
                    match = re.search(rb'<script[^>]*id="pv-boot"[^>]*>(.*?)</script>', body, re.S)
                    data = json.loads(match.group(1)) if match else {}
                info["identity_missing"] = data.get("error") == "identity_missing"
                info["no_student_or_csrf_payload"] = not any(key in data for key in ("identity_key", "csrf_token", "task"))
                pages[path] = info
                checks[label + path + "_enabled_and_gated"] = (
                    info["status"] == 401 and info["identity_missing"]
                    and info["no_store"] and info["no_student_or_csrf_payload"]
                )
            except Exception as error:
                pages[path] = {"error_type": type(error).__name__}
                checks[label + path + "_enabled_and_gated"] = False
        if args.preflight:
            continue
        for path in PUBLIC_CATALOGS:
            try:
                info, body = fetch(base, path)
                info["structure"] = catalog_structure(body, path)
                pages[path] = info
                checks[label + path + "_batch2_markup"] = info["status"] == 200 and info["structure"]["ok"]
            except Exception as error:
                pages[path] = {"error_type": type(error).__name__}
                checks[label + path + "_batch2_markup"] = False
        for path in ("/writing/", "/writing/topics"):
            try:
                info, _ = fetch(base, path)
                pages[path] = info
                checks[label + path + "_anonymous_gate"] = info["status"] == 302 and info["redirects_to_practice"]
            except Exception as error:
                pages[path] = {"error_type": type(error).__name__}
                checks[label + path + "_anonymous_gate"] = False
    if not args.preflight:
        manifest = file_manifest(args.manifest_b64)
        for name, digest in manifest.items():
            result["files_match"][name] = hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
        checks["source_manifest_matches"] = all(result["files_match"].values())
        name = "static/js/practice_shell.js"
        try:
            info, _ = fetch(args.public_base, "/" + name)
            result["public_assets"][name] = info
            checks["public_practice_shell_sha_matches"] = info["status"] == 200 and info["sha256"] == manifest[name]
        except Exception as error:
            result["public_assets"][name] = {"error_type": type(error).__name__}
            checks["public_practice_shell_sha_matches"] = False
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
        result = {"ok": False, "mode": "preflight" if args.preflight else "postdeploy", "error_type": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
