"""Synthetic cache probe with request outcomes and actual loader instrumentation.

Reuses Claude's workload unchanged, but does not infer cache hits from latency.
No production connection, student identity, response payload or token is saved.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
import tempfile
import threading
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    original_path = (
        repo
        / "docs/reviews/vocabulary-entry-stage2-20261117"
        / "independent-claude/cache_under_writes.py"
    )
    spec = importlib.util.spec_from_file_location("original_cache_probe", original_path)
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    report = {"synthetic_only": True, "reader_due_backlog_words": 2400, "cases": []}
    with tempfile.TemporaryDirectory(prefix="studytracker-cachewrites-verified-") as tmp:
        harness = probe.flow.Harness(repo, Path(tmp))
        from services import vocabulary_autonomous_review as review

        original_loader = review._eligible_due_sense_ids
        original_call = harness.call
        local = threading.local()
        rows = []
        row_lock = threading.Lock()

        def counted_loader(user, now):
            local.loads = getattr(local, "loads", 0) + 1
            return original_loader(user, now)

        def checked_call(kind, method, url, student, body=None, log=None):
            local.loads = 0
            result = original_call(kind, method, url, student, body, log)
            payload = result.get("json") or {}
            row = {
                "kind": kind,
                "status": result["status"],
                "ok": payload.get("ok") is True,
                "elapsed_ms": round(result["elapsed_s"] * 1000, 3),
                "exact_loader_calls": local.loads,
            }
            with row_lock:
                rows.append(row)
            return result

        review._eligible_due_sense_ids = counted_loader
        harness.call = checked_call
        try:
            reader = harness.seed_student(2400, "context")
            for count, gap in ((0, 0.0), (1, 3.0), (3, 3.0), (6, 3.0)):
                writers = [harness.seed_student(400, "meaning") for _ in range(count)]
                rows.clear()
                measured = probe.measure(harness, reader, writers, gap, 12)
                summary_rows = [row for row in rows if row["kind"] == "s"]
                second_rows = summary_rows[1::2]
                with sqlite3.connect(harness.db_path) as connection:
                    written_per_student = [
                        connection.execute(
                            "SELECT count(*) FROM vocabulary_review_item "
                            "WHERE student_id=? AND state_applied=1 AND first_attempt_id IS NOT NULL",
                            (student["id"],),
                        ).fetchone()[0]
                        for student in writers
                    ]
                observed = {
                    "workload_timing_report": measured,
                    "requests": list(rows),
                    "request_counts": dict(Counter(row["kind"] for row in rows)),
                    "all_requests_http200_ok": all(
                        row["status"] == 200 and row["ok"] for row in rows
                    ),
                    "actual_second_read_cache_hits": sum(
                        row["exact_loader_calls"] == 0 for row in second_rows
                    ),
                    "actual_second_read_loader_calls": sum(
                        row["exact_loader_calls"] for row in second_rows
                    ),
                    "writers_with_persisted_answers": sum(
                        value > 0 for value in written_per_student
                    ),
                    "persisted_first_answer_items": sum(written_per_student),
                    "settlement_exercised": any(row["kind"] == "t" for row in rows),
                }
                report["cases"].append(observed)
                assert len(summary_rows) == 24, observed
                assert observed["all_requests_http200_ok"], observed
                assert observed["actual_second_read_cache_hits"] == 12, observed
                assert observed["writers_with_persisted_answers"] == count, observed
                assert (
                    observed["persisted_first_answer_items"]
                    == measured["answers_written_during_run"]
                ), observed
        finally:
            review._eligible_due_sense_ids = original_loader
            harness.call = original_call
            harness.close()
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            [
                {key: value for key, value in case.items() if key != "requests"}
                for case in report["cases"]
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
