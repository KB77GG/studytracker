"""Synthetic in-memory forgotten-answer -> due-review bridge; no production access.

Run from the repository root with the project's Python environment. This uses
the existing unittest fixture and commits each answer to model the API boundary.
No Flask application/configuration or persistent student database is imported.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from models import (  # noqa: E402
    DictationRecord,
    StudentVocabularyMastery,
    Task,
    VocabularyTaskSettlement,
    db,
)
from services.vocabulary_autonomous_review import claim_today_review  # noqa: E402
from services.vocabulary_group_learning import (  # noqa: E402
    finalize_vocabulary_group_task,
    get_vocabulary_group_queue,
)
from tests.test_vocabulary_group_learning import VocabularyGroupLearningTest  # noqa: E402


def run_case(goal: str, *, finalize: bool) -> dict:
    fixture = VocabularyGroupLearningTest()
    fixture.setUp()
    try:
        with fixture.app.app_context():
            user = fixture._user()
            now = datetime(2026, 11, 14, 10)
            task = fixture._task(goal, end=3, task_date=now.date())
            task_id = task.id
            queue = get_vocabulary_group_queue(user, task_id, now=now)
            steps = []
            while not queue["completed"]:
                queue = fixture._view_group(user, task_id, queue, now=now)
                question = queue["current_question"]
                assert question is not None
                response = fixture._answer_for_current(
                    user, task_id, queue, now=now, response_kind="forgot"
                )
                assert response["revealed_answer"]
                assert response["response_kind"] == "forgot"
                assert response["is_correct"] is False
                assert response["correction_required"] is False
                db.session.commit()
                steps.append((queue["phase"], question["dimension"]))
                assert len(steps) < 50
                queue = get_vocabulary_group_queue(user, task_id, now=now)

            # Verify the last answer already persisted its due schedule before
            # the separate completion/finalization action has ever happened.
            db.session.commit()
            db.session.expire_all()
            user = fixture._user()
            assert VocabularyTaskSettlement.query.filter_by(task_id=task_id).count() == 0
            assert not db.session.get(Task, task_id).student_submitted
            masteries = StudentVocabularyMastery.query.filter_by(student_id=user.id).all()
            assert len(masteries) == 3
            due_dimensions = []
            for mastery in masteries:
                scheduled = {
                    dimension: getattr(mastery, f"{dimension}_next_due_at")
                    for dimension in StudentVocabularyMastery.DIMENSIONS
                    if getattr(mastery, f"{dimension}_next_due_at") is not None
                }
                assert scheduled
                assert all(due == now + timedelta(days=1) for due in scheduled.values())
                due_dimensions.append(sorted(scheduled))

            settlement = None
            if finalize:
                settlement = finalize_vocabulary_group_task(
                    user, task_id, {"queue_token": queue["queue_token"]}, now=now
                )
                assert settlement["accuracy"] == 0
                assert settlement["correct_count"] == 0
                db.session.commit()
            assert VocabularyTaskSettlement.query.filter_by(task_id=task_id).count() == int(
                finalize
            )
            records = DictationRecord.query.filter_by(task_id=task_id).all()
            assert len(records) == len(steps)
            assert all(row.response_kind == "forgot" and not row.is_correct for row in records)

            same_day = claim_today_review(user, now=now)
            assert same_day["empty"]
            before_due = claim_today_review(user, now=now + timedelta(days=1, seconds=-1))
            assert before_due["empty"]
            at_due = claim_today_review(user, now=now + timedelta(days=1))
            assert at_due["total_count"] == 3
            assert len({row["sense_id"] for row in at_due["items"]}) == 3
            return {
                "goal": goal,
                "finalized": finalize,
                "answers": len(steps),
                "retry_answers": sum(phase == "retry" for phase, _dimension in steps),
                "all_results_have_revealed_answer": True,
                "all_forgot_responses_are_wrong": True,
                "all_forgot_responses_omit_immediate_correction": True,
                "persisted_before_finalize": True,
                "due_dimensions_by_synthetic_word": due_dimensions,
                "scheduled_at": now.isoformat() + "Z",
                "next_due_at": (now + timedelta(days=1)).isoformat() + "Z",
                "before_24h_review_empty": True,
                "exact_24h_review_count": at_due["total_count"],
                "review_dimensions": [row["dimension"] for row in at_due["items"]],
                "settled_accuracy": settlement["accuracy"] if settlement else None,
                "settlement_count": int(finalize),
            }
    finally:
        fixture.tearDown()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = {
        "ok": True,
        "database": "sqlite:///:memory:",
        "clock": "controlled UTC; 24 elapsed hours, not next calendar midnight",
        "cases": [
            run_case(goal, finalize=finalize)
            for goal in ("reading", "listening", "writing", "comprehensive")
            for finalize in (True, False)
        ],
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
