"""Explicit classroom synonym pairs using the existing recall snapshot contract.

Explicit sense metadata, rather than a display-string prefix, identifies this
material.  ``context_fill`` is the existing client's free English response
renderer; the mastery dimension remains meaning/form recall.
"""

from __future__ import annotations

import hashlib

from dictation_answers import canonical_vocabulary_word

SYNONYM_SENSE_PREFIX = "classroom-synonym:v1:"
SYNONYM_SENSE_POS = "synonym"


def synonym_sense_key(left, right):
    pair = f"{canonical_vocabulary_word(left)}\x1f{canonical_vocabulary_word(right)}"
    return SYNONYM_SENSE_PREFIX + hashlib.sha256(pair.encode("utf-8")).hexdigest()


def is_synonym_word(word):
    sense = getattr(word, "sense", None)
    # Either marker preserves the intent if the other field was damaged.
    # The builder requires both plus the complete pair hash before grading.
    return bool(
        sense
        and (
            getattr(sense, "part_of_speech", None) == SYNONYM_SENSE_POS
            or str(getattr(sense, "canonical_key", "")).startswith(SYNONYM_SENSE_PREFIX)
        )
    )


def build_synonym_question(word, dimension, stage=0):
    if not is_synonym_word(word) or dimension not in {"meaning_recall", "form_recall"}:
        return None
    sense = word.sense
    left = str(sense.lemma or "").strip()
    right = str(sense.definition_en or "").strip()
    if (
        not left
        or not right
        or sense.part_of_speech != SYNONYM_SENSE_POS
        or sense.canonical_key != synonym_sense_key(left, right)
        or not canonical_vocabulary_word(left)
        or not canonical_vocabulary_word(right)
        or canonical_vocabulary_word(word.word) != canonical_vocabulary_word(left)
    ):
        return None
    cue, answer = (left, right) if dimension == "meaning_recall" else (right, left)
    seed = f"{word.id}:{sense.canonical_key}:{dimension}:{stage}"
    return (
        {
            "question_id": "synonym_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24],
            "dimension": dimension,
            "kind": "synonym_recall",
            "mode": "context_fill",
            "prompt": {
                "instruction": "填写课堂词表中的同义词或词组",
                "sentence": f"{cue} = ____",
            },
            "options": [],
            "answer_type": "english",
            "input_mode": "native",
        },
        {
            "answer": canonical_vocabulary_word(answer),
            "accepted_answers": [],
            "answer_type": "english",
        },
    )
