"""Classroom import parser, staff boundaries and atomic/idempotent writes."""

import io
import unittest
from unittest.mock import patch

from flask import Flask
from flask_login import LoginManager
from jinja2 import DictLoader
from openpyxl import Workbook
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from api.classroom_vocabulary import classroom_vocabulary_bp
from dictation_answers import is_chinese_answer_correct, strip_part_of_speech_prefix
from models import DictationBook, DictationWord, Task, User, VocabularySense, db
from services.classroom_vocabulary import (
    BOOK_DESCRIPTION,
    MAX_BYTES,
    SYNONYM_BOOK_DESCRIPTION,
    ClassroomVocabularyError,
    preview_text,
    preview_workbook,
    validate_rows,
)
from services.vocabulary_synonyms import SYNONYM_SENSE_POS, synonym_sense_key


def workbook_file(rows, *, second_sheet=False, active_second=False):
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    if second_sheet:
        workbook.create_sheet("另一张表").append(["wrong", "adj.", "错误的"])
    if active_second:
        workbook.active = 1
    stream = io.BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return FileStorage(stream, filename="课堂词表.xlsx")


class ClassroomVocabularyParserTest(unittest.TestCase):
    def test_tsv_header_blanks_phrase_and_pos_are_preserved(self):
        result = preview_text(
            "\ufeff单词\t词性\t中文\n\n take off \t 短语 \t 起飞 \n bed\t名词\t床\n"
        )
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["word_count"], 2)
        self.assertEqual(
            result["rows"][0],
            {"line": 3, "word": "take off", "part_of_speech": "phr.", "meaning": "起飞"},
        )
        self.assertEqual(result["rows"][1]["part_of_speech"], "n.")
        self.assertEqual(len(result["warnings"]), 2)

    def test_csv_quoted_comma_is_one_meaning(self):
        result = preview_text('word,pos,meaning\n"rely on",phr.,"依靠,依赖"')
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["rows"][0]["meaning"], "依靠,依赖")

    def test_empty_pos_and_headerless_rows_are_supported(self):
        result = preview_text("look after\t\t照顾")
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["rows"][0]["part_of_speech"], "")

    def test_bad_columns_and_empty_meaning_are_visible(self):
        result = preview_text("apple n. 苹果\nword\tn.\t\nwrong\tadj.\t错误\textra")
        self.assertFalse(result["valid"])
        self.assertEqual(result["word_count"], 3)
        self.assertEqual({row["line"] for row in result["errors"]}, {1, 2, 3})

    def test_exact_duplicates_error_but_different_meanings_survive(self):
        result = preview_text("bank\tn.\t银行\nBank\t名词\t银行\nbank\tn.\t河岸")
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["rows"]), 3)
        self.assertIn("第 1 行重复", result["errors"][0]["message"])
        different = preview_text("bank\tn.\t银行\nbank\tn.\t河岸")
        self.assertTrue(different["valid"], different)

    def test_multiple_targets_are_rejected_instead_of_silently_using_first(self):
        for word in ("apple / pear", "apple, pear", "apple;pear"):
            with self.subTest(word=word):
                result = validate_rows(
                    [{"word": word, "part_of_speech": "n.", "meaning": "苹果；梨"}]
                )
                self.assertFalse(result["valid"])

    def test_limits_and_malformed_types(self):
        for rows in (None, {}, [None] * 1201):
            with self.assertRaises(ClassroomVocabularyError):
                validate_rows(rows)
        for row in (
            {"word": 5},
            {"word": "a" * 101, "meaning": "词"},
            {"word": "hi", "meaning": "x\ny"},
        ):
            self.assertFalse(validate_rows([row])["valid"])
        with self.assertRaises(ClassroomVocabularyError):
            preview_text("x" * (MAX_BYTES + 1))
        self.assertFalse(preview_text("")["valid"])

    def test_normalized_pos_length_limit(self):
        row = {"word": "word", "part_of_speech": "a/a/a/a/a/a/a/a", "meaning": "词"}
        self.assertFalse(validate_rows([row])["valid"])

    def test_common_and_combined_pos_keep_short_chinese_gradeable(self):
        for pos in (
            "n",
            "名词",
            "数词",
            "det.",
            "art.",
            "aux.",
            "int.",
            "interj.",
            "modal.",
            "n./v.",
            "vt. & vi.",
        ):
            with self.subTest(pos=pos):
                result = preview_text(f"word\t{pos}\t词")
                self.assertTrue(result["valid"], result)
                translation = result["rows"][0]["part_of_speech"] + " 词"
                self.assertEqual(strip_part_of_speech_prefix(translation), "词")
                self.assertTrue(is_chinese_answer_correct("词", translation))
                self.assertFalse(is_chinese_answer_correct("床", translation))

    def test_xlsx_uses_first_sheet_even_if_another_is_active(self):
        result = preview_workbook(
            workbook_file(
                [["单词", "词性", "中文"], ["bed", "n.", "床"]],
                second_sheet=True,
                active_second=True,
            )
        )
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["rows"][0]["word"], "bed")
        self.assertIn("第一个工作表", result["warnings"][0]["message"])

    def test_xlsx_rejects_formula_corruption_and_old_extension(self):
        for file in (
            workbook_file([["bed", "n.", '=CONCAT("床")']]),
            FileStorage(io.BytesIO(b"not-a-workbook"), filename="bad.xlsx"),
            FileStorage(io.BytesIO(b"old"), filename="old.xls"),
        ):
            with self.assertRaises(ClassroomVocabularyError):
                preview_workbook(file)

    def test_synonym_header_and_complete_phrases_are_preserved(self):
        result = preview_text(
            "原词或词组\t=\t同义替换词或词组\n"
            " participate \t = \t take part in \n"
            "in spite of\t＝\tdespite"
        )
        self.assertTrue(result["valid"], result)
        self.assertEqual(
            result["rows"],
            [
                {
                    "line": 2,
                    "word": "participate",
                    "part_of_speech": "=",
                    "meaning": "take part in",
                },
                {"line": 3, "word": "in spite of", "part_of_speech": "=", "meaning": "despite"},
            ],
        )
        self.assertEqual(result["word_count"], 2)
        self.assertIn("符号已统一", result["warnings"][0]["message"])

    def test_mixed_csv_and_xlsx_lists_keep_original_order(self):
        rows = [["bed", "n.", "床"], ["participate", "=", "take part in"], ["help", "v.", "帮助"]]
        for result in (
            preview_text("\n".join(",".join(row) for row in rows)),
            preview_workbook(workbook_file(rows)),
        ):
            with self.subTest(result=result):
                self.assertTrue(result["valid"], result)
                self.assertEqual(
                    [row["word"] for row in result["rows"]], ["bed", "participate", "help"]
                )
                self.assertEqual(result["rows"][1]["meaning"], "take part in")
                self.assertEqual(result["rows"][1]["part_of_speech"], "=")

    def test_synonym_duplicates_normalize_both_sides_but_preserve_direction(self):
        result = preview_text("join\t=\ttake part in\nJOIN\t＝\tTAKE  PART IN")
        self.assertFalse(result["valid"])
        self.assertIn("第 1 行重复", result["errors"][0]["message"])
        self.assertTrue(preview_text("join\t=\tparticipate\nparticipate\t=\tjoin")["valid"])
        self.assertTrue(preview_text("join\t=\tparticipate\njoin\t=\ttake part in")["valid"])

    def test_synonym_rejects_self_pairs_incomplete_phrases_and_annotations(self):
        for left, right in (
            ("Join", "join"),
            ("take part in", "take  part in"),
            ("join", ""),
            ("", "participate"),
            ("参加", "participate"),
            ("join", "参加"),
            ("join", "take part in / participate"),
            ("join", "participate; enroll"),
            ("join", "participate, enroll"),
            ("join", "take part in (sth)"),
            ("join (a group)", "participate"),
            ("join", "v. participate"),
            ("join", "x" * 101),
            ("x" * 101, "participate"),
            ("join", "take\npart in"),
        ):
            with self.subTest(left=left, right=right):
                result = validate_rows([{"word": left, "part_of_speech": "=", "meaning": right}])
                self.assertFalse(result["valid"], result)
        self.assertFalse(
            preview_text("join = take part in")["valid"], "Spaces must not delimit columns"
        )

    def test_synonym_typography_normalizes_visibly_and_plain_english_meaning_warns(self):
        result = preview_text("one’s own\t=\tself‑owned")
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["rows"][0]["word"], "one's own")
        self.assertEqual(result["rows"][0]["meaning"], "self-owned")
        self.assertEqual(len(result["warnings"]), 2)
        ordinary = preview_text("join\tv.\tparticipate")
        self.assertTrue(ordinary["valid"], ordinary)
        self.assertIn("第二列改为 =", ordinary["warnings"][0]["message"])


class ClassroomVocabularyApiTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="classroom-test",
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        self.app.jinja_loader = DictLoader({"classroom_vocabulary.html": "{{ csrf_token }}"})
        db.init_app(self.app)
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(classroom_vocabulary_bp)
        with self.app.app_context():
            db.create_all()
            for role in ("teacher", "assistant", "admin", "student", "parent", "course_planner"):
                db.session.add(User(username=role, password_hash="test", role=role))
            db.session.commit()
            self.ids = {user.role: user.id for user in User.query.all()}
        self.client = self.app.test_client()
        self.login()
        self.payload = {
            "title": "阅读课生词",
            "rows": [
                {"word": "bed", "part_of_speech": "名词", "meaning": "床"},
                {"word": "take off", "part_of_speech": "phr.", "meaning": "起飞"},
            ],
        }

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def login(self, role="teacher"):
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(self.ids[role])
            session["_fresh"] = True
            session["classroom_vocabulary_csrf"] = "csrf-test"
        self.headers = {"X-CSRF-Token": "csrf-test"}

    def save(self, payload=None, headers=None):
        return self.client.post(
            "/api/classroom-vocabulary/books",
            json=self.payload if payload is None else payload,
            headers=self.headers if headers is None else headers,
        )

    def counts(self):
        with self.app.app_context():
            return DictationBook.query.count(), DictationWord.query.count(), Task.query.count()

    def test_staff_roles_can_preview_and_save(self):
        for role in ("teacher", "assistant", "admin"):
            self.login(role)
            response = self.client.post(
                "/api/classroom-vocabulary/preview",
                data={"text": "bed\tn.\t床"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json["valid"])
            self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.counts(), (3, 6, 0))

    def test_student_parent_planner_and_anonymous_cannot_import(self):
        for role in ("student", "parent", "course_planner"):
            self.login(role)
            self.assertEqual(self.save().status_code, 403)
            self.assertEqual(self.client.get("/materials/classroom-vocabulary").status_code, 403)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.save().status_code, 401)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_csrf_origin_and_inactive_account_rejected(self):
        self.assertEqual(self.save(headers={}).status_code, 403)
        self.assertEqual(
            self.save(headers={**self.headers, "Origin": "https://elsewhere.invalid"}).status_code,
            403,
        )
        with self.app.app_context():
            db.session.get(User, self.ids["teacher"]).is_active = False
            db.session.commit()
        self.assertIn(self.save().status_code, (401, 403))
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_page_issues_csrf_token_and_preview_has_no_db_effect(self):
        with self.client.session_transaction() as session:
            session.pop("classroom_vocabulary_csrf")
        page = self.client.get("/materials/classroom-vocabulary")
        self.assertEqual(page.status_code, 200)
        self.headers = {"X-CSRF-Token": page.get_data(as_text=True)}
        response = self.client.post(
            "/api/classroom-vocabulary/preview", data={"text": "bed\tn.\t床"}, headers=self.headers
        )
        self.assertTrue(response.json["valid"])
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_save_order_reading_defaults_and_retry_reuses(self):
        result = self.save().json
        self.assertFalse(result["reused"])
        self.assertEqual(
            result["assignment_url"], f'/tasks?preset_dictation_book={result["book"]["id"]}'
        )
        retry = self.save().json
        self.assertTrue(retry["reused"])
        self.assertEqual(retry["book"]["id"], result["book"]["id"])
        with self.app.app_context():
            book = db.session.get(DictationBook, result["book"]["id"])
            self.assertEqual(book.default_vocabulary_goal, "reading")
            self.assertEqual(book.book_type, "dictation")
            words = book.words.order_by(DictationWord.sequence).all()
            self.assertEqual(
                [(word.sequence, word.word, word.translation) for word in words],
                [(1, "bed", "n. 床"), (2, "take off", "phr. 起飞")],
            )
            self.assertTrue(
                all(
                    word.core_meaning_zh is None
                    and word.example_en is None
                    and word.audio_us is None
                    for word in words
                )
            )
        self.assertEqual(self.counts(), (1, 2, 0))

    def test_changed_content_and_other_teacher_are_not_overwritten(self):
        first = self.save().json["book"]["id"]
        self.payload["rows"][0]["meaning"] = "河床"
        second = self.save().json["book"]["id"]
        self.assertNotEqual(first, second)
        self.login("assistant")
        third = self.save().json["book"]["id"]
        self.assertNotEqual(second, third)
        self.assertEqual(self.counts(), (3, 6, 0))

    def test_invalid_rows_or_title_never_partially_create_book(self):
        for payload in (
            [1],
            {"title": "hello\nworld", "rows": self.payload["rows"]},
            {"title": "list", "rows": [*self.payload["rows"], {"word": "missing", "meaning": ""}]},
        ):
            self.assertEqual(self.save(payload).status_code, 400)
            self.assertEqual(self.counts(), (0, 0, 0))

    def test_db_failure_rolls_back_book_and_words(self):
        with self.assertLogs(self.app.logger, level="ERROR"):
            with patch.object(
                db.session, "commit", side_effect=SQLAlchemyError("synthetic failure")
            ):
                response = self.save()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json["error"], "save_failed")
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_mixed_import_saves_typed_synonym_sense_and_retry_reuses(self):
        preview = self.client.post(
            "/api/classroom-vocabulary/preview",
            data={"text": "bed\tn.\t床\nparticipate\t＝\ttake part in"},
            headers=self.headers,
        )
        self.assertEqual(preview.status_code, 200)
        self.assertTrue(preview.json["valid"], preview.json)
        payload = {"title": "课堂同义替换", "rows": preview.json["rows"]}
        result = self.save(payload)
        self.assertEqual(result.status_code, 200, result.json)
        retry = self.save(payload)
        self.assertTrue(retry.json["reused"])
        self.assertEqual(result.json["book"]["id"], retry.json["book"]["id"])
        with self.app.app_context():
            book = db.session.get(DictationBook, result.json["book"]["id"])
            self.assertEqual(book.description, SYNONYM_BOOK_DESCRIPTION)
            self.assertEqual(book.default_vocabulary_goal, "reading")
            ordinary, synonym = book.words.order_by(DictationWord.sequence).all()
            self.assertEqual(
                (ordinary.word, ordinary.translation, ordinary.sense_id), ("bed", "n. 床", None)
            )
            self.assertEqual((synonym.word, synonym.translation), ("participate", "= take part in"))
            self.assertEqual(synonym.sense.part_of_speech, SYNONYM_SENSE_POS)
            self.assertEqual(synonym.sense.definition_en, "take part in")
            self.assertEqual(
                synonym.sense.canonical_key, synonym_sense_key("participate", "take part in")
            )
            self.assertIsNone(synonym.sense.meaning_zh)
            self.assertIsNone(synonym.accepted_answers)
            self.assertIsNone(synonym.core_meaning_zh)
            self.assertEqual(VocabularySense.query.count(), 1)
        self.assertEqual(self.counts(), (1, 2, 0))

    def test_synonym_sense_reuses_only_the_same_ordered_pair_across_books(self):
        pairs = [
            ("participate", "take part in"),
            ("PARTICIPATE", "TAKE  PART IN"),
            ("participate", "join"),
            ("take part in", "participate"),
        ]
        ids = []
        for index, (left, right) in enumerate(pairs):
            response = self.save(
                {
                    "title": f"课堂词表{index}",
                    "rows": [{"word": left, "part_of_speech": "=", "meaning": right}],
                }
            )
            self.assertEqual(response.status_code, 200, response.json)
            ids.append(response.json["book"]["id"])
        with self.app.app_context():
            senses = [
                DictationWord.query.filter_by(book_id=book_id).one().sense_id for book_id in ids
            ]
            self.assertEqual(senses[0], senses[1])
            self.assertEqual(len(set(senses)), 3)
            self.assertEqual(VocabularySense.query.count(), 3)

    def test_synonym_and_ordinary_books_do_not_merge_even_with_same_display(self):
        payload = {
            "title": "同名词表",
            "rows": [{"word": "join", "part_of_speech": "=", "meaning": "participate"}],
        }
        with self.app.app_context():
            old = DictationBook(
                title=payload["title"],
                description=BOOK_DESCRIPTION,
                created_by=self.ids["teacher"],
                word_count=1,
            )
            db.session.add(old)
            db.session.flush()
            db.session.add(
                DictationWord(book_id=old.id, sequence=1, word="join", translation="= participate")
            )
            db.session.commit()
            old_id = old.id
        saved = self.save(payload)
        self.assertEqual(saved.status_code, 200)
        self.assertFalse(saved.json["reused"])
        self.assertNotEqual(saved.json["book"]["id"], old_id)
        self.assertEqual(self.counts(), (2, 2, 0))

    def test_synonym_retry_requires_matching_typed_sense_not_only_display(self):
        payload = {
            "title": "同义替换",
            "rows": [{"word": "join", "part_of_speech": "=", "meaning": "participate"}],
        }
        first = self.save(payload)
        with self.app.app_context():
            word = DictationWord.query.filter_by(book_id=first.json["book"]["id"]).one()
            word.sense_id = None
            db.session.commit()
        retry = self.save(payload)
        self.assertEqual(retry.status_code, 200)
        self.assertFalse(retry.json["reused"])
        self.assertNotEqual(retry.json["book"]["id"], first.json["book"]["id"])
        with self.app.app_context():
            self.assertEqual(VocabularySense.query.count(), 1)

    def test_invalid_synonym_cannot_bypass_preview_or_partially_save(self):
        payload = {
            "title": "坏词表",
            "rows": [*self.payload["rows"], {"word": "join", "part_of_speech": "=", "meaning": ""}],
        }
        self.assertEqual(self.save(payload).status_code, 400)
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_inconsistent_existing_sense_is_not_reused_or_overwritten(self):
        payload = {
            "title": "同义替换",
            "rows": [{"word": "join", "part_of_speech": "=", "meaning": "participate"}],
        }
        self.assertEqual(self.save(payload).status_code, 200)
        with self.app.app_context():
            sense = VocabularySense.query.one()
            sense.definition_en = "conflicting content"
            db.session.commit()
        retry = self.save(payload)
        self.assertEqual(retry.status_code, 400)
        self.assertIn("资料不一致", retry.json["message"])
        self.assertEqual(self.counts(), (1, 1, 0))
        with self.app.app_context():
            self.assertEqual(VocabularySense.query.one().definition_en, "conflicting content")

    def test_synonym_database_failure_also_rolls_back_senses(self):
        payload = {
            "title": "同义替换",
            "rows": [{"word": "join", "part_of_speech": "=", "meaning": "participate"}],
        }
        with self.assertLogs(self.app.logger, level="ERROR"):
            with patch.object(
                db.session, "commit", side_effect=SQLAlchemyError("synthetic failure")
            ):
                self.assertEqual(self.save(payload).status_code, 500)
        self.assertEqual(self.counts(), (0, 0, 0))
        with self.app.app_context():
            self.assertEqual(VocabularySense.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
