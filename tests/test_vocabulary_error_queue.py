"""Core state/capacity tests use only synthetic in-memory SQLite."""

import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from sqlalchemy import event

from models import (
    DictationBook,
    DictationWord,
    StudentVocabularyMastery,
    User,
    VocabularyErrorQueue,
    VocabularyPolicyAllocation,
    VocabularyPolicyCheckpoint,
    VocabularyPolicyEvent,
    VocabularyReviewItem,
    VocabularyReviewSession,
    db,
)
from services import vocabulary_error_queue as policy
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense


class VocabularyErrorPolicyCoreTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI=getattr(self, "database_uri", "sqlite://"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            VOCABULARY_ERROR_REVIEW_ENABLED=True,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.now = datetime(2026, 11, 1, 15, 58)  # Shanghai Nov 1 23:58
        self.user = User(
            username="core-student", password_hash="test", role="student", is_active=True
        )
        self.other = User(
            username="core-other", password_hash="test", role="student", is_active=True
        )
        db.session.add_all([self.user, self.other])
        db.session.flush()
        self.book = DictationBook(
            title="core synthetic", created_by=self.user.id, word_count=50, is_active=True
        )
        db.session.add(self.book)
        db.session.flush()
        self.words = []
        for index in range(50):
            word = DictationWord(
                book_id=self.book.id,
                sequence=index + 1,
                word=f"policyword{index}",
                translation=f"meaning {index}",
                core_meaning_zh=f"meaning {index}",
            )
            db.session.add(word)
            db.session.flush()
            ensure_word_sense(word)
            self.words.append(word)
        self.enrollment = policy.enroll_student(self.user, starts_at=self.now, now=self.now)
        db.session.commit()
        self.serial = 0

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def learn(
        self,
        index=0,
        *,
        correct=False,
        now=None,
        source=None,
        first=True,
        dimension="meaning_recall",
        user=None,
    ):
        self.serial += 1
        word = self.words[index]
        return policy.record_learning_answer(
            user or self.user,
            sense_id=word.sense_id,
            dimension=dimension,
            correct=correct,
            source_key=source or f"learning:{self.serial}",
            now=now or self.now,
            word_id=word.id,
            first_attempt=first,
        )

    def issue(self, entries, now, *, optional=False, user=None):
        user = user or self.user
        self.serial += 1
        session = VocabularyReviewSession(
            student_id=user.id,
            review_date=policy.local_date(now),
            status="active",
            session_token=f"session-{self.serial}",
            queue_token=f"queue-{self.serial}",
            started_at=now,
        )
        db.session.add(session)
        db.session.flush()
        items = []
        for index, entry in enumerate(entries):
            word = db.session.get(DictationWord, entry["word_id"])
            item = VocabularyReviewItem(
                session_id=session.id,
                student_id=user.id,
                book_id=word.book_id,
                word_id=word.id,
                sense_id=entry["sense_id"],
                dimension=entry["dimension"],
                due_at=now,
                queue_index=index,
                question_id=f"q-{session.id}-{index}",
                question_snapshot_json="{}",
                answer_payload_json="{}",
            )
            db.session.add(item)
            db.session.flush()
            items.append({"item_id": item.id, "entry": entry})
        allocations = policy.reserve_items(user, session.id, items, now=now, optional=optional)
        return session, allocations

    def answer_next(self, now, correct, *, index=0):
        entries = policy.plan_today(self.user, now=now)["entries"]
        self.assertTrue(entries)
        session, allocations = self.issue([entries[index]], now)
        row = allocations[0]
        policy.apply_review_answer(
            self.user,
            item_id=row.item_id,
            correct=correct,
            source_key=f"review:{row.item_id}",
            now=now,
        )
        session.status = "settled"
        db.session.commit()
        return row

    def queue(self, index=0):
        return VocabularyErrorQueue.query.filter_by(
            student_id=self.user.id, sense_id=self.words[index].sense_id, dimension="meaning_recall"
        ).one()

    def test_global_off_does_not_touch_new_tables_or_write(self):
        self.app.config[policy.FEATURE_FLAG] = False
        calls = []

        def trace(*args):
            calls.append(args[2])

        event.listen(db.engine, "before_cursor_execute", trace)
        try:
            stub = SimpleNamespace(id=123456)
            self.assertIsNone(policy.enabled_for(stub, self.now))
            self.assertEqual(policy.summary(stub, self.now), {"enabled": False})
            self.assertEqual(policy.plan_today(stub, now=self.now)["entries"], [])
            self.assertEqual(policy.refresh_day(stub, now=self.now), {"enabled": False})
            self.assertIsNone(
                policy.record_learning_answer(
                    stub,
                    sense_id=1,
                    dimension="form_recall",
                    correct=False,
                    source_key="off",
                    now=self.now,
                )
            )
            self.assertEqual(calls, [])
        finally:
            event.remove(db.engine, "before_cursor_execute", trace)

    def test_no_legacy_import_and_before_start_or_correction_ignored(self):
        for word in self.words:
            mastery = ensure_mastery(self.user, word, ensure_word_sense(word))
            mastery.meaning_recall_stage = 0
            mastery.meaning_recall_next_due_at = self.now - timedelta(days=30)
        db.session.commit()
        self.assertEqual(policy.summary(self.user, self.now)["mandatory_remaining"], 0)
        self.assertEqual(VocabularyErrorQueue.query.count(), 0)
        self.assertIsNone(self.learn(now=self.now - timedelta(seconds=1)))
        self.assertIsNone(self.learn(first=False))
        self.assertEqual(VocabularyErrorQueue.query.count(), 0)

    def test_error_due_next_natural_date_and_forgot_is_error(self):
        self.learn()
        self.assertEqual(self.queue().due_local_date.isoformat(), "2026-11-02")
        self.assertEqual(policy.plan_today(self.user, now=self.now)["entries"], [])
        self.assertEqual(
            len(policy.plan_today(self.user, now=self.now + timedelta(minutes=3))["entries"]), 1
        )
        word = self.words[1]
        policy.record_learning_answer(
            self.user,
            sense_id=word.sense_id,
            dimension="form_recall",
            correct=True,
            response_kind="forgot",
            source_key="forgot:1",
            now=self.now,
            word_id=word.id,
        )
        self.assertEqual(VocabularyErrorQueue.query.count(), 2)

    def test_learning_event_replay_and_cross_ability_key_reuse(self):
        self.learn(source="stable")
        version = self.queue().version
        self.assertTrue(self.learn(source="stable")["idempotent"])
        self.assertEqual(self.queue().version, version)
        with self.assertRaises(policy.PolicyConflict):
            self.learn(1, source="stable")
        self.assertEqual(VocabularyErrorQueue.query.count(), 1)

    def test_two_separated_review_successes_close_without_touching_mastery(self):
        word = self.words[0]
        mastery = ensure_mastery(self.user, word, ensure_word_sense(word))
        mastery.meaning_recall_stage = 3
        mastery.meaning_recall_next_due_at = self.now + timedelta(days=21)
        before = (mastery.meaning_recall_stage, mastery.meaning_recall_next_due_at)
        self.learn()
        first = self.answer_next(self.now + timedelta(days=1), True)
        queue = self.queue()
        self.assertEqual(queue.success_count, 1)
        self.assertEqual(queue.status, "active")
        self.assertEqual(
            policy.plan_today(self.user, now=self.now + timedelta(days=2))["entries"], []
        )
        policy.apply_review_answer(
            self.user,
            item_id=first.item_id,
            correct=False,
            source_key=f"review:{first.item_id}",
            now=self.now + timedelta(days=1),
        )
        self.assertEqual(queue.success_count, 1)
        self.answer_next(self.now + timedelta(days=3), True)
        self.assertEqual(self.queue().status, "closed")
        self.assertEqual(self.queue().closed_reason, "two_delayed_successes")
        self.assertEqual((mastery.meaning_recall_stage, mastery.meaning_recall_next_due_at), before)
        self.assertEqual(StudentVocabularyMastery.query.count(), 1)

    def test_learning_success_cannot_graduate_open_error(self):
        self.learn()
        self.answer_next(self.now + timedelta(days=1), True)
        self.learn(correct=True, now=self.now + timedelta(days=3))
        self.assertEqual(self.queue().success_count, 1)
        self.assertEqual(self.queue().status, "active")
        self.assertEqual(VocabularyPolicyCheckpoint.query.count(), 0)

    def test_three_failed_review_dates_pause_and_resume_after_seven_days(self):
        self.learn()
        self.assertEqual(self.queue().failure_streak, 0)
        for day in (1, 2, 3):
            self.answer_next(self.now + timedelta(days=day), False)
        queue = self.queue()
        self.assertEqual(queue.status, "paused")
        self.assertEqual(
            queue.pause_until_local_date, policy.local_date(self.now + timedelta(days=10))
        )
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="paused").count(), 1)
        self.learn(now=self.now + timedelta(days=4))
        self.assertEqual(queue.status, "paused")
        self.assertEqual(
            policy.plan_today(self.user, now=self.now + timedelta(days=9))["entries"], []
        )
        self.answer_next(self.now + timedelta(days=10), True)
        self.assertEqual(queue.status, "active")
        self.assertEqual(queue.failure_streak, 0)
        self.assertEqual(queue.success_count, 1)
        self.assertEqual(
            VocabularyPolicyEvent.query.filter_by(
                kind="reopened", detail_code="pause_elapsed"
            ).count(),
            1,
        )

    def test_new_error_resets_prior_success_and_reopens_closed(self):
        self.learn()
        self.answer_next(self.now + timedelta(days=1), True)
        self.answer_next(self.now + timedelta(days=3), False)
        self.assertEqual(self.queue().success_count, 0)
        self.answer_next(self.now + timedelta(days=4), True)
        self.answer_next(self.now + timedelta(days=6), True)
        self.assertEqual(self.queue().status, "closed")
        self.learn(now=self.now + timedelta(days=7))
        self.assertEqual(self.queue().status, "active")
        self.assertEqual(self.queue().success_count, 0)
        self.assertEqual(self.queue().failure_streak, 0)

    def test_checkpoint_once_per_cohort_four_slots_and_error_capacity_reuse(self):
        for index in range(10):
            self.learn(index, correct=True)
            self.learn(index, correct=True, now=self.now + timedelta(days=1))
        self.assertEqual(VocabularyPolicyCheckpoint.query.count(), 20)
        now = self.now + timedelta(days=7)
        for index in range(10, 40):
            self.learn(index, now=now - timedelta(days=1))
        planned = policy.plan_today(self.user, now=now)
        self.assertEqual(len(planned["entries"]), 20)
        self.assertEqual(sum(row["kind"] == "sample" for row in planned["entries"]), 4)
        self.assertEqual(planned["entries"], policy.plan_today(self.user, now=now)["entries"])
        session, allocations = self.issue(planned["entries"], now)
        self.assertEqual(len(allocations), 20)
        self.assertEqual(policy.plan_today(self.user, now=now)["entries"], [])
        self.assertEqual(policy.summary(self.user, now)["mandatory_remaining"], 20)
        for slot in allocations:
            policy.apply_review_answer(
                self.user,
                item_id=slot.item_id,
                correct=True,
                source_key=f"quota:{slot.item_id}",
                now=now,
            )
        session.status = "settled"
        db.session.commit()
        self.assertEqual(policy.summary(self.user, now)["mandatory_remaining"], 0)
        self.assertEqual(policy.summary(self.user, now)["mandatory_answered"], 20)

    def test_absent_checkpoint_uses_twenty_errors_and_sample_only_stays_four(self):
        for index in range(25):
            self.learn(index)
        self.assertEqual(
            len(policy.plan_today(self.user, now=self.now + timedelta(days=1))["entries"]), 20
        )
        for index in range(25, 40):
            self.learn(index, correct=True)
        planned = policy.plan_today(self.user, now=self.now + timedelta(days=7))
        self.assertEqual(sum(row["kind"] == "sample" for row in planned["entries"]), 4)
        VocabularyErrorQueue.query.update({"status": "closed"})
        db.session.flush()
        self.assertEqual(
            len(policy.plan_today(self.user, now=self.now + timedelta(days=7))["entries"]), 4
        )

    def test_today_first_and_overloaded_old_errors_transfer_without_deletion(self):
        today = self.now + timedelta(days=12)
        for index in range(10):
            self.learn(index)
        for index in range(10, 35):
            self.learn(index, now=today - timedelta(days=1))
        planned = policy.plan_today(self.user, now=today)
        self.assertTrue(planned["overloaded"])
        self.assertEqual(planned["overdue_transferred_count"], 10)
        expected = {word.sense_id for word in self.words[10:35]}
        self.assertTrue(all(row["sense_id"] in expected for row in planned["entries"]))
        self.assertEqual(
            VocabularyErrorQueue.query.filter_by(status="maintenance").count(), 0
        )  # pure read
        self.issue(planned["entries"], today)
        self.assertEqual(VocabularyErrorQueue.query.filter_by(status="maintenance").count(), 10)
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="overdue_overload").count(), 10)
        self.assertEqual(VocabularyErrorQueue.query.count(), 35)

    def test_old_errors_stay_mandatory_when_not_overloaded(self):
        self.learn()
        late = self.now + timedelta(days=12)
        planned = policy.plan_today(self.user, now=late)
        self.assertFalse(planned["overloaded"])
        self.assertEqual(len(planned["entries"]), 1)
        self.issue(planned["entries"], late)
        self.assertEqual(self.queue().status, "active")

    def test_unselected_checkpoints_become_missed_without_extra_samples(self):
        for index in range(10):
            self.learn(index, correct=True)
        sample_day = self.now + timedelta(days=7)
        planned = policy.plan_today(self.user, now=sample_day)
        self.assertEqual(len(planned["entries"]), 4)
        session, allocations = self.issue(planned["entries"], sample_day)
        for slot in allocations:
            policy.apply_review_answer(
                self.user,
                item_id=slot.item_id,
                correct=True,
                source_key=f"sample:{slot.item_id}",
                now=sample_day,
            )
        session.status = "settled"
        self.learn(15, now=sample_day)
        tomorrow = sample_day + timedelta(days=1)
        self.issue(policy.plan_today(self.user, now=tomorrow)["entries"], tomorrow)
        self.assertEqual(
            VocabularyPolicyCheckpoint.query.filter_by(interval_days=7, status="missed").count(), 6
        )
        self.assertEqual(
            VocabularyPolicyCheckpoint.query.filter_by(interval_days=30, status="pending").count(),
            10,
        )

    def test_sample_failure_enters_error_queue_next_day(self):
        self.learn(correct=True)
        sample_day = self.now + timedelta(days=7)
        self.answer_next(sample_day, False)
        self.assertEqual(self.queue().status, "active")
        self.assertEqual(self.queue().failure_streak, 0)
        self.assertEqual(
            self.queue().due_local_date, policy.local_date(sample_day) + timedelta(days=1)
        )

    def test_stale_plan_rejected_and_capacity_reserved_across_sessions(self):
        for index in range(25):
            self.learn(index)
        now = self.now + timedelta(days=1)
        old_plan = policy.plan_today(self.user, now=now)["entries"]
        self.learn(0, now=now)
        with self.assertRaises(policy.PolicyConflict):
            self.issue(
                [next(row for row in old_plan if row["sense_id"] == self.words[0].sense_id)], now
            )
        db.session.rollback()
        # Build a fresh committed test after rejected caller transaction.
        for index in range(25):
            self.learn(index, now=self.now)
        db.session.commit()
        entries = policy.plan_today(self.user, now=now)["entries"]
        self.issue(entries[:15], now)
        remaining = policy.plan_today(self.user, now=now)["entries"]
        self.assertEqual(len(remaining), 5)
        self.issue(remaining, now)
        self.assertEqual(VocabularyPolicyAllocation.query.count(), 20)

    def test_optional_cap_does_not_create_a_mandatory_gate(self):
        now = self.now + timedelta(days=1)
        entries = [
            {
                "queue_id": None,
                "checkpoint_id": None,
                "sense_id": word.sense_id,
                "dimension": "meaning_recall",
                "word_id": word.id,
                "kind": "maintenance",
                "version": None,
            }
            for word in self.words[:11]
        ]
        with self.assertRaises(policy.PolicyConflict):
            self.issue(entries, now, optional=True)
        db.session.rollback()
        self.issue(entries[:10], now, optional=True)
        self.assertEqual(policy.summary(self.user, now)["maintenance_remaining"], 0)
        self.assertEqual(policy.summary(self.user, now)["mandatory_remaining"], 0)

    def test_optional_foreign_queue_reference_rejected(self):
        policy.enroll_student(self.other, starts_at=self.now, now=self.now)
        self.learn(user=self.other)
        foreign = VocabularyErrorQueue.query.filter_by(student_id=self.other.id).one()
        foreign.status = "maintenance"
        db.session.commit()
        entry = {
            "queue_id": foreign.id,
            "checkpoint_id": None,
            "sense_id": self.words[0].sense_id,
            "dimension": "meaning_recall",
            "word_id": self.words[0].id,
            "kind": "maintenance",
            "version": foreign.version,
        }
        with self.assertRaises(policy.PolicyConflict):
            self.issue([entry], self.now + timedelta(days=1), optional=True)
        db.session.rollback()
        self.assertEqual(db.session.get(VocabularyErrorQueue, foreign.id).status, "maintenance")

    def test_reservation_and_answer_are_rolled_back_with_caller_transaction(self):
        self.learn()
        db.session.commit()
        now = self.now + timedelta(days=1)
        _, slots = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        policy.apply_review_answer(
            self.user,
            item_id=slots[0].item_id,
            correct=True,
            source_key="rolled-back-answer",
            now=now,
        )
        self.assertEqual(self.queue().success_count, 1)
        db.session.rollback()
        self.assertEqual(self.queue().success_count, 0)
        self.assertEqual(VocabularyPolicyAllocation.query.count(), 0)
        self.assertEqual(VocabularyReviewSession.query.count(), 0)
        self.assertEqual(
            VocabularyPolicyEvent.query.filter_by(source_key="rolled-back-answer").count(), 0
        )

    def test_review_source_key_cannot_be_reused_for_another_ability(self):
        self.learn(0)
        self.learn(1)
        now = self.now + timedelta(days=1)
        _, slots = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        policy.apply_review_answer(
            self.user, item_id=slots[0].item_id, correct=True, source_key="one-key", now=now
        )
        with self.assertRaises(policy.PolicyConflict):
            policy.apply_review_answer(
                self.user, item_id=slots[1].item_id, correct=True, source_key="one-key", now=now
            )
        self.assertEqual(slots[1].status, "reserved")

    def test_deferred_unanswerable_is_not_a_correct_answer(self):
        self.learn()
        now = self.now + timedelta(days=1)
        entries = policy.plan_today(self.user, now=now)["entries"]
        self.assertEqual(policy.defer_unusable_entries(self.user, entries, now=now), 1)
        self.assertEqual(self.queue().status, "maintenance")
        self.assertEqual(self.queue().success_count, 0)
        self.assertEqual(policy.summary(self.user, now)["mandatory_answered"], 0)
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="unanswerable").count(), 1)

    def test_stale_material_deferral_cannot_downgrade_new_error_cycle(self):
        self.learn()
        now = self.now + timedelta(days=1)
        entries = policy.plan_today(self.user, now=now)["entries"]
        self.learn(now=now + timedelta(seconds=1))
        with self.assertRaises(policy.PolicyConflict):
            policy.defer_unusable_entries(self.user, entries, now=now + timedelta(seconds=2))
        self.assertEqual(self.queue().status, "active")
        self.assertEqual(self.queue().due_local_date, policy.local_date(now) + timedelta(days=1))
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="unanswerable").count(), 0)

    def test_skipping_old_frozen_item_preserves_new_future_due_error(self):
        self.learn()
        now = self.now + timedelta(days=1)
        _, slots = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        self.learn(now=now + timedelta(seconds=1))
        self.assertEqual(policy.mark_skipped(self.user, item_ids=[slots[0].item_id], now=now), 1)
        self.assertEqual(slots[0].status, "skipped")
        self.assertEqual(self.queue().status, "active")
        self.assertEqual(self.queue().due_local_date, policy.local_date(now) + timedelta(days=1))
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="unanswerable").count(), 0)

    def test_frozen_skip_consumes_capacity_but_never_success(self):
        self.learn()
        now = self.now + timedelta(days=1)
        _, slots = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        self.assertEqual(policy.mark_skipped(self.user, item_ids=[slots[0].item_id], now=now), 1)
        self.assertEqual(policy.mark_skipped(self.user, item_ids=[slots[0].item_id], now=now), 0)
        self.assertEqual(self.queue().success_count, 0)
        self.assertEqual(self.queue().status, "maintenance")
        self.assertEqual(policy.summary(self.user, now)["mandatory_answered"], 1)

    def test_enrollment_refuses_active_legacy_session(self):
        self.serial += 1
        session = VocabularyReviewSession(
            student_id=self.other.id,
            review_date=policy.local_date(self.now),
            status="active",
            session_token="legacy",
            queue_token="legacy",
            started_at=self.now,
        )
        db.session.add(session)
        db.session.flush()
        with self.assertRaises(policy.PolicyConflict):
            policy.enroll_student(self.other, starts_at=self.now, now=self.now)

    def test_cross_day_frozen_slot_cannot_count_for_new_day(self):
        self.learn()
        now = self.now + timedelta(days=1)
        _, allocations = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        with self.assertRaises(policy.PolicyConflict):
            policy.apply_review_answer(
                self.user,
                item_id=allocations[0].item_id,
                correct=True,
                source_key="too-late",
                now=now + timedelta(days=1),
            )
        self.assertEqual(self.queue().success_count, 0)

    def test_empty_claim_refresh_persists_transfers_without_answer_credit(self):
        for index in range(21):
            self.learn(index)
        now = self.now + timedelta(days=10)
        plan = policy.plan_today(self.user, now=now)
        self.assertEqual(plan["entries"], [])
        self.assertEqual(plan["overdue_transferred_count"], 21)
        refreshed = policy.refresh_day(self.user, now=now)
        self.assertEqual(refreshed["maintenance_count"], 21)
        self.assertEqual(refreshed["mandatory_answered"], 0)
        self.assertEqual(refreshed["overdue_transferred_count"], 21)
        self.assertEqual(refreshed["overdue_transferred_today"], 21)
        self.assertEqual(refreshed["overdue_transfer_pending_count"], 0)
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="overdue_overload").count(), 21)
        policy.refresh_day(self.user, now=now)
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="overdue_overload").count(), 21)
        self.assertEqual(len(policy.plan_today(self.user, now=now, optional=True)["entries"]), 10)

    def test_learning_error_after_claim_does_not_count_same_day_review_success(self):
        self.learn()
        now = self.now + timedelta(days=1)
        _, slots = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        self.learn(now=now + timedelta(seconds=1))
        policy.apply_review_answer(
            self.user,
            item_id=slots[0].item_id,
            correct=True,
            source_key="after-new-task-error",
            now=now + timedelta(seconds=2),
        )
        self.assertEqual(slots[0].status, "answered")
        self.assertEqual(self.queue().success_count, 0)
        self.assertEqual(self.queue().failure_streak, 0)
        self.assertIsNone(self.queue().last_attempt_local_date)
        self.assertEqual(self.queue().due_local_date, policy.local_date(now) + timedelta(days=1))

    def test_configurable_daily_sample_and_maintenance_limits(self):
        self.app.config.update(
            VOCABULARY_ERROR_REVIEW_DAILY_LIMIT="3",
            VOCABULARY_ERROR_REVIEW_SAMPLE_LIMIT=1,
            VOCABULARY_ERROR_REVIEW_MAINTENANCE_LIMIT=2,
        )
        for index in range(3):
            self.learn(index, correct=True)
        for index in range(3, 8):
            self.learn(index, now=self.now + timedelta(days=6))
        now = self.now + timedelta(days=7)
        plan = policy.plan_today(self.user, now=now)
        self.assertEqual(len(plan["entries"]), 3)
        self.assertEqual(sum(entry["kind"] == "sample" for entry in plan["entries"]), 1)
        self.assertEqual(plan["mandatory_limit"], 3)
        self.assertEqual(plan["maintenance_remaining"], 2)
        self.issue(plan["entries"], now)
        self.assertEqual(policy.plan_today(self.user, now=now)["entries"], [])
        for index in range(10, 13):
            self.learn(index, now=now)
            self.queue(index).status = "maintenance"
        optional = policy.plan_today(self.user, now=now + timedelta(days=1), optional=True)
        self.assertEqual(len(optional["entries"]), 2)

    def test_configurable_success_failure_pause_and_overdue_intervals(self):
        self.app.config.update(
            VOCABULARY_ERROR_REVIEW_SUCCESS_INTERVAL_DAYS=3,
            VOCABULARY_ERROR_REVIEW_FAILURE_LIMIT=2,
            VOCABULARY_ERROR_REVIEW_PAUSE_DAYS=4,
            VOCABULARY_ERROR_REVIEW_OVERDUE_DAYS=5,
        )
        self.learn()
        self.answer_next(self.now + timedelta(days=1), True)
        self.assertEqual(
            self.queue().due_local_date, policy.local_date(self.now) + timedelta(days=4)
        )
        self.assertEqual(
            policy.plan_today(self.user, now=self.now + timedelta(days=3))["entries"], []
        )
        self.answer_next(self.now + timedelta(days=4), False)
        self.answer_next(self.now + timedelta(days=5), False)
        self.assertEqual(self.queue().status, "paused")
        self.assertEqual(
            self.queue().pause_until_local_date, policy.local_date(self.now) + timedelta(days=9)
        )
        self.app.config.update(
            VOCABULARY_ERROR_REVIEW_DAILY_LIMIT=1, VOCABULARY_ERROR_REVIEW_SAMPLE_LIMIT=0
        )
        self.learn(1)
        self.learn(2)
        plan = policy.plan_today(self.user, now=self.now + timedelta(days=7))
        self.assertEqual(plan["overdue_transferred_count"], 2)

    def test_invalid_policy_parameters_rejected_and_off_still_short_circuits(self):
        for bad in (True, 1.5, "twenty", 0, -1):
            with self.subTest(value=bad):
                self.app.config["VOCABULARY_ERROR_REVIEW_DAILY_LIMIT"] = bad
                with self.assertRaises(ValueError):
                    policy.summary(self.user, self.now)
        self.app.config.update(
            VOCABULARY_ERROR_REVIEW_DAILY_LIMIT=3, VOCABULARY_ERROR_REVIEW_SAMPLE_LIMIT=4
        )
        with self.assertRaisesRegex(ValueError, "sample_limit_exceeds"):
            policy.summary(self.user, self.now)
        self.app.config[policy.FEATURE_FLAG] = False
        self.assertEqual(policy.summary(self.user, self.now), {"enabled": False})


class VocabularyErrorPolicyConcurrencyTest(unittest.TestCase):
    learn = VocabularyErrorPolicyCoreTest.learn
    issue = VocabularyErrorPolicyCoreTest.issue
    queue = VocabularyErrorPolicyCoreTest.queue

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="vocab-policy-core-")
        self.database_uri = "sqlite:///" + str(Path(self.directory.name) / "test.sqlite")
        VocabularyErrorPolicyCoreTest.setUp(self)

    def tearDown(self):
        VocabularyErrorPolicyCoreTest.tearDown(self)
        self.directory.cleanup()

    def run_contending(self, first_call, second_call):
        first_locked = threading.Event()
        second_waiting = threading.Event()
        release = threading.Event()
        errors, results = [], []
        original_lock = policy._lock_enrollment

        def lock(user, now):
            value = original_lock(user, now)
            if threading.current_thread().name == "policy-first":
                first_locked.set()
                if not release.wait(3):
                    raise TimeoutError("test_first_writer_not_released")
            return value

        def trace(_connection, _cursor, statement, _parameters, _context, _many):
            if threading.current_thread().name == "policy-second" and statement.startswith(
                "UPDATE vocabulary_review_policy_enrollment"
            ):
                second_waiting.set()

        def run(call):
            with self.app.app_context():
                try:
                    results.append(call())
                    db.session.commit()
                except BaseException as error:
                    db.session.rollback()
                    errors.append(error)
                finally:
                    db.session.remove()

        engine = db.engine
        event.listen(engine, "before_cursor_execute", trace)
        first = threading.Thread(target=run, args=(first_call,), name="policy-first")
        second = threading.Thread(target=run, args=(second_call,), name="policy-second")
        try:
            with patch.object(policy, "_lock_enrollment", lock):
                first.start()
                self.assertTrue(first_locked.wait(3))
                second.start()
                self.assertTrue(second_waiting.wait(3))
                release.set()
                first.join(4)
                second.join(4)
                self.assertFalse(first.is_alive())
                self.assertFalse(second.is_alive())
        finally:
            release.set()
            if first.ident is not None:
                first.join(4)
            if second.ident is not None:
                second.join(4)
            event.remove(engine, "before_cursor_execute", trace)
        db.session.expire_all()
        return results, errors

    def test_two_connections_same_answer_advances_queue_once(self):
        self.learn()
        now = self.now + timedelta(days=1)
        _, slots = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        item_id, student_id = slots[0].item_id, self.user.id
        db.session.commit()

        def answer():
            return policy.apply_review_answer(
                db.session.get(User, student_id),
                item_id=item_id,
                correct=True,
                source_key="same-concurrent-answer",
                now=now,
            )

        results, errors = self.run_contending(answer, answer)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(result["idempotent"] for result in results), [False, True])
        self.assertEqual(self.queue().success_count, 1)
        self.assertEqual(
            VocabularyPolicyEvent.query.filter_by(source_key="same-concurrent-answer").count(), 1
        )

    def test_two_connections_cannot_reserve_thirty_daily_slots(self):
        for index in range(30):
            self.learn(index)
        now = self.now + timedelta(days=1)
        entries = policy.plan_today(self.user, now=now)["entries"]
        prepared = []
        # Existing unbound session fixtures isolate the daily-slot transaction
        # from the independent old claim-key guard covered by adapter tests.
        for group in (entries[:15], entries[5:20]):
            self.serial += 1
            session = VocabularyReviewSession(
                student_id=self.user.id,
                review_date=policy.local_date(now),
                status="active",
                session_token=f"concurrent-{self.serial}",
                queue_token="synthetic",
                started_at=now,
            )
            db.session.add(session)
            db.session.flush()
            items = []
            for index, entry in enumerate(group):
                word = db.session.get(DictationWord, entry["word_id"])
                item = VocabularyReviewItem(
                    session_id=session.id,
                    student_id=self.user.id,
                    book_id=word.book_id,
                    word_id=word.id,
                    sense_id=word.sense_id,
                    dimension=entry["dimension"],
                    due_at=now,
                    queue_index=index,
                    question_id=f"concurrent-{session.id}-{index}",
                    question_snapshot_json="{}",
                    answer_payload_json="{}",
                )
                db.session.add(item)
                db.session.flush()
                items.append({"item_id": item.id, "entry": entry})
            prepared.append((session.id, items))
        student_id = self.user.id
        db.session.commit()

        def reserve(index):
            session_id, items = prepared[index]
            return policy.reserve_items(
                db.session.get(User, student_id), session_id, items, now=now
            )

        results, errors = self.run_contending(lambda: reserve(0), lambda: reserve(1))
        self.assertEqual(len(results), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], policy.PolicyConflict)
        self.assertEqual(VocabularyPolicyAllocation.query.count(), 15)


if __name__ == "__main__":
    unittest.main()
