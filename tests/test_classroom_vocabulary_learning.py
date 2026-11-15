"""Three-column imports work with the existing student learning/review APIs."""

import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from flask import Flask
from flask_login import LoginManager

from api.classroom_vocabulary import classroom_vocabulary_bp
from api.dictation import dictation_bp
from api.miniprogram import mp_bp
from api.vocab_review import vocab_review_bp
from dictation_answers import is_english_answer_correct
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
from services.vocabulary_autonomous_review import (
    _candidate_is_eligible,
    claim_today_review,
    settle_review_session,
    submit_review_answer,
    submit_review_correction,
)
from services.vocabulary_context import build_context_question
from services.vocabulary_mastery import _question_for, build_meaning_recall_options
from services.vocabulary_synonyms import (
    SYNONYM_SENSE_POS,
    is_synonym_word,
    synonym_sense_key,
)


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

    def test_mixed_synonym_learning_correction_settlement_and_due_review(self):
        book_id = self._import_book(
            "participate\t=\ttake part in\n"
            "look after\t=\tcare for\n"
            "bed\tn.\t床\n"
            "well-being\t=\twelfare"
        )
        task_id = self._assign_synthetic_task(book_id)
        queue_path = (
            f"/api/miniprogram/student/tasks/{task_id}/vocabulary-queue?supports_correction=1"
        )
        queue = self._student_request("get", queue_path)
        cards = {item["word"]: item["meaning"] for item in queue["familiarity"]}
        self.assertEqual(cards["participate"], "= take part in")
        self.assertEqual(cards["look after"], "= care for")
        self.assertEqual(cards["bed"], "n. 床")
        while queue["phase"] == "familiarity":
            item = next(item for item in queue["familiarity"] if not item["viewed"])
            queue = self._student_request(
                "post",
                f"/api/miniprogram/student/tasks/{task_id}/vocabulary-learning/familiarity",
                json={"queue_token": queue["queue_token"], "word_id": item["word_id"]},
            )
        answers = {
            "participate": "take part in",
            "look after": "care for",
            "bed": "床",
            "well-being": "welfare",
        }
        wrong_first_seen = False
        for index in range(12):
            if queue["completed"]:
                break
            question = queue["current_question"]
            snapshot = question["question"]
            self.assertEqual(question["dimension"], "meaning_recall")
            if question["mode"] == "context_fill":
                self.assertEqual(snapshot["kind"], "synonym_recall")
                self.assertEqual(snapshot["answer_type"], "english")
                word = snapshot["prompt"]["sentence"].removesuffix(" = ____")
                self.assertNotIn(answers[word], str(snapshot))
            else:
                self.assertEqual(question["mode"], "en_to_zh")
                word = snapshot["prompt"]["word"]
                self.assertEqual(word, "bed")
            is_wrong_first = word == "participate" and not wrong_first_seen
            payload = {
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
                "answer": "take" if is_wrong_first else answers[word],
                "attempt_id": f"synonym-task-{index}",
                "retry": bool(question.get("retry")),
                "supports_correction": True,
                "input_mode": "native",
            }
            result = self._student_request("post", "/api/dictation/submit", json=payload)
            self.assertEqual(result["is_correct"], not is_wrong_first)
            if is_wrong_first:
                wrong_first_seen = True
                # Reading's existing flow corrects at the group-end retry;
                # immediate task corrections are reserved for comprehensive.
                self.assertFalse(result["correction_required"])
            queue = self._student_request("get", queue_path)
        self.assertTrue(wrong_first_seen)
        self.assertTrue(queue["completed"])
        settled = self._student_request(
            "post",
            f"/api/miniprogram/student/tasks/{task_id}/submit",
            json={"queue_token": queue["queue_token"], "duration_seconds": 10},
        )
        self.assertEqual(settled["accuracy"], 75)
        self.assertEqual(settled["dimensions"], {"meaning_recall": {"correct": 3, "total": 4}})
        with self.app.app_context():
            masteries = StudentVocabularyMastery.query.filter_by(student_id=self.student_id).all()
            self.assertEqual(len(masteries), 4)
            next_review_at = max(item.meaning_recall_next_due_at for item in masteries)
            next_review_at += timedelta(seconds=1)

        # Exercise real review HTTP submit/correct/settle with only its injected
        # clock advanced. Existing first-answer scores must remain unchanged.
        with patch.multiple(
            "api.vocab_review",
            claim_today_review=lambda *a, **k: claim_today_review(*a, **k, now=next_review_at),
            submit_review_answer=lambda *a, **k: submit_review_answer(*a, **k, now=next_review_at),
            submit_review_correction=lambda *a, **k: submit_review_correction(
                *a, **k, now=next_review_at
            ),
            settle_review_session=lambda *a, **k: settle_review_session(
                *a, **k, now=next_review_at
            ),
        ):
            review = self._student_request(
                "get", "/api/miniprogram/student/vocabulary-review/today"
            )
            self.assertEqual(review["total_count"], 4)
            review_url = (
                "/api/miniprogram/student/vocabulary-review/sessions/" f"{review['session_id']}"
            )
            for item in review["items"]:
                snapshot = item["question"]
                word = (
                    snapshot["prompt"]["sentence"].removesuffix(" = ____")
                    if item["mode"] == "context_fill"
                    else snapshot["prompt"]["word"]
                )
                self.assertEqual(item["dimension"], "meaning_recall")
                payload = {
                    "session_token": review["session_token"],
                    **{
                        key: item[key]
                        for key in (
                            "review_item_id",
                            "question_id",
                            "word_id",
                            "sense_id",
                            "dimension",
                        )
                    },
                    "answer": "takepartin" if word == "participate" else answers[word],
                    "attempt_id": f"synonym-review-{item['word_id']}",
                    "supports_correction": True,
                    "input_mode": "native",
                }
                result = self._student_request("post", review_url + "/answers", json=payload)
                self.assertEqual(result["is_correct"], word != "participate")
                if word == "participate":
                    self.assertTrue(result["correction_required"])
                    corrected = self._student_request(
                        "post",
                        review_url + "/corrections",
                        json={
                            **payload,
                            "answer": "TAKE   PART IN",
                            "attempt_id": "synonym-review-correction",
                        },
                    )
                    self.assertTrue(corrected["correction_is_correct"])
            review_result = self._student_request(
                "post",
                review_url + "/settle",
                json={
                    "session_token": review["session_token"],
                    "queue_token": review["queue_token"],
                    "supports_correction": True,
                },
            )
            self.assertEqual(review_result["accuracy"], 75)
            self.assertEqual(review_result["total_count"], 4)
            self.assertTrue(review_result["independent_review"])
        with self.app.app_context():
            self.assertEqual(
                json.loads(VocabularyTaskSettlement.query.one().result_json)["accuracy"], 75
            )


class ClassroomSynonymQuestionTest(unittest.TestCase):
    def word(self, left="participate", right="take part in"):
        return SimpleNamespace(
            id=10,
            sense_id=20,
            word=left,
            translation="= " + right,
            core_meaning_zh=None,
            accepted_answers=None,
            phonetic=None,
            sense=SimpleNamespace(
                lemma=left,
                definition_en=right,
                canonical_key=synonym_sense_key(left, right),
                part_of_speech=SYNONYM_SENSE_POS,
            ),
        )

    def test_synonym_uses_full_english_answers_in_both_directions(self):
        word = self.word()
        public, private = _question_for(word, "meaning_recall", "reading", 0, [])
        self.assertEqual(public["mode"], "context_fill")
        self.assertEqual(public["prompt"]["sentence"], "participate = ____")
        self.assertEqual(private["accepted_answers"], [])
        for answer in ("take", "part in", "take part", "takepartin", "participate"):
            self.assertFalse(is_english_answer_correct(answer, private["answer"]), answer)
        self.assertTrue(is_english_answer_correct("TAKE   PART IN", private["answer"]))
        reverse, reverse_answer = _question_for(word, "form_recall", "writing", 0, [])
        self.assertEqual(reverse["prompt"]["sentence"], "take part in = ____")
        self.assertEqual(reverse_answer["answer"], "participate")
        for dimension in ("context_use", "audio_form_recall"):
            self.assertIsNone(_question_for(word, dimension, "comprehensive", 0, []))
            self.assertFalse(_candidate_is_eligible(word, None, dimension, {}))
        for dimension in ("meaning_recall", "form_recall"):
            self.assertTrue(_candidate_is_eligible(word, None, dimension, {}))
        self.assertIsNone(build_context_question(word, []))

    def test_only_explicit_valid_pair_metadata_selects_synonym_recall(self):
        word = self.word()
        word.sense = None
        self.assertFalse(is_synonym_word(word))
        question, answer = _question_for(word, "meaning_recall", "reading", 0, [])
        self.assertEqual(question["mode"], "en_to_zh")
        self.assertEqual(answer["answer_type"], "chinese")
        for changed in ("word", "definition", "key", "marker", "missing_key", "bad_prefix"):
            word = self.word()
            if changed == "word":
                word.word = "join"
            elif changed == "definition":
                word.sense.definition_en = ""
            elif changed == "marker":
                word.sense.part_of_speech = None
            elif changed == "missing_key":
                word.sense.canonical_key = None
            elif changed == "bad_prefix":
                word.sense.canonical_key = "broken-key"
            else:
                word.sense.canonical_key += "invalid"
            self.assertTrue(is_synonym_word(word))
            self.assertIsNone(_question_for(word, "meaning_recall", "reading", 0, []))
            self.assertFalse(_candidate_is_eligible(word, None, "meaning_recall", {}))

    def test_pairs_never_become_chinese_distractors_in_a_mixed_book(self):
        candidates = []
        for index, (word, meaning) in enumerate(
            (("bed", "床"), ("desk", "桌子"), ("chair", "椅子"), ("sofa", "沙发"))
        ):
            candidate = self.word(word, "placeholder")
            candidate.id = index + 1
            candidate.sense = None
            candidate.translation = meaning
            candidate.example_en = "The bed is next to the window."
            candidates.append(candidate)
        candidates.append(self.word())
        public, _ = build_context_question(
            candidates[0], candidates, allowed_kinds={"meaning_choice"}
        )
        self.assertCountEqual(
            [option["label"] for option in public["options"]], ["床", "桌子", "椅子", "沙发"]
        )
        options = build_meaning_recall_options(candidates[0], candidates, "mixed-synonym")
        self.assertCountEqual(
            [option["label"] for option in options], ["床", "桌子", "椅子", "沙发"]
        )

    def test_pair_key_and_expected_answer_normalize_phrase_punctuation(self):
        self.assertEqual(
            synonym_sense_key("WELL–BEING", "one’s welfare"),
            synonym_sense_key("well-being", "one's   welfare"),
        )
        _public, private = _question_for(
            self.word("well-being", "one’s welfare"), "meaning_recall", "reading", 0, []
        )
        self.assertTrue(is_english_answer_correct("one's welfare", private["answer"]))


if __name__ == "__main__":
    unittest.main()
