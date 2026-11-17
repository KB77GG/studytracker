"""An in-progress vocabulary task must not rescan the student's due backlog per step.

The review gate only decides whether a task may be *entered*.  Once the task's
flow exists, every queue/familiarity/answer request used to recount the whole
backlog (twice for the queue) although the result could not change the gate.
"""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import jwt
from flask import Flask
from flask_login import LoginManager

from api.dictation import dictation_bp
from api.miniprogram import mp_bp
from api.vocab_review import vocab_review_bp
from models import (
    DictationBook,
    DictationWord,
    StudentProfile,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyLearningQuestion,
    VocabularyReviewItem,
    VocabularySense,
    db,
)
from services import vocabulary_autonomous_review as review
from services.task_date_gate import beijing_today

BACKLOG = 30
GATE_FIELDS = (
    "required",
    "review_required",
    "task_flow_started",
    "active_session_id",
    "clearance_session_id",
)


class VocabularyFlowBacklogGateTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="backlog-gate-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        for blueprint in (dictation_bp, mp_bp, vocab_review_bp):
            self.app.register_blueprint(blueprint)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="gate_teacher", password_hash="x", role=User.ROLE_TEACHER, is_active=True
            )
            db.session.add(teacher)
            db.session.commit()
            self.teacher_id = teacher.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _student(self, label, backlog):
        """A student with ``backlog`` due review words and a fresh 3-word task."""

        with self.app.app_context():
            student = User(
                username=f"gate_{label}", password_hash="x", role=User.ROLE_STUDENT, is_active=True
            )
            db.session.add(student)
            db.session.flush()
            name = f"积压门禁学生{label}"
            db.session.add(StudentProfile(user_id=student.id, full_name=name))
            task_book = DictationBook(
                title=f"任务书{label}", word_count=3, created_by=self.teacher_id, is_active=True
            )
            db.session.add(task_book)
            db.session.flush()
            for index in range(3):
                db.session.add(
                    DictationWord(
                        book_id=task_book.id,
                        sequence=index + 1,
                        word=f"task{label}word{index}",
                        translation=f"任务义{label}{index}",
                        core_meaning_zh=f"任务义{label}{index}",
                        usage_pattern=f"use task{label}word{index} well",
                        example_en=f"Students use task{label}word{index} in class.",
                    )
                )
            if backlog:
                book = DictationBook(
                    title=f"积压书{label}",
                    word_count=backlog,
                    created_by=self.teacher_id,
                    is_active=True,
                )
                db.session.add(book)
                db.session.flush()
                due = datetime.utcnow() - timedelta(days=1)
                later = datetime.utcnow() + timedelta(days=5)
                for index in range(backlog):
                    sense = VocabularySense(
                        canonical_key=f"gate-{label}-{index}",
                        lemma=f"old{label}word{index}",
                        meaning_zh=f"旧义{label}{index}",
                    )
                    db.session.add(sense)
                    db.session.flush()
                    word = DictationWord(
                        book_id=book.id,
                        sense_id=sense.id,
                        sequence=index + 1,
                        word=f"old{label}word{index}",
                        translation=f"旧义{label}{index}",
                        core_meaning_zh=f"旧义{label}{index}",
                        usage_pattern=f"use old{label}word{index} in class",
                        example_en=f"Students use old{label}word{index} in class.",
                    )
                    db.session.add(word)
                    db.session.flush()
                    db.session.add(
                        StudentVocabularyMastery(
                            student_id=student.id,
                            sense_id=sense.id,
                            representative_word_id=word.id,
                            representative_book_id=book.id,
                            meaning_recall_stage=1,
                            meaning_recall_next_due_at=due,
                            form_recall_stage=1,
                            form_recall_next_due_at=later,
                            audio_form_recall_stage=1,
                            audio_form_recall_next_due_at=later,
                            context_use_stage=1,
                            context_use_next_due_at=later,
                        )
                    )
            task = Task(
                date=beijing_today(),
                student_name=name,
                category="词汇",
                detail="积压门禁任务",
                created_by=self.teacher_id,
                dictation_book_id=task_book.id,
                vocabulary_goal="reading",
                dictation_word_start=1,
                dictation_word_end=3,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()
            token = jwt.encode(
                {"sub": str(student.id), "role": User.ROLE_STUDENT},
                self.app.config["SECRET_KEY"],
                algorithm="HS256",
            )
            return {
                "id": student.id,
                "task_id": task.id,
                "headers": {"Authorization": f"Bearer {token}"},
            }

    # -- HTTP helpers ------------------------------------------------------
    def _get(self, student, url):
        return self.client.get(url, headers=student["headers"])

    def _post(self, student, url, body):
        return self.client.post(url, json=body, headers=student["headers"])

    def _queue(self, student):
        return self._get(
            student,
            f"/api/miniprogram/student/tasks/{student['task_id']}/vocabulary-queue?supports_correction=1",
        )

    def _stored_answer(self, model, row_id):
        with self.app.app_context():
            payload = json.loads(db.session.get(model, row_id).answer_payload_json)
        return payload.get("answer_option_id") or payload.get("answer")

    def _claim(self, student):
        response = self._get(
            student,
            f"/api/miniprogram/student/vocabulary-review/today?origin_task_id={student['task_id']}",
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def _finish_review(self, student, session):
        base = f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}"
        for item in session["items"]:
            answered = self._post(
                student,
                f"{base}/answers",
                {
                    "session_token": session["session_token"],
                    "review_item_id": item["review_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "sense_id": item["sense_id"],
                    "dimension": item["dimension"],
                    "answer": self._stored_answer(VocabularyReviewItem, item["review_item_id"]),
                    "attempt_id": f"gate-review:{item['review_item_id']}",
                    "input_mode": "native",
                },
            )
            self.assertEqual(answered.status_code, 200, answered.get_json())
        settled = self._post(
            student,
            f"{base}/settle",
            {
                "session_token": session["session_token"],
                "queue_token": session.get("queue_token"),
                "duration_seconds": 0,
            },
        )
        self.assertEqual(settled.status_code, 200, settled.get_json())

    def _one_learning_round(self, student, queue, step):
        """View a word or answer a question, then fetch the next queue like the client."""

        task_id = student["task_id"]
        unviewed = [item for item in queue.get("familiarity") or [] if not item.get("viewed")]
        if queue.get("phase") == "familiarity" and unviewed:
            response = self._post(
                student,
                f"/api/miniprogram/student/tasks/{task_id}/vocabulary-learning/familiarity",
                {"queue_token": queue["queue_token"], "word_id": unviewed[0]["word_id"]},
            )
            self.assertEqual(response.status_code, 200, response.get_json())
            return response.get_json()
        question = queue["current_question"]
        submitted = self._post(
            student,
            "/api/dictation/submit",
            {
                "task_id": task_id,
                "queue_token": queue["queue_token"],
                "learning_question_id": question["learning_question_id"],
                "queue_item_id": question["queue_item_id"],
                "question_id": question["question_id"],
                "word_id": question["word_id"],
                "sense_id": question["sense_id"],
                "dimension": question["dimension"],
                "answer": self._stored_answer(
                    VocabularyLearningQuestion, question["learning_question_id"]
                ),
                "attempt_id": f"gate-learn:{task_id}:{step}",
                "retry": bool(queue.get("retry")),
                "input_mode": (
                    "strict"
                    if question["mode"] in {"audio_to_en", "zh_to_en", "context_fill"}
                    else "native"
                ),
            },
        )
        self.assertEqual(submitted.status_code, 200, submitted.get_json())
        response = self._queue(student)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _assert_gate_only_agrees(self, student, expected_required):
        with self.app.app_context():
            user = db.session.get(User, student["id"])
            full = review.review_preflight(user, student["task_id"])
            lean = review.review_preflight(user, student["task_id"], gate_only=True)
        self.assertEqual(full["required"], expected_required)
        for field in GATE_FIELDS:
            self.assertEqual(lean[field], full[field], field)
        if full["required"]:
            self.assertEqual(lean["due_count"], full["due_count"])
        return full, lean

    # -- tests -------------------------------------------------------------
    def test_gate_decision_is_identical_in_every_state(self):
        student = self._student("a", BACKLOG)
        full, _lean = self._assert_gate_only_agrees(student, True)  # backlog, nothing done today
        self.assertEqual(full["due_count"], BACKLOG)

        session = self._claim(student)
        self._assert_gate_only_agrees(student, True)  # an active batch

        self._finish_review(student, session)
        full, lean = self._assert_gate_only_agrees(student, False)  # cleared for today
        self.assertGreater(full["due_count"], 0)
        self.assertIsNone(lean["due_count"])

        self.assertEqual(self._queue(student).status_code, 200)
        self._assert_gate_only_agrees(student, False)  # task started

        self._claim(student)  # a second batch opened from Home must not interrupt the task
        self._assert_gate_only_agrees(student, False)

        self._assert_gate_only_agrees(self._student("b", 0), False)  # nothing due at all

    def test_new_task_is_still_blocked_until_the_review_batch_is_done(self):
        student = self._student("c", BACKLOG)
        blocked = self._queue(student)
        self.assertEqual(blocked.status_code, 409)
        payload = blocked.get_json()
        self.assertEqual(payload["error"], "vocabulary_review_required")
        self.assertEqual(payload["due_count"], BACKLOG)
        self.assertTrue(payload["batch_limit"])

        familiarity = self._post(
            student,
            f"/api/miniprogram/student/tasks/{student['task_id']}/vocabulary-learning/familiarity",
            {"queue_token": "x", "word_id": 1},
        )
        self.assertEqual(familiarity.status_code, 409)
        self.assertEqual(familiarity.get_json()["error"], "vocabulary_review_required")

    def test_in_progress_task_never_rescans_the_backlog(self):
        student = self._student("d", BACKLOG)
        self._finish_review(student, self._claim(student))
        scans = []
        original = review._due_candidates

        def counted(*args, **kwargs):
            scans.append(1)
            return original(*args, **kwargs)

        with patch.object(review, "_due_candidates", side_effect=counted):
            response = self._queue(student)  # entering the task
            self.assertEqual(response.status_code, 200, response.get_json())
            queue = response.get_json()
            for step in range(8):  # views, answers and the queue fetch after each answer
                if not (queue.get("current_question") or queue.get("familiarity")):
                    break
                queue = self._one_learning_round(student, queue, step)
        self.assertEqual(len(scans), 0)

    def test_home_summary_and_task_preflight_still_report_the_backlog(self):
        student = self._student("e", BACKLOG)
        self._finish_review(student, self._claim(student))
        self.assertEqual(self._queue(student).status_code, 200)

        preflight = self._get(
            student,
            f"/api/miniprogram/student/tasks/{student['task_id']}/vocabulary-review/preflight",
        ).get_json()
        summary = self._get(
            student, "/api/miniprogram/student/vocabulary-review/summary"
        ).get_json()
        self.assertFalse(preflight["required"])
        self.assertIsInstance(preflight["due_count"], int)
        self.assertEqual(preflight["due_count"], summary["due_count"])
        self.assertGreater(summary["due_count"], 0)

    def test_one_students_review_answer_keeps_other_students_counts_cached(self):
        reader = self._student("f", BACKLOG)
        writer = self._student("g", BACKLOG)
        summary_url = "/api/miniprogram/student/vocabulary-review/summary"
        loads = []
        original = review._eligible_due_sense_ids

        def counted(user, now):
            loads.append(user.id)
            return original(user, now)

        with patch.object(review, "_eligible_due_sense_ids", side_effect=counted):
            self.assertEqual(self._get(reader, summary_url).get_json()["due_count"], BACKLOG)
            session = self._claim(writer)
            before = self._get(writer, summary_url).get_json()
            item = session["items"][0]
            answered = self._post(
                writer,
                f"/api/miniprogram/student/vocabulary-review/sessions/{session['session_id']}/answers",
                {
                    "session_token": session["session_token"],
                    "review_item_id": item["review_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "sense_id": item["sense_id"],
                    "dimension": item["dimension"],
                    "answer": self._stored_answer(VocabularyReviewItem, item["review_item_id"]),
                    "attempt_id": "cache-isolation-1",
                    "input_mode": "native",
                },
            )
            self.assertEqual(answered.status_code, 200, answered.get_json())
            reader_loads_before = loads.count(reader["id"])
            self.assertEqual(self._get(reader, summary_url).get_json()["due_count"], BACKLOG)
            after = self._get(writer, summary_url).get_json()

        # The other student's snapshot survived the answer ...
        self.assertEqual(loads.count(reader["id"]), reader_loads_before)
        # ... while the answering student's own numbers were recomputed.
        self.assertEqual(after["due_count"], before["due_count"] - 1)


if __name__ == "__main__":
    unittest.main()
