import json
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Flask
from sqlalchemy import create_engine, inspect, text

from models import (
    DictationBook,
    DictationWord,
    StudentProfile,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyTaskReview,
    db,
)
from services.vocabulary_context import (
    _collocation_choice,
    _collocation_fill,
    _example_fill,
    _first_collocation_frame,
    _meaning_choice,
    grade_context_answer,
)
from services.vocabulary_mastery import (
    _apply_dimension_answer,
    _refresh_global_mastery,
    default_course_system_for_book_id,
    default_goal_for_book_id,
    dimensions_for_goal,
    ensure_vocabulary_schema,
    finalize_vocabulary_task,
    get_vocabulary_task_queue,
    is_vocabulary_v2_task,
    required_dimensions_long_term,
    submit_vocabulary_answer,
)


class VocabularyMasteryFlowTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="vocabulary-test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="vocabulary_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            student = User(
                username="vocabulary_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add_all([teacher, student])
            db.session.flush()
            profile = StudentProfile(user_id=student.id, full_name="四维学生")
            book = DictationBook(
                title="四维测试词书",
                word_count=4,
                created_by=teacher.id,
                is_active=True,
            )
            db.session.add_all([profile, book])
            db.session.flush()
            words = [
                DictationWord(
                    book_id=book.id,
                    sequence=1,
                    word="depend",
                    translation="依赖",
                    core_meaning_zh="依赖",
                    usage_pattern="depend on",
                    example_en="Students depend on clear feedback every day.",
                    example_zh="学生每天依赖清晰的反馈。",
                ),
                DictationWord(
                    book_id=book.id,
                    sequence=2,
                    word="focus",
                    translation="集中",
                    core_meaning_zh="集中",
                    usage_pattern="focus during class",
                    example_en="Students focus on the main idea during class.",
                    example_zh="学生在课堂上集中于主旨。",
                ),
                DictationWord(
                    book_id=book.id,
                    sequence=3,
                    word="contribute",
                    translation="贡献",
                    core_meaning_zh="贡献",
                    usage_pattern="contribute to",
                    example_en="Students contribute to a useful discussion.",
                    example_zh="学生为有益的讨论作出贡献。",
                ),
                DictationWord(
                    book_id=book.id,
                    sequence=4,
                    word="colour",
                    translation="颜色",
                    core_meaning_zh="颜色",
                    accepted_answers='["color"]',
                ),
            ]
            db.session.add_all(words)
            db.session.commit()
            self.teacher_id = teacher.id
            self.student_id = student.id
            self.book_id = book.id
            self.word_ids = [word.id for word in words]

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _task(self, goal="reading", start=1, end=1):
        task = Task(
            date=date(2026, 8, 7),
            student_name="四维学生",
            category="词汇",
            detail="v2 test",
            created_by=self.teacher_id,
            dictation_book_id=self.book_id,
            vocabulary_goal=goal,
            dictation_mode="audio_to_en",
            dictation_word_start=start,
            dictation_word_end=end,
        )
        db.session.add(task)
        db.session.commit()
        return task

    def test_collocation_choice_normalizes_candidates_and_is_stable(self):
        with self.app.app_context():
            words = DictationWord.query.order_by(DictationWord.id.asc()).all()
            words[0].usage_pattern = "depend on clear feedback"
            words[1].usage_pattern = "focus on the main idea"
            words[2].word = "rely"
            words[2].usage_pattern = "rely upon strong evidence"
            extra = DictationWord(word="count", usage_pattern="count on a teammate")
            candidates = [*words[1:3], extra]
            public_a, answer_a = _collocation_choice(words[0], candidates, "fixed")
            public_b, answer_b = _collocation_choice(words[0], list(reversed(candidates)), "fixed")
            self.assertEqual(public_a, public_b)
            self.assertEqual(answer_a, answer_b)
            self.assertEqual(answer_a["answer_type"], "option_id")
            labels = [option["label"] for option in public_a["options"]]
            self.assertEqual(len(labels), 4)
            self.assertIn("____ on clear feedback", labels)
            self.assertTrue(all("depend" not in label.lower() for label in labels))
            self.assertTrue(all("focus" not in label.lower() for label in labels))
            self.assertEqual(public_a["prompt"]["target_word"], "depend")

    def test_collocation_frame_allows_pure_english_alternation_only(self):
        safe = DictationWord(
            word="data",
            usage_pattern="information/data/measurement analysis",
        )
        unsafe = DictationWord(
            word="data",
            usage_pattern="information/data/measurement 分析",
        )
        self.assertEqual(
            _first_collocation_frame(safe),
            (
                "information/data/measurement analysis",
                "information/____/measurement analysis",
            ),
        )
        self.assertIsNone(_first_collocation_frame(unsafe))

    def test_context_public_snapshot_has_no_answer(self):
        with self.app.app_context():
            word = DictationWord.query.get(self.word_ids[0])
            public, answer = _example_fill(word, "fixed")
            encoded = json.dumps(public, ensure_ascii=False)
            self.assertNotIn("answer", public)
            self.assertNotIn("depend", encoded.lower())
            self.assertEqual(answer["answer"], "depend")
            self.assertEqual(public["prompt"]["translation"], "学生每天依赖清晰的反馈。")
            self.assertEqual(public["prompt"]["translation_label"], "句子翻译")

    def test_context_fill_accepts_teacher_approved_spelling_variant(self):
        with self.app.app_context():
            word = db.session.get(DictationWord, self.word_ids[3])
            word.usage_pattern = "colour palette"
            public, answer = _collocation_fill(word, "fixed")
            self.assertNotIn("colour", json.dumps(public, ensure_ascii=False).lower())
            self.assertEqual(public["prompt"]["translation"], "颜色")
            self.assertEqual(public["prompt"]["translation_label"], "目标词义")
            self.assertTrue(grade_context_answer(public, answer, "color"))

    def test_example_fill_uses_meaning_as_honest_fallback_when_sentence_translation_is_missing(self):
        word = DictationWord(
            word="clarify",
            core_meaning_zh="澄清",
            example_en="Teachers clarify difficult concepts with examples.",
        )
        public, _answer = _example_fill(word, "meaning-fallback")
        self.assertEqual(public["prompt"]["translation"], "澄清")
        self.assertEqual(public["prompt"]["translation_label"], "目标词义")

    def test_context_fill_masks_every_independent_target_occurrence(self):
        word = DictationWord(
            word="action",
            core_meaning_zh="行动",
            example_en="Action guides action teams through action plans.",
            usage_pattern="take action; course of action",
        )

        example_public, _ = _example_fill(word, "repeated")
        collocation_public, _ = _collocation_fill(word, "repeated")

        self.assertNotRegex(
            example_public["prompt"]["sentence"],
            r"(?<![A-Za-z])action(?![A-Za-z])",
        )
        self.assertNotRegex(
            collocation_public["prompt"]["sentence"],
            r"(?<![A-Za-z])action(?![A-Za-z])",
        )
        self.assertEqual(
            collocation_public["prompt"]["sentence"],
            "take ____; course of ____",
        )

    def test_context_rejects_ambiguous_catalog_target_but_accepts_approved_variant(self):
        ambiguous = DictationWord(
            word="teaching/ pedagogical methodology",
            core_meaning_zh="教学法",
            example_en="Teaching methodology shapes classroom practice.",
            usage_pattern="teaching methodology",
        )
        self.assertIsNone(_example_fill(ambiguous, "ambiguous"))
        self.assertIsNone(_collocation_fill(ambiguous, "ambiguous"))
        self.assertIsNone(
            _meaning_choice(
                ambiguous,
                [
                    ambiguous,
                    DictationWord(word="class", core_meaning_zh="课堂"),
                    DictationWord(word="teacher", core_meaning_zh="教师"),
                ],
                "ambiguous",
            )
        )

        approved = DictationWord(
            word="teaching/ pedagogical methodology",
            accepted_answers='["teaching methodology", "pedagogical methodology"]',
            core_meaning_zh="教学法",
            example_en="Teaching methodology shapes classroom practice.",
            usage_pattern="teaching methodology",
        )
        public, answer = _collocation_fill(approved, "approved")
        self.assertNotIn("teaching methodology", public["prompt"]["sentence"].lower())
        self.assertEqual(answer["answer"], "teaching methodology")

        approved.example_en = (
            "Teaching methodology and pedagogical methodology shape classroom practice."
        )
        public, answer = _example_fill(approved, "approved-both")
        prompt = public["prompt"]["sentence"].lower()
        self.assertNotIn("teaching methodology", prompt)
        self.assertNotIn("pedagogical methodology", prompt)

        approved.example_en = "Pedagogical methodology shapes classroom practice."
        public, answer = _example_fill(approved, "approved-second")
        self.assertEqual(answer["answer"], "pedagogical methodology")
        self.assertTrue(grade_context_answer(public, answer, "teaching methodology"))

    def test_meaning_choice_exposes_only_a_safe_canonical_target(self):
        target = DictationWord(
            word="n. assignment",
            core_meaning_zh="作业",
            example_en="Students submit the assignment by Friday.",
        )
        distractor_a = DictationWord(word="elective", core_meaning_zh="选修课")
        distractor_b = DictationWord(word="credit", core_meaning_zh="学分")
        distractor_c = DictationWord(word="evidence", core_meaning_zh="证据")
        public, _ = _meaning_choice(
            target,
            [target, distractor_a, distractor_b, distractor_c],
            "canonical",
        )
        self.assertEqual(public["prompt"]["target_word"], "assignment")

    def test_meaning_choice_has_stable_option_ids_and_server_only_answer(self):
        with self.app.app_context():
            words = DictationWord.query.order_by(DictationWord.id.asc()).all()
            public_a, answer_a = _meaning_choice(words[0], words[1:4], "fixed")
            public_b, answer_b = _meaning_choice(
                words[0],
                list(reversed(words[1:4])),
                "fixed",
            )
            self.assertEqual(public_a, public_b)
            self.assertEqual(answer_a, answer_b)
            self.assertEqual(len(public_a["options"]), 4)
            self.assertNotIn("answer_option_id", public_a)
            self.assertTrue(
                grade_context_answer(
                    public_a,
                    answer_a,
                    answer_a["answer_option_id"],
                )
            )

    def test_defaults_keep_goal_and_course_system_independent(self):
        self.assertEqual(default_goal_for_book_id(2), "listening")
        self.assertEqual(default_goal_for_book_id(40), "reading")
        self.assertIsNone(default_goal_for_book_id(174))
        self.assertEqual(default_goal_for_book_id(188), "writing")
        self.assertEqual(default_course_system_for_book_id(2), "IELTS")
        self.assertEqual(default_course_system_for_book_id(166), "general")
        self.assertIsNone(default_course_system_for_book_id(174))
        self.assertEqual(default_course_system_for_book_id(192), "TOEFL")

    def test_task_creation_does_not_prewarm_non_audio_v2_goals(self):
        source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'vocabulary_goal in {"listening", "comprehensive"}',
            source,
        )

    def test_sense_merge_is_conservative_for_same_spelling(self):
        with self.app.app_context():
            from services.vocabulary_mastery import ensure_word_sense

            same_a = DictationWord(
                book_id=self.book_id,
                sequence=10,
                word="record",
                core_meaning_zh="记录",
                translation="n. 记录；档案",
            )
            same_b = DictationWord(
                book_id=self.book_id,
                sequence=11,
                word="record",
                core_meaning_zh="记录",
                translation="n. 记录；档案",
            )
            different = DictationWord(
                book_id=self.book_id,
                sequence=12,
                word="record",
                core_meaning_zh="记录",
                translation="v. 记录；录制",
            )
            db.session.add_all([same_a, same_b, different])
            db.session.flush()

            sense_a = ensure_word_sense(same_a)
            sense_b = ensure_word_sense(same_b)
            sense_different = ensure_word_sense(different)
            self.assertEqual(sense_a.id, sense_b.id)
            self.assertNotEqual(sense_a.id, sense_different.id)

    def test_incremental_schema_is_idempotent_and_backfills_only_known_books(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE user (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE task (id INTEGER PRIMARY KEY)"))
            connection.execute(
                text("CREATE TABLE dictation_book (id INTEGER PRIMARY KEY)")
            )
            connection.execute(
                text(
                    "CREATE TABLE dictation_word ("
                    "id INTEGER PRIMARY KEY, book_id INTEGER, word VARCHAR(100))"
                )
            )
            connection.execute(
                text("CREATE TABLE dictation_record (id INTEGER PRIMARY KEY)")
            )
            # Simulate a development database created before the SQLite CAS
            # column was added to the group-flow table.
            connection.execute(
                text(
                    "CREATE TABLE vocabulary_learning_flow ("
                    "id INTEGER PRIMARY KEY, student_id INTEGER, task_id INTEGER, "
                    "book_id INTEGER, vocabulary_goal VARCHAR(32), group_size INTEGER, "
                    "total_word_count INTEGER, total_group_count INTEGER, groups_json TEXT, "
                    "started_at DATETIME)"
                )
            )
            connection.execute(
                text("INSERT INTO dictation_book (id) VALUES (2), (40), (174), (188)")
            )

        ensure_vocabulary_schema(engine)
        ensure_vocabulary_schema(engine)

        inspector = inspect(engine)
        self.assertIn("vocabulary_goal", {
            column["name"] for column in inspector.get_columns("task")
        })
        self.assertIn("course_system", {
            column["name"] for column in inspector.get_columns("dictation_book")
        })
        table_names = set(inspector.get_table_names())
        self.assertIn("vocabulary_task_review", table_names)
        self.assertTrue(
            {
                "vocabulary_review_session",
                "vocabulary_review_item",
                "vocabulary_review_attempt",
                "vocabulary_review_settlement",
            }.issubset(table_names)
        )
        index_names = {
            index["name"]
            for table_name in (
                "task",
                "dictation_book",
                "dictation_word",
                "dictation_record",
                "vocabulary_review_attempt",
            )
            for index in inspector.get_indexes(table_name)
        }
        self.assertIn("ix_dictation_word_sense_id", index_names)
        self.assertIn("uq_vocabulary_review_attempt_first", index_names)
        self.assertIn(
            "state_version",
            {
                column["name"]
                for column in inspector.get_columns("vocabulary_learning_flow")
            },
        )
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT id, default_vocabulary_goal, course_system "
                    "FROM dictation_book ORDER BY id"
                )
            ).all()
        self.assertEqual(
            rows,
            [
                (2, "listening", "IELTS"),
                (40, "reading", "TOEFL"),
                (174, None, None),
                (188, "writing", "TOEFL"),
            ],
        )

    def test_schema_adds_vocabulary_record_lookup_and_first_answer_guard(self):
        with self.app.app_context():
            ensure_vocabulary_schema(db.engine)
            indexes = {
                index["name"]: index
                for index in inspect(db.engine).get_indexes("dictation_record")
            }
            self.assertIn("ix_dictation_record_vocabulary_review_first", indexes)
            self.assertTrue(indexes["uq_dictation_record_vocabulary_first"]["unique"])
            review_indexes = {
                index["name"]: index
                for index in inspect(db.engine).get_indexes(
                    "vocabulary_review_attempt"
                )
            }
            self.assertTrue(
                review_indexes["uq_vocabulary_review_attempt_first"]["unique"]
            )

    def test_long_meanings_keep_distinct_sense_keys(self):
        with self.app.app_context():
            from services.vocabulary_mastery import ensure_word_sense

            first = DictationWord(
                book_id=self.book_id,
                sequence=10,
                word="same",
                translation="meaning-" + "a" * 300,
            )
            second = DictationWord(
                book_id=self.book_id,
                sequence=11,
                word="same",
                translation="meaning-" + "b" * 300,
            )
            db.session.add_all([first, second])
            db.session.flush()
            first_sense = ensure_word_sense(first)
            second_sense = ensure_word_sense(second)
            self.assertNotEqual(first_sense.id, second_sense.id)
            self.assertNotEqual(first_sense.canonical_key, second_sense.canonical_key)

    def test_v2_queue_uses_one_dimension_per_sense_and_hides_answer(self):
        with self.app.app_context():
            task = self._task(goal="comprehensive", start=1, end=3)
            queue = get_vocabulary_task_queue(
                db.session.get(User, self.student_id),
                task.id,
                datetime(2026, 8, 7, 9, 0),
            )
            self.assertEqual(queue["task_mode"], "vocabulary_v2")
            self.assertEqual(len(queue["words"]), 3)
            self.assertEqual(len({item["sense_id"] for item in queue["words"]}), 3)
            for item in queue["words"]:
                self.assertNotIn("answer_payload", item)
                self.assertNotIn("answer", item["question"])
                self.assertNotIn("answer_option_id", item["question"])
                self.assertNotIn("revealed_answer", item)
            self.assertEqual(
                VocabularyTaskReview.query.filter_by(task_id=task.id).count(),
                3,
            )

    def test_listening_bootstraps_the_other_recall_dimension_for_next_day(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            now = datetime(2026, 8, 7, 9, 0)
            first_task = self._task(goal="listening", start=1, end=1)
            first_queue = get_vocabulary_task_queue(user, first_task.id, now)
            first_item = first_queue["words"][0]
            answer = "依赖" if first_item["dimension"] == "meaning_recall" else "depend"
            submit_vocabulary_answer(
                user,
                {
                    "task_id": first_task.id,
                    "queue_item_id": first_item["queue_item_id"],
                    "question_id": first_item["question_id"],
                    "word_id": first_item["word_id"],
                    "dimension": first_item["dimension"],
                    "answer": answer,
                    "input_mode": "native",
                    "attempt_id": "bootstrap-listening",
                },
                now=now,
            )
            mastery = StudentVocabularyMastery.query.filter_by(student_id=user.id).one()
            other = (
                "audio_form_recall"
                if first_item["dimension"] == "meaning_recall"
                else "meaning_recall"
            )
            self.assertEqual(getattr(mastery, f"{other}_stage"), 0)
            self.assertEqual(
                getattr(mastery, f"{other}_next_due_at"),
                now + timedelta(days=1),
            )
            self.assertIsNone(mastery.context_use_next_due_at)

            next_task = self._task(goal="listening", start=1, end=1)
            next_queue = get_vocabulary_task_queue(user, next_task.id, now + timedelta(days=1))
            self.assertEqual(next_queue["words"][0]["dimension"], other)

    def test_comprehensive_bootstraps_all_non_context_dimensions(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            now = datetime(2026, 8, 7, 10, 0)
            task = self._task(goal="comprehensive", start=1, end=1)
            queue = get_vocabulary_task_queue(user, task.id, now)
            item = queue["words"][0]
            answer = "依赖" if item["dimension"] == "meaning_recall" else "depend"
            submit_vocabulary_answer(
                user,
                {
                    "task_id": task.id,
                    "queue_item_id": item["queue_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "dimension": item["dimension"],
                    "answer": answer,
                    "input_mode": "native",
                    "attempt_id": "bootstrap-comprehensive",
                },
                now=now,
            )
            mastery = StudentVocabularyMastery.query.filter_by(student_id=user.id).one()
            for dimension in ("meaning_recall", "form_recall", "audio_form_recall"):
                if dimension == item["dimension"]:
                    continue
                self.assertEqual(getattr(mastery, f"{dimension}_stage"), 0)
                self.assertEqual(
                    getattr(mastery, f"{dimension}_next_due_at"),
                    now + timedelta(days=1),
                )
            self.assertEqual(
                mastery.context_use_next_due_at,
                now + timedelta(days=7),
            )

    def test_listening_queue_uses_word_id_tts_when_static_audio_is_missing(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            task = self._task(goal="listening", start=1, end=1)
            queue = get_vocabulary_task_queue(
                user,
                task.id,
                datetime(2026, 8, 7, 9, 30),
            )
            item = queue["words"][0]
            self.assertEqual(item["mode"], "audio_to_zh")
            self.assertEqual(
                item["question"]["prompt"]["audio_tts_url"],
                f"/dictation/words/{item['word_id']}/tts",
            )
            self.assertGreaterEqual(len(item["question"]["options"]), 2)
            self.assertLessEqual(len(item["question"]["options"]), 4)
            self.assertNotIn("word", item["question"]["prompt"])
            self.assertNotIn("audio_us", item["question"]["prompt"])

    def test_due_sense_stays_out_of_teacher_queue_and_is_not_claimed_there(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            word = DictationWord.query.get(self.word_ids[1])
            from services.vocabulary_mastery import ensure_mastery, ensure_word_sense

            sense = ensure_word_sense(word)
            mastery = ensure_mastery(user, word, sense)
            now = datetime(2026, 8, 7, 10, 0)
            mastery.meaning_recall_stage = 2
            mastery.meaning_recall_next_due_at = now - timedelta(minutes=1)
            db.session.commit()

            first = self._task(goal="reading", start=1, end=1)
            first_queue = get_vocabulary_task_queue(user, first.id, now)
            due_items = [item for item in first_queue["words"] if item["word_id"] == word.id]
            self.assertEqual(len(due_items), 0)
            self.assertEqual(first_queue["auto_review_count"], 0)

            second = self._task(goal="reading", start=1, end=1)
            second_queue = get_vocabulary_task_queue(user, second.id, now)
            self.assertNotIn(word.id, [item["word_id"] for item in second_queue["words"]])

    def test_same_day_claim_uses_shanghai_calendar_date(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            task = self._task(goal="reading", start=1, end=1)
            now = datetime(2026, 8, 6, 16, 30)  # 00:30 on Aug 7 in Shanghai
            queue = get_vocabulary_task_queue(user, task.id, now)
            review = VocabularyTaskReview.query.filter_by(task_id=task.id).first()
            self.assertEqual(review.review_date.isoformat(), "2026-08-07")
            self.assertEqual(queue["queue_token"], get_vocabulary_task_queue(user, task.id, now)["queue_token"])

    def test_schedule_wrong_resets_to_tomorrow_and_early_correct_does_not_advance(self):
        with self.app.app_context():
            mastery = StudentVocabularyMastery(
                student_id=self.student_id,
                sense_id=1,
                meaning_recall_stage=2,
                meaning_recall_next_due_at=datetime(2026, 8, 10),
            )
            db.session.add(mastery)
            db.session.flush()
            early = _apply_dimension_answer(
                mastery,
                "meaning_recall",
                True,
                datetime(2026, 8, 8),
            )
            self.assertFalse(early["advanced"])
            self.assertEqual(mastery.meaning_recall_stage, 2)
            wrong_at = datetime(2026, 8, 11, 12, 0)
            wrong = _apply_dimension_answer(mastery, "meaning_recall", False, wrong_at)
            self.assertEqual(wrong["stage"], 0)
            self.assertEqual(mastery.meaning_recall_next_due_at, wrong_at + timedelta(days=1))

    def test_teacher_assigned_early_word_stays_practicable_without_advancing(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            word = db.session.get(DictationWord, self.word_ids[0])
            from services.vocabulary_mastery import ensure_mastery, ensure_word_sense

            sense = ensure_word_sense(word)
            mastery = ensure_mastery(user, word, sense)
            now = datetime(2026, 8, 7, 10, 0)
            mastery.meaning_recall_stage = 2
            mastery.meaning_recall_next_due_at = now + timedelta(days=2)
            # Keep context locked so the explicitly assigned early meaning
            # dimension is the only qualified question.
            mastery.context_use_stage = 0
            mastery.context_use_next_due_at = now + timedelta(days=5)
            db.session.commit()

            task = self._task(goal="reading", start=1, end=1)
            queue = get_vocabulary_task_queue(user, task.id, now)
            self.assertEqual(len(queue["words"]), 1)
            item = queue["words"][0]
            self.assertEqual(item["dimension"], "meaning_recall")
            self.assertEqual(item["source"], "assigned")

            result = submit_vocabulary_answer(
                user,
                {
                    "task_id": task.id,
                    "queue_item_id": item["queue_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "dimension": item["dimension"],
                    "answer": "依赖",
                    "input_mode": "native",
                    "attempt_id": "v2-early-assigned",
                },
                now=now,
            )
            self.assertTrue(result["is_correct"])
            db.session.refresh(mastery)
            self.assertEqual(mastery.meaning_recall_stage, 2)
            self.assertEqual(
                mastery.meaning_recall_next_due_at,
                now + timedelta(days=2),
            )

    def test_global_long_term_requires_all_dimensions_and_failure_preserves_other_timestamps(self):
        with self.app.app_context():
            mastery = StudentVocabularyMastery(
                student_id=self.student_id,
                sense_id=1,
                meaning_recall_stage=6,
                form_recall_stage=6,
                audio_form_recall_stage=6,
                context_use_stage=5,
                meaning_recall_long_term_at=datetime(2026, 7, 1),
                form_recall_long_term_at=datetime(2026, 7, 1),
            )
            db.session.add(mastery)
            db.session.flush()
            _refresh_global_mastery(mastery, datetime(2026, 8, 7))
            self.assertIsNone(mastery.long_term_mastered_at)
            self.assertFalse(required_dimensions_long_term(mastery, "reading"))
            self.assertFalse(required_dimensions_long_term(mastery, "comprehensive"))
            mastery.context_use_stage = 6
            _refresh_global_mastery(mastery, datetime(2026, 8, 7))
            self.assertIsNotNone(mastery.long_term_mastered_at)
            self.assertTrue(required_dimensions_long_term(mastery, "reading"))
            self.assertTrue(required_dimensions_long_term(mastery, "comprehensive"))
            before = mastery.form_recall_long_term_at
            _apply_dimension_answer(mastery, "meaning_recall", False, datetime(2026, 8, 7))
            self.assertIsNone(mastery.meaning_recall_long_term_at)
            self.assertEqual(mastery.form_recall_long_term_at, before)
            self.assertIsNone(mastery.long_term_mastered_at)

    def test_due_teacher_item_does_not_consume_autonomous_schedule(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            word = DictationWord.query.get(self.word_ids[0])
            from services.vocabulary_mastery import ensure_mastery, ensure_word_sense

            sense = ensure_word_sense(word)
            mastery = ensure_mastery(user, word, sense)
            now = datetime(2026, 8, 7, 12, 0)
            mastery.meaning_recall_stage = 1
            mastery.meaning_recall_next_due_at = now - timedelta(days=1)
            db.session.commit()
            task = self._task(goal="reading", start=1, end=1)
            queue = get_vocabulary_task_queue(user, task.id, now)
            item = queue["words"][0]
            self.assertEqual(item["source"], "assigned")
            result = submit_vocabulary_answer(
                user,
                {
                    "task_id": task.id,
                    "queue_item_id": item["queue_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "dimension": item["dimension"],
                    "answer": "依赖",
                    "input_mode": "native",
                    "attempt_id": "v2-due-first",
                },
                now=now,
            )
            self.assertTrue(result["is_correct"])
            db.session.refresh(mastery)
            self.assertEqual(mastery.meaning_recall_stage, 1)
            settled = finalize_vocabulary_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
                now=now,
            )
            db.session.refresh(mastery)
            self.assertEqual(mastery.meaning_recall_stage, 1)
            repeated = finalize_vocabulary_task(
                user,
                task.id,
                {"queue_token": queue["queue_token"]},
                now=now + timedelta(minutes=1),
            )
            self.assertEqual(repeated, settled)

    def test_accepted_english_answer_is_used_for_v2(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            task = self._task(goal="writing", start=4, end=4)
            now = datetime(2026, 8, 7, 13, 0)
            queue = get_vocabulary_task_queue(user, task.id, now)
            item = queue["words"][0]
            self.assertEqual(item["mode"], "zh_to_en")
            result = submit_vocabulary_answer(
                user,
                {
                    "task_id": task.id,
                    "queue_item_id": item["queue_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "dimension": item["dimension"],
                    "answer": "color",
                    "input_mode": "strict",
                    "attempt_id": "v2-accepted-answer",
                },
                now=now,
            )
            self.assertTrue(result["is_correct"])

    def test_context_choice_reveals_correct_label_only_after_submission(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            word = DictationWord.query.get(self.word_ids[0])
            from services.vocabulary_mastery import ensure_mastery, ensure_word_sense

            sense = ensure_word_sense(word)
            mastery = ensure_mastery(user, word, sense)
            mastery.meaning_recall_stage = 6
            mastery.form_recall_stage = 6
            mastery.audio_form_recall_stage = 6
            mastery.meaning_recall_next_due_at = datetime(2026, 8, 20)
            mastery.form_recall_next_due_at = datetime(2026, 8, 20)
            mastery.audio_form_recall_next_due_at = datetime(2026, 8, 20)
            mastery.context_use_stage = 1
            mastery.context_use_next_due_at = datetime(2026, 8, 6)
            db.session.commit()
            task = self._task(goal="comprehensive", start=1, end=1)
            now = datetime(2026, 8, 7, 14, 0)
            queue = get_vocabulary_task_queue(user, task.id, now)
            item = queue["words"][0]
            self.assertEqual(item["mode"], "context_choice")
            self.assertNotIn("answer_option_id", item["question"])
            options = item["question"]["options"]
            answer_payload = json.loads(
                VocabularyTaskReview.query.get(item["queue_item_id"]).answer_payload_json
            )
            correct_option = next(
                option for option in options
                if option["id"] == answer_payload["answer_option_id"]
            )
            wrong = next(option for option in options if option["id"] != correct_option["id"])
            result = submit_vocabulary_answer(
                user,
                {
                    "task_id": task.id,
                    "queue_item_id": item["queue_item_id"],
                    "question_id": item["question_id"],
                    "word_id": item["word_id"],
                    "dimension": "context_use",
                    "answer": wrong["id"],
                    "input_mode": "native",
                    "attempt_id": "v2-context-wrong",
                },
                now=now,
            )
            self.assertFalse(result["is_correct"])
            self.assertTrue(result["revealed_answer"])
            self.assertEqual(result["revealed_answer"], correct_option["label"])
            self.assertEqual(result["revealed_answer_option_id"], correct_option["id"])
            refreshed = get_vocabulary_task_queue(user, task.id, now)
            refreshed_item = refreshed["words"][0]
            self.assertEqual(refreshed_item["revealed_answer"], correct_option["label"])
            self.assertEqual(
                refreshed_item["revealed_answer_option_id"], correct_option["id"]
            )

    def test_old_task_remains_legacy_and_no_double_graduation(self):
        with self.app.app_context():
            old = self._task(goal=None)
            self.assertFalse(is_vocabulary_v2_task(old))
            mastery = StudentVocabularyMastery(
                student_id=self.student_id,
                sense_id=1,
                meaning_recall_stage=6,
            )
            db.session.add(mastery)
            db.session.flush()
            _apply_dimension_answer(mastery, "meaning_recall", True, datetime(2026, 8, 7))
            self.assertEqual(mastery.meaning_recall_stage, 6)

    def test_full_book_queue_does_not_silently_stop_at_four_hundred(self):
        def letters(number):
            value = ""
            while number:
                number, remainder = divmod(number - 1, 26)
                value = chr(97 + remainder) + value
            return value or "a"

        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            book = DictationBook(
                title="超过四百词的真实规模词书",
                word_count=405,
                created_by=self.teacher_id,
                is_active=True,
            )
            db.session.add(book)
            db.session.flush()
            db.session.add_all(
                DictationWord(
                    book_id=book.id,
                    sequence=index,
                    word=f"bulk{letters(index)}",
                    translation=f"批量释义{index}",
                    core_meaning_zh=f"批量释义{index}",
                )
                for index in range(1, 406)
            )
            task = Task(
                date=date(2026, 8, 8),
                student_name="四维学生",
                category="词汇",
                detail="完整词书不截断",
                created_by=self.teacher_id,
                dictation_book_id=book.id,
                vocabulary_goal="reading",
                dictation_word_start=1,
                dictation_word_end=405,
            )
            db.session.add(task)
            db.session.commit()

            queue = get_vocabulary_task_queue(
                user,
                task.id,
                datetime(2026, 8, 8, 9, 0),
            )
            self.assertEqual(queue["assigned_count"], 405)
            self.assertEqual(queue["total_count"], 405)


if __name__ == "__main__":
    unittest.main()
