"""Synthetic-only lock/write probe for the student today-task and task-history APIs.

Everything here runs against a throwaway SQLite file in a temp directory with
invented students and tasks.  It never opens the project ``app.db``, never talks
to the network and must not be pointed at a production database.

The real ``api.miniprogram`` blueprint is mounted on a minimal Flask app (same
pattern as ``tests/test_miniprogram_task_visibility.py``) with **no engine
options**, i.e. the same pysqlite defaults ``config.Config`` gives production
(5 s busy timeout, QueuePool).  The journal mode is a parameter because the
production value is not recorded anywhere in the repository.

Usage (cwd = repository under test):
    python -B docs/reviews/student-tasks-db-lock-20261116/probe_task_endpoints.py \
        --repo . --output docs/reviews/student-tasks-db-lock-20261116/probe-main.json
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import re
import sqlite3
import sys
import tempfile
import threading
import time
from collections import Counter
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

THREADS = 6  # production gunicorn: workers=1, gthread, threads=6
STUDENT_NAME_PREFIX = "合成学生"
# Same pattern docs/reviews/miniprogram-entry-20261116/audit_logs.py applied to the journal.
AUDIT_ERROR_PATTERN = re.compile(
    r"\b(?:[A-Za-z]+Error|WORKER TIMEOUT|database is locked|database disk image is malformed)\b"
)


def _normalise_statement(statement: str) -> str:
    words = statement.strip().split()
    verb = words[0].upper() if words else ""
    if verb == "UPDATE" and len(words) > 1:
        return f"UPDATE {words[1]}"
    if verb in {"INSERT", "DELETE"} and len(words) > 2:
        return f"{verb} {words[2]}"
    return verb


class Harness:
    """One isolated app + database for a given journal mode."""

    def __init__(self, repo: Path, journal_mode: str, workdir: Path, variable_limit: int | None = None):
        import jwt
        from flask import Flask
        from sqlalchemy import event

        from api.miniprogram import mp_bp
        from models import db

        self.jwt = jwt
        self.db = db
        self.journal_mode = journal_mode
        self.db_path = workdir / f"synthetic-{journal_mode}-{time.time_ns()}.db"
        raw = sqlite3.connect(self.db_path)
        self.effective_journal_mode = raw.execute(f"PRAGMA journal_mode={journal_mode}").fetchone()[0]
        raw.close()

        app = Flask(f"probe-{journal_mode}-{time.time_ns()}")
        app.config.update(
            SECRET_KEY="synthetic-probe-secret",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{self.db_path}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=False,
            PROPAGATE_EXCEPTIONS=False,  # behave like production: unhandled error -> 500 page
        )
        db.init_app(app)
        app.register_blueprint(mp_bp)
        self.app = app

        self.log_stream = io.StringIO()
        handler = logging.StreamHandler(self.log_stream)
        app.logger.handlers[:] = [handler]
        app.logger.propagate = False

        self._dml: list[str] = []
        self._dml_lock = threading.Lock()
        with app.app_context():
            db.create_all()
            engine = db.engine
            self.pool_class = type(engine.pool).__name__

            if variable_limit is not None:
                @event.listens_for(engine, "connect")
                def _limit(dbapi_connection, _record):  # simulate an older SQLite build
                    dbapi_connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, variable_limit)

                engine.dispose()

            @event.listens_for(engine, "before_cursor_execute")
            def _record(_conn, _cursor, statement, _params, _context, _many):
                verb = statement.lstrip().split(" ", 1)[0].upper()
                if verb not in {"SELECT", "PRAGMA"}:
                    with self._dml_lock:
                        self._dml.append(_normalise_statement(statement))

        self._counter = 0

    # -- synthetic data ----------------------------------------------------
    def today(self):
        from services.task_date_gate import beijing_now

        return beijing_now().date()

    def new_student(self) -> dict:
        from models import StudentProfile, User

        self._counter += 1
        name = f"{STUDENT_NAME_PREFIX}{self._counter:04d}"
        with self.app.app_context():
            user = User(
                username=f"synthetic_student_{self._counter:04d}",
                password_hash="synthetic",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            self.db.session.add(user)
            self.db.session.flush()
            self.db.session.add(StudentProfile(user_id=user.id, full_name=name))
            self.db.session.commit()
            now = int(time.time())
            token = self.jwt.encode(
                {"sub": str(user.id), "role": user.role, "iat": now, "exp": now + 3600},
                "synthetic-probe-secret",
                algorithm="HS256",
            )
            return {"id": user.id, "name": name, "headers": {"Authorization": f"Bearer {token}"}}

    def add_task(self, student: dict, day, **fields) -> int:
        from models import Task

        defaults = dict(
            date=day.isoformat(),
            student_name=student["name"],
            category="课后作业",
            detail="synthetic",
            status="pending",
        )
        defaults.update(fields)
        with self.app.app_context():
            task = Task(**defaults)
            self.db.session.add(task)
            self.db.session.commit()
            return task.id

    def task_tokens(self, task_id: int) -> dict:
        row = self.raw_query(
            "SELECT listening_access_token, reading_access_token FROM task WHERE id=?", (task_id,)
        )[0]
        return {"listening": row[0], "reading": row[1]}

    def raw_query(self, sql: str, params=()):
        raw = sqlite3.connect(self.db_path, timeout=30)
        try:
            return raw.execute(sql, params).fetchall()
        finally:
            raw.close()

    # -- instrumentation ----------------------------------------------------
    def reset_dml(self):
        with self._dml_lock:
            self._dml.clear()

    def dml(self) -> dict:
        with self._dml_lock:
            return dict(Counter(self._dml))

    def take_log(self) -> str:
        text = self.log_stream.getvalue()
        self.log_stream.seek(0)
        self.log_stream.truncate()
        return text

    def get(self, student: dict, url: str) -> dict:
        started = time.perf_counter()
        response = self.app.test_client().get(url, headers=student["headers"])
        elapsed = time.perf_counter() - started
        payload = response.get_json(silent=True)
        return {
            "status": response.status_code,
            "bytes": len(response.get_data()),
            "content_type": response.content_type,
            "elapsed_s": round(elapsed, 3),
            "json": payload,
        }

    def today_url(self, day) -> str:
        return f"/api/miniprogram/student/tasks/today?date={day.isoformat()}"

    @contextmanager
    def foreign_lock(self, kind: str):
        """Another connection holds a SQLite lock, as a concurrent writer would."""

        raw = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False, timeout=30)
        raw.execute("CREATE TABLE IF NOT EXISTS synthetic_lock_holder (id INTEGER PRIMARY KEY, n INTEGER)")
        raw.execute("INSERT OR IGNORE INTO synthetic_lock_holder (id, n) VALUES (1, 0)")
        raw.execute("BEGIN IMMEDIATE" if kind == "reserved" else "BEGIN EXCLUSIVE")
        raw.execute("UPDATE synthetic_lock_holder SET n = n + 1 WHERE id = 1")
        try:
            yield
        finally:
            raw.execute("ROLLBACK")
            raw.close()

    @contextmanager
    def foreign_reader(self):
        """Another connection is still fetching a large SELECT (holds SHARED)."""

        raw = sqlite3.connect(self.db_path, timeout=30)
        cursor = raw.execute("SELECT id FROM task")
        cursor.fetchone()
        try:
            yield
        finally:
            cursor.close()
            raw.close()

    def idle_pooled_connections(self) -> int:
        with self.app.app_context():
            return self.db.engine.pool.checkedin()

    def checked_out(self) -> int:
        with self.app.app_context():
            return self.db.engine.pool.checkedout()

    def parallel(self, calls):
        results = [None] * len(calls)
        start = threading.Barrier(len(calls))

        def run(index, call):
            start.wait(timeout=30)
            try:
                results[index] = call()
            except Exception as error:  # pragma: no cover - reported, not hidden
                results[index] = {"status": "exception", "error": type(error).__name__}

        threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(calls)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=120)
        return results


def _slim(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "json"}


def _task_from(result: dict, task_id: int) -> dict | None:
    payload = result.get("json") or {}
    for item in payload.get("tasks") or []:
        if item.get("id") == task_id:
            return item
    return None


# --------------------------------------------------------------------------
def scenario_write_conditions(h: Harness) -> list[dict]:
    """Which GETs actually issue DML."""

    today = h.today()
    listening = dict(category="雅思-听力-精听", listening_resource_type="intensive",
                     listening_exercise_id="synthetic_intensive_1")
    cambridge = dict(category="雅思-听力", listening_resource_type="cambridge_test",
                     listening_exercise_id="synthetic_cambridge_1")
    reading = dict(category="雅思-阅读", reading_test_id="synthetic_reading_1")
    cases = [
        ("today_pending_listening_missing_token", today, today, dict(listening)),
        ("today_pending_listening_empty_string_token", today, today, dict(listening, listening_access_token="")),
        ("today_pending_reading_missing_token", today, today, dict(reading)),
        ("today_pending_listening_has_token", today, today, dict(listening, listening_access_token="synthetic-existing")),
        ("today_pending_plain_homework", today, today, {}),
        ("yesterday_done_cambridge_missing_token", today - timedelta(days=1), today - timedelta(days=1),
         dict(cambridge, status="done")),
        ("two_days_ago_pending_listening_missing_token", today - timedelta(days=2), today - timedelta(days=2),
         dict(listening)),
        ("tomorrow_pending_listening_missing_token", today + timedelta(days=1), today + timedelta(days=1),
         dict(listening)),
        ("outside_window_listening_missing_token", today - timedelta(days=5), today - timedelta(days=5),
         dict(listening)),
        ("date_without_tasks", today, None, {}),
    ]
    rows = []
    for name, query_day, task_day, fields in cases:
        student = h.new_student()
        task_id = h.add_task(student, task_day, **fields) if task_day else None
        h.reset_dml()
        result = h.get(student, h.today_url(query_day))
        dml = h.dml()
        item = _task_from(result, task_id) if task_id else None
        rows.append({
            "case": name,
            "endpoint": "tasks/today",
            "status": result["status"],
            "dml": dml,
            "wrote": bool(dml),
            "task_date_state": item.get("task_date_state") if item else None,
            "token_returned": bool(item and (item.get("listening_token") or item.get("reading_token"))),
        })

    # The single-task detail GET shares the same lazy backfill.
    student = h.new_student()
    task_id = h.add_task(student, today, **listening)
    h.reset_dml()
    result = h.get(student, f"/api/miniprogram/student/tasks/{task_id}")
    rows.append({
        "case": "detail_today_pending_listening_missing_token",
        "endpoint": "tasks/:id",
        "status": result["status"],
        "dml": h.dml(),
        "wrote": bool(h.dml()),
    })

    student = h.new_student()
    h.add_task(student, today - timedelta(days=1), status="done", accuracy=80, actual_seconds=600)
    h.reset_dml()
    result = h.get(student, "/api/miniprogram/student/task-history")
    rows.append({
        "case": "history_with_completed_task",
        "endpoint": "task-history",
        "status": result["status"],
        "dml": h.dml(),
        "wrote": bool(h.dml()),
    })
    return rows


def _race_round(h: Harness, forced: bool) -> dict:
    import api.miniprogram as mp

    today = h.today()
    student = h.new_student()
    task_id = h.add_task(
        student, today, category="雅思-听力", listening_resource_type="cambridge_test",
        listening_exercise_id="synthetic_cambridge_race",
    )
    original = mp.secrets.token_urlsafe
    barrier = threading.Barrier(THREADS)

    def delayed(nbytes=None):
        # Every request has already read "token missing" before any of them commits.
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
        return original(nbytes)

    calls = [lambda: h.get(student, h.today_url(today)) for _ in range(THREADS)]
    h.reset_dml()
    if forced:
        with patch.object(mp.secrets, "token_urlsafe", side_effect=delayed):
            results = h.parallel(calls)
    else:
        results = h.parallel(calls)
    stored = h.task_tokens(task_id)["listening"]
    returned = [(_task_from(r, task_id) or {}).get("listening_token") for r in results]
    return {
        "student": student,
        "task_id": task_id,
        "statuses": dict(Counter(str(r["status"]) for r in results)),
        "distinct_tokens_returned": len({t for t in returned if t}),
        "responses_with_token_not_in_db": sum(1 for t in returned if t and t != stored),
        "responses_without_token": sum(1 for t in returned if not t),
        "stored_token_present": bool(stored),
        "update_statements": h.dml().get("UPDATE task", 0),
        "_returned": returned,
        "_stored": stored,
    }


def scenario_concurrent_missing_token(h: Harness, natural_rounds: int) -> dict:
    forced = _race_round(h, forced=True)
    stale = next((t for t in forced["_returned"] if t and t != forced["_stored"]), None)
    use = {}
    base = f"/api/miniprogram/student/listening/cambridge/{forced['task_id']}?token="
    if stale:
        use["stale_token_status"] = h.get(forced["student"], base + stale)["status"]
    if forced["_stored"]:
        use["stored_token_status"] = h.get(forced["student"], base + forced["_stored"])["status"]

    natural = Counter()
    natural_non_200 = 0
    for _ in range(natural_rounds):
        outcome = _race_round(h, forced=False)
        natural["rounds"] += 1
        if outcome["distinct_tokens_returned"] > 1:
            natural["rounds_with_divergent_tokens"] += 1
        if outcome["responses_with_token_not_in_db"]:
            natural["rounds_with_stale_token_response"] += 1
        natural_non_200 += sum(v for k, v in outcome["statuses"].items() if k != "200")
    public = {k: v for k, v in forced.items() if not k.startswith("_") and k != "student"}
    return {
        "threads": THREADS,
        "forced_interleave": public,
        "token_use_after_forced_race": use,
        "natural_interleave": dict(natural, non_200_responses=natural_non_200),
    }


def scenario_existing_token_reads(h: Harness) -> dict:
    today = h.today()
    student = h.new_student()
    task_id = h.add_task(
        student, today, category="雅思-听力-精听", listening_resource_type="intensive",
        listening_exercise_id="synthetic_intensive_2", listening_access_token="synthetic-stable-token",
    )
    h.add_task(student, today, category="雅思-阅读", reading_test_id="synthetic_reading_2",
               reading_access_token="synthetic-stable-reading")
    watcher = sqlite3.connect(h.db_path, timeout=30)
    version_before = watcher.execute("PRAGMA data_version").fetchone()[0]
    h.reset_dml()
    sequential = [h.get(student, h.today_url(today)) for _ in range(30)]
    concurrent = []
    for _ in range(10):
        concurrent.extend(h.parallel([lambda: h.get(student, h.today_url(today)) for _ in range(THREADS)]))
    version_after = watcher.execute("PRAGMA data_version").fetchone()[0]
    watcher.close()
    everything = sequential + concurrent
    tokens = {(_task_from(r, task_id) or {}).get("listening_token") for r in everything}
    out = {
        "requests": len(everything),
        "statuses": dict(Counter(str(r["status"]) for r in everything)),
        "dml": h.dml(),
        "distinct_tokens": sorted(t for t in tokens if t),
        "sqlite_data_version_changed": version_before != version_after,
    }
    for kind in ("reserved", "exclusive"):
        h.take_log()
        with h.foreign_lock(kind):
            out[f"under_foreign_{kind}_lock"] = _slim(h.get(student, h.today_url(today)))
    return out


def scenario_missing_token_under_write_lock(h: Harness) -> dict:
    today = h.today()
    student = h.new_student()
    task_id = h.add_task(
        student, today, category="雅思-听力-精听", listening_resource_type="intensive",
        listening_exercise_id="synthetic_intensive_3",
    )
    complete_day = today - timedelta(days=1)
    h.add_task(student, complete_day, category="雅思-阅读", reading_test_id="synthetic_reading_3",
               reading_access_token="synthetic-complete", status="done", accuracy=90)
    out = {}
    h.take_log()
    h.reset_dml()
    with h.foreign_lock("reserved"):
        failed = h.get(student, h.today_url(today))
        log_text = h.take_log()
        out["backfill_request_during_lock"] = _slim(failed)
        out["audit_regex_matches_for_this_one_500"] = dict(Counter(AUDIT_ERROR_PATTERN.findall(log_text)))
        out["logged_exception_summary"] = sorted({
            line.split(":", 1)[0].strip()
            for line in log_text.splitlines()
            if "OperationalError" in line and not line.startswith(" ")
        })
        out["stored_token_after_failure"] = h.task_tokens(task_id)["listening"]
        out["pool_connections_checked_out_after_failure"] = h.checked_out()
        out["same_lock_today_date_with_complete_tokens"] = _slim(h.get(student, h.today_url(complete_day)))
        out["same_lock_history"] = _slim(h.get(student, "/api/miniprogram/student/task-history?summary_only=1"))
        detail = h.get(student, f"/api/miniprogram/student/tasks/{task_id}")
        body = json.dumps(detail.get("json") or {}, ensure_ascii=False)
        out["same_lock_detail_endpoint"] = dict(
            _slim(detail),
            error_body_exposes_sql_text="UPDATE task" in body,
            error_body_exposes_bound_parameters="[parameters:" in body,
        )
        h.take_log()
    out["dml_attempted_during_lock"] = h.dml()
    h.reset_dml()
    first = h.get(student, h.today_url(today))
    second = h.get(student, h.today_url(today))
    token_first = (_task_from(first, task_id) or {}).get("listening_token")
    token_second = (_task_from(second, task_id) or {}).get("listening_token")
    out["after_lock_released"] = {
        "first_status": first["status"],
        "second_status": second["status"],
        "token_backfilled": bool(token_first),
        "token_stable_across_reads": bool(token_first) and token_first == token_second,
        "stored_matches_returned": h.task_tokens(task_id)["listening"] == token_first,
        "dml": h.dml(),
    }
    return out


def scenario_failed_commit_aftermath(h: Harness) -> dict:
    """The back-fill COMMIT itself fails because a reader outlives the busy timeout.

    Afterwards the slow reader is gone, so nothing should be locked any more.
    """

    today = h.today()
    bystander = h.new_student()
    h.add_task(bystander, today - timedelta(days=1), status="done", accuracy=80, actual_seconds=300)
    h.add_task(bystander, today, category="雅思-听力-精听", listening_resource_type="intensive",
               listening_exercise_id="synthetic_intensive_b", listening_access_token="synthetic-b")
    trigger = h.new_student()
    task_id = h.add_task(trigger, today, category="雅思-听力-精听", listening_resource_type="intensive",
                         listening_exercise_id="synthetic_intensive_t")
    history_url = "/api/miniprogram/student/task-history?summary_only=1"
    h.parallel([lambda: h.get(bystander, history_url) for _ in range(THREADS)])  # warm the pool
    out = {"idle_pooled_connections_before": h.idle_pooled_connections()}
    h.take_log()
    with h.foreign_reader():
        triggering = h.get(trigger, h.today_url(today))
    out["backfill_request_while_reader_active"] = dict(
        _slim(triggering),
        tasks_returned=len((triggering.get("json") or {}).get("tasks") or []),
    )
    out["audit_regex_matches_for_trigger"] = dict(Counter(AUDIT_ERROR_PATTERN.findall(h.take_log())))
    followups = []
    for index in range(8):
        url = history_url if index % 2 == 0 else h.today_url(today)
        result = h.get(bystander, url)
        followups.append({
            "n": index + 1,
            "endpoint": "task-history" if index % 2 == 0 else "tasks/today",
            "status": result["status"],
            "bytes": result["bytes"],
            "elapsed_s": result["elapsed_s"],
        })
    out["pure_read_requests_after_reader_left"] = followups
    out["pure_read_failures_after_reader_left"] = sum(1 for row in followups if row["status"] != 200)
    out["audit_regex_matches_for_followups"] = dict(Counter(AUDIT_ERROR_PATTERN.findall(h.take_log())))
    out["token_of_failed_request_stored_afterwards"] = bool(h.task_tokens(task_id)["listening"])
    retry = h.get(trigger, h.today_url(today))
    out["trigger_retry"] = {
        "status": retry["status"],
        "token_returned": bool((_task_from(retry, task_id) or {}).get("listening_token")),
    }
    return out


def scenario_any_handler_failed_commit(h: Harness) -> dict:
    """Stand-in for any other handler that commits and lets the error propagate.

    Only the app-context teardown (scoped_session.remove()) cleans up, exactly as
    for a real request.  Shows whether today/history become collateral damage.
    """

    from sqlalchemy import text

    today = h.today()
    bystander = h.new_student()
    h.add_task(bystander, today - timedelta(days=1), status="done", accuracy=80, actual_seconds=300)
    h.add_task(bystander, today, category="雅思-听力-精听", listening_resource_type="intensive",
               listening_exercise_id="synthetic_intensive_c", listening_access_token="synthetic-c")
    history_url = "/api/miniprogram/student/task-history?summary_only=1"
    with h.foreign_lock("reserved"):
        pass  # make sure the lock-holder table exists
    h.parallel([lambda: h.get(bystander, history_url) for _ in range(THREADS)])
    out = {"idle_pooled_connections_before": h.idle_pooled_connections()}
    with h.foreign_reader():
        with h.app.app_context():
            h.db.session.execute(text("UPDATE synthetic_lock_holder SET n = n + 1 WHERE id = 1"))
            try:
                h.db.session.commit()
                out["other_handler_commit"] = "ok"
            except Exception as error:
                out["other_handler_commit"] = str(getattr(error, "orig", error))
    followups = []
    for index in range(8):
        url = history_url if index % 2 == 0 else h.today_url(today)
        result = h.get(bystander, url)
        followups.append({
            "n": index + 1,
            "endpoint": "task-history" if index % 2 == 0 else "tasks/today",
            "status": result["status"],
            "bytes": result["bytes"],
            "elapsed_s": result["elapsed_s"],
        })
    h.take_log()
    out["pure_read_requests_after_reader_left"] = followups
    out["pure_read_failures_after_reader_left"] = sum(1 for row in followups if row["status"] != 200)
    return out


def _seed_history(h: Harness, student: dict, count: int) -> None:
    from models import ListeningTestSubmission, ReadingTestSubmission, Task

    today = h.today()
    blob = json.dumps([
        {"ids": [str(n)], "numbers": [n], "q": str(n), "answer": "synthetic", "value": "synthetic",
         "marks": 1, "awarded": n % 2, "correct": bool(n % 2), "section": 0}
        for n in range(1, 41)
    ])
    with h.app.app_context():
        tasks = [
            Task(
                date=(today - timedelta(days=1 + index // 6)).isoformat(),
                student_name=student["name"], category="雅思-听力" if index % 2 else "雅思-阅读",
                detail=f"synthetic {index}", status="done", accuracy=75, actual_seconds=900,
                listening_exercise_id="synthetic_cambridge_h" if index % 2 else None,
                listening_resource_type="cambridge_test" if index % 2 else None,
                listening_access_token="synthetic-h" if index % 2 else None,
                reading_test_id=None if index % 2 else "synthetic_reading_h",
                reading_access_token=None if index % 2 else "synthetic-h",
            )
            for index in range(count)
        ]
        h.db.session.add_all(tasks)
        h.db.session.flush()
        for index, task in enumerate(tasks):
            common = dict(task_id=task.id, student_name=student["name"], correct_count=30, total_count=40,
                          accuracy=75, completion_rate=100, answers_json=blob, results_json=blob,
                          wrong_numbers_json=json.dumps(list(range(1, 11))))
            if index % 2:
                h.db.session.add(ListeningTestSubmission(
                    test_id="synthetic_cambridge_h", test_title="Synthetic Listening", **common))
            else:
                h.db.session.add(ReadingTestSubmission(
                    test_id="synthetic_reading_h", test_title="Synthetic Reading", **common))
        h.db.session.commit()


def scenario_history(h: Harness, sizes: list[int]) -> dict:
    out = {"scaling": []}
    student = None
    for size in sizes:
        student = h.new_student()
        _seed_history(h, student, size)
        h.reset_dml()
        summary = h.get(student, "/api/miniprogram/student/task-history?summary_only=1")
        full = h.get(student, "/api/miniprogram/student/task-history")
        out["scaling"].append({
            "completed_tasks": size,
            "summary_only_status": summary["status"],
            "summary_only_elapsed_s": summary["elapsed_s"],
            "summary_only_bytes": summary["bytes"],
            "full_status": full["status"],
            "full_elapsed_s": full["elapsed_s"],
            "full_bytes": full["bytes"],
            "summary_total": ((summary.get("json") or {}).get("summary") or {}).get("total"),
            "summary_wrong_tasks": ((summary.get("json") or {}).get("summary") or {}).get("wrong_tasks"),
            "dml": h.dml(),
        })
    h.reset_dml()
    concurrent = []
    for _ in range(5):
        concurrent.extend(h.parallel([
            lambda: h.get(student, "/api/miniprogram/student/task-history?summary_only=1")
            for _ in range(THREADS)
        ]))
    out["concurrent_reads"] = {
        "requests": len(concurrent),
        "statuses": dict(Counter(str(r["status"]) for r in concurrent)),
        "dml": h.dml(),
    }
    for kind in ("reserved", "exclusive"):
        h.take_log()
        with h.foreign_lock(kind):
            result = h.get(student, "/api/miniprogram/student/task-history?summary_only=1")
        log_text = h.take_log()
        out[f"under_foreign_{kind}_lock"] = dict(
            _slim(result),
            audit_regex_matches=dict(Counter(AUDIT_ERROR_PATTERN.findall(log_text))),
        )
    return out


def scenario_history_variable_limit(repo: Path, workdir: Path, journal_mode: str) -> dict:
    """What an SQLite build with the pre-3.32 default (999 bound variables) would do."""

    h = Harness(repo, journal_mode, workdir, variable_limit=999)
    rows = []
    for size in (999, 1000):
        student = h.new_student()
        _seed_history(h, student, size)
        h.take_log()
        result = h.get(student, "/api/miniprogram/student/task-history?summary_only=1")
        log_text = h.take_log()
        rows.append({
            "completed_tasks": size,
            "status": result["status"],
            "bytes": result["bytes"],
            "too_many_sql_variables_logged": "too many SQL variables" in log_text,
            "audit_regex_matches": dict(Counter(AUDIT_ERROR_PATTERN.findall(log_text))),
        })
    return {"simulated_variable_limit": 999, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output")
    parser.add_argument("--natural-rounds", type=int, default=100)
    parser.add_argument("--history-sizes", default="200,1000,3000")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    from importlib.metadata import version

    import sqlalchemy
    from werkzeug.exceptions import InternalServerError

    report = {
        "synthetic_only": True,
        "repo": str(repo),
        "versions": {
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
            "sqlalchemy": sqlalchemy.__version__,
            "flask": version("flask"),
            "werkzeug": version("werkzeug"),
            "flask_sqlalchemy": version("flask_sqlalchemy"),
        },
        "werkzeug_default_500_body_bytes": len(InternalServerError().get_body().encode()),
        "engine_options": "none (pysqlite defaults, as config.Config)",
        "modes": {},
    }
    sizes = [int(part) for part in args.history_sizes.split(",") if part]
    with tempfile.TemporaryDirectory(prefix="studytracker-lock-probe-") as tmp:
        workdir = Path(tmp)
        for journal_mode in ("delete", "wal"):
            h = Harness(repo, journal_mode, workdir)
            report["modes"][journal_mode] = {
                "effective_journal_mode": h.effective_journal_mode,
                "pool_class": h.pool_class,
                "write_conditions": scenario_write_conditions(h),
                "concurrent_missing_token": scenario_concurrent_missing_token(h, args.natural_rounds),
                "existing_token_reads": scenario_existing_token_reads(h),
                "missing_token_under_write_lock": scenario_missing_token_under_write_lock(h),
                "history": scenario_history(h, sizes),
                "failed_commit_aftermath": scenario_failed_commit_aftermath(h),
                "any_handler_failed_commit": scenario_any_handler_failed_commit(h),
            }
        report["history_variable_limit"] = scenario_history_variable_limit(repo, workdir, "delete")
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
