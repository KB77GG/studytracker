"""Pure text helpers: word counting, sentence splitting and band arithmetic."""

from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass

WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*")
MIN_WORDS = {"task1": 150, "task2": 250}
TASK_LABELS = {"task1": "Academic Task 1", "task2": "Task 2"}
CRITERIA = ("task", "coherence", "lexical", "grammar")
CRITERION_LABELS = {
    "task1": {
        "task": "Task Achievement",
        "coherence": "Coherence & Cohesion",
        "lexical": "Lexical Resource",
        "grammar": "Grammatical Range & Accuracy",
    },
    "task2": {
        "task": "Task Response",
        "coherence": "Coherence & Cohesion",
        "lexical": "Lexical Resource",
        "grammar": "Grammatical Range & Accuracy",
    },
}
CRITERION_SHORT = {
    "task1": {"task": "TA", "coherence": "CC", "lexical": "LR", "grammar": "GRA"},
    "task2": {"task": "TR", "coherence": "CC", "lexical": "LR", "grammar": "GRA"},
}

# Tokens ending in "." that do not end a sentence.
ABBREVIATIONS = {
    "e.g",
    "i.e",
    "etc",
    "vs",
    "mr",
    "mrs",
    "ms",
    "dr",
    "prof",
    "approx",
    "no",
    "st",
    "u.s",
    "u.k",
    "a.m",
    "p.m",
    "fig",
    "cf",
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "sept",
    "oct",
    "nov",
    "dec",
}
BOUNDARY_RE = re.compile(r"[.!?]+[\"'”’)\]]*(?=\s)")


@dataclass(frozen=True)
class Sentence:
    index: int
    paragraph: int
    text: str


def count_words(text: str | None) -> int:
    return len(WORD_RE.findall(text or ""))


def normalize_newlines(text: str | None) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def split_paragraphs(text: str | None) -> list[str]:
    """Each non-empty line is a paragraph: students separate paragraphs with
    either one newline or a blank line, and IELTS essays never wrap lines."""
    return [line.strip() for line in normalize_newlines(text).split("\n") if line.strip()]


def _is_abbreviation(paragraph: str, end: int) -> bool:
    """True if the '.' run ending at ``end`` belongs to an abbreviation/initial."""
    start = end
    while start > 0 and not paragraph[start - 1].isspace():
        start -= 1
    raw = paragraph[start:end].strip("\"'“‘([").rstrip(".")
    if not raw:
        return False
    if raw.lower() in ABBREVIATIONS:
        return True
    # Uppercase single-letter initials such as "J." in "J. Smith".
    return len(raw) == 1 and raw.isupper() and raw not in {"A", "I"}


def split_sentences(text: str | None) -> list[Sentence]:
    sentences: list[Sentence] = []
    for p_index, paragraph in enumerate(split_paragraphs(text)):
        cursor = 0
        for match in BOUNDARY_RE.finditer(paragraph):
            punct_end = match.start() + len(match.group(0).rstrip("\"'”’)]"))
            if paragraph[match.start()] == "." and _is_abbreviation(paragraph, punct_end - 1):
                continue
            piece = paragraph[cursor : match.end()].strip()
            if piece:
                sentences.append(Sentence(len(sentences), p_index, piece))
            cursor = match.end()
        tail = paragraph[cursor:].strip()
        if tail:
            sentences.append(Sentence(len(sentences), p_index, tail))
    return sentences


def join_sentences(sentences: list[Sentence], texts: list[str] | None = None) -> str:
    """Rebuild an essay from sentences, one paragraph per line with a blank line between."""
    paragraphs: dict[int, list[str]] = {}
    for position, sentence in enumerate(sentences):
        value = texts[position] if texts is not None else sentence.text
        paragraphs.setdefault(sentence.paragraph, []).append(value.strip())
    return "\n\n".join(
        " ".join(part for part in parts if part) for _, parts in sorted(paragraphs.items())
    )


def squash(text: str | None) -> str:
    """Comparison form: unify quotes/dashes/whitespace and case."""
    value = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    value = value.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", value).strip().lower()


def same_text(a: str | None, b: str | None) -> bool:
    """Equal apart from whitespace and quote/dash styles; case-sensitive, so a
    capitalisation fix (i -> I) still counts as a change."""

    def norm(value):
        value = (
            (value or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
        )
        return re.sub(r"\s+", " ", value.replace("—", "-").replace("–", "-")).strip()

    return norm(a) == norm(b)


def contains_quote(essay: str, quote: str) -> bool:
    """Locate a quote leniently (case/whitespace/quote style) - used for evidence."""
    needle = squash(quote).strip(" .,;:!?\"'")
    return bool(needle) and needle in squash(essay)


def _exact_form(text: str | None) -> str:
    value = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    value = value.replace("—", "-").replace("–", "-")
    return re.sub(r"\s+", " ", value).strip()


def contains_exact(essay: str, fragment: str) -> bool:
    """Case-sensitive containment (whitespace/quote style only normalised) - used for
    claims about what a rewrite now says, where "i" vs "I" matters."""
    return count_exact(essay, fragment) > 0


def count_exact(essay: str, fragment: str) -> int:
    """Case-sensitive, non-overlapping occurrences of ``fragment`` in ``essay``."""
    needle = _exact_form(fragment).strip(" .,;:!?\"'")
    return _exact_form(essay).count(needle) if needle else 0


def snap_band(value) -> float | None:
    """Coerce a model-provided band to the 0-9 half-band scale."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or number < 0 or number > 9:
        return None
    return math.floor(number * 2 + 0.5) / 2


def overall_band(bands: list[float]) -> float | None:
    """IELTS-style: mean of the criteria, .25 rounds up to .5 and .75 up to the next band."""
    if not bands or any(b is None for b in bands):
        return None
    mean = sum(bands) / len(bands)
    return math.floor(mean * 2 + 0.5 + 1e-9) / 2


# Sentences that repeat the task wording almost word for word. In the test, words
# copied from the question are not counted and are not the candidate's own language;
# the official 5.5 sample of Task 2B opens with the question copied, with two slips
# ("impaction", "outweight"), so a near-verbatim match counts, not only an exact one.
COPY_MIN_TOKENS = 6
COPY_SHARE = 0.85
COPY_MIN_RUN = 5
_COPY_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _copy_tokens(text: str) -> list[str]:
    return _COPY_TOKEN_RE.findall((text or "").lower())


def copied_from_prompt(essay: str | None, prompt: str | None) -> list[dict]:
    """[{"p": paragraph number, "sentence": text, "words": count}] for every sentence
    of at least COPY_MIN_TOKENS words of which COPY_SHARE or more match the prompt in
    order, with one run of at least COPY_MIN_RUN words. A text comparison, not a
    judgement of intent: reusing a few words of the question does not count."""
    question = _copy_tokens(prompt)
    if len(question) < COPY_MIN_TOKENS:
        return []
    found = []
    for sentence in split_sentences(essay):
        tokens = _copy_tokens(sentence.text)
        if len(tokens) < COPY_MIN_TOKENS:
            continue
        blocks = difflib.SequenceMatcher(
            None, tokens, question, autojunk=False
        ).get_matching_blocks()
        matched = sum(b.size for b in blocks)
        if matched >= COPY_SHARE * len(tokens) and max(b.size for b in blocks) >= COPY_MIN_RUN:
            found.append(
                {
                    "p": sentence.paragraph + 1,
                    "sentence": sentence.text,
                    "words": count_words(sentence.text),
                }
            )
    return found
