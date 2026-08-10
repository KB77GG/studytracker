import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import jwt
from flask import Flask
from flask_login import LoginManager

from api.miniprogram import mp_bp
from api.vocab_review import vocab_review_bp
from models import (
    DictationBook,
    DictationWord,
    StudentProfile,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyReviewItem,
    VocabularyReviewSession,
    db,
)
from services.vocabulary_autonomous_review import (
    claim_today_review,
    get_review_session,
    review_preflight,
    review_summary,
    settle_review_session,
    submit_review_answer,
)
from services.vocabulary_group_learning import get_vocabulary_group_queue
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense


class AutonomousVocabularyReviewTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="autonomous-vocabulary-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(vocab_review_bp)
        self.app.register_blueprint(mp_bp)
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="autonomous_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            student = User(
                username="autonomous_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, student])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="自主复习学生"))
            books = [
                DictationBook(
                    title="自主复习书一",
                    word_count=12,
                    created_by=teacher.id,
                    is_active=True,
                ),
                DictationBook(
                    title="自主复习书二",
                    word_count=12,
                    created_by=teacher.id,
                    is_active=True,
                ),
            ]
            db.session.add_all(books)
            db.session.flush()
            words = []
            for index in range(22):
                book = books[index % 2]
                words.append(
                    DictationWord(
                        book_id=book.id,
                        sequence=index // 2 + 1,
                        word=f"autoword{index}",
                        translation=f"自动释义{index}",
                        core_meaning_zh=f"自动释义{index}",
                    )
                )
            db.session.add_all(words)
            db.session.flush()
            student = db.session.get(User, student.id)
            now = datetime(2026, 8, 8, 12, 0)
            for index, word in enumerate(words):
                sense = ensure_word_sense(word)
                mastery = ensure_mastery(student, word, sense)
                mastery.meaning_recall_stage = 0 if index == 0 else (4 if index == 1 else (5 if index == 2 else 1))
                mastery.meaning_recall_next_due_at = now - timedelta(days=index + 1)
            task = Task(
                date=date(2026, 8, 8),
                student_name="自主复习学生",
                category="词汇",
                detail="独立队列任务",
                created_by=teacher.id,
                dictation_book_id=books[0].id,
                vocabulary_goal="reading",
                dictation_word_start=1,
                dictation_word_end=1,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()
            self.student_id = student.id
            self.task_id = task.id
            self.now = now
        token = jwt.encode(
            {"sub": str(self.student_id), "role": User.ROLE_STUDENT},
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _answer_all(self, session):
        for item in session.items:
            answer = json.loads(item.answer_payload_json).get("answer")
            if json.loads(item.answer_payload_json).get("answer_type") == "option_id":
                answer = json.loads(item.answer_payload_json)["answer_option_id"]
            result = submit_review_answer(
                db.session.get(User, self.student_id),
                session.id,
                {
                    "session_token": session.session_token,
                    "review_item_id": item.id,
                    "question_id": item.question_id,
                    "word_id": item.word_id,
                    "sense_id": item.sense_id,
                    "dimension": item.dimension,
                    "answer": answer,
                    "attempt_id": f"auto-test-{item.id}",
                },
                now=self.now,
            )
            self.assertTrue(result["is_correct"])

    def _api_get_with_review_clock(self, path):
        def fixed_review_preflight(user, task_id):
            return review_preflight(user, task_id, now=self.now)

        def fixed_group_queue(user, task_id):
            return get_vocabulary_group_queue(user, task_id, now=self.now)

        with patch(
            "api.vocab_review.review_preflight",
            side_effect=fixed_review_preflight,
        ), patch(
            "api.vocab_review.get_vocabulary_group_queue",
            side_effect=fixed_group_queue,
        ):
            return self.client.get(path, headers=self.headers)

    def test_cross_book_batch_is_real_questions_and_repeat_claim_is_idempotent(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            first = claim_today_review(user, now=self.now)
            self.assertTrue(first["ok"])
            self.assertEqual(first["total_count"], 20)
            self.assertEqual(first["session_id"], claim_today_review(user, now=self.now)["session_id"])
            self.assertEqual(len(first["items"]), 20)
            self.assertGreater(len({item["book_id"] for item in first["items"]}), 1)
            self.assertTrue(all("answer_payload" not in item for item in first["items"]))
            self.assertTrue(all("answer_feedback" not in item for item in first["items"]))
            self.assertTrue(
                all(
                    "answer" not in item["question"]
                    and "accepted_answers" not in item["question"]
                    for item in first["items"]
                )
            )
            db.session.commit()
            restored_from_api = self.client.get(
                "/api/miniprogram/student/vocabulary-review/today",
                headers=self.headers,
            )
            self.assertEqual(restored_from_api.status_code, 200)
            self.assertEqual(
                restored_from_api.get_json()["session_id"], first["session_id"]
            )
            self._answer_all(db.session.get(VocabularyReviewSession, first["session_id"]))
            task_before = db.session.get(Task, self.task_id)
            task_stats_before = (
                task_before.status,
                task_before.accuracy,
                task_before.completion_rate,
                task_before.submitted_at,
            )
            result = settle_review_session(
                user,
                first["session_id"],
                {
                    "session_token": first["session_token"],
                    "queue_token": first["queue_token"],
                },
                session_token=first["session_token"],
                now=self.now,
            )
            self.assertEqual(result["total_count"], 20)
            self.assertEqual(result["remaining_due_count"], 2)
            task = db.session.get(Task, self.task_id)
            self.assertEqual(
                (
                    task.status,
                    task.accuracy,
                    task.completion_rate,
                    task.submitted_at,
                ),
                task_stats_before,
            )

            continued = claim_today_review(user, now=self.now, origin_task_id=self.task_id)
            self.assertEqual(continued["total_count"], 2)
            self.assertEqual(continued["origin_task_id"], self.task_id)

    def test_answer_feedback_is_returned_after_answer_and_restored_on_refresh(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            claimed = claim_today_review(user, now=self.now)
            item = claimed["items"][0]
            self.assertNotIn("answer_feedback", item)

            stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
            word = stored.word
            word.word = "n. analysis"
            word.accepted_answers = json.dumps(["analysis"])
            word.phonetic = "/əˈnæləsɪs/"
            word.core_meaning_zh = "分析"
            word.usage_pattern = "data analysis"
            word.example_en = "The analysis supports the conclusion."
            word.example_zh = "这项分析支持该结论。"
            word.usage_note = "常与 data 搭配。"
            expected_answer = json.loads(stored.answer_payload_json).get("answer")

            result = submit_review_answer(
                user,
                claimed["session_id"],
                {
                    "session_token": claimed["session_token"],
                    "review_item_id": item["review_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "sense_id": item["sense_id"],
                    "dimension": item["dimension"],
                    "answer": expected_answer,
                    "attempt_id": "answer-feedback-first",
                },
                now=self.now,
            )
            expected_feedback = {
                "word": "analysis",
                "syllables": "anal·y·sis",
                "phonetic": "/əˈnæləsɪs/",
                "core_meaning_zh": "分析",
                "usage_pattern": "data analysis",
                "example_en": "The analysis supports the conclusion.",
                "example_zh": "这项分析支持该结论。",
                "usage_note": "常与 data 搭配。",
                "audio_tts_url": f"/dictation/words/{word.id}/tts",
            }
            self.assertEqual(result["answer_feedback"], expected_feedback)

            restored = get_review_session(
                user,
                claimed["session_id"],
                claimed["session_token"],
            )
            restored_item = next(
                candidate
                for candidate in restored["items"]
                if candidate["review_item_id"] == item["review_item_id"]
            )
            self.assertEqual(restored_item["answer_feedback"], expected_feedback)
            self.assertTrue(restored_item["answered"])
            self.assertTrue(
                all(
                    "answer_feedback" not in candidate
                    for candidate in restored["items"]
                    if candidate["review_item_id"] != item["review_item_id"]
                )
            )

    def test_active_review_blocks_task_queue_and_daily_settlement_clears_second_task(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            active = claim_today_review(
                user,
                origin_task_id=self.task_id,
                now=self.now,
            )
            db.session.commit()

            preflight = self._api_get_with_review_clock(
                f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-review/preflight"
                "?reviewDone=1",
            )
            self.assertEqual(preflight.status_code, 200)
            self.assertTrue(preflight.get_json()["required"])
            blocked = self._api_get_with_review_clock(
                f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-queue?reviewDone=1",
            )
            self.assertEqual(blocked.status_code, 409)
            self.assertEqual(blocked.get_json()["error"], "vocabulary_review_required")
            self._answer_all(db.session.get(VocabularyReviewSession, active["session_id"]))
            settled = settle_review_session(
                user,
                active["session_id"],
                {"queue_token": active["queue_token"]},
                session_token=active["session_token"],
                now=self.now,
            )
            self.assertTrue(settled["independent_review"])
            db.session.commit()

            first_after_settlement = self._api_get_with_review_clock(
                f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-queue",
            )
            self.assertEqual(first_after_settlement.status_code, 200)
            first_gate = self._api_get_with_review_clock(
                f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-review/preflight",
            ).get_json()
            self.assertFalse(first_gate["required"])
            self.assertEqual(first_gate["clearance_session_id"], active["session_id"])
            self.assertGreater(first_gate["due_count"], 0)

            second = Task(
                date=date(2026, 8, 8),
                student_name="自主复习学生",
                category="词汇",
                detail="当天第二个新版任务",
                created_by=db.session.get(Task, self.task_id).created_by,
                dictation_book_id=db.session.get(Task, self.task_id).dictation_book_id,
                vocabulary_goal="reading",
                dictation_word_start=2,
                dictation_word_end=2,
                status="pending",
            )
            db.session.add(second)
            db.session.commit()
            second_gate = self._api_get_with_review_clock(
                f"/api/miniprogram/student/tasks/{second.id}/vocabulary-review/preflight",
            )
            self.assertEqual(second_gate.status_code, 200)
            self.assertFalse(second_gate.get_json()["required"])
            self.assertGreater(second_gate.get_json()["due_count"], 0)
            second_queue = self._api_get_with_review_clock(
                f"/api/miniprogram/student/tasks/{second.id}/vocabulary-queue?reviewDone=1",
            )
            self.assertEqual(second_queue.status_code, 200)

    def test_empty_review_queue_is_explicit(self):
        with self.app.app_context():
            for mastery in StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id
            ).all():
                mastery.meaning_recall_next_due_at = self.now + timedelta(days=1)
            db.session.commit()
            result = claim_today_review(
                db.session.get(User, self.student_id),
                now=self.now,
            )
            self.assertTrue(result["empty"])
            self.assertEqual(result["status"], "empty")
            self.assertEqual(result["items"], [])

    def test_wrong_is_plus_24h_and_30_60_day_intervals_are_consumed(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            session_payload = claim_today_review(user, now=self.now)
            first_item = session_payload["items"][0]
            wrong = submit_review_answer(
                user,
                session_payload["session_id"],
                {
                    "session_token": session_payload["session_token"],
                    "review_item_id": first_item["review_item_id"],
                    "question_id": first_item["question_id"],
                    "word_id": first_item["word_id"],
                    "sense_id": first_item["sense_id"],
                    "dimension": first_item["dimension"],
                    "answer": "明显错误",
                    "attempt_id": "autonomous-wrong",
                },
                now=self.now,
            )
            self.assertFalse(wrong["is_correct"])
            wrong_mastery = StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id,
                sense_id=first_item["sense_id"],
            ).one()
            self.assertEqual(
                wrong_mastery.meaning_recall_next_due_at,
                self.now + timedelta(days=1),
            )
            duplicate = submit_review_answer(
                user,
                session_payload["session_id"],
                {
                    "session_token": session_payload["session_token"],
                    "review_item_id": first_item["review_item_id"],
                    "question_id": first_item["question_id"],
                    "word_id": first_item["word_id"],
                    "sense_id": first_item["sense_id"],
                    "dimension": first_item["dimension"],
                    "answer": "另一个答案",
                    "attempt_id": "autonomous-wrong",
                },
                now=self.now,
            )
            self.assertTrue(duplicate["idempotent"])
            for item in db.session.get(VocabularyReviewSession, session_payload["session_id"]).items[1:]:
                answer_payload = json.loads(item.answer_payload_json)
                self.assertTrue(
                    submit_review_answer(
                        user,
                        session_payload["session_id"],
                        {
                            "session_token": session_payload["session_token"],
                            "review_item_id": item.id,
                            "question_id": item.question_id,
                            "word_id": item.word_id,
                            "sense_id": item.sense_id,
                            "dimension": item.dimension,
                            "answer": answer_payload.get("answer") or answer_payload.get("answer_option_id"),
                            "attempt_id": f"auto-tail-{item.id}",
                        },
                        now=self.now,
                    )["is_correct"]
                )
            settle_review_session(
                user,
                session_payload["session_id"],
                {"queue_token": session_payload["queue_token"]},
                session_token=session_payload["session_token"],
                now=self.now,
            )
            mastery = StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id,
                sense_id=first_item["sense_id"],
            ).one()
            self.assertEqual(
                mastery.meaning_recall_next_due_at,
                self.now + timedelta(days=1),
            )
            for item in VocabularyReviewItem.query.filter_by(session_id=session_payload["session_id"]).all():
                if item.stage_at_claim in {4, 5}:
                    row = db.session.get(StudentVocabularyMastery, mastery.id) if item.sense_id == mastery.sense_id else StudentVocabularyMastery.query.filter_by(sense_id=item.sense_id).one()
                    expected_days = 30 if item.stage_at_claim == 4 else 60
                    self.assertEqual(
                        getattr(row, f"{item.dimension}_next_due_at"),
                        self.now + timedelta(days=expected_days),
                    )

    def test_preflight_and_http_api_are_independent_from_teacher_task(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            gate = review_preflight(user, self.task_id, now=self.now)
            self.assertTrue(gate["required"])
        response = self.client.get(
            f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-review/preflight",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["required"])
        today = self.client.get(
            f"/api/miniprogram/student/vocabulary-review/today?origin_task_id={self.task_id}&limit=1",
            headers=self.headers,
        )
        self.assertEqual(today.status_code, 200)
        payload = today.get_json()
        self.assertTrue(payload["items"])
        self.assertEqual(payload["total_count"], 20)
        self.assertIn("question", payload["items"][0])

    def test_http_answer_settle_continue_are_idempotent_and_independent(self):
        today = self.client.get(
            "/api/miniprogram/student/vocabulary-review/today",
            headers=self.headers,
        )
        self.assertEqual(today.status_code, 200)
        session = today.get_json()
        item = session["items"][0]
        with self.app.app_context():
            stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
            answer_payload = json.loads(stored.answer_payload_json)
            answer = answer_payload.get("answer") or answer_payload.get("answer_option_id")
        answer_payload = {
            "session_token": session["session_token"],
            "review_item_id": item["review_item_id"],
            "question_id": item["question_id"],
            "word_id": item["word_id"],
            "sense_id": item["sense_id"],
            "dimension": item["dimension"],
            "answer": answer,
            "attempt_id": "http-autonomous-first",
        }
        missing_token = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/answers",
            json=dict(answer_payload, session_token=""),
            headers=self.headers,
        )
        self.assertEqual(missing_token.status_code, 400)
        self.assertEqual(
            missing_token.get_json()["error"], "review_session_token_required"
        )
        first = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/answers",
            json=answer_payload,
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        duplicate = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/answers",
            json=dict(answer_payload, answer="different-after-first"),
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.get_json()["idempotent"])
        settle_url = (
            f"/api/miniprogram/student/vocabulary-review/sessions/"
            f"{session['session_id']}/settle"
        )
        settled = self.client.post(
            settle_url,
            json={
                "session_token": session["session_token"],
                "queue_token": session["queue_token"],
            },
            headers=self.headers,
        )
        self.assertEqual(settled.status_code, 409)
        self.assertEqual(settled.get_json()["error"], "review_session_incomplete")

        with self.app.app_context():
            stored_session = db.session.get(
                VocabularyReviewSession, session["session_id"]
            )
            for tail in stored_session.items:
                if tail.first_attempt_id:
                    continue
                tail_payload = json.loads(tail.answer_payload_json)
                submit_review_answer(
                    db.session.get(User, self.student_id),
                    stored_session.id,
                    {
                        "session_token": stored_session.session_token,
                        "review_item_id": tail.id,
                        "question_id": tail.question_id,
                        "word_id": tail.word_id,
                        "sense_id": tail.sense_id,
                        "dimension": tail.dimension,
                        "answer": tail_payload.get("answer")
                        or tail_payload.get("answer_option_id"),
                        "attempt_id": f"http-tail-{tail.id}",
                    },
                    now=self.now,
                )
            db.session.commit()
        missing_queue_token = self.client.post(
            settle_url,
            json={"session_token": session["session_token"]},
            headers=self.headers,
        )
        self.assertEqual(missing_queue_token.status_code, 400)
        self.assertEqual(
            missing_queue_token.get_json()["error"],
            "review_queue_token_required",
        )
        settled = self.client.post(
            settle_url,
            json={
                "session_token": session["session_token"],
                "queue_token": session["queue_token"],
            },
            headers=self.headers,
        )
        self.assertEqual(settled.status_code, 200)
        self.assertTrue(settled.get_json()["independent_review"])
        settled_again = self.client.post(
            settle_url,
            json={"session_token": session["session_token"]},
            headers=self.headers,
        )
        self.assertEqual(settled_again.status_code, 200)
        self.assertEqual(settled_again.get_json(), settled.get_json())

        continued = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/continue",
            json={"session_token": session["session_token"]},
            headers=self.headers,
        )
        self.assertEqual(continued.status_code, 200)
        self.assertGreater(continued.get_json()["total_count"], 0)

    def test_wrong_stage_zero_outranks_unanswered_stage_zero(self):
        with self.app.app_context():
            rows = StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id
            ).order_by(StudentVocabularyMastery.id.asc()).all()
            for mastery in rows:
                mastery.meaning_recall_next_due_at = self.now + timedelta(days=1)
            untouched, failed = rows[:2]
            untouched.meaning_recall_stage = 0
            untouched.meaning_recall_last_answered_at = None
            untouched.meaning_recall_next_due_at = self.now - timedelta(days=10)
            failed.meaning_recall_stage = 0
            failed.meaning_recall_last_answered_at = self.now - timedelta(days=1)
            failed.meaning_recall_next_due_at = self.now - timedelta(hours=1)
            db.session.commit()

            claimed = claim_today_review(
                db.session.get(User, self.student_id),
                now=self.now,
            )
            self.assertEqual(claimed["items"][0]["sense_id"], failed.sense_id)

    def test_listening_meaning_review_keeps_audio_cue(self):
        with self.app.app_context():
            for mastery in StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id
            ).all():
                mastery.meaning_recall_next_due_at = self.now + timedelta(days=1)
            teacher_id = db.session.get(Task, self.task_id).created_by
            book = DictationBook(
                title="自主听力复习书",
                word_count=1,
                created_by=teacher_id,
                is_active=True,
                default_vocabulary_goal="listening",
            )
            db.session.add(book)
            db.session.flush()
            word = DictationWord(
                book_id=book.id,
                sequence=1,
                word="auditory",
                translation="听觉的",
                core_meaning_zh="听觉的",
            )
            db.session.add(word)
            db.session.flush()
            sense = ensure_word_sense(word)
            mastery = ensure_mastery(db.session.get(User, self.student_id), word, sense)
            mastery.meaning_recall_stage = 1
            mastery.meaning_recall_next_due_at = self.now - timedelta(minutes=1)
            db.session.commit()

            claimed = claim_today_review(
                db.session.get(User, self.student_id),
                now=self.now,
            )
            item = claimed["items"][0]
            self.assertEqual(item["mode"], "audio_to_zh")
            self.assertNotIn("word", item["question"]["prompt"])
            self.assertIn("audio_tts_url", item["question"]["prompt"])
            self.assertTrue(item["question"]["options"])
            self.assertLessEqual(len(item["question"]["options"]), 4)
            selected_label = item["question"]["options"][0]["label"]
            result = submit_review_answer(
                db.session.get(User, self.student_id),
                claimed["session_id"],
                {
                    "session_token": claimed["session_token"],
                    "review_item_id": item["review_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "sense_id": item["sense_id"],
                    "dimension": item["dimension"],
                    "answer": selected_label,
                    "attempt_id": "audio-meaning-choice",
                },
                now=self.now,
            )
            self.assertTrue(result["is_correct"])

    def test_answered_active_session_stays_visible_until_settlement(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            claimed = claim_today_review(user, now=self.now)
            session = db.session.get(VocabularyReviewSession, claimed["session_id"])
            self._answer_all(session)
            summary = review_summary(user, now=self.now)
            self.assertTrue(summary["has_active_session"])
            self.assertGreaterEqual(summary["review_due_count"], 1)

    def test_cross_midnight_settlement_grants_completion_day_clearance(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            claimed = claim_today_review(
                user,
                origin_task_id=self.task_id,
                now=self.now,
            )
            session = db.session.get(VocabularyReviewSession, claimed["session_id"])
            self._answer_all(session)
            completed_at = self.now + timedelta(hours=5)
            settled = settle_review_session(
                user,
                session.id,
                {"queue_token": session.queue_token},
                session_token=session.session_token,
                now=completed_at,
            )
            self.assertGreater(settled["remaining_due_count"], 0)
            self.assertEqual(session.review_date, date(2026, 8, 9))
            gate = review_preflight(user, self.task_id, now=completed_at)
            self.assertFalse(gate["required"])
            self.assertEqual(gate["clearance_review_date"], "2026-08-09")


if __name__ == "__main__":
    unittest.main()
