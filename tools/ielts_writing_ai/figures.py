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
- any other number of 10 or more needs the same value in the source; smaller plain
  numbers are structural ("补 1 个例子", "第 2 段") and always allowed.
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

PERCENT, LENGTH, PLAIN = "percent", "length", "plain"


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


def figures(text: str | None) -> list[tuple[str, str, str]]:
    """(value, kind, as written) for every whole figure in the text."""
    text = text or ""
    found, taken = [], []
    for match in _CN_PERCENT_RE.finditer(text):
        value = _value(match.group(1)) if match.group(1) else cn_number(match.group(2))
        found.append((value, PERCENT, match.group()))
        taken.append(match.span())
    for match in _NUMBER_RE.finditer(text):
        if match.start() and text[match.start() - 1].isdigit():
            continue  # never part of a longer number
        if any(start <= match.start() < end for start, end in taken):
            continue  # already read as 百分之N
        percent = _PERCENT_RE.match(text, match.end())
        if percent:
            kind, shown = PERCENT, text[match.start() : percent.end()]
        elif _WORD_UNIT_RE.match(text, match.end()) or _WORD_COUNT_BEFORE_RE.search(
            text[: match.start()]
        ):
            kind, shown = LENGTH, match.group()
        else:
            kind, shown = PLAIN, match.group()
        found.append((_value(match.group()), kind, shown.strip()))
    return found


class Sources:
    """The figures a suggestion may use: everything the student supplied plus the
    task's own numbers (word count, minimum length)."""

    def __init__(self, *texts: str | None, numbers=()):
        self.text = "\n".join(t for t in texts if t)
        self.values = set()
        self.percents = set()
        for value, kind, _shown in figures(self.text):
            self.values.add(value)
            if kind == PERCENT:
                self.percents.add(value)
        self.values.update(_value(str(n)) for n in numbers if n is not None)

    def unsourced(self, text: str | None) -> list[str]:
        missing = []
        for value, kind, shown in figures(text):
            if kind == PERCENT:
                sourced = value in self.percents
            elif kind == LENGTH:
                sourced = float(value) <= MAX_WORD_TARGET
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
