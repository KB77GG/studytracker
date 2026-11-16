"""Synthetic-only latency probe for the mini-program vocabulary learning flow.

Drives the real HTTP routes (queue -> familiarity -> answer ...) for invented
students on a throwaway SQLite file and records, per request kind, wall time,
SQL statement count and how much of the time is spent recomputing the student's
whole due-review backlog (``_due_candidates``).

Nothing here touches the project ``app.db``, a network or production.

Usage (cwd = repository under test):
    python -B docs/reviews/vocabulary-flow-latency-20261116/probe_vocabulary_flow.py \
        --repo . --backlogs 0,500,2400 --output <file.json>
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

GROUP_WORDS = 10


class Harness:
    def __init__(self, repo: Path, workdir: Path):
        import jwt
        from flask import Flask
        from flask_login import LoginManager
        from sqlalchemy import event

        from api.dictation import dictation_bp
        from api.miniprogram import mp_bp
        from api.vocab_review import vocab_review_bp
        from models import User, db
        from services import vocabulary_autonomous_review as review

        self.jwt, self.db, self.review = jwt, db, review
        self.db_path = workdir / f"synthetic-{time.time_ns()}.db"
        app = Flask(f"vocab-probe-{time.time_ns()}")
        app.config.update(
            SECRET_KEY="synthetic-vocab-probe",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{self.db_path}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            PROPAGATE_EXCEPTIONS=False,
        )
        db.init_app(app)
        login_manager = LoginManager(app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        for blueprint in (dictation_bp, mp_bp, vocab_review_bp):
            app.register_blueprint(blueprint)
        app.logger.disabled = True
        self.app = app
        self._local = threading.local()
        self.backlog_calls = defaultdict(list)  # thread id -> [seconds]
        with app.app_context():
            db.create_all()

            @event.listens_for(db.engine, "before_cursor_execute")
            def _count(*_args):
                self._local.sql = getattr(self._local, "sql", 0) + 1

        original = review._due_candidates

        def timed_due_candidates(*args, **kwargs):
            started = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                self._local.backlog = getattr(self._local, "backlog", 0.0) + time.perf_counter() - started
                self._local.backlog_calls = getattr(self._local, "backlog_calls", 0) + 1

        review._due_candidates = timed_due_candidates
        self._restore = lambda: setattr(review, "_due_candidates", original)
        self._n = 0

    def close(self):
        self._restore()

    def seed_student(self, backlog: int, due_dimension: str) -> dict:
        """One student, a backlog book with ``backlog`` due words, a fresh 10-word task."""

        from models import (
            DictationBook,
            DictationWord,
            StudentProfile,
            StudentVocabularyMastery,
            Task,
            User,
            VocabularySense,
        )
        from services.task_date_gate import beijing_today

        db = self.db
        self._n += 1
        n = self._n
        now = datetime.utcnow()
        with self.app.app_context():
            teacher = User(username=f"syn_teacher_{n}", password_hash="x", role=User.ROLE_TEACHER, is_active=True)
            student = User(username=f"syn_student_{n}", password_hash="x", role=User.ROLE_STUDENT, is_active=True)
            db.session.add_all([teacher, student])
            db.session.flush()
            name = f"合成背词学生{n}"
            db.session.add(StudentProfile(user_id=student.id, full_name=name))

            task_book = DictationBook(title=f"合成任务词书{n}", word_count=GROUP_WORDS, created_by=teacher.id, is_active=True)
            db.session.add(task_book)
            db.session.flush()
            db.session.add_all([
                DictationWord(
                    book_id=task_book.id, sequence=i + 1, word=f"taskword{n}x{i}",
                    translation=f"任务释义{n}的{i}", core_meaning_zh=f"任务释义{n}的{i}",
                    usage_pattern=f"use taskword{n}x{i} well",
                    example_en=f"Students use taskword{n}x{i} in class.",
                )
                for i in range(GROUP_WORDS)
            ])

            if backlog:
                book = DictationBook(title=f"合成积压词书{n}", word_count=backlog, created_by=teacher.id, is_active=True)
                db.session.add(book)
                db.session.flush()
                senses = [
                    VocabularySense(canonical_key=f"syn-{n}-{i}", lemma=f"backlog{n}x{i}", meaning_zh=f"积压释义{n}的{i}")
                    for i in range(backlog)
                ]
                db.session.add_all(senses)
                db.session.flush()
                words = [
                    DictationWord(
                        book_id=book.id, sense_id=sense.id, sequence=i + 1, word=f"backlog{n}x{i}",
                        translation=f"积压释义{n}的{i}", core_meaning_zh=f"积压释义{n}的{i}",
                        usage_pattern=f"use backlog{n}x{i} in class",
                        example_en=f"Students use backlog{n}x{i} in class.",
                    )
                    for i, sense in enumerate(senses)
                ]
                db.session.add_all(words)
                db.session.flush()
                later, earlier = now + timedelta(days=3), now - timedelta(days=1)
                db.session.add_all([
                    StudentVocabularyMastery(
                        student_id=student.id, sense_id=sense.id, representative_word_id=word.id,
                        representative_book_id=book.id,
                        meaning_recall_stage=1, form_recall_stage=1, audio_form_recall_stage=1, context_use_stage=1,
                        meaning_recall_next_due_at=earlier if due_dimension in {"meaning", "all"} else later,
                        form_recall_next_due_at=earlier if due_dimension == "all" else later,
                        audio_form_recall_next_due_at=earlier if due_dimension == "all" else later,
                        context_use_next_due_at=earlier if due_dimension in {"context", "all"} else later,
                    )
                    for sense, word in zip(senses, words, strict=True)
                ])
            task = Task(
                date=beijing_today(), student_name=name, category="词汇", detail="合成背词任务",
                created_by=teacher.id, dictation_book_id=task_book.id, vocabulary_goal="reading",
                dictation_word_start=1, dictation_word_end=GROUP_WORDS, status="pending",
            )
            db.session.add(task)
            db.session.commit()
            token = self.jwt.encode({"sub": str(student.id), "role": User.ROLE_STUDENT},
                                    "synthetic-vocab-probe", algorithm="HS256")
            return {"id": student.id, "task_id": task.id, "backlog": backlog,
                    "headers": {"Authorization": f"Bearer {token}"}}

    def call(self, kind: str, method: str, url: str, student: dict, body=None, log=None) -> dict:
        self._local.sql = 0
        self._local.backlog = 0.0
        self._local.backlog_calls = 0
        client = self.app.test_client()
        started = time.perf_counter()
        if method == "GET":
            response = client.get(url, headers=student["headers"])
        else:
            response = client.post(url, json=body, headers=student["headers"])
        elapsed = time.perf_counter() - started
        row = {
            "kind": kind, "status": response.status_code, "elapsed_s": elapsed,
            "backlog_s": self._local.backlog, "backlog_calls": self._local.backlog_calls,
            "sql": self._local.sql,
        }
        if log is not None:
            log.append(row)
        return dict(row, json=response.get_json(silent=True))

    def stored_answer(self, table: str, row_id: int):
        raw = sqlite3.connect(self.db_path, timeout=30)
        try:
            payload = raw.execute(f"SELECT answer_payload_json FROM {table} WHERE id=?", (row_id,)).fetchone()
        finally:
            raw.close()
        data = json.loads(payload[0]) if payload and payload[0] else {}
        return data.get("answer_option_id") or data.get("answer")


def run_entry_and_learning(h: Harness, student: dict, max_steps: int = 60) -> list[dict]:
    """What the mini-program does when a student opens a vocabulary task and studies."""

    log: list[dict] = []
    task_id = student["task_id"]
    base = f"/api/miniprogram/student/tasks/{task_id}"
    h.call("home: review summary", "GET", "/api/miniprogram/student/vocabulary-review/summary", student, log=log)
    gate = h.call("task page: preflight", "GET", f"{base}/vocabulary-review/preflight", student, log=log)["json"] or {}
    if gate.get("required"):
        session = h.call("review: claim batch", "GET",
                         f"/api/miniprogram/student/vocabulary-review/today?origin_task_id={task_id}", student, log=log)["json"]
        sid, token = session["session_id"], session["session_token"]
        for item in session["items"]:
            answer = h.stored_answer("vocabulary_review_item", item["review_item_id"])
            h.call("review: answer", "POST", f"/api/miniprogram/student/vocabulary-review/sessions/{sid}/answers", student, {
                "session_token": token, "review_item_id": item["review_item_id"],
                "question_id": item["question_id"], "word_id": item["word_id"], "sense_id": item["sense_id"],
                "dimension": item["dimension"], "answer": answer, "input_mode": "native",
                "attempt_id": f"syn-review:{sid}:{item['review_item_id']}",
            }, log=log)
        h.call("review: settle", "POST", f"/api/miniprogram/student/vocabulary-review/sessions/{sid}/settle", student,
               {"session_token": token, "queue_token": session.get("queue_token"), "duration_seconds": 0}, log=log)

    queue = h.call("learning: first queue (enter)", "GET", f"{base}/vocabulary-queue?supports_correction=1", student, log=log)["json"] or {}
    for step in range(max_steps):
        if not queue.get("ok"):
            break
        familiarity = [item for item in (queue.get("familiarity") or []) if not item.get("viewed")]
        question = queue.get("current_question")
        if queue.get("phase") == "familiarity" and familiarity:
            queue = h.call("learning: mark word viewed", "POST", f"{base}/vocabulary-learning/familiarity", student,
                           {"queue_token": queue["queue_token"], "word_id": familiarity[0]["word_id"]}, log=log)["json"] or {}
            continue
        if not question:
            break
        answer = h.stored_answer("vocabulary_learning_question", question["learning_question_id"])
        h.call("learning: submit answer", "POST", "/api/dictation/submit", student, {
            "task_id": task_id, "queue_token": queue["queue_token"],
            "learning_question_id": question["learning_question_id"], "queue_item_id": question["queue_item_id"],
            "question_id": question["question_id"], "word_id": question["word_id"], "sense_id": question["sense_id"],
            "dimension": question["dimension"], "answer": answer, "attempt_id": f"syn-learn:{task_id}:{step}",
            "retry": bool(queue.get("retry")),
            "input_mode": "strict" if question["mode"] in {"audio_to_en", "zh_to_en", "context_fill"} else "native",
        }, log=log)
        queue = h.call("learning: next queue", "GET", f"{base}/vocabulary-queue?supports_correction=1", student, log=log)["json"] or {}
    return log


def summarise(log: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in log:
        grouped[row["kind"]].append(row)
    out = []
    for kind, rows in grouped.items():
        elapsed = [r["elapsed_s"] for r in rows]
        backlog = [r["backlog_s"] for r in rows]
        out.append({
            "request": kind,
            "count": len(rows),
            "statuses": sorted({r["status"] for r in rows}),
            "median_ms": round(statistics.median(elapsed) * 1000, 1),
            "max_ms": round(max(elapsed) * 1000, 1),
            "backlog_recomputations_per_request": round(statistics.mean(r["backlog_calls"] for r in rows), 2),
            "share_of_time_in_backlog_recompute": round(sum(backlog) / sum(elapsed), 3) if sum(elapsed) else 0,
            "median_sql_statements": int(statistics.median(r["sql"] for r in rows)),
        })
    return out


def concurrent_entry(h: Harness, backlog: int, due_dimension: str, students: int) -> dict:
    """Several students open their vocabulary task at the same moment (one process, GIL)."""

    seeded = [h.seed_student(backlog, due_dimension) for _ in range(students)]
    for student in seeded:  # flows already started: the gate result cannot depend on the backlog
        run_entry_and_learning(h, student, max_steps=2)
    results = [None] * students
    barrier = threading.Barrier(students)

    def work(index, student):
        barrier.wait(timeout=30)
        results[index] = h.call("queue", "GET",
                                f"/api/miniprogram/student/tasks/{student['task_id']}/vocabulary-queue?supports_correction=1",
                                student)["elapsed_s"]

    threads = [threading.Thread(target=work, args=(i, s)) for i, s in enumerate(seeded)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=600)
    return {"students_at_once": students, "queue_get_median_ms": round(statistics.median(results) * 1000, 1),
            "queue_get_max_ms": round(max(results) * 1000, 1)}


def concurrent_first_open(h: Harness, backlog: int, due_dimension: str, students: int) -> dict:
    """Several students open a *new* vocabulary task at once: preflight, then claim a review batch."""

    seeded = [h.seed_student(backlog, due_dimension) for _ in range(students)]
    timings = {"preflight": [None] * students, "claim": [None] * students}
    barrier = threading.Barrier(students)

    def work(index, student):
        base = f"/api/miniprogram/student/tasks/{student['task_id']}"
        barrier.wait(timeout=30)
        timings["preflight"][index] = h.call("p", "GET", f"{base}/vocabulary-review/preflight", student)["elapsed_s"]
        timings["claim"][index] = h.call(
            "c", "GET", f"/api/miniprogram/student/vocabulary-review/today?origin_task_id={student['task_id']}",
            student)["elapsed_s"]

    threads = [threading.Thread(target=work, args=(i, s)) for i, s in enumerate(seeded)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=900)
    return {
        "students_at_once": students,
        "preflight_median_ms": round(statistics.median(timings["preflight"]) * 1000, 1),
        "preflight_max_ms": round(max(timings["preflight"]) * 1000, 1),
        "claim_batch_median_ms": round(statistics.median(timings["claim"]) * 1000, 1),
        "claim_batch_max_ms": round(max(timings["claim"]) * 1000, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--output")
    parser.add_argument("--backlogs", default="0,500,2400")
    parser.add_argument("--due-dimension", default="context", choices=["meaning", "context", "all"])
    parser.add_argument("--concurrency", default="1,3,6")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    report = {"synthetic_only": True, "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
              "due_dimension": args.due_dimension, "task_words": GROUP_WORDS, "flows": [], "concurrent_entry": [],
              "concurrent_first_open": []}
    with tempfile.TemporaryDirectory(prefix="studytracker-vocab-probe-") as tmp:
        h = Harness(repo, Path(tmp))
        try:
            for backlog in [int(v) for v in args.backlogs.split(",") if v != ""]:
                student = h.seed_student(backlog, args.due_dimension)
                log = run_entry_and_learning(h, student)
                learning = [r for r in log if r["kind"].startswith("learning")]
                report["flows"].append({
                    "due_backlog_words": backlog,
                    "requests": summarise(log),
                    "learning_requests": len(learning),
                    "learning_total_s": round(sum(r["elapsed_s"] for r in learning), 2),
                    "learning_time_in_backlog_recompute_s": round(sum(r["backlog_s"] for r in learning), 2),
                    "non_2xx": sum(1 for r in log if not 200 <= r["status"] < 300),
                })
            largest = max(int(v) for v in args.backlogs.split(",") if v != "")
            for students in [int(v) for v in args.concurrency.split(",") if v]:
                report["concurrent_entry"].append(dict(due_backlog_words=largest,
                                                       **concurrent_entry(h, largest, args.due_dimension, students)))
                report["concurrent_first_open"].append(dict(
                    due_backlog_words=largest, **concurrent_first_open(h, largest, args.due_dimension, students)))
        finally:
            h.close()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
