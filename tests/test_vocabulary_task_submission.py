"""Real group settlement keeps Task and PlanItem atomic and replay-safe."""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from flask import Flask

from models import (
    DictationBook,
    DictationRecord,
    DictationWord,
    PlanEvidence,
    PlanItem,
    StudentProfile,
    StudyPlan,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyTaskSettlement,
    db,
)
from services.task_date_gate import beijing_today
from services.vocabulary_group_learning import (
    VocabularyGroupLearningError,
    get_vocabulary_group_queue,
    mark_familiarity_viewed,
    submit_vocabulary_group_answer,
)
from services.vocabulary_task_submission import settle_vocabulary_group_submission


class VocabularyTaskSubmissionTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="synthetic-settlement",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(
            username="submission-student", password_hash="test", role="student", is_active=True
        )
        self.other = User(
            username="submission-other", password_hash="test", role="student", is_active=True
        )
        db.session.add_all([self.user, self.other])
        db.session.flush()
        self.profile = StudentProfile(user_id=self.user.id, full_name="合成结算学生")
        other_profile = StudentProfile(user_id=self.other.id, full_name="另一合成学生")
        db.session.add_all([self.profile, other_profile])
        db.session.flush()
        book = DictationBook(title="合成听力词书", word_count=1, created_by=self.user.id)
        db.session.add(book)
        db.session.flush()
        db.session.add(DictationWord(book_id=book.id, sequence=1, word="focus", translation="集中"))
        plan = StudyPlan(
            student_id=self.profile.id, plan_date=beijing_today(), created_by=self.user.id
        )
        db.session.add(plan)
        db.session.flush()
        self.item = PlanItem(
            plan_id=plan.id,
            exam_system="雅思",
            module="词汇",
            task_name="词汇任务",
            actual_seconds=10,
        )
        db.session.add(self.item)
        db.session.flush()
        self.task = Task(
            student_name=self.profile.full_name,
            date=beijing_today(),
            category="词汇",
            created_by=self.user.id,
            plan_item_id=self.item.id,
            dictation_book_id=book.id,
            vocabulary_goal="listening",
            dictation_mode="audio_to_en",
            dictation_word_start=1,
            dictation_word_end=1,
        )
        db.session.add(self.task)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def _complete_learning(self):
        queue = get_vocabulary_group_queue(self.user, self.task.id, supports_correction=True)
        while queue["phase"] == "familiarity":
            word = next(row for row in queue["familiarity"] if not row["viewed"])
            queue = mark_familiarity_viewed(
                self.user,
                self.task.id,
                {"queue_token": queue["queue_token"], "word_id": word["word_id"]},
            )
        for index in range(10):
            if queue["completed"]:
                break
            question = queue["current_question"]
            stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
            answer = json.loads(stored.answer_payload_json)
            payload = {
                key: question[key]
                for key in (
                    "learning_question_id",
                    "queue_item_id",
                    "question_id",
                    "word_id",
                    "sense_id",
                    "dimension",
                )
            }
            payload.update(
                task_id=self.task.id,
                queue_token=queue["queue_token"],
                attempt_id=f"shared-submission:{index}",
                retry=bool(queue["retry"]),
                input_mode="native",
                supports_correction=True,
                answer=answer.get("answer_option_id") or answer["answer"],
            )
            submit_vocabulary_group_answer(self.user, payload)
            queue = get_vocabulary_group_queue(self.user, self.task.id, supports_correction=True)
        self.assertTrue(queue["completed"])
        db.session.commit()
        return queue["queue_token"]

    def test_first_settlement_syncs_once_and_replay_cannot_add_effects(self):
        token = self._complete_learning()
        original_answers = DictationRecord.query.count()
        result = settle_vocabulary_group_submission(
            self.user,
            self.task.id,
            {
                "queue_token": token,
                "duration_seconds": 30,
                "note": "初次结算",
                "evidence_files": ["/uploads/first.mp3"],
            },
            uploader_id=self.user.id,
        )
        db.session.commit()
        self.assertEqual((result["accuracy"], result["total_count"]), (100.0, 2))
        self.assertEqual(
            (self.task.status, self.task.actual_seconds, self.task.completion_rate),
            ("done", 30, 100),
        )
        self.assertEqual((self.item.student_status, self.item.actual_seconds), ("submitted", 30))
        self.assertEqual(json.loads(self.item.resource_metadata)["vocabulary_goal"], "listening")
        self.assertEqual(PlanEvidence.query.one().uploader_id, self.user.id)
        before = (
            self.task.submitted_at,
            self.item.submitted_at,
            self.item.updated_at,
        )
        # Recovery also works after the assignment's deadline without reopening it.
        self.item.plan.plan_date = beijing_today() - timedelta(days=2)
        db.session.commit()
        repeated = settle_vocabulary_group_submission(
            self.user,
            self.task.id,
            {
                "queue_token": token,
                "duration_seconds": 900,
                "note": "不得覆盖",
                "evidence_files": ["/uploads/second.mp3"],
            },
            uploader_id=self.user.id,
        )
        self.assertTrue(repeated.pop("already_settled"))
        self.assertEqual(repeated, result)
        self.assertFalse(db.session.new or db.session.dirty)
        db.session.commit()
        self.assertEqual(
            (self.task.actual_seconds, self.item.actual_seconds, self.item.student_comment),
            (30, 30, "初次结算"),
        )
        self.assertEqual(
            (
                self.task.submitted_at,
                self.item.submitted_at,
                self.item.updated_at,
            ),
            before,
        )
        self.assertEqual(
            (
                PlanEvidence.query.count(),
                VocabularyTaskSettlement.query.count(),
                VocabularyLearningFlow.query.count(),
                DictationRecord.query.count(),
            ),
            (1, 1, 1, original_answers),
        )

    def test_read_only_replay_still_requires_owner_and_frozen_queue_token(self):
        token = self._complete_learning()
        settle_vocabulary_group_submission(
            self.user, self.task.id, {"queue_token": token}, uploader_id=self.user.id
        )
        db.session.commit()
        for user, payload, error in [
            (self.other, {"queue_token": token}, "forbidden"),
            (self.user, {}, "queue_token_required"),
            (self.user, {"queue_token": "wrong"}, "queue_changed"),
        ]:
            with (
                self.subTest(error=error),
                self.assertRaises(VocabularyGroupLearningError) as raised,
            ):
                settle_vocabulary_group_submission(user, self.task.id, payload, uploader_id=user.id)
            self.assertEqual(raised.exception.error, error)
        self.assertEqual(VocabularyTaskSettlement.query.count(), 1)

    def test_projection_failure_rolls_back_completion_and_settlement(self):
        token = self._complete_learning()
        with patch(
            "services.vocabulary_task_submission.sync_plan_item_from_task_submission",
            side_effect=RuntimeError("synthetic sync failure"),
        ):
            with self.assertRaises(RuntimeError):
                settle_vocabulary_group_submission(
                    self.user,
                    self.task.id,
                    {"queue_token": token, "duration_seconds": 35},
                    uploader_id=self.user.id,
                )
        db.session.rollback()
        self.assertEqual(VocabularyTaskSettlement.query.count(), 0)
        self.assertNotEqual(self.task.status, "done")
        self.assertEqual(self.item.student_status, "pending")
        result = settle_vocabulary_group_submission(
            self.user,
            self.task.id,
            {"queue_token": token, "duration_seconds": 35},
            uploader_id=self.user.id,
        )
        db.session.commit()
        self.assertEqual(result["accuracy"], 100)
        self.assertEqual((self.item.actual_seconds, self.task.actual_seconds), (35, 35))

    def test_incomplete_learning_cannot_mark_either_record_done(self):
        queue = get_vocabulary_group_queue(self.user, self.task.id, supports_correction=True)
        db.session.commit()
        with self.assertRaises(VocabularyGroupLearningError) as raised:
            settle_vocabulary_group_submission(
                self.user,
                self.task.id,
                {"queue_token": queue["queue_token"]},
                uploader_id=self.user.id,
            )
        self.assertEqual(raised.exception.error, "group_flow_incomplete")
        self.assertNotEqual(self.task.status, "done")
        self.assertEqual(self.item.student_status, "pending")
        self.assertEqual(VocabularyTaskSettlement.query.count(), 0)

    def test_race_loser_with_already_synced_result_does_not_append_evidence(self):
        token = self._complete_learning()
        result = settle_vocabulary_group_submission(
            self.user,
            self.task.id,
            {
                "queue_token": token,
                "duration_seconds": 30,
                "evidence_files": ["/uploads/first.png"],
            },
            uploader_id=self.user.id,
        )
        db.session.commit()
        # Simulate only the unique-settlement race: the initial lookup missed,
        # then finalize recovered the winner after rollback with refreshed rows.
        with (
            patch("services.vocabulary_task_submission.VocabularyTaskSettlement.query") as query,
            patch(
                "services.vocabulary_task_submission.finalize_vocabulary_group_task",
                return_value=result,
            ),
        ):
            query.filter_by.return_value.first.return_value = None
            settle_vocabulary_group_submission(
                self.user,
                self.task.id,
                {
                    "queue_token": token,
                    "duration_seconds": 900,
                    "evidence_files": ["/uploads/late.png"],
                },
                uploader_id=self.user.id,
            )
        db.session.commit()
        self.assertEqual(PlanEvidence.query.count(), 1)
        self.assertEqual(self.item.actual_seconds, 30)

    def test_cancelled_task_is_rejected_even_when_already_in_identity_map(self):
        token = self._complete_learning()
        settle_vocabulary_group_submission(
            self.user, self.task.id, {"queue_token": token}, uploader_id=self.user.id
        )
        db.session.commit()
        self.task.cancelled_at = datetime(2026, 11, 26, 12)
        db.session.flush()
        self.assertIs(db.session.get(Task, self.task.id), self.task)
        with self.assertRaises(VocabularyGroupLearningError) as raised:
            settle_vocabulary_group_submission(
                self.user, self.task.id, {"queue_token": token}, uploader_id=self.user.id
            )
        self.assertEqual(raised.exception.error, "task_not_found")
        self.assertEqual(VocabularyTaskSettlement.query.count(), 1)
