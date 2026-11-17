"""Graduation sampling is a new dated opportunity, never reconstructed history."""

import unittest
from datetime import timedelta
from hashlib import sha256

from models import VocabularyPolicyCheckpoint, VocabularyPolicyEvent, db
from services import vocabulary_error_queue as policy
from tests import test_vocabulary_error_queue as fixtures


class GraduationCheckpointTest(unittest.TestCase):
    setUp = fixtures.VocabularyErrorPolicyCoreTest.setUp
    tearDown = fixtures.VocabularyErrorPolicyCoreTest.tearDown
    learn = fixtures.VocabularyErrorPolicyCoreTest.learn
    issue = fixtures.VocabularyErrorPolicyCoreTest.issue
    queue = fixtures.VocabularyErrorPolicyCoreTest.queue
    answer_next = fixtures.VocabularyErrorPolicyCoreTest.answer_next

    def graduate(self, index=0, *, offset=0):
        self.learn(index, now=self.now + timedelta(days=offset))
        self.answer_next(self.now + timedelta(days=offset + 1), True)
        return self.answer_next(self.now + timedelta(days=offset + 3), True)

    def test_first_correct_sources_and_selection_order_remain_compatible(self):
        self.learn(correct=True)
        rows = VocabularyPolicyCheckpoint.query.order_by(
            VocabularyPolicyCheckpoint.interval_days
        ).all()
        self.assertEqual([row.interval_days for row in rows], [7, 30])
        for row in rows:
            self.assertEqual(
                (row.source_kind, row.source_key, row.origin_event_id),
                ("first_correct", "initial", None),
            )
            prior_key = f"{row.student_id}:{row.cohort_key}:{row.sense_id}:{row.dimension}:{row.interval_days}"
            self.assertEqual(row.selection_key, sha256(prior_key.encode()).hexdigest())

    def test_graduation_creates_one_d7_linked_to_immutable_closed_event(self):
        slot = self.graduate()
        row = VocabularyPolicyCheckpoint.query.one()
        event = db.session.get(VocabularyPolicyEvent, row.origin_event_id)
        self.assertEqual((row.source_kind, row.interval_days), ("graduation", 7))
        self.assertEqual(row.source_key, f"graduation:{event.id}")
        self.assertEqual((event.kind, event.detail_code), ("closed", "two_delayed_successes"))
        self.assertEqual(row.anchor_at, self.now + timedelta(days=3))
        self.assertEqual(row.due_local_date, policy.local_date(self.now) + timedelta(days=10))
        policy.apply_review_answer(
            self.user,
            item_id=slot.item_id,
            correct=True,
            source_key=f"review:{slot.item_id}",
            now=self.now + timedelta(days=3),
        )
        self.assertEqual(VocabularyPolicyCheckpoint.query.count(), 1)

    def test_repeated_graduations_have_independent_cycles_and_no_false_reset(self):
        self.graduate()
        self.graduate(offset=4)
        rows = VocabularyPolicyCheckpoint.query.order_by(VocabularyPolicyCheckpoint.id).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row.source_key for row in rows}), 2)
        self.assertEqual(len({row.origin_event_id for row in rows}), 2)
        self.assertEqual(
            [row.due_local_date for row in rows],
            [policy.local_date(self.now) + timedelta(days=n) for n in (10, 14)],
        )
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="success_reset").count(), 0)

    def test_graduation_sample_wrong_reopens_only_ability_and_preserves_source(self):
        self.graduate()
        row = VocabularyPolicyCheckpoint.query.one()
        origin = row.origin_event_id
        self.answer_next(self.now + timedelta(days=10), False)
        self.assertEqual(
            (row.status, row.source_kind, row.origin_event_id), ("answered", "graduation", origin)
        )
        self.assertEqual(self.queue().status, "active")
        self.assertEqual(
            self.queue().due_local_date, policy.local_date(self.now) + timedelta(days=11)
        )
        self.assertEqual(self.queue().success_count, 0)
        answer = VocabularyPolicyEvent.query.filter_by(checkpoint_id=row.id, source="review").one()
        self.assertFalse(answer.is_correct)
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="success_reset").count(), 0)

    def test_graduation_samples_share_four_slots_and_unselected_are_missed(self):
        for index in range(5):
            self.graduate(index)
        now = self.now + timedelta(days=10)
        plan = policy.plan_today(self.user, now=now)
        self.assertEqual(len(plan["entries"]), 4)
        self.assertTrue(all(entry["kind"] == "sample" for entry in plan["entries"]))
        _, slots = self.issue(plan["entries"], now)
        for slot in slots:
            policy.apply_review_answer(
                self.user,
                item_id=slot.item_id,
                correct=True,
                source_key=f"sample:{slot.item_id}",
                now=now,
            )
        policy.refresh_day(self.user, now=now + timedelta(days=1))
        self.assertEqual(
            VocabularyPolicyCheckpoint.query.filter_by(
                source_kind="graduation", status="answered"
            ).count(),
            4,
        )
        self.assertEqual(
            VocabularyPolicyCheckpoint.query.filter_by(
                source_kind="graduation", status="missed"
            ).count(),
            1,
        )

    def test_overlapping_first_correct_and_graduation_sources_use_one_ability_slot(self):
        self.enrollment.starts_at = self.now - timedelta(days=30)
        db.session.commit()
        self.learn(correct=True, now=self.now - timedelta(days=20))
        self.graduate()
        now = self.now + timedelta(days=10)
        due = VocabularyPolicyCheckpoint.query.filter_by(
            due_local_date=policy.local_date(now)
        ).all()
        self.assertEqual({row.source_kind for row in due}, {"first_correct", "graduation"})
        plan = policy.plan_today(self.user, now=now)
        self.assertEqual(len(plan["entries"]), 1)
        self.answer_next(now, True)
        policy.refresh_day(self.user, now=now + timedelta(days=1))
        self.assertEqual(sorted(row.status for row in due), ["answered", "missed"])

    def test_reset_event_counts_only_positive_progress_to_zero_and_is_idempotent(self):
        self.learn()
        self.learn(source="another-zero-error")
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="success_reset").count(), 0)
        self.answer_next(self.now + timedelta(days=1), True)
        slot = self.answer_next(self.now + timedelta(days=3), False)
        policy.apply_review_answer(
            self.user,
            item_id=slot.item_id,
            correct=False,
            source_key=f"review:{slot.item_id}",
            now=self.now + timedelta(days=3),
        )
        self.answer_next(self.now + timedelta(days=4), False)
        events = VocabularyPolicyEvent.query.filter_by(kind="success_reset").all()
        self.assertEqual([event.detail_code for event in events], ["review_error"])

    def test_learning_error_reset_has_distinct_source_and_same_key_replay_counts_once(self):
        self.learn()
        self.answer_next(self.now + timedelta(days=1), True)
        for _ in range(2):
            self.learn(now=self.now + timedelta(days=2), source="fresh-learning-error")
        events = VocabularyPolicyEvent.query.filter_by(kind="success_reset").all()
        self.assertEqual([event.detail_code for event in events], ["learning_error"])

    def test_graduation_checkpoint_and_event_roll_back_with_answer(self):
        self.learn()
        self.answer_next(self.now + timedelta(days=1), True)
        now = self.now + timedelta(days=3)
        _, slots = self.issue(policy.plan_today(self.user, now=now)["entries"], now)
        item_id = slots[0].item_id
        db.session.commit()
        policy.apply_review_answer(
            self.user, item_id=item_id, correct=True, source_key="rolled-back", now=now
        )
        self.assertEqual(
            VocabularyPolicyCheckpoint.query.filter_by(source_kind="graduation").count(), 1
        )
        db.session.rollback()
        self.assertEqual(self.queue().status, "active")
        self.assertEqual(self.queue().success_count, 1)
        self.assertEqual(VocabularyPolicyCheckpoint.query.count(), 0)
        self.assertEqual(VocabularyPolicyEvent.query.filter_by(kind="closed").count(), 0)

    def test_off_does_not_create_opportunities_or_import_old_closed_state(self):
        self.app.config[policy.FEATURE_FLAG] = False
        self.learn(correct=True)
        self.learn(correct=False)
        self.assertEqual(VocabularyPolicyCheckpoint.query.count(), 0)
        self.assertEqual(VocabularyPolicyEvent.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
