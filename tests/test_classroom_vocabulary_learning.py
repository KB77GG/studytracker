"""Three-column imports work with the existing student learning/review APIs."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from flask import Flask
from flask_login import LoginManager

from api.classroom_vocabulary import classroom_vocabulary_bp
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
    VocabularyTaskSettlement,
    db,
)
from services.task_date_gate import beijing_today
from services.vocabulary_autonomous_review import claim_today_review


class ClassroomVocabularyLearningTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="classroom-learning-test-only",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        login_manager = LoginManager(self.app)

        @login_manager.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        for blueprint in (
            classroom_vocabulary_bp,
            dictation_bp,
            mp_bp,
            vocab_review_bp,
        ):
            self.app.register_blueprint(blueprint)
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="classroom_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            student = User(
                username="classroom_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, student])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="合成课堂学生"))
            db.session.commit()
            self.teacher_id, self.student_id = teacher.id, student.id
        self.staff = self.app.test_client()
        with self.staff.session_transaction() as session:
            session["_user_id"] = str(self.teacher_id)
            session["_fresh"] = True
            session["classroom_vocabulary_csrf"] = "test-csrf"
        self.staff_headers = {"X-CSRF-Token": "test-csrf"}
        token = jwt.encode(
            {"sub": str(self.student_id), "role": User.ROLE_STUDENT},
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        self.student = self.app.test_client()
        self.student_headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _student_request(self, method, path, **kwargs):
        response = getattr(self.student, method)(path, headers=self.student_headers, **kwargs)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _import_book(self, text):
        preview = self.staff.post(
            "/api/classroom-vocabulary/preview",
            data={"text": text},
            headers=self.staff_headers,
        )
        self.assertEqual(preview.status_code, 200, preview.get_json())
        parsed = preview.get_json()
        self.assertTrue(parsed["valid"], parsed)
        saved = self.staff.post(
            "/api/classroom-vocabulary/books",
            json={"title": "合成阅读课堂生词", "rows": parsed["rows"]},
            headers=self.staff_headers,
        )
        self.assertEqual(saved.status_code, 200, saved.get_json())
        book_id = saved.get_json()["book"]["id"]
        self.assertEqual(
            saved.get_json()["assignment_url"],
            f"/tasks?preset_dictation_book={book_id}",
        )
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 0, "Import must not publish tasks")
        return book_id

    def _assign_synthetic_task(self, book_id):
        # Task creation itself uses the existing staff drawer. This fixture
        # selects its saved defaults without importing the side-effectful app.
        with self.app.app_context():
            book = db.session.get(DictationBook, book_id)
            self.assertEqual(book.default_vocabulary_goal, "reading")
            words = DictationWord.query.filter_by(book_id=book_id).all()
            for word in words:
                self.assertFalse(word.core_meaning_zh)
                self.assertFalse(word.example_en)
                self.assertFalse(word.usage_pattern)
            task = Task(
                date=beijing_today(),
                student_name="合成课堂学生",
                category="词汇",
                detail="合成课堂词表任务",
                created_by=self.teacher_id,
                dictation_book_id=book.id,
                vocabulary_goal=book.default_vocabulary_goal,
                dictation_word_start=1,
                dictation_word_end=book.word_count,
                status="pending",
            )
            db.session.add(task)
            db.session.commit()
            return task.id

    def test_three_column_learning_settles_and_enters_next_day_meaning_review(self):
        book_id = self._import_book(
            "单词\t词性\t中文\n"
            "bed\t名词\t床\n"
            "fish\tn. & v.\t鱼\n"
            "sustainable\t形容词\t可持续的\n"
            "take part in\t短语\t参加"
        )
        task_id = self._assign_synthetic_task(book_id)
        queue_path = (
            f"/api/miniprogram/student/tasks/{task_id}/vocabulary-queue" "?supports_correction=1"
        )
        queue = self._student_request("get", queue_path)
        self.assertEqual(queue["phase"], "familiarity")
        meanings = {item["word"]: item["meaning"] for item in queue["familiarity"]}
        self.assertEqual(meanings["bed"], "n. 床")
        self.assertEqual(meanings["fish"], "n./v. 鱼")
        self.assertEqual(meanings["sustainable"], "adj. 可持续的")
        self.assertEqual(meanings["take part in"], "phr. 参加")
        while queue["phase"] == "familiarity":
            item = next(item for item in queue["familiarity"] if not item["viewed"])
            queue = self._student_request(
                "post",
                f"/api/miniprogram/student/tasks/{task_id}/vocabulary-learning/familiarity",
                json={"queue_token": queue["queue_token"], "word_id": item["word_id"]},
            )

        chinese_answers = {
            "bed": "床",
            "fish": "鱼",
            "sustainable": "可持续的",
            "take part in": "参加",
        }
        answered = []
        for _ in range(len(chinese_answers)):
            question = queue["current_question"]
            self.assertEqual(question["dimension"], "meaning_recall")
            self.assertEqual(question["mode"], "en_to_zh")
            word = question["question"]["prompt"]["word"]
            result = self._student_request(
                "post",
                "/api/dictation/submit",
                json={
                    "task_id": task_id,
                    "queue_token": queue["queue_token"],
                    **{
                        key: question[key]
                        for key in (
                            "learning_question_id",
                            "queue_item_id",
                            "question_id",
                            "word_id",
                            "sense_id",
                            "dimension",
                        )
                    },
                    "answer": chinese_answers[word],
                    "attempt_id": f"classroom-first-{question['word_id']}",
                    "retry": False,
                    "input_mode": "native",
                },
            )
            self.assertTrue(result["is_correct"], (word, result))
            answered.append(word)
            queue = self._student_request("get", queue_path)
        self.assertCountEqual(answered, chinese_answers)
        self.assertTrue(queue["completed"])

        settled = self._student_request(
            "post",
            f"/api/miniprogram/student/tasks/{task_id}/submit",
            json={"queue_token": queue["queue_token"], "duration_seconds": 10},
        )
        self.assertEqual(settled["accuracy"], 100)
        self.assertEqual(settled["total_count"], 4)
        self.assertEqual(settled["dimensions"], {"meaning_recall": {"correct": 4, "total": 4}})
        self.assertEqual(settled["skipped_count"], 4)
        self.assertTrue(all("context" in item["reason"] for item in settled["diagnostics"]))
        with self.app.app_context():
            self.assertTrue(db.session.get(Task, task_id).student_submitted)
            self.assertEqual(VocabularyTaskSettlement.query.count(), 1)
            masteries = StudentVocabularyMastery.query.filter_by(student_id=self.student_id).all()
            self.assertEqual(len(masteries), 4)
            due_times = [item.meaning_recall_next_due_at for item in masteries]
            self.assertTrue(all(due_times))
            next_review_at = max(due_times) + timedelta(seconds=1)
            # Keep the test importable on production's Python 3.10.
            current_utc = datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: UP017
            self.assertGreater(next_review_at, current_utc)
            self.assertLess(next_review_at - current_utc, timedelta(days=2))

        # Advance only the review service's injected clock. No production DB,
        # task state shortcuts or artificial due-date edits are involved.
        with patch(
            "api.vocab_review.claim_today_review",
            side_effect=lambda user, origin_task_id=None: claim_today_review(
                user, origin_task_id=origin_task_id, now=next_review_at
            ),
        ):
            review = self._student_request(
                "get", "/api/miniprogram/student/vocabulary-review/today"
            )
        self.assertEqual(review["total_count"], 4)
        self.assertEqual({item["dimension"] for item in review["items"]}, {"meaning_recall"})
        self.assertCountEqual(
            [item["question"]["prompt"]["word"] for item in review["items"]],
            chinese_answers,
        )


if __name__ == "__main__":
    unittest.main()
