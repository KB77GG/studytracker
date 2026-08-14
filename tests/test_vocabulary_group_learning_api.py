import json
import unittest
from datetime import date
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
    Task,
    User,
    VocabularyLearningQuestion,
    db,
)


class VocabularyGroupLearningApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="group-api-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(dictation_bp)
        self.app.register_blueprint(mp_bp)
        self.app.register_blueprint(vocab_review_bp)
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="group_api_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            student = User(
                username="group_api_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, student])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="HTTP 小组学生"))
            book = DictationBook(
                title="HTTP 小组书",
                word_count=4,
                created_by=teacher.id,
                is_active=True,
            )
            db.session.add(book)
            db.session.flush()
            db.session.add_all(
                [
                    DictationWord(
                        book_id=book.id,
                        sequence=1,
                        word="depend",
                        translation="依赖",
                        core_meaning_zh="依赖",
                        usage_pattern="depend on",
                        example_en="Students depend on clear feedback.",
                    ),
                    DictationWord(
                        book_id=book.id,
                        sequence=2,
                        word="focus",
                        translation="集中",
                        core_meaning_zh="集中",
                        usage_pattern="focus on",
                        example_en="Students focus on the main idea.",
                    ),
                    DictationWord(
                        book_id=book.id,
                        sequence=3,
                        word="contribute",
                        translation="贡献",
                        core_meaning_zh="贡献",
                        usage_pattern="contribute to",
                        example_en="Students contribute to discussion.",
                    ),
                    DictationWord(
                        book_id=book.id,
                        sequence=4,
                        word="achieve",
                        translation="实现",
                        core_meaning_zh="实现",
                        usage_pattern="achieve a goal",
                        example_en="Students achieve a useful goal.",
                    ),
                ]
            )
            db.session.flush()
            task = Task(
                date=date(2026, 8, 8),
                student_name="HTTP 小组学生",
                category="词汇",
                detail="HTTP 小组任务",
                created_by=teacher.id,
                dictation_book_id=book.id,
                vocabulary_goal="listening",
                dictation_mode="audio_to_en",
                dictation_word_start=1,
                dictation_word_end=1,
            )
            db.session.add(task)
            db.session.commit()
            self.student_id = student.id
            self.task_id = task.id
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

    def _task(self, goal, *, start=1, end=1, mode="audio_to_en"):
        with self.app.app_context():
            task = Task(
                date=date(2026, 8, 8),
                student_name="HTTP 小组学生",
                category="词汇",
                detail=f"HTTP {goal} 测试",
                created_by=db.session.query(User).filter_by(username="group_api_teacher").one().id,
                dictation_book_id=db.session.query(DictationBook).one().id,
                vocabulary_goal=goal,
                dictation_mode=mode,
                dictation_word_start=start,
                dictation_word_end=end,
            )
            db.session.add(task)
            db.session.commit()
            return task.id

    def _answer_current(self, task_id, queue, attempt_id):
        question = queue["current_question"]
        with self.app.app_context():
            stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
            answer_payload = json.loads(stored.answer_payload_json)
            answer = answer_payload.get("answer_option_id") or answer_payload.get("answer")
        return self.client.post(
            "/api/dictation/submit",
            json={
                "task_id": task_id,
                "queue_token": queue["queue_token"],
                "learning_question_id": question["learning_question_id"],
                "queue_item_id": question["queue_item_id"],
                "question_id": question["question_id"],
                "word_id": question["word_id"],
                "sense_id": question["sense_id"],
                "dimension": question["dimension"],
                "answer": answer,
                "attempt_id": attempt_id,
                "retry": bool(queue.get("retry")),
                "input_mode": "strict" if question["mode"] in {"audio_to_en", "zh_to_en", "context_fill"} else "native",
            },
            headers=self.headers,
        )

    def test_numeric_word_tts_uses_raw_text_and_licensed_provider(self):
        with self.app.app_context():
            book = db.session.query(DictationBook).one()
            word = DictationWord(
                book_id=book.id,
                sequence=5,
                word="28th June",
                translation="6月28日",
            )
            db.session.add(word)
            db.session.commit()
            word_id = word.id

        response = self.app.response_class(b"AUDIO", mimetype="audio/mpeg")
        with patch("api.dictation._proxy_tts_for_word", return_value=response) as proxy:
            result = self.client.get(f"/api/dictation/words/{word_id}/tts")

        self.assertEqual(result.status_code, 200)
        proxy.assert_called_once_with("28th June", preferred_providers=["dashscope"])

    def test_http_group_queue_requires_contract_and_finalize_is_idempotent(self):
        queue_url = f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-queue"
        queue = self.client.get(queue_url, headers=self.headers).get_json()
        self.assertEqual(queue["group_number"], 1)
        self.assertEqual(queue["phase"], "familiarity")
        self.assertTrue(queue["queue_token"])

        familiarity_url = (
            f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-learning/familiarity"
        )
        missing_familiarity_token = self.client.post(
            familiarity_url,
            json={"word_id": queue["familiarity"][0]["word_id"]},
            headers=self.headers,
        )
        self.assertEqual(missing_familiarity_token.status_code, 409)
        self.assertEqual(missing_familiarity_token.get_json()["error"], "queue_changed")
        queue = self.client.post(
            familiarity_url,
            json={
                "queue_token": queue["queue_token"],
                "word_id": queue["familiarity"][0]["word_id"],
            },
            headers=self.headers,
        ).get_json()
        question = queue["current_question"]
        missing_attempt = self.client.post(
            "/api/dictation/submit",
            json={
                "task_id": self.task_id,
                "queue_token": queue["queue_token"],
                "retry": False,
                "answer": "depend",
            },
            headers=self.headers,
        )
        self.assertEqual(missing_attempt.status_code, 400)
        self.assertEqual(missing_attempt.get_json()["error"], "attempt_id_required")

        with self.app.app_context():
            stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
            answer = json.loads(stored.answer_payload_json)["answer"]
        answer_payload = {
            "task_id": self.task_id,
            "queue_token": queue["queue_token"],
            "learning_question_id": question["learning_question_id"],
            "queue_item_id": question["queue_item_id"],
            "question_id": question["question_id"],
            "word_id": question["word_id"],
            "sense_id": question["sense_id"],
            "dimension": question["dimension"],
            "answer": answer,
            "attempt_id": "http-group-first",
            "retry": False,
            "input_mode": "strict",
        }
        first = self.client.post(
            "/api/dictation/submit", json=answer_payload, headers=self.headers
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        duplicate = self.client.post(
            "/api/dictation/submit",
            json=dict(answer_payload, answer="late-lost-response"),
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.get_json()["idempotent"])

        queue = self.client.get(queue_url, headers=self.headers).get_json()
        while not queue["completed"]:
            self.assertIsNotNone(queue["current_question"])
            follow_up = self._answer_current(
                self.task_id,
                queue,
                f"http-group-follow-up-{queue['current_question']['learning_question_id']}",
            )
            self.assertEqual(follow_up.status_code, 200, follow_up.get_json())
            queue = self.client.get(queue_url, headers=self.headers).get_json()

        finalize_url = f"/api/miniprogram/student/tasks/{self.task_id}/submit"
        settled = self.client.post(
            finalize_url,
            json={"queue_token": queue["queue_token"], "duration_seconds": 3},
            headers=self.headers,
        )
        self.assertEqual(settled.status_code, 200, settled.get_json())
        repeated = self.client.post(
            finalize_url,
            json={"queue_token": queue["queue_token"], "duration_seconds": 99},
            headers=self.headers,
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.get_json()["total_count"], settled.get_json()["total_count"])

    def test_http_context_choice_and_fill_share_one_mastery_encounter(self):
        task_id = self._task("reading")
        queue_url = f"/api/miniprogram/student/tasks/{task_id}/vocabulary-queue"
        queue = self.client.get(queue_url, headers=self.headers).get_json()
        familiarity_url = (
            f"/api/miniprogram/student/tasks/{task_id}/vocabulary-learning/familiarity"
        )
        while queue["phase"] == "familiarity":
            item = next(item for item in queue["familiarity"] if not item["viewed"])
            queue = self.client.post(
                familiarity_url,
                json={"queue_token": queue["queue_token"], "word_id": item["word_id"]},
                headers=self.headers,
            ).get_json()

        choice_seen = False
        fill_seen = False
        attempt_number = 0
        while queue["phase"] != "context_discrimination":
            self.assertIsNotNone(queue["current_question"])
            response = self._answer_current(task_id, queue, f"http-context-pre-{attempt_number}")
            self.assertEqual(response.status_code, 200, response.get_json())
            attempt_number += 1
            queue = self.client.get(queue_url, headers=self.headers).get_json()
        self.assertEqual(queue["current_question"]["mode"], "context_choice")
        choice_seen = True
        response = self._answer_current(task_id, queue, "http-context-choice")
        self.assertEqual(response.status_code, 200, response.get_json())
        queue = self.client.get(queue_url, headers=self.headers).get_json()
        self.assertEqual(queue["phase"], "context_production")
        self.assertEqual(queue["current_question"]["mode"], "context_fill")
        fill_seen = True
        response = self._answer_current(task_id, queue, "http-context-fill")
        self.assertEqual(response.status_code, 200, response.get_json())
        queue = self.client.get(queue_url, headers=self.headers).get_json()
        self.assertTrue(queue["completed"])
        settled = self.client.post(
            f"/api/miniprogram/student/tasks/{task_id}/submit",
            json={"queue_token": queue["queue_token"], "duration_seconds": 4},
            headers=self.headers,
        )
        self.assertEqual(settled.status_code, 200, settled.get_json())
        result = settled.get_json()
        self.assertTrue(choice_seen and fill_seen)
        self.assertEqual(result["dimensions"]["context_use"]["total"], 1)
        self.assertEqual(result["guidance_count"], 1)

    def test_http_mismatched_word_and_dimension_are_rejected(self):
        task_id = self._task("listening")
        queue_url = f"/api/miniprogram/student/tasks/{task_id}/vocabulary-queue"
        queue = self.client.get(queue_url, headers=self.headers).get_json()
        familiarity_url = (
            f"/api/miniprogram/student/tasks/{task_id}/vocabulary-learning/familiarity"
        )
        queue = self.client.post(
            familiarity_url,
            json={
                "queue_token": queue["queue_token"],
                "word_id": queue["familiarity"][0]["word_id"],
            },
            headers=self.headers,
        ).get_json()
        question = queue["current_question"]
        base = {
            "task_id": task_id,
            "queue_token": queue["queue_token"],
            "learning_question_id": question["learning_question_id"],
            "queue_item_id": question["queue_item_id"],
            "question_id": question["question_id"],
            "word_id": question["word_id"],
            "sense_id": question["sense_id"],
            "dimension": question["dimension"],
            "answer": "depend",
            "retry": False,
            "input_mode": "strict",
        }
        wrong_word = self.client.post(
            "/api/dictation/submit",
            json=dict(base, word_id=question["word_id"] + 1, attempt_id="http-wrong-word"),
            headers=self.headers,
        )
        self.assertEqual(wrong_word.status_code, 409)
        self.assertEqual(wrong_word.get_json()["error"], "question_not_current")
        wrong_dimension = self.client.post(
            "/api/dictation/submit",
            json=dict(base, dimension="context_use", attempt_id="http-wrong-dimension"),
            headers=self.headers,
        )
        self.assertEqual(wrong_dimension.status_code, 409)
        self.assertEqual(wrong_dimension.get_json()["error"], "question_not_current")

    def test_legacy_null_goal_keeps_old_queue_contract(self):
        with self.app.app_context():
            task = Task(
                date=date(2026, 8, 8),
                student_name="HTTP 小组学生",
                category="听写",
                detail="legacy API task",
                created_by=db.session.query(User).filter_by(username="group_api_teacher").one().id,
                dictation_book_id=db.session.query(DictationBook).one().id,
                vocabulary_goal=None,
                dictation_mode="audio_to_en",
                dictation_word_start=1,
                dictation_word_end=1,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        response = self.client.get(
            f"/api/miniprogram/student/tasks/{task_id}/dictation-queue",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertNotEqual(payload.get("task_mode"), "vocabulary_group_v2")
        self.assertIn("words", payload)


if __name__ == "__main__":
    unittest.main()
