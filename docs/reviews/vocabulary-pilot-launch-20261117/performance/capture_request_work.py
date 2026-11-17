"""Reproduce the formal C3 test's actual DBAPI SQL/row observations."""

import argparse
import json
import platform
import sqlite3
import sys
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from tests.test_vocabulary_policy_performance import CountingConnection, PolicyPerformanceTest
from tests import test_vocabulary_error_review_integration as fixtures
from models import DictationWord, VocabularyErrorQueue, VocabularySense, db
from sqlalchemy import insert
from services import vocabulary_autonomous_review as review
from services import vocabulary_error_queue as policy


def new_queue_case(size):
    fixture = fixtures.ErrorReviewIntegrationTest()
    fixture.setUp()
    observations = []
    times = {}
    try:
        with fixture.app.app_context():
            user = fixture._enable()
            for word in DictationWord.query.all():
                fixture._error(user, word)
            if size:
                cohort = policy._cohort(policy.enabled_for(user, fixture.now))
                db.session.execute(
                    insert(VocabularySense),
                    [
                        {"id": 10000 + n, "canonical_key": f"scale-{n}", "lemma": f"scale{n}"}
                        for n in range(size)
                    ],
                )
                db.session.execute(
                    insert(VocabularyErrorQueue),
                    [
                        {
                            "student_id": user.id,
                            "sense_id": 10000 + n,
                            "dimension": "meaning_recall",
                            "cohort_key": cohort,
                            "status": "active",
                            "due_local_date": policy.local_date(fixture.now) - timedelta(days=10),
                            "opened_at": fixture.now - timedelta(days=11),
                        }
                        for n in range(size)
                    ],
                )
                db.session.commit()
            for label, function in (
                ("summary", lambda: review.review_summary(user, now=fixture.now)),
                ("claim", lambda: review.claim_today_review(user, now=fixture.now)),
            ):
                started = time.perf_counter()
                PolicyPerformanceTest().measure(label, function, observations)
                times[label] = round(1000 * (time.perf_counter() - started), 3)
            return {
                "observations": observations,
                "wall_ms": times,
                "cleanup_rows_persisted": VocabularyErrorQueue.query.filter_by(
                    status="maintenance"
                ).count(),
            }
    finally:
        fixture.tearDown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    connect = sqlite3.dbapi2.connect

    def counted(*positional, **keywords):
        return connect(*positional, **dict(keywords, factory=CountingConnection))

    with patch.object(sqlite3.dbapi2, "connect", side_effect=counted):
        result = {
            str(size): PolicyPerformanceTest().history_case(size) for size in (0, 2400, 10000)
        }
        new_queue = {str(size): new_queue_case(size) for size in (0, 2400, 10000)}
    output = {
        "python": platform.python_version(),
        "synthetic_only": True,
        "measurement": "Every DBAPI execute/executemany and fetchone/fetchmany/fetchall row, including commit; fixture setup excluded",
        "old_history_definition": "additional old mastery/sense rows; current target words/catalog fixed",
        "columns": ["request", "sql_calls", "fetched_rows"],
        "all_three_equal": result["0"] == result["2400"] == result["10000"],
        "request_count": len(result["0"]),
        "observations": result,
        "new_queue_scale": new_queue,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    if not output["all_three_equal"]:
        raise SystemExit("C3 work-growth assertion failed")
    print(json.dumps({key: output[key] for key in ("python", "all_three_equal", "request_count")}))


if __name__ == "__main__":
    main()
