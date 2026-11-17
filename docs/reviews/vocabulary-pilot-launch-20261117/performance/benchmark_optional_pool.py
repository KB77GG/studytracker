"""Synthetic optional-pool cost; no production/app server or real identities."""

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "delete_probe", Path(__file__).with_name("benchmark_delete_concurrency.py")
)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


def seed_blocked(harness, students, *, partial=False):
    from sqlalchemy import insert

    from models import StudentVocabularyMastery, User, VocabularyErrorQueue, db
    from services import vocabulary_error_queue as policy

    now = datetime.utcnow()
    later = policy.local_date(now) + timedelta(days=7)
    with harness.app.app_context():
        for student in students:
            user = db.session.get(User, student["id"])
            enrollment = policy.enabled_for(user, now)
            existing = VocabularyErrorQueue.query.filter_by(student_id=user.id).all()
            existing_senses = {row.sense_id for row in existing}
            for row in existing:
                row.status = "paused"
                row.due_local_date = later
                row.pause_until_local_date = later
                if partial:
                    row.dimension = "meaning_recall"
            rows = StudentVocabularyMastery.query.filter_by(student_id=user.id).all()
            if partial:
                for row in rows:
                    row.meaning_recall_next_due_at = now - timedelta(days=30)
                    row.form_recall_next_due_at = now - timedelta(days=1)
                    row.context_use_next_due_at = now + timedelta(days=3)
            db.session.execute(
                insert(VocabularyErrorQueue),
                [
                    {
                        "student_id": user.id,
                        "sense_id": row.sense_id,
                        "dimension": "meaning_recall" if partial else "context_use",
                        "cohort_key": policy._cohort(enrollment),
                        "representative_word_id": row.representative_word_id,
                        "status": "paused",
                        "due_local_date": later,
                        "pause_until_local_date": later,
                        "opened_at": now,
                    }
                    for row in rows
                    if row.sense_id not in existing_senses
                ],
            )
        db.session.commit()


def run_case(workdir, concurrency, backlog, blocked):
    from services.vocabulary_context_catalog import _parsed_lemma
    from services.vocabulary_optional_selection import _simple_eligible

    _parsed_lemma.cache_clear()
    _simple_eligible.cache_clear()
    harness = PROBE.FLOW.Harness(PROBE.ROOT, workdir)
    barrier = threading.Barrier(concurrency)
    threads = []
    records, failures = [], []
    try:
        with harness.app.app_context():
            assert (
                harness.db.session.connection()
                .exec_driver_sql("PRAGMA journal_mode=DELETE")
                .scalar()
                == "delete"
            )
            harness.db.session.commit()
        students = [harness.seed_student(backlog, "context") for _ in range(concurrency)]
        PROBE.seed_policy(harness, students, "context")
        if blocked:
            seed_blocked(harness, students, partial=blocked == "partial")

        def request(student):
            try:
                barrier.wait(timeout=120)
                payload, row = PROBE.measured_call(
                    harness,
                    (
                        "optional_partially_blocked"
                        if blocked == "partial"
                        else ("optional_all_blocked" if blocked else "optional_available_ten")
                    ),
                    "GET",
                    "/api/miniprogram/student/vocabulary-review/today?mode=maintenance",
                    student,
                    None,
                )
                row["attempt"] = 0
                row["items"] = len(payload.get("items", []))
                records.append(row)
                if row["status"] != 200 or row["items"] != (0 if blocked else 10):
                    failures.append(f"unexpected_optional_result:{row['status']}:{row['items']}")
            except BaseException as error:
                failures.append(str(error) or type(error).__name__)
                barrier.abort()

        threads = [threading.Thread(target=request, args=(student,)) for student in students]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=240)
        if any(thread.is_alive() for thread in threads):
            raise RuntimeError("optional_thread_timeout")
        return {
            "enabled": True,
            "dimension": "context",
            "concurrency": concurrency,
            "backlog_per_student": backlog,
            "blocked": blocked,
            "failures": failures,
            "requests": records,
        }
    finally:
        barrier.abort()
        for thread in threads:
            thread.join(timeout=30)
        harness.close()
        with harness.app.app_context():
            harness.db.session.remove()
            harness.db.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--concurrency", default="1,6")
    parser.add_argument("--backlog", type=int, default=2400)
    parser.add_argument("--scenarios", default="available,blocked")
    args = parser.parse_args()
    source_paths = [
        PROBE.ROOT / "models.py",
        *sorted((PROBE.ROOT / "services").glob("vocabulary*.py")),
    ]
    source_hashes = {
        str(path.relative_to(PROBE.ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    }
    original = sqlite3.dbapi2.connect

    def connect(*values, **kwargs):
        return original(*values, **dict(kwargs, factory=PROBE.TracedConnection))

    sqlite3.dbapi2.connect = connect
    cases = []
    try:
        with tempfile.TemporaryDirectory(prefix="optional-vocabulary-probe-") as temporary:
            for iteration in range(args.rounds):
                for concurrency in map(int, args.concurrency.split(",")):
                    for scenario in args.scenarios.split(","):
                        if scenario not in {"available", "blocked", "partial"}:
                            raise ValueError("invalid_scenario")
                        blocked = "partial" if scenario == "partial" else scenario == "blocked"
                        case = run_case(Path(temporary), concurrency, args.backlog, blocked)
                        case["round"] = iteration + 1
                        cases.append(case)
                        print(
                            json.dumps(
                                {key: value for key, value in case.items() if key != "requests"}
                            ),
                            flush=True,
                        )
                        Path(args.output).write_text(
                            json.dumps(
                                {
                                    "synthetic_only": True,
                                    "python": sys.version.split()[0],
                                    "journal_mode": "delete",
                                    "source_hashes": source_hashes,
                                    "source_files_unchanged": all(
                                        hashlib.sha256((PROBE.ROOT / name).read_bytes()).hexdigest()
                                        == digest
                                        for name, digest in source_hashes.items()
                                    ),
                                    "cases": cases,
                                    "summary": PROBE.summarize(cases),
                                },
                                indent=2,
                            )
                            + "\n"
                        )
    finally:
        sqlite3.dbapi2.connect = original


if __name__ == "__main__":
    main()
