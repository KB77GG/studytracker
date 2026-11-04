"""Figures in model advice must come from what the student gave us.

Suggestions are advice, so a statistic, percentage or year in a suggestion that
appears nowhere in the essay, the question or the chart reading has no source (the
2026-11-04 run recommended "over 80%" emission cuts to an essay without any figure).
Such suggestions are removed rather than shown. This checks where a number comes
from, not whether a statement is true.

Numbers are compared as whole values: 1980 or 180 in the essay is not a source for
80, and a percentage needs the same percentage in the source. Small plain numbers
(under 10) are structural ("补 1 个例子", "第 2 段") and always allowed.
"""

from __future__ import annotations

import re

from . import essay as essay_lib

SMALL = 10
_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_PERCENT_RE = re.compile(r"\s*(?:%|％|per\s*cent|percentage\s+points?)", re.IGNORECASE)
_CN_PERCENT_RE = re.compile(r"百分之[零〇一二两三四五六七八九十百千点]+")


def _value(raw: str) -> str:
    value = raw.replace(",", "")
    if "." in value:
        value = value.rstrip("0").rstrip(".") or "0"
    return value


def figures(text: str | None) -> list[tuple[str, bool, str]]:
    """(value, is_percentage, as written) for every whole number in the text."""
    text = text or ""
    found = []
    for match in _NUMBER_RE.finditer(text):
        if match.start() and text[match.start() - 1].isdigit():
            continue  # never part of a longer number
        percent = _PERCENT_RE.match(text, match.end())
        shown = text[match.start() : percent.end() if percent else match.end()]
        found.append((_value(match.group()), bool(percent), shown.strip()))
    return found


class Sources:
    """The figures a suggestion may use: everything the student supplied plus the
    task's own numbers (word count, minimum length)."""

    def __init__(self, *texts: str | None, numbers=()):
        self.text = "\n".join(t for t in texts if t)
        self.values = set()
        self.percents = set()
        for value, percent, _shown in figures(self.text):
            self.values.add(value)
            if percent:
                self.percents.add(value)
        self.values.update(_value(str(n)) for n in numbers if n is not None)

    def unsourced(self, text: str | None) -> list[str]:
        missing = []
        for value, percent, shown in figures(text):
            if percent:
                sourced = value in self.percents
            else:
                sourced = value in self.values or float(value) < SMALL
            if not sourced:
                missing.append(shown)
        missing += [
            m.group() for m in _CN_PERCENT_RE.finditer(text or "") if m.group() not in self.text
        ]
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
