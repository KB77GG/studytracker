"""Read-only deployment acceptance: files, systemd and anonymous HTTP only."""

import argparse
import ast
import base64
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True).strip()


def service(root):
    output = command(
        root,
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
        "ExecMainStartTimestamp",
    )
    return dict(row.split("=", 1) for row in output.splitlines())


def fetch(path):
    started = time.monotonic()
    with urlopen("http://127.0.0.1:5002" + path, timeout=25) as response:
        body = response.read()
        return response.status, body, round(time.monotonic() - started, 3)


def inspect(root, expected_head, manifest, check_runtime, reading_manifest):
    head = command(root, "git", "rev-parse", "HEAD")
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
    state = service(root)
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Read-only files, Git, systemd and anonymous GET; no app import or DB access.",
        "head": head,
        "expected_head": expected_head,
        "tracked_clean": not command(root, "git", "status", "--porcelain", "--untracked-files=no"),
        "untracked_count": len(
            command(root, "git", "ls-files", "--others", "--exclude-standard").splitlines()
        ),
        "gunicorn": config,
        "service": state,
        "files": {},
    }
    for name, expected in manifest.items():
        path = root / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        result["files"][name] = {"sha256": actual, "matches": actual == expected}
    warnings = command(
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
    result["warnings_since_restart"] = sum(
        bool(row.strip()) and row != "-- No entries --" for row in warnings.splitlines()
    )
    failures = []
    if expected_head and head != expected_head:
        failures.append("unexpected production HEAD")
    if not result["tracked_clean"]:
        failures.append("tracked production changes")
    if state["ActiveState"] != "active" or state["SubState"] != "running":
        failures.append("service not running")
    if config != {"bind": "127.0.0.1:5002", "workers": 1, "worker_class": "gthread", "threads": 6}:
        failures.append("gunicorn constraints changed")
    if any(not row["matches"] for row in result["files"].values()):
        failures.append("runtime file hashes differ")
    if check_runtime:
        runtime = {
            "tests": 0,
            "questions": 0,
            "with_evidence": 0,
            "with_clip": 0,
            "unavailable": [],
            "request_seconds": [],
        }
        for path in sorted((root / "static/listening_tests").glob("ielts*_test*.json")):
            status, body, duration = fetch("/api/listening/test/" + path.stem)
            payload = json.loads(body)
            runtime["tests"] += 1
            runtime["request_seconds"].append(duration)
            for section in payload.get("sections", []):
                for group in section.get("groups", []):
                    for question in group.get("questions", []):
                        review = question.get("audio_review") or {}
                        runtime["questions"] += 1
                        runtime["with_evidence"] += bool(review.get("evidence"))
                        runtime["with_clip"] += bool(review.get("available"))
                        if not review.get("available"):
                            runtime["unavailable"].append(
                                {
                                    "test": path.stem,
                                    "number": question["number"],
                                    "reason": review.get("reason"),
                                }
                            )
            if path.stem == "ielts20_test1":
                runtime["ielts20_test1_section1_timeline"] = payload["sections"][0][
                    "audio_timeline"
                ]
            if path.stem == "ielts18_test1":
                questions = [
                    q for s in payload["sections"] for g in s["groups"] for q in g["questions"]
                ]
                by_number = {q["number"]: q for q in questions}
                q14 = " ".join(row["text"] for row in by_number[14]["audio_review"]["evidence"])
                q29 = " ".join(row["text"] for row in by_number[29]["audio_review"]["evidence"])
                runtime["c18_multi_evidence_complete"] = all(
                    word in q14 for word in ("enough hours", "dedication")
                ) and all(word in q29 for word in ("gap in the market", "returned", "good to know"))
        result["listening_runtime"] = runtime
        if (
            runtime["tests"],
            runtime["questions"],
            runtime["with_evidence"],
            runtime["with_clip"],
        ) != (72, 2880, 2880, 2880):
            failures.append("listening runtime coverage differs")
        if not runtime.get("c18_multi_evidence_complete"):
            failures.append("C18 multi-answer evidence incomplete")
        reading = {"tests": 0, "questions": 0, "source_matches": 0, "mismatches": []}
        for path in sorted((root / "static/reading_tests").glob("ielts*_test*_reading.json")):
            status, body, _duration = fetch("/api/reading/test/" + path.stem)
            payload = json.loads(body)
            reading["tests"] += 1
            reading["questions"] += sum(
                len(group.get("questions", []))
                for passage in payload.get("passages", [])
                for group in passage.get("groups", [])
            )
            actual = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            matches = status == 200 and actual == reading_manifest.get(path.stem)
            reading["source_matches"] += matches
            if not matches:
                reading["mismatches"].append(path.stem)
        result["reading_runtime"] = reading
        if (reading["tests"], reading["questions"], reading["source_matches"]) != (72, 2880, 72):
            failures.append("reading API content differs from validated normalized source files")
        page_checks = []
        for path, required in (
            (
                "/listening/test/ielts18_test1",
                "String(question.id || question.number || '') === String(id)",
            ),
            ("/reading/test/ielts6_test2_reading", "A new study conducted for the World Bank"),
        ):
            status, body, duration = fetch(path)
            present = required in body.decode()
            page_checks.append(
                {"path": path, "status": status, "expected_content": present, "seconds": duration}
            )
            if status != 200 or not present:
                failures.append("page content mismatch: " + path)
        result["pages"] = page_checks
    result["failures"] = failures
    result["ok"] = not failures
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument("--expected-head")
    parser.add_argument("--manifest-b64", default="e30=")
    parser.add_argument("--reading-manifest-b64", default="e30=")
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    result = inspect(
        args.root, args.expected_head, json.loads(base64.b64decode(args.manifest_b64)), args.runtime,
        json.loads(base64.b64decode(args.reading_manifest_b64)),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
