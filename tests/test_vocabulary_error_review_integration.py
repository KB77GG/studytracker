"""Exercise the opt-in policy through the existing public review protocol."""

import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from sqlalchemy import event

from models import (
    DictationRecord,
    DictationWord,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyErrorQueue,
    VocabularyLearningQuestion,
    VocabularyPolicyAllocation,
    VocabularyPolicyCheckpoint,
    VocabularyPolicyEvent,
    VocabularyReviewAttempt,
    VocabularyReviewSession,
    VocabularyTaskReview,
    db,
)
from services import vocabulary_autonomous_review as review
from services import vocabulary_error_queue as policy
from services import vocabulary_error_review as bridge
from services.vocabulary_group_learning import get_vocabulary_group_queue
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense
from tests import test_vocabulary_autonomous_review as review_fixtures
from tests import test_vocabulary_group_learning as group_fixtures
from tests import test_vocabulary_mastery as mastery_fixtures


class ErrorReviewIntegrationTest(unittest.TestCase):
    setUp = review_fixtures.AutonomousVocabularyReviewTest.setUp
    tearDown = review_fixtures.AutonomousVocabularyReviewTest.tearDown
    _answer_all = review_fixtures.AutonomousVocabularyReviewTest._answer_all

    def _enable(self, now=None):
        self.app.config[policy.FEATURE_FLAG] = True
        user = db.session.get(User, self.student_id)
        policy.enroll_student(user, starts_at=self.now - timedelta(days=40), now=now or self.now)
        db.session.commit()
        return user

    def _error(self, user, word, dimension="meaning_recall", *, now=None):
        at = now or self.now - timedelta(days=1)
        policy.record_learning_answer(
            user,
            sense_id=word.sense_id,
            dimension=dimension,
            correct=False,
            source_key=f"seed:{word.id}:{dimension}:{at.isoformat()}",
            word_id=word.id,
            now=at,
        )
        db.session.commit()

    def _session(self, user, *, optional=False, now=None, origin_task_id=None):
        payload = review.claim_today_review(
            user,
            now=now or self.now,
            optional=optional,
            origin_task_id=origin_task_id,
        )
        db.session.commit()
        return payload, db.session.get(VocabularyReviewSession, payload["session_id"])

    def _settle(self, user, session, *, now=None):
        result = review.settle_review_session(
            user,
            session.id,
            {"queue_token": session.queue_token},
            session_token=session.session_token,
            now=now or self.now,
        )
        db.session.commit()
        return result

    def _answer(self, user, session, item, *, correct=True, now=None, forgot=False):
        expected = json.loads(item.answer_payload_json)
        payload = {
            "session_token": session.session_token,
            "review_item_id": item.id,
            "question_id": item.question_id,
            "word_id": item.word_id,
            "sense_id": item.sense_id,
            "dimension": item.dimension,
            "answer": (
                (expected.get("answer_option_id") or expected.get("answer"))
                if correct
                else "wrong-answer"
            ),
            "attempt_id": f"policy-first:{item.id}",
            "supports_correction": True,
        }
        if forgot:
            payload.update(response_kind="forgot", answer="")
        result = review.submit_review_answer(user, session.id, payload, now=now or self.now)
        db.session.commit()
        return result, payload

    def test_off_makes_no_new_table_queries_and_keeps_legacy_shape(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            seen = []

            def capture(conn, cursor, statement, parameters, context, executemany):
                if any(
                    name in statement.lower()
                    for name in (
                        "vocabulary_review_policy_enrollment",
                        "vocabulary_error_queue",
                        "vocabulary_policy_checkpoint",
                        "vocabulary_policy_allocation",
                        "vocabulary_policy_event",
                    )
                ):
                    seen.append(statement)

            event.listen(db.engine, "before_cursor_execute", capture)
            try:
                summary = review.review_summary(user, now=self.now)
                self.assertNotIn("policy_enabled", summary)
                self.assertGreater(summary["due_count"], 0)
                payload, session = self._session(user, optional=True)
                self.assertNotIn("session_mode", payload)
                self._answer_all(session)
                result = self._settle(user, session)
                self.assertNotIn("policy_enabled", result)
                self.assertEqual(seen, [])
            finally:
                event.remove(db.engine, "before_cursor_execute", capture)

    def test_legacy_backlog_never_enters_pilot_gate_or_mandatory_scan(self):
        with self.app.app_context():
            user = self._enable()
            with (
                patch.object(review, "_due_sense_ids", side_effect=AssertionError("old count")),
                patch.object(
                    review, "_iter_due_candidates", side_effect=AssertionError("old scan")
                ),
            ):
                self.assertFalse(
                    review.review_preflight(user, self.task_id, now=self.now)["required"]
                )
                self.assertEqual(review.review_summary(user, now=self.now)["due_count"], 0)
                self.assertTrue(review.claim_today_review(user, now=self.now)["empty"])
            self.assertEqual(VocabularyErrorQueue.query.count(), 0)

    def test_http_default_is_mandatory_and_explicit_mode_selects_optional(self):
        with self.app.app_context():
            self._enable()

        def frozen_claim(user, origin_task_id=None, optional=False):
            return review.claim_today_review(
                user, now=self.now, origin_task_id=origin_task_id, optional=optional
            )

        with patch("api.vocab_review.claim_today_review", side_effect=frozen_claim):
            mandatory = self.client.get(
                "/api/miniprogram/student/vocabulary-review/today", headers=self.headers
            )
            self.assertEqual(mandatory.status_code, 200)
            self.assertEqual(mandatory.json["session_mode"], "mandatory")
            self.assertTrue(mandatory.json["empty"])
            optional = self.client.get(
                "/api/miniprogram/student/vocabulary-review/today?mode=maintenance",
                headers=self.headers,
            )
            self.assertEqual(optional.status_code, 200)
            self.assertEqual(optional.json["session_mode"], "maintenance")
            self.assertEqual(optional.json["total_count"], 10)
            resumed = self.client.get(
                "/api/miniprogram/student/vocabulary-review/today?mode=maintenance",
                headers=self.headers,
            )
            self.assertEqual(resumed.json["session_id"], optional.json["session_id"])
            conflict = self.client.get(
                "/api/miniprogram/student/vocabulary-review/today", headers=self.headers
            )
            self.assertEqual(conflict.status_code, 409)
            self.assertEqual(conflict.json["error"], "review_other_mode_active")

    def test_two_abilities_of_same_word_use_two_slots_and_only_requested_dimensions(self):
        with self.app.app_context():
            user = self._enable()
            word = DictationWord.query.order_by(DictationWord.id).first()
            self._error(user, word)
            self._error(user, word, "form_recall")
            with patch.object(
                review, "_iter_due_candidates", side_effect=AssertionError("old scan")
            ):
                payload, session = self._session(user)
                self.assertEqual(payload["total_count"], 2)
                self.assertEqual(
                    {item.dimension for item in session.items}, {"meaning_recall", "form_recall"}
                )
                self.assertEqual(len({item.word_id for item in session.items}), 1)
                self.assertEqual(len({item.question_id for item in session.items}), 2)
                self._answer_all(session)
                result = self._settle(user, session)
            self.assertEqual(result["mandatory_answered"], 2)
            self.assertEqual(result["remaining_due_count"], 0)
            self.assertFalse(result["continue_available"])
            self.assertFalse(review.review_preflight(user, self.task_id, now=self.now)["required"])
            self.assertEqual({q.success_count for q in VocabularyErrorQueue.query.all()}, {1})

    def test_first_answer_replay_and_correction_do_not_graduate_error(self):
        with self.app.app_context():
            user = self._enable()
            word = DictationWord.query.order_by(DictationWord.id).first()
            self._error(user, word)
            _, session = self._session(user)
            item = session.items[0]
            result, payload = self._answer(user, session, item, correct=False)
            self.assertFalse(result["is_correct"])
            replay = review.submit_review_answer(user, session.id, payload, now=self.now)
            self.assertTrue(replay["idempotent"])
            expected = json.loads(item.answer_payload_json)
            review.submit_review_correction(
                user,
                session.id,
                {
                    "session_token": session.session_token,
                    "review_item_id": item.id,
                    "word_id": item.word_id,
                    "sense_id": item.sense_id,
                    "dimension": item.dimension,
                    "question_id": item.question_id,
                    "answer": expected.get("answer_option_id") or expected.get("answer"),
                    "attempt_id": "policy-correction",
                },
                now=self.now,
            )
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual((queue.success_count, queue.failure_streak), (0, 1))
            self.assertEqual(
                VocabularyPolicyEvent.query.filter_by(source="review", kind="answer").count(), 1
            )
            self._settle(user, session)
            self.assertTrue(review.claim_today_review(user, now=self.now)["empty"])

    def test_two_successes_are_separated_by_two_natural_dates(self):
        with self.app.app_context():
            user = self._enable()
            word = DictationWord.query.order_by(DictationWord.id).first()
            self._error(user, word, now=self.now.replace(hour=15, minute=59) - timedelta(days=1))
            _, first = self._session(user, now=self.now.replace(hour=0))
            self._answer_all(first, now=self.now.replace(hour=0))
            self._settle(user, first, now=self.now.replace(hour=0))
            self.assertTrue(
                review.claim_today_review(user, now=self.now + timedelta(days=1))["empty"]
            )
            _, second = self._session(user, now=self.now + timedelta(days=2))
            self._answer_all(second, now=self.now + timedelta(days=2))
            self._settle(user, second, now=self.now + timedelta(days=2))
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual(queue.status, "closed")
            self.assertEqual(queue.success_count, 2)

    def test_four_samples_count_inside_twenty_daily_ability_limit(self):
        with self.app.app_context():
            user = self._enable()
            words = DictationWord.query.order_by(DictationWord.id).all()
            for word in words:
                self._error(user, word)
                policy.record_learning_answer(
                    user,
                    sense_id=word.sense_id,
                    dimension="form_recall",
                    correct=True,
                    source_key=f"checkpoint:{word.id}",
                    word_id=word.id,
                    now=self.now - timedelta(days=7),
                )
            db.session.commit()
            payload, session = self._session(user)
            self.assertEqual(payload["total_count"], 20)
            slots = VocabularyPolicyAllocation.query.filter_by(session_id=session.id).all()
            self.assertEqual(sum(slot.kind == "sample" for slot in slots), 4)
            self.assertEqual(sum(slot.kind == "error" for slot in slots), 16)
            self._answer_all(session)
            self._settle(user, session)
            self.assertTrue(review.claim_today_review(user, now=self.now)["empty"])
            self.assertFalse(review.review_preflight(user, self.task_id, now=self.now)["required"])
            self.assertEqual(
                VocabularyPolicyAllocation.query.filter_by(mode="mandatory").count(), 20
            )

    def test_optional_maintenance_ten_budget_and_active_session_never_gate(self):
        with self.app.app_context():
            user = self._enable()
            payload, session = self._session(user, optional=True)
            self.assertEqual((payload["total_count"], payload["session_mode"]), (10, "maintenance"))
            self.assertFalse(review.review_preflight(user, self.task_id, now=self.now)["required"])
            summary = review.review_summary(user, now=self.now)
            self.assertFalse(summary["has_active_session"])
            self.assertEqual(summary["optional_active_session_id"], session.id)
            self.assertEqual(summary["maintenance_remaining"], 0)
            self.assertTrue(summary["optional_available"])
            task_queue = get_vocabulary_group_queue(user, self.task_id, now=self.now)
            self.assertTrue(task_queue["ok"])
            self.assertFalse(task_queue.get("review_required", False))
            self._answer_all(session)
            summary = review.review_summary(user, now=self.now)
            self.assertEqual(summary["maintenance_remaining"], 0)
            self.assertTrue(summary["optional_available"])
            resumed = review.claim_today_review(user, optional=True, now=self.now)
            self.assertEqual(resumed["session_id"], session.id)
            self.assertTrue(resumed["optional_available"])
            self.assertFalse(review.review_preflight(user, self.task_id, now=self.now)["required"])
            result = self._settle(user, session)
            self.assertEqual(result["maintenance_remaining"], 0)
            self.assertFalse(result["continue_available"])
            self.assertFalse(review.review_summary(user, now=self.now)["optional_available"])
            self.assertTrue(
                review.continue_review(
                    user, session.id, session_token=session.session_token, now=self.now
                )["empty"]
            )

    def test_optional_forgot_opens_only_that_ability_for_next_day(self):
        with self.app.app_context():
            user = self._enable()
            _, session = self._session(user, optional=True)
            item = session.items[0]
            self._answer(user, session, item, correct=False, forgot=True)
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual((queue.sense_id, queue.dimension), (item.sense_id, item.dimension))
            self.assertEqual(queue.due_local_date, policy.local_date(self.now) + timedelta(days=1))
            self.assertEqual(queue.success_count, 0)
            self.assertFalse(review.review_preflight(user, self.task_id, now=self.now)["required"])

    def test_optional_policy_queries_are_constant_when_large_old_pool_is_excluded(self):
        with self.app.app_context():
            user = self._enable()
            book_id = DictationWord.query.first().book_id
            for word in DictationWord.query.all():
                self._error(user, word, now=self.now)

            def measure():
                plan = policy.plan_today(user, now=self.now, optional=True)
                queries = []

                def capture(conn, cursor, statement, parameters, context, executemany):
                    if statement.lstrip().upper().startswith("SELECT") and any(
                        name in statement
                        for name in (
                            "vocabulary_review_policy_enrollment",
                            "vocabulary_error_queue",
                            "vocabulary_policy_allocation",
                        )
                    ):
                        queries.append(statement)

                event.listen(db.engine, "before_cursor_execute", capture)
                try:
                    candidates, _ = bridge._optional_candidates(user, self.now, plan)
                finally:
                    event.remove(db.engine, "before_cursor_execute", capture)
                self.assertEqual(candidates, [])
                return len(queries)

            small_queries = measure()
            for index in range(22, 220):
                word = DictationWord(
                    book_id=book_id,
                    sequence=index + 100,
                    word=f"poolword{index}",
                    translation=f"池中义{index}",
                    core_meaning_zh=f"池中义{index}",
                )
                db.session.add(word)
                db.session.flush()
                mastery = ensure_mastery(user, word, ensure_word_sense(word))
                mastery.meaning_recall_stage = 1
                mastery.meaning_recall_next_due_at = self.now - timedelta(days=1)
                policy.record_learning_answer(
                    user,
                    sense_id=word.sense_id,
                    dimension="meaning_recall",
                    correct=False,
                    source_key=f"pool-error:{index}",
                    now=self.now,
                    word_id=word.id,
                )
            # Include both mandatory-active and teacher-paused exclusions.
            for row in VocabularyErrorQueue.query.order_by(VocabularyErrorQueue.id).limit(100):
                row.status = "paused"
                row.pause_until_local_date = policy.local_date(self.now) + timedelta(days=7)
            db.session.commit()
            self.assertEqual(measure(), small_queries)
            self.assertLessEqual(small_queries, 3)

    def test_optional_final_reservation_rechecks_new_error_after_bulk_snapshot(self):
        with self.app.app_context():
            user = self._enable()
            reserve = policy.reserve_items

            def concurrent_error(student, session_id, items, **kwargs):
                entry = items[0]["entry"]
                policy.record_learning_answer(
                    student,
                    sense_id=entry["sense_id"],
                    dimension=entry["dimension"],
                    word_id=entry["word_id"],
                    correct=False,
                    source_key="changed-after-selection",
                    now=self.now,
                )
                return reserve(student, session_id, items, **kwargs)

            with patch.object(policy, "reserve_items", side_effect=concurrent_error):
                with self.assertRaises(review.VocabularyAutonomousReviewError) as raised:
                    review.claim_today_review(user, optional=True, now=self.now)
                self.assertEqual(raised.exception.error, "review_policy_changed")
                db.session.rollback()
            self.assertEqual(VocabularyReviewSession.query.count(), 0)
            self.assertEqual(VocabularyPolicyAllocation.query.count(), 0)

    def test_pilot_session_expires_at_midnight_even_task_has_grace(self):
        with self.app.app_context():
            user = self._enable()
            word = DictationWord.query.first()
            self._error(user, word)
            _, session = self._session(user, origin_task_id=self.task_id)
            with self.assertRaises(review.VocabularyAutonomousReviewError) as raised:
                self._answer(
                    user, session, session.items[0], now=self.now.replace(hour=16, minute=1)
                )
            self.assertEqual(
                (raised.exception.error, raised.exception.status_code), ("task_expired", 403)
            )
            self.assertEqual(VocabularyPolicyEvent.query.filter_by(source="review").count(), 0)

    def test_unusable_new_error_is_deferred_without_success_or_permanent_gate(self):
        with self.app.app_context():
            user = self._enable()
            word = DictationWord.query.first()
            self._error(user, word)
            with patch.object(
                bridge,
                "_materialize_entries",
                return_value=([], policy.plan_today(user, now=self.now)["entries"]),
            ):
                result = review.claim_today_review(user, now=self.now)
                db.session.commit()
            self.assertTrue(result["empty"])
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual(
                (queue.status, queue.success_count, queue.closed_reason),
                ("maintenance", 0, "unanswerable"),
            )
            self.assertFalse(review.review_preflight(user, self.task_id, now=self.now)["required"])

    def test_empty_claim_persists_overdue_transfers_and_optional_can_claim_them(self):
        with self.app.app_context():
            user = self._enable()
            for word in DictationWord.query.all():
                self._error(user, word, now=self.now - timedelta(days=10))
            planned = policy.plan_today(user, now=self.now)
            self.assertEqual(planned["entries"], [])
            self.assertEqual(planned["overdue_transferred_count"], 22)
            result = review.claim_today_review(user, now=self.now)
            db.session.commit()
            self.assertTrue(result["empty"])
            self.assertEqual(VocabularyErrorQueue.query.filter_by(status="maintenance").count(), 22)
            self.assertEqual(
                VocabularyPolicyEvent.query.filter_by(kind="overdue_overload").count(), 22
            )
            optional, session = self._session(user, optional=True)
            self.assertEqual(optional["total_count"], 10)

    def test_deployment_configuration_limits_are_returned_and_enforced(self):
        with self.app.app_context():
            self.app.config.update(
                VOCABULARY_ERROR_REVIEW_DAILY_LIMIT=3,
                VOCABULARY_ERROR_REVIEW_SAMPLE_LIMIT=1,
                VOCABULARY_ERROR_REVIEW_MAINTENANCE_LIMIT=2,
            )
            user = self._enable()
            for word in DictationWord.query.limit(6).all():
                self._error(user, word)
            payload, session = self._session(user)
            self.assertEqual(
                (
                    payload["total_count"],
                    payload["batch_limit"],
                    payload["mandatory_limit"],
                    payload["checkpoint_limit"],
                    payload["maintenance_limit"],
                ),
                (3, 3, 3, 1, 2),
            )
            self._answer_all(session)
            self._settle(user, session)
            self.assertTrue(review.claim_today_review(user, now=self.now)["empty"])
            optional, session = self._session(user, optional=True)
            self.assertEqual((optional["total_count"], optional["batch_limit"]), (2, 2))

    def test_revalidation_rejects_changed_batch_atomically(self):
        with self.app.app_context():
            user = self._enable()
            word = DictationWord.query.first()
            self._error(user, word)
            materialize = bridge._materialize_entries
            calls = []

            def changed(*args, **kwargs):
                calls.append(1)
                candidates, invalid = materialize(*args, **kwargs)
                if len(calls) == 2:
                    candidates[0]["public"] = {**candidates[0]["public"], "changed": True}
                return candidates, invalid

            with patch.object(bridge, "_materialize_entries", side_effect=changed):
                with self.assertRaises(review.VocabularyAutonomousReviewError) as raised:
                    review.claim_today_review(user, now=self.now)
                self.assertEqual(raised.exception.error, "review_claim_changed")
                db.session.rollback()
            self.assertEqual(VocabularyReviewSession.query.count(), 0)
            self.assertEqual(VocabularyPolicyAllocation.query.count(), 0)

    def test_policy_failure_rolls_back_first_attempt_and_mastery_together(self):
        with self.app.app_context():
            user = self._enable()
            word = DictationWord.query.first()
            self._error(user, word)
            _, session = self._session(user)
            item = session.items[0]
            item_id, session_id = item.id, session.id
            before = (
                StudentVocabularyMastery.query.filter_by(student_id=user.id, sense_id=item.sense_id)
                .one()
                .meaning_recall_stage
            )
            with patch.object(
                policy, "apply_review_answer", side_effect=policy.PolicyConflict("injected")
            ):
                with self.assertRaises(review.VocabularyAutonomousReviewError):
                    self._answer(user, session, item)
                db.session.rollback()
            self.assertEqual(VocabularyReviewAttempt.query.count(), 0)
            session = db.session.get(VocabularyReviewSession, session_id)
            item = next(row for row in session.items if row.id == item_id)
            self.assertIsNone(item.first_attempt_id)
            self.assertFalse(item.state_applied)
            self.assertEqual(
                StudentVocabularyMastery.query.filter_by(student_id=user.id, sense_id=item.sense_id)
                .one()
                .meaning_recall_stage,
                before,
            )
            self.assertEqual(VocabularyPolicyAllocation.query.one().status, "reserved")
            self._answer(user, session, item)
            self.assertEqual(VocabularyPolicyAllocation.query.one().status, "answered")

    def test_only_server_validated_bad_question_can_consume_slot_without_success(self):
        with self.app.app_context():
            user = self._enable()
            self._error(user, DictationWord.query.first())
            _, session = self._session(user)
            item = session.items[0]
            payload = {
                "queue_token": session.queue_token,
                "skipped_items": [{"review_item_id": item.id, "reason": "invalid_question"}],
            }
            with self.assertRaises(review.VocabularyAutonomousReviewError) as raised:
                review.settle_review_session(
                    user, session.id, payload, session_token=session.session_token, now=self.now
                )
            self.assertEqual(raised.exception.error, "review_item_skip_invalid")
            self.assertEqual(VocabularyPolicyAllocation.query.one().status, "reserved")
            item.question_snapshot_json = "{not-json"
            result = review.settle_review_session(
                user, session.id, payload, session_token=session.session_token, now=self.now
            )
            db.session.commit()
            self.assertEqual(
                (result["total_count"], result["skipped_count"], result["mandatory_answered"]),
                (0, 1, 1),
            )
            self.assertEqual(VocabularyPolicyAllocation.query.one().status, "skipped")
            queue = VocabularyErrorQueue.query.one()
            self.assertEqual((queue.status, queue.success_count), ("maintenance", 0))
            self.assertEqual(VocabularyReviewAttempt.query.count(), 0)
            self.assertFalse(review.review_preflight(user, self.task_id, now=self.now)["required"])


class ErrorPolicyLearningHookTest(unittest.TestCase):
    setUp = group_fixtures.VocabularyGroupLearningTest.setUp
    tearDown = group_fixtures.VocabularyGroupLearningTest.tearDown
    _task = group_fixtures.VocabularyGroupLearningTest._task
    _user = group_fixtures.VocabularyGroupLearningTest._user
    _view_group = group_fixtures.VocabularyGroupLearningTest._view_group
    _answer_for_current = group_fixtures.VocabularyGroupLearningTest._answer_for_current
    _correct_current = group_fixtures.VocabularyGroupLearningTest._correct_current

    def test_policy_failure_rolls_back_group_position_and_first_record(self):
        with self.app.app_context():
            self.app.config[policy.FEATURE_FLAG] = True
            user = self._user()
            now = datetime.utcnow()
            policy.enroll_student(user, starts_at=now - timedelta(days=1), now=now)
            task = self._task(goal="listening", end=1)
            queue = self._view_group(
                user, task.id, get_vocabulary_group_queue(user, task.id, now=now), now=now
            )
            question_id = queue["current_question"]["learning_question_id"]
            db.session.commit()
            with patch.object(
                policy, "record_learning_answer", side_effect=policy.PolicyConflict("injected")
            ):
                with self.assertRaises(group_fixtures.VocabularyGroupLearningError):
                    self._answer_for_current(user, task.id, queue, wrong=True, now=now)
                db.session.rollback()
            self.assertEqual(DictationRecord.query.count(), 0)
            self.assertIsNone(
                db.session.get(VocabularyLearningQuestion, question_id).first_attempt_id
            )
            fresh = get_vocabulary_group_queue(user, task.id, now=now)
            self.assertEqual(fresh["current_question"]["learning_question_id"], question_id)
            self._answer_for_current(user, task.id, fresh, wrong=True, now=now)
            self.assertEqual(VocabularyErrorQueue.query.count(), 1)

    def test_group_first_wrong_and_forgot_are_atomic_idempotent_but_retries_are_not_successes(self):
        with self.app.app_context():
            self.app.config[policy.FEATURE_FLAG] = True
            user = self._user()
            now = datetime.utcnow()
            policy.enroll_student(user, starts_at=now - timedelta(days=1), now=now)
            task = self._task(goal="listening", end=1)
            queue = self._view_group(
                user, task.id, get_vocabulary_group_queue(user, task.id, now=now), now=now
            )
            result = self._answer_for_current(
                user, task.id, queue, response_kind="forgot", attempt_id="first-forgot", now=now
            )
            self.assertFalse(result["is_correct"])
            repeat = self._answer_for_current(
                user, task.id, queue, response_kind="forgot", attempt_id="first-forgot", now=now
            )
            self.assertTrue(repeat["idempotent"])
            db.session.commit()
            self.assertEqual(VocabularyErrorQueue.query.count(), 1)
            self.assertEqual(VocabularyPolicyEvent.query.filter_by(source="learning").count(), 1)
            while True:
                queue = get_vocabulary_group_queue(user, task.id, now=now)
                if queue["completed"]:
                    break
                self._answer_for_current(user, task.id, queue, now=now)
            db.session.commit()
            error = VocabularyErrorQueue.query.one()
            self.assertEqual(
                (error.status, error.success_count, error.failure_streak), ("active", 0, 0)
            )

    def test_group_context_guidance_and_remediation_do_not_create_checkpoint_successes(self):
        with self.app.app_context():
            self.app.config[policy.FEATURE_FLAG] = True
            user = self._user()
            now = datetime.utcnow()
            policy.enroll_student(user, starts_at=now - timedelta(days=1), now=now)
            task = self._task(goal="reading", end=3)
            queue = get_vocabulary_group_queue(user, task.id, now=now)
            while not queue["completed"]:
                queue = self._view_group(user, task.id, queue, now=now)
                question = queue.get("current_question")
                if question:
                    self._answer_for_current(user, task.id, queue, now=now)
                queue = get_vocabulary_group_queue(user, task.id, now=now)
            db.session.commit()
            formal = VocabularyLearningQuestion.query.filter_by(
                student_id=user.id, score_eligible=True
            ).all()
            keys = {(q.sense_id, q.dimension) for q in formal}
            checkpoints = VocabularyPolicyCheckpoint.query.all()
            self.assertEqual(len(checkpoints), 2 * len(keys))
            self.assertEqual(
                VocabularyPolicyEvent.query.filter_by(source="learning").count(), len(formal)
            )
            self.assertEqual(VocabularyErrorQueue.query.count(), 0)


class ErrorPolicyLegacyLearningHookTest(unittest.TestCase):
    setUp = mastery_fixtures.VocabularyMasteryFlowTest.setUp
    tearDown = mastery_fixtures.VocabularyMasteryFlowTest.tearDown
    _task = mastery_fixtures.VocabularyMasteryFlowTest._task

    def test_policy_failure_rolls_back_legacy_first_record_and_retry_only_records_once(self):
        with self.app.app_context():
            self.app.config[policy.FEATURE_FLAG] = True
            user = db.session.get(User, self.student_id)
            now = datetime(2026, 8, 7, 12)
            policy.enroll_student(user, starts_at=now - timedelta(days=1), now=now)
            task = self._task(goal="reading", start=1, end=1)
            queue = mastery_fixtures.get_vocabulary_task_queue(user, task.id, now)
            item = queue["words"][0]
            payload = {
                "task_id": task.id,
                "queue_item_id": item["queue_item_id"],
                "question_id": item["question_id"],
                "word_id": item["word_id"],
                "dimension": item["dimension"],
                "answer": "wrong-answer",
                "input_mode": "native",
                "attempt_id": "legacy-policy-first",
            }
            db.session.commit()
            with patch.object(
                policy, "record_learning_answer", side_effect=policy.PolicyConflict("injected")
            ):
                with self.assertRaises(mastery_fixtures.VocabularyMasteryError):
                    mastery_fixtures.submit_vocabulary_answer(user, payload, now=now)
                db.session.rollback()
            self.assertEqual(DictationRecord.query.count(), 0)
            stored = db.session.get(VocabularyTaskReview, item["queue_item_id"])
            self.assertIsNone(stored.first_attempt_id)
            mastery_fixtures.submit_vocabulary_answer(user, payload, now=now)
            db.session.commit()
            expected = json.loads(stored.answer_payload_json)
            mastery_fixtures.submit_vocabulary_answer(
                user,
                {
                    **payload,
                    "attempt_id": "legacy-policy-retry",
                    "answer": expected.get("answer_option_id") or expected.get("answer"),
                },
                now=now,
            )
            self.assertEqual(VocabularyPolicyEvent.query.filter_by(source="learning").count(), 1)
            self.assertEqual(VocabularyErrorQueue.query.one().success_count, 0)


class PolicyActivationRaceTest(unittest.TestCase):
    """Real file SQLite, independent app contexts and separate connections."""

    def setUp(self):
        review_fixtures.AutonomousVocabularyReviewTest.setUp(self)
        self.directory = tempfile.TemporaryDirectory(prefix="vocab-policy-race-")
        database = Path(self.directory.name) / "race.sqlite"
        with self.app.app_context():
            source = db.engine.raw_connection()
            destination = sqlite3.connect(str(database))
            try:
                source.driver_connection.backup(destination)
            finally:
                destination.close()
                source.close()
            config = dict(self.app.config)
        self.app = Flask(__name__)
        self.app.config.update(config)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{database}", VOCABULARY_ERROR_REVIEW_ENABLED=True
        )
        db.init_app(self.app)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.directory.cleanup()

    def _thread(self, action, results):
        def run():
            with self.app.app_context():
                try:
                    action(db.session.get(User, self.student_id))
                    db.session.commit()
                    results.append("committed")
                except Exception as error:
                    db.session.rollback()
                    results.append(error)
                finally:
                    db.session.remove()

        thread = threading.Thread(target=run)
        thread.start()
        self.addCleanup(lambda: thread.join(5))
        return thread

    def test_enrollment_wins_after_legacy_candidate_preparation(self):
        prepared, release = threading.Event(), threading.Event()
        results = []
        begin = review._begin_claim_outer_transaction

        def before_write():
            prepared.set()
            if not release.wait(4):
                raise RuntimeError("race test release timed out")
            begin()

        self.addCleanup(release.set)
        with patch.object(review, "_begin_claim_outer_transaction", side_effect=before_write):
            worker = self._thread(
                lambda user: review.claim_today_review(user, now=self.now), results
            )
            self.assertTrue(prepared.wait(3))
            with self.app.app_context():
                policy.enroll_student(
                    db.session.get(User, self.student_id), starts_at=self.now, now=self.now
                )
                db.session.commit()
            release.set()
            worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], review.VocabularyAutonomousReviewError)
        self.assertEqual(results[0].error, "review_policy_changed")
        with self.app.app_context():
            self.assertEqual(VocabularyReviewSession.query.count(), 0)
            self.assertTrue(policy.enabled_for(db.session.get(User, self.student_id), self.now))

    def test_legacy_claim_wins_and_enrollment_refuses_committed_active_session(self):
        locked, release, enrolling = threading.Event(), threading.Event(), threading.Event()
        claims, enrollments = [], []
        revalidate = review._revalidate_claim_candidates

        def under_lock(*args):
            locked.set()
            if not release.wait(4):
                raise RuntimeError("race test release timed out")
            return revalidate(*args)

        def enroll(user):
            enrolling.set()
            policy.enroll_student(user, starts_at=self.now, now=self.now)

        self.addCleanup(release.set)
        with patch.object(review, "_revalidate_claim_candidates", side_effect=under_lock):
            claimer = self._thread(
                lambda user: review.claim_today_review(user, now=self.now), claims
            )
            self.assertTrue(locked.wait(3))
            enroller = self._thread(enroll, enrollments)
            self.assertTrue(enrolling.wait(3))
            release.set()
            claimer.join(4)
            enroller.join(4)
        self.assertFalse(claimer.is_alive())
        self.assertFalse(enroller.is_alive())
        self.assertEqual(claims, ["committed"])
        self.assertEqual(len(enrollments), 1)
        self.assertIsInstance(enrollments[0], policy.PolicyConflict)
        with self.app.app_context():
            self.assertEqual(VocabularyReviewSession.query.filter_by(status="active").count(), 1)
            self.assertIsNone(policy.enabled_for(db.session.get(User, self.student_id), self.now))
