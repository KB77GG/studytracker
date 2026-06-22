import unittest
from pathlib import Path

import jwt
from flask import Flask
from flask_login import LoginManager

from api.dictation import dictation_bp
from dictation_answers import (
    is_chinese_answer_correct,
    is_english_answer_correct,
    parse_answer_variants,
    serialize_answer_variants,
)
from models import DictationAnswerAppeal, DictationBook, DictationWord, User, db


ROOT = Path(__file__).resolve().parents[1]


class DictationAnswerTest(unittest.TestCase):
    def test_does_not_automatically_accept_regional_spellings_or_synonyms(self):
        self.assertFalse(is_english_answer_correct("behaviour", "behavior"))
        self.assertFalse(is_english_answer_correct("behavior", "behaviour"))
        self.assertFalse(is_english_answer_correct("bicycle", "bike"))

    def test_teacher_approved_answers_are_parsed_without_fuzzy_matching(self):
        stored = serialize_answer_variants("cellphone; mobile phone")
        self.assertEqual(parse_answer_variants(stored), ["cellphone", "mobile phone"])
        self.assertTrue(
            is_english_answer_correct(
                "mobile phone", "cell phone", accepted_answers=stored
            )
        )
        self.assertFalse(is_english_answer_correct("effect", "affect"))
        self.assertEqual(parse_answer_variants("n. bike / bicycle"), ["bike", "bicycle"])

    def test_chinese_review_answers_remain_supported(self):
        self.assertTrue(is_chinese_answer_correct("自行车", "自行车；脚踏车"))
        self.assertTrue(is_chinese_answer_correct("脚踏车", "自行车；脚踏车"))
        self.assertFalse(is_chinese_answer_correct("汽车", "自行车；脚踏车"))

    def test_task_review_page_exposes_vocabulary_appeals(self):
        markup = (ROOT / "templates/tasks.html").read_text(encoding="utf-8")
        self.assertIn("词汇判分申诉", markup)
        self.assertIn("wordAppealReviewList", markup)
        self.assertIn("通过并收录", markup)
        self.assertIn("/api/dictation/appeals?status=pending", markup)


class DictationSubmitApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
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

        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="answer_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            student = User(
                username="answer_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, student])
            db.session.flush()
            book = DictationBook(
                title="answer variants",
                word_count=2,
                created_by=teacher.id,
                is_active=True,
                book_type="translation",
            )
            db.session.add(book)
            db.session.flush()
            bike = DictationWord(
                book_id=book.id,
                sequence=1,
                word="bike",
                translation="自行车",
            )
            behaviour = DictationWord(
                book_id=book.id,
                sequence=2,
                word="behaviour",
                translation="行为；举止",
            )
            db.session.add_all([bike, behaviour])
            db.session.commit()
            self.teacher_id = teacher.id
            self.student_id = student.id
            self.book_id = book.id
            self.bike_id = bike.id
            self.behaviour_id = behaviour.id

        token = jwt.encode(
            {"sub": str(self.student_id)},
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        self.client = self.app.test_client()
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def submit(self, word_id, answer, mode):
        return self.client.post(
            "/api/dictation/submit",
            json={
                "word_id": word_id,
                "book_id": self.book_id,
                "answer": answer,
                "mode": mode,
            },
            headers=self.headers,
        )

    def test_english_grading_requires_canonical_or_reviewed_answer(self):
        regional = self.submit(self.behaviour_id, "behavior", "audio_to_en")
        synonym = self.submit(self.bike_id, "bicycle", "zh_to_en")
        audio_synonym = self.submit(self.bike_id, "bicycle", "audio_to_en")

        self.assertFalse(regional.get_json()["is_correct"])
        self.assertFalse(synonym.get_json()["is_correct"])
        self.assertFalse(audio_synonym.get_json()["is_correct"])

    def test_chinese_review_grading(self):
        response = self.submit(self.behaviour_id, "举止", "en_to_zh")
        self.assertTrue(response.get_json()["is_correct"])

    def create_appeal(self, answer="cycle", mode="zh_to_en"):
        return self.client.post(
            "/api/dictation/appeals",
            json={
                "word_id": self.bike_id,
                "answer": answer,
                "mode": mode,
                "reason": "这个表达意思相同",
            },
            headers=self.headers,
        )

    def login_teacher(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.teacher_id)
            session["_fresh"] = True

    def test_appeal_is_deduplicated_and_teacher_can_accept_answer(self):
        created = self.create_appeal()
        duplicate = self.create_appeal()
        self.assertEqual(created.status_code, 201)
        self.assertTrue(duplicate.get_json()["duplicate"])
        appeal_id = created.get_json()["appeal"]["id"]

        self.login_teacher()
        queue = self.client.get("/api/dictation/appeals?status=pending")
        self.assertEqual(queue.get_json()["total"], 1)
        reviewed = self.client.post(
            f"/api/dictation/appeals/{appeal_id}/review",
            json={"decision": "approved", "resolution_note": "可接受"},
        )
        self.assertTrue(reviewed.get_json()["appeal"]["added_to_accepted_answers"])

        with self.app.app_context():
            word = db.session.get(DictationWord, self.bike_id)
            self.assertIn("cycle", parse_answer_variants(word.accepted_answers))
            appeal = db.session.get(DictationAnswerAppeal, appeal_id)
            self.assertEqual(appeal.status, DictationAnswerAppeal.STATUS_APPROVED)

    def test_cannot_appeal_the_canonical_answer(self):
        response = self.create_appeal(answer="bike")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "answer_already_accepted")


if __name__ == "__main__":
    unittest.main()
