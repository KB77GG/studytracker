"""Independent stage-two equivalence and two-connection claim checks."""

import importlib.util
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from sqlalchemy.orm import Session

from models import (
    DictationBook,
    DictationWord,
    StudentVocabularyMastery,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    VocabularyReviewSession,
    db,
)
from services import vocabulary_autonomous_review as review
from services.dictation_review import local_date


def fixture_module():
    path = Path(__file__).resolve().parents[1] / "scripts/benchmark_vocabulary_review.py"
    spec = importlib.util.spec_from_file_location("adversarial_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signature(rows):
    return [
        (
            row["mastery"].id,
            row["word"].id,
            row["dimension"],
            row["stage"],
            row["due_at"],
            row["last_answered_at"],
            row["remediation_kind"],
        )
        for row in rows
    ]


class VocabularyStage2AdversarialTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vocab-stage2-adversarial-")
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{self.temp.name}/fixture.sqlite",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"timeout": 0.2}},
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.fixture = fixture_module()
        self.now = self.fixture.BENCHMARK_NOW

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.context.pop()
        self.temp.cleanup()

    def stale_session(self, user):
        old = VocabularyReviewSession(
            student_id=user.id,
            review_date=local_date(self.now - timedelta(days=5)),
            status=VocabularyReviewSession.STATUS_ACTIVE,
            claim_key=f"old-adversarial-{user.id}",
            session_token="old-adversarial-token",
            queue_token="old-adversarial-queue",
            started_at=self.now - timedelta(days=5),
        )
        db.session.add(old)
        db.session.commit()

    def assert_safe_conflict(self, user, task, mutation, *, stale=True):
        if stale:
            self.stale_session(user)
        uid, tid = user.id, task.id
        original = review._materialize_due_candidates
        mutation_calls = []

        def interleave(*args, **kwargs):
            selected = original(*args, **kwargs)
            if not mutation_calls:
                self.assertTrue(selected)
                mutation_calls.append(1)
                # A separately committed connection changes eligibility after
                # selection but before the claimant acquires its write lock.
                with Session(db.engine) as writer:
                    mutation(writer, selected)
                    writer.commit()
            return selected

        with patch.object(review, "_materialize_due_candidates", new=interleave):
            try:
                result = review.claim_today_review(user, origin_task_id=tid, now=self.now)
            except review.VocabularyAutonomousReviewError as error:
                self.assertEqual(error.status_code, 409)
                self.assertIn(error.error, {"review_claim_changed", "review_claim_in_progress"})
                db.session.rollback()  # The actual HTTP route also rolls back.
            else:
                db.session.rollback()
                self.fail(f"stale selection accepted: total_count={result.get('total_count')}")
        self.assertEqual(mutation_calls, [1])
        self.assertEqual(
            VocabularyReviewSession.query.filter_by(
                student_id=uid,
                status=VocabularyReviewSession.STATUS_ACTIVE,
                review_date=local_date(self.now),
            ).count(),
            0,
        )

    def test_claim_rechecks_new_cooldown_after_a_concurrent_completed_batch(self):
        user, task = self.fixture._seed(1)

        def cool(writer, selected):
            candidate = selected[0]
            word = candidate["word"]
            session = VocabularyReviewSession(
                student_id=user.id,
                review_date=local_date(self.now),
                status=VocabularyReviewSession.STATUS_SETTLED,
                session_token="concurrent-settled-token",
                queue_token="concurrent-settled-queue",
                started_at=self.now - timedelta(seconds=5),
                settled_at=self.now,
            )
            writer.add(session)
            writer.flush()
            item = VocabularyReviewItem(
                session_id=session.id,
                student_id=user.id,
                book_id=word.book_id,
                word_id=word.id,
                sense_id=word.sense_id,
                dimension=candidate["dimension"],
                due_at=candidate["due_at"],
                queue_index=0,
                question_id="concurrent-question",
                question_snapshot_json="{}",
                answer_payload_json="{}",
                first_attempt_id="concurrent-first",
                first_is_correct=True,
                state_applied=True,
            )
            writer.add(item)
            writer.flush()
            writer.add(
                VocabularyReviewAttempt(
                    session_id=session.id,
                    item_id=item.id,
                    student_id=user.id,
                    attempt_id="concurrent-first",
                    question_id=item.question_id,
                    student_answer="synthetic",
                    is_correct=True,
                    is_first_attempt=True,
                    submitted_at=self.now,
                )
            )

        self.assert_safe_conflict(user, task, cool)

    def test_claim_rechecks_concurrently_invalidated_word_despite_identity_map(self):
        user, task = self.fixture._seed(1)

        def invalidate(writer, selected):
            word = writer.get(DictationWord, selected[0]["word"].id)
            word.word = "bad/ambiguous"
            word.accepted_answers = None

        self.assert_safe_conflict(user, task, invalidate)

    def test_claim_rechecks_rescheduled_dimension_after_selection(self):
        user, task = self.fixture._seed(1)

        def reschedule(writer, selected):
            row = writer.get(StudentVocabularyMastery, selected[0]["mastery"].id)
            row.meaning_recall_next_due_at = self.now + timedelta(days=1)

        self.assert_safe_conflict(user, task, reschedule)

    def test_first_claim_conflict_rolls_back_insert_even_without_prior_write(self):
        user, task = self.fixture._seed(1)

        def reschedule(writer, selected):
            row = writer.get(StudentVocabularyMastery, selected[0]["mastery"].id)
            row.meaning_recall_next_due_at = self.now + timedelta(days=1)

        # No stale batch flush precedes SAVEPOINT. SQLite legacy transaction
        # mode must still roll back the new claim when its validation fails.
        self.assert_safe_conflict(user, task, reschedule, stale=False)

    def test_fallback_order_null_sense_representative_and_ties_match_legacy(self):
        user, _task = self.fixture._seed(5)
        words = DictationWord.query.order_by(DictationWord.id).all()
        masteries = StudentVocabularyMastery.query.order_by(StudentVocabularyMastery.id).all()
        book = DictationBook(title="independent-fallback", created_by=user.id)
        db.session.add(book)
        db.session.flush()
        for index, source in enumerate(words):
            db.session.add(
                DictationWord(
                    book_id=book.id,
                    sense_id=source.sense_id,
                    sequence=-99,
                    word=f"fallback{index}",
                    translation=f"替代词义{index}",
                )
            )
        masteries[0].representative_word_id = None
        masteries[1].representative_word_id = 999999
        # Existing NULL-sense representative is deliberately NOT repaired
        # through fallback in the legacy path; preserve the skipped row.
        words[2].sense_id = None
        # A representative of another sense is legal legacy input.
        masteries[3].representative_word_id = words[4].id
        for mastery in masteries:
            mastery.form_recall_stage = 1
            mastery.form_recall_next_due_at = mastery.meaning_recall_next_due_at
            mastery.meaning_recall_last_answered_at = None
            mastery.form_recall_last_answered_at = None
        db.session.commit()
        expected = review._due_candidates(user, self.now)
        actual = list(review._iter_due_candidates(user, self.now))
        self.assertEqual(signature(actual), signature(expected))
        self.assertEqual(
            review._eligible_due_sense_ids(user, self.now),
            {row["mastery"].sense_id for row in expected},
        )
        self.assertNotIn(masteries[2].id, [row["mastery"].id for row in actual])

    def test_display_zero_cannot_authorize_or_remove_real_queue_items(self):
        user, task = self.fixture._seed(3)
        expected = review._due_candidates(user, self.now)
        with patch.object(review, "_due_sense_ids", return_value=frozenset()):
            gate = review.review_preflight(user, task.id, now=self.now)
            self.assertEqual(gate["due_count"], 0)
            self.assertTrue(gate["required"])
            claimed = review.claim_today_review(user, origin_task_id=task.id, now=self.now)
        self.assertEqual(claimed["total_count"], 3)
        self.assertEqual(
            [item["sense_id"] for item in claimed["items"]],
            [candidate["mastery"].sense_id for candidate in expected],
        )

    def test_display_phantom_count_cannot_require_or_create_review(self):
        user, task = self.fixture._seed(3)
        StudentVocabularyMastery.query.update(
            {
                "meaning_recall_next_due_at": self.now + timedelta(days=1),
            }
        )
        db.session.commit()
        with patch.object(review, "_due_sense_ids", return_value=frozenset({999991, 999992})):
            gate = review.review_preflight(user, task.id, now=self.now)
            self.assertEqual(gate["due_count"], 2)
            self.assertFalse(gate["required"])
            claimed = review.claim_today_review(user, origin_task_id=task.id, now=self.now)
        self.assertTrue(claimed["empty"])
        self.assertEqual(claimed["total_count"], 0)
        self.assertEqual(VocabularyReviewSession.query.count(), 0)

    def test_grace_batch_stays_on_task_date_while_cooldown_uses_current_date(self):
        user, task = self.fixture._seed(2)
        # Benchmark task is 27 August. At 28 August 01:00 Beijing it remains
        # writable under the existing 03:00 grace rule.
        grace_now = self.now.replace(hour=17)
        claimed = review.claim_today_review(user, origin_task_id=task.id, now=grace_now)
        db.session.commit()
        session = db.session.get(VocabularyReviewSession, claimed["session_id"])
        self.assertEqual(session.review_date.isoformat(), str(task.date))
        self.assertNotEqual(session.review_date, local_date(grace_now))
        self.assertEqual(claimed["total_count"], 2)
        gate = review.review_preflight(user, task.id, now=grace_now)
        self.assertTrue(gate["required"])
        self.assertEqual(gate["active_session_id"], session.id)
        self.assertEqual(
            signature(list(review._iter_due_candidates(user, grace_now))),
            signature(review._due_candidates(user, grace_now)),
        )


if __name__ == "__main__":
    unittest.main()
