import time
import unittest
from datetime import datetime, timedelta

import jwt
from flask import Flask
from sqlalchemy import inspect as sqlalchemy_inspect

from api.dictation import dictation_bp
from api.miniprogram import mp_bp
from api.vocab_review import vocab_review_bp
from models import (
    DictationBook,
    DictationRecord,
    DictationTaskReview,
    DictationWord,
    StudentProfile,
    StudentWordMastery,
    Task,
    User,
    db,
)
from services.dictation_review import (
    AUTO_REVIEW_COLLECTION_START_UTC,
    AUTO_REVIEW_QUEUE_START_UTC,
    DictationReviewError,
    auto_review_queue_enabled,
    ensure_incremental_schema,
    finalize_strict_task,
    get_task_queue,
    import_legacy_wrong_words,
    list_server_wrong_words,
    next_local_midnight,
    submit_dictation_answer,
)

AUTO_REVIEW_NOW = AUTO_REVIEW_QUEUE_START_UTC + timedelta(hours=1)


class DictationReviewFlowTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="review-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(dictation_bp)
        self.app.register_blueprint(mp_bp)
        self.app.register_blueprint(vocab_review_bp)
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="review_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            student = User(
                username="review_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, student])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="复习学生"))
            book = DictationBook(
                title="自动回流词库",
                word_count=6,
                created_by=teacher.id,
                is_active=True,
            )
            other_book = DictationBook(
                title="另一本词库",
                word_count=1,
                created_by=teacher.id,
                is_active=True,
            )
            db.session.add_all([book, other_book])
            db.session.flush()
            words = [
                DictationWord(book_id=book.id, sequence=i, word=word, translation=translation)
                for i, (word, translation) in enumerate(
                    [
                        ("alpha", "甲"),
                        ("bravo", "乙"),
                        ("charlie", "丙"),
                        ("delta", "丁"),
                        ("echo", "回声"),
                        ("foxtrot", "狐步舞"),
                    ],
                    start=1,
                )
            ]
            other_word = DictationWord(
                book_id=other_book.id,
                sequence=1,
                word="other",
                translation="其他",
            )
            db.session.add_all(words + [other_word])
            db.session.flush()
            self.teacher_id = teacher.id
            self.student_id = student.id
            self.book_id = book.id
            self.other_book_id = other_book.id
            self.word_ids = [word.id for word in words]
            self.other_word_id = other_word.id
            db.session.commit()
        self.client = self.app.test_client()
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": str(self.student_id),
                "role": User.ROLE_STUDENT,
                "iat": now,
                "exp": now + int(timedelta(hours=1).total_seconds()),
            },
            "review-secret",
            algorithm="HS256",
        )
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _task(self, start=1, end=2, mode="audio_to_en", order="sequence"):
        with self.app.app_context():
            task = Task(
                date="2026-07-16",
                student_name="复习学生",
                category="词汇",
                detail=f"范围 {start}-{end}",
                created_by=self.teacher_id,
                dictation_book_id=self.book_id,
                dictation_mode=mode,
                dictation_order=order,
                dictation_word_start=start,
                dictation_word_end=end,
            )
            db.session.add(task)
            db.session.commit()
            return task.id

    def _queue(self, task_id):
        response = self.client.get(
            f"/api/miniprogram/student/tasks/{task_id}/dictation-queue",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _submit(self, task_id, word_id, answer, mode="audio_to_en", attempt_id=None):
        return self.client.post(
            "/api/dictation/submit",
            headers=self.headers,
            json={
                "task_id": task_id,
                "book_id": self.book_id,
                "word_id": word_id,
                "answer": answer,
                "mode": mode,
                "attempt_id": attempt_id or f"attempt:{task_id}:{word_id}:{answer}",
                "is_first_attempt": True,
                "strict_queue": True,
            },
        )

    def test_queue_contains_all_due_words_and_interleaves_without_limit(self):
        review_now = AUTO_REVIEW_NOW
        with self.app.app_context():
            db.session.add(
                StudentWordMastery(
                    student_id=self.student_id,
                    word_id=self.word_ids[2],
                    book_id=self.book_id,
                    mistake_count=3,
                    review_level=1,
                    auto_review_active=True,
                    auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                    auto_review_due_at=review_now - timedelta(minutes=1),
                )
            )
            db.session.commit()
            task_id = self._task(start=1, end=2)
            queue = get_task_queue(
                db.session.get(User, self.student_id), task_id, review_now
            )
            self.assertEqual(queue["assigned_count"], 2)
            self.assertEqual(queue["auto_review_count"], 1)
            self.assertEqual(queue["total_count"], 3)
            self.assertEqual([item["word_id"] for item in queue["words"]], [self.word_ids[0], self.word_ids[2], self.word_ids[1]])
            self.assertEqual(queue["words"][1]["source"], "auto_review")

    def test_overlap_counts_once_and_queue_snapshot_survives_reopen(self):
        now = AUTO_REVIEW_NOW
        with self.app.app_context():
            db.session.add(
                StudentWordMastery(
                    student_id=self.student_id,
                    word_id=self.word_ids[0],
                    book_id=self.book_id,
                    mistake_count=1,
                    review_level=1,
                    auto_review_active=True,
                    auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                    auto_review_due_at=now - timedelta(minutes=1),
                )
            )
            db.session.commit()
            task_id = self._task(start=1, end=1)
            first = get_task_queue(db.session.get(User, self.student_id), task_id, now)
            second = get_task_queue(db.session.get(User, self.student_id), task_id, now)
            db.session.commit()
        self.assertEqual(first["total_count"], 1)
        self.assertEqual(first["assigned_count"], 1)
        self.assertEqual(first["auto_review_count"], 0)
        self.assertEqual(first["auto_review_overlap_count"], 1)
        self.assertEqual(first["queue_token"], second["queue_token"])
        with self.app.app_context():
            self.assertEqual(DictationTaskReview.query.filter_by(task_id=task_id).count(), 1)

    def test_due_word_waits_until_a_same_book_task_exists(self):
        now = AUTO_REVIEW_NOW
        with self.app.app_context():
            mastery = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[2],
                book_id=self.book_id,
                mistake_count=1,
                review_level=1,
                auto_review_active=True,
                auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                auto_review_due_at=now - timedelta(minutes=1),
            )
            db.session.add(mastery)
            db.session.commit()
            self.assertIsNone(DictationTaskReview.query.filter_by(word_id=self.word_ids[2]).first())
            task_id = self._task(start=1, end=1)
            queue = get_task_queue(db.session.get(User, self.student_id), task_id, now)
            self.assertIn(self.word_ids[2], [item["word_id"] for item in queue["words"]])

    def test_same_day_claim_deduplicates_and_books_are_isolated(self):
        review_now = AUTO_REVIEW_NOW
        with self.app.app_context():
            db.session.add_all(
                [
                    StudentWordMastery(
                        student_id=self.student_id,
                        word_id=self.word_ids[2],
                        book_id=self.book_id,
                        mistake_count=1,
                        review_level=1,
                        auto_review_active=True,
                        auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                        auto_review_due_at=review_now - timedelta(days=1),
                    ),
                    StudentWordMastery(
                        student_id=self.student_id,
                        word_id=self.other_word_id,
                        book_id=self.other_book_id,
                        mistake_count=1,
                        review_level=1,
                        auto_review_active=True,
                        auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                        auto_review_due_at=review_now - timedelta(days=1),
                    ),
                ]
            )
            db.session.commit()
            first = self._task(start=1, end=1)
            second = self._task(start=1, end=1)
            first_queue = get_task_queue(db.session.get(User, self.student_id), first, review_now)
            second_queue = get_task_queue(db.session.get(User, self.student_id), second, review_now)
            self.assertEqual([item["word_id"] for item in first_queue["words"]], [self.word_ids[0], self.word_ids[2]])
            self.assertEqual([item["word_id"] for item in second_queue["words"]], [self.word_ids[0]])
            other_task = Task(
                date="2026-07-17",
                student_name="复习学生",
                category="词汇",
                detail="另一本",
                created_by=self.teacher_id,
                dictation_book_id=self.other_book_id,
                dictation_mode="zh_to_en",
                dictation_word_start=1,
                dictation_word_end=1,
            )
            db.session.add(other_task)
            db.session.flush()
            other_queue = get_task_queue(db.session.get(User, self.student_id), other_task.id, review_now)
            self.assertEqual([item["word_id"] for item in other_queue["words"]], [self.other_word_id])

    def test_historical_mastery_is_not_activated_by_queue_or_wrong_list(self):
        now = AUTO_REVIEW_NOW
        old_due = AUTO_REVIEW_COLLECTION_START_UTC - timedelta(minutes=1)
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            mastery = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[0],
                book_id=self.book_id,
                mistake_count=4,
                review_level=1,
                auto_review_active=True,
                auto_review_correct_streak=1,
                auto_review_due_at=old_due,
                auto_review_activated_at=None,
            )
            db.session.add(mastery)
            db.session.commit()
            task_id = self._task(start=2, end=2)
            queue = get_task_queue(user, task_id, now)
            listed = list_server_wrong_words(user, self.book_id)
            db.session.refresh(mastery)

            self.assertNotIn(self.word_ids[0], [item["word_id"] for item in queue["words"]])
            self.assertNotIn(self.word_ids[0], [item["word_id"] for item in listed["items"]])
            self.assertTrue(mastery.auto_review_active)
            self.assertEqual(mastery.auto_review_correct_streak, 1)
            self.assertEqual(mastery.auto_review_due_at, old_due)
            self.assertIsNone(mastery.auto_review_activated_at)

    def test_july_17_error_is_collected_but_claimed_on_july_18(self):
        collected_at = AUTO_REVIEW_COLLECTION_START_UTC + timedelta(hours=1)
        before_queue = AUTO_REVIEW_QUEUE_START_UTC - timedelta(minutes=1)
        after_queue = AUTO_REVIEW_QUEUE_START_UTC + timedelta(hours=1)
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            collecting_task = self._task(start=1, end=1)
            collecting_queue = get_task_queue(user, collecting_task, before_queue)
            self.assertEqual(collecting_queue["auto_review_count"], 0)
            result = submit_dictation_answer(
                user,
                {
                    "task_id": collecting_task,
                    "word_id": self.word_ids[0],
                    "answer": "not-alpha",
                    "mode": "audio_to_en",
                    "attempt_id": "cutoff:july17:first",
                    "strict_queue": True,
                },
                now=collected_at,
            )
            db.session.commit()
            mastery = StudentWordMastery.query.filter_by(
                student_id=self.student_id,
                word_id=self.word_ids[0],
            ).one()
            self.assertFalse(result["is_correct"])
            self.assertTrue(mastery.auto_review_active)
            self.assertEqual(mastery.auto_review_activated_at, collected_at)
            self.assertEqual(mastery.auto_review_due_at, next_local_midnight(collected_at))
            self.assertFalse(auto_review_queue_enabled(before_queue))
            self.assertTrue(auto_review_queue_enabled(after_queue))

            before_task = self._task(start=2, end=2)
            before_snapshot = get_task_queue(user, before_task, before_queue)
            self.assertNotIn(self.word_ids[0], [item["word_id"] for item in before_snapshot["words"]])

            after_task = self._task(start=2, end=2)
            after_snapshot = get_task_queue(user, after_task, after_queue)
            self.assertEqual(after_snapshot["auto_review_count"], 1)
            self.assertIn(self.word_ids[0], [item["word_id"] for item in after_snapshot["words"]])

    def test_historical_word_reenters_when_it_is_wrong_again_after_cutoff(self):
        collected_at = AUTO_REVIEW_COLLECTION_START_UTC + timedelta(hours=2)
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            mastery = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[1],
                book_id=self.book_id,
                mistake_count=2,
                review_level=1,
                auto_review_active=False,
                auto_review_due_at=None,
                auto_review_activated_at=None,
            )
            db.session.add(mastery)
            db.session.commit()
            result = submit_dictation_answer(
                user,
                {
                    "word_id": self.word_ids[1],
                    "answer": "not-bravo",
                    "mode": "audio_to_en",
                    "attempt_id": "cutoff:historical:again",
                },
                now=collected_at,
            )
            db.session.commit()
            db.session.refresh(mastery)
            self.assertFalse(result["is_correct"])
            self.assertTrue(mastery.auto_review_active)
            self.assertEqual(mastery.auto_review_activated_at, collected_at)
            self.assertEqual(mastery.auto_review_due_at, next_local_midnight(collected_at))

    def test_confirmed_legacy_import_can_enter_loop_without_resetting_active_state(self):
        import_at = AUTO_REVIEW_COLLECTION_START_UTC - timedelta(days=1)
        due_at = AUTO_REVIEW_QUEUE_START_UTC - timedelta(minutes=1)
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            active = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[0],
                book_id=self.book_id,
                mistake_count=3,
                review_level=1,
                auto_review_active=True,
                auto_review_correct_streak=1,
                auto_review_due_at=due_at,
                auto_review_activated_at=import_at,
            )
            graduated = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[2],
                book_id=self.book_id,
                mistake_count=4,
                review_level=StudentWordMastery.LEVEL_GRADUATED,
                auto_review_active=False,
            )
            db.session.add_all([active, graduated])
            db.session.commit()
            result = import_legacy_wrong_words(
                user,
                {
                    "book_id": self.book_id,
                    "words": ["alpha", "bravo", "charlie"],
                    "confirmed": True,
                    "confirmed_student_id": self.student_id,
                },
                now=import_at,
            )
            db.session.commit()
            self.assertEqual(result["imported_count"], 1)
            self.assertEqual(result["already_active_count"], 1)
            self.assertEqual(result["skipped_graduated_count"], 1)
            db.session.refresh(active)
            self.assertEqual(active.auto_review_correct_streak, 1)
            self.assertEqual(active.auto_review_due_at, due_at)
            self.assertEqual(active.auto_review_activated_at, import_at)

            imported = StudentWordMastery.query.filter_by(
                student_id=self.student_id,
                word_id=self.word_ids[1],
            ).one()
            self.assertTrue(imported.auto_review_active)
            self.assertEqual(imported.auto_review_activated_at, import_at)

            repeated = import_legacy_wrong_words(
                user,
                {
                    "book_id": self.book_id,
                    "words": ["alpha", "bravo", "charlie"],
                    "confirmed": True,
                    "confirmed_student_id": self.student_id,
                },
                now=AUTO_REVIEW_NOW,
            )
            self.assertEqual(repeated["imported_count"], 0)
            self.assertEqual(repeated["already_active_count"], 2)
            self.assertEqual(repeated["skipped_graduated_count"], 1)

    def test_wrong_then_two_next_day_first_correct_reviews_exit(self):
        first_now = AUTO_REVIEW_NOW
        second_now = AUTO_REVIEW_NOW + timedelta(days=2)
        third_now = AUTO_REVIEW_NOW + timedelta(days=4)
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            db.session.add(
                StudentWordMastery(
                    student_id=self.student_id,
                    word_id=self.word_ids[0],
                    book_id=self.book_id,
                    mistake_count=1,
                    review_level=1,
                    auto_review_active=True,
                    auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                    auto_review_due_at=first_now - timedelta(minutes=1),
                )
            )
            db.session.commit()
            first_task = self._task(start=1, end=1)
            get_task_queue(user, first_task, first_now)
            wrong = submit_dictation_answer(
                user,
                {
                    "task_id": first_task,
                    "word_id": self.word_ids[0],
                    "answer": "wrong",
                    "mode": "audio_to_en",
                    "attempt_id": "state:first",
                    "strict_queue": True,
                },
                now=first_now,
            )
            self.assertFalse(wrong["is_correct"])
            db.session.commit()

            second_task = self._task(start=2, end=2)
            # The due word is outside the assigned range and is therefore
            # automatically claimed by the next same-book task.
            second_queue = get_task_queue(user, second_task, second_now)
            self.assertEqual(second_queue["auto_review_count"], 1)
            correct_one = submit_dictation_answer(
                user,
                {
                    "task_id": second_task,
                    "word_id": self.word_ids[0],
                    "answer": "alpha",
                    "mode": "audio_to_en",
                    "attempt_id": "state:second",
                    "strict_queue": True,
                },
                now=second_now,
            )
            self.assertEqual(correct_one["auto_review_correct_streak"], 0)
            submit_dictation_answer(
                user,
                {
                    "task_id": second_task,
                    "word_id": self.word_ids[1],
                    "answer": "bravo",
                    "mode": "audio_to_en",
                    "attempt_id": "state:second-assigned",
                    "strict_queue": True,
                },
                now=second_now,
            )
            finalized = finalize_strict_task(user, second_task, {}, now=second_now)
            self.assertEqual(finalized["accuracy"], 100.0)
            db.session.commit()
            self.assertEqual(
                StudentWordMastery.query.filter_by(
                    student_id=self.student_id,
                    word_id=self.word_ids[0],
                ).one().auto_review_correct_streak,
                1,
            )

            third_task = self._task(start=3, end=3)
            third_queue = get_task_queue(user, third_task, third_now)
            self.assertEqual(third_queue["auto_review_count"], 1)
            correct_two = submit_dictation_answer(
                user,
                {
                    "task_id": third_task,
                    "word_id": self.word_ids[0],
                    "answer": "alpha",
                    "mode": "audio_to_en",
                    "attempt_id": "state:third",
                    "strict_queue": True,
                },
                now=third_now,
            )
            self.assertEqual(correct_two["auto_review_correct_streak"], 1)
            submit_dictation_answer(
                user,
                {
                    "task_id": third_task,
                    "word_id": self.word_ids[2],
                    "answer": "charlie",
                    "mode": "audio_to_en",
                    "attempt_id": "state:third-assigned",
                    "strict_queue": True,
                },
                now=third_now,
            )
            finalized = finalize_strict_task(user, third_task, {}, now=third_now)
            self.assertEqual(finalized["accuracy"], 100.0)
            db.session.commit()
            mastery = StudentWordMastery.query.filter_by(
                student_id=self.student_id,
                word_id=self.word_ids[0],
            ).one()
            self.assertFalse(mastery.auto_review_active)
            self.assertEqual(mastery.review_level, StudentWordMastery.LEVEL_GRADUATED)

    def test_auto_review_correct_waits_for_finalize_and_finalize_is_idempotent(self):
        now = AUTO_REVIEW_NOW
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            db.session.add(
                StudentWordMastery(
                    student_id=self.student_id,
                    word_id=self.word_ids[0],
                    book_id=self.book_id,
                    mistake_count=1,
                    review_level=1,
                    auto_review_active=True,
                    auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                    auto_review_due_at=now - timedelta(minutes=1),
                )
            )
            db.session.commit()
            task_id = self._task(start=2, end=2)
            queue = get_task_queue(user, task_id, now)
            result = submit_dictation_answer(
                user,
                {
                    "task_id": task_id,
                    "word_id": self.word_ids[0],
                    "answer": "alpha",
                    "mode": "audio_to_en",
                    "attempt_id": "deferred-correct",
                    "strict_queue": True,
                },
                now=now,
            )
            mastery = StudentWordMastery.query.filter_by(
                student_id=self.student_id,
                word_id=self.word_ids[0],
            ).one()
            snapshot = DictationTaskReview.query.filter_by(
                task_id=task_id,
                word_id=self.word_ids[0],
            ).one()
            self.assertTrue(result["is_correct"])
            self.assertEqual(mastery.auto_review_correct_streak, 0)
            self.assertFalse(snapshot.state_applied)

            submit_dictation_answer(
                user,
                {
                    "task_id": task_id,
                    "word_id": self.word_ids[1],
                    "answer": "bravo",
                    "mode": "audio_to_en",
                    "attempt_id": "deferred-assigned",
                    "strict_queue": True,
                },
                now=now,
            )
            db.session.commit()

            with self.assertRaises(DictationReviewError) as invalid_finalize:
                finalize_strict_task(
                    user,
                    task_id,
                    {"queue_token": queue["queue_token"], "duration_seconds": "bad"},
                    now=now,
                )
            self.assertEqual(invalid_finalize.exception.error, "invalid_duration")
            mastery = StudentWordMastery.query.filter_by(
                student_id=self.student_id,
                word_id=self.word_ids[0],
            ).one()
            snapshot = DictationTaskReview.query.filter_by(
                task_id=task_id,
                word_id=self.word_ids[0],
            ).one()
            self.assertEqual(mastery.auto_review_correct_streak, 0)
            self.assertFalse(snapshot.state_applied)

            first_finalize = finalize_strict_task(
                user,
                task_id,
                {"queue_token": queue["queue_token"]},
                now=now,
            )
            db.session.commit()
            self.assertEqual(first_finalize["accuracy"], 100.0)
            self.assertEqual(mastery.auto_review_correct_streak, 1)
            self.assertTrue(snapshot.state_applied)

            second_finalize = finalize_strict_task(
                user,
                task_id,
                {"queue_token": queue["queue_token"]},
                now=now,
            )
            db.session.commit()
            self.assertEqual(second_finalize["accuracy"], 100.0)
            self.assertEqual(mastery.auto_review_correct_streak, 1)

    def test_non_task_correct_does_not_advance_auto_review_state(self):
        now = datetime(2026, 7, 17, 3, 0)
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            mastery = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[0],
                book_id=self.book_id,
                mistake_count=1,
                review_level=1,
                auto_review_active=True,
                auto_review_due_at=now - timedelta(minutes=1),
            )
            db.session.add(mastery)
            db.session.commit()
            result = submit_dictation_answer(
                user,
                {
                    "word_id": self.word_ids[0],
                    "answer": "alpha",
                    "mode": "audio_to_en",
                    "attempt_id": "non-task-correct",
                },
                now=now,
            )
            self.assertTrue(result["is_correct"])
            self.assertTrue(mastery.auto_review_active)
            self.assertEqual(mastery.auto_review_correct_streak, 0)

    def test_attempt_id_over_96_chars_is_rejected(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            with self.assertRaises(DictationReviewError) as context:
                submit_dictation_answer(
                    user,
                    {
                        "word_id": self.word_ids[0],
                        "answer": "alpha",
                        "attempt_id": "x" * 97,
                    },
                )
            self.assertEqual(context.exception.error, "attempt_id_too_long")

    def test_wrong_then_retry_correct_stays_wrong_and_idempotent_attempt_is_safe(self):
        now = AUTO_REVIEW_NOW
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            task_id = self._task(start=1, end=1)
            get_task_queue(user, task_id, now)
            first = submit_dictation_answer(
                user,
                {
                    "task_id": task_id,
                    "word_id": self.word_ids[0],
                    "answer": "alhpa",
                    "mode": "spelling_drill",
                    "attempt_id": "same-attempt",
                    "strict_queue": True,
                },
                now=now,
            )
            duplicate = submit_dictation_answer(
                user,
                {
                    "task_id": task_id,
                    "word_id": self.word_ids[0],
                    "answer": "alhpa",
                    "mode": "spelling_drill",
                    "attempt_id": "same-attempt",
                    "strict_queue": True,
                },
                now=now,
            )
            retry = submit_dictation_answer(
                user,
                {
                    "task_id": task_id,
                    "word_id": self.word_ids[0],
                    "answer": "alpha",
                    "mode": "spelling_drill",
                    "attempt_id": "retry-attempt",
                    "strict_queue": True,
                },
                now=now,
            )
            self.assertFalse(first["is_correct"])
            self.assertTrue(duplicate["idempotent"])
            self.assertFalse(retry["first_attempt"])
            self.assertEqual(DictationRecord.query.filter_by(task_id=task_id).count(), 2)
            mastery = StudentWordMastery.query.filter_by(
                student_id=self.student_id,
                word_id=self.word_ids[0],
            ).one()
            self.assertTrue(mastery.auto_review_active)
            self.assertEqual(mastery.auto_review_correct_streak, 0)

    def test_duplicate_attempt_cannot_cross_task_context(self):
        now = AUTO_REVIEW_NOW
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            first_task = self._task(start=1, end=1)
            get_task_queue(user, first_task, now)
            accepted = submit_dictation_answer(
                user,
                {
                    "task_id": first_task,
                    "word_id": self.word_ids[0],
                    "book_id": self.book_id,
                    "answer": "alpha",
                    "attempt_id": "cross-task-attempt",
                    "strict_queue": True,
                },
                now=now,
            )
            self.assertTrue(accepted["is_correct"])
            db.session.commit()

            second_task = self._task(start=1, end=1)
            get_task_queue(user, second_task, now)
            with self.assertRaises(DictationReviewError) as context:
                submit_dictation_answer(
                    user,
                    {
                        "task_id": second_task,
                        "word_id": self.word_ids[0],
                        "book_id": self.book_id,
                        "answer": "alpha",
                        "attempt_id": "cross-task-attempt",
                        "strict_queue": True,
                    },
                    now=now,
                )
            self.assertEqual(context.exception.error, "attempt_id_conflict")

    def test_review_correct_then_wrong_resets_only_that_word(self):
        first_now = AUTO_REVIEW_NOW
        second_now = AUTO_REVIEW_NOW + timedelta(days=2)
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            db.session.add(
                StudentWordMastery(
                    student_id=self.student_id,
                    word_id=self.word_ids[0],
                    book_id=self.book_id,
                    mistake_count=1,
                    review_level=1,
                    auto_review_active=True,
                    auto_review_activated_at=AUTO_REVIEW_COLLECTION_START_UTC,
                    auto_review_due_at=first_now - timedelta(minutes=1),
                )
            )
            db.session.commit()
            first_task = self._task(start=1, end=1)
            get_task_queue(user, first_task, first_now)
            submit_dictation_answer(
                user,
                {
                    "task_id": first_task,
                    "word_id": self.word_ids[0],
                    "answer": "alpha",
                    "mode": "audio_to_en",
                    "attempt_id": "reset:first",
                    "strict_queue": True,
                },
                now=first_now,
            )
            db.session.commit()
            second_task = self._task(start=2, end=2)
            second_queue = get_task_queue(user, second_task, second_now)
            self.assertEqual(second_queue["auto_review_count"], 1)
            submit_dictation_answer(
                user,
                {
                    "task_id": second_task,
                    "word_id": self.word_ids[0],
                    "answer": "not-alpha",
                    "mode": "audio_to_en",
                    "attempt_id": "reset:second",
                    "strict_queue": True,
                },
                now=second_now,
            )
            db.session.commit()
            mastery = StudentWordMastery.query.filter_by(
                student_id=self.student_id,
                word_id=self.word_ids[0],
            ).one()
            self.assertTrue(mastery.auto_review_active)
            self.assertEqual(mastery.auto_review_correct_streak, 0)
            self.assertEqual(mastery.review_level, 1)

    def test_strict_task_score_is_server_merged_score(self):
        now = AUTO_REVIEW_NOW
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            task_id = self._task(start=1, end=2)
            queue = get_task_queue(user, task_id, now)
            for item in queue["words"]:
                answer = item["word"] if item["word_id"] == self.word_ids[0] else "wrong"
                submit_dictation_answer(
                    user,
                    {
                        "task_id": task_id,
                        "word_id": item["word_id"],
                        "answer": answer,
                        "mode": "audio_to_en",
                        "attempt_id": f"score:{item['word_id']}",
                        "strict_queue": True,
                    },
                    now=now,
                )
            db.session.commit()
            response = self.client.post(
                f"/api/miniprogram/student/tasks/{task_id}/submit",
                headers=self.headers,
                json={
                    "strict_queue": True,
                    "queue_token": queue["queue_token"],
                },
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            result = response.get_json()
            self.assertEqual(result["correct_count"], 1)
            self.assertEqual(result["total_count"], 2)
            self.assertEqual(result["accuracy"], 50.0)
            self.assertEqual(Task.query.get(task_id).accuracy, 50.0)

    def test_strict_task_submission_rejects_missing_first_answers(self):
        with self.app.app_context():
            task_id = self._task(start=1, end=2)
        queue = self._queue(task_id)
        response = self.client.post(
            f"/api/miniprogram/student/tasks/{task_id}/submit",
            headers=self.headers,
            json={"strict_queue": True, "queue_token": queue["queue_token"]},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "queue_incomplete")

    def test_all_four_modes_grade_on_server(self):
        answers = {
            "audio_to_en": "alpha",
            "zh_to_en": "bravo",
            "en_to_zh": "丙",
            "spelling_drill": "delta",
        }
        word_ids = {
            "audio_to_en": self.word_ids[0],
            "zh_to_en": self.word_ids[1],
            "en_to_zh": self.word_ids[2],
            "spelling_drill": self.word_ids[3],
        }
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            for mode, answer in answers.items():
                result = submit_dictation_answer(
                    user,
                    {
                        "word_id": word_ids[mode],
                        "answer": answer,
                        "mode": mode,
                        "attempt_id": f"mode:{mode}",
                    },
                    now=AUTO_REVIEW_NOW,
                )
                self.assertTrue(result["is_correct"], mode)

    def test_strict_task_uses_server_owned_task_mode(self):
        with self.app.app_context():
            task_id = self._task(start=1, end=1, mode="en_to_zh")
            user = db.session.get(User, self.student_id)
            queue = get_task_queue(user, task_id)
            result = submit_dictation_answer(
                user,
                {
                    "task_id": task_id,
                    "word_id": self.word_ids[0],
                    "answer": "甲",
                    "mode": "audio_to_en",
                    "attempt_id": "server-mode-authoritative",
                    "strict_queue": True,
                },
            )
            self.assertTrue(result["is_correct"])
            self.assertEqual(queue["task_mode"], "en_to_zh")

    def test_wrong_list_and_confirmed_legacy_import(self):
        with self.app.app_context():
            student = db.session.get(User, self.student_id)
            db.session.add(
                StudentWordMastery(
                    student_id=student.id,
                    word_id=self.word_ids[0],
                    book_id=self.book_id,
                    mistake_count=1,
                    review_level=1,
                    auto_review_active=True,
                    auto_review_due_at=datetime(2026, 7, 16, 15, 0),
                )
            )
            db.session.add(
                StudentWordMastery(
                    student_id=student.id,
                    word_id=self.word_ids[2],
                    book_id=self.book_id,
                    mistake_count=4,
                    review_level=StudentWordMastery.LEVEL_GRADUATED,
                    auto_review_active=False,
                    auto_review_correct_streak=0,
                    auto_review_due_at=None,
                )
            )
            db.session.commit()
        listed = self.client.get(
            f"/api/miniprogram/student/dictation-wrongs?book_id={self.book_id}",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["student"]["id"], self.student_id)
        missing_confirmation = self.client.post(
            "/api/miniprogram/student/dictation-wrongs/import",
            headers=self.headers,
            json={"book_id": self.book_id, "words": ["bravo"]},
        )
        self.assertEqual(missing_confirmation.status_code, 400)
        imported = self.client.post(
            "/api/miniprogram/student/dictation-wrongs/import",
            headers=self.headers,
            json={
                "book_id": self.book_id,
                "words": ["bravo", "charlie", "not-in-book"],
                "confirmed": True,
                "confirmed_student_id": self.student_id,
            },
        )
        self.assertEqual(imported.status_code, 201)
        self.assertEqual(imported.get_json()["imported_count"], 1)
        self.assertEqual(imported.get_json()["already_active_count"], 0)
        self.assertEqual(imported.get_json()["skipped_graduated_count"], 1)
        self.assertEqual(imported.get_json()["unresolved"], ["not-in-book"])
        imported_again = self.client.post(
            "/api/miniprogram/student/dictation-wrongs/import",
            headers=self.headers,
            json={
                "book_id": self.book_id,
                "words": ["bravo", "charlie"],
                "confirmed": True,
                "confirmed_student_id": self.student_id,
            },
        )
        self.assertEqual(imported_again.status_code, 201)
        self.assertEqual(imported_again.get_json()["imported_count"], 0)
        self.assertEqual(imported_again.get_json()["already_active_count"], 1)
        self.assertEqual(imported_again.get_json()["skipped_graduated_count"], 1)

    def test_local_midnight_uses_asia_shanghai(self):
        now = datetime(2026, 7, 16, 15, 0)
        self.assertEqual(next_local_midnight(now), datetime(2026, 7, 16, 16, 0))

    def test_incremental_schema_is_idempotent_and_keeps_indexes(self):
        with self.app.app_context():
            legacy = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[4],
                book_id=self.book_id,
                mistake_count=2,
                review_level=1,
                next_review_at=datetime(2026, 7, 17, 16, 0),
            )
            legacy_without_due = StudentWordMastery(
                student_id=self.student_id,
                word_id=self.word_ids[5],
                book_id=self.book_id,
                mistake_count=1,
                review_level=1,
                next_review_at=None,
            )
            db.session.add_all([legacy, legacy_without_due])
            db.session.commit()
            migration_now = datetime(2026, 7, 16, 15, 0)
            ensure_incremental_schema(db.engine, now=migration_now)
            ensure_incremental_schema(db.engine, now=migration_now)
            db.session.refresh(legacy)
            db.session.refresh(legacy_without_due)
            # Migration adds columns/indexes only.  It must not activate old
            # mastery rows or manufacture a due time from the DB clock.
            self.assertFalse(legacy.auto_review_active)
            self.assertIsNone(legacy.auto_review_due_at)
            self.assertIsNone(legacy.auto_review_activated_at)
            self.assertFalse(legacy_without_due.auto_review_active)
            self.assertIsNone(legacy_without_due.auto_review_due_at)
            self.assertIsNone(legacy_without_due.auto_review_activated_at)
            inspector = sqlalchemy_inspect(db.engine)
            record_indexes = {
                index["name"] for index in inspector.get_indexes("dictation_record")
            }
            record_indexes.update(
                constraint["name"]
                for constraint in inspector.get_unique_constraints("dictation_record")
            )
            self.assertIn("uq_dictation_record_student_attempt", record_indexes)
            mastery_indexes = {
                index["name"]
                for index in inspector.get_indexes("student_word_mastery")
            }
            self.assertIn("ix_mastery_auto_review_due", mastery_indexes)
            self.assertIn("ix_mastery_auto_review_activated", mastery_indexes)


if __name__ == "__main__":
    unittest.main()
