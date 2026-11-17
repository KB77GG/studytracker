"""Read-only live pilot verification; no login, claim, answer, or app/config import."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import sqlite3
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PREFIX = "VOCABULARY_ERROR_REVIEW_"
DEFAULTS = dict(
    DAILY_LIMIT=20,
    SAMPLE_LIMIT=4,
    MAINTENANCE_LIMIT=10,
    SUCCESS_INTERVAL_DAYS=2,
    FAILURE_LIMIT=3,
    PAUSE_DAYS=7,
    OVERDUE_DAYS=7,
)
TABLES = (
    "vocabulary_review_policy_enrollment",
    "vocabulary_error_queue",
    "vocabulary_policy_checkpoint",
    "vocabulary_policy_allocation",
    "vocabulary_policy_event",
)
REQUIRED = {
    "models.py",
    "config.py",
    "services/vocabulary_error_queue.py",
    "services/vocabulary_error_review.py",
    "services/vocabulary_policy_planning.py",
    "services/vocabulary_group_learning.py",
    "services/vocabulary_pilot_metrics.py",
    "scripts/migrate_vocabulary_checkpoint_sources.py",
    "services/vocabulary_checkpoint_identity.py",
    "gunicorn.conf.py",
    "docs/reviews/miniprogram-entry-20261116/verify_production_entry.py",
}
SAFE_ERRORS = {
    "private_selection_required",
    "expected_unique_students_required",
    "manifest_incomplete",
    "invalid_manifest",
    "manifest_mismatch",
    "unexpected_worker_count",
    "invalid_runtime_parameters",
    "unverified_gunicorn_override",
    "selected_student_not_eligible",
    "ambiguous_student_binding",
    "selected_student_missing_task",
    "unexpected_read_policy",
    "unsafe_preloaded_module",
    "unexpected_source_state",
    "invalid_expected_parameters",
    "unsupported_checkpoint_schema",
    "unsupported_policy_index",
}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(root, *args):
    return subprocess.check_output(
        args,
        cwd=root,
        stderr=subprocess.DEVNULL,
        text=True,
        env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"),
        timeout=20,
    ).strip()


def load_selection(path, expected_size=6):
    if type(expected_size) is not int or expected_size not in (4, 6):
        raise ValueError("expected_unique_students_required")
    path = Path(path)
    if path.is_symlink() or path.stat().st_mode & 0o077 or path.stat().st_uid != os.geteuid():
        raise ValueError("private_selection_required")
    ids = json.loads(path.read_text())["student_ids"]
    if (
        not isinstance(ids, list)
        or len(ids) != expected_size
        or any(type(value) is not int or value <= 0 for value in ids)
        or len(set(ids)) != expected_size
    ):
        raise ValueError("expected_unique_students_required")
    return sorted(ids)


def manifest_check(root, path):
    manifest = json.loads(Path(path).read_text())
    if not isinstance(manifest, dict) or not REQUIRED.issubset(manifest):
        raise ValueError("manifest_incomplete")
    paths = []
    for name, digest in manifest.items():
        target = (root / name).resolve()
        if (
            Path(name).is_absolute()
            or not target.is_relative_to(root.resolve())
            or not re.fullmatch(r"[0-9a-f]{64}", str(digest))
        ):
            raise ValueError("invalid_manifest")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("manifest_mismatch")
        paths.append(target)
    return len(paths), max(p.stat().st_mtime for p in paths if p.suffix == ".py")


def dotenv_values(path):
    """Match config._load_env_file exactly: first assignment wins; no interpolation."""
    result = {}
    if path.exists():
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                if key.startswith(PREFIX) or key == "GUNICORN_CMD_ARGS":
                    result.setdefault(key, value.strip().strip("'").strip('"'))
    return result


def settings(values):
    flag = str(values.get(PREFIX + "ENABLED", "")).strip().lower() in {"1", "true", "yes", "on"}
    parsed = {name: int(values.get(PREFIX + name, default)) for name, default in DEFAULTS.items()}
    if (
        any(value < (0 if name == "SAMPLE_LIMIT" else 1) for name, value in parsed.items())
        or parsed["SAMPLE_LIMIT"] > parsed["DAILY_LIMIT"]
    ):
        raise ValueError("invalid_runtime_parameters")
    return flag, parsed


def launch_verified(root, description, working_directory):
    if Path(working_directory).resolve() != root.resolve() or "argv[]=" not in description:
        return False
    argv = shlex.split(description.split("argv[]=", 1)[1].split(";", 1)[0])
    if not argv or Path(argv[0]).name != "gunicorn":
        return False
    options = {"workers": "1", "threads": "6", "worker-class": "gthread", "bind": "127.0.0.1:5002"}
    aliases = {"-w": "workers", "-k": "worker-class", "-b": "bind", "-c": "config"}
    for index, argument in enumerate(argv[1:], 1):
        name, _, inline = argument.partition("=")
        attached = name[:2] in aliases and len(name) > 2
        if attached:
            name, inline = name[:2], name[2:]
        key = aliases.get(name, name.removeprefix("--"))
        if key not in {*options, "config"}:
            continue
        value = (
            inline
            if "=" in argument or attached
            else (argv[index + 1] if index + 1 < len(argv) else "")
        )
        if key == "config":
            if (root / value).resolve() != (root / "gunicorn.conf.py").resolve():
                return False
        elif value != options[key]:
            return False
    return True


def runtime_settings(root, service, enabled, source_mtime, expected, proc=Path("/proc")):
    pid = int(service["systemd"]["MainPID"])
    children = (proc / f"{pid}/task/{pid}/children").read_text().split()
    if len(children) != 1:
        raise ValueError("unexpected_worker_count")
    dotenv = root / ".env"
    file_values = dotenv_values(dotenv)
    boot = next(
        int(line.split()[1])
        for line in (proc / "stat").read_text().splitlines()
        if line.startswith("btime ")
    )
    start = boot + int(
        (proc / f"{children[0]}/stat").read_text().rsplit(")", 1)[1].split()[19]
    ) / os.sysconf("SC_CLK_TCK")
    configs, explicit = [], 0
    for process in (str(pid), *children):
        environment = dict(
            item.split(b"=", 1)
            for item in (proc / f"{process}/environ").read_bytes().split(b"\0")
            if b"=" in item
        )
        overrides = {
            key.decode(): value.decode()
            for key, value in environment.items()
            if key.startswith(PREFIX.encode()) or key == b"GUNICORN_CMD_ARGS"
        }
        explicit += int(PREFIX + "ENABLED" in overrides)
        values = {**file_values, **overrides}
        # Reject any runtime Gunicorn option override; configured 1/gthread/6
        # is then the effective policy, not just an unused config file.
        if values.get("GUNICORN_CMD_ARGS", "").strip():
            raise ValueError("unverified_gunicorn_override")
        configs.append(settings(values))
    safe = {
        "effective_flag_matches_mode": all(flag == enabled for flag, _ in configs),
        "parameters_match": all(params == expected for _, params in configs),
        "parameters": configs[-1][1],
        "explicit_process_flag_count": explicit,
        "dotenv_flag_present": PREFIX + "ENABLED" in file_values,
        "dotenv_flag_matches_mode": settings(file_values)[0] == enabled,
        "dotenv_precedes_worker_start": not dotenv.exists() or dotenv.stat().st_mtime <= start,
        "worker_started_after_sources": source_mtime <= start,
        "worker_started_at_utc": datetime.fromtimestamp(
            start, timezone.utc  # noqa: UP017 - Python 3.10
        ).isoformat(),
    }
    safe["ok"] = all(
        safe[key]
        for key in (
            "effective_flag_matches_mode",
            "parameters_match",
            "dotenv_precedes_worker_start",
            "worker_started_after_sources",
        )
    )
    safe["ok"] = safe["ok"] and (
        not safe["dotenv_flag_present"] or safe["dotenv_flag_matches_mode"]
    )
    return {
        PREFIX + "ENABLED": configs[-1][0],
        **{PREFIX + key: value for key, value in configs[-1][1].items()},
    }, safe


def readonly_connection(path, observations):
    conn = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=0.25, check_same_thread=False
    )
    conn.execute("PRAGMA query_only=ON")
    state = {"blocked": 0, "connection": conn}
    observations.append(state)
    deadline = time.monotonic() + 10
    conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 5000)
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_RECURSIVE,
    }

    def authorize(action, first, second, _database, _source):
        permitted = action in allowed
        if action == sqlite3.SQLITE_FUNCTION:
            permitted = str(second).lower() not in {"load_extension", "readfile", "writefile"}
        if action == sqlite3.SQLITE_PRAGMA:
            permitted = first in {"table_info", "index_info", "index_list"} or (
                second is None
                and first in {"query_only", "read_uncommitted", "foreign_keys", "journal_mode"}
            )
        if not permitted:
            state["blocked"] += 1
        return sqlite3.SQLITE_OK if permitted else sqlite3.SQLITE_DENY

    conn.set_authorizer(authorize)
    return conn


def enrollment_check(conn, ids, enabled, now):
    rows = conn.execute(
        "SELECT student_id,enabled,starts_at FROM vocabulary_review_policy_enrollment"
    ).fetchall()
    selected = set(ids)
    active = {row[0] for row in rows if row[1]}
    started = sum(
        row[0] in selected and row[1] and datetime.fromisoformat(row[2]) <= now for row in rows
    )
    return {
        "selected_count": len(selected),
        "selected_enabled": len(active & selected),
        "other_enabled": len(active - selected),
        "selected_started": started,
        "ok": active == (selected if enabled else set())
        and (not enabled or started == len(selected)),
    }


def read_case(app, user_id, enabled):
    from models import StudentProfile, Task, User, db
    from services.vocabulary_autonomous_review import review_preflight, review_summary
    from services.vocabulary_mastery import is_vocabulary_v2_task

    with app.app_context():
        db.session.autoflush = False
        raw = db.session.connection().connection.driver_connection
        raw.execute("BEGIN")
        try:
            user = db.session.get(User, user_id)
            profiles = StudentProfile.query.filter_by(user_id=user_id).all()
            if (
                not user
                or user.role != User.ROLE_STUDENT
                or not user.is_active
                or len(profiles) != 1
                or profiles[0].is_deleted
            ):
                raise ValueError("selected_student_not_eligible")
            name = profiles[0].full_name
            if StudentProfile.query.filter_by(full_name=name, is_deleted=False).count() != 1:
                raise ValueError("ambiguous_student_binding")
            tasks = (
                Task.query.filter_by(student_name=name)
                .filter(Task.dictation_book_id.isnot(None))
                .order_by(Task.date.desc(), Task.id.desc())
                .limit(30)
                .all()
            )
            task = next((item for item in tasks if is_vocabulary_v2_task(item)), None)
            if task is None:
                raise ValueError("selected_student_missing_task")

            def counts():
                return tuple(
                    raw.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE student_id=?", (user_id,)
                    ).fetchone()[0]
                    for table in TABLES
                )

            before = counts()
            result = {}
            for label, call in (
                ("summary", lambda: review_summary(user)),
                ("preflight", lambda: review_preflight(user, task.id)),
            ):
                started = time.perf_counter()
                payload = call()
                if payload.get("ok") is not True or bool(payload.get("policy_enabled")) != enabled:
                    raise ValueError("unexpected_read_policy")
                result[label] = round(1000 * (time.perf_counter() - started), 3)
            result["ok"] = (
                raw.total_changes == 0
                and before == counts()
                and raw.execute("PRAGMA query_only").fetchone()[0] == 1
                and not (db.session.new or db.session.dirty or db.session.deleted)
            )
            return result
        finally:
            db.session.rollback()
            db.session.remove()


def replay(root, database, ids, configuration, enabled, observations, previous):
    if any(name in sys.modules for name in previous.PROHIBITED_IMPORTS):
        raise RuntimeError("unsafe_preloaded_module")
    sys.meta_path.insert(0, previous.RejectProhibitedImports())
    sys.path.insert(0, str(root))
    from flask import Flask
    from sqlalchemy.pool import NullPool

    from models import db

    app = Flask("vocabulary-pilot-readonly")
    app.config.update(
        configuration,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={
            "creator": lambda: readonly_connection(database, observations),
            "poolclass": NullPool,
        },
    )
    db.init_app(app)
    results = [read_case(app, student, enabled) for student in ids]
    return {
        "sample_count": len(results),
        "all_ok": all(row["ok"] for row in results),
        "calls_ms": {
            label: {
                "n": len(results),
                "p50": round(statistics.median(row[label] for row in results), 3),
                "max": max(row[label] for row in results),
                "total": round(sum(row[label] for row in results), 3),
            }
            for label in ("summary", "preflight")
        },
        "all_calls_under_5_seconds": all(
            row[label] < 5000 for row in results for label in ("summary", "preflight")
        ),
    }


def run(args):
    sys.dont_write_bytecode = True
    root = args.root.resolve()
    result = {
        "read_only": True,
        "identities_exported": False,
        "real_wechat_end_to_end": False,
        "enabled_expected": args.enabled,
        "at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
    }
    ids = load_selection(args.selection, args.expected_size)
    result["expected_size"] = args.expected_size
    result["head_matches"] = command(root, "git", "rev-parse", "HEAD") == args.expected_head
    result["tracked_clean"] = not command(
        root, "git", "status", "--porcelain", "--untracked-files=no"
    )
    count, source_mtime = manifest_check(root, args.manifest)
    result["manifest_files_verified"] = count
    if not result["head_matches"] or not result["tracked_clean"]:
        raise ValueError("unexpected_source_state")
    previous = load_module(
        "live_previous", root / "docs/reviews/miniprogram-entry-20261116/verify_production_entry.py"
    )
    service = previous.service_info(root)
    result["service"] = {
        "ok": service["ok"],
        "actual_worker_count": service["actual_worker_count"],
        "configuration": service["gunicorn_config"],
        "listener_owned": service["listener_5002_owned"],
        "loopback_only": service["loopback_only"],
        "restart_count": int(service["systemd"]["NRestarts"]),
    }
    result["service"]["launch_matches_config"] = launch_verified(
        root,
        command(root, "systemctl", "show", "studytracker.service", "-p", "ExecStart", "--value"),
        command(
            root, "systemctl", "show", "studytracker.service", "-p", "WorkingDirectory", "--value"
        ),
    )
    expected = (
        DEFAULTS if args.expected_parameters is None else json.loads(args.expected_parameters)
    )
    if set(expected) != set(DEFAULTS) or any(type(value) is not int for value in expected.values()):
        raise ValueError("invalid_expected_parameters")
    configuration, result["runtime"] = runtime_settings(
        root, service, args.enabled, source_mtime, expected
    )
    result["anonymous_http"] = {
        label: previous.anonymous_http(base)
        for label, base in (
            ("loopback", "http://127.0.0.1:5002"),
            ("public", "https://studytracker.xin"),
        )
    }
    observations = []
    database = root / "app.db"
    conn = readonly_connection(database, observations)
    try:
        conn.execute("BEGIN")
        migration = load_module(
            "live_checkpoint_schema", root / "scripts/migrate_vocabulary_checkpoint_sources.py"
        )
        result["schema"] = migration.inspect(conn)
        result["enrollment"] = enrollment_check(
            conn, ids, args.enabled, datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: UP017
        )
        result["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
        result["schema_snapshot_zero_writes"] = conn.total_changes == 0
    finally:
        conn.close()
    schema_ok = not result["schema"]["migration_required"] or (
        args.allow_pending_migration and not args.enabled
    )
    if not (service["ok"] and result["runtime"]["ok"] and schema_ok and result["enrollment"]["ok"]):
        result["ok"] = False
        return result
    result["replay"] = replay(
        root, database, ids, configuration, args.enabled, observations, previous
    )
    result["blocked_sql_attempts"] = sum(row["blocked"] for row in observations)
    result["prohibited_imports_absent"] = not any(
        name in sys.modules for name in previous.PROHIBITED_IMPORTS
    )
    result["ok"] = all(
        (
            result["schema_snapshot_zero_writes"],
            result["journal_mode"] == "delete",
            result["blocked_sql_attempts"] == 0,
            result["prohibited_imports_absent"],
            result["replay"]["all_ok"],
            result["replay"]["all_calls_under_5_seconds"],
            result["service"]["restart_count"] == 0,
            result["service"]["launch_matches_config"],
            all(item["ok"] for values in result["anonymous_http"].values() for item in values),
        )
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/root/apps/studytracker"))
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--expected-size", type=int, choices=(4, 6), default=6)
    parser.add_argument("--enabled", action="store_true")
    parser.add_argument("--allow-pending-migration", action="store_true")
    parser.add_argument(
        "--expected-parameters",
        help="JSON object with the seven approved uppercase parameter names",
    )
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except Exception as error:
        result = {
            "ok": False,
            "read_only": True,
            "identities_exported": False,
            "error_type": type(error).__name__,
            "error_code": str(error) if str(error) in SAFE_ERRORS else "verification_failed",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
