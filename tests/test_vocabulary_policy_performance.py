"""C3 structural performance gates: real DBAPI reads, no timing assertions."""

import json
import sqlite3
import unittest
from contextlib import closing
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import event, insert

from models import (
    DictationWord,
    StudentVocabularyMastery,
    User,
    VocabularyErrorQueue,
    VocabularyLearningFlow,
    VocabularyPolicyAllocation,
    VocabularyPolicyEvent,
    VocabularyReviewSession,
    VocabularySense,
    db,
)
from services import vocabulary_autonomous_review as review
from services import vocabulary_error_queue as policy
from services import vocabulary_policy_planning as planning
from services.vocabulary_group_learning import get_vocabulary_group_queue, mark_familiarity_viewed
from services.vocabulary_mastery import ensure_mastery
from tests import test_vocabulary_error_review_integration as fixtures
from tests import test_vocabulary_group_learning as group_fixtures

_measurement = {"active": False, "sql": [], "rows": 0, "writing": False}


class CountingCursor(sqlite3.Cursor):
    def execute(self, sql, *args):
        if _measurement["active"]:
            _measurement["sql"].append(sql)
            if sql.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                _measurement["writing"] = True
        return super().execute(sql, *args)

    def executemany(self, sql, *args):
        if _measurement["active"]:
            _measurement["sql"].append(sql)
            _measurement["writing"] = True
        return super().executemany(sql, *args)

    def fetchone(self):
        row = super().fetchone()
        if _measurement["active"]:
            _measurement["rows"] += int(row is not None)
        return row

    def fetchmany(self, *args):
        rows = super().fetchmany(*args)
        if _measurement["active"]:
            _measurement["rows"] += len(rows)
        return rows

    def fetchall(self):
        rows = super().fetchall()
        if _measurement["active"]:
            _measurement["rows"] += len(rows)
        return rows


class CountingConnection(sqlite3.Connection):
    def cursor(self, *args, **kwargs):
        kwargs["factory"] = CountingCursor
        return super().cursor(*args, **kwargs)


class PolicyPerformanceTest(unittest.TestCase):
    def test_policy_claim_quarantines_representative_reassigned_to_another_sense(self):
        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                words = DictationWord.query.order_by(DictationWord.id).limit(2).all()
                fixture._error(user, words[0])
                original_sense_id = words[0].sense_id
                words[0].sense_id = words[1].sense_id
                db.session.commit()
                db.session.expire_all()

                payload = review.claim_today_review(user, now=fixture.now)
                db.session.commit()
                self.assertTrue(payload["empty"])
                self.assertEqual(VocabularyReviewSession.query.count(), 0)
                self.assertEqual(VocabularyPolicyAllocation.query.count(), 0)
                queue = VocabularyErrorQueue.query.filter_by(
                    student_id=user.id, sense_id=original_sense_id
                ).one()
                self.assertEqual((queue.status, queue.success_count), ("maintenance", 0))
                self.assertEqual(
                    VocabularyPolicyEvent.query.filter_by(
                        queue_id=queue.id, kind="unanswerable"
                    ).count(),
                    1,
                )
                optional_payload, optional_session = fixture._session(user, optional=True)
                self.assertEqual(optional_payload["total_count"], 10)
                self.assertTrue(
                    all(item.sense_id == item.word.sense_id for item in optional_session.items)
                )
                self.assertEqual((queue.status, queue.success_count), ("maintenance", 0))
        finally:
            fixture.tearDown()

    def test_claim_rechecks_selected_synonym_sense_after_preparation(self):
        from services.vocabulary_synonyms import synonym_sense_key

        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                word = DictationWord.query.order_by(DictationWord.id).first()
                word.word = "correct"
                word.sense.part_of_speech = "synonym"
                word.sense.lemma = "correct"
                word.sense.definition_en = "accurate"
                word.sense.canonical_key = synonym_sense_key("correct", "accurate")
                db.session.commit()
                fixture._error(user, word)
                begin = review._begin_claim_outer_transaction

                def change_selected_sense():
                    word.sense.definition_en = "precise"
                    word.sense.canonical_key = synonym_sense_key("correct", "precise")
                    db.session.commit()
                    return begin()

                with patch.object(
                    review, "_begin_claim_outer_transaction", side_effect=change_selected_sense
                ):
                    with self.assertRaises(review.VocabularyAutonomousReviewError) as raised:
                        review.claim_today_review(user, now=fixture.now)
                self.assertEqual(raised.exception.error, "review_claim_changed")
                db.session.rollback()
                self.assertEqual(VocabularyReviewSession.query.count(), 0)
                self.assertEqual(VocabularyPolicyAllocation.query.count(), 0)
                self.assertEqual(word.sense.definition_en, "precise")
        finally:
            fixture.tearDown()

    def test_claim_rechecks_missing_word_book_mastery_goal_after_preparation(self):
        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                word = DictationWord.query.order_by(DictationWord.id).first()
                mastery = StudentVocabularyMastery.query.filter_by(
                    student_id=user.id, sense_id=word.sense_id
                ).one()
                book = mastery.representative_book
                book.default_vocabulary_goal = "listening"
                word.word, word.accepted_answers = "123", None
                word.core_meaning_zh = word.translation = "数字"
                word.book_id = 999999
                db.session.commit()
                db.session.expire_all()
                fixture._error(user, word)
                begin = review._begin_claim_outer_transaction

                def change_effective_book():
                    book.default_vocabulary_goal = "reading"
                    db.session.commit()
                    return begin()

                with patch.object(
                    review, "_begin_claim_outer_transaction", side_effect=change_effective_book
                ):
                    with self.assertRaises(review.VocabularyAutonomousReviewError) as raised:
                        review.claim_today_review(user, now=fixture.now)
                self.assertEqual(raised.exception.error, "review_claim_changed")
                db.session.rollback()
                self.assertEqual(VocabularyReviewSession.query.count(), 0)
                self.assertEqual(VocabularyPolicyAllocation.query.count(), 0)
                self.assertEqual(book.default_vocabulary_goal, "reading")
        finally:
            fixture.tearDown()

    def test_scalar_optional_preserves_missing_book_mastery_goal_fallback(self):
        from services import vocabulary_optional_selection as optional

        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                word = DictationWord.query.order_by(DictationWord.id).first()
                mastery = StudentVocabularyMastery.query.filter_by(
                    student_id=user.id, sense_id=word.sense_id
                ).one()
                mastery.representative_book.default_vocabulary_goal = "listening"
                word.word, word.accepted_answers = "123", None
                word.core_meaning_zh = word.translation = "数字"
                # SQLite legacy deployments can contain a dangling book FK.
                # The existing predicate intentionally falls back to the
                # mastery representative book in this case.
                word.book_id = 999999
                sense_id = word.sense_id
                db.session.commit()
                db.session.expire_all()

                def keys(candidates):
                    return [
                        (item["mastery"].sense_id, item["word"].id, item["dimension"])
                        for item in candidates
                    ]

                expected = keys(review._iter_due_candidates(user, fixture.now))
                actual = keys(
                    optional.iter_candidates(
                        user, fixture.now, blocked=set(), condition=None, catalogs={}
                    )
                )
                self.assertTrue(
                    any(key[0] == sense_id and key[2] == "meaning_recall" for key in expected)
                )
                self.assertEqual(actual, expected)
        finally:
            fixture.tearDown()

    def test_optional_continuation_pages_keep_first_eligible_order(self):
        from services import vocabulary_optional_selection as optional
        from services.vocabulary_policy_planning import optional_mastery_condition

        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                book_id = DictationWord.query.first().book_id
                cohort = policy._cohort(policy.enabled_for(user, fixture.now))
                blocked = set()
                for index in range(140):
                    sense = VocabularySense(canonical_key=f"page-{index}", lemma=f"pageword{index}")
                    db.session.add(sense)
                    db.session.flush()
                    word = DictationWord(
                        book_id=book_id,
                        sense_id=sense.id,
                        sequence=1000 + index,
                        word=f"pageword{index}",
                        translation=f"页词义{index}",
                    )
                    db.session.add(word)
                    db.session.flush()
                    mastery = ensure_mastery(user, word, sense)
                    mastery.meaning_recall_next_due_at = fixture.now - timedelta(days=100)
                    mastery.form_recall_next_due_at = fixture.now - timedelta(days=1)
                    db.session.add(
                        VocabularyErrorQueue(
                            student_id=user.id,
                            sense_id=sense.id,
                            dimension="meaning_recall",
                            cohort_key=cohort,
                            status="active",
                            due_local_date=policy.local_date(fixture.now),
                            opened_at=fixture.now,
                        )
                    )
                    blocked.add((sense.id, "meaning_recall"))
                db.session.commit()
                expected = []
                with closing(review._iter_due_candidates(user, fixture.now)) as old:
                    for item in old:
                        key = (item["mastery"].sense_id, item["dimension"])
                        if key not in blocked:
                            expected.append(key)
                        if len(expected) == 10:
                            break
                condition = optional_mastery_condition(user.id, cohort, fixture.now)
                observed = []
                with patch.object(optional, "_words", wraps=optional._words) as load:
                    with closing(
                        optional.iter_candidates(
                            user, fixture.now, blocked=blocked, condition=condition, catalogs={}
                        )
                    ) as new:
                        for item in new:
                            observed.append((item["mastery"].sense_id, item["dimension"]))
                            if len(observed) == 10:
                                break
                self.assertEqual(observed, expected)
                self.assertEqual(len(load.call_args_list[0].args[0]), 128)
                self.assertEqual(load.call_count, 2)
        finally:
            fixture.tearDown()

    def test_scalar_optional_eligibility_matches_orm_and_source_edits_invalidate_cache(self):
        from services import vocabulary_optional_selection as optional
        from services.vocabulary_synonyms import synonym_sense_key

        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                words = DictationWord.query.order_by(DictationWord.id).all()
                words[0].word = "123"
                words[1].word, words[1].accepted_answers = "correct", '["accurate"]'
                words[2].word = "correct"
                words[2].sense.part_of_speech = "synonym"
                words[2].sense.canonical_key = synonym_sense_key("correct", "accurate")
                words[2].sense.lemma, words[2].sense.definition_en = "correct", "accurate"
                words[3].word, words[3].accepted_answers = "中文", '["word"]'
                for word in words[4:]:
                    word.example_en = f"They use {word.word} in this example."
                    word.example_zh = "例句。"
                    word.usage_pattern = f"use {word.word}"
                db.session.commit()
                for goal in ("reading", "listening"):
                    for word in words:
                        word.book.default_vocabulary_goal = goal
                    db.session.commit()
                    scalars = optional._words({word.id for word in words})
                    for word in words:
                        mastery = StudentVocabularyMastery.query.filter_by(
                            sense_id=word.sense_id
                        ).first()
                        for dimension in sorted(policy.DIMENSIONS):
                            expected = review._candidate_is_eligible(
                                word, mastery, dimension, {}, {}
                            )
                            scalar = scalars[word.id]
                            if dimension == "context_use":
                                catalogs = {}
                                review._candidate_words(scalar, catalogs, prefetch_senses=True)
                                actual = review._candidate_is_eligible(
                                    scalar, mastery, dimension, catalogs, {}
                                )
                            else:
                                actual = optional._simple_eligible(scalar, dimension)
                            self.assertEqual(expected, actual, (word.id, dimension, goal))
                word = words[1]
                self.assertTrue(
                    optional._simple_eligible(optional._words({word.id})[word.id], "form_recall")
                )
                word.translation = word.core_meaning_zh = None
                db.session.commit()
                self.assertFalse(
                    optional._simple_eligible(optional._words({word.id})[word.id], "form_recall")
                )
        finally:
            fixture.tearDown()

    def test_initial_pilot_flow_has_real_writer_before_savepoint_and_rolls_back(self):
        from services import vocabulary_context_catalog as catalog

        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                seen = []
                state = {"writing": False}

                def before_sql(conn, cursor, statement, parameters, context, executemany):
                    if statement.lstrip().upper().startswith("BEGIN IMMEDIATE"):
                        state["writing"] = True
                    if statement.lstrip().upper().startswith("SAVEPOINT"):
                        seen.append(cursor.connection.in_transaction)

                original = catalog.load_question_catalog

                def prepare(*args, **kwargs):
                    self.assertFalse(state["writing"], "flow catalog was hydrated under writer")
                    return original(*args, **kwargs)

                event.listen(db.engine, "before_cursor_execute", before_sql)
                try:
                    with patch.object(
                        catalog, "load_question_catalog", side_effect=prepare
                    ) as load:
                        get_vocabulary_group_queue(user, fixture.task_id, now=fixture.now)
                    self.assertEqual(load.call_count, 1)
                    self.assertTrue(seen)
                    self.assertTrue(all(seen), "SAVEPOINT opened a deferred read→write transaction")
                    self.assertEqual(VocabularyLearningFlow.query.count(), 1)
                    db.session.rollback()
                    self.assertEqual(VocabularyLearningFlow.query.count(), 0)
                finally:
                    event.remove(db.engine, "before_cursor_execute", before_sql)
        finally:
            fixture.tearDown()

    def test_optional_excludes_fully_blocked_senses_without_changing_partial_selection(self):
        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                for word in DictationWord.query.all():
                    fixture._error(user, word)
                with patch.object(
                    review,
                    "_candidate_is_eligible",
                    side_effect=AssertionError("fully blocked old pool was hydrated"),
                ):
                    result = review.claim_today_review(user, now=fixture.now, optional=True)
                    self.assertTrue(result["empty"])
                db.session.commit()
                mastery = StudentVocabularyMastery.query.first()
                mastery.meaning_recall_next_due_at = fixture.now - timedelta(days=30)
                mastery.form_recall_next_due_at = fixture.now - timedelta(days=1)
                db.session.commit()
                # The first eligible ability remains the blocked meaning item.
                # An ability-level SQL filter would wrongly select the form item.
                result = review.claim_today_review(user, now=fixture.now, optional=True)
                self.assertTrue(result["empty"])
                self.assertEqual(VocabularyReviewSession.query.count(), 0)
        finally:
            fixture.tearDown()

    def test_prepared_catalog_preserves_every_question_and_reuses_derived_metadata(self):
        from services import vocabulary_context as context
        from services.vocabulary_context_catalog import PreparedQuestionCatalog

        words = []
        for index in range(120):
            lemma = f"word {chr(97 + index // 26)}{chr(97 + index % 26)}"
            words.append(
                SimpleNamespace(
                    id=index + 1,
                    word=lemma,
                    accepted_answers=lemma + "; other",
                    translation=f"词义{index % 17}",
                    core_meaning_zh=None,
                    example_en=f"They use {lemma} in this example.",
                    example_zh="他们在这里使用这个词。",
                    usage_pattern=f"use {lemma}",
                    sense=SimpleNamespace(
                        part_of_speech="synonym" if index % 11 == 0 else "noun",
                        canonical_key="ordinary",
                    ),
                )
            )
        prepared = PreparedQuestionCatalog(words)
        for word in words[:12]:
            for rotation in range(4):
                for allowed in (
                    None,
                    ["meaning_choice"],
                    ["collocation_choice"],
                    ["example_fill", "collocation_fill"],
                ):
                    with self.subTest(word=word.id, rotation=rotation, allowed=allowed):
                        self.assertEqual(
                            context.build_context_question(
                                word, words, rotation=rotation, allowed_kinds=allowed
                            ),
                            context.build_context_question(
                                word, prepared, rotation=rotation, allowed_kinds=allowed
                            ),
                        )
        with patch.object(context, "_lemma", wraps=context._lemma) as lemma:
            for index in range(20):
                context._stable_candidates(prepared.context_candidates, f"unchanged:{index}")
            self.assertEqual(lemma.call_count, 0)

    def test_projected_catalog_matches_orm_and_observes_catalog_edits(self):
        from services import vocabulary_context_catalog as catalog

        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                words = DictationWord.query.order_by(DictationWord.id).all()
                for index, word in enumerate(words):
                    word.word = f"word {chr(97 + index)}"
                    word.example_en = f"They use {word.word} in this example."
                    word.example_zh = "测试例句。"
                    word.usage_pattern = f"use {word.word}"
                db.session.commit()
                for book_id in {word.book_id for word in words}:
                    projected = catalog.load_question_catalog(book_id)
                    originals = [word for word in words if word.book_id == book_id]
                    for word in originals:
                        for stage in (0, 1, 2, 3):
                            for dimension, goal in (
                                ("context_use", "reading"),
                                ("meaning_recall", "listening"),
                            ):
                                self.assertEqual(
                                    review._question_for(word, dimension, goal, stage, originals),
                                    review._question_for(word, dimension, goal, stage, projected),
                                )
                word = words[0]
                before = catalog._parsed_lemma(word.word, word.accepted_answers)
                word.word = "changed"
                db.session.commit()
                changed = catalog.load_question_catalog(word.book_id)
                metadata = next(
                    row
                    for row in changed.context_candidates.context_metadata
                    if row[0].id == word.id
                )
                self.assertNotEqual(metadata[1], before)
                self.assertEqual(metadata[1], "changed")
        finally:
            fixture.tearDown()

    def test_optional_questions_preserve_legacy_order_with_one_catalog_read_per_book(self):
        from services import vocabulary_context_catalog as catalog

        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                for word in DictationWord.query.all():
                    word.book.default_vocabulary_goal = "listening"
                db.session.commit()
                with closing(review._iter_due_candidates(user, fixture.now)) as candidates:
                    old = []
                    for candidate in candidates:
                        old.extend(review._materialize_due_candidates([candidate], 1))
                        if len(old) == 10:
                            break
                with patch.object(
                    catalog, "load_question_catalog", wraps=catalog.load_question_catalog
                ) as read_catalog:
                    payload, session = fixture._session(user, optional=True)
                self.assertEqual(read_catalog.call_count, len({row["word"].book_id for row in old}))
                self.assertEqual(payload["total_count"], 10)
                for item, expected in zip(session.items, old, strict=True):
                    self.assertEqual(
                        (item.sense_id, item.dimension),
                        (expected["mastery"].sense_id, expected["dimension"]),
                    )
                    actual = json.loads(item.question_snapshot_json)
                    actual.pop("catalog_options_frozen", None)
                    self.assertEqual(actual, expected["public"])
                    self.assertEqual(json.loads(item.answer_payload_json), expected["answer"])
        finally:
            fixture.tearDown()

    def measure(self, label, call, observations):
        _measurement.update(active=True, sql=[], rows=0, writing=False)
        try:
            result = call()
            db.session.commit()
        finally:
            _measurement["active"] = False
        observations.append((label, len(_measurement["sql"]), _measurement["rows"]))
        return result

    def history_case(self, size):
        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        observations = []
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                StudentVocabularyMastery.query.delete(synchronize_session=False)
                if size:
                    db.session.execute(
                        insert(VocabularySense),
                        [
                            {
                                "id": 10000 + n,
                                "canonical_key": f"perf-history-{n}",
                                "lemma": f"old{n}",
                            }
                            for n in range(size)
                        ],
                    )
                    db.session.execute(
                        insert(StudentVocabularyMastery),
                        [
                            {
                                "student_id": user.id,
                                "sense_id": 10000 + n,
                                "meaning_recall_next_due_at": fixture.now - timedelta(days=30),
                            }
                            for n in range(size)
                        ],
                    )
                db.session.commit()
                for index, word in enumerate(
                    DictationWord.query.order_by(DictationWord.id).limit(3)
                ):
                    word.word = ("discover", "support", "improve")[index]
                    word.example_en = f"They {word.word} new ideas."
                    word.example_zh = "他们研究新的想法。"
                    if index == 1:
                        word.book.default_vocabulary_goal = "listening"
                    ensure_mastery(user, word, db.session.get(VocabularySense, word.sense_id))
                    for dimension in sorted(policy.DIMENSIONS):
                        fixture._error(user, word, dimension)

                def record(label, call):
                    return self.measure(label, call, observations)

                record("summary", lambda: review.review_summary(user, now=fixture.now))
                record(
                    "preflight",
                    lambda: review.review_preflight(user, fixture.task_id, now=fixture.now),
                )
                payload = record("claim", lambda: review.claim_today_review(user, now=fixture.now))
                self.assertEqual(payload["total_count"], 12)
                session = db.session.get(VocabularyReviewSession, payload["session_id"])
                record("resume_claim", lambda: review.claim_today_review(user, now=fixture.now))
                with patch.object(
                    review, "utc_naive", side_effect=lambda value=None: value or fixture.now
                ):
                    record(
                        "session_snapshot",
                        lambda: review.get_review_session(user, session.id, session.session_token),
                    )
                items = list(session.items)
                for index, item in enumerate(items):
                    result, answer = record(
                        f"answer:{item.dimension}:{index}",
                        lambda item=item, index=index: fixture._answer(
                            user, session, item, correct=index > 1, forgot=index == 1
                        ),
                    )
                    if index == 0:
                        record(
                            "answer_replay",
                            lambda answer=answer: review.submit_review_answer(
                                user, session.id, answer, now=fixture.now
                            ),
                        )
                        expected = json.loads(item.answer_payload_json)
                        record(
                            "correction",
                            lambda answer=answer, expected=expected: review.submit_review_correction(
                                user,
                                session.id,
                                {
                                    **answer,
                                    "answer": expected.get("answer_option_id")
                                    or expected.get("answer"),
                                    "attempt_id": "perf-correction",
                                },
                                now=fixture.now,
                            ),
                        )
                record("settle", lambda: fixture._settle(user, session))
                record("settle_replay", lambda: fixture._settle(user, session))
                record(
                    "continue_empty",
                    lambda: review.continue_review(
                        user, session.id, session_token=session.session_token, now=fixture.now
                    ),
                )
                record("empty_claim", lambda: review.claim_today_review(user, now=fixture.now))
                queue = record(
                    "task_first_queue",
                    lambda: get_vocabulary_group_queue(user, fixture.task_id, now=fixture.now),
                )
                answer_count = 0
                step = 0
                while not queue["completed"]:
                    step += 1
                    self.assertLess(step, 30)
                    if queue["phase"] == "familiarity":
                        current = next(row for row in queue["familiarity"] if not row["viewed"])
                        queue = record(
                            f"task_view:{step}",
                            lambda queue=queue, current=current: mark_familiarity_viewed(
                                user,
                                fixture.task_id,
                                {
                                    "queue_token": queue["queue_token"],
                                    "word_id": current["word_id"],
                                },
                                now=fixture.now,
                            ),
                        )
                        continue
                    if queue.get("current_question"):
                        response_kind = "forgot" if answer_count == 1 else "answer"
                        result = record(
                            f"task_answer:{queue['phase']}:{step}",
                            lambda queue=queue, answer_count=answer_count, response_kind=response_kind: group_fixtures.VocabularyGroupLearningTest._answer_for_current(
                                fixture,
                                user,
                                fixture.task_id,
                                queue,
                                wrong=answer_count == 0,
                                response_kind=response_kind,
                                now=fixture.now,
                            ),
                        )
                        if result.get("correction_required"):
                            record(
                                f"task_correction:{step}",
                                lambda queue=queue: group_fixtures.VocabularyGroupLearningTest._correct_current(
                                    fixture, user, fixture.task_id, queue, now=fixture.now
                                ),
                            )
                        answer_count += 1
                    queue = record(
                        f"task_next_queue:{step}",
                        lambda: get_vocabulary_group_queue(user, fixture.task_id, now=fixture.now),
                    )
                record("final_summary", lambda: review.review_summary(user, now=fixture.now))
                return observations
        finally:
            fixture.tearDown()

    def test_every_request_sql_and_fetch_are_independent_of_old_history(self):
        connect = sqlite3.dbapi2.connect

        def counted(*args, **kwargs):
            return connect(*args, **dict(kwargs, factory=CountingConnection))

        with patch.object(sqlite3.dbapi2, "connect", side_effect=counted):
            samples = [self.history_case(size) for size in (0, 2400, 10000)]
        self.assertEqual(samples[0], samples[1])
        self.assertEqual(samples[0], samples[2])
        self.assertGreater(len(samples[0]), 25)

    def test_daily_thirty_and_forty_still_claim_at_most_twenty(self):
        for daily_limit, expected_batches in ((30, [20, 10]), (40, [20, 20])):
            fixture = fixtures.ErrorReviewIntegrationTest()
            fixture.setUp()
            try:
                with fixture.app.app_context():
                    user = fixture._enable()
                    fixture.app.config["VOCABULARY_ERROR_REVIEW_DAILY_LIMIT"] = daily_limit
                    for word in DictationWord.query.all():
                        fixture._error(user, word, "meaning_recall")
                        fixture._error(user, word, "form_recall")
                    observed = []
                    for _expected in expected_batches:
                        payload, session = fixture._session(user)
                        observed.append(payload["total_count"])
                        self.assertLessEqual(payload["batch_limit"], 20)
                        fixture._answer_all(session)
                        fixture._settle(user, session)
                    self.assertEqual(observed, expected_batches)
                    self.assertTrue(review.claim_today_review(user, now=fixture.now)["empty"])
                    self.assertEqual(
                        policy.summary(user, now=fixture.now)["mandatory_answered"], daily_limit
                    )
            finally:
                fixture.tearDown()

    def test_large_queue_cleanup_is_bounded_and_planning_never_runs_under_write(self):
        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                for word in DictationWord.query.all():
                    fixture._error(user, word)
                cohort = policy._cohort(policy.enabled_for(user, fixture.now))
                db.session.execute(
                    insert(VocabularySense),
                    [
                        {"id": 10000 + n, "canonical_key": f"new-debt-{n}", "lemma": f"debt{n}"}
                        for n in range(10000)
                    ],
                )
                db.session.execute(
                    insert(VocabularyErrorQueue),
                    [
                        {
                            "student_id": user.id,
                            "sense_id": 10000 + n,
                            "dimension": "meaning_recall",
                            "cohort_key": cohort,
                            "status": "active",
                            "due_local_date": policy.local_date(fixture.now) - timedelta(days=10),
                            "opened_at": fixture.now - timedelta(days=11),
                        }
                        for n in range(10000)
                    ],
                )
                db.session.commit()
                state = {"writing": False}
                loaded_queue_ids = []

                def loaded_queue(row, _context):
                    loaded_queue_ids.append(row.id)

                original = planning.planning

                def before_sql(conn, cursor, statement, parameters, context, executemany):
                    if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                        state["writing"] = True

                def guarded(*args, **kwargs):
                    self.assertFalse(
                        state["writing"], "whole policy planning ran while owning a writer"
                    )
                    return original(*args, **kwargs)

                event.listen(db.engine, "before_cursor_execute", before_sql)
                event.listen(VocabularyErrorQueue, "load", loaded_queue)
                try:
                    with patch.object(planning, "planning", side_effect=guarded):
                        payload, session = fixture._session(user)
                        self.assertEqual(payload["total_count"], 20)
                        self.assertLessEqual(
                            len(loaded_queue_ids), 60, "planning hydrated the large queue"
                        )
                        self.assertEqual(
                            VocabularyErrorQueue.query.filter_by(status="maintenance").count(), 100
                        )
                        self.assertEqual(
                            VocabularyPolicyEvent.query.filter_by(kind="overdue_overload").count(),
                            100,
                        )
                        fixture._answer_all(session)
                        db.session.commit()
                        state["writing"] = False
                        fixture._settle(user, session)
                finally:
                    event.remove(db.engine, "before_cursor_execute", before_sql)
                    event.remove(VocabularyErrorQueue, "load", loaded_queue)
        finally:
            fixture.tearDown()

    def test_catalog_preparation_and_empty_audio_options_never_run_under_writer(self):
        fixture = fixtures.ErrorReviewIntegrationTest()
        fixture.setUp()
        try:
            with fixture.app.app_context():
                user = fixture._enable()
                word = DictationWord.query.first()
                word.book.default_vocabulary_goal = "listening"
                for row in DictationWord.query.filter_by(book_id=word.book_id):
                    row.translation = row.core_meaning_zh = "相同释义"
                fixture._error(user, word)
                db.session.commit()
                state = {"writing": False}

                def before_sql(conn, cursor, statement, parameters, context, executemany):
                    if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                        state["writing"] = True

                original = review._candidate_words

                def catalog(*args, **kwargs):
                    self.assertFalse(state["writing"], "catalog hydration ran under writer")
                    return original(*args, **kwargs)

                event.listen(db.engine, "before_cursor_execute", before_sql)
                try:
                    with (
                        patch.object(review, "_candidate_words", side_effect=catalog),
                        patch(
                            "services.vocabulary_mastery.build_meaning_recall_options",
                            return_value=[],
                        ),
                    ):
                        payload, session = fixture._session(user)
                        self.assertEqual(payload["items"][0]["mode"], "audio_to_zh")
                        self.assertEqual(payload["items"][0]["question"]["options"], [])
                        state["writing"] = False
                        fixture._answer_all(session)
                finally:
                    event.remove(db.engine, "before_cursor_execute", before_sql)
        finally:
            fixture.tearDown()
