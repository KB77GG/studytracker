"""Independent synthetic probes through public protocol, not owner test classes."""

import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import event, insert

from models import (
    DictationWord,
    StudentVocabularyMastery,
    User,
    VocabularyErrorQueue,
    VocabularyPolicyAllocation,
    VocabularyPolicyCheckpoint,
    VocabularyPolicyEvent,
    VocabularyReviewSession,
    VocabularySense,
    db,
)
from services import vocabulary_autonomous_review as review
from services import vocabulary_error_queue as policy
from tests import test_vocabulary_autonomous_review as legacy_fixture


class IndependentPolicyEdges(unittest.TestCase):
    setUp = legacy_fixture.AutonomousVocabularyReviewTest.setUp
    tearDown = legacy_fixture.AutonomousVocabularyReviewTest.tearDown
    _answer_all = legacy_fixture.AutonomousVocabularyReviewTest._answer_all

    def enable(self):
        self.app.config[policy.FEATURE_FLAG] = True
        student = db.session.get(User, self.student_id)
        policy.enroll_student(student, starts_at=self.now - timedelta(days=40), now=self.now)
        db.session.commit()
        return student

    def error(self, student, word, at, source="initial"):
        policy.record_learning_answer(
            student,
            sense_id=word.sense_id,
            dimension="meaning_recall",
            correct=False,
            word_id=word.id,
            source_key=f"independent:{source}:{word.id}",
            now=at,
        )

    def claim(self, student, at=None):
        payload = review.claim_today_review(student, now=at or self.now)
        db.session.commit()
        session = (
            db.session.get(VocabularyReviewSession, payload["session_id"])
            if payload["session_id"]
            else None
        )
        return payload, session

    def settle(self, student, session, at=None):
        result = review.settle_review_session(
            student,
            session.id,
            {"queue_token": session.queue_token},
            session_token=session.session_token,
            now=at or self.now,
        )
        db.session.commit()
        return result

    def test_all_old_overloaded_errors_are_persisted_to_maintenance_on_empty_claim(self):
        with self.app.app_context():
            student = self.enable()
            for word in DictationWord.query.all():
                self.error(student, word, self.now - timedelta(days=12))
            db.session.commit()
            self.assertEqual(policy.plan_today(student, now=self.now)["entries"], [])
            payload, session = self.claim(student)
            self.assertTrue(payload["empty"])
            self.assertIsNone(session)
            self.assertEqual(VocabularyErrorQueue.query.filter_by(status="maintenance").count(), 22)
            self.assertEqual(
                VocabularyPolicyEvent.query.filter_by(kind="overdue_overload").count(), 22
            )
            optional = review.claim_today_review(student, now=self.now, optional=True)
            self.assertGreater(optional["total_count"], 0)

    def test_late_new_learning_error_cannot_receive_delayed_success_from_earlier_slot(self):
        with self.app.app_context():
            student = self.enable()
            word = DictationWord.query.first()
            self.error(student, word, self.now - timedelta(days=1))
            db.session.commit()
            _, session = self.claim(student)
            self.error(student, word, self.now + timedelta(minutes=1), source="new-error")
            db.session.commit()
            self._answer_all(session, now=self.now + timedelta(minutes=2))
            self.settle(student, session, at=self.now + timedelta(minutes=2))
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual(queue.success_count, 0)
            self.assertEqual(queue.due_local_date, policy.local_date(self.now) + timedelta(days=1))

    def test_missed_checkpoints_do_not_become_late_success_or_next_day_mandatory(self):
        with self.app.app_context():
            student = self.enable()
            word = DictationWord.query.first()
            policy.record_learning_answer(
                student,
                sense_id=word.sense_id,
                dimension="meaning_recall",
                correct=True,
                word_id=word.id,
                source_key="independent:sample",
                now=self.now - timedelta(days=7),
            )
            db.session.commit()
            _, session = self.claim(student)
            next_day = self.now + timedelta(days=1)
            payload, _ = self.claim(student, at=next_day)
            self.assertTrue(payload["empty"])
            checkpoint = VocabularyPolicyCheckpoint.query.filter_by(interval_days=7).one()
            self.assertEqual(checkpoint.status, "missed")
            item = session.items[0]
            with self.assertRaises(review.VocabularyAutonomousReviewError):
                review.submit_review_answer(
                    student,
                    session.id,
                    {
                        "session_token": session.session_token,
                        "review_item_id": item.id,
                        "question_id": item.question_id,
                        "word_id": item.word_id,
                        "sense_id": item.sense_id,
                        "dimension": item.dimension,
                        "answer": json.loads(item.answer_payload_json).get("answer"),
                        "attempt_id": "late-sample-answer",
                    },
                    now=next_day,
                )
            self.assertEqual(VocabularyPolicyEvent.query.filter_by(source="review").count(), 0)

    def test_old_client_wrong_answer_bypasses_correction_without_changing_failure_count(self):
        with self.app.app_context():
            student = self.enable()
            word = DictationWord.query.first()
            self.error(student, word, self.now - timedelta(days=1))
            db.session.commit()
            payload, session = self.claim(student)
            self.assertTrue(
                {"items", "words", "session_token", "queue_token", "due_count"}.issubset(payload)
            )
            item = session.items[0]
            answer = {
                "session_token": session.session_token,
                "review_item_id": item.id,
                "question_id": item.question_id,
                "word_id": item.word_id,
                "sense_id": item.sense_id,
                "dimension": item.dimension,
                "answer": "independent wrong answer",
                "attempt_id": "old-client-answer",
            }

            def frozen_answer(user, session_id, body, **kwargs):
                return review.submit_review_answer(user, session_id, body, now=self.now, **kwargs)

            def frozen_settle(user, session_id, body, **kwargs):
                return review.settle_review_session(user, session_id, body, now=self.now, **kwargs)

            prefix = f"/api/miniprogram/student/vocabulary-review/sessions/{session.id}"
            with (
                patch("api.vocab_review.submit_review_answer", side_effect=frozen_answer),
                patch("api.vocab_review.settle_review_session", side_effect=frozen_settle),
            ):
                response = self.client.post(prefix + "/answers", json=answer, headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json["is_correct"])
                settled = self.client.post(
                    prefix + "/settle",
                    json={
                        "queue_token": session.queue_token,
                        "session_token": session.session_token,
                    },
                    headers=self.headers,
                )
                self.assertEqual(settled.status_code, 200)
                result = settled.json
            self.assertFalse(result["continue_available"])
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual((queue.success_count, queue.failure_streak), (0, 1))
            self.assertEqual(VocabularyPolicyAllocation.query.one().status, "answered")

    def test_foreign_session_read_and_answer_do_not_change_bound_queue(self):
        with self.app.app_context():
            student = self.enable()
            word = DictationWord.query.first()
            self.error(student, word, self.now - timedelta(days=1))
            db.session.commit()
            _, session = self.claim(student)
            other = User(username="independent-other", password_hash="synthetic", role="student")
            db.session.add(other)
            db.session.commit()
            with self.assertRaises(review.VocabularyAutonomousReviewError):
                review.get_review_session(other, session.id, session_token=session.session_token)
            item = session.items[0]
            with self.assertRaises(review.VocabularyAutonomousReviewError):
                review.submit_review_answer(
                    other,
                    session.id,
                    {
                        "session_token": session.session_token,
                        "review_item_id": item.id,
                        "question_id": item.question_id,
                        "word_id": item.word_id,
                        "sense_id": item.sense_id,
                        "dimension": item.dimension,
                        "answer": "synthetic",
                        "attempt_id": "foreign-answer",
                    },
                    now=self.now,
                )
            self.assertEqual(VocabularyPolicyAllocation.query.one().status, "reserved")
            self.assertEqual(VocabularyErrorQueue.query.one().success_count, 0)

    def test_large_old_mastery_pool_is_not_queried_by_mandatory_summary(self):
        with self.app.app_context():
            student = self.enable()
            # Existing pool is deliberately much larger than the mandatory queue.
            db.session.execute(
                insert(VocabularySense),
                [
                    {
                        "id": 10000 + n,
                        "canonical_key": f"independent-scale-{n}",
                        "lemma": f"scale{n}",
                    }
                    for n in range(5000)
                ],
            )
            db.session.execute(
                insert(StudentVocabularyMastery),
                [
                    {
                        "student_id": student.id,
                        "sense_id": 10000 + n,
                        "meaning_recall_next_due_at": self.now - timedelta(days=20),
                    }
                    for n in range(5000)
                ],
            )
            db.session.commit()
            statements = []

            def capture(_conn, _cursor, sql, _params, _ctx, _many):
                statements.append(sql.lower())

            event.listen(db.engine, "before_cursor_execute", capture)
            try:
                with patch.object(
                    review, "_iter_due_candidates", side_effect=AssertionError("legacy pool scan")
                ):
                    self.assertEqual(review.review_summary(student, now=self.now)["due_count"], 0)
                    self.assertFalse(
                        review.review_preflight(student, self.task_id, now=self.now)["required"]
                    )
            finally:
                event.remove(db.engine, "before_cursor_execute", capture)
            self.assertFalse(any("student_vocabulary_mastery" in sql for sql in statements))
            self.assertEqual(VocabularyErrorQueue.query.count(), 0)

    def test_stale_unusable_plan_cannot_remove_later_new_error(self):
        with self.app.app_context():
            student = self.enable()
            word = DictationWord.query.first()
            self.error(student, word, self.now - timedelta(days=1))
            db.session.commit()
            entry = policy.plan_today(student, now=self.now)["entries"][0]
            self.error(student, word, self.now + timedelta(seconds=1), source="later-error")
            db.session.commit()
            try:
                policy.defer_unusable_entries(student, [entry], now=self.now + timedelta(seconds=2))
            except policy.PolicyConflict:
                db.session.rollback()
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual(queue.status, "active")
            self.assertEqual(queue.due_local_date, policy.local_date(self.now) + timedelta(days=1))
            self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="unanswerable").count(), 0)


if __name__ == "__main__":
    unittest.main()
