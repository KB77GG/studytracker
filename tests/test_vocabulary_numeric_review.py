"""Numeric dictation through frozen autonomous-review sessions (SQLite only)."""

import json
import unittest
from datetime import datetime, timedelta

from flask import Flask

from models import (
    DictationBook,
    DictationWord,
    StudentProfile,
    User,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    db,
)
from services.vocabulary_autonomous_review import (
    _candidate_is_eligible,
    _review_item_skip_reason,
    claim_today_review,
    settle_review_session,
    submit_review_answer,
    submit_review_correction,
)
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense


class NumericAutonomousReviewTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.now = datetime(2026, 8, 8, 12)
        self.user = User(username="numeric_review_student", password_hash="test", role="student", is_active=True)
        db.session.add(self.user)
        db.session.flush()
        db.session.add(StudentProfile(user_id=self.user.id, full_name="数字复习测试"))
        self.book = DictationBook(title="数字听写", created_by=self.user.id, is_active=True, default_vocabulary_goal="listening")
        db.session.add(self.book)
        db.session.flush()
        self.sequence = 0

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def _word(self, value, meaning="", due=True):
        self.sequence += 1
        word = DictationWord(book_id=self.book.id, sequence=self.sequence, word=value, translation=meaning)
        db.session.add(word)
        db.session.flush()
        mastery = ensure_mastery(self.user, word, ensure_word_sense(word))
        mastery.audio_form_recall_stage = 1
        mastery.audio_form_recall_next_due_at = self.now - timedelta(days=1) if due else None
        db.session.flush()
        return word, mastery

    def _claim(self):
        claimed = claim_today_review(self.user, now=self.now)
        self.assertFalse(claimed.get("empty", False))
        items = [db.session.get(VocabularyReviewItem, entry["review_item_id"]) for entry in claimed["items"]]
        return claimed, items

    def _identity(self, claimed, item):
        return {
            "session_token": claimed["session_token"],
            "review_item_id": item.id,
            "question_id": item.question_id,
            "word_id": item.word_id,
            "sense_id": item.sense_id,
            "dimension": item.dimension,
            "input_mode": "native",
        }

    def _answer(self, claimed, item, answer, attempt_id="first", **extra):
        return submit_review_answer(self.user, claimed["session_id"], dict(self._identity(claimed, item), answer=answer, attempt_id=attempt_id, **extra), now=self.now)

    def _correct(self, claimed, item, answer, attempt_id):
        return submit_review_correction(self.user, claimed["session_id"], dict(self._identity(claimed, item), answer=answer, attempt_id=attempt_id), now=self.now)

    def test_numeric_without_meaning_is_only_eligible_for_audio_form(self):
        word, mastery = self._word("020 7946 0018")
        self.assertTrue(_candidate_is_eligible(word, mastery, "audio_form_recall", {}))
        self.assertFalse(_candidate_is_eligible(word, mastery, "form_recall", {}))
        self.assertFalse(_candidate_is_eligible(word, mastery, "meaning_recall", {}))

    def test_numeric_only_queue_keeps_all_answers_and_private_metadata(self):
        values = ["020 7946 0018", "1.23", "£12.50", "12 March 2026", "03/04/2026"]
        for value in values:
            self._word(value)
        claimed, items = self._claim()
        self.assertEqual(claimed["total_count"], len(values))
        self.assertEqual({json.loads(item.answer_payload_json)["answer"] for item in items}, set(values))
        for item in items:
            question = json.loads(item.question_snapshot_json)
            self.assertEqual(question["answer_type"], "numeric")
            self.assertEqual(question["mode"], "audio_to_en")
            self.assertTrue(question["prompt"]["audio_tts_url"].endswith("?numeric=1"))
            self.assertIn("input_hint", question["prompt"])
            self.assertNotIn("answer", question)
            self.assertNotIn("tts_text", question["prompt"])
            self.assertIsNone(_review_item_skip_reason(item))
            answer = json.loads(item.answer_payload_json)["answer"]
            self.assertTrue(self._answer(claimed, item, answer, f"first-{item.id}")["is_correct"])

    def test_phone_correction_preserves_leading_zero_and_retries_next_day(self):
        word, mastery = self._word("020 7946 0018")
        claimed, (item,) = self._claim()
        frozen = (item.question_snapshot_json, item.answer_payload_json)
        wrong = self._answer(claimed, item, "20 7946 0018")
        self.assertFalse(wrong["is_correct"])
        self.assertTrue(wrong["correction_required"])
        self.assertEqual(wrong["answer_feedback"]["word"], "020 7946 0018")
        self.assertEqual(wrong["answer_feedback"]["audio_tts_url"], f"/dictation/words/{word.id}/tts?numeric=1")
        corrected = self._correct(claimed, item, "020-7946-0018", "correction")
        self.assertTrue(corrected["correction_completed"])
        self.assertFalse(item.first_is_correct)
        duplicate = self._correct(claimed, item, "wrong", "correction")
        self.assertTrue(duplicate["idempotent"])
        self.assertEqual(item.correction_count, 1)
        self.assertEqual((item.question_snapshot_json, item.answer_payload_json), frozen)
        attempts = VocabularyReviewAttempt.query.filter_by(item_id=item.id).order_by(VocabularyReviewAttempt.id).all()
        self.assertEqual([attempt.student_answer for attempt in attempts], ["20 7946 0018", "020-7946-0018"])
        self.assertEqual([attempt.is_correct for attempt in attempts], [False, True])
        settle_review_session(self.user, claimed["session_id"], {"queue_token": claimed["queue_token"]}, session_token=claimed["session_token"], now=self.now)
        self.assertEqual(mastery.audio_form_recall_next_due_at, self.now + timedelta(days=1))
        tomorrow = claim_today_review(self.user, now=self.now + timedelta(days=1))
        self.assertEqual(tomorrow["total_count"], 1)
        self.assertEqual(tomorrow["items"][0]["word_id"], word.id)
        self.assertEqual(tomorrow["items"][0]["remediation_kind"], "same_dimension")
        self.assertEqual(tomorrow["items"][0]["question"]["answer_type"], "numeric")

    def test_decimal_first_and_correction_do_not_use_english_punctuation_rules(self):
        self._word("1.23")
        claimed, (item,) = self._claim()
        self.assertFalse(self._answer(claimed, item, "1 23")["is_correct"])
        self.assertFalse(self._correct(claimed, item, "123", "wrong-correction")["correction_completed"])
        self.assertTrue(self._correct(claimed, item, "1.230", "right-correction")["correction_completed"])

    def test_date_ambiguity_is_not_silently_reinterpreted(self):
        self._word("03/04/2026")
        claimed, (item,) = self._claim()
        self.assertEqual(json.loads(item.answer_payload_json)["numeric_kind"], "literal")
        self.assertFalse(self._answer(claimed, item, "4 March 2026")["is_correct"])
        self.assertTrue(self._correct(claimed, item, "03/04/2026", "correct-date")["correction_completed"])

    def test_mixed_queue_keeps_ordinary_english_on_existing_contract(self):
        self._word("12.50")
        self._word("B2B", "企业对企业")
        self._word("apple", "苹果")
        claimed, items = self._claim()
        self.assertEqual(claimed["total_count"], 3)
        for item in items:
            expected = json.loads(item.answer_payload_json)
            is_numeric = expected["answer"] == "12.50"
            self.assertEqual(expected["answer_type"], "numeric" if is_numeric else "english")
            self.assertTrue(self._answer(claimed, item, expected["answer"], f"mixed-{item.id}")["is_correct"])

    def test_existing_english_snapshot_remains_unchanged_and_uses_old_grader(self):
        self._word("1.23")
        claimed, (item,) = self._claim()
        question = json.loads(item.question_snapshot_json)
        question["answer_type"] = "english"
        question.pop("numeric_kind", None)
        item.question_snapshot_json = json.dumps(question)
        item.answer_payload_json = json.dumps({"answer_type": "english", "answer": "1.23", "accepted_answers": []})
        frozen = (item.question_snapshot_json, item.answer_payload_json)
        # This legacy punctuation behavior is retained only for old payloads.
        result = self._answer(claimed, item, "1 23")
        self.assertTrue(result["is_correct"])
        self.assertEqual(result["answer_feedback"]["audio_tts_url"], f"/dictation/words/{item.word_id}/tts")
        self.assertEqual((item.question_snapshot_json, item.answer_payload_json), frozen)

    def test_forgotten_replay_retains_frozen_numeric_answer_and_audio(self):
        word, _ = self._word("020 7946 0018")
        claimed, (item,) = self._claim()
        # The question's frozen answer survives subsequent catalog edits.
        word.word = "changed catalog text"
        self._answer(claimed, item, "", response_kind="forgot")
        settled = settle_review_session(self.user, claimed["session_id"], {"queue_token": claimed["queue_token"]}, session_token=claimed["session_token"], now=self.now)
        self.assertEqual(len(settled["forgot_items"]), 1)
        forgotten = settled["forgot_items"][0]
        self.assertEqual(forgotten["correct_spelling"], "020 7946 0018")
        self.assertEqual(forgotten["revealed_answer"], "020 7946 0018")
        self.assertEqual(forgotten["audio_tts_url"], f"/dictation/words/{word.id}/tts?numeric=1")

    def test_numeric_forgot_is_valid_but_numeric_non_audio_snapshot_is_invalid(self):
        self._word("42")
        claimed, (item,) = self._claim()
        self.assertIsNone(_review_item_skip_reason(item))
        forgotten = self._answer(claimed, item, "", response_kind="forgot")
        self.assertFalse(forgotten["is_correct"])
        self.assertFalse(forgotten["correction_required"])
        self.assertTrue(item.deferred_to_review)
        question = json.loads(item.question_snapshot_json)
        question["mode"] = "zh_to_en"
        question["prompt"]["meaning"] = "测试"
        item.question_snapshot_json = json.dumps(question)
        self.assertEqual(_review_item_skip_reason(item), "invalid_question")


if __name__ == "__main__":
    unittest.main()
