"""Anonymous read-only production audit; run through Python 3.10 stdin.

The helper is pinned before import. No authenticated HTTP, claims, submissions,
app/config imports, heavy models, DB writes, service changes, or server files.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import importlib.util
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HELPER = "docs/reviews/miniprogram-entry-20261116/verify_production_entry.py"
HELPER_SHA = "2a57054e43d87cfb594d0039dfd68cb95f8106c05bcd365c5a2fc779adb5a45f"
PRODUCT_FILES = (
    "services/vocabulary_autonomous_review.py",
    "services/vocabulary_group_learning.py",
    "api/vocab_review.py",
)
LOG_PATTERN = re.compile(r'\[([^\]]+)\] "(GET|POST) ([^ ]+) HTTP/[^ ]+" (\d+) ')


def helper(root):
    path = root / HELPER
    if hashlib.sha256(path.read_bytes()).hexdigest() != HELPER_SHA:
        raise RuntimeError("unexpected_helper_source")
    spec = importlib.util.spec_from_file_location("entry_readonly_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe_gate(base, app, label, user_id, task_id, *, now=None):
    from sqlalchemy.orm import load_only, selectinload

    from models import StudentProfile, User, db
    from services import vocabulary_autonomous_review as review

    with app.app_context():
        db.session.autoflush = False
        raw = db.session.connection().connection.driver_connection
        raw.execute("BEGIN")
        try:

            def counts():
                return {
                    table: raw.execute(
                        "SELECT COUNT(*) FROM " + table + " WHERE student_id=?",
                        (user_id,),
                    ).fetchone()[0]
                    for table in base.ROW_TABLES
                }

            before = counts()
            query_only_before = raw.execute("PRAGMA query_only").fetchone()[0]
            changes_before = raw.total_changes
            user = (
                User.query.options(
                    load_only(User.id, User.role, User.is_active),
                    selectinload(User.student_profile).load_only(
                        StudentProfile.user_id, StudentProfile.full_name
                    ),
                )
                .filter_by(id=user_id)
                .one()
            )
            if user.role != User.ROLE_STUDENT or not user.is_active:
                raise RuntimeError("invalid_case")
            with patch.object(
                review, "_due_count", side_effect=RuntimeError("backlog_scan_attempted")
            ) as scan:
                started = time.perf_counter()
                value = review.review_preflight(user, task_id, now=now, gate_only=True)
                elapsed = round((time.perf_counter() - started) * 1000, 3)
            payload = base.safe_payload(value)
            after = counts()
            zero_changes = changes_before == raw.total_changes == 0
            query_only = (
                query_only_before == raw.execute("PRAGMA query_only").fetchone()[0] == 1
            )
            clean = not (db.session.new or db.session.dirty or db.session.deleted)
            return {
                "case": label,
                "elapsed_ms": elapsed,
                "safe_result": payload,
                "safe_result_sha256": base.digest(payload),
                "backlog_scan_calls": scan.call_count,
                "query_only_before_and_after": query_only,
                "total_changes_before_and_after_zero": zero_changes,
                "selected_business_counts": before,
                "same_snapshot_counts_unchanged": before == after,
                "no_pending_orm_mutations": clean,
                "ok": bool(payload.get("ok") and payload.get("task_flow_started"))
                and payload.get("required") is False
                and payload.get("due_count") is None
                and scan.call_count == 0
                and zero_changes
                and query_only
                and clean
                and before == after,
            }
        finally:
            db.session.rollback()
            db.session.remove()


def endpoint(method, raw):
    route = raw.split("?", 1)[0]
    if method == "GET" and re.fullmatch(
        r"/api/miniprogram/student/tasks/\d+/vocabulary-queue", route
    ):
        return "vocabulary_queue"
    if method == "GET" and re.fullmatch(
        r"/api/miniprogram/student/tasks/\d+/dictation-queue", route
    ):
        return "dictation_queue_mixed"
    if method == "POST" and route == "/api/dictation/submit":
        return "dictation_submit_mixed"
    return None


def summarize_logs(log_root, deployment, minutes=20):
    windows = (
        ("before", deployment - timedelta(minutes=minutes), deployment),
        ("after", deployment, deployment + timedelta(minutes=minutes)),
    )
    stats = {
        label: {
            "start_inclusive": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "minutes": minutes,
            "logged_get_post_requests": 0,
            "endpoints": {
                key: {
                    "requests": 0,
                    "status_counts": collections.Counter(),
                    "versions": collections.Counter(),
                }
                for key in (
                    "vocabulary_queue",
                    "dictation_queue_mixed",
                    "dictation_submit_mixed",
                )
            },
        }
        for label, start, end in windows
    }
    files_read = 0
    for path in sorted(log_root.glob("access.log*")):
        files_read += 1
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", errors="replace") as stream:
            for line in stream:
                match = LOG_PATTERN.search(line)
                if not match:
                    continue
                stamp, method, raw, status = match.groups()
                try:
                    instant = datetime.strptime(stamp, "%d/%b/%Y:%H:%M:%S %z")
                except ValueError:
                    continue
                for label, start, end in windows:
                    if not start <= instant < end:
                        continue
                    stats[label]["logged_get_post_requests"] += 1
                    key = endpoint(method, raw)
                    if key is None:
                        break
                    item = stats[label]["endpoints"][key]
                    item["requests"] += 1
                    item["status_counts"][status] += 1
                    version = re.search(r"servicewechat\.com/[^/]+/(\d+)/", line)
                    item["versions"][version.group(1) if version else "unknown"] += 1
                    break
    return {
        "retained_logs_only": True,
        "files_read": files_read,
        "windows": stats,
        "interpretation": {
            "499_means_client_closed_request_not_proven_timeout": True,
            "submit_mixes_vocabulary_and_dictation_no_body_inspection": True,
            "request_counts_not_student_counts": True,
            "no_latency_field_available": True,
            "zero_samples_do_not_prove_recovery": True,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument(
        "--expected-head", default="c7e852140cc613b708212a352ec680a0f9dcc8a2"
    )
    parser.add_argument("--deployment", default="2026-11-17T07:41:05+08:00")
    parser.add_argument("--logs", type=Path, default=Path("/var/log/nginx"))
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    result = {
        "at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10
        "python_version": sys.version.split()[0],
        "authenticated_http_called": False,
        "real_wechat_end_to_end": False,
    }
    try:
        base = helper(args.root)
        result["head"] = base.command(args.root, "git", "rev-parse", "HEAD")
        result["head_matches"] = result["head"] == args.expected_head
        result["tracked_clean"] = not base.command(
            args.root, "git", "status", "--porcelain", "--untracked-files=no"
        )
        result["product_source"] = {
            name: {
                "sha256": hashlib.sha256((args.root / name).read_bytes()).hexdigest(),
                "matches_expected_commit": (args.root / name).read_text().strip()
                == base.command(
                    args.root, "git", "show", args.expected_head + ":" + name
                ),
            }
            for name in PRODUCT_FILES
        }
        if not result["head_matches"] or not all(
            item["matches_expected_commit"]
            for item in result["product_source"].values()
        ):
            raise RuntimeError("unexpected_source")
        result["service"] = base.service_info(args.root)
        result["anonymous_http"] = {
            "loopback": base.anonymous_http("http://127.0.0.1:5002"),
            "public_from_server": base.anonymous_http("https://studytracker.xin"),
        }
        cases = base.select_cases(args.root / "app.db", args.logs)
        observations = []
        app = base.make_readonly_app(args.root, args.root / "app.db", observations)
        result["gate_only_probes"] = [probe_gate(base, app, *case) for case in cases]
        result["blocked_sql_attempts"] = sum(item["blocked"] for item in observations)
        result["no_prohibited_imports"] = not any(
            name in sys.modules for name in base.PROHIBITED_IMPORTS
        )
        result["logs"] = summarize_logs(
            args.logs, datetime.fromisoformat(args.deployment)
        )
        result["ok"] = (
            result["tracked_clean"]
            and result["service"]["ok"]
            and all(
                item["ok"]
                for items in result["anonymous_http"].values()
                for item in items
            )
            and len(cases) == 2
            and all(item["ok"] for item in result["gate_only_probes"])
            and result["blocked_sql_attempts"] == 0
            and result["no_prohibited_imports"]
        )
    except Exception as error:
        result.update(ok=False, error_type=type(error).__name__)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
