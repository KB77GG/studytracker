"""Local synthetic timing only; never connects to a production database."""

import json
import platform
import statistics
from datetime import timedelta
from time import perf_counter

from sqlalchemy import event, insert
from test_policy_edges import IndependentPolicyEdges

from models import StudentVocabularyMastery, VocabularyErrorQueue, VocabularySense, db
from services import vocabulary_autonomous_review as review
from services import vocabulary_error_queue as policy


def run():
    fixture = IndependentPolicyEdges()
    fixture.setUp()
    observations = []
    try:
        with fixture.app.app_context():
            user = fixture.enable()
            cohort = policy._cohort(policy.enabled_for(user, fixture.now))
            previous = 0
            for size in (0, 5000, 20000):
                if size > previous:
                    db.session.execute(
                        insert(VocabularySense),
                        [
                            {
                                "id": 10000 + n,
                                "canonical_key": f"scale-probe-{n}",
                                "lemma": f"scale{n}",
                            }
                            for n in range(previous, size)
                        ],
                    )
                    db.session.execute(
                        insert(StudentVocabularyMastery),
                        [
                            {
                                "student_id": user.id,
                                "sense_id": 10000 + n,
                                "meaning_recall_next_due_at": fixture.now - timedelta(days=30),
                            }
                            for n in range(previous, size)
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
                                "status": "maintenance",
                                "opened_at": fixture.now,
                                "due_local_date": policy.local_date(fixture.now)
                                - timedelta(days=30),
                            }
                            for n in range(previous, size)
                        ],
                    )
                    db.session.commit()
                # Warm statement compilation; this does not cache policy counts.
                review.review_summary(user, now=fixture.now)
                statements = []

                def capture(_conn, _cursor, sql, _params, _ctx, _many, captured=statements):
                    captured.append(sql.lower())

                event.listen(db.engine, "before_cursor_execute", capture)
                samples = []
                try:
                    for _ in range(25):
                        started = perf_counter()
                        result = review.review_summary(user, now=fixture.now)
                        samples.append(1000 * (perf_counter() - started))
                        assert result["due_count"] == 0
                finally:
                    event.remove(db.engine, "before_cursor_execute", capture)
                observations.append(
                    {
                        "additional_legacy_masteries": size,
                        "maintenance_queue_rows": size,
                        "repetitions": len(samples),
                        "median_ms": round(statistics.median(samples), 3),
                        "p95_ms": round(sorted(samples)[23], 3),
                        "sql_per_call": len(statements) / 25,
                        "legacy_mastery_queries": sum(
                            "student_vocabulary_mastery" in sql for sql in statements
                        ),
                    }
                )
                previous = size
    finally:
        fixture.tearDown()
    return {
        "python": platform.python_version(),
        "database": "synthetic in-memory SQLite",
        "observations": observations,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
