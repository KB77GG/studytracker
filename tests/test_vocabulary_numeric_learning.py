"""Selected numeric ranges through actual task queues; no production database."""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from models import (
    DictationRecord,
    DictationWord,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyTaskReview,
    db,
)
from services.vocabulary_group_learning import _grade_question, get_vocabulary_group_queue
from services.vocabulary_mastery import (
    _grade_recall,
    ensure_mastery,
    ensure_word_sense,
    get_vocabulary_task_queue,
)
from tests import test_vocabulary_group_learning as group_fixture


class NumericLearningTest(unittest.TestCase):
    # Reuse only fixture/helpers, not the base suite's test methods.
    setUp = group_fixture.VocabularyGroupLearningTest.setUp
    tearDown = group_fixture.VocabularyGroupLearningTest.tearDown
    _task = group_fixture.VocabularyGroupLearningTest._task
    _user = group_fixture.VocabularyGroupLearningTest._user
    _view_group = group_fixture.VocabularyGroupLearningTest._view_group
    _answer_for_current = group_fixture.VocabularyGroupLearningTest._answer_for_current
    _finish_flow = group_fixture.VocabularyGroupLearningTest._finish_flow

    def _numeric_words(self):
        values = ["020 7946 0018", "12 March 2026", "£12.50", "1.23"]
        for word_id, value in zip(self.word_ids, values, strict=True):
            word = db.session.get(DictationWord, word_id)
            word.word = value
            for field in (
                "translation",
                "core_meaning_zh",
                "usage_pattern",
                "example_en",
                "example_zh",
            ):
                setattr(word, field, "")
        db.session.commit()
        return values

    def test_numeric_only_selected_subset_finishes_with_nonempty_denominator(self):
        with self.app.app_context():
            values = self._numeric_words()
            now = datetime(2026, 8, 8, 12)
            task = self._task("listening", end=3, task_date=now.date())
            task.dictation_word_start = 2
            db.session.commit()
            queue = get_vocabulary_group_queue(self._user(), task.id, now=now)
            self.assertEqual(queue["total_word_count"], 2)
            self.assertEqual(queue["base_progress_total"], 2)
            self.assertEqual({entry["word"] for entry in queue["familiarity"]}, set(values[1:3]))
            self.assertTrue(
                all(entry["audio_tts_url"].endswith("?numeric=1") for entry in queue["familiarity"])
            )
            questions = VocabularyLearningQuestion.query.filter_by(task_id=task.id).all()
            self.assertEqual({q.word_id for q in questions}, set(self.word_ids[1:3]))
            self.assertEqual({q.dimension for q in questions}, {"audio_form_recall"})
            for q in questions:
                public, private = json.loads(q.question_snapshot_json), json.loads(
                    q.answer_payload_json
                )
                self.assertEqual(public["answer_type"], "numeric")
                self.assertNotIn(private["answer"], json.dumps(public))
                self.assertNotIn("tts_text", json.dumps(public))
                self.assertEqual(private["numeric_rule_version"], 1)
            completed = self._finish_flow(self._user(), task, now=now)
            self.assertTrue(completed["completed"])
            self.assertEqual(completed["base_progress_completed"], 2)
            records = DictationRecord.query.filter_by(task_id=task.id).all()
            self.assertEqual(len(records), 2)
            self.assertTrue(all(record.is_correct for record in records))
            self.assertEqual([db.session.get(DictationWord, i).word for i in self.word_ids], values)

    def test_mixed_task_preserves_english_and_skips_only_missing_meaning(self):
        with self.app.app_context():
            word = db.session.get(DictationWord, self.word_ids[0])
            word.word, word.translation, word.core_meaning_zh = "0217856361", "", ""
            task = self._task("listening", end=2)
            queue = get_vocabulary_group_queue(self._user(), task.id)
            self.assertEqual(queue["total_word_count"], 2)
            self.assertEqual(queue["base_progress_total"], 3)
            rows = VocabularyLearningQuestion.query.filter_by(task_id=task.id).all()
            self.assertEqual(
                {r.dimension for r in rows if r.word_id == word.id}, {"audio_form_recall"}
            )
            self.assertEqual(
                {json.loads(r.answer_payload_json)["answer_type"] for r in rows},
                {"numeric", "english", "chinese"},
            )
            self.assertTrue(self._finish_flow(self._user(), task)["completed"])

    def test_numeric_with_meaning_keeps_meaning_question_and_new_audio(self):
        with self.app.app_context():
            word = db.session.get(DictationWord, self.word_ids[0])
            word.word, word.translation, word.core_meaning_zh = "12.50", "费用", "费用"
            task = self._task("listening", end=1)
            queue = get_vocabulary_group_queue(self._user(), task.id)
            self.assertEqual(queue["base_progress_total"], 2)
            rows = VocabularyLearningQuestion.query.filter_by(task_id=task.id).all()
            self.assertEqual({r.dimension for r in rows}, {"audio_form_recall", "meaning_recall"})
            self.assertTrue(
                all(
                    json.loads(r.question_snapshot_json)["prompt"]["audio_tts_url"].endswith(
                        "?numeric=1"
                    )
                    for r in rows
                )
            )

    def test_phone_wrong_zero_then_retry_preserves_original_and_audio(self):
        with self.app.app_context():
            self._numeric_words()
            task = self._task("listening", end=1)
            user = self._user()
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            response = self._answer_for_current(user, task.id, queue, answer_override="2079460018")
            self.assertFalse(response["is_correct"])
            queue = get_vocabulary_group_queue(user, task.id, supports_correction=True)
            self.assertTrue(
                queue["last_saved_response"]["answer_feedback"]["audio_tts_url"].endswith(
                    "?numeric=1"
                )
            )
            self.assertEqual(queue["phase"], "retry")
            self.assertTrue(self._finish_flow(user, task)["completed"])
            first = DictationRecord.query.filter_by(task_id=task.id, is_first_attempt=True).one()
            self.assertEqual(first.student_answer, "2079460018")
            self.assertFalse(first.is_correct)

    def test_all_goals_keep_numeric_only_and_mixed_comprehensive_words(self):
        with self.app.app_context():
            self._numeric_words()
            for goal in ("reading", "writing", "comprehensive", "listening"):
                with self.subTest(goal=goal):
                    task = self._task(goal, end=1)
                    queue = get_vocabulary_group_queue(self._user(), task.id)
                    self.assertEqual(queue["base_progress_total"], 1)
                    self.assertEqual(queue["total_word_count"], 1)
                    self.assertTrue(self._finish_flow(self._user(), task)["completed"])
                    legacy_task = self._task(goal, end=1)
                    legacy = get_vocabulary_task_queue(self._user(), legacy_task.id)
                    self.assertEqual(legacy["total_count"], 1)
            word = db.session.get(DictationWord, self.word_ids[1])
            word.word, word.translation, word.core_meaning_zh = "focus", "集中", "集中"
            word.usage_pattern, word.example_en = "focus on", "Students focus on the main idea."
            task = self._task("comprehensive", end=2)
            queue = get_vocabulary_group_queue(self._user(), task.id)
            rows = VocabularyLearningQuestion.query.filter_by(task_id=task.id).all()
            self.assertEqual(
                {r.dimension for r in rows if r.word_id == self.word_ids[0]}, {"audio_form_recall"}
            )
            self.assertEqual(
                {r.dimension for r in rows if r.word_id == word.id}, {"form_recall", "context_use"}
            )
            self.assertEqual(queue["total_word_count"], 2)
            self.assertTrue(self._finish_flow(self._user(), task)["completed"])

    def test_old_initialized_flow_does_not_gain_questions_or_change_snapshot(self):
        with self.app.app_context():
            self._numeric_words()
            task = self._task("listening", end=1)
            with (
                patch("services.vocabulary_mastery.classify_numeric_dictation", return_value=None),
                patch(
                    "services.vocabulary_group_learning.classify_numeric_dictation",
                    return_value=None,
                ),
            ):
                old = get_vocabulary_group_queue(self._user(), task.id)
            flow = VocabularyLearningFlow.query.filter_by(task_id=task.id).one()
            frozen = flow.groups_json, flow.queue_token, flow.diagnostics_json
            current = get_vocabulary_group_queue(self._user(), task.id)
            self.assertEqual(current["base_progress_total"], old["base_progress_total"])
            self.assertEqual(VocabularyLearningQuestion.query.filter_by(task_id=task.id).count(), 0)
            self.assertEqual((flow.groups_json, flow.queue_token, flow.diagnostics_json), frozen)

    def test_started_old_task_keeps_questions_answers_and_progress(self):
        with self.app.app_context():
            word = db.session.get(DictationWord, self.word_ids[0])
            word.word = "15th May"  # Previously accepted as English, now an explicit date.
            task = self._task("listening", end=2)
            user = self._user()
            with (
                patch("services.vocabulary_mastery.classify_numeric_dictation", return_value=None),
                patch(
                    "services.vocabulary_group_learning.classify_numeric_dictation",
                    return_value=None,
                ),
            ):
                queue = get_vocabulary_group_queue(user, task.id)
            queue = self._view_group(user, task.id, queue)
            self._answer_for_current(user, task.id, queue)
            flow = VocabularyLearningFlow.query.filter_by(task_id=task.id).one()

            def frozen_state():
                rows = (
                    VocabularyLearningQuestion.query.filter_by(task_id=task.id)
                    .order_by(VocabularyLearningQuestion.id)
                    .all()
                )
                records = DictationRecord.query.filter_by(task_id=task.id).all()
                return (
                    flow.queue_token,
                    flow.groups_json,
                    flow.phase,
                    flow.phase_index,
                    [
                        (
                            r.id,
                            r.question_snapshot_json,
                            r.answer_payload_json,
                            r.first_answer,
                            r.first_is_correct,
                            r.first_attempt_id,
                        )
                        for r in rows
                    ],
                    [(r.id, r.student_answer, r.is_correct) for r in records],
                )

            before = frozen_state()
            resumed = get_vocabulary_group_queue(user, task.id)
            self.assertEqual(resumed["base_progress_completed"], 1)
            self.assertEqual(frozen_state(), before)

    def test_task_review_queue_and_grading_uses_same_numeric_policy(self):
        with self.app.app_context():
            self._numeric_words()
            task = self._task("listening", end=4)
            queue = get_vocabulary_task_queue(self._user(), task.id)
            self.assertEqual(queue["total_count"], 4)
            rows = VocabularyTaskReview.query.filter_by(task_id=task.id).all()
            checks = {
                "020 7946 0018": ("02079460018", "2079460018"),
                "12 March 2026": ("2026-03-12", "03/12/2026"),
                "£12.50": ("12.5 GBP", "$12.50"),
                "1.23": ("1.230", "123"),
            }
            for row in rows:
                answer = json.loads(row.answer_payload_json)["answer"]
                correct, incorrect = checks[answer]
                self.assertTrue(_grade_recall(row, correct))
                self.assertFalse(_grade_recall(row, incorrect))
                group_row = VocabularyLearningQuestion(
                    answer_payload_json=row.answer_payload_json,
                    question_snapshot_json=row.question_snapshot_json,
                )
                self.assertTrue(_grade_question(group_row, correct))
                self.assertFalse(_grade_question(group_row, incorrect))

    def test_existing_english_snapshot_is_not_reclassified(self):
        payload = json.dumps({"answer_type": "english", "answer": "B2B", "accepted_answers": []})
        row = VocabularyTaskReview(
            answer_payload_json=payload, question_snapshot_json='{"mode":"audio_to_en"}'
        )
        self.assertTrue(_grade_recall(row, "b2b"))
        self.assertFalse(_grade_recall(row, "22"))
        self.assertEqual(row.answer_payload_json, payload)

    def test_selected_numeric_with_stage_zero_future_review_still_has_question(self):
        with self.app.app_context():
            self._numeric_words()
            user = self._user()
            word = db.session.get(DictationWord, self.word_ids[0])
            mastery = ensure_mastery(user, word, ensure_word_sense(word))
            now = datetime(2026, 8, 8, 12)
            mastery.audio_form_recall_stage = 0
            mastery.audio_form_recall_next_due_at = now + timedelta(days=1)
            db.session.commit()
            for goal in ("listening", "reading", "writing", "comprehensive"):
                with self.subTest(goal=goal):
                    task = self._task(goal, end=1, task_date=now.date())
                    queue = get_vocabulary_task_queue(user, task.id, now=now)
                    self.assertEqual(queue["total_count"], 1)
                    self.assertEqual(mastery.audio_form_recall_stage, 0)
                    self.assertEqual(mastery.audio_form_recall_next_due_at, now + timedelta(days=1))

    def test_comprehensive_separates_numeric_meaning_feedback_from_dictation(self):
        with self.app.app_context():
            self._numeric_words()
            for index, word_id in enumerate(self.word_ids):
                word = db.session.get(DictationWord, word_id)
                word.translation, word.core_meaning_zh = f"编号{index}", f"编号{index}"
            task = self._task("comprehensive", end=4)
            get_vocabulary_group_queue(self._user(), task.id)
            rows = (
                VocabularyLearningQuestion.query.filter_by(task_id=task.id)
                .order_by(VocabularyLearningQuestion.question_order)
                .all()
            )
            self.assertEqual(len(rows), 8)
            self.assertTrue(
                all(a.sense_id != b.sense_id for a, b in zip(rows, rows[1:], strict=False))
            )
            self.assertTrue(self._finish_flow(self._user(), task)["completed"])
