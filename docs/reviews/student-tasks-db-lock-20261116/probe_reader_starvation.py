"""Synthetic-only check: can a *pure-read* request fail with "database is locked"?

Hypothesis under test (not a production finding): with one gunicorn process and
six threads, a CPU-bound Python request makes every other thread wait for the GIL
after each SQLite row step.  A large SELECT therefore keeps its SHARED lock for
seconds; a writer that then commits sits in PENDING, and in rollback-journal mode
PENDING blocks every new reader until the 5 s pysqlite busy timeout expires.

Actors, all on a throwaway SQLite file with invented data:
  hog     - pure Python loop (stands in for any CPU-heavy request)
  big     - GET task-history for a synthetic student with many completed tasks
  writer  - separate connection: BEGIN IMMEDIATE, UPDATE, COMMIT (5 s timeout)
  readers - GET task-history / tasks/today (tokens present) for a tiny student,
            arriving at several offsets after the writer
The writer is either a raw connection or the real tasks/today handler
back-filling a missing token (``writer_kind``).

Usage: python -B probe_reader_starvation.py --repo . --output probe-starvation.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_task_endpoints as base  # noqa: E402


def _hog(stop: threading.Event) -> None:
    while not stop.is_set():
        sum(i * i for i in range(20000))


def _writer(db_path, out: dict) -> None:
    raw = sqlite3.connect(db_path, isolation_level=None, timeout=5)
    raw.execute("BEGIN IMMEDIATE")
    raw.execute("UPDATE synthetic_lock_holder SET n = n + 1 WHERE id = 1")
    started = time.perf_counter()
    try:
        raw.execute("COMMIT")
        out["outcome"] = "committed"
    except sqlite3.OperationalError as error:
        out["outcome"] = str(error)
        raw.execute("ROLLBACK")
    out["commit_elapsed_s"] = round(time.perf_counter() - started, 3)
    raw.close()


def run_case(h: base.Harness, big: dict, small: dict, with_hog: bool, app_writer: dict | None = None) -> dict:
    """``app_writer``: a synthetic student whose today task lacks a token, so the
    real tasks/today handler is the committing writer instead of a raw connection."""

    today = h.today()
    results: dict = {"with_cpu_bound_thread": with_hog, "writer_kind": "app_backfill_get" if app_writer else "raw"}
    stop = threading.Event()
    hog = threading.Thread(target=_hog, args=(stop,), daemon=True)
    if with_hog:
        hog.start()
        time.sleep(0.2)

    def timed(key, url, student):
        results[key] = base._slim(h.get(student, url))

    writer_out: dict = {}
    big_thread = threading.Thread(target=timed, args=("big_history", "/api/miniprogram/student/task-history", big))
    if app_writer:
        writer_thread = threading.Thread(target=timed, args=("writer", h.today_url(today), app_writer))
    else:
        writer_thread = threading.Thread(target=_writer, args=(h.db_path, writer_out))
    # Pure-read requests arriving at different moments after the writer starts.
    offsets = (0.4, 0.8, 1.5, 3.0) if with_hog else (0.02,)
    readers = []
    for offset in offsets:
        readers.append((offset, threading.Thread(
            target=timed,
            args=(f"reader_history_t+{offset}", "/api/miniprogram/student/task-history?summary_only=1", small))))
        readers.append((offset, threading.Thread(
            target=timed, args=(f"reader_today_t+{offset}", h.today_url(today), small))))

    h.take_log()
    big_thread.start()
    time.sleep(0.6 if with_hog else 0.02)   # big SELECT is mid-fetch
    writer_thread.start()
    writer_started = time.perf_counter()
    for offset, thread in readers:
        delay = offset - (time.perf_counter() - writer_started)
        if delay > 0:
            time.sleep(delay)
        thread.start()
    for thread in [big_thread, writer_thread] + [t for _, t in readers]:
        thread.join(timeout=240)
    stop.set()
    if with_hog:
        hog.join(timeout=10)
    if not app_writer:
        results["writer"] = writer_out
    log_text = h.take_log()
    results["lock_tracebacks_logged"] = log_text.count("sqlalchemy.exc.OperationalError")
    results["pure_read_requests_failed"] = sum(
        1 for key, value in results.items() if key.startswith("reader_") and value["status"] != 200)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output")
    parser.add_argument("--big-history", type=int, default=3000)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    report = {
        "synthetic_only": True,
        "hypothesis_test_not_production_evidence": True,
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "switch_interval_s": sys.getswitchinterval(),
        "big_history_tasks": args.big_history,
        "modes": {},
    }
    with tempfile.TemporaryDirectory(prefix="studytracker-starvation-probe-") as tmp:
        for journal_mode in ("delete", "wal"):
            h = base.Harness(repo, journal_mode, Path(tmp))
            big = h.new_student()
            base._seed_history(h, big, args.big_history)
            small = h.new_student()
            today = h.today()
            h.add_task(small, today, category="雅思-听力-精听", listening_resource_type="intensive",
                       listening_exercise_id="synthetic_intensive_s", listening_access_token="synthetic-s")
            h.add_task(small, today - base.timedelta(days=1), status="done", accuracy=80)
            with h.foreign_lock("reserved"):
                pass  # creates the lock-holder table used by the writer
            cases = {
                "control": run_case(h, big, small, with_hog=False),
                "contended_raw_writer": run_case(h, big, small, with_hog=True),
            }
            for label, hog_on in (("control_app_writer", False), ("contended_app_writer", True)):
                writer_student = h.new_student()
                h.add_task(writer_student, today, category="雅思-听力-精听", listening_resource_type="intensive",
                           listening_exercise_id="synthetic_intensive_w")
                cases[label] = run_case(h, big, small, with_hog=hog_on, app_writer=writer_student)
            report["modes"][journal_mode] = cases
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
