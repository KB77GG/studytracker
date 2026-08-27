"""Repeatable local benchmark for the vocabulary review pipeline.

This benchmark intentionally uses synthetic, non-student data.  It is kept in
the repository so the same database shape and workload can be run before and
after a performance change:

    .venv/bin/python scripts/benchmark_vocabulary_review.py \
        --output docs/vocabulary-performance-before.json

The script never connects to a production database and never writes outside
the requested output path.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from sqlalchemy import event

from models import (
    DictationBook,
    DictationWord,
    StudentProfile,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularySense,
    db,
)
from services.vocabulary_autonomous_review import (
    MAX_REVIEW_BATCH,
    _due_candidates,
    claim_today_review,
    review_preflight,
    review_summary,
)

BENCHMARK_NOW = datetime(2026, 8, 27, 12, 0, 0)
SCALES = (0, 1, 20, 50, 100, 300, 1000)


def _make_app() -> Flask:
    app = Flask("vocabulary-review-benchmark")
    app.config.update(
        SECRET_KEY="local-vocabulary-review-benchmark",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    login_manager = LoginManager(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    return app


def _timed_call(fn):
    query_count = 0
    statements = []

    def before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal query_count
        query_count += 1
        if len(statements) < 20:
            statements.append(" ".join(statement.split())[:240])

    engine = db.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    started = time.perf_counter()
    try:
        value = fn()
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return value, elapsed_ms, query_count, statements


def _seed(student_count: int):
    teacher = User(
        username="benchmark-teacher",
        password_hash="benchmark",
        role=User.ROLE_TEACHER,
        is_active=True,
    )
    student = User(
        username="benchmark-student",
        password_hash="benchmark",
        role=User.ROLE_STUDENT,
        is_active=True,
    )
    db.session.add_all([teacher, student])
    db.session.flush()
    db.session.add(StudentProfile(user_id=student.id, full_name="仿真学生"))
    book = DictationBook(
        title="仿真词书",
        word_count=student_count,
        created_by=teacher.id,
        is_active=True,
        default_vocabulary_goal="reading",
    )
    db.session.add(book)
    db.session.flush()

    senses = [
        VocabularySense(
            canonical_key=f"benchmark-sense-{index}",
            lemma=f"benchmarkword{index}",
            meaning_zh=f"仿真释义{index}",
        )
        for index in range(student_count)
    ]
    db.session.add_all(senses)
    db.session.flush()
    words = [
        DictationWord(
            book_id=book.id,
            sense_id=sense.id,
            sequence=index + 1,
            word=f"benchmarkword{index}",
            translation=f"仿真释义{index}",
            core_meaning_zh=f"仿真释义{index}",
            example_en=f"Students use benchmarkword{index} in class.",
            example_zh=f"学生在课堂使用仿真释义{index}。",
            usage_pattern=f"use benchmarkword{index} in class",
        )
        for index, sense in enumerate(senses)
    ]
    db.session.add_all(words)
    db.session.flush()
    masteries = [
        StudentVocabularyMastery(
            student_id=student.id,
            sense_id=sense.id,
            representative_word_id=word.id,
            representative_book_id=book.id,
            meaning_recall_stage=1,
            meaning_recall_next_due_at=BENCHMARK_NOW - timedelta(days=1),
            form_recall_stage=1,
            form_recall_next_due_at=BENCHMARK_NOW + timedelta(days=1),
            audio_form_recall_stage=1,
            audio_form_recall_next_due_at=BENCHMARK_NOW + timedelta(days=1),
            context_use_stage=1,
            context_use_next_due_at=BENCHMARK_NOW + timedelta(days=1),
        )
        for sense, word in zip(senses, words, strict=True)
    ]
    db.session.add_all(masteries)
    task = Task(
        date=date(2026, 8, 27),
        student_name="仿真学生",
        category="词汇",
        detail="性能仿真任务",
        created_by=teacher.id,
        dictation_book_id=book.id,
        vocabulary_goal="reading",
        dictation_word_start=1,
        dictation_word_end=max(1, student_count),
        status="pending",
    )
    db.session.add(task)
    db.session.commit()
    return db.session.get(User, student.id), db.session.get(Task, task.id)


def _response_bytes(payload: dict) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _run_scale(app: Flask, scale: int) -> dict:
    with app.app_context():
        db.drop_all()
        db.create_all()
        user, task = _seed(scale)
        raw_mastery_count = StudentVocabularyMastery.query.filter_by(student_id=user.id).count()

        due, due_ms, due_queries, due_statements = _timed_call(
            lambda: _due_candidates(user, BENCHMARK_NOW)
        )
        summary, summary_ms, summary_queries, _ = _timed_call(
            lambda: review_summary(user, now=BENCHMARK_NOW)
        )
        preflight, preflight_ms, preflight_queries, _ = _timed_call(
            lambda: review_preflight(user, task.id, now=BENCHMARK_NOW)
        )
        claim, claim_ms, claim_queries, _ = _timed_call(
            lambda: claim_today_review(user, origin_task_id=task.id, now=BENCHMARK_NOW)
        )
        serialized = _response_bytes(claim)
        first_set_data = {
            "loading": False,
            "empty": bool(claim.get("empty")),
            "sessionId": claim.get("session_id"),
            "sessionToken": claim.get("session_token", ""),
            "queueToken": claim.get("queue_token", ""),
            "currentIndex": 0,
            "totalCount": int(claim.get("total_count", 0)),
            "currentItem": (claim.get("items") or [None])[0],
        }
        return {
            "scale": scale,
            "raw_mastery_count": raw_mastery_count,
            "due_candidate_count": len(due),
            "skipped_count": max(0, raw_mastery_count - len(due)),
            "batch_limit": MAX_REVIEW_BATCH,
            "actual_batch_count": int(claim.get("total_count", 0)),
            "due_count": int(claim.get("due_count", 0)),
            "remaining_due_count": int(claim.get("remaining_due_count", 0)),
            "claim": {
                "elapsed_ms": round(claim_ms, 3),
                "query_count": claim_queries,
                "response_bytes": serialized,
                "first_set_data_bytes": _response_bytes(first_set_data),
            },
            "due_candidates": {
                "elapsed_ms": round(due_ms, 3),
                "query_count": due_queries,
                "sampled_sql": due_statements,
            },
            "summary": {
                "elapsed_ms": round(summary_ms, 3),
                "query_count": summary_queries,
                "response_bytes": _response_bytes(summary),
            },
            "preflight": {
                "elapsed_ms": round(preflight_ms, 3),
                "query_count": preflight_queries,
                "response_bytes": _response_bytes(preflight),
            },
            "client_proxy": {
                "returned_items": len(claim.get("items", [])),
                "first_set_data_items": 1 if first_set_data["currentItem"] else 0,
                "first_set_data_bytes": _response_bytes(first_set_data),
                "current_item_update_bytes": _response_bytes(
                    {"currentIndex": 1, "currentItem": (claim.get("items") or [None])[0]}
                ),
                "legacy_whole_batch_rewrite_bytes": _response_bytes(
                    {"items": claim.get("items", []), "currentIndex": 1}
                ),
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    app = _make_app()
    with app.app_context():
        results = [_run_scale(app, scale) for scale in SCALES]
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "environment": "synthetic sqlite in-memory; no production data",
        "now": BENCHMARK_NOW.isoformat(),
        "scales": list(SCALES),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
