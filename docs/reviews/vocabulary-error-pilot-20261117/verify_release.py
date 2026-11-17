"""Production read-only checks. stdin execution; no app/config import or writes."""

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

TABLES = (
    "vocabulary_review_policy_enrollment",
    "vocabulary_error_queue",
    "vocabulary_policy_checkpoint",
    "vocabulary_policy_allocation",
    "vocabulary_policy_event",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--after", action="store_true")
    parser.add_argument("--old-schema-sha")
    args = parser.parse_args()
    root = Path("/root/apps/studytracker")
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(
        "previous_readonly_verifier",
        root / "docs/reviews/miniprogram-entry-20261116/verify_production_entry.py",
    )
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    output = {
        "at_utc": datetime.now(timezone.utc).isoformat(),  # noqa: UP017 - Python 3.10
        "read_only": True,
        "student_identities_exported": False,
    }  # noqa: UP017
    try:
        output["head"] = previous.command(root, "git", "rev-parse", "HEAD")
        output["tracked_clean"] = not previous.command(
            root, "git", "status", "--porcelain", "--untracked-files=no"
        )
        output["service"] = previous.service_info(root)
        output["http"] = previous.anonymous_http("http://127.0.0.1:5002")
        output["public_http"] = previous.anonymous_http("https://studytracker.xin")
        pid = int(output["service"]["systemd"]["MainPID"])
        children = Path(f"/proc/{pid}/task/{pid}/children").read_text().split()
        flag = b"VOCABULARY_ERROR_REVIEW_ENABLED="
        dotenv = root / ".env"
        dotenv_value = b""
        if dotenv.exists():
            for line in dotenv.read_text().splitlines():
                if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "VOCABULARY_ERROR_REVIEW_ENABLED":
                    dotenv_value = value.strip().strip("'").strip('"').encode()
                    break
        values = []
        for process in [str(pid), *children]:
            initial = [
                line[len(flag) :]
                for line in Path(f"/proc/{process}/environ").read_bytes().split(b"\0")
                if line.startswith(flag)
            ]
            values.append((initial[0] if initial else dotenv_value).strip().lower())
        boot_time = next(
            int(line.split()[1])
            for line in Path("/proc/stat").read_text().splitlines()
            if line.startswith("btime ")
        )
        start_seconds = [
            boot_time
            + int(Path(f"/proc/{process}/stat").read_text().rsplit(")", 1)[1].split()[19])
            / os.sysconf("SC_CLK_TCK")
            for process in children
        ]
        output["dotenv_precedes_worker_start"] = (
            not dotenv.exists() or dotenv.stat().st_mtime <= min(start_seconds)
        )
        output["process_feature_switch_off"] = all(
            value not in {b"1", b"true", b"yes", b"on"} for value in values
        )
        assignments = [
            node
            for node in ast.walk(ast.parse((root / "config.py").read_text()))
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "VOCABULARY_ERROR_REVIEW_ENABLED"
                for target in node.targets
            )
        ]
        output["code_flag_defaults_off"] = not assignments or all(
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_env_bool"
            and len(node.value.args) == 1
            and not node.value.keywords
            for node in assignments
        )
        observations = []
        connection = previous.readonly_connection(root / "app.db", observations)
        try:
            schema = connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
            ).fetchall()
            old_schema = [row for row in schema if row[2] not in TABLES]
            output["old_schema_sha256"] = previous.digest(old_schema)
            existing = {row[1] for row in schema if row[0] == "table"}
            output["policy_tables_present"] = sum(name in existing for name in TABLES)
            output["policy_row_counts"] = {
                name: connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in TABLES
                if name in existing
            }
            output["schema_read_changes"] = connection.total_changes
        finally:
            connection.close()
        cases = previous.select_cases(root / "app.db", Path("/var/log/nginx"))
        app = previous.make_readonly_app(root, root / "app.db", observations)
        checks = [previous.check_case(app, *case) for case in cases]
        output["legacy_reads_under_5_seconds"] = all(
            call["elapsed_ms"] < 5000 for case in checks for call in case["calls"].values()
        )
        # Do not retain per-student payloads or activity counts, even pseudonymous.
        output["legacy_read_checks"] = [
            {
                "ok": case["ok"],
                "query_only": case["query_only"],
                "zero_changes": case["total_changes_zero"],
                "calls_ms": {name: call["elapsed_ms"] for name, call in case["calls"].items()},
            }
            for case in checks
        ]
        output["blocked_sql"] = sum(state["blocked"] for state in observations)
        output["prohibited_imports_absent"] = not any(
            name in sys.modules for name in previous.PROHIBITED_IMPORTS
        )
        if args.after:
            manifest = json.loads(
                (
                    root / "docs/reviews/vocabulary-error-pilot-20261117/backend-manifest.json"
                ).read_text()
            )
            output["product_hashes_match"] = all(
                hashlib.sha256((root / name).read_bytes()).hexdigest() == value
                for name, value in manifest.items()
            )
            required_paths = {
                "models.py",
                "config.py",
                "services/vocabulary_error_queue.py",
                "services/vocabulary_error_review.py",
                "services/vocabulary_error_reporting.py",
                "api/vocabulary_error_reports.py",
                "api/vocab_review.py",
                "services/vocabulary_autonomous_review.py",
                "services/vocabulary_group_learning.py",
                "services/vocabulary_mastery.py",
            }
            output["product_hashes_match"] = output[
                "product_hashes_match"
            ] and required_paths.issubset(manifest)
            output["old_schema_unchanged"] = output["old_schema_sha256"] == args.old_schema_sha
        output["ok"] = all(
            (
                output["head"] == args.expected_head,
                output["tracked_clean"],
                output["service"]["ok"],
                output["process_feature_switch_off"],
                output["dotenv_precedes_worker_start"],
                output["code_flag_defaults_off"],
                output["schema_read_changes"] == 0,
                output["blocked_sql"] == 0,
                output["prohibited_imports_absent"],
                len(checks) == 2,
                output["legacy_reads_under_5_seconds"],
                all(case["ok"] for case in checks),
                all(row["ok"] for row in output["http"] + output["public_http"]),
            )
        )
        if args.after:
            output["ok"] = (
                output["ok"]
                and output["policy_tables_present"] == 5
                and not any(output["policy_row_counts"].values())
                and output["product_hashes_match"]
                and output["old_schema_unchanged"]
            )
    except Exception as error:
        output.update(ok=False, error_type=type(error).__name__)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
