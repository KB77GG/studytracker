"""Synthetic real-route comparison; never connect to production or app.db.

Uses the prior audit's fixture and flow driver, adding cold/warm entry samples,
eligibility work counts and status checks for every concurrent request.
"""

import argparse
import importlib.util
import json
import sqlite3
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--backlogs", default="0,500,2400")
    parser.add_argument("--concurrency", default="1,6")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    source = repo / "docs/reviews/vocabulary-flow-latency-20261116/probe_vocabulary_flow.py"
    spec = importlib.util.spec_from_file_location("entry_flow_fixture", source)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    report = {
        "synthetic_only": True,
        "repo": str(repo),
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "flows": [],
        "concurrent_first_open": [],
    }
    with tempfile.TemporaryDirectory(prefix="vocabulary-stage2-benchmark-") as tmp:
        h = fixture.Harness(repo, Path(tmp))
        original_eligible = h.review._candidate_is_eligible
        original_call = h.call

        def eligible(*positional, **keywords):
            h._local.eligibility_checks = getattr(h._local, "eligibility_checks", 0) + 1
            return original_eligible(*positional, **keywords)

        def call(*positional, **keywords):
            h._local.eligibility_checks = 0
            row = original_call(*positional, **keywords)
            row["eligibility_checks"] = h._local.eligibility_checks
            log = keywords.get("log")
            if log:
                log[-1]["eligibility_checks"] = row["eligibility_checks"]
            return row

        h.review._candidate_is_eligible = eligible
        h.call = call

        def safe(row):
            result = {key: value for key, value in row.items() if key != "json"}
            body = row.get("json") or {}
            result.update(
                ok=body.get("ok"),
                error=body.get("error"),
                required=body.get("required"),
                due_count=body.get("due_count"),
                total_count=body.get("total_count"),
            )
            return result

        try:
            backlogs = [int(value) for value in args.backlogs.split(",")]
            for backlog in backlogs:
                student = h.seed_student(backlog, "context")
                url = "/api/miniprogram/student/vocabulary-review/summary"
                cold = h.call("summary_cold", "GET", url, student)
                warm = h.call("summary_warm", "GET", url, student)
                log = fixture.run_entry_and_learning(h, student)
                report["flows"].append(
                    {
                        "backlog": backlog,
                        "cold": safe(cold),
                        "warm": safe(warm),
                        "requests": fixture.summarise(log),
                        "eligibility_by_request": {
                            kind: [row["eligibility_checks"] for row in log if row["kind"] == kind]
                            for kind in sorted({row["kind"] for row in log})
                        },
                        "non_2xx": sum(not 200 <= row["status"] < 300 for row in log),
                    }
                )
                print(f"completed flow backlog={backlog}", flush=True)

            for count in [int(value) for value in args.concurrency.split(",") if value]:
                students = [h.seed_student(max(backlogs), "context") for _ in range(count)]
                barrier = threading.Barrier(count)

                def open_task(student, barrier=barrier):
                    barrier.wait(timeout=30)
                    url = f"/api/miniprogram/student/tasks/{student['task_id']}/vocabulary-review/preflight"
                    preflight = h.call("preflight_cold", "GET", url, student)
                    claim = h.call(
                        "claim_after_preflight",
                        "GET",
                        f"/api/miniprogram/student/vocabulary-review/today?origin_task_id={student['task_id']}",
                        student,
                    )
                    return {"preflight": safe(preflight), "claim": safe(claim)}

                with ThreadPoolExecutor(max_workers=count) as pool:
                    rows = list(pool.map(open_task, students))
                report["concurrent_first_open"].append({"students": count, "rows": rows})
                print(f"completed concurrent entry students={count}", flush=True)
        finally:
            h.review._candidate_is_eligible = original_eligible
            h.close()

    report["all_requests_successful"] = all(
        flow["non_2xx"] == 0 and flow["cold"]["ok"] and flow["warm"]["ok"]
        for flow in report["flows"]
    ) and all(
        row[kind]["status"] == 200 and row[kind]["ok"]
        for group in report["concurrent_first_open"]
        for row in group["rows"]
        for kind in ("preflight", "claim")
    )
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"all_requests_successful": report["all_requests_successful"]}))
    return 0 if report["all_requests_successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
