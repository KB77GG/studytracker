"""Immutable derived context metadata, retained only for one pilot request.

The original rows remain available to other builders. Context builders use the
same ordered rows and hash suffixes as before, without parsing each row again
for every question. Never put this object in a process-wide cache. Only the
pure string parser is bounded-cached across requests; its key contains both
source strings, so catalog edits cannot reuse an obsolete result.
"""

from collections import namedtuple
from functools import lru_cache

from dictation_answers import parse_vocabulary_word_variants


@lru_cache(maxsize=16384)
def _parsed_lemma(word_text, accepted_answers):
    variants = parse_vocabulary_word_variants(word_text)
    if not variants:
        variants = parse_vocabulary_word_variants(accepted_answers, allow_approved_delimiters=True)
    return (variants or [""])[0]


CatalogSense = namedtuple("CatalogSense", "part_of_speech canonical_key")
CatalogWord = namedtuple(
    "CatalogWord",
    "id sense_id word accepted_answers translation core_meaning_zh usage_pattern sense",
)


def load_question_catalog(book_id):
    """Read only immutable distractor inputs, not thousands of ORM entities."""
    from models import DictationWord as Word
    from models import VocabularySense as Sense
    from models import db

    rows = (
        db.session.query(
            Word.id,
            Word.sense_id,
            Word.word,
            Word.accepted_answers,
            Word.translation,
            Word.core_meaning_zh,
            Word.usage_pattern,
            Sense.id,
            Sense.part_of_speech,
            Sense.canonical_key,
        )
        .outerjoin(Sense, Sense.id == Word.sense_id)
        .filter(Word.book_id == book_id)
        .order_by(Word.id)
        .all()
    )
    return PreparedQuestionCatalog(
        [
            CatalogWord(*row[:7], CatalogSense(*row[8:]) if row[7] is not None else None)
            for row in rows
        ]
    )


class PreparedContextCandidates(list):
    def __init__(self, rows, metadata):
        super().__init__(rows)
        self.context_metadata = metadata


class PreparedQuestionCatalog(list):
    def __init__(self, candidates):
        from services.vocabulary_context import _meaning
        from services.vocabulary_synonyms import is_synonym_word

        super().__init__(candidates)
        rows = []
        for candidate in candidates:
            if is_synonym_word(candidate):
                continue
            lemma = _parsed_lemma(
                getattr(candidate, "word", None), getattr(candidate, "accepted_answers", None)
            )
            meaning = _meaning(candidate)
            rows.append(
                (candidate, lemma, meaning, f"{getattr(candidate, 'id', '')}|{lemma}|{meaning}")
            )
        self.context_candidates = PreparedContextCandidates([row[0] for row in rows], rows)
