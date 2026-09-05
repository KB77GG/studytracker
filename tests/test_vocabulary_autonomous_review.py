import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

import jwt
from flask import Flask
from flask_login import LoginManager
from sqlalchemy.exc import OperationalError

from api.miniprogram import mp_bp
from api.vocab_review import vocab_review_bp
from models import (
    DictationBook,
    DictationWord,
    StudentProfile,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    VocabularyReviewSession,
    db,
)
from services.task_date_gate import beijing_today
from services.vocabulary_autonomous_review import (
    VocabularyAutonomousReviewError,
    claim_today_review,
    get_review_session,
    review_preflight,
    review_summary,
    settle_review_session,
    submit_review_answer,
    submit_review_correction,
)
from services.vocabulary_context import build_context_question
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

    def _answer_all(self, session, *, now=None):
        submitted_at = now or self.now
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
                now=submitted_at,
            )
            self.assertTrue(result["is_correct"])

    def _api_get_with_review_clock(self, path):
        def fixed_claim_today_review(user, origin_task_id=None):
            return claim_today_review(
                user,
                origin_task_id=origin_task_id,
                now=self.now,
            )

        def fixed_review_preflight(user, task_id):
            return review_preflight(user, task_id, now=self.now)

        def fixed_group_queue(user, task_id, **kwargs):
            return get_vocabulary_group_queue(user, task_id, now=self.now, **kwargs)

        with patch(
            "api.vocab_review.claim_today_review",
            side_effect=fixed_claim_today_review,
        ), patch(
            "api.vocab_review.review_preflight",
            side_effect=fixed_review_preflight,
        ), patch(
            "api.vocab_review.get_vocabulary_group_queue",
            side_effect=fixed_group_queue,
        ):
            return self.client.get(path, headers=self.headers)

    def _api_review_request_with_clock(self, method, path, *, now, payload=None):
        def fixed_claim_today_review(user, origin_task_id=None):
            return claim_today_review(
                user,
                origin_task_id=origin_task_id,
                now=now,
            )

        def fixed_submit_review_answer(
            user,
            session_id,
            request_payload,
            *,
            session_token=None,
        ):
            return submit_review_answer(
                user,
                session_id,
                request_payload,
                session_token=session_token,
                now=now,
            )

        def fixed_submit_review_correction(
            user,
            session_id,
            request_payload,
            *,
            session_token=None,
        ):
            return submit_review_correction(
                user,
                session_id,
                request_payload,
                session_token=session_token,
                now=now,
            )

        def fixed_settle_review_session(
            user,
            session_id,
            request_payload=None,
            *,
            session_token=None,
        ):
            return settle_review_session(
                user,
                session_id,
                request_payload,
                session_token=session_token,
                now=now,
            )

        with patch(
            "api.vocab_review.claim_today_review",
            side_effect=fixed_claim_today_review,
        ), patch(
            "api.vocab_review.submit_review_answer",
            side_effect=fixed_submit_review_answer,
        ), patch(
            "api.vocab_review.submit_review_correction",
            side_effect=fixed_submit_review_correction,
        ), patch(
            "api.vocab_review.settle_review_session",
            side_effect=fixed_settle_review_session,
        ):
            return self.client.open(
                path,
                method=method,
                json=payload,
                headers=self.headers,
            )

    def _run_bounded_correction_case(self, dimension, expected_mode, *, context_kind=None):
        """Exercise one public mode through correction, delay, and retry claim."""

        user = db.session.get(User, self.student_id)
        masteries = StudentVocabularyMastery.query.filter_by(student_id=user.id).all()
        target = masteries[0]
        for mastery in masteries:
            for candidate_dimension in StudentVocabularyMastery.DIMENSIONS:
                setattr(
                    mastery,
                    f"{candidate_dimension}_next_due_at",
                    self.now + timedelta(days=10),
                )
        setattr(target, f"{dimension}_next_due_at", self.now)
        word = target.representative_word
        target_word = str(word.word).split()[0]
        word.usage_pattern = f"{target_word} on evidence"
        word.example_en = f"Students {target_word} on evidence."
        word.example_zh = "学生依赖证据。"
        db.session.flush()
        claimed = claim_today_review(user, now=self.now)
        self.assertEqual(claimed["total_count"], 1)
        item = claimed["items"][0]
        stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
        if context_kind:
            generated = build_context_question(
                word,
                DictationWord.query.filter_by(book_id=word.book_id).all(),
                seed=f"autonomous-mode:{context_kind}:{word.id}",
                allowed_kinds={context_kind},
            )
            self.assertIsNotNone(generated)
            public, answer_payload = generated
            stored.question_id = public["question_id"]
            stored.question_snapshot_json = json.dumps(public, ensure_ascii=False, sort_keys=True)
            stored.answer_payload_json = json.dumps(answer_payload, ensure_ascii=False, sort_keys=True)
            item = dict(item, question_id=stored.question_id, question=public)
        db.session.flush()
        identity = {
            "session_token": claimed["session_token"],
            "review_item_id": stored.id,
            "question_id": stored.question_id,
            "word_id": stored.word_id,
            "sense_id": stored.sense_id,
            "dimension": stored.dimension,
        }
        self.assertEqual(json.loads(stored.question_snapshot_json)["mode"], expected_mode)
        wrong = submit_review_answer(
            user,
            claimed["session_id"],
            dict(identity, answer="明显错误", attempt_id=f"mode-first:{dimension}"),
            now=self.now,
        )
        self.assertFalse(wrong["is_correct"])
        self.assertTrue(wrong["correction_required"])
        with self.assertRaises(VocabularyAutonomousReviewError) as incomplete:
            settle_review_session(
                user,
                claimed["session_id"],
                {"queue_token": claimed["queue_token"]},
                session_token=claimed["session_token"],
                now=self.now,
            )
        self.assertEqual(incomplete.exception.error, "review_session_incomplete")
        wrong_correction = submit_review_correction(
            user,
            claimed["session_id"],
            dict(identity, answer="仍然错误", attempt_id=f"mode-correction-wrong:{dimension}"),
            now=self.now,
        )
        self.assertFalse(wrong_correction["correction_completed"])
        self.assertTrue(wrong_correction["correction_required"])
        duplicate = submit_review_correction(
            user,
            claimed["session_id"],
            dict(identity, answer="另一个错误", attempt_id=f"mode-correction-wrong:{dimension}"),
            now=self.now,
        )
        self.assertTrue(duplicate["idempotent"])
        self.assertTrue(duplicate["correction_required"])
        expected_answer = json.loads(stored.answer_payload_json).get("answer")
        if json.loads(stored.answer_payload_json).get("answer_type") == "option_id":
            expected_answer = json.loads(stored.answer_payload_json).get("answer_option_id")
        corrected = submit_review_correction(
            user,
            claimed["session_id"],
            dict(
                identity,
                answer=expected_answer,
                attempt_id=f"mode-correction-right:{dimension}",
            ),
            now=self.now,
        )
        self.assertTrue(corrected["correction_completed"])
        self.assertFalse(corrected["correction_required"])
        self.assertEqual(corrected["correction_count"], 2)
        self.assertEqual(
            corrected["correction_attempt_id"],
            f"mode-correction-right:{dimension}",
        )
        stale_replay = submit_review_correction(
            user,
            claimed["session_id"],
            dict(
                identity,
                answer="旧 attempt 不得覆盖",
                attempt_id=f"mode-correction-wrong:{dimension}",
            ),
            now=self.now,
        )
        self.assertTrue(stale_replay["idempotent"])
        self.assertEqual(
            db.session.get(VocabularyReviewItem, stored.id).correction_attempt_id,
            f"mode-correction-right:{dimension}",
        )
        self.assertEqual(
            db.session.get(VocabularyReviewItem, stored.id).correction_count,
            2,
        )
        settled = settle_review_session(
            user,
            claimed["session_id"],
            {"queue_token": claimed["queue_token"]},
            session_token=claimed["session_token"],
            now=self.now,
        )
        self.assertEqual(settled["total_count"], 1)
        mastery = db.session.get(StudentVocabularyMastery, target.id)
        self.assertEqual(
            getattr(mastery, f"{dimension}_next_due_at"),
            self.now + timedelta(days=1),
        )
        self.assertTrue(claim_today_review(user, now=self.now + timedelta(hours=1))["empty"])
        next_day = claim_today_review(user, now=self.now + timedelta(days=1))
        self.assertEqual(next_day["total_count"], 1)
        self.assertEqual(next_day["items"][0]["remediation_kind"], "same_dimension")
        return user, next_day

    def test_autonomous_zh_to_en_has_correction_and_day1_retry(self):
        with self.app.app_context():
            self._run_bounded_correction_case("form_recall", "zh_to_en")

    def test_autonomous_audio_to_en_has_correction_and_day1_retry(self):
        with self.app.app_context():
            self._run_bounded_correction_case("audio_form_recall", "audio_to_en")

    def test_autonomous_en_to_zh_has_correction_and_day1_retry(self):
        with self.app.app_context():
            self._run_bounded_correction_case("meaning_recall", "en_to_zh")

    def test_autonomous_context_choice_has_correction_and_day1_retry(self):
        with self.app.app_context():
            self._run_bounded_correction_case(
                "context_use", "context_choice", context_kind="meaning_choice"
            )

    def test_autonomous_context_fill_has_correction_and_day1_retry(self):
        with self.app.app_context():
            self._run_bounded_correction_case(
                "context_use", "context_fill", context_kind="example_fill"
            )

    def test_autonomous_failed_delayed_retry_releases_one_related_dimension(self):
        with self.app.app_context():
            user, delayed = self._run_bounded_correction_case(
                "form_recall", "zh_to_en"
            )
            item = delayed["items"][0]
            identity = {
                "session_token": delayed["session_token"],
                "review_item_id": item["review_item_id"],
                "question_id": item["question_id"],
                "word_id": item["word_id"],
                "sense_id": item["sense_id"],
                "dimension": item["dimension"],
            }
            wrong = submit_review_answer(
                user,
                delayed["session_id"],
                dict(identity, answer="又一次错误", attempt_id="related-retry-first"),
                now=self.now + timedelta(days=1),
            )
            self.assertTrue(wrong["correction_required"])
            stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
            expected = json.loads(stored.answer_payload_json).get("answer")
            corrected = submit_review_correction(
                user,
                delayed["session_id"],
                dict(identity, answer=expected, attempt_id="related-retry-correction"),
                now=self.now + timedelta(days=1),
            )
            self.assertTrue(corrected["correction_completed"])
            settle_review_session(
                user,
                delayed["session_id"],
                {"queue_token": delayed["queue_token"]},
                session_token=delayed["session_token"],
                now=self.now + timedelta(days=1),
            )
            related_day = claim_today_review(user, now=self.now + timedelta(days=2))
            dimensions = [candidate["dimension"] for candidate in related_day["items"]]
            self.assertEqual(dimensions, ["context_use"])
            self.assertLessEqual(
                sum(candidate["remediation_kind"] is not None for candidate in related_day["items"]),
                2,
            )

    def test_comprehensive_sense_rotates_one_dimension_per_day(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            masteries = StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id
            ).all()
            target = masteries[0]
            word = target.representative_word
            word_word = str(word.word).split()[0]
            word.usage_pattern = f"{word_word} on evidence"
            word.example_en = f"Students {word_word} on evidence."
            word.example_zh = "学生依赖证据。"
            for mastery in masteries:
                for dimension in StudentVocabularyMastery.DIMENSIONS:
                    setattr(
                        mastery,
                        f"{dimension}_next_due_at",
                        self.now + timedelta(days=30),
                    )
                    setattr(mastery, f"{dimension}_stage", 0)
                    setattr(mastery, f"{dimension}_last_answered_at", None)
            for dimension in StudentVocabularyMastery.DIMENSIONS:
                setattr(target, f"{dimension}_next_due_at", self.now)
            db.session.commit()

            expected_dimensions = [
                "meaning_recall",
                "audio_form_recall",
                "form_recall",
                "context_use",
            ]
            seen_dimensions = []
            for day, expected_dimension in enumerate(expected_dimensions):
                current = self.now + timedelta(days=day)
                claimed = claim_today_review(user, now=current)
                self.assertEqual(claimed["total_count"], 1)
                self.assertEqual(claimed["due_count"], 1)
                self.assertEqual(
                    len({item["sense_id"] for item in claimed["items"]}),
                    1,
                )
                item = claimed["items"][0]
                self.assertEqual(item["sense_id"], target.sense_id)
                self.assertEqual(item["dimension"], expected_dimension)
                seen_dimensions.append(item["dimension"])
                stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
                answer = json.loads(stored.answer_payload_json).get("answer")
                if json.loads(stored.answer_payload_json).get("answer_type") == "option_id":
                    answer = json.loads(stored.answer_payload_json)["answer_option_id"]
                answered = submit_review_answer(
                    user,
                    claimed["session_id"],
                    {
                        "session_token": claimed["session_token"],
                        "review_item_id": item["review_item_id"],
                        "question_id": item["question_id"],
                        "word_id": item["word_id"],
                        "sense_id": item["sense_id"],
                        "dimension": item["dimension"],
                        "answer": answer,
                        "attempt_id": f"rotation-first-{day}",
                    },
                    now=current,
                )
                self.assertTrue(answered["is_correct"])
                settled = settle_review_session(
                    user,
                    claimed["session_id"],
                    {"queue_token": claimed["queue_token"]},
                    session_token=claimed["session_token"],
                    now=current,
                )
                self.assertEqual(settled["total_count"], 1)
                self.assertEqual(settled["remaining_due_count"], 0)
                same_day = claim_today_review(user, now=current + timedelta(hours=1))
                self.assertTrue(same_day["empty"])
                self.assertEqual(same_day["remaining_due_count"], 0)
                self.assertEqual(review_summary(user, now=current + timedelta(hours=1))["due_count"], 0)
                if day == 0:
                    preflight = review_preflight(user, self.task_id, now=current)
                    self.assertEqual(preflight["due_count"], 0)

            self.assertEqual(seen_dimensions, expected_dimensions)
            next_day = claim_today_review(
                user,
                now=self.now + timedelta(days=len(expected_dimensions)),
            )
            self.assertTrue(next_day["total_count"] <= 1)

    def test_due_batch_never_repeats_a_sense_and_error_wins(self):
        with self.app.app_context():
            rows = StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id
            ).order_by(StudentVocabularyMastery.sense_id.asc()).all()
            for mastery in rows:
                for dimension in StudentVocabularyMastery.DIMENSIONS:
                    setattr(mastery, f"{dimension}_next_due_at", self.now)
                    setattr(mastery, f"{dimension}_stage", 0)
                    setattr(mastery, f"{dimension}_last_answered_at", None)
            failed = rows[1]
            failed.meaning_recall_last_answered_at = self.now - timedelta(days=1)
            db.session.commit()

            claimed = claim_today_review(
                db.session.get(User, self.student_id),
                now=self.now,
            )
            sense_ids = [item["sense_id"] for item in claimed["items"]]
            self.assertGreater(len(sense_ids), 1)
            self.assertEqual(len(sense_ids), len(set(sense_ids)))
            self.assertEqual(claimed["items"][0]["sense_id"], failed.sense_id)

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
            restored_from_api = self._api_get_with_review_clock(
                "/api/miniprogram/student/vocabulary-review/today",
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

    def test_new_day_expires_partial_session_before_claiming_current_task_review(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            stale = claim_today_review(
                user,
                origin_task_id=self.task_id,
                now=self.now,
            )
            stale_item = stale["items"][0]
            stored_stale_item = db.session.get(
                VocabularyReviewItem,
                stale_item["review_item_id"],
            )
            expected = json.loads(stored_stale_item.answer_payload_json).get("answer")
            if json.loads(stored_stale_item.answer_payload_json).get("answer_type") == "option_id":
                expected = json.loads(stored_stale_item.answer_payload_json)["answer_option_id"]
            submit_review_answer(
                user,
                stale["session_id"],
                {
                    "session_token": stale["session_token"],
                    "review_item_id": stale_item["review_item_id"],
                    "question_id": stale_item["question_id"],
                    "word_id": stale_item["word_id"],
                    "sense_id": stale_item["sense_id"],
                    "dimension": stale_item["dimension"],
                    "answer": expected,
                    "attempt_id": "stale-review-first-answer",
                },
                now=self.now,
            )
            db.session.commit()

            next_day = self.now + timedelta(days=1)
            current_task = Task(
                date=beijing_today(next_day),
                student_name="自主复习学生",
                category="词汇",
                detail="次日独立队列任务",
                created_by=db.session.get(Task, self.task_id).created_by,
                dictation_book_id=db.session.get(Task, self.task_id).dictation_book_id,
                vocabulary_goal="reading",
                dictation_word_start=1,
                dictation_word_end=1,
                status="pending",
            )
            db.session.add(current_task)
            db.session.commit()

            summary = review_summary(user, now=next_day)
            self.assertFalse(summary["has_active_session"])
            self.assertIsNone(summary["active_session_id"])
            preflight = review_preflight(user, current_task.id, now=next_day)
            self.assertTrue(preflight["required"])
            self.assertIsNone(preflight["active_session_id"])

            current = claim_today_review(
                user,
                origin_task_id=current_task.id,
                now=next_day,
            )
            self.assertNotEqual(current["session_id"], stale["session_id"])
            self.assertEqual(current["review_date"], beijing_today(next_day).isoformat())
            self.assertEqual(current["origin_task_id"], current_task.id)

            expired = db.session.get(VocabularyReviewSession, stale["session_id"])
            self.assertEqual(expired.status, VocabularyReviewSession.STATUS_EXPIRED)
            self.assertIsNone(expired.claim_key)
            self.assertEqual(
                VocabularyReviewAttempt.query.filter_by(session_id=expired.id).count(),
                1,
            )

            current_item = current["items"][0]
            stored_current_item = db.session.get(
                VocabularyReviewItem,
                current_item["review_item_id"],
            )
            current_expected = json.loads(stored_current_item.answer_payload_json).get("answer")
            if json.loads(stored_current_item.answer_payload_json).get("answer_type") == "option_id":
                current_expected = json.loads(stored_current_item.answer_payload_json)[
                    "answer_option_id"
                ]
            accepted = submit_review_answer(
                user,
                current["session_id"],
                {
                    "session_token": current["session_token"],
                    "review_item_id": current_item["review_item_id"],
                    "question_id": current_item["question_id"],
                    "word_id": current_item["word_id"],
                    "sense_id": current_item["sense_id"],
                    "dimension": current_item["dimension"],
                    "answer": current_expected,
                    "attempt_id": "current-review-first-answer",
                },
                now=next_day,
            )
            self.assertTrue(accepted["is_correct"])

    def test_http_new_day_replaces_stale_session_and_blocks_every_old_write(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            stale = claim_today_review(
                user,
                origin_task_id=self.task_id,
                now=self.now,
            )
            wrong_item, unanswered_item = stale["items"][:2]
            wrong = submit_review_answer(
                user,
                stale["session_id"],
                {
                    "session_token": stale["session_token"],
                    "review_item_id": wrong_item["review_item_id"],
                    "question_id": wrong_item["question_id"],
                    "word_id": wrong_item["word_id"],
                    "sense_id": wrong_item["sense_id"],
                    "dimension": wrong_item["dimension"],
                    "answer": "definitely-wrong-review-answer",
                    "attempt_id": "http-stale-review-wrong",
                    "supports_correction": True,
                },
                now=self.now,
            )
            self.assertTrue(wrong["correction_required"])
            stored_wrong = db.session.get(
                VocabularyReviewItem,
                wrong_item["review_item_id"],
            )
            correction_answer_payload = json.loads(stored_wrong.answer_payload_json)
            correction_answer = correction_answer_payload.get(
                "answer"
            ) or correction_answer_payload.get("answer_option_id")

            next_day = self.now + timedelta(days=1)
            original_task = db.session.get(Task, self.task_id)
            current_task = Task(
                date=beijing_today(next_day),
                student_name="自主复习学生",
                category="词汇",
                detail="次日 HTTP 独立队列任务",
                created_by=original_task.created_by,
                dictation_book_id=original_task.dictation_book_id,
                vocabulary_goal="reading",
                dictation_word_start=1,
                dictation_word_end=1,
                status="pending",
            )
            db.session.add(current_task)
            db.session.commit()
            current_task_id = current_task.id

        today = self._api_review_request_with_clock(
            "GET",
            (
                "/api/miniprogram/student/vocabulary-review/today"
                f"?origin_task_id={current_task_id}"
            ),
            now=next_day,
        )
        self.assertEqual(today.status_code, 200, today.get_json())
        current = today.get_json()
        self.assertNotEqual(current["session_id"], stale["session_id"])
        self.assertEqual(current["origin_task_id"], current_task_id)

        with self.app.app_context():
            expired = db.session.get(VocabularyReviewSession, stale["session_id"])
            self.assertEqual(expired.status, VocabularyReviewSession.STATUS_EXPIRED)
            self.assertIsNone(expired.claim_key)
            self.assertEqual(
                VocabularyReviewAttempt.query.filter_by(session_id=expired.id).count(),
                1,
            )
            current_item = db.session.get(
                VocabularyReviewItem,
                current["items"][0]["review_item_id"],
            )
            current_answer_payload = json.loads(current_item.answer_payload_json)
            current_answer = current_answer_payload.get(
                "answer"
            ) or current_answer_payload.get("answer_option_id")

        current_answer_response = self._api_review_request_with_clock(
            "POST",
            (
                "/api/miniprogram/student/vocabulary-review/sessions/"
                f"{current['session_id']}/answers"
            ),
            now=next_day,
            payload={
                "session_token": current["session_token"],
                "review_item_id": current_item.id,
                "question_id": current_item.question_id,
                "word_id": current_item.word_id,
                "sense_id": current_item.sense_id,
                "dimension": current_item.dimension,
                "answer": current_answer,
                "attempt_id": "http-current-review-answer",
            },
        )
        self.assertEqual(
            current_answer_response.status_code,
            200,
            current_answer_response.get_json(),
        )

        stale_answer_payload = {
            "session_token": stale["session_token"],
            "review_item_id": unanswered_item["review_item_id"],
            "question_id": unanswered_item["question_id"],
            "word_id": unanswered_item["word_id"],
            "sense_id": unanswered_item["sense_id"],
            "dimension": unanswered_item["dimension"],
            "answer": "blocked-after-midnight",
            "attempt_id": "http-stale-review-answer-after-midnight",
        }
        stale_correction_payload = {
            "session_token": stale["session_token"],
            "review_item_id": wrong_item["review_item_id"],
            "question_id": wrong_item["question_id"],
            "word_id": wrong_item["word_id"],
            "sense_id": wrong_item["sense_id"],
            "dimension": wrong_item["dimension"],
            "answer": correction_answer,
            "attempt_id": "http-stale-review-correction-after-midnight",
        }
        stale_settle_payload = {
            "session_token": stale["session_token"],
            "queue_token": stale["queue_token"],
        }
        stale_writes = (
            (
                f"/api/miniprogram/student/vocabulary-review/sessions/"
                f"{stale['session_id']}/answers",
                stale_answer_payload,
            ),
            (
                f"/api/miniprogram/student/vocabulary-review/sessions/"
                f"{stale['session_id']}/corrections",
                stale_correction_payload,
            ),
            (
                f"/api/miniprogram/student/vocabulary-review/sessions/"
                f"{stale['session_id']}/settle",
                stale_settle_payload,
            ),
        )
        for path, payload in stale_writes:
            blocked = self._api_review_request_with_clock(
                "POST",
                path,
                now=next_day,
                payload=payload,
            )
            self.assertEqual(blocked.status_code, 403, blocked.get_json())
            self.assertEqual(blocked.get_json()["error"], "task_expired")
            self.assertEqual(blocked.get_json()["task_date_state"], "expired")

        with self.app.app_context():
            self.assertEqual(
                VocabularyReviewAttempt.query.filter_by(
                    session_id=stale["session_id"],
                ).count(),
                1,
            )

    def test_http_stale_rollover_lock_conflict_is_retryable(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            stale = claim_today_review(user, now=self.now)
            db.session.commit()

        locked = OperationalError(
            "UPDATE vocabulary_review_session",
            {},
            RuntimeError("database is locked"),
        )
        with patch(
            "services.vocabulary_autonomous_review.db.session.flush",
            side_effect=locked,
        ):
            response = self._api_review_request_with_clock(
                "GET",
                "/api/miniprogram/student/vocabulary-review/today",
                now=self.now + timedelta(days=1),
            )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "review_claim_in_progress")
        with self.app.app_context():
            restored = db.session.get(VocabularyReviewSession, stale["session_id"])
            self.assertEqual(restored.status, VocabularyReviewSession.STATUS_ACTIVE)
            self.assertIsNotNone(restored.claim_key)

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
            correction_answer = json.loads(
                db.session.get(VocabularyReviewItem, first_item["review_item_id"]).answer_payload_json
            ).get("answer")
            correction = submit_review_correction(
                user,
                session_payload["session_id"],
                {
                    "session_token": session_payload["session_token"],
                    "review_item_id": first_item["review_item_id"],
                    "question_id": first_item["question_id"],
                    "word_id": first_item["word_id"],
                    "sense_id": first_item["sense_id"],
                    "dimension": first_item["dimension"],
                    "answer": correction_answer,
                    "attempt_id": "autonomous-wrong-correction",
                },
                now=self.now,
            )
            self.assertTrue(correction["correction_completed"])
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
            db.session.get(Task, self.task_id).date = beijing_today()
            db.session.commit()
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
            session_now = datetime.combine(
                stored_session.review_date,
                datetime.min.time(),
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
                    now=session_now,
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

    def test_http_wrong_review_requires_correction_and_keeps_false_feedback(self):
        today = self.client.get(
            "/api/miniprogram/student/vocabulary-review/today",
            headers=self.headers,
        )
        self.assertEqual(today.status_code, 200, today.get_json())
        session = today.get_json()
        item = session["items"][0]
        answer_payload = {
            "session_token": session["session_token"],
            "review_item_id": item["review_item_id"],
            "question_id": item["question_id"],
            "word_id": item["word_id"],
            "sense_id": item["sense_id"],
            "dimension": item["dimension"],
            "answer": "明显错误",
            "attempt_id": "http-review-wrong-first",
            "supports_correction": True,
        }
        wrong = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/answers",
            json=answer_payload,
            headers=self.headers,
        )
        self.assertEqual(wrong.status_code, 200, wrong.get_json())
        self.assertTrue(wrong.get_json()["correction_required"])
        correction_payload = dict(
            answer_payload,
            answer="仍然错误",
            attempt_id="http-review-wrong-correction",
        )
        correction = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/corrections",
            json=correction_payload,
            headers=self.headers,
        )
        self.assertEqual(correction.status_code, 200, correction.get_json())
        self.assertFalse(correction.get_json()["correction_completed"])
        self.assertTrue(correction.get_json()["correction_required"])
        duplicate = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/corrections",
            json=dict(correction_payload, answer="别的错误"),
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertTrue(duplicate.get_json()["idempotent"])
        self.assertTrue(duplicate.get_json()["correction_required"])

    def test_published_legacy_client_can_settle_wrong_review_without_correction_ui(self):
        today = self.client.get(
            "/api/miniprogram/student/vocabulary-review/today?limit=1",
            headers=self.headers,
        )
        self.assertEqual(today.status_code, 200, today.get_json())
        session = today.get_json()
        item = session["items"][0]
        wrong = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/answers",
            json={
                "session_token": session["session_token"],
                "review_item_id": item["review_item_id"],
                "question_id": item["question_id"],
                "word_id": item["word_id"],
                "sense_id": item["sense_id"],
                "dimension": item["dimension"],
                "answer": "legacy-wrong-answer",
                "attempt_id": "legacy-review-first-wrong",
            },
            headers=self.headers,
        )
        self.assertEqual(wrong.status_code, 200, wrong.get_json())
        self.assertFalse(wrong.get_json()["correction_required"])
        with self.app.app_context():
            stored_session = db.session.get(
                VocabularyReviewSession,
                session["session_id"],
            )
            session_now = datetime.combine(
                stored_session.review_date,
                datetime.min.time(),
            )
            # Recreate the transitional state left by the brief pre-hotfix
            # deployment. Legacy settlement must still release it.
            first_item = db.session.get(VocabularyReviewItem, item["review_item_id"])
            first_item.correction_exhausted = False
            first_item.deferred_to_review = False
            for tail in stored_session.items:
                if tail.first_attempt_id:
                    continue
                expected = json.loads(tail.answer_payload_json)
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
                        "answer": expected.get("answer")
                        or expected.get("answer_option_id"),
                        "attempt_id": f"legacy-review-tail-{tail.id}",
                    },
                    now=session_now,
                )
            db.session.commit()
        settled = self.client.post(
            f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/settle",
            json={
                "session_token": session["session_token"],
                "queue_token": session["queue_token"],
            },
            headers=self.headers,
        )
        self.assertEqual(settled.status_code, 200, settled.get_json())
        self.assertEqual(settled.get_json()["status"], "settled")

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

    def test_previous_day_home_review_rejects_direct_answer_without_origin_task(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            claimed = claim_today_review(user, now=self.now)
            item = claimed["items"][0]
            stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
            answer_payload = json.loads(stored.answer_payload_json)
            answer = answer_payload.get("answer") or answer_payload.get("answer_option_id")

            with self.assertRaises(VocabularyAutonomousReviewError) as blocked:
                submit_review_answer(
                    user,
                    claimed["session_id"],
                    {
                        "session_token": claimed["session_token"],
                        "review_item_id": item["review_item_id"],
                        "question_id": item["question_id"],
                        "word_id": item["word_id"],
                        "sense_id": item["sense_id"],
                        "dimension": item["dimension"],
                        "answer": answer,
                        "attempt_id": "stale-home-review-answer",
                    },
                    now=self.now + timedelta(days=1),
                )

            self.assertEqual(blocked.exception.error, "task_expired")
            self.assertEqual(blocked.exception.details["task_date_state"], "expired")
            self.assertEqual(
                VocabularyReviewAttempt.query.filter_by(
                    session_id=claimed["session_id"],
                ).count(),
                0,
            )

    def test_undated_origin_task_still_blocks_answers_after_completion(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            task = db.session.get(Task, self.task_id)
            task.date = ""
            claimed = claim_today_review(
                user, origin_task_id=task.id, now=self.now
            )
            session = db.session.get(VocabularyReviewSession, claimed["session_id"])
            task.status = "done"
            with self.assertRaises(VocabularyAutonomousReviewError) as blocked:
                self._answer_all(session)
            self.assertEqual(blocked.exception.error, "task_completed_read_only")
            self.assertEqual(
                VocabularyReviewAttempt.query.filter_by(session_id=session.id).count(),
                0,
            )

    def test_task_linked_review_remains_attributed_and_writable_until_three_am(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            claimed = claim_today_review(
                user,
                origin_task_id=self.task_id,
                now=self.now,
            )
            grace_time = self.now + timedelta(hours=6)
            resumed = claim_today_review(
                user,
                origin_task_id=self.task_id,
                now=grace_time,
            )
            self.assertEqual(resumed["session_id"], claimed["session_id"])
            self.assertEqual(resumed["review_date"], "2026-08-08")

            session = db.session.get(VocabularyReviewSession, claimed["session_id"])
            self._answer_all(session, now=grace_time)
            result = settle_review_session(
                user,
                session.id,
                {"queue_token": session.queue_token},
                session_token=session.session_token,
                now=grace_time,
            )
            self.assertEqual(result["status"], VocabularyReviewSession.STATUS_SETTLED)
            self.assertEqual(session.review_date.isoformat(), "2026-08-08")

    def test_cross_midnight_settlement_is_blocked_after_three_am_cutoff(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            claimed = claim_today_review(
                user,
                origin_task_id=self.task_id,
                now=self.now,
            )
            session = db.session.get(VocabularyReviewSession, claimed["session_id"])
            self._answer_all(session)
            completed_at = self.now + timedelta(hours=8)
            with self.assertRaises(VocabularyAutonomousReviewError) as blocked:
                settle_review_session(
                    user,
                    session.id,
                    {"queue_token": session.queue_token},
                    session_token=session.session_token,
                    now=completed_at,
                )
            self.assertEqual(blocked.exception.error, "task_expired")

    def _claim_protocol_fixture(self, count=2):
        user = db.session.get(User, self.student_id)
        rows = StudentVocabularyMastery.query.filter_by(
            student_id=self.student_id
        ).order_by(StudentVocabularyMastery.id.asc()).all()
        for mastery in rows:
            for dimension in StudentVocabularyMastery.DIMENSIONS:
                setattr(
                    mastery,
                    f"{dimension}_next_due_at",
                    self.now + timedelta(days=30),
                )
        for mastery in rows[:count]:
            mastery.meaning_recall_next_due_at = self.now
        db.session.commit()
        claimed = claim_today_review(user, now=self.now)
        self.assertEqual(claimed["total_count"], count)
        return user, claimed

    def _answer_protocol_item(self, user, claimed, item):
        stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
        expected = json.loads(stored.answer_payload_json)
        answer = expected.get("answer") or expected.get("answer_option_id")
        return submit_review_answer(
            user,
            claimed["session_id"],
            {
                "session_token": claimed["session_token"],
                "review_item_id": stored.id,
                "question_id": stored.question_id,
                "word_id": stored.word_id,
                "sense_id": stored.sense_id,
                "dimension": stored.dimension,
                "answer": answer,
                "attempt_id": f"protocol-good-{stored.id}",
            },
            now=self.now,
        )

    def test_verified_bad_item_can_settle_without_attempt_and_is_regenerated(self):
        with self.app.app_context():
            user, claimed = self._claim_protocol_fixture()
            good, bad = claimed["items"]
            bad_row = db.session.get(VocabularyReviewItem, bad["review_item_id"])
            bad_row.question_snapshot_json = "{not-json"
            self._answer_protocol_item(user, claimed, good)
            settled = settle_review_session(
                user,
                claimed["session_id"],
                {
                    "queue_token": claimed["queue_token"],
                    "skipped_items": [
                        {"review_item_id": bad_row.id, "reason": "invalid_question"},
                        {"review_item_id": bad_row.id, "reason": "invalid_question"},
                    ],
                },
                session_token=claimed["session_token"],
                now=self.now,
            )
            self.assertEqual(settled["total_count"], 1)
            self.assertEqual(settled["skipped_count"], 1)
            self.assertEqual(settled["skipped_item_ids"], [bad_row.id])
            self.assertEqual(
                VocabularyReviewAttempt.query.filter_by(item_id=bad_row.id).count(),
                0,
            )
            self.assertTrue(bad_row.deferred_to_review)
            self.assertTrue(bad_row.state_applied)
            mastery = db.session.get(StudentVocabularyMastery, bad_row.sense_id)
            self.assertLessEqual(mastery.meaning_recall_next_due_at, self.now)

            regenerated = claim_today_review(user, now=self.now)
            self.assertEqual(regenerated["total_count"], 1)
            self.assertEqual(regenerated["items"][0]["sense_id"], bad_row.sense_id)
            self.assertEqual(regenerated["items"][0]["dimension"], "meaning_recall")

    def test_valid_item_cannot_be_maliciously_skipped(self):
        with self.app.app_context():
            user, claimed = self._claim_protocol_fixture()
            item = claimed["items"][0]
            with self.assertRaises(VocabularyAutonomousReviewError) as error:
                settle_review_session(
                    user,
                    claimed["session_id"],
                    {
                        "queue_token": claimed["queue_token"],
                        "skipped_items": [
                            {"review_item_id": item["review_item_id"], "reason": "invalid_question"}
                        ],
                    },
                    session_token=claimed["session_token"],
                    now=self.now,
                )
            self.assertEqual(error.exception.error, "review_item_skip_invalid")
            self.assertFalse(db.session.get(VocabularyReviewItem, item["review_item_id"]).state_applied)

    def test_all_bad_items_settle_with_zero_score_and_remain_recoverable(self):
        with self.app.app_context():
            user, claimed = self._claim_protocol_fixture(count=1)
            item = claimed["items"][0]
            row = db.session.get(VocabularyReviewItem, item["review_item_id"])
            row.question_snapshot_json = "{not-json"
            settled = settle_review_session(
                user,
                claimed["session_id"],
                {
                    "queue_token": claimed["queue_token"],
                    "skipped_items": [
                        {"review_item_id": row.id, "reason": "invalid_question"}
                    ],
                },
                session_token=claimed["session_token"],
                now=self.now,
            )
            self.assertEqual(settled["total_count"], 0)
            self.assertEqual(settled["correct_count"], 0)
            self.assertEqual(settled["skipped_count"], 1)
            self.assertEqual(VocabularyReviewAttempt.query.filter_by(item_id=row.id).count(), 0)
            regenerated = claim_today_review(user, now=self.now)
            self.assertEqual(regenerated["total_count"], 1)
            self.assertEqual(regenerated["items"][0]["sense_id"], row.sense_id)


if __name__ == "__main__":
    unittest.main()
