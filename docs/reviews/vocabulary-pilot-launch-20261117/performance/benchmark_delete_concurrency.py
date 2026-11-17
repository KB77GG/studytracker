"""Real HTTP routes, synthetic DELETE-journal SQLite, synchronized students.

No network server or production configuration. DML execute includes lock wait
and SQL execution; post-DML-to-commit is a lower bound on writer lock lifetime.
"""

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "synthetic_flow",
    ROOT / "docs/reviews/vocabulary-flow-latency-20261116/probe_vocabulary_flow.py",
)
FLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FLOW)
LOCAL = threading.local()


def record_finish(state, started, name):
    if state is None:
        return
    held = False
    for stamp, metric in (
        ("first_completed", "post_first_dml_to_finish_ms"),
        ("writer_begin_completed", "post_writer_begin_to_finish_ms"),
    ):
        if state[stamp] is not None:
            state[metric] += 1000 * (time.perf_counter() - state[stamp])
            state[stamp] = None
            held = True
    if held:
        state[name + "_ms"] += 1000 * (time.perf_counter() - started)
        state["first_started"] = None


class TracedCursor(sqlite3.Cursor):
    def _execute(self, function, sql, *args):
        state = getattr(LOCAL, "state", None)
        first = bool(
            state is not None
            and state["first_started"] is None
            and sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}
        )
        if first:
            state["first_started"] = time.perf_counter()
        immediate = state is not None and " ".join(sql.upper().split()).startswith(
            "BEGIN IMMEDIATE"
        )
        started = time.perf_counter()
        try:
            result = function(sql, *args)
            if first:
                state["first_completed"] = time.perf_counter()
            if immediate:
                state["writer_begin_completed"] = time.perf_counter()
            if not self.connection.in_transaction:
                record_finish(state, started, "implicit_finish")
            return result
        except sqlite3.Error as error:
            if state is not None:
                state["sqlite_errors"].append(str(error))
            raise
        finally:
            if first:
                state["first_dml_execute_ms"] += 1000 * (time.perf_counter() - started)
            if immediate:
                state["writer_begin_execute_ms"] += 1000 * (time.perf_counter() - started)

    def execute(self, sql, *args):
        return self._execute(super().execute, sql, *args)

    def executemany(self, sql, *args):
        return self._execute(super().executemany, sql, *args)

    def fetchone(self):
        row = super().fetchone()
        if getattr(LOCAL, "state", None) is not None:
            LOCAL.state["fetched_rows"] += int(row is not None)
        return row

    def fetchall(self):
        rows = super().fetchall()
        if getattr(LOCAL, "state", None) is not None:
            LOCAL.state["fetched_rows"] += len(rows)
        return rows

    def fetchmany(self, *args):
        rows = super().fetchmany(*args)
        if getattr(LOCAL, "state", None) is not None:
            LOCAL.state["fetched_rows"] += len(rows)
        return rows


class TracedConnection(sqlite3.Connection):
    def cursor(self, *args, **kwargs):
        kwargs["factory"] = TracedCursor
        return super().cursor(*args, **kwargs)

    def _finish(self, function, name):
        started = time.perf_counter()
        try:
            return function()
        finally:
            record_finish(getattr(LOCAL, "state", None), started, name)

    def commit(self):
        return self._finish(super().commit, "commit")

    def rollback(self):
        return self._finish(super().rollback, "rollback")


def measured_call(harness, kind, method, url, student, body):
    state = {
        "first_started": None,
        "first_completed": None,
        "writer_begin_completed": None,
        "writer_begin_execute_ms": 0,
        "post_writer_begin_to_finish_ms": 0,
        "first_dml_execute_ms": 0,
        "post_first_dml_to_finish_ms": 0,
        "commit_ms": 0,
        "rollback_ms": 0,
        "fetched_rows": 0,
        "implicit_finish_ms": 0,
        "sqlite_errors": [],
    }
    LOCAL.state = state
    try:
        result = harness.call(kind, method, url, student, body=body)
    finally:
        LOCAL.state = None
    row = {key: value for key, value in result.items() if key != "json"}
    row.update(
        {
            key: value
            for key, value in state.items()
            if key not in {"first_started", "first_completed", "writer_begin_completed"}
        }
    )
    row["error"] = (result["json"] or {}).get("error")
    return result["json"] or {}, row


def run_student(harness, student, barrier, records, failures, retry_limit):
    def call(kind, method, url, body=None):
        barrier.wait(timeout=120)
        for attempt in range(retry_limit + 1):
            payload, record = measured_call(harness, kind, method, url, student, body)
            record["attempt"] = attempt
            records.append(record)
            if record["status"] == 200 and payload.get("ok") is not False:
                return payload
            if record["status"] != 409 or attempt == retry_limit:
                raise RuntimeError(f"{kind}:{record['status']}:{record['error']}")
            time.sleep(0.02 * (attempt + 1))
        raise AssertionError("unreachable")

    try:
        task = f"/api/miniprogram/student/tasks/{student['task_id']}"
        call("home_summary", "GET", "/api/miniprogram/student/vocabulary-review/summary")
        gate = call("task_preflight", "GET", task + "/vocabulary-review/preflight")
        if not gate.get("required"):
            raise RuntimeError("synthetic_review_gate_missing")
        session = call(
            "review_claim_20",
            "GET",
            f"/api/miniprogram/student/vocabulary-review/today?origin_task_id={student['task_id']}",
        )
        if len(session.get("items", [])) != 20:
            raise RuntimeError("synthetic_review_batch_not_twenty")
        base = f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}"
        for item in session["items"]:
            answer = harness.stored_answer("vocabulary_review_item", item["review_item_id"])
            call(
                "review_answer",
                "POST",
                base + "/answers",
                {
                    "session_token": session["session_token"],
                    "review_item_id": item["review_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "sense_id": item["sense_id"],
                    "dimension": item["dimension"],
                    "answer": answer,
                    "input_mode": "native",
                    "attempt_id": f"benchmark-review:{session['session_id']}:{item['review_item_id']}",
                },
            )
        call(
            "review_settle_20",
            "POST",
            base + "/settle",
            {
                "session_token": session["session_token"],
                "queue_token": session["queue_token"],
                "duration_seconds": 0,
            },
        )
        queue = call(
            "learning_first_queue", "GET", task + "/vocabulary-queue?supports_correction=1"
        )
        for step in range(25):
            familiarity = [item for item in queue.get("familiarity", []) if not item.get("viewed")]
            if queue.get("phase") == "familiarity" and familiarity:
                queue = call(
                    "learning_familiarity",
                    "POST",
                    task + "/vocabulary-learning/familiarity",
                    {
                        "queue_token": queue["queue_token"],
                        "word_id": familiarity[0]["word_id"],
                    },
                )
                continue
            question = queue.get("current_question")
            if not question:
                raise RuntimeError("synthetic_learning_question_missing")
            answer = harness.stored_answer(
                "vocabulary_learning_question", question["learning_question_id"]
            )
            call(
                "learning_first_answer",
                "POST",
                "/api/dictation/submit",
                {
                    "task_id": student["task_id"],
                    "queue_token": queue["queue_token"],
                    "learning_question_id": question["learning_question_id"],
                    "queue_item_id": question["queue_item_id"],
                    "question_id": question["question_id"],
                    "word_id": question["word_id"],
                    "sense_id": question["sense_id"],
                    "dimension": question["dimension"],
                    "answer": answer,
                    "attempt_id": f"benchmark-learning:{student['task_id']}:{step}",
                    "retry": bool(queue.get("retry")),
                    "input_mode": (
                        "strict"
                        if question["mode"] in {"audio_to_en", "zh_to_en", "context_fill"}
                        else "native"
                    ),
                },
            )
            call("learning_next_queue", "GET", task + "/vocabulary-queue?supports_correction=1")
            return
        raise RuntimeError("synthetic_learning_step_limit")
    except BaseException as error:
        failures.append(str(error) or type(error).__name__)
        barrier.abort()


def seed_policy(harness, students, dimension):
    from models import StudentVocabularyMastery, User, db
    from services import vocabulary_error_queue as policy

    harness.app.config[policy.FEATURE_FLAG] = True
    now = datetime.utcnow()
    with harness.app.app_context():
        for student in students:
            user = db.session.get(User, student["id"])
            policy.enroll_student(user, starts_at=now - timedelta(days=2), now=now)
            words = (
                StudentVocabularyMastery.query.filter_by(student_id=user.id)
                .order_by(StudentVocabularyMastery.id)
                .limit(20)
                .all()
            )
            for row in words:
                policy.record_learning_answer(
                    user,
                    sense_id=row.sense_id,
                    dimension="context_use" if dimension == "context" else "meaning_recall",
                    correct=False,
                    source_key=f"benchmark-new-error:{row.id}",
                    word_id=row.representative_word_id,
                    now=now - timedelta(days=1),
                )
        db.session.commit()


def pad_task_books(harness, students, total):
    from sqlalchemy import insert

    from models import DictationBook, DictationWord, Task, db

    with harness.app.app_context():
        for number, student in enumerate(students):
            task = db.session.get(Task, student["task_id"])
            book = db.session.get(DictationBook, task.dictation_book_id)
            book.word_count = max(total, FLOW.GROUP_WORDS)
            if total > FLOW.GROUP_WORDS:
                db.session.execute(
                    insert(DictationWord),
                    [
                        {
                            "book_id": book.id,
                            "sequence": index + 1,
                            "word": f"extra{number}word{index}",
                            "translation": f"附加释义{number}的{index}",
                            "core_meaning_zh": f"附加释义{number}的{index}",
                            "usage_pattern": f"use extra{number}word{index} well",
                            "example_en": f"Students use extra{number}word{index} in class.",
                        }
                        for index in range(FLOW.GROUP_WORDS, total)
                    ],
                )
        db.session.commit()


def run_case(workdir, *, concurrency, dimension, enabled, backlog, retry_limit, task_book_size=10):
    from services.vocabulary_context_catalog import _parsed_lemma

    # Fresh fixture text repeats across cases; do not allow earlier cases to
    # turn a nominally cold catalog into a warm process-cache benchmark.
    _parsed_lemma.cache_clear()
    harness = FLOW.Harness(ROOT, workdir)
    barrier, threads = None, []
    try:
        with harness.app.app_context():
            connection = harness.db.session.connection()
            assert connection.exec_driver_sql("PRAGMA journal_mode=DELETE").scalar() == "delete"
            harness.db.session.commit()
        students = [harness.seed_student(backlog, dimension) for _ in range(concurrency)]
        if task_book_size > FLOW.GROUP_WORDS:
            pad_task_books(harness, students, task_book_size)
        seed_policy(harness, students, dimension)
        harness.app.config["VOCABULARY_ERROR_REVIEW_ENABLED"] = enabled
        records, failures = [], []
        barrier = threading.Barrier(concurrency)
        threads = [
            threading.Thread(
                target=run_student, args=(harness, student, barrier, records, failures, retry_limit)
            )
            for student in students
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=240)
        if any(thread.is_alive() for thread in threads):
            barrier.abort()
            raise RuntimeError("benchmark_thread_timeout")
        return {
            "enabled": enabled,
            "concurrency": concurrency,
            "dimension": dimension,
            "backlog_per_student": backlog,
            "new_error_abilities_per_student": 20,
            "task_words": FLOW.GROUP_WORDS,
            "task_book_size": task_book_size,
            "failures": failures,
            "requests": records,
        }
    except BaseException:
        if barrier is not None:
            barrier.abort()
        for thread in threads:
            thread.join(timeout=30)
        raise
    finally:
        harness.close()
        with harness.app.app_context():
            harness.db.session.remove()
            harness.db.engine.dispose()


def distribution(values):
    values = sorted(values)
    return {
        "n": len(values),
        "p50": round(statistics.median(values), 3),
        "p95": round(values[max(0, int(len(values) * 0.95 + 0.999999) - 1)], 3),
        "max": round(max(values), 3),
    }


def summarize(cases):
    groups = defaultdict(list)
    for case in cases:
        for row in case["requests"]:
            groups[(case["enabled"], case["concurrency"], case["dimension"], row["kind"])].append(
                row
            )
    output = []
    for (enabled, concurrency, dimension, kind), rows in sorted(groups.items()):
        output.append(
            {
                "enabled": enabled,
                "concurrency": concurrency,
                "dimension": dimension,
                "path": kind,
                "statuses": dict(Counter(row["status"] for row in rows)),
                "retries": sum(row["attempt"] > 0 for row in rows),
                "sqlite_errors": dict(
                    Counter(error for row in rows for error in row["sqlite_errors"])
                ),
                "wall_ms": distribution([1000 * row["elapsed_s"] for row in rows]),
                **{
                    key: distribution([row[key] for row in rows])
                    for key in (
                        "first_dml_execute_ms",
                        "post_first_dml_to_finish_ms",
                        "writer_begin_execute_ms",
                        "post_writer_begin_to_finish_ms",
                        "commit_ms",
                        "rollback_ms",
                        "implicit_finish_ms",
                        "sql",
                        "fetched_rows",
                    )
                },
            }
        )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--concurrency", default="1,3,6")
    parser.add_argument("--dimensions", default="meaning,context")
    parser.add_argument("--modes", default="off,on")
    parser.add_argument("--backlog", type=int, default=2400)
    parser.add_argument("--task-book-size", type=int, default=10)
    parser.add_argument("--retry-limit", type=int, default=4)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    product_paths = [
        "models.py",
        "services/vocabulary_error_queue.py",
        "services/vocabulary_error_review.py",
        "services/vocabulary_policy_planning.py",
        "services/vocabulary_autonomous_review.py",
        "services/vocabulary_group_learning.py",
        "services/vocabulary_mastery.py",
        "services/vocabulary_context.py",
        "services/vocabulary_context_catalog.py",
        "services/vocabulary_synonyms.py",
        "services/vocabulary_review_selection.py",
        "services/vocabulary_optional_selection.py",
        "dictation_answers.py",
    ]
    source_hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in product_paths
    }
    original_connect = sqlite3.dbapi2.connect

    def traced_connect(*values, **kwargs):
        kwargs["factory"] = TracedConnection
        return original_connect(*values, **kwargs)

    sqlite3.dbapi2.connect = traced_connect
    cases = []
    try:
        with tempfile.TemporaryDirectory(prefix="vocabulary-delete-probe-") as temporary:
            for iteration in range(args.rounds):
                for dimension in args.dimensions.split(","):
                    for concurrency in map(int, args.concurrency.split(",")):
                        for mode in args.modes.split(","):
                            case = run_case(
                                Path(temporary),
                                concurrency=concurrency,
                                dimension=dimension,
                                enabled=mode == "on",
                                backlog=args.backlog,
                                retry_limit=args.retry_limit,
                                task_book_size=args.task_book_size,
                            )
                            case["round"] = iteration + 1
                            cases.append(case)
                            print(
                                json.dumps(
                                    {
                                        "round": iteration + 1,
                                        "dimension": dimension,
                                        "concurrency": concurrency,
                                        "enabled": mode == "on",
                                        "requests": len(case["requests"]),
                                        "failures": case["failures"],
                                    }
                                ),
                                flush=True,
                            )
                            Path(args.output).write_text(
                                json.dumps(
                                    {
                                        "synthetic_only": True,
                                        "python": sys.version.split()[0],
                                        "sqlite": sqlite3.sqlite_version,
                                        "journal_mode": "delete",
                                        "source_hashes": source_hashes,
                                        "source_files_unchanged": all(
                                            hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                            == value
                                            for name, value in source_hashes.items()
                                        ),
                                        "cases": cases,
                                        "summary": summarize(cases),
                                    },
                                    indent=2,
                                )
                                + "\n"
                            )
    finally:
        sqlite3.dbapi2.connect = original_connect


if __name__ == "__main__":
    main()
