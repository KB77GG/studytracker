"""Deterministic, server-owned context-use question generation.

This module deliberately uses only structured fields already attached to a
DictationWord. It never calls an LLM, samples random distractors, or sends the
answer-bearing snapshot to the client. A caller stores the returned ``public``
and ``answer`` objects separately and grades against the latter.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from dictation_answers import parse_vocabulary_word_variants

_WORD_BOUNDARY = r"(?<![A-Za-z]){target}(?![A-Za-z])"
_COLLOCATION_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*'?$")
_COLLOCATION_ALT_TOKEN_RE = re.compile(
    r"[A-Za-z]+(?:['-][A-Za-z]+)*'?"
    r"(?:/[A-Za-z]+(?:['-][A-Za-z]+)*'?)+$"
)


def _text(value) -> str:
    return " ".join(str(value or "").split()).strip()


def _meaning(word) -> str:
    return _text(getattr(word, "core_meaning_zh", None) or getattr(word, "translation", None))


def _lemma(word) -> str:
    return (_lemma_variants(word) or [""])[0]


def _lemma_variants(word) -> list[str]:
    variants = parse_vocabulary_word_variants(getattr(word, "word", None))
    if variants:
        return variants
    return parse_vocabulary_word_variants(
        getattr(word, "accepted_answers", None),
        allow_approved_delimiters=True,
    )


def _answer_variants(word) -> list[str]:
    variants = _lemma_variants(word)
    seen = set(variants)
    for variant in parse_vocabulary_word_variants(
        getattr(word, "accepted_answers", None),
        allow_approved_delimiters=True,
    ):
        if variant not in seen:
            variants.append(variant)
            seen.add(variant)
    return variants


def _accepted_answers(word, answer: str | None = None) -> list[str]:
    selected = answer or _lemma(word)
    return [variant for variant in _answer_variants(word) if variant != selected]


def _replace_word(sentence: str, word: str, replacement: str) -> str | None:
    if not sentence or not word:
        return None
    pattern = re.compile(_WORD_BOUNDARY.format(target=re.escape(word)), re.IGNORECASE)
    if not pattern.search(sentence):
        return None
    return pattern.sub(replacement, sentence, count=1)


def _replace_all_words(sentence: str, word: str, replacement: str) -> str | None:
    """Replace every independent occurrence of ``word`` in a fill prompt."""

    if not sentence or not word:
        return None
    pattern = re.compile(_WORD_BOUNDARY.format(target=re.escape(word)), re.IGNORECASE)
    if not pattern.search(sentence):
        return None
    return pattern.sub(replacement, sentence)


def _replace_first_matching_variant(text: str, word, replacement: str):
    for variant in _lemma_variants(word):
        replaced = _replace_word(text, variant, replacement)
        if replaced is not None:
            return variant, replaced
    return None, None


def _replace_all_matching_variant(text: str, word, replacement: str):
    matched = None
    result = text
    # Longest first avoids a short approved variant consuming part of a
    # longer phrase. Every teacher-approved form is then masked so a prompt
    # containing two accepted variants cannot reveal the second answer.
    for variant in sorted(_lemma_variants(word), key=len, reverse=True):
        replaced = _replace_all_words(result, variant, replacement)
        if replaced is None:
            continue
        matched = matched or variant
        result = replaced
    return (matched, result) if matched else (None, None)


def _first_collocation_frame(word):
    """Return the first short, standalone-English usage frame for a word."""

    phrase = _text(getattr(word, "usage_pattern", None))
    if not phrase or len(phrase) > 100:
        return None
    for raw_fragment in re.split(r"[;；\n]+", phrase):
        fragment = _text(raw_fragment)
        fragment = (
            fragment.replace("’", "'")
            .replace("‘", "'")
            .replace("‐", "-")
            .replace("‑", "-")
            .replace("–", "-")
            .replace("—", "-")
        )
        fragment = re.sub(r"\s*/\s*", "/", fragment)
        if not fragment or len(fragment) > 80 or len(fragment.split()) > 12:
            continue
        if any(
            not (
                _COLLOCATION_TOKEN_RE.fullmatch(token)
                or _COLLOCATION_ALT_TOKEN_RE.fullmatch(token)
            )
            for token in fragment.split()
        ):
            continue
        for variant in _lemma_variants(word):
            masked = _replace_all_words(fragment, variant, "____")
            if masked is not None and masked != fragment:
                return fragment, masked
    return None


def _stable_id(seed: str, prefix: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _options(labels: Iterable[str], seed: str):
    clean = []
    seen = set()
    for label in labels:
        label = _text(label)
        if not label or label in seen:
            continue
        seen.add(label)
        clean.append(label)
    clean.sort(key=lambda label: hashlib.sha256(f"{seed}|{label}".encode()).hexdigest())
    result = []
    for index, label in enumerate(clean):
        result.append(
            {
                "id": _stable_id(f"{seed}|{index}|{label}", "option"),
                "label": label,
            }
        )
    return result


def _stable_candidates(candidates, seed: str):
    """Sort candidate rows before slicing so DB row order cannot alter a snapshot."""

    return sorted(
        list(candidates or []),
        key=lambda candidate: hashlib.sha256(
            f"{seed}|{getattr(candidate, 'id', '')}|{_lemma(candidate)}|{_meaning(candidate)}".encode()
        ).hexdigest(),
    )


def _public_question(question_id, kind, prompt, *, options=None, input_mode=None):
    payload = {
        "question_id": question_id,
        "kind": kind,
        "prompt": prompt,
    }
    if options is not None:
        payload["options"] = options
        payload["answer_type"] = "option_id"
        payload["mode"] = "context_choice"
    else:
        payload["options"] = []
        payload["answer_type"] = "english_strict"
        payload["mode"] = "context_fill"
        payload["input_mode"] = input_mode or "strict"
    return payload


def _example_fill(word, seed):
    sentence = _text(getattr(word, "example_en", None))
    lemma = _lemma(word)
    matched_lemma, masked = _replace_all_matching_variant(sentence, word, "____")
    if not masked or len(sentence) < 12:
        return None
    question_id = _stable_id(f"{seed}|example_fill|{sentence}", "context")
    sentence_translation = _text(getattr(word, "example_zh", None))
    supporting_chinese = sentence_translation or _meaning(word)
    if not supporting_chinese:
        return None
    public = _public_question(
        question_id,
        "example_fill",
        {
            "sentence": masked,
            "translation": supporting_chinese,
            "translation_label": "句子翻译" if sentence_translation else "目标词义",
            "instruction": "根据例句填写目标词",
        },
    )
    return public, {
        "answer": matched_lemma or lemma,
        "accepted_answers": _accepted_answers(word, matched_lemma or lemma),
        "answer_type": "english_strict",
    }


def _collocation_fill(word, seed):
    phrase = _text(getattr(word, "usage_pattern", None))
    lemma = _lemma(word)
    meaning = _meaning(word)
    if not phrase or not lemma or not meaning:
        return None
    # Only accept patterns that visibly contain the target. A pre-existing
    # generic blank may refer to some other slot and is not safe to grade as
    # the target word without an explicit authoring contract.
    matched_lemma, masked = _replace_all_matching_variant(phrase, word, "____")
    if not masked or masked == phrase:
        return None
    question_id = _stable_id(f"{seed}|collocation_fill|{phrase}", "context")
    public = _public_question(
        question_id,
        "collocation_fill",
        {
            "sentence": masked,
            "translation": meaning,
            "translation_label": "目标词义",
            "instruction": "根据搭配补全目标词",
        },
    )
    return public, {
        "answer": matched_lemma or lemma,
        "accepted_answers": _accepted_answers(word, matched_lemma or lemma),
        "answer_type": "english_strict",
    }


def _meaning_choice(word, candidates, seed):
    sentence = _text(getattr(word, "example_en", None))
    meaning = _meaning(word)
    if not sentence or not meaning or not _lemma(word) or len(sentence) < 12:
        return None
    distractors = []
    for candidate in _stable_candidates(candidates, f"{seed}|meaning_distractors"):
        if candidate is word:
            continue
        candidate_meaning = _meaning(candidate)
        if candidate_meaning and candidate_meaning != meaning:
            distractors.append(candidate_meaning)
    option_values = _options([meaning, *distractors[:3]], f"{seed}|meaning_choice")
    if len(option_values) < 4:
        return None
    correct = next(option for option in option_values if option["label"] == meaning)
    question_id = _stable_id(
        f"{seed}|meaning_choice|{sentence}|{meaning}|{','.join(o['id'] for o in option_values)}",
        "context",
    )
    public = _public_question(
        question_id,
        "meaning_choice",
        {
            "sentence": sentence,
            "target_word": _lemma(word),
            "instruction": "根据句意选择目标词在此处的正确词义",
        },
        options=option_values,
    )
    return public, {"answer_option_id": correct["id"], "answer_type": "option_id"}


def _collocation_choice(word, candidates, seed):
    lemma = _lemma(word)
    target_frame = _first_collocation_frame(word)
    if not lemma or not target_frame:
        return None
    phrase, masked_target = target_frame
    distractor_frames = []
    seen_frames = set()
    for candidate in _stable_candidates(candidates, f"{seed}|collocation_distractors"):
        candidate_lemma = _lemma(candidate)
        frame = _first_collocation_frame(candidate)
        if (
            not candidate_lemma
            or candidate_lemma.lower() == lemma.lower()
            or not frame
        ):
            continue
        _candidate_phrase, masked_candidate = frame
        if masked_candidate != masked_target and masked_candidate not in seen_frames:
            distractor_frames.append(masked_candidate)
            seen_frames.add(masked_candidate)
            if len(distractor_frames) == 3:
                break
    # Four complete masked frames are required. If the catalog cannot provide
    # three distinct real distractors, disable this question instead of
    # manufacturing semantically invalid combinations.
    option_values = _options(
        [masked_target, *distractor_frames], f"{seed}|collocation_choice"
    )
    if len(option_values) != 4:
        return None
    correct = next(option for option in option_values if option["label"] == masked_target)
    question_id = _stable_id(
        f"{seed}|collocation_choice|{lemma}|{masked_target}|{','.join(o['id'] for o in option_values)}",
        "context",
    )
    public = _public_question(
        question_id,
        "collocation_choice",
        {
            "target_word": lemma,
            "instruction": "选择本词书收录的目标搭配",
        },
        options=option_values,
    )
    return public, {"answer_option_id": correct["id"], "answer_type": "option_id"}


def build_context_question(
    word,
    candidates=None,
    *,
    seed: str | None = None,
    rotation: int = 0,
    allowed_kinds: Iterable[str] | None = None,
):
    """Return ``(public_snapshot, answer_snapshot)`` or ``None``.

    The order is deterministic but rotates between qualified question types so
    a word with several reliable materials does not always show the same form.
    """

    candidates = list(candidates or [])
    seed = seed or f"word:{getattr(word, 'id', '')}"
    builder_specs = (
        ("example_fill", lambda: _example_fill(word, seed)),
        ("collocation_fill", lambda: _collocation_fill(word, seed)),
        ("meaning_choice", lambda: _meaning_choice(word, candidates, seed)),
        ("collocation_choice", lambda: _collocation_choice(word, candidates, seed)),
    )
    allowed = {str(kind).strip() for kind in (allowed_kinds or ()) if str(kind).strip()}
    builders = tuple(
        builder for kind, builder in builder_specs if not allowed or kind in allowed
    )
    if not builders:
        return None
    start = (int(rotation or 0) + int(getattr(word, "id", 0) or 0)) % len(builders)
    for offset in range(len(builders)):
        result = builders[(start + offset) % len(builders)]()
        if result:
            return result
    return None


def grade_context_answer(public_snapshot: dict, answer_snapshot: dict, answer: str) -> bool:
    """Grade only against the frozen server answer contract."""

    answer = _text(answer)
    if answer_snapshot.get("answer_type") == "option_id":
        return answer == str(answer_snapshot.get("answer_option_id") or "")
    from dictation_answers import is_english_answer_correct

    return is_english_answer_correct(
        answer,
        answer_snapshot.get("answer") or "",
        accepted_answers=answer_snapshot.get("accepted_answers") or [],
    )
