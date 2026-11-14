"""Language advice must not keep a figure the same evaluation calls wrong.

The official Task 1 run of 2026-11-14 (docs/design/ielts-writing-ai-official-t1-pro-
20261114-results/content-review.json) found suggestions under Coherence, Lexical or
Grammar that rewrote a sentence for its language but kept a value which the Task
Achievement part of the same answer had just corrected. A student following both
pieces of advice gets two versions of the data.

This only looks at figures, not at trend words: a Task Achievement issue counts as a
data correction when its suggestion replaces a number of the quoted text with a
different one (a number of the quote is gone *and* a new one appears; dropping detail
alone is not a correction). The replaced values are percentages or numbers of 10 or
more: smaller plain numbers ("00" of "22:00", "two" categories) are too common to tell
anything. A suggestion of another criterion whose quote lies in the same sentence and
still contains a replaced value loses its suggestion; its comment stays.
"""

from __future__ import annotations

from . import essay as essay_lib
from . import figures as figures_lib

REASON = "task_conflict"
OTHER_CRITERIA = ("coherence", "lexical", "grammar")


def _values(text: str | None) -> set[str]:
    return {
        value
        for value, kind, _shown in figures_lib.figures(text)
        if kind == figures_lib.PERCENT or float(value) >= figures_lib.SMALL
    }


def corrected_values(issue: dict) -> set[str]:
    """Values a Task Achievement issue replaces in its own quote (empty if it only
    removes or only adds figures, or has no verified quote)."""
    if not (issue.get("quote_found") and issue.get("suggestion")):
        return set()
    before, after = _values(issue["quote"]), _values(issue["suggestion"])
    return before - after if before - after and after - before else set()


class _Sentences:
    """Which sentences of the essay a quote touches (in the lenient quote form)."""

    def __init__(self, essay: str):
        self.text = essay_lib.squash(essay)
        self.ranges, cursor = [], 0
        for sentence in essay_lib.split_sentences(essay):
            piece = essay_lib.squash(sentence.text)
            start = self.text.find(piece, cursor)
            if start < 0:
                continue
            self.ranges.append((start, start + len(piece)))
            cursor = start + len(piece)

    def of(self, quote: str) -> set[int]:
        needle = essay_lib.squash(quote).strip(" .,;:!?\"'")
        start = self.text.find(needle) if needle else -1
        if start < 0:
            return set()
        end = start + len(needle)
        return {n for n, (a, b) in enumerate(self.ranges) if a < end and start < b}


def remove_conflicting(criteria: list[dict], essay: str) -> int:
    """Drop language suggestions that keep a value Task Achievement corrected in the
    same sentence. Returns how many were removed."""
    by_key = {c["key"]: c for c in criteria}
    task = by_key.get("task")
    if not task or task.get("state") != "scored":
        return 0
    sentences = _Sentences(essay)
    corrections = []  # (sentences touched, values replaced)
    for issue in task.get("issues") or []:
        values = corrected_values(issue)
        if values:
            corrections.append((sentences.of(issue["quote"]), values))
    if not corrections:
        return 0
    removed = 0
    for key in OTHER_CRITERIA:
        for issue in (by_key.get(key) or {}).get("issues") or []:
            if not (issue.get("quote_found") and issue.get("suggestion")):
                continue
            touched, kept = sentences.of(issue["quote"]), _values(issue["suggestion"])
            if any(touched & where and kept & values for where, values in corrections):
                issue.update(suggestion="", suggestion_removed=True, removed_reason=REASON)
                removed += 1
    return removed
