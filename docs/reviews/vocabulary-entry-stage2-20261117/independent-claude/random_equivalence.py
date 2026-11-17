"""Independent randomized check of the stage-two selection against the legacy scan.

Synthetic in-memory SQLite only.  For each random data set it compares:
  * full candidate order (sense, word, dimension, stage, remediation kind, due time)
    from the legacy ``_due_candidates`` vs the new paged ``_iter_due_candidates``;
  * the exact-count membership ``_eligible_due_sense_ids`` vs the legacy senses;
  * ``_has_due`` vs "legacy list is non-empty";
  * the first 20 materialized questions (public snapshot + answer).

Usage (cwd = repository): python -B <this file> [--trials 300] [--seed 1]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--trials", type=int, default=300)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--output")
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.repo).resolve()))

    from flask import Flask

    from models import (
        DictationBook,
        DictationWord,
        StudentProfile,
        StudentVocabularyMastery,
        User,
        VocabularyReviewAttempt,
        VocabularyReviewItem,
        VocabularyReviewSession,
        VocabularySense,
        db,
    )
    from services import vocabulary_autonomous_review as review
    from services.dictation_review import local_date
    from services.vocabulary_mastery import DIMENSIONS

    app = Flask("independent-equivalence")
    app.config.update(SECRET_KEY="x", SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
                      SQLALCHEMY_TRACK_MODIFICATIONS=False)
    db.init_app(app)
    rng = random.Random(args.seed)
    now = datetime.utcnow().replace(microsecond=0)
    today = local_date(now)
    stats = {"trials": 0, "mismatches": [], "total_candidates": 0, "empty_trials": 0,
             "trials_with_remediation": 0, "trials_with_cooled": 0, "max_candidates": 0}

    def project(candidates):
        return [
            (c["mastery"].sense_id, c["word"].id, c["dimension"], c["stage"], c["remediation_kind"],
             c["due_at"].isoformat())
            for c in candidates
        ]

    with app.app_context():
        for trial in range(args.trials):
            db.session.remove()
            db.drop_all()
            db.create_all()
            teacher = User(username="t", password_hash="x", role=User.ROLE_TEACHER, is_active=True)
            student = User(username="s", password_hash="x", role=User.ROLE_STUDENT, is_active=True)
            other = User(username="o", password_hash="x", role=User.ROLE_STUDENT, is_active=True)
            db.session.add_all([teacher, student, other])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="合成对照学生"))
            books = [DictationBook(title=f"合成书{i}", word_count=0, created_by=teacher.id, is_active=True)
                     for i in range(rng.randint(1, 3))]
            db.session.add_all(books)
            db.session.flush()
            size = rng.choice([1, 5, 20, 40, 130, 260])  # crosses the 128-row page boundary
            # A handful of shared timestamps forces ties in every ordering key.
            past = [now - timedelta(days=d, hours=h) for d, h in [(0, 1), (1, 0), (1, 0), (3, 5), (9, 0)]]
            future = now + timedelta(days=2)
            masteries, words_by_sense = [], {}
            for index in range(size):
                sense = VocabularySense(canonical_key=f"k{trial}-{index}", lemma=f"word{index}",
                                        meaning_zh=f"义{index}")
                db.session.add(sense)
                db.session.flush()
                rows = []
                for _copy in range(rng.choice([1, 1, 1, 2])):
                    blank = rng.random() < 0.08          # cannot produce a meaning question
                    with_example = rng.random() < 0.7
                    word = DictationWord(
                        book_id=rng.choice(books).id, sense_id=sense.id, sequence=rng.randint(1, 40),
                        word=f"word{index}" if rng.random() > 0.03 else "",
                        translation="" if blank else f"义{index}",
                        core_meaning_zh="" if blank else f"义{index}",
                        usage_pattern=f"use word{index} well" if rng.random() < 0.5 else "",
                        example_en=f"Students use word{index} in class." if with_example else "",
                    )
                    db.session.add(word)
                    rows.append(word)
                db.session.flush()
                words_by_sense[sense.id] = rows
                mastery = StudentVocabularyMastery(
                    student_id=student.id if rng.random() > 0.05 else other.id, sense_id=sense.id,
                    representative_word_id=rng.choice(rows).id if rng.random() < 0.7 else None,
                    representative_book_id=rows[0].book_id,
                )
                for dimension in DIMENSIONS:
                    stage = rng.choice([0, 0, 1, 2, 3, 6])
                    setattr(mastery, f"{dimension}_stage", stage)
                    setattr(mastery, f"{dimension}_next_due_at",
                            rng.choice([None, future, *past, *past]))
                    setattr(mastery, f"{dimension}_last_answered_at", rng.choice([None, *past]))
                if rng.random() < 0.15:
                    mastery.review_related_dimension = rng.choice(DIMENSIONS)
                    mastery.review_related_due_at = rng.choice([None, future, *past])
                if rng.random() < 0.25:
                    mastery.review_remediation_date = rng.choice([today, today - timedelta(days=1)])
                    mastery.review_remediation_count = rng.randint(0, 3)
                db.session.add(mastery)
                masteries.append(mastery)
            db.session.flush()

            cooled = remediation = False
            for number in range(rng.randint(0, 3)):
                session = VocabularyReviewSession(
                    student_id=student.id, review_date=today - timedelta(days=number),
                    status=VocabularyReviewSession.STATUS_SETTLED, session_token=f"tok{trial}-{number}",
                    queue_token=f"q{trial}-{number}", batch_limit=20, started_at=now - timedelta(days=number),
                )
                db.session.add(session)
                db.session.flush()
                picked = rng.sample(masteries, k=min(len(masteries), rng.randint(1, 12)))
                for queue_index, mastery in enumerate(picked):
                    if mastery.student_id != student.id:
                        continue
                    word = words_by_sense[mastery.sense_id][0]
                    answered = rng.random() < 0.8
                    correct = rng.choice([True, False, False]) if answered else None
                    item = VocabularyReviewItem(
                        session_id=session.id, student_id=student.id, book_id=word.book_id, word_id=word.id,
                        sense_id=mastery.sense_id, dimension=rng.choice(DIMENSIONS), due_at=past[1],
                        stage_at_claim=0, queue_index=queue_index, question_id=f"qid{queue_index}",
                        question_snapshot_json="{}", answer_payload_json="{}",
                        first_attempt_id=f"a{trial}-{number}-{queue_index}" if answered else None,
                        first_is_correct=correct,
                        first_response_kind=rng.choice([None, "answer", "forgot"]) if answered else None,
                        correction_is_correct=rng.choice([None, True, False]) if correct is False else None,
                        correction_exhausted=bool(correct is False and rng.random() < 0.3),
                    )
                    db.session.add(item)
                    db.session.flush()
                    remediation = remediation or correct is False
                    if answered:
                        when = now - timedelta(minutes=5) if number == 0 and rng.random() < 0.6 else past[3]
                        cooled = cooled or when > now - timedelta(hours=1)
                        db.session.add(VocabularyReviewAttempt(
                            session_id=session.id, item_id=item.id, student_id=student.id,
                            attempt_id=item.first_attempt_id, question_id=item.question_id, student_answer="x",
                            is_correct=bool(correct), is_first_attempt=True, submitted_at=when,
                        ))
            db.session.commit()
            db.session.expire_all()

            user = db.session.get(User, student.id)
            legacy = review._due_candidates(user, now)
            legacy_projection = project(legacy)
            legacy_batch = [[c["public"], c["answer"]] for c in review._materialize_due_candidates(legacy, 20)]
            db.session.expire_all()
            with closing(review._iter_due_candidates(user, now)) as current:
                fresh = list(current)
            fresh_projection = project(fresh)
            with closing(review._iter_due_candidates(user, now)) as current:
                fresh_batch = [[c["public"], c["answer"]] for c in review._materialize_due_candidates(current, 20)]
            members = set(review._eligible_due_sense_ids(user, now))
            has_due = review._has_due(user, now)

            problems = []
            if legacy_projection != fresh_projection:
                problems.append("order")
            if members != {row[0] for row in legacy_projection}:
                problems.append("count_membership")
            if has_due != bool(legacy_projection):
                problems.append("has_due")
            if json.dumps(legacy_batch, sort_keys=True, ensure_ascii=False) != json.dumps(
                    fresh_batch, sort_keys=True, ensure_ascii=False):
                problems.append("first_batch")
            stats["trials"] += 1
            stats["total_candidates"] += len(legacy_projection)
            stats["max_candidates"] = max(stats["max_candidates"], len(legacy_projection))
            stats["empty_trials"] += not legacy_projection
            stats["trials_with_remediation"] += any(row[4] for row in legacy_projection)
            stats["trials_with_cooled"] += cooled
            if problems:
                first = next((i for i, (a, b) in enumerate(zip(legacy_projection, fresh_projection, strict=False)) if a != b),
                             min(len(legacy_projection), len(fresh_projection)))
                stats["mismatches"].append({
                    "trial": trial, "size": size, "problems": problems, "legacy_len": len(legacy_projection),
                    "fresh_len": len(fresh_projection), "first_difference_at": first,
                    "legacy": legacy_projection[first:first + 2], "fresh": fresh_projection[first:first + 2],
                })
    stats["mismatch_trials"] = len(stats["mismatches"])
    stats["mismatches"] = stats["mismatches"][:5]
    stats.update(seed=args.seed, synthetic_only=True)
    text = json.dumps(stats, ensure_ascii=False, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
