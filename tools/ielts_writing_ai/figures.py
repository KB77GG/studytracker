"""Figures in model advice must come from what the student gave us.

Suggestions are advice, so a statistic, percentage or year in a suggestion that
appears nowhere in the essay, the question or the chart reading has no source (the
2026-11-04 run recommended "over 80%" emission cuts to an essay without any figure).
Such suggestions are removed rather than shown. This checks where a number comes
from, not whether a statement is true.

Three kinds of figure (real runs of 2026-11-04):
- a percentage ("80%", "80 per cent", "百分之八十", "百分之8") needs the same percentage
  in the source; values are compared whole, so 1980 or 180 is not a source for 80%
  and 百分之八十一 is not a source for 百分之八十;
- a length target ("扩写到 260 词以上", "260-300 words", "字数达到 260") is a writing
  goal, not a fact, and is allowed up to MAX_WORD_TARGET ("260 次事故" is not one);
- a span of time ("twenty years later", "two decades") is sourced when it equals the
  gap between two years the input gives (2000 and 2020 -> 20 years);
- a multiplier ("forty times as many", "three times", "40-fold") is a factual claim
  and needs the same multiplier in the source, however small (a plain 40 is not a
  source for "forty times");
- any other number of 10 or more needs the same value in the source; smaller plain
  numbers are structural ("补 1 个例子", "第 2 段", "one example") and always allowed.

Numbers are read in digits, with a scale word ("1.5 million" = 1500000), as Chinese
percentages, and as English words ("forty", "forty-two", "one hundred and twenty":
the 2026-11-04 thinking run advised "about forty times as many people", which the
digit-only reader could not see). Ordinals ("twenty-first") are not figures.
"""

from __future__ import annotations

import re

from . import essay as essay_lib

SMALL = 10
MAX_WORD_TARGET = 600
_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_PERCENT_RE = re.compile(r"\s*(?:%|％|per\s*cent|percentage\s+points?)", re.IGNORECASE)
_WORD_UNIT_RE = re.compile(
    r"\s*(?:(?:-|–|—|~|～|到|至|to)\s*\d+\s*)?(?:个)?(?:单词|词|字(?!母)|words?\b)",
    re.IGNORECASE,
)
_WORD_COUNT_BEFORE_RE = re.compile(
    r"(?:字数|词数|篇幅|word\s*count)[^，。,.;；!?！？]{0,8}$", re.IGNORECASE
)
_CN_PERCENT_RE = re.compile(r"百分之(?:(\d+(?:\.\d+)?)|([零〇一二两三四五六七八九十百千点]+))")
_CN_DIGITS = dict(
    zip("零〇一二两三四五六七八九", (0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9), strict=True)
)
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}

PERCENT, LENGTH, PLAIN, MULTIPLIER, DURATION = (
    "percent",
    "length",
    "plain",
    "multiplier",
    "duration",
)


def _value(raw: str) -> str:
    value = raw.replace(",", "")
    if "." in value:
        value = value.rstrip("0").rstrip(".") or "0"
    return value


def cn_number(text: str) -> str:
    """Chinese numerals to a value string: 八十一 -> 81, 一百零五 -> 105, 五点五 -> 5.5."""
    whole, _, decimals = text.partition("点")
    total = current = 0
    for char in whole:
        if char in _CN_DIGITS:
            current = _CN_DIGITS[char]
        elif char in _CN_UNITS:
            total += (current or 1) * _CN_UNITS[char]
            current = 0
    total += current
    digits = "".join(str(_CN_DIGITS[c]) for c in decimals if c in _CN_DIGITS)
    return _value(f"{total}.{digits}" if digits else str(total))


_EN_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fourty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip
_EN_SCALES = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9}
_EN_WORD = "|".join(sorted(list(_EN_UNITS) + list(_EN_SCALES), key=len, reverse=True))
# "forty", "forty-two", "one hundred and twenty", "a hundred", "two thousand and twenty"
_EN_NUMBER_RE = re.compile(
    rf"\b(?:a\s+(?=(?:hundred|thousand|million|billion)\b))?(?:{_EN_WORD})"
    rf"(?:(?:\s+and\s+|\s+|-)(?:{_EN_WORD}))*\b",
    re.IGNORECASE,
)
_ORDINAL_AFTER_RE = re.compile(
    r"-(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)\b|th\b", re.IGNORECASE
)
_SCALE_AFTER_RE = re.compile(r"\s*(thousand|million|billion)\b", re.IGNORECASE)
# "forty times as many", "three times", "40-fold": a multiplier is a factual claim
_TIMES_RE = re.compile(r"\s*(?:-\s*fold\b|fold\b|times\b)", re.IGNORECASE)
# "twenty years later", "two decades": a span of time, in years
_DURATION_RE = re.compile(r"\s*-?\s*(years?|decades?)\b", re.IGNORECASE)


def _is_year(value: str) -> bool:
    return value.isdigit() and 1000 <= int(value) <= 2100


def en_number(text: str) -> str:
    """English number words to a value string: forty-two -> 42, a hundred -> 100."""
    total = current = 0
    for word in re.findall(r"[A-Za-z]+", text.lower()):
        if word in _EN_UNITS:
            current += _EN_UNITS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        elif word in _EN_SCALES:
            total += (current or 1) * _EN_SCALES[word]
            current = 0
    return str(total + current)


DECADES = "decades"  # internal: converted to a DURATION in years


def _years(value: str, kind: str) -> tuple[str, str]:
    if kind == DECADES:
        return _value(str(float(value) * 10)).removesuffix(".0"), DURATION
    return value, kind


def _kind(text: str, end: int, before: str) -> tuple[str, int]:
    """(kind, end of the figure as written) from what follows the number."""
    percent = _PERCENT_RE.match(text, end)
    if percent:
        return PERCENT, percent.end()
    times = _TIMES_RE.match(text, end)
    if times:
        return MULTIPLIER, times.end()
    duration = _DURATION_RE.match(text, end)
    if duration:
        return (
            DECADES if duration.group(1).lower().startswith("decade") else DURATION
        ), duration.end()
    if _WORD_UNIT_RE.match(text, end) or _WORD_COUNT_BEFORE_RE.search(before):
        return LENGTH, end
    return PLAIN, end


def figures(text: str | None) -> list[tuple[str, str, str]]:
    """(value, kind, as written) for every whole figure in the text: digits (with an
    optional scale word), Chinese percentages and English number words."""
    text = text or ""
    found, taken = [], []
    for match in _CN_PERCENT_RE.finditer(text):
        value = _value(match.group(1)) if match.group(1) else cn_number(match.group(2))
        found.append((match.start(), value, PERCENT, match.group()))
        taken.append(match.span())
    for match in _NUMBER_RE.finditer(text):
        if match.start() and text[match.start() - 1].isdigit():
            continue  # never part of a longer number
        if any(start <= match.start() < end for start, end in taken):
            continue  # already read as 百分之N
        value, end = _value(match.group()), match.end()
        scale = _SCALE_AFTER_RE.match(text, end)
        if scale:  # "1.5 million" is 1500000, not a small 1.5
            value = _value(str(float(value) * _EN_SCALES[scale.group(1).lower()]))
            value = value[:-2] if value.endswith(".0") else value
            end = scale.end()
            taken.append((match.start(), end))  # the scale word is not a number of its own
        kind, shown_end = _kind(text, end, text[: match.start()])
        value, kind = _years(value, kind)
        found.append((match.start(), value, kind, text[match.start() : shown_end].strip()))
    for match in _EN_NUMBER_RE.finditer(text):
        if _ORDINAL_AFTER_RE.match(text, match.end()):
            continue  # "twenty-first century" is an ordinal, not a figure
        if any(start <= match.start() < end for start, end in taken):
            continue  # "million" in "1.5 million" was read with its digits
        kind, shown_end = _kind(text, match.end(), text[: match.start()])
        value, kind = _years(en_number(match.group()), kind)
        found.append((match.start(), value, kind, text[match.start() : shown_end].strip()))
    return [(value, kind, shown) for _pos, value, kind, shown in sorted(found)]


class Sources:
    """The figures a suggestion may use: everything the student supplied plus the
    task's own numbers (word count, minimum length)."""

    def __init__(self, *texts: str | None, numbers=()):
        self.text = "\n".join(t for t in texts if t)
        self.values = set()
        self.percents = set()
        self.multipliers = set()
        for value, kind, _shown in figures(self.text):
            self.values.add(value)
            if kind == PERCENT:
                self.percents.add(value)
            elif kind == MULTIPLIER:
                self.multipliers.add(value)
        self.values.update(_value(str(n)) for n in numbers if n is not None)
        # Spans between two years the input gives ("2000 ... 2020" -> 20 years), so
        # "twenty years later" is derived from the source, not invented.
        years = sorted({int(float(v)) for v in self.values if _is_year(v)})
        self.year_spans = {str(b - a) for i, a in enumerate(years) for b in years[i + 1 :]}

    def unsourced(self, text: str | None) -> list[str]:
        missing = []
        for value, kind, shown in figures(text):
            if kind == PERCENT:
                sourced = value in self.percents
            elif kind == LENGTH:
                sourced = float(value) <= MAX_WORD_TARGET
            elif kind == MULTIPLIER:  # no small-number exemption: "three times" is a fact
                sourced = value in self.multipliers
            elif kind == DURATION:
                sourced = value in self.values or value in self.year_spans or float(value) < SMALL
            else:
                sourced = value in self.values or float(value) < SMALL
            if not sourced:
                missing.append(shown)
        return missing


def for_submission(submission: dict) -> Sources:
    task_type = submission.get("task_type") or "task2"
    chart = (
        submission.get("image_description") if submission.get("image_status") == "ready" else None
    )
    return Sources(
        submission.get("essay_text"),
        submission.get("prompt_text"),
        chart,
        numbers=(submission.get("word_count"), essay_lib.MIN_WORDS.get(task_type)),
    )
