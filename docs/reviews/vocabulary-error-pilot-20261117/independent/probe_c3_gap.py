"""Local synthetic C3 gap probe; no app/config import or production connection."""

import json
import platform
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from sqlalchemy import insert  # noqa: E402

from models import DictationWord, StudentVocabularyMastery, VocabularySense, db  # noqa: E402
from services import vocabulary_autonomous_review as review  # noqa: E402
from services.vocabulary_group_learning import get_vocabulary_group_queue  # noqa: E402
from services.vocabulary_mastery import ensure_mastery  # noqa: E402
from tests.test_vocabulary_error_review_integration import ErrorReviewIntegrationTest  # noqa: E402

state = {"active": False, "sql": [], "rows": 0, "first_write": None}


class CountingCursor(sqlite3.Cursor):
    def execute(self, sql, *args):
        if state["active"]:
            state["sql"].append(sql)
            if state["first_write"] is None and sql.lstrip().split()[0].upper() in {
                "INSERT", "UPDATE", "DELETE"
            }:
                state["first_write"] = perf_counter()
        return super().execute(sql, *args)

    def executemany(self, sql, *args):
        if state["active"]:
            state["sql"].append(sql)
            if state["first_write"] is None:
                state["first_write"] = perf_counter()
        return super().executemany(sql, *args)

    def fetchone(self):
        row = super().fetchone()
        if state["active"]:
            state["rows"] += int(row is not None)
        return row

    def fetchmany(self, *args):
        rows = super().fetchmany(*args)
        if state["active"]:
            state["rows"] += len(rows)
        return rows

    def fetchall(self):
        rows = super().fetchall()
        if state["active"]:
            state["rows"] += len(rows)
        return rows


class CountingConnection(sqlite3.Connection):
    def cursor(self, *args, **kwargs):
        kwargs["factory"] = CountingCursor
        return super().cursor(*args, **kwargs)


original_connect = sqlite3.dbapi2.connect


def connect(*args, **kwargs):
    kwargs["factory"] = CountingConnection
    return original_connect(*args, **kwargs)


def measure(label, call):
    state.update(active=True, sql=[], rows=0, first_write=None)
    started = perf_counter()
    try:
        value = call()
        db.session.commit()
        finished = perf_counter()
    finally:
        state["active"] = False
    return value, {
        "path": label,
        "sql_statements": len(state["sql"]),
        "fetched_rows": state["rows"],
        "legacy_mastery_statements": sum("student_vocabulary_mastery" in sql.lower() for sql in state["sql"]),
        "elapsed_ms": round((finished - started) * 1000, 3),
        "first_dml_to_commit_ms": round((finished - state["first_write"]) * 1000, 3) if state["first_write"] else 0,
    }


def dispose(fixture):
    with fixture.app.app_context():
        engine = db.engine
    fixture.tearDown()
    engine.dispose()


def history_case(size):
    fixture = ErrorReviewIntegrationTest()
    fixture.setUp()
    metrics = []
    try:
        with fixture.app.app_context():
            user = fixture._enable()
            # Keep ten current error abilities fixed; vary unrelated legacy
            # mastery history only. Remove the fixture's initial old pool.
            StudentVocabularyMastery.query.delete(synchronize_session=False)
            if size:
                db.session.execute(insert(VocabularySense), [
                    {"id": 10000 + n, "canonical_key": f"c3-history-{n}", "lemma": f"history{n}"}
                    for n in range(size)
                ])
                db.session.execute(insert(StudentVocabularyMastery), [
                    {"student_id": user.id, "sense_id": 10000 + n,
                     "meaning_recall_next_due_at": fixture.now - timedelta(days=30)}
                    for n in range(size)
                ])
            db.session.commit()
            for word in DictationWord.query.order_by(DictationWord.id).limit(10).all():
                ensure_mastery(user, word, db.session.get(VocabularySense, word.sense_id))
                fixture._error(user, word)

            def record(label, call):
                value, result = measure(label, call)
                metrics.append(result)
                return value

            record("summary", lambda: review.review_summary(user, now=fixture.now))
            record("task_preflight", lambda: review.review_preflight(user, fixture.task_id, now=fixture.now))
            payload = record("claim_10", lambda: review.claim_today_review(user, now=fixture.now))
            assert payload["total_count"] == 10
            from models import VocabularyReviewSession
            session = db.session.get(VocabularyReviewSession, payload["session_id"])
            items = list(session.items)
            record("first_correct_answer", lambda: fixture._answer(user, session, items[0]))
            for item in items[1:]:
                fixture._answer(user, session, item)
            record("settle_10", lambda: fixture._settle(user, session))
            record("task_queue_first", lambda: get_vocabulary_group_queue(user, fixture.task_id, now=fixture.now))
            record("task_queue_existing", lambda: get_vocabulary_group_queue(user, fixture.task_id, now=fixture.now))
            return {"unrelated_legacy_masteries": size, "current_error_abilities": 10, "metrics": metrics}
    finally:
        dispose(fixture)


def capacity_case(limit):
    fixture = ErrorReviewIntegrationTest()
    fixture.setUp()
    try:
        with fixture.app.app_context():
            user = fixture._enable()
            fixture.app.config["VOCABULARY_ERROR_REVIEW_DAILY_LIMIT"] = limit
            for word in DictationWord.query.order_by(DictationWord.id).all():
                fixture._error(user, word, "meaning_recall")
                fixture._error(user, word, "form_recall")
            payload = review.claim_today_review(user, now=fixture.now)
            result = {"daily_limit": limit, "available_error_abilities": 44,
                      "materialized_items": payload["total_count"], "batch_limit": payload["batch_limit"]}
            assert result["materialized_items"] == limit
            db.session.rollback()
            return result
    finally:
        dispose(fixture)


if __name__ == "__main__":
    with patch.object(sqlite3.dbapi2, "connect", side_effect=connect):
        histories = [history_case(size) for size in (0, 2400, 10000)]
        capacities = [capacity_case(limit) for limit in (20, 30, 40)]
    signatures = [[(row["path"], row["sql_statements"], row["fetched_rows"]) for row in sample["metrics"]]
                  for sample in histories]
    assert signatures[0] == signatures[1] == signatures[2]
    print(json.dumps({"python": platform.python_version(), "synthetic_only": True,
                      "database": "SQLite in-memory, one thread",
                      "history_sql_and_fetched_rows_equal": True,
                      "history_cases": histories, "capacity_cases": capacities}, indent=2))
