"""Read-only production acceptance; no app/config import, browser JS, or writes.

The remote runner sends this file on stdin to ``python -``. Database identifiers
and capability tokens stay in memory: only safe aggregates and booleans leave
the process. All exceptions are reduced to class names, never their messages.
"""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
import re
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

EXPECTED_CONFIG = {
    "bind": "127.0.0.1:5002",
    "workers": 1,
    "worker_class": "gthread",
    "threads": 6,
}
INTEGRITY_TABLES = (
    "exam_integrity_policy",
    "exam_integrity_state",
    "exam_integrity_event",
)
SESSION_FIELDS = (
    "status",
    "current_section",
    "started_at",
    "finished_at",
    "listening_started_at",
    "listening_deadline_at",
    "listening_submitted_at",
    "reading_started_at",
    "reading_deadline_at",
    "reading_submitted_at",
    "writing_started_at",
    "writing_deadline_at",
    "writing_submitted_at",
)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def command(root, *args):
    # Prevent even an optional Git index refresh while gathering read-only state.
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    return subprocess.check_output(
        args, cwd=root, text=True, stderr=subprocess.DEVNULL, env=env, timeout=30
    ).strip()


def fetch(base, path, markers=(), expected_sha=None):
    """GET only; never return URLs, response headers, bodies, or exception text."""
    try:
        request = Request(
            base.rstrip("/") + path,
            headers={"User-Agent": "StudyTracker read-only release verification"},
            method="GET",
        )
        try:
            response = build_opener(NoRedirect()).open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            body = response.read(4_000_001)
            result = {
                "status": response.code,
                "body_bytes": len(body),
                "body_within_limit": len(body) <= 4_000_000,
                "has_integrity_guard": b"exam_guard" in body,
                "markers": {marker: marker.encode() in body for marker in markers},
            }
            if expected_sha is not None:
                result["sha256_matches"] = hashlib.sha256(body).hexdigest() == expected_sha
            return result
    except Exception as error:
        return {"error": type(error).__name__}


def service_info(root):
    keys = (
        "ActiveState",
        "SubState",
        "MainPID",
        "NRestarts",
        "ExecMainStartTimestamp",
    )
    args = ["systemctl", "show", "studytracker.service"]
    for key in keys:
        args.extend(["-p", key])
    state = {}
    for line in command(root, *args).splitlines():
        key, _, value = line.partition("=")
        if key in keys:
            state[key] = value
    config = {}
    for node in ast.parse((root / "gunicorn.conf.py").read_text()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in EXPECTED_CONFIG:
                    config[target.id] = ast.literal_eval(node.value)
    main_pid = int(state.get("MainPID", "0"))
    children = [
        int(pid) for pid in Path(f"/proc/{main_pid}/task/{main_pid}/children").read_text().split()
    ]
    worker_count = sum(b"gunicorn" in Path(f"/proc/{pid}/cmdline").read_bytes() for pid in children)
    listener_lines = command(root, "ss", "-lntp", "( sport = :5002 )").splitlines()
    listeners = [line for line in listener_lines if line.lstrip().startswith("LISTEN")]
    listener_pids = {int(pid) for line in listeners for pid in re.findall(r"pid=(\d+)", line)}
    listener_owned = bool(listener_pids.intersection({main_pid, *children}))
    loopback_only = bool(listeners) and all(
        len(line.split()) > 3 and line.split()[3] == "127.0.0.1:5002" for line in listeners
    )
    return {
        "systemd": state,
        "gunicorn_config": config,
        "direct_child_count": len(children),
        "actual_gunicorn_worker_count": worker_count,
        "listening_5002": bool(listeners),
        "listening_only_expected_address": loopback_only,
        "listener_owned_by_service": listener_owned,
        "ok": state.get("ActiveState") == "active"
        and state.get("SubState") == "running"
        and config == EXPECTED_CONFIG
        and len(children) == worker_count == 1
        and loopback_only
        and listener_owned,
    }


def deploy_script_info():
    source = Path("/usr/local/sbin/deploy-studytracker").read_bytes()
    return {
        "sha256": hashlib.sha256(source).hexdigest(),
        "contains_literals": {
            key: key.encode() in source
            for key in ("create_all", "create_exam_integrity_tables", *INTEGRITY_TABLES)
        },
    }


def integrity_policy_summary(connection):
    names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?)",
            INTEGRITY_TABLES,
        )
    }
    result = {"tables_present": {name: name in names for name in INTEGRITY_TABLES}}
    if "exam_integrity_policy" not in names:
        result.update(
            source="absent_policy_table_defaults_off",
            policy_rows=0,
            off_rows=0,
            monitor_rows=0,
            enforce_rows=0,
            unexpected_mode_rows=0,
            all_exams_disabled=True,
        )
        return result
    row = connection.execute(
        "SELECT COUNT(*), "
        "COALESCE(SUM(mode='off'),0), COALESCE(SUM(mode='monitor'),0), "
        "COALESCE(SUM(mode='enforce'),0), "
        "COALESCE(SUM(mode NOT IN ('off','monitor','enforce') OR mode IS NULL),0) "
        "FROM exam_integrity_policy"
    ).fetchone()
    result.update(
        source="stored_policy_mode_aggregates",
        policy_rows=row[0],
        off_rows=row[1],
        monitor_rows=row[2],
        enforce_rows=row[3],
        unexpected_mode_rows=row[4],
        all_exams_disabled=row[2] == row[3] == row[4] == 0,
    )
    return result


def session_snapshot(connection, session_id):
    return connection.execute(
        "SELECT " + ",".join(SESSION_FIELDS) + " FROM mock_exam_session WHERE id=?",
        (session_id,),
    ).fetchone()


def database_and_pages(root, base):
    database = root / "app.db"
    if not database.is_file():
        raise FileNotFoundError
    with closing(
        sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)
    ) as conn:
        conn.execute("PRAGMA query_only=ON")
        before_policy = integrity_policy_summary(conn)
        # Prefer a historical unfinished session. Its capability is used only in
        # this function and never returned, stored, included in errors, or printed.
        chosen = conn.execute(
            "SELECT s.id, s.exam_id, s.access_token FROM mock_exam_session s "
            "JOIN mock_exam e ON e.id=s.exam_id "
            "WHERE s.status='in_progress' AND s.access_token IS NOT NULL "
            "AND s.access_token<>'' "
            "ORDER BY CASE WHEN s.started_at<datetime('now','-1 day') THEN 0 ELSE 1 END, "
            "s.id DESC LIMIT 1"
        ).fetchone()
        exam = (
            (chosen[1],)
            if chosen
            else conn.execute("SELECT id FROM mock_exam ORDER BY id DESC LIMIT 1").fetchone()
        )
        login = (
            fetch(base, f"/exam/{exam[0]}", ("examName", "examPin", "btnLogin"))
            if exam
            else {"unverified_reason": "no_existing_exam"}
        )
        if chosen:
            before_session = session_snapshot(conn, chosen[0])
            chapter = fetch(
                base,
                f"/exam/{chosen[1]}/session/{chosen[2]}",
                ("cardPretest", "cardListening", "cardReading"),
            )
            unchanged = before_session == session_snapshot(conn, chosen[0])
        else:
            chapter = {"unverified_reason": "no_existing_unsubmitted_session"}
            unchanged = None
        after_policy = integrity_policy_summary(conn)
        pages_ok = all(
            page.get("status") == 200
            and page.get("body_within_limit")
            and page.get("has_integrity_guard") is False
            and all(page.get("markers", {}).values())
            for page in (login, chapter)
        )
        return {
            "sqlite_open_mode": "ro",
            "query_only": bool(conn.execute("PRAGMA query_only").fetchone()[0]),
            "policy": after_policy,
            "policy_aggregates_and_table_presence_unchanged": before_policy == after_policy,
            "existing_login_page": login,
            "existing_chapter_page": chapter,
            "selected_session_state_and_timestamps_unchanged": unchanged,
            "no_response_body_or_capability_persisted": True,
            "no_javascript_or_post_requests": True,
            "ok": pages_ok
            and unchanged is True
            and before_policy == after_policy
            and after_policy["all_exams_disabled"],
        }


def valid_manifest(root, manifest):
    if not isinstance(manifest, dict):
        raise ValueError
    for name, expected in manifest.items():
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", name)
            or Path(name).is_absolute()
            or ".." in Path(name).parts
            or not (root / name).resolve().is_relative_to(root.resolve())
            or not isinstance(expected, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected)
        ):
            raise ValueError
    return manifest


def inspect(root, expected_head=None, manifest=None, phase="post", base=None, public_base=None):
    result = {
        # Keep the stdin probe usable with a Python 3.10 production interpreter.
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "phase": phase,
        "scope": "Read-only Git/files/systemd/SQLite aggregates/GET; no app import or admin pages",
        "errors": {},
    }
    try:
        head = command(root, "git", "rev-parse", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}", head):
            raise ValueError
        result["head"] = head
        result["expected_head"] = expected_head
        result["head_matches"] = head == expected_head if expected_head else phase == "pre"
        result["tracked_clean"] = not command(
            root, "git", "status", "--porcelain", "--untracked-files=no"
        )
        result["untracked_count"] = len(
            command(root, "git", "ls-files", "--others", "--exclude-standard").splitlines()
        )
    except Exception as error:
        result["errors"]["git"] = type(error).__name__
    for key, reader in (
        ("service", lambda: service_info(root)),
        ("deployment_helper", deploy_script_info),
        ("database_and_pages", lambda: database_and_pages(root, base or "http://127.0.0.1:5002")),
    ):
        try:
            result[key] = reader()
        except Exception as error:
            result["errors"][key] = type(error).__name__
    try:
        manifest = valid_manifest(root, manifest or {})
        result["files_match"] = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
            for name, expected in manifest.items()
        }
        result["public_static_assets"] = {
            name: fetch(public_base, "/" + name, expected_sha=expected)
            for name, expected in manifest.items()
            if public_base and name.startswith("static/")
        }
    except Exception as error:
        result["errors"]["manifest"] = type(error).__name__
    result["ok"] = (
        not result["errors"]
        and result.get("head_matches", False)
        and result.get("tracked_clean", False)
        and result.get("service", {}).get("ok", False)
        and result.get("database_and_pages", {}).get("ok", False)
        and all(result.get("files_match", {}).values())
        and all(
            item.get("status") == 200 and item.get("sha256_matches")
            for item in result.get("public_static_assets", {}).values()
        )
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument("--expected-head")
    parser.add_argument("--manifest-b64")
    parser.add_argument("--phase", choices=("pre", "post"), default="post")
    parser.add_argument("--base", default="http://127.0.0.1:5002")
    parser.add_argument("--public-base")
    args = parser.parse_args()
    try:
        if args.expected_head and not re.fullmatch(r"[0-9a-f]{40}", args.expected_head):
            raise ValueError
        manifest = (
            json.loads(base64.b64decode(args.manifest_b64, validate=True))
            if args.manifest_b64
            else {}
        )
        result = inspect(
            args.root, args.expected_head, manifest, args.phase, args.base, args.public_base
        )
    except Exception as error:
        result = {"ok": False, "error": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
