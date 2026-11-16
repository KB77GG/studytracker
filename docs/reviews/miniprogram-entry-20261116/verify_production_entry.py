"""Read-only release checks for vocabulary entry; suitable for python stdin.

No app/config import, login, queue claim, answer/settlement, or token issuance.
Only anonymous booleans, counts and elapsed times leave this process.
"""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import importlib.abc
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

EXPECTED_CONFIG = {
    "bind": "127.0.0.1:5002",
    "workers": 1,
    "worker_class": "gthread",
    "threads": 6,
}
PRODUCT_FILES = (
    "services/vocabulary_context.py",
    "services/vocabulary_autonomous_review.py",
)
ROW_TABLES = (
    "student_vocabulary_mastery",
    "vocabulary_learning_flow",
    "vocabulary_learning_question",
    "vocabulary_review_session",
    "vocabulary_review_item",
    "vocabulary_review_attempt",
    "vocabulary_review_settlement",
    "dictation_record",
)
CASE_WINDOWS = (("case_a", "15/Nov/2026:17:12"), ("case_b", "16/Nov/2026:10:44"))
PROHIBITED_IMPORTS = {"app", "config", "torch", "whisper", "kokoro", "tensorflow"}


class RejectProhibitedImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".", 1)[0] in PROHIBITED_IMPORTS:
            raise ImportError("prohibited_acceptance_import")
        return None


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def command(root, *args):
    return subprocess.check_output(
        args,
        cwd=root,
        text=True,
        stderr=subprocess.DEVNULL,
        env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
        timeout=20,
    ).strip()


def readonly_connection(path, observations):
    connection = sqlite3.connect(
        "file:" + quote(str(Path(path).resolve()), safe="/") + "?mode=ro",
        uri=True,
        timeout=2,
        check_same_thread=False,
    )
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=2000")
    state = {"blocked": 0, "selects": 0, "connection": connection}
    observations.append(state)
    permitted = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_RECURSIVE,
    }

    def authorizer(action, first, second, _database, _source):
        if (
            action == sqlite3.SQLITE_PRAGMA
            and second is None
            and first in {"query_only", "read_uncommitted"}
        ):
            return sqlite3.SQLITE_OK
        if action in permitted:
            if action == sqlite3.SQLITE_SELECT:
                state["selects"] += 1
            return sqlite3.SQLITE_OK
        state["blocked"] += 1
        return sqlite3.SQLITE_DENY

    connection.set_authorizer(authorizer)
    return connection


def matching_tasks(log_root):
    found = {label: set() for label, _stamp in CASE_WINDOWS}
    for path in Path(log_root).glob("access.log*"):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", errors="replace") as stream:
            for line in stream:
                labels = [label for label, stamp in CASE_WINDOWS if stamp in line]
                if not labels:
                    continue
                match = re.search(
                    r'"GET /api/miniprogram/student/tasks/(\d+)(?:[ /?])', line
                )
                if match:
                    for label in labels:
                        found[label].add(int(match.group(1)))
    return found


def select_cases(db_path, log_root):
    observations = []
    connection = readonly_connection(db_path, observations)
    try:
        cases = []
        for label, ids in matching_tasks(log_root).items():
            rows = []
            for task_id in ids:
                rows.extend(
                    connection.execute(
                        "SELECT student_id, task_id FROM vocabulary_learning_flow WHERE task_id=?",
                        (task_id,),
                    ).fetchall()
                )
            # Refuse an ambiguous time window rather than guessing an identity.
            if len(rows) != 1:
                raise RuntimeError("ambiguous_case_window")
            cases.append((label, int(rows[0][0]), int(rows[0][1])))
        return cases
    finally:
        connection.close()


def safe_payload(payload):
    keys = (
        "ok",
        "required",
        "review_required",
        "task_flow_started",
        "due_count",
        "batch_limit",
        "remaining_due_count",
        "review_due_count",
        "has_active_session",
    )
    result = {key: payload[key] for key in keys if key in payload}
    result["active_batch_present"] = bool(payload.get("active_session_id"))
    result["clearance_present"] = bool(payload.get("clearance_session_id"))
    return result


def make_readonly_app(root, db_path, observations):
    sys.dont_write_bytecode = True
    if any(name in sys.modules for name in PROHIBITED_IMPORTS):
        raise RuntimeError("unsafe_preloaded_module")
    sys.meta_path.insert(0, RejectProhibitedImports())
    sys.path.insert(0, str(root))
    from flask import Flask
    from sqlalchemy.pool import NullPool

    from models import db

    app = Flask("vocabulary-entry-readonly-acceptance")
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "creator": lambda: readonly_connection(db_path, observations),
            "poolclass": NullPool,
        },
    )
    db.init_app(app)
    return app


def check_case(app, label, user_id, task_id, *, now=None):
    from sqlalchemy.orm import load_only, selectinload

    from models import StudentProfile, User, db
    from services.vocabulary_autonomous_review import review_preflight, review_summary

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
                    for table in ROW_TABLES
                }

            before = counts()
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
                raise RuntimeError("inactive_or_invalid_case")
            results = {}
            for name, call in (
                ("preflight", lambda: review_preflight(user, task_id, now=now)),
                ("summary", lambda: review_summary(user, now=now)),
            ):
                started = time.perf_counter()
                value = call()
                results[name] = {
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                    "result": safe_payload(value),
                }
                results[name]["safe_result_sha256"] = digest(results[name]["result"])
            after = counts()
            readonly = raw.execute("PRAGMA query_only").fetchone()[0] == 1
            no_pending = not (db.session.new or db.session.dirty or db.session.deleted)
            no_changes = raw.total_changes == changes_before == 0
            return {
                "case": label,
                "calls": results,
                "query_only": readonly,
                "selected_business_counts": before,
                "same_snapshot_counts_unchanged": before == after,
                "total_changes_zero": no_changes,
                "no_pending_orm_mutations": no_pending,
                "ok": readonly
                and no_changes
                and no_pending
                and before == after
                and all(item["result"].get("ok") for item in results.values()),
            }
        finally:
            db.session.rollback()
            db.session.remove()


def service_info(root):
    keys = ("ActiveState", "SubState", "MainPID", "NRestarts", "ExecMainStartTimestamp")
    args = ["systemctl", "show", "studytracker.service"]
    for key in keys:
        args.extend(["-p", key])
    state = dict(
        line.split("=", 1) for line in command(root, *args).splitlines() if "=" in line
    )
    config = {}
    for node in ast.parse((root / "gunicorn.conf.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in EXPECTED_CONFIG:
                    config[target.id] = ast.literal_eval(node.value)
    pid = int(state.get("MainPID", "0"))
    children = [
        int(value)
        for value in Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
    ]
    worker_count = sum(
        b"gunicorn" in Path(f"/proc/{child}/cmdline").read_bytes() for child in children
    )
    listeners = [
        line
        for line in command(root, "ss", "-lntp", "( sport = :5002 )").splitlines()
        if line.lstrip().startswith("LISTEN")
    ]
    listener_pids = {
        int(value) for line in listeners for value in re.findall(r"pid=(\d+)", line)
    }
    bound_correctly = bool(listeners) and all(
        len(line.split()) > 3 and line.split()[3] == "127.0.0.1:5002"
        for line in listeners
    )
    owned = bool(listener_pids.intersection({pid, *children}))
    return {
        "systemd": state,
        "gunicorn_config": config,
        "actual_worker_count": worker_count,
        "listener_5002_owned": owned,
        "loopback_only": bound_correctly,
        "ok": state.get("ActiveState") == "active"
        and state.get("SubState") == "running"
        and config == EXPECTED_CONFIG
        and len(children) == worker_count == 1
        and bound_correctly
        and owned,
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def anonymous_http(base):
    result = []
    for path, expected in (
        ("/login", 200),
        ("/api/miniprogram/student/vocabulary-review/summary", 401),
    ):
        try:
            request = Request(
                base.rstrip("/") + path,
                method="GET",
                headers={"User-Agent": "StudyTracker read-only entry verification"},
            )
            try:
                response = build_opener(NoRedirect()).open(request, timeout=10)
            except HTTPError as error:
                response = error
            with response:
                status = response.code
                response.read(1024)
            result.append({"route": path, "status": status, "ok": status == expected})
        except Exception as error:
            result.append(
                {"route": path, "error_type": type(error).__name__, "ok": False}
            )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--context-sha", required=True)
    parser.add_argument("--review-sha", required=True)
    parser.add_argument("--logs", type=Path, default=Path("/var/log/nginx"))
    args = parser.parse_args()
    root = args.root.resolve()
    result = {
        "at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10
        "read_only_service_replay": True,
        "real_wechat_end_to_end": False,
    }
    try:
        head = command(root, "git", "rev-parse", "HEAD")
        product_sha = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in PRODUCT_FILES
        }
        result.update(
            head=head,
            head_matches=head == args.expected_head,
            product_sha256=product_sha,
            product_sha_matches=list(product_sha.values())
            == [args.context_sha, args.review_sha],
            tracked_clean=not command(
                root, "git", "status", "--porcelain", "--untracked-files=no"
            ),
        )
        if not (result["head_matches"] and result["product_sha_matches"]):
            raise RuntimeError("unexpected_release_source")
        result["service"] = service_info(root)
        result["anonymous_http"] = anonymous_http("http://127.0.0.1:5002")
        cases = select_cases(root / "app.db", args.logs)
        observations = []
        app = make_readonly_app(root, root / "app.db", observations)
        result["cases"] = [check_case(app, *case) for case in cases]
        result["all_read_calls_under_5_seconds"] = all(
            call["elapsed_ms"] < 5000
            for case in result["cases"]
            for call in case["calls"].values()
        )
        result["no_prohibited_imports"] = not any(
            name in sys.modules for name in PROHIBITED_IMPORTS
        )
        result["blocked_sql_attempts"] = sum(item["blocked"] for item in observations)
        result["ok"] = (
            result["tracked_clean"]
            and result["service"]["ok"]
            and all(item["ok"] for item in result["anonymous_http"])
            and len(result["cases"]) == 2
            and all(item["ok"] for item in result["cases"])
            and result["no_prohibited_imports"]
            and result["blocked_sql_attempts"] == 0
            and result["all_read_calls_under_5_seconds"]
        )
    except Exception as error:
        result.update(ok=False, error_type=type(error).__name__)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
