import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from flask import Flask
from flask_login import LoginManager
from sqlalchemy.exc import OperationalError

from models import (
    DictationBook,
    DictationRecord,
    DictationWord,
    StudentProfile,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyReviewItem,
    db,
)
from services.vocabulary_autonomous_review import (
    VocabularyAutonomousReviewError,
    claim_today_review,
    review_preflight,
    review_summary,
    settle_review_session,
    submit_review_answer,
)
from services.vocabulary_group_learning import (
    PHASE_COMPLETE,
    PHASE_FAMILIARITY,
    PHASE_RECALL,
    PHASE_RETRY,
    VocabularyGroupLearningError,
    build_fixed_groups,
    finalize_vocabulary_group_task,
    get_vocabulary_group_queue,
    group_size_for_goal,
    mark_familiarity_viewed,
    stable_question_order,
    submit_vocabulary_group_answer,
    submit_vocabulary_group_correction,
)
from services.task_date_gate import beijing_today
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense


class VocabularyGroupLearningTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="vocabulary-group-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="group_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            student = User(
                username="group_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, student])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="小组学生"))
            book = DictationBook(
                title="小组测试词书",
                word_count=4,
                created_by=teacher.id,
                is_active=True,
            )
            db.session.add(book)
            db.session.flush()
            words = [
                DictationWord(
                    book_id=book.id,
                    sequence=index,
                    word=word,
                    translation=meaning,
                    core_meaning_zh=meaning,
                    usage_pattern=pattern,
                    example_en=example,
                    example_zh=f"这是{meaning}。",
                )
                for index, (word, meaning, pattern, example) in enumerate(
                    (
                        ("depend", "依赖", "depend on", "Students depend on clear feedback."),
                        ("focus", "集中", "focus on", "Students focus on the main idea."),
                        ("contribute", "贡献", "contribute to", "Students contribute to discussion."),
                        ("achieve", "实现", "achieve a goal", "Students achieve a useful goal."),
                    ),
                    start=1,
                )
            ]
            db.session.add_all(words)
            db.session.commit()
            self.student_id = student.id
            self.teacher_id = teacher.id
            self.book_id = book.id
            self.word_ids = [word.id for word in words]

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _task(self, goal="reading", end=3, task_date=None):
        task = Task(
            date=task_date or beijing_today(),
            student_name="小组学生",
            category="词汇",
            detail="小组学习测试",
            created_by=self.teacher_id,
            dictation_book_id=self.book_id,
            vocabulary_goal=goal,
            dictation_mode="audio_to_en",
            dictation_word_start=1,
            dictation_word_end=end,
        )
        db.session.add(task)
        db.session.commit()
        return task

    def _user(self):
        return db.session.get(User, self.student_id)

    def _ensure_six_words(self):
        book = db.session.get(DictationBook, self.book_id)
        if DictationWord.query.filter_by(book_id=self.book_id).count() >= 6:
            return
        extra = [
            (5, "improve", "改进", "improve on", "Students improve on the first draft."),
            (6, "support", "支持", "support a plan", "Students support a practical plan."),
        ]
        db.session.add_all(
            [
                DictationWord(
                    book_id=book.id,
                    sequence=sequence,
                    word=word,
                    translation=meaning,
                    core_meaning_zh=meaning,
                    usage_pattern=pattern,
                    example_en=example,
                    example_zh=f"这是{meaning}。",
                )
                for sequence, word, meaning, pattern, example in extra
            ]
        )
        book.word_count = 6
        db.session.commit()

    def _answer_for_current(self, user, task_id, queue, *, wrong=False, now=None):
        question = queue["current_question"]
        stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
        answer_payload = json.loads(stored.answer_payload_json)
        answer = answer_payload.get("answer_option_id") or answer_payload.get("answer")
        if wrong:
            answer = "definitely-not-the-answer"
        result = submit_vocabulary_group_answer(
            user,
            {
                "task_id": task_id,
                "queue_token": queue["queue_token"],
                "learning_question_id": question["learning_question_id"],
                "queue_item_id": question["queue_item_id"],
                "question_id": question["question_id"],
                "word_id": question["word_id"],
                "sense_id": question["sense_id"],
                "dimension": question["dimension"],
                "answer": answer,
                "attempt_id": (
                    f"group-test:{task_id}:{'retry' if queue['phase'] == PHASE_RETRY else 'first'}:"
                    f"{question['learning_question_id']}:{'wrong' if wrong else 'right'}"
                ),
                "retry": queue["phase"] == PHASE_RETRY,
            },
            now=now,
        )
        return result

    def _correct_current(self, user, task_id, queue, *, wrong=False, attempt_id=None, now=None):
        question = queue["current_question"]
        stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
        answer_payload = json.loads(stored.answer_payload_json)
        answer = answer_payload.get("answer_option_id") or answer_payload.get("answer")
        if wrong:
            answer = "definitely-not-the-answer"
        return submit_vocabulary_group_correction(
            user,
            {
                "task_id": task_id,
                "queue_token": queue["queue_token"],
                "learning_question_id": question["learning_question_id"],
                "queue_item_id": question["queue_item_id"],
                "answer": answer,
                "attempt_id": attempt_id or f"group-correction:{task_id}:{question['learning_question_id']}",
            },
            now=now,
        )

    def _view_group(self, user, task_id, queue, now=None):
        while queue["phase"] == PHASE_FAMILIARITY:
            current = next(item for item in queue["familiarity"] if not item["viewed"])
            queue = mark_familiarity_viewed(
                user,
                task_id,
                {"queue_token": queue["queue_token"], "word_id": current["word_id"]},
                now=now,
            )
        return queue

    def _finish_flow(
        self,
        user,
        task,
        *,
        wrong_question_id=None,
        wrong_retry=False,
        stop_at_retry=False,
        now=None,
    ):
        queue = get_vocabulary_group_queue(user, task.id, now=now)
        while not queue["completed"]:
            queue = self._view_group(user, task.id, queue, now=now)
            if stop_at_retry and queue["phase"] == PHASE_RETRY:
                return queue
            if queue["current_question"] is None:
                queue = get_vocabulary_group_queue(user, task.id, now=now)
                continue
            question_id = queue["current_question"]["learning_question_id"]
            wrong = wrong_question_id == question_id and not wrong_retry
            self._answer_for_current(user, task.id, queue, wrong=wrong, now=now)
            queue = get_vocabulary_group_queue(user, task.id, now=now)
            if wrong:
                wrong_retry = True
        return queue

    def test_group_sizes_and_last_remainder_are_server_constants(self):
        self.assertEqual(group_size_for_goal("reading"), 10)
        self.assertEqual(group_size_for_goal("listening"), 8)
        self.assertEqual(group_size_for_goal("writing"), 8)
        self.assertEqual(group_size_for_goal("comprehensive"), 6)
        words = list(range(23))
        self.assertEqual([len(group) for group in build_fixed_groups(words, 10)], [10, 10, 3])
        self.assertEqual([len(group) for group in build_fixed_groups(words, 8)], [8, 8, 7])
        self.assertEqual([len(group) for group in build_fixed_groups(words, 6)], [6, 6, 6, 5])
        self.assertEqual([len(group) for group in build_fixed_groups(words[:9], 8)], [8, 1])

    def test_comprehensive_uses_two_base_questions_per_word_and_fixed_progress(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            now = datetime(2026, 8, 8, 12, 0)
            task = self._task("comprehensive", end=6, task_date=now.date())
            queue = get_vocabulary_group_queue(user, task.id, now=now)
            self.assertEqual(queue["phase"], PHASE_FAMILIARITY)
            self.assertEqual(queue["base_progress_completed"], 0)
            self.assertEqual(queue["base_progress_total"], 12)
            self.assertEqual(queue["remediation_progress_total"], 0)
            self.assertEqual(queue["remediation_budget_total"], 12)
            masteries = StudentVocabularyMastery.query.all()
            self.assertEqual(len(masteries), 6)
            self.assertTrue(
                all(
                    mastery.meaning_recall_next_due_at == now + timedelta(days=1)
                    and mastery.audio_form_recall_next_due_at == now + timedelta(days=1)
                    for mastery in masteries
                )
            )
            same_day_gate = review_preflight(user, task.id, now=now)
            self.assertFalse(same_day_gate["required"])
            day_one_gate = review_preflight(user, task.id, now=now + timedelta(days=1))
            self.assertGreater(day_one_gate["due_count"], 0)
            queue = self._view_group(user, task.id, queue, now=now)

            questions = VocabularyLearningQuestion.query.filter_by(
                task_id=task.id,
                group_index=0,
            ).all()
            formal = [item for item in questions if item.remediation_kind is None]
            self.assertEqual(len(formal), 12)
            self.assertEqual(
                {item.phase for item in formal},
                {PHASE_RECALL, "context_discrimination"},
            )
            self.assertFalse(any(item.phase == "context_production" for item in formal))
            self.assertEqual(
                {item.dimension for item in formal},
                {"form_recall", "context_use"},
            )
            self.assertTrue(
                all(
                    json.loads(item.question_snapshot_json).get("mode") == "zh_to_en"
                    for item in formal
                    if item.dimension == "form_recall"
                )
            )
            self.assertTrue(
                all(
                    json.loads(item.question_snapshot_json).get("mode")
                    in {"context_choice", "context_fill"}
                    for item in formal
                    if item.dimension == "context_use"
                )
            )
            by_word = {}
            for item in formal:
                by_word.setdefault(item.word_id, []).append(item)
            self.assertEqual({len(items) for items in by_word.values()}, {2})
            for items in by_word.values():
                positions = sorted(item.formal_ordinal for item in items)
                self.assertGreaterEqual(positions[1] - positions[0], 6)
            self.assertEqual(queue["base_progress_total"], 12)
            self.assertEqual(queue["remediation_progress_total"], 0)
            self.assertEqual(queue["remediation_budget_total"], 12)

    def test_wrong_correction_keeps_choice_pending_then_bounded_release(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            task = self._task("comprehensive", end=6)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            while queue["current_question"] and queue["current_question"]["mode"] != "context_choice":
                self._answer_for_current(user, task.id, queue)
                queue = get_vocabulary_group_queue(user, task.id)
            question = queue["current_question"]
            self.assertEqual(question["mode"], "context_choice")
            self._answer_for_current(user, task.id, queue, wrong=True)
            pending = get_vocabulary_group_queue(user, task.id)
            self.assertTrue(pending["correction_required"])
            first_wrong = self._correct_current(
                user,
                task.id,
                pending,
                wrong=True,
                attempt_id=f"bounded-choice:{question['learning_question_id']}:1",
            )
            self.assertFalse(first_wrong["correction_completed"])
            self.assertTrue(first_wrong["correction_required"])
            self.assertFalse(first_wrong["correction_is_correct"])
            still_pending = get_vocabulary_group_queue(user, task.id)
            second_wrong = self._correct_current(
                user,
                task.id,
                still_pending,
                wrong=True,
                attempt_id=f"bounded-choice:{question['learning_question_id']}:2",
            )
            self.assertTrue(second_wrong["correction_completed"])
            self.assertTrue(second_wrong["correction_exhausted"])
            self.assertFalse(second_wrong["correction_required"])
            self.assertGreaterEqual(second_wrong["deferred_review_count"], 1)

    def test_group_correction_increments_attempt_id_and_rejects_stale_replay(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            task = self._task("comprehensive", end=6)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            question = queue["current_question"]
            self._answer_for_current(user, task.id, queue, wrong=True)
            pending = get_vocabulary_group_queue(user, task.id)
            first_id = f"increment-choice:{question['learning_question_id']}:1"
            first_wrong = self._correct_current(
                user,
                task.id,
                pending,
                wrong=True,
                attempt_id=first_id,
            )
            self.assertTrue(first_wrong["correction_required"])
            second_id = f"increment-choice:{question['learning_question_id']}:2"
            second_correct = self._correct_current(
                user,
                task.id,
                get_vocabulary_group_queue(user, task.id),
                attempt_id=second_id,
            )
            self.assertTrue(second_correct["correction_completed"])
            self.assertEqual(second_correct["correction_count"], 2)
            self.assertEqual(second_correct["correction_attempt_id"], second_id)
            stored = db.session.get(
                VocabularyLearningQuestion,
                question["learning_question_id"],
            )
            with self.assertRaises(VocabularyGroupLearningError) as stale:
                submit_vocabulary_group_correction(
                    user,
                    {
                        "task_id": task.id,
                        "queue_token": second_correct["queue_token"],
                        "learning_question_id": question["learning_question_id"],
                        "queue_item_id": question["queue_item_id"],
                        "answer": "旧 attempt 不得覆盖",
                        "attempt_id": first_id,
                    },
                )
            self.assertEqual(stale.exception.error, "correction_not_current")
            self.assertEqual(stored.correction_attempt_id, second_id)
            self.assertEqual(stored.correction_count, 2)

    def test_comprehensive_wrong_answer_requires_idempotent_nonformal_correction(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            task = self._task("comprehensive", end=6)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            wrong_question_id = queue["current_question"]["learning_question_id"]
            self._answer_for_current(user, task.id, queue, wrong=True)
            correction_queue = get_vocabulary_group_queue(user, task.id)
            self.assertTrue(correction_queue["correction_required"])
            self.assertEqual(
                correction_queue["current_question"]["learning_question_id"],
                wrong_question_id,
            )
            self.assertTrue(correction_queue["current_question"]["first_answer"])
            self.assertTrue(correction_queue["current_question"]["revealed_answer"])
            self.assertEqual(correction_queue["base_progress_completed"], 1)
            self.assertEqual(DictationWord.query.count(), 6)
            self.assertEqual(
                VocabularyLearningQuestion.query.filter_by(task_id=task.id).count(),
                12,
            )
            self.assertEqual(
                DictationRecord.query.filter_by(task_id=task.id).count(),
                1,
            )

            correction_payload_id = f"group-correction:{task.id}:{wrong_question_id}"
            first = self._correct_current(
                user,
                task.id,
                correction_queue,
                attempt_id=correction_payload_id,
            )
            duplicate = self._correct_current(
                user,
                task.id,
                correction_queue,
                attempt_id=correction_payload_id,
            )
            self.assertTrue(first["correction_completed"])
            self.assertTrue(duplicate["correction_idempotent"])
            self.assertEqual(first["correction_count"], 1)
            resumed = get_vocabulary_group_queue(user, task.id)
            self.assertFalse(resumed["correction_required"])
            self.assertEqual(resumed["base_progress_completed"], 1)
            self.assertEqual(
                DictationRecord.query.filter_by(task_id=task.id).count(),
                1,
            )

    def test_legacy_comprehensive_flow_without_formal_ordinals_keeps_old_contract(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            task = self._task("comprehensive", end=1)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            flow = VocabularyLearningFlow.query.filter_by(task_id=task.id).one()
            for question in flow.questions:
                question.formal_ordinal = None
            db.session.flush()
            self._answer_for_current(user, task.id, queue, wrong=True)
            resumed = get_vocabulary_group_queue(user, task.id)
            self.assertFalse(resumed["correction_required"])
            self.assertNotEqual(resumed["phase"], PHASE_COMPLETE)

    def test_comprehensive_same_dimension_retry_can_release_one_related_dimension(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            task = self._task("comprehensive", end=6)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            wrong_base_ids = set()
            while queue["phase"] != PHASE_RETRY:
                question = queue["current_question"]
                self.assertIsNotNone(question)
                wrong = question["dimension"] == "form_recall"
                wrong_base_ids.add(question["learning_question_id"]) if wrong else None
                self._answer_for_current(user, task.id, queue, wrong=wrong)
                queue = get_vocabulary_group_queue(user, task.id)
                if queue["correction_required"]:
                    self._correct_current(user, task.id, queue)
                    queue = get_vocabulary_group_queue(user, task.id)
            self.assertEqual(len(wrong_base_ids), 6)
            self.assertEqual(queue["remediation_pending_count"], 6)
            self.assertEqual(queue["remediation_progress_total"], 6)
            self.assertEqual(queue["remediation_budget_total"], 12)

            primary_ids = []
            while (
                queue["phase"] == PHASE_RETRY
                and queue["current_question"]
                and queue["current_question"]["remediation_kind"] is None
            ):
                question = queue["current_question"]
                primary_ids.append(question["learning_question_id"])
                self.assertIsNone(question["remediation_kind"])
                self._answer_for_current(user, task.id, queue, wrong=True)
                queue_after_wrong = get_vocabulary_group_queue(user, task.id)
                self.assertTrue(queue_after_wrong["correction_required"])
                self._correct_current(user, task.id, queue_after_wrong)
                queue = get_vocabulary_group_queue(user, task.id)
            self.assertEqual(len(primary_ids), 6)
            related = queue["current_question"]
            self.assertEqual(related["remediation_kind"], "related_dimension")
            self.assertEqual(related["dimension"], "context_use")

            first_related_queue = queue
            self._answer_for_current(user, task.id, first_related_queue)
            duplicate_related = self._answer_for_current(user, task.id, first_related_queue)
            self.assertTrue(duplicate_related["idempotent"])
            queue = get_vocabulary_group_queue(user, task.id)
            while not queue["completed"]:
                self.assertIsNotNone(queue["current_question"])
                self._answer_for_current(user, task.id, queue)
                queue = get_vocabulary_group_queue(user, task.id)
            result = finalize_vocabulary_group_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
            )
            self.assertEqual(result["total_count"], 12)
            self.assertEqual(result["retry_count"], 12)
            self.assertEqual(result["remediation_budget_per_word"], 2)
            self.assertEqual(
                VocabularyLearningQuestion.query.filter_by(
                    task_id=task.id,
                    remediation_kind="related_dimension",
                ).count(),
                6,
            )

    def test_comprehensive_two_base_dimension_errors_are_capped_at_four_formal_questions(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            task = self._task("comprehensive", end=6)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            while queue["phase"] != PHASE_RETRY:
                self._answer_for_current(user, task.id, queue, wrong=True)
                queue = get_vocabulary_group_queue(user, task.id)
                if queue["correction_required"]:
                    self._correct_current(user, task.id, queue)
                    queue = get_vocabulary_group_queue(user, task.id)
            while not queue["completed"]:
                self._answer_for_current(user, task.id, queue, wrong=True)
                queue = get_vocabulary_group_queue(user, task.id)
                if queue["correction_required"]:
                    self._correct_current(user, task.id, queue)
                    queue = get_vocabulary_group_queue(user, task.id)
            result = finalize_vocabulary_group_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
            )
            formal = VocabularyLearningQuestion.query.filter_by(task_id=task.id).all()
            by_word = {}
            for item in formal:
                by_word.setdefault(item.word_id, 0)
                by_word[item.word_id] += 1 + int(bool(item.retry_attempt_id))
            self.assertEqual(set(by_word.values()), {4})
            self.assertEqual(
                VocabularyLearningQuestion.query.filter_by(
                    task_id=task.id,
                    remediation_kind="related_dimension",
                ).count(),
                0,
            )
            self.assertEqual(result["retry_count"], 12)

    def test_constrained_scheduler_handles_sparse_errors_and_tiny_pool(self):
        with self.app.app_context():
            self._ensure_six_words()
            user = self._user()
            task = self._task("comprehensive", end=6)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            formal_seen = 0
            while queue["phase"] != PHASE_RETRY:
                question = queue["current_question"]
                self.assertIsNotNone(question)
                sparse_error = formal_seen in {0, 11}
                self._answer_for_current(user, task.id, queue, wrong=sparse_error)
                formal_seen += 1
                queue = get_vocabulary_group_queue(user, task.id)
                if queue["correction_required"]:
                    self._correct_current(user, task.id, queue)
                    queue = get_vocabulary_group_queue(user, task.id)
            retry_count = 0
            while not queue["completed"]:
                self._answer_for_current(user, task.id, queue)
                retry_count += 1
                queue = get_vocabulary_group_queue(user, task.id)
            result = finalize_vocabulary_group_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
            )
            self.assertLessEqual(retry_count, 2)
            self.assertLessEqual(result["retry_count"], 2)

            tiny_task = self._task("comprehensive", end=1)
            queue = self._view_group(user, tiny_task.id, get_vocabulary_group_queue(user, tiny_task.id))
            while not queue["completed"]:
                self._answer_for_current(user, tiny_task.id, queue, wrong=True)
                queue = get_vocabulary_group_queue(user, tiny_task.id)
                if queue["correction_required"]:
                    self._correct_current(user, tiny_task.id, queue)
                    queue = get_vocabulary_group_queue(user, tiny_task.id)
            tiny_result = finalize_vocabulary_group_task(
                user,
                tiny_task.id,
                {"queue_token": queue["queue_token"]},
            )
            self.assertLessEqual(tiny_result["retry_count"], 4)

    def test_stable_order_avoids_adjacent_sense_and_is_deterministic(self):
        specs = [
            {"question_id": f"q{index}", "word_id": index, "sense_id": index % 3, "dimension": "meaning_recall"}
            for index in range(9)
        ]
        first = stable_question_order(specs, "same-seed")
        second = stable_question_order(list(reversed(specs)), "same-seed")
        self.assertEqual([item["question_id"] for item in first], [item["question_id"] for item in second])
        for previous, current in zip(first[:-1], first[1:], strict=True):
            self.assertNotEqual(previous["sense_id"], current["sense_id"])
        boundary = stable_question_order(specs, "same-seed", previous_sense_id=1)
        self.assertNotEqual(boundary[0]["sense_id"], 1)

        imbalanced = [
            {"question_id": f"imbalanced-{index}", "word_id": index, "sense_id": sense, "dimension": "meaning_recall"}
            for index, sense in enumerate(("A", "A", "A", "B", "C"))
        ]
        feasible = stable_question_order(imbalanced, "imbalanced")
        self.assertEqual(
            [item["question_id"] for item in feasible],
            [item["question_id"] for item in stable_question_order(list(reversed(imbalanced)), "imbalanced")],
        )
        self.assertTrue(
            all(
                a["sense_id"] != b["sense_id"]
                for a, b in zip(feasible[:-1], feasible[1:], strict=True)
            )
        )

        impossible_specs = [
            {"question_id": f"impossible-{index}", "word_id": index, "sense_id": sense, "dimension": "meaning_recall"}
            for index, sense in enumerate(("A", "A", "A", "A", "B", "C"))
        ]
        impossible = stable_question_order(impossible_specs, "impossible")
        self.assertEqual(
            [item["question_id"] for item in impossible],
            [item["question_id"] for item in stable_question_order(list(reversed(impossible_specs)), "impossible")],
        )
        self.assertTrue(
            any(
                a["sense_id"] == b["sense_id"]
                for a, b in zip(impossible[:-1], impossible[1:], strict=True)
            )
        )

    def test_all_correct_intermediate_group_enters_next_group(self):
        with self.app.app_context():
            user = self._user()
            book = db.session.get(DictationBook, self.book_id)
            for sequence in range(5, 12):
                db.session.add(
                    DictationWord(
                        book_id=book.id,
                        sequence=sequence,
                        word=f"groupword{sequence}",
                        translation=f"小组释义{sequence}",
                        core_meaning_zh=f"小组释义{sequence}",
                    )
                )
            book.word_count = 11
            db.session.commit()
            task = self._task("reading", end=11)
            queue = get_vocabulary_group_queue(user, task.id)
            while queue["group_index"] == 0:
                queue = self._view_group(user, task.id, queue)
                if queue["current_question"] is not None:
                    self._answer_for_current(user, task.id, queue)
                queue = get_vocabulary_group_queue(user, task.id)
            self.assertEqual(queue["group_number"], 2)
            self.assertEqual(queue["phase"], PHASE_FAMILIARITY)
            self.assertFalse(queue["completed"])

    def test_familiarity_does_not_update_mastery_and_cannot_skip(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=3)
            queue = get_vocabulary_group_queue(user, task.id)
            self.assertEqual(queue["group_number"], 1)
            self.assertEqual(queue["group_size"], 3)
            with self.assertRaises(VocabularyGroupLearningError) as error:
                mark_familiarity_viewed(
                    user,
                    task.id,
                    {"queue_token": queue["queue_token"], "word_id": queue["familiarity"][1]["word_id"]},
                )
            self.assertEqual(error.exception.error, "familiarity_order_violation")
            mark_familiarity_viewed(
                user,
                task.id,
                {"queue_token": queue["queue_token"], "word_id": queue["familiarity"][0]["word_id"]},
            )
            self.assertEqual(StudentVocabularyMastery.query.count(), 3)
            self.assertTrue(
                all(
                    mastery.meaning_recall_stage == 0
                    for mastery in StudentVocabularyMastery.query.all()
                )
            )

    def test_familiarity_to_recall_avoids_last_seen_sense(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=3)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            self.assertEqual(queue["phase"], PHASE_RECALL)
            self.assertIsNotNone(queue["current_question"])
            last_word = db.session.get(
                DictationWord,
                queue["familiarity"][-1]["word_id"],
            )
            self.assertNotEqual(
                queue["current_question"]["sense_id"],
                last_word.sense_id,
            )

    def test_three_context_senses_apply_once_and_choice_is_guidance(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=3)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            while not queue["completed"]:
                question = queue["current_question"]
                self.assertIsNotNone(question)
                self._answer_for_current(user, task.id, queue)
                queue = get_vocabulary_group_queue(user, task.id)
                if queue["current_question"] is None and not queue["completed"]:
                    queue = self._view_group(user, task.id, queue)
            result = finalize_vocabulary_group_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
            )
            self.assertEqual(result["dimensions"]["context_use"]["total"], 3)
            self.assertEqual(result["guidance_count"], 3)
            masteries = StudentVocabularyMastery.query.order_by(StudentVocabularyMastery.id).all()
            self.assertEqual([mastery.context_use_stage for mastery in masteries], [1, 1, 1])
            self.assertEqual(
                VocabularyLearningQuestion.query.filter_by(
                    task_id=task.id,
                    context_role="guide",
                    score_eligible=False,
                ).count(),
                3,
            )

    def test_wrong_mastery_encounter_requires_one_retry_but_retry_does_not_advance(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=3)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            wrong_question_id = queue["current_question"]["learning_question_id"]
            queue = self._finish_flow(
                user,
                task,
                wrong_question_id=wrong_question_id,
                stop_at_retry=True,
            )
            self.assertEqual(queue["phase"], PHASE_RETRY)
            retry_question = queue["current_question"]
            self.assertEqual(retry_question["learning_question_id"], wrong_question_id)
            before = StudentVocabularyMastery.query.filter_by(sense_id=retry_question["sense_id"]).one()
            self.assertEqual(before.meaning_recall_stage, 0)
            self._answer_for_current(user, task.id, queue)
            queue = get_vocabulary_group_queue(user, task.id)
            self.assertTrue(queue["completed"])
            after = StudentVocabularyMastery.query.filter_by(sense_id=retry_question["sense_id"]).one()
            self.assertEqual(after.meaning_recall_stage, 0)
            result = finalize_vocabulary_group_task(user, task.id, {"queue_token": queue["queue_token"]})
            self.assertEqual(result["retry_count"], 1)
            self.assertEqual(result["total_count"], 6)

    def test_retry_shuffle_respects_last_formal_phase_sense_boundary(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=3)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            injected_wrong = 0
            while queue["phase"] != PHASE_RETRY:
                self.assertIsNotNone(queue["current_question"])
                wrong = queue["phase"] == "active_recall" and injected_wrong < 2
                self._answer_for_current(user, task.id, queue, wrong=wrong)
                injected_wrong += int(wrong)
                queue = get_vocabulary_group_queue(user, task.id)
            last_formal = None
            for phase in ("context_production", "context_discrimination", "active_recall"):
                candidates = (
                    VocabularyLearningQuestion.query.filter_by(task_id=task.id, phase=phase)
                    .order_by(VocabularyLearningQuestion.phase_index.desc())
                    .all()
                )
                last_formal = next((item for item in candidates if item.first_attempt_id), None)
                if last_formal:
                    break
            self.assertIsNotNone(last_formal)
            self.assertNotEqual(queue["current_question"]["sense_id"], last_formal.sense_id)

    def test_retry_wrong_can_finish_and_is_marked_for_review(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=1)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            self._answer_for_current(user, task.id, queue, wrong=True)
            queue = get_vocabulary_group_queue(user, task.id)
            while queue["phase"] != PHASE_RETRY:
                self.assertIsNotNone(queue["current_question"])
                self._answer_for_current(user, task.id, queue)
                queue = get_vocabulary_group_queue(user, task.id)
            self._answer_for_current(user, task.id, queue, wrong=True)
            queue = get_vocabulary_group_queue(user, task.id)
            self.assertTrue(queue["completed"])
            result = finalize_vocabulary_group_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
            )
            self.assertEqual(result["needs_review_count"], 1)

    def test_context_choice_only_is_explicit_degraded_single_encounter(self):
        with self.app.app_context(), patch(
            "services.vocabulary_group_learning._context_question"
        ) as context_question:
            context_question.side_effect = lambda word, candidates, **kwargs: (
                (
                    {
                        "question_id": f"safe-choice-{word.id}",
                        "mode": "context_choice",
                        "dimension": "context_use",
                        "prompt": {"sentence": "Choose the meaning.", "instruction": "选择词义"},
                        "options": [{"id": "correct", "label": "依赖"}],
                    },
                    {"answer_option_id": "correct", "answer_type": "option_id"},
                )
                if "context-choice" in kwargs["seed"]
                else None
            )
            user = self._user()
            task = self._task("reading", end=1)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            while not queue["completed"]:
                self.assertIsNotNone(queue["current_question"])
                self._answer_for_current(user, task.id, queue)
                queue = get_vocabulary_group_queue(user, task.id)
            result = finalize_vocabulary_group_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
            )
            self.assertEqual(result["dimensions"]["context_use"]["total"], 1)
            self.assertEqual(result["guidance_count"], 0)
            self.assertTrue(
                any(item["reason"] == "degraded_to_context_discrimination" for item in result["diagnostics"])
            )

    def test_same_attempt_is_idempotent_and_stale_question_cannot_double_advance(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=1)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            question = queue["current_question"]
            stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
            answer_payload = json.loads(stored.answer_payload_json)
            answer = answer_payload.get("answer_option_id") or answer_payload.get("answer")
            payload = {
                "task_id": task.id,
                "queue_token": queue["queue_token"],
                "learning_question_id": question["learning_question_id"],
                "queue_item_id": question["queue_item_id"],
                "question_id": question["question_id"],
                "word_id": question["word_id"],
                "sense_id": question["sense_id"],
                "dimension": question["dimension"],
                "answer": answer,
                "attempt_id": "same-attempt-idempotency",
                "retry": False,
            }
            before = db.session.get(VocabularyLearningFlow, stored.flow_id).state_version
            first = submit_vocabulary_group_answer(user, payload)
            after = db.session.get(VocabularyLearningFlow, stored.flow_id).state_version
            self.assertEqual(after, before + 1)
            duplicate = submit_vocabulary_group_answer(user, dict(payload, answer="stale-answer"))
            self.assertTrue(duplicate["idempotent"])
            self.assertEqual(duplicate["is_correct"], first["is_correct"])
            with self.assertRaises(VocabularyGroupLearningError) as stale:
                submit_vocabulary_group_answer(
                    user,
                    dict(payload, attempt_id="stale-tab-different-attempt"),
                )
            self.assertEqual(stale.exception.error, "question_not_current")

    def test_started_task_is_blocked_after_assigned_day_ends(self):
        with self.app.app_context():
            user = self._user()
            day_one = datetime(2026, 8, 8, 23, 55)
            day_two = datetime(2026, 8, 9, 8, 0)
            task = self._task("reading", end=1, task_date=day_one.date())
            get_vocabulary_group_queue(user, task.id, now=day_one)
            with self.assertRaises(VocabularyAutonomousReviewError) as blocked:
                claim_today_review(user, origin_task_id=task.id, now=day_two)
            self.assertEqual(blocked.exception.error, "task_expired")

    def test_daily_clearance_errors_are_normalized_by_group_service(self):
        with self.app.app_context():
            with self.assertRaises(VocabularyGroupLearningError) as error:
                get_vocabulary_group_queue(self._user(), 999999)
            self.assertEqual(error.exception.error, "task_not_found")
            self.assertEqual(error.exception.status_code, 404)

    def test_sqlite_lock_is_a_retryable_state_conflict(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("listening", end=1)
            get_vocabulary_group_queue(user, task.id)
            lock_error = OperationalError("database is locked", {}, RuntimeError("locked"))
            with patch(
                "services.vocabulary_group_learning.review_preflight",
                side_effect=lock_error,
            ):
                with self.assertRaises(VocabularyGroupLearningError) as error:
                    get_vocabulary_group_queue(user, task.id)
            self.assertEqual(error.exception.error, "state_conflict")
            self.assertTrue(error.exception.details["retryable"])

    def test_listening_has_no_context_questions(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("listening", end=3)
            queue = self._view_group(user, task.id, get_vocabulary_group_queue(user, task.id))
            questions = VocabularyLearningQuestion.query.filter_by(task_id=task.id).all()
            self.assertTrue(questions)
            self.assertFalse(any(question.dimension == "context_use" for question in questions))
            self.assertNotIn("context_use", queue["dimensions"])

    def test_queue_token_and_question_contract_are_required(self):
        with self.app.app_context():
            user = self._user()
            task = self._task("reading", end=1)
            queue = get_vocabulary_group_queue(user, task.id)
            with self.assertRaises(VocabularyGroupLearningError) as token_error:
                mark_familiarity_viewed(user, task.id, {"word_id": queue["familiarity"][0]["word_id"]})
            self.assertEqual(token_error.exception.error, "queue_changed")
            queue = self._view_group(user, task.id, queue)
            with self.assertRaises(VocabularyGroupLearningError) as contract_error:
                submit_vocabulary_group_answer(
                    user,
                    {
                        "task_id": task.id,
                        "queue_token": queue["queue_token"],
                        "retry": False,
                        "answer": "依赖",
                    },
                )
            self.assertEqual(contract_error.exception.error, "attempt_id_required")


if __name__ == "__main__":
    unittest.main()
