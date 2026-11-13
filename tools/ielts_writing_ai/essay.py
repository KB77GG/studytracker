"""Pure text helpers: word counting, sentence splitting and band arithmetic."""

from __future__ import annotations

import difflib
import json
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


# Copying from the question. In the test, words copied from the question are not
# counted and are not the candidate's own language. Review f46756f (2026-11-13) showed
# that a text comparison cannot decide this: a sentence that borrows the question's
# nouns but adds the writer's own trend or opinion was taken as copied (152 words
# counted as 138), and the official 5.5 script's copied lines were only partly found
# (18 of 34 words). So a comparison is only a hint shown to the reader; only copying
# confirmed by a person or an examiner's comment (stored with the submission) is left
# out of the word count and passed to the model.
COPY_MIN_TOKENS = 6
COPY_SHARE = 0.85
COPY_MIN_RUN = 5
_COPY_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _copy_tokens(text: str) -> list[str]:
    return _COPY_TOKEN_RE.findall((text or "").lower())


def similar_to_prompt(essay: str | None, prompt: str | None) -> list[dict]:
    """Hints only: [{"p": paragraph number, "sentence": text, "words": count}] for every
    sentence of at least COPY_MIN_TOKENS words of which COPY_SHARE or more follow the
    question's wording in order, with one run of at least COPY_MIN_RUN words. It never
    decides that a sentence was copied."""
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


def _paragraph_offsets(text: str) -> list[tuple[int, int]]:
    """(start, end) of each paragraph of split_paragraphs in ``text`` (normalized)."""
    offsets, position = [], 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            start = position + line.index(stripped)
            offsets.append((start, start + len(stripped)))
        position += len(line) + 1
    return offsets


def _splits_a_word(text: str, start: int, end: int) -> bool:
    """True when a passage [start, end) begins or ends inside a word as count_words
    sees it (WORD_RE keeps "don't", "don’t" and "cost-effective" whole), or next to
    any other letter or digit. Otherwise two passages could take the halves of one
    word and count it twice (review cd82fc1: 151 words counted as 149)."""
    for token in WORD_RE.finditer(text):
        if token.start() >= end:
            break
        if token.start() < start < token.end() or token.start() < end < token.end():
            return True
    return (start > 0 and text[start - 1].isalnum()) or (end < len(text) and text[end].isalnum())


def resolve_copied(essay: str, entries) -> list[dict]:
    """Confirmed copying, given as [{"paragraph": n} | {"quote": verbatim text}, ...],
    turned into [{"p": paragraph number, "text": exact passage}] in essay order. A quote
    must lie inside one paragraph, occur once and start and end on the word boundaries
    count_words uses, so the words of all passages add up without counting one twice.
    Raises ValueError when an entry is malformed, missing or overlaps another."""
    if not isinstance(entries, list) or not entries:
        raise ValueError("必须是非空列表")
    text = normalize_newlines(essay)
    paragraphs = _paragraph_offsets(text)
    spans = []
    for n, entry in enumerate(entries, 1):
        if isinstance(entry, dict) and set(entry) == {"paragraph"}:
            number = entry["paragraph"]
            if type(number) is not int or not 1 <= number <= len(paragraphs):
                raise ValueError(f"第 {n} 项的段号不在 1–{len(paragraphs)} 之间")
            start, end = paragraphs[number - 1]
        elif (
            isinstance(entry, dict) and set(entry) == {"quote"} and isinstance(entry["quote"], str)
        ):
            quote = entry["quote"].strip()
            if not quote or "\n" in quote or text.count(quote) != 1:
                raise ValueError(f"第 {n} 项的原文在作文里找不到、跨段或出现不止一次")
            start = text.index(quote)
            end = start + len(quote)
            if _splits_a_word(text, start, end):
                raise ValueError(f"第 {n} 项的原文没有从完整的词开始或结束")
            number = next(i for i, (a, b) in enumerate(paragraphs, 1) if a <= start < b)
        else:
            raise ValueError(f'第 {n} 项应为 {{"paragraph": 段号}} 或 {{"quote": "原文"}}')
        if any(start < b and a < end for a, b, _p in spans):
            raise ValueError(f"第 {n} 项与前面的区间重叠")
        spans.append((start, end, number))
    return [{"p": number, "text": text[a:b]} for a, b, number in sorted(spans)]


def confirmed_copies(submission: dict) -> dict | None:
    """Copying confirmed for a submission (stored as JSON in its copied_spans column):
    {"spans": [{"p", "text", "words"}], "source": str, "words": int}, or None."""
    raw = submission.get("copied_spans")
    if not raw:
        return None
    data = json.loads(raw) if isinstance(raw, str) else raw
    spans = [
        {"p": span["p"], "text": span["text"], "words": count_words(span["text"])}
        for span in data.get("spans") or []
    ]
    if not spans:
        return None
    return {
        "spans": spans,
        "source": data.get("source") or "",
        "words": sum(span["words"] for span in spans),
    }


def unconfirmed_similar(submission: dict) -> list[dict]:
    """similar_to_prompt hints that are not already inside confirmed copying."""
    confirmed = confirmed_copies(submission) or {"spans": []}
    return [
        hint
        for hint in similar_to_prompt(submission.get("essay_text"), submission.get("prompt_text"))
        if not any(
            span["p"] == hint["p"] and hint["sentence"] in span["text"]
            for span in confirmed["spans"]
        )
    ]
