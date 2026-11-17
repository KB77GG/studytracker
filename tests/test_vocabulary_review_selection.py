"""Compare incremental entry work with the unchanged full-scan reference."""

import importlib.util
import json
import random
import unittest
from contextlib import closing
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event

from models import (
    DictationWord,
    StudentVocabularyMastery,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    VocabularyReviewSession,
    db,
)
from services import vocabulary_autonomous_review as review
from services.dictation_review import local_date
from services.vocabulary_mastery import DIMENSIONS


def fixture_module():
    path = Path(__file__).resolve().parents[1] / "scripts/benchmark_vocabulary_review.py"
    spec = importlib.util.spec_from_file_location("selection_fixture", path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    return fixture


def signature(candidates):
    return [
        {
            **{key: value for key, value in candidate.items() if key not in {"word", "mastery"}},
            "word": candidate["word"].id,
            "mastery": candidate["mastery"].id,
        }
        for candidate in candidates
    ]


class VocabularyReviewSelectionTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module()
        self.app = self.fixture._make_app()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.now = self.fixture.BENCHMARK_NOW

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _session(self, user, suffix, *, days_ago=2):
        session = VocabularyReviewSession(
            student_id=user.id,
            review_date=local_date(self.now - timedelta(days=days_ago)),
            status=VocabularyReviewSession.STATUS_ACTIVE,
            session_token=f"selection-token-{suffix}",
            queue_token=f"selection-queue-{suffix}",
            started_at=self.now - timedelta(days=days_ago),
        )
        db.session.add(session)
        db.session.flush()
        return session

    def _history(self, user, session, word, dimension, index, rng):
        item = VocabularyReviewItem(
            session_id=session.id,
            student_id=user.id,
            book_id=word.book_id,
            word_id=word.id,
            sense_id=word.sense_id,
            dimension=dimension,
            due_at=self.now - timedelta(days=3),
            queue_index=index,
            question_id=f"historical-{session.id}-{index}",
            question_snapshot_json="{}",
            answer_payload_json="{}",
            first_attempt_id=rng.choice([None, "", f"first-{session.id}-{index}"]),
            first_is_correct=rng.choice([None, False, True]),
            first_response_kind=rng.choice(["answer", "forgot"]),
            correction_is_correct=rng.choice([None, False, True]),
            correction_exhausted=rng.choice([False, True]),
        )
        db.session.add(item)
        db.session.flush()
        if rng.randrange(4) == 0:
            db.session.add(
                VocabularyReviewAttempt(
                    session_id=session.id,
                    item_id=item.id,
                    student_id=user.id,
                    attempt_id=f"cool-{session.id}-{index}",
                    question_id=item.question_id,
                    student_answer="synthetic",
                    is_correct=False,
                    is_first_attempt=rng.choice([False, True]),
                    submitted_at=self.now - timedelta(hours=rng.choice([1, 30])),
                )
            )

    def test_randomized_priority_eligibility_representatives_and_cooldown_match(self):
        for seed in range(12):
            if seed:
                db.session.remove()
                db.drop_all()
                db.create_all()
            user, _task = self.fixture._seed(80)
            rng = random.Random(7351 + seed)
            words = DictationWord.query.order_by(DictationWord.id).all()
            masteries = StudentVocabularyMastery.query.order_by(StudentVocabularyMastery.id).all()
            old = self._session(user, f"old-{seed}", days_ago=4)
            newer = self._session(user, f"new-{seed}")
            for index, (word, mastery) in enumerate(zip(words, masteries, strict=True)):
                for dimension in DIMENSIONS:
                    setattr(mastery, f"{dimension}_stage", rng.choice([0, 0, 1, 2, 5]))
                    setattr(
                        mastery,
                        f"{dimension}_next_due_at",
                        rng.choice(
                            [
                                None,
                                self.now - timedelta(days=rng.choice([1, 2, 3])),
                                self.now + timedelta(seconds=1),
                                self.now,
                            ]
                        ),
                    )
                    setattr(
                        mastery,
                        f"{dimension}_last_answered_at",
                        rng.choice(
                            [None, self.now - timedelta(days=4), self.now - timedelta(days=2)]
                        ),
                    )
                mastery.review_related_dimension = rng.choice([None, *DIMENSIONS])
                mastery.review_related_due_at = rng.choice(
                    [None, self.now - timedelta(days=1), self.now + timedelta(days=1)]
                )
                mastery.review_remediation_date = rng.choice(
                    [None, local_date(self.now), local_date(self.now - timedelta(days=1))]
                )
                mastery.review_remediation_count = rng.choice([0, 1, 2, 3])
                if index % 13 == 0:
                    mastery.representative_word_id = None
                if index % 17 == 0:
                    mastery.representative_word_id = 999999
                if index % 19 == 0:
                    # The existing representative wins even if linked to a
                    # different sense. Preserve this legacy data behavior.
                    mastery.representative_word_id = words[-1].id
                if index % 7 == 0:
                    word.core_meaning_zh = word.translation = ""
                if index % 5 == 0:
                    word.word = "invalid/ambiguous"
                    word.accepted_answers = '["accepted target"]' if index % 10 else None
                word.example_en = rng.choice(
                    ["", "This example has no target.", f"We use {word.word} in the classroom."]
                )
                word.usage_pattern = rng.choice(["", f"use {word.word} in class"])
                for historical_session in (old, newer):
                    if rng.randrange(3) == 0:
                        self._history(
                            user, historical_session, word, rng.choice(DIMENSIONS), index, rng
                        )
            # Multiple catalog rows per sense exercise deterministic fallback.
            for index, source in enumerate(words[:6]):
                db.session.add(
                    DictationWord(
                        book_id=source.book_id,
                        sense_id=source.sense_id,
                        sequence=-index,
                        word=f"fallback{index}",
                        translation=f"替代{index}",
                    )
                )
            db.session.commit()
            db.session.expire_all()
            expected = review._due_candidates(user, self.now)
            actual = list(review._iter_due_candidates(user, self.now))
            with self.subTest(seed=seed):
                self.assertEqual(signature(actual), signature(expected))
                self.assertEqual(
                    review._eligible_due_sense_ids(user, self.now),
                    {row["mastery"].sense_id for row in expected},
                )
                subset = {row.sense_id for row in masteries[::4]}
                self.assertEqual(
                    signature(
                        list(review._iter_due_candidates(user, self.now, only_sense_ids=subset))
                    ),
                    signature([row for row in expected if row["mastery"].sense_id in subset]),
                )
                self.assertEqual(
                    [
                        (x["public"], x["answer"])
                        for x in review._materialize_due_candidates(actual, 20)
                    ],
                    [
                        (x["public"], x["answer"])
                        for x in review._materialize_due_candidates(expected, 20)
                    ],
                )

    def test_existence_and_batch_stop_eligibility_early(self):
        user, _task = self.fixture._seed(2400)
        original = review._candidate_is_eligible
        examined = []

        def count(*args, **kwargs):
            examined.append(args[0].id)
            return original(*args, **kwargs)

        with (
            patch.object(
                review,
                "_due_candidates",
                side_effect=AssertionError("fresh selection scanned full backlog"),
            ),
            patch.object(review, "_candidate_is_eligible", new=count),
        ):
            self.assertTrue(review._has_due(user, self.now))
            self.assertEqual(len(examined), 1)
            examined.clear()
            with closing(review._iter_due_candidates(user, self.now)) as candidates:
                selected = review._materialize_due_candidates(candidates, 20)
            self.assertEqual(len(selected), 20)
            self.assertLessEqual(len(examined), 21)

    def test_invalid_leading_words_do_not_reduce_batch_size_or_change_order(self):
        user, _task = self.fixture._seed(180)
        for word in DictationWord.query.order_by(DictationWord.id).limit(140):
            word.word = "bad/ambiguous"
            word.accepted_answers = None
        db.session.commit()
        expected = review._due_candidates(user, self.now)
        with closing(review._iter_due_candidates(user, self.now)) as candidates:
            actual = review._materialize_due_candidates(candidates, 20)
        self.assertEqual([x["word"].id for x in actual], [x["word"].id for x in expected[:20]])
        self.assertEqual(len(actual), 20)

    def test_cached_zero_count_does_not_authorize_a_newly_due_task(self):
        user, task = self.fixture._seed(1)
        mastery = StudentVocabularyMastery.query.one()
        mastery.meaning_recall_next_due_at = self.now + timedelta(seconds=1)
        db.session.commit()
        first = review.review_preflight(user, task.id, now=self.now)
        self.assertEqual(first["due_count"], 0)
        self.assertFalse(first["required"])
        later = review.review_preflight(user, task.id, now=self.now + timedelta(seconds=2))
        self.assertEqual(later["due_count"], 0)  # Display-only 30-second snapshot.
        self.assertTrue(later["required"])
        claimed = review.claim_today_review(
            user, origin_task_id=task.id, now=self.now + timedelta(seconds=2)
        )
        self.assertEqual(claimed["total_count"], 1)

    def test_local_midnight_cooldown_matches_reference(self):
        user, _task = self.fixture._seed(1)
        word = DictationWord.query.one()
        session = self._session(user, "midnight")
        self._history(user, session, word, "meaning_recall", 0, random.Random(9))
        item = VocabularyReviewItem.query.one()
        VocabularyReviewAttempt.query.delete()
        before = self.now.replace(hour=15, minute=59, second=59)
        db.session.add(
            VocabularyReviewAttempt(
                session_id=session.id,
                item_id=item.id,
                student_id=user.id,
                attempt_id="midnight-first",
                question_id=item.question_id,
                student_answer="synthetic",
                is_correct=True,
                is_first_attempt=True,
                submitted_at=before - timedelta(seconds=1),
            )
        )
        db.session.commit()
        for point in (before, before + timedelta(seconds=1)):
            self.assertEqual(
                signature(list(review._iter_due_candidates(user, point))),
                signature(review._due_candidates(user, point)),
            )
        self.assertFalse(review._has_due(user, before))
        self.assertTrue(review._has_due(user, before + timedelta(seconds=1)))

    def test_claim_counts_before_stale_session_write_and_never_scans_after(self):
        user, task = self.fixture._seed(300)
        self._session(user, "stale")
        db.session.commit()
        writes = []
        counts = []
        original = review._eligible_due_sense_ids

        def sql(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                writes.append(statement.split(None, 1)[0])

        def count(*args, **kwargs):
            self.assertFalse(writes, "full backlog count ran after a write")
            counts.append(1)
            return original(*args, **kwargs)

        event.listen(db.engine, "before_cursor_execute", sql)
        try:
            with patch.object(review, "_eligible_due_sense_ids", new=count):
                result = review.claim_today_review(user, origin_task_id=task.id, now=self.now)
        finally:
            event.remove(db.engine, "before_cursor_execute", sql)
        self.assertEqual(result["total_count"], 20)
        self.assertEqual(result["due_count"], 300)
        self.assertEqual(result["remaining_due_count"], 280)
        self.assertEqual(len(counts), 1)
        self.assertTrue(writes)

    def test_settlement_counts_before_cas_and_rechecks_only_batch_senses(self):
        user, task = self.fixture._seed(60)
        claimed = review.claim_today_review(user, origin_task_id=task.id, now=self.now)
        db.session.commit()
        for index, item in enumerate(claimed["items"]):
            row = db.session.get(VocabularyReviewItem, item["review_item_id"])
            expected = json.loads(row.answer_payload_json)
            review.submit_review_answer(
                user,
                claimed["session_id"],
                {
                    "session_token": claimed["session_token"],
                    "review_item_id": row.id,
                    "word_id": row.word_id,
                    "sense_id": row.sense_id,
                    "dimension": row.dimension,
                    "question_id": row.question_id,
                    "answer": expected.get("answer_option_id") or expected.get("answer"),
                    "attempt_id": f"selection-answer-{index}",
                    "input_mode": "native",
                },
                now=self.now,
            )
            db.session.commit()
        writes = []
        original_count = review._eligible_due_sense_ids
        original_iter = review._iter_due_candidates
        rechecked = []

        def sql(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                writes.append(1)

        def count(*args, **kwargs):
            self.assertFalse(writes, "full backlog count ran under settlement write lock")
            return original_count(*args, **kwargs)

        def limited(*args, **kwargs):
            senses = kwargs.get("only_sense_ids")
            if senses is None:
                self.assertFalse(writes)
                self.assertEqual(len(kwargs["exclude_sense_ids"]), 20)
                return original_iter(*args, **kwargs)
            self.assertIsNotNone(senses)
            self.assertLessEqual(len(senses), 20)
            rechecked.append(len(senses))
            return original_iter(*args, **kwargs)

        event.listen(db.engine, "before_cursor_execute", sql)
        try:
            with (
                patch.object(review, "_eligible_due_sense_ids", new=count),
                patch.object(review, "_iter_due_candidates", new=limited),
            ):
                result = review.settle_review_session(
                    user,
                    claimed["session_id"],
                    {
                        "session_token": claimed["session_token"],
                        "queue_token": claimed["queue_token"],
                        "supports_correction": True,
                    },
                    now=self.now,
                )
        finally:
            event.remove(db.engine, "before_cursor_execute", sql)
        self.assertEqual(result["remaining_due_count"], len(original_count(user, self.now)))
        self.assertEqual(result["remaining_due_count"], 40)
        self.assertEqual(rechecked, [20])
        self.assertTrue(writes)

    def test_cached_positive_and_zero_counts_do_not_decide_continue(self):
        for actual_due in (False, True):
            db.session.remove()
            db.drop_all()
            db.create_all()
            user, task = self.fixture._seed(21)
            claimed = review.claim_today_review(user, origin_task_id=task.id, now=self.now)
            db.session.commit()
            for index, entry in enumerate(claimed["items"]):
                row = db.session.get(VocabularyReviewItem, entry["review_item_id"])
                expected = json.loads(row.answer_payload_json)
                review.submit_review_answer(
                    user,
                    claimed["session_id"],
                    {
                        "session_token": claimed["session_token"],
                        "review_item_id": row.id,
                        "word_id": row.word_id,
                        "sense_id": row.sense_id,
                        "dimension": row.dimension,
                        "question_id": row.question_id,
                        "answer": expected.get("answer_option_id") or expected.get("answer"),
                        "attempt_id": f"continue-answer-{index}",
                        "input_mode": "native",
                    },
                    now=self.now,
                )
                db.session.commit()
            last = StudentVocabularyMastery.query.order_by(
                StudentVocabularyMastery.id.desc()
            ).first()
            if not actual_due:
                last.meaning_recall_next_due_at = self.now + timedelta(days=1)
                db.session.commit()
            stale_senses = frozenset() if actual_due else frozenset({last.sense_id})
            with patch.object(review, "_due_sense_ids", return_value=stale_senses):
                result = review.settle_review_session(
                    user,
                    claimed["session_id"],
                    {
                        "session_token": claimed["session_token"],
                        "queue_token": claimed["queue_token"],
                        "supports_correction": True,
                    },
                    now=self.now,
                )
            with self.subTest(actual_due=actual_due):
                self.assertEqual(result["remaining_due_count"], len(stale_senses))
                self.assertEqual(result["continue_available"], actual_due)


if __name__ == "__main__":
    unittest.main()
