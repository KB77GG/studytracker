#!/usr/bin/env python3
"""Production acceptance via SSH stdin: files/systemd and anonymous loopback HTTP.

No app/config/model import, database connection, credential/session read or ML
initialization. By default two anonymous grading POSTs are sent with no cookies,
learner name, task or access token, and each must return synced=false. Use
--skip-guest-post for strictly GET/HEAD-only acceptance. JSON evidence goes only
to stdout; this script does not publish files, restart services or change Git.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

BASE_URL = "http://127.0.0.1:5002"
GUNICORN = {"bind": "127.0.0.1:5002", "workers": 1, "worker_class": "gthread", "threads": 6}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def command(root, *arguments):
    return subprocess.check_output(arguments, cwd=root, text=True, timeout=30).strip()


def fetch(path, *, method="GET", payload=None):
    parsed = urlsplit(path)
    if (
        not path.startswith("/")
        or path.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or any(ord(char) < 32 for char in path)
    ):
        raise ValueError("Only loopback-relative request paths are allowed")
    headers = {"User-Agent": "StudyTracker exam-sprint release acceptance"}
    raw = None
    if payload is not None:
        raw = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(BASE_URL + path, data=raw, headers=headers, method=method)
    # No proxy, redirect, cookie jar or authentication handler is permitted.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        try:
            response = opener.open(request, timeout=25)
        except HTTPError as error:
            response = error
        with response:
            body = b"" if method == "HEAD" else response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError("Unexpectedly large practice response")
            return {
                "status": response.code,
                "content_type": response.headers.get("Content-Type", ""),
                "bytes": int(response.headers.get("Content-Length", "0") or 0),
                "body": body.decode("utf-8", errors="replace"),
            }
    except OSError as error:
        return {
            "status": 0,
            "content_type": "",
            "bytes": 0,
            "body": "",
            "error": type(error).__name__,
        }


def gunicorn_config(root):
    result = {}
    for node in ast.parse((root / "gunicorn.conf.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in GUNICORN:
                    result[target.id] = ast.literal_eval(node.value)
    return result


def command_line_overrides_are_safe(exec_start):
    for flag, expected in (
        (r"--workers|-w", "1"),
        (r"--threads", "6"),
        (r"--worker-class|-k", "gthread"),
        (r"--bind|-b", "127.0.0.1:5002"),
    ):
        matches = re.findall(rf"(?:^|\s)(?:{flag})(?:=|\s+)([^\s;]+)", exec_start)
        if any(value.strip("'\"") != expected for value in matches):
            return False
    return True


def canonical_answers(subject, payload, passage):
    """Use public answer keys with the same controls as the actual practice page."""
    answers, total = {}, 0
    parts = payload["passages"] if subject == "reading" else [payload]
    if subject == "reading" and passage:
        parts = [parts[passage - 1]]
    for part in parts:
        for group in part["groups"]:
            questions = group["questions" if subject == "reading" else "items"]
            total += len(questions)
            first = str(questions[0].get("answer") or "")
            letters = [value.strip() for value in first.split(",")]
            shared = (
                len(questions) > 1
                and len(letters) == len(questions)
                and all(re.fullmatch(r"[A-Z]", value) for value in letters)
                and all(question.get("answer") == first for question in questions)
            )
            if subject == "listening" and str(group.get("type")) == "2" and shared:
                answers[group.get("desc") or group.get("question_title")] = ",".join(letters)
                continue
            for index, question in enumerate(questions):
                key = str(question["id"] if subject == "reading" else question["number"])
                value = str(question.get("answer") or "")
                if not value:
                    raise ValueError("Imported exercise has an empty canonical answer")
                answers[key] = (
                    letters[index] if subject == "reading" and shared else value.split("/")[0]
                )
    return answers, total


def media_urls(subject, payload):
    result = set()
    if subject == "listening":
        value = payload["audio"]["local_path"]
        result.add(value if value.startswith("/") else f"/static/listening_jijing/{value}")
    for part in payload["passages"] if subject == "reading" else [payload]:
        for group in part["groups"]:
            if group.get("img_local"):
                result.add(f"/static/{group['img_local']}")
            elif group.get("img_url"):
                result.add(group["img_url"])
        if subject == "reading":
            for image in (part.get("content") or {}).get("images", []):
                value = image["url"]
                result.add(value if value.startswith("/") else f"/static/{value}")
    return result


def inspect_release(root, expected_head, *, skip_guest_post=False):
    root = Path(root).resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise ValueError("Expected HEAD must be a full Git SHA")
    head = command(root, "git", "rev-parse", "HEAD")
    properties = (
        "ActiveState",
        "SubState",
        "NRestarts",
        "MainPID",
        "ExecMainStartTimestamp",
        "WorkingDirectory",
        "ExecStart",
    )
    raw_service = command(
        root,
        "systemctl",
        "show",
        "studytracker.service",
        *[argument for name in properties for argument in ("-p", name)],
    )
    service = dict(line.split("=", 1) for line in raw_service.splitlines() if "=" in line)
    config = gunicorn_config(root)
    clean = not command(root, "git", "status", "--porcelain", "--untracked-files=no")
    command_safe = command_line_overrides_are_safe(service.get("ExecStart", ""))
    master_pid = int(service.get("MainPID") or 0)
    workers = []
    if master_pid:
        # Only PIDs are inspected; never process environments or learner records.
        children = subprocess.run(
            ["ps", "--no-headers", "-o", "pid", "--ppid", str(master_pid)],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if children.returncode not in (0, 1):
            raise ValueError("Cannot inspect gunicorn worker count")
        workers = [int(pid) for pid in children.stdout.split()]
    system_ok = (
        head == expected_head
        and clean
        and config == GUNICORN
        and command_safe
        and service.get("ActiveState") == "active"
        and service.get("SubState") == "running"
        and Path(service.get("WorkingDirectory", "")).resolve() == root
        and master_pid > 0
        and len(workers) == 1
    )
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 (Python 3.10)
        "scope": "Git/systemd/public content and anonymous loopback HTTP; no app/config/DB import",
        "head": head,
        "expected_head": expected_head,
        "tracked_clean": clean,
        "service": {key: service.get(key) for key in properties if key != "ExecStart"},
        "gunicorn": {
            **config,
            "actual_worker_count": len(workers),
            "command_overrides_safe": command_safe,
        },
        "guest_posts_skipped": skip_guest_post,
        "ok": False,
    }
    if not system_ok:
        report["failure"] = "Release HEAD, tracked files or service configuration differs"
        return report
    sys.path.insert(0, str(root))
    from scripts.activate_exam_sprint import using_state_directory, validate_candidate
    from services.exam_sprint import _local_target, load_sprint_view

    state = root / "instance/exam_sprint"
    current = state / "current.json"
    if current.is_symlink():
        raise ValueError("Current snapshot is not a regular runtime file")
    raw = current.read_bytes()
    snapshot = json.loads(raw)
    report["snapshot_sha256"] = hashlib.sha256(raw).hexdigest()
    report["snapshot_validation"] = validate_candidate(root, snapshot, state)
    pages, practices, assets, selected, failures = {}, [], {}, {}, []
    with using_state_directory(state):
        for subject, total in (("reading", 60), ("listening", 80)):
            view = load_sprint_view(root, subject)
            page = fetch(f"/practice/sprint/{subject}")
            pages[subject] = {
                "status": page["status"],
                "total": view["total"],
                "ready": view["ready_count"],
                "stale": view["stale"],
            }
            if page["status"] != 200 or view["total"] != total or view["ready_count"] != total:
                failures.append(f"{subject} list is not fully available")
            for group in snapshot["subjects"][subject]:
                for row in group["items"]:
                    mapping = row.get("mapping")
                    target = _local_target(root, mapping or {})
                    if target is None:
                        failures.append(f"Unavailable public source unit {row['source_id']}")
                        continue
                    payload, url = target
                    response = fetch(url)
                    practice = {
                        "subject": subject,
                        "target_id": payload["id"],
                        "status": response["status"],
                    }
                    practices.append(practice)
                    variable = "rawTestData" if subject == "reading" else "part"
                    match = re.search(rf"^const {variable} = (.+);$", response["body"], re.M)
                    embedded = json.loads(match[1]) if match else {}
                    if response["status"] != 200 or embedded.get("id") != payload["id"]:
                        failures.append(f"Practice GET failed for {payload['id']}")
                    if mapping.get("target_kind") == "ninefen" and subject not in selected:
                        selected[subject] = (mapping, payload)
                    for url in media_urls(subject, payload):
                        if url in assets:
                            continue
                        response = fetch(url, method="HEAD")
                        assets[url] = {
                            key: response[key] for key in ("status", "content_type", "bytes")
                        }
                        kind = "audio/" if url.endswith(".mp3") else "image/"
                        if (
                            response["status"] != 200
                            or response["bytes"] <= 0
                            or not response["content_type"].startswith(kind)
                        ):
                            failures.append(f"Public media HEAD failed: {url}")
    report.update(
        {
            "pages": pages,
            "practices": practices,
            "assets": assets,
            "practice_get_count": len(practices),
            "media_head_count": len(assets),
            "audio_count": sum(row["content_type"].startswith("audio/") for row in assets.values()),
            "image_count": sum(row["content_type"].startswith("image/") for row in assets.values()),
        }
    )
    if len(practices) != 140 or report["audio_count"] != 80 or report["image_count"] != 15:
        failures.append("Expected 140 practices, 80 audio files and 15 diagrams for this release")
    report["anonymous_grading"] = []
    if not failures and not skip_guest_post:
        for subject in ("reading", "listening"):
            if subject not in selected:
                failures.append(f"No native {subject} exercise for guest grading")
                continue
            mapping, payload = selected[subject]
            answers, total = canonical_answers(subject, payload, mapping.get("passage"))
            prefix = "/api/reading/test/" if subject == "reading" else "/api/listening/jijing/"
            response = fetch(
                prefix + payload["id"] + "/submit",
                method="POST",
                payload={"answers": answers, "passage_number": mapping.get("passage")},
            )
            result = json.loads(response["body"]) if response["status"] == 200 else {}
            grade = result.get("result") or {}
            check = {
                "subject": subject,
                "status": response["status"],
                "synced": result.get("synced"),
                "correct": grade.get("correct"),
                "total": grade.get("total"),
            }
            report["anonymous_grading"].append(check)
            if (
                response["status"] != 200
                or result.get("ok") is not True
                or result.get("synced") is not False
                or grade.get("correct") != total
                or grade.get("total") != total
            ):
                failures.append(f"Anonymous {subject} canonical grading failed")
    report["failures"] = failures
    report["ok"] = not failures
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--skip-guest-post", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = inspect_release(
            args.root, args.expected_head, skip_guest_post=args.skip_guest_post
        )
    except Exception as error:
        # Never print arbitrary HTTP bodies, process command lines or tracebacks.
        report = {
            "ok": False,
            "failure_type": type(error).__name__,
            "failure": "Production acceptance could not complete; no publication or restart performed",
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
