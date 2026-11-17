"""Exact legacy optional order with scalar eligibility before ORM hydration.

Blocked first-eligible abilities still consume the sense's position; they do
not allow a later ability to jump the legacy order. Only candidates that can
actually be returned are materialized as mastery/word ORM entities.
"""

from collections import namedtuple
from contextlib import closing
from functools import lru_cache
from types import SimpleNamespace

from sqlalchemy.orm import joinedload

from models import DictationBook, DictationWord, StudentVocabularyMastery, VocabularySense, db
from services.vocabulary_review_selection import due_metadata_pages

ScalarBook = namedtuple("ScalarBook", "default_vocabulary_goal")
ScalarSense = namedtuple("ScalarSense", "id canonical_key lemma part_of_speech definition_en")
ScalarWord = namedtuple(
    "ScalarWord",
    "id book_id sense_id word accepted_answers core_meaning_zh translation example_en example_zh usage_pattern book sense",
)


def _words(word_ids):
    if not word_ids:
        return {}
    word, sense, book = DictationWord, VocabularySense, DictationBook
    rows = (
        db.session.query(
            word.id,
            word.book_id,
            word.sense_id,
            word.word,
            word.accepted_answers,
            word.core_meaning_zh,
            word.translation,
            word.example_en,
            word.example_zh,
            word.usage_pattern,
            book.default_vocabulary_goal,
            sense.id,
            sense.canonical_key,
            sense.lemma,
            sense.part_of_speech,
            sense.definition_en,
            book.id,
        )
        .outerjoin(book, book.id == word.book_id)
        .outerjoin(sense, sense.id == word.sense_id)
        .filter(word.id.in_(word_ids))
        .all()
    )
    return {
        row[0]: ScalarWord(
            *row[:10],
            ScalarBook(row[10]) if row[16] is not None else None,
            ScalarSense(*row[11:16]) if row[11] is not None else None,
        )
        for row in rows
    }


@lru_cache(maxsize=16384)
def _simple_eligible(word, dimension):
    """Cache only a pure eligibility decision whose entire input is in the key."""
    from services import vocabulary_autonomous_review as legacy

    return legacy._candidate_is_eligible(word, None, dimension, {}, {})


def iter_candidates(user, now, *, blocked, condition, catalogs):
    from services import vocabulary_autonomous_review as legacy

    seen, context_choices = set(), {}
    # Keep normal finite claims small; continuing an empty/blocked scan uses
    # bounded larger scalar pages to amortize projection SQL. No truncation.
    with closing(
        due_metadata_pages(
            user.id,
            now,
            page_size=128,
            subsequent_page_size=1024,
            extra_mastery_condition=condition,
        )
    ) as pages:
        for rows in pages:
            words = _words({row.word_id for row in rows if row.sense_id not in seen})
            missing_book = {
                row.mastery_id
                for row in rows
                if row.word_id in words and words[row.word_id].book is None
            }
            fallback_goals = (
                dict(
                    db.session.query(
                        StudentVocabularyMastery.id, DictationBook.default_vocabulary_goal
                    )
                    .outerjoin(
                        DictationBook,
                        DictationBook.id == StudentVocabularyMastery.representative_book_id,
                    )
                    .filter(StudentVocabularyMastery.id.in_(missing_book))
                    .all()
                )
                if missing_book
                else {}
            )
            for row in rows:
                if row.sense_id in seen:
                    continue
                word = words.get(row.word_id)
                if word is None or word.sense_id != row.sense_id:
                    continue
                if word.book is None:
                    # The legacy helper falls back to the mastery's book when
                    # a damaged/orphan catalog row has lost its own book.
                    word = word._replace(book=ScalarBook(fallback_goals.get(row.mastery_id)))
                if row.dimension == "context_use":
                    legacy._candidate_words(word, catalogs, prefetch_senses=True)
                    proxy = SimpleNamespace(context_use_stage=row.stage)
                    eligible = legacy._candidate_is_eligible(
                        word, proxy, row.dimension, catalogs, context_choices
                    )
                else:
                    eligible = _simple_eligible(
                        word._replace(example_en=None, example_zh=None, usage_pattern=None),
                        row.dimension,
                    )
                if not eligible:
                    continue
                seen.add(row.sense_id)
                if (row.sense_id, row.dimension) in blocked:
                    continue
                mastery = (
                    StudentVocabularyMastery.query.filter_by(id=row.mastery_id)
                    .populate_existing()
                    .first()
                )
                original = (
                    DictationWord.query.options(joinedload(DictationWord.book))
                    .filter_by(id=row.word_id)
                    .populate_existing()
                    .first()
                )
                if (
                    mastery is not None
                    and original is not None
                    and original.sense_id == mastery.sense_id
                ):
                    yield {
                        "mastery": mastery,
                        "word": original,
                        "dimension": row.dimension,
                        "due_at": row.due_at,
                        "stage": row.stage,
                    }
