"""Synthetic-only: how long does each vocabulary request keep SQLite's write lock?

A request owns the write lock from its first INSERT/UPDATE/DELETE until COMMIT.
While it is held, every other student's write waits (pysqlite gives up after
5 s with "database is locked").  Measures that window per request kind for a
student with a large due backlog.

Usage: python -B probe_write_lock_hold.py --repo . [--backlog 2400] [--output f.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_vocabulary_flow as flow  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--backlog", type=int, default=2400)
    parser.add_argument("--output")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    from sqlalchemy import event

    with tempfile.TemporaryDirectory(prefix="studytracker-lockhold-") as tmp:
        h = flow.Harness(repo, Path(tmp))
        state = {"first_write": None, "held": 0.0}
        with h.app.app_context():
            engine = h.db.engine

            @event.listens_for(engine, "before_cursor_execute")
            def _first_write(_c, _cur, statement, *_rest):
                verb = statement.lstrip().split(" ", 1)[0].upper()
                if state["first_write"] is None and verb in {"INSERT", "UPDATE", "DELETE"}:
                    state["first_write"] = time.perf_counter()

            def _released(_conn):
                if state["first_write"] is not None:
                    state["held"] += time.perf_counter() - state["first_write"]
                    state["first_write"] = None

            event.listen(engine, "commit", _released)
            event.listen(engine, "rollback", _released)

        original_call = h.call
        holds = defaultdict(list)

        def call(kind, method, url, student, body=None, log=None):
            state["first_write"], state["held"] = None, 0.0
            result = original_call(kind, method, url, student, body, log)
            holds[kind].append((state["held"], result["elapsed_s"], result["backlog_calls"]))
            return result

        h.call = call
        try:
            student = h.seed_student(args.backlog, "context")
            flow.run_entry_and_learning(h, student)
        finally:
            h.close()

    rows = []
    for kind, values in holds.items():
        held = [v[0] for v in values]
        rows.append({
            "request": kind,
            "count": len(values),
            "median_request_ms": round(statistics.median(v[1] for v in values) * 1000, 1),
            "median_write_lock_held_ms": round(statistics.median(held) * 1000, 1),
            "max_write_lock_held_ms": round(max(held) * 1000, 1),
            "backlog_scans_per_request": round(statistics.mean(v[2] for v in values), 2),
        })
    report = {"synthetic_only": True, "due_backlog_words": args.backlog, "requests": rows}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
