#!/usr/bin/env python3
"""Export identity-free pilot metrics using a bounded, read-only SQLite connection."""

import argparse
import json
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import vocabulary_pilot_metrics as metrics  # noqa: E402


@contextmanager
def readonly(database):
    path = Path(database).resolve(strict=True)
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.25)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        # One consistent read snapshot across queue/event/checkpoint queries.
        connection.execute("BEGIN")
        deadline = time.monotonic() + 10
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 5000)

        def authorize(action, table, column, _database, _source):
            allowed = action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE)
            if action == sqlite3.SQLITE_READ:
                allowed = table in metrics.READ_COLUMNS and (
                    column in metrics.READ_COLUMNS[table] or column == ""
                )
            return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        yield connection
        if connection.total_changes:
            raise metrics.MetricsError("read_only_violation")
    finally:
        connection.close()


def evaluate(database, *, student_ids=None, as_of=None, week=None):
    with readonly(database) as connection:

        def execute(sql, params):
            return [dict(row) for row in connection.execute(sql, params)]

        now = metrics.utc_time(as_of)
        rows = metrics.load_rows(execute, student_ids=student_ids, as_of=now)
    # The materialized rows form the consistent snapshot. Release SQLite's
    # read transaction before pure aggregation so reporting cannot prolong
    # a writer's wait while formatting historical metrics.
    return metrics.aggregate(rows, as_of=now, week=week)["summary"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--students", nargs="*", type=int)
    parser.add_argument("--as-of", help="UTC ISO timestamp; default current UTC")
    parser.add_argument("--week", help="Any YYYY-MM-DD date in the reporting week")
    args = parser.parse_args(argv)
    try:
        result = evaluate(
            args.database, student_ids=args.students, as_of=args.as_of, week=args.week
        )
    except (OSError, ValueError, sqlite3.Error):
        # Never echo a database path, SQL, student ID, or database contents.
        print(json.dumps({"ok": False, "error": "pilot_metrics_unavailable"}))
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
