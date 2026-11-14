"""Language advice must not keep a figure the same evaluation calls wrong.

The official Task 1 run of 2026-11-14 (docs/design/ielts-writing-ai-official-t1-pro-
20261114-results/content-review.json) found suggestions under Coherence, Lexical or
Grammar that rewrote a sentence for its language but kept a value which the Task
Achievement part of the same answer had just corrected. A student following both
pieces of advice gets two versions of the data.

Only figures are compared, not trend words. The review of the first version
(docs/design/iwa-task-conflicts-recheck-20261114) showed that comparing bare numbers per
sentence removes correct advice (men 20% corrected, women's 20% removed; 45% vs. 45
minutes; 22:00 vs. 22%), that a short quote found twice cannot be placed, that the
300-character display quote can cut off the corrected figure, and that a correction is
lost when the existing source check has emptied the TA suggestion. So:

- A correction is tied to the exact figures in the essay (position and kind: percent,
  plain number ...): a TA issue whose full verified quote occurs exactly once (on word
  boundaries) and whose own suggestion replaces a figure of that quote by a different
  one (a figure of the quote is gone *and* a new one appears). If the source check
  removed that suggestion (a new figure without a source), it is never shown and on
  its own proves nothing; a replaced figure then counts only when the TA comment, which
  is shown, names that same figure (L9: the comment called the figure wrong, the
  suggestion's own replacement had no source).
- Only percentages and numbers of 10 or more count (not "00" of "22:00", not "two").
- A suggestion of another criterion conflicts with a corrected figure when its quote
  occurs exactly once and either contains that figure, or lies in the same sentence
  where that figure is the only one of its value and kind. It conflicts only if it
  keeps more figures of that value and kind than its quote has uncorrected ones.
  Whatever cannot be placed or told apart is left alone.
"""

from __future__ import annotations

from collections import Counter

from . import essay as essay_lib
from . import figures as figures_lib

REASON = "task_conflict"
OTHER_CRITERIA = ("coherence", "lexical", "grammar")


def _counted(value: str, kind: str) -> bool:
    return kind == figures_lib.PERCENT or float(value) >= figures_lib.SMALL


def _figures(text: str | None) -> Counter:
    return Counter(
        (value, kind) for value, kind, _shown in figures_lib.figures(text) if _counted(value, kind)
    )


class _Essay:
    """The essay in the lenient quote form, with its figures and sentences placed."""

    def __init__(self, essay: str):
        self.text = essay_lib.squash(essay)
        self.figures = [
            (start, value, kind)
            for start, value, kind, _shown in figures_lib.located(self.text)
            if _counted(value, kind)
        ]
        self.sentences, cursor = [], 0
        for sentence in essay_lib.split_sentences(essay):
            piece = essay_lib.squash(sentence.text)
            start = self.text.find(piece, cursor)
            if start >= 0:
                self.sentences.append((start, start + len(piece)))
                cursor = start + len(piece)

    def span(self, quote: str | None) -> tuple[int, int] | None:
        """Where a quote is, if it occurs exactly once on word boundaries."""
        needle = essay_lib.squash(quote).strip(" .,;:!?\"'")
        if not needle:
            return None
        found, start = [], self.text.find(needle)
        while start >= 0:
            end = start + len(needle)
            before = self.text[start - 1] if start else " "
            after = self.text[end] if end < len(self.text) else " "
            if not (before.isalnum() and needle[0].isalnum()) and not (
                after.isalnum() and needle[-1].isalnum()
            ):
                found.append((start, end))
            start = self.text.find(needle, start + 1)
        return found[0] if len(found) == 1 else None

    def inside(self, span) -> list[tuple[int, str, str]]:
        return [f for f in self.figures if span[0] <= f[0] < span[1]]

    def sentence_of(self, position: int) -> tuple[int, int] | None:
        return next((s for s in self.sentences if s[0] <= position < s[1]), None)


def corrected_figures(essay: _Essay, quote: str | None, suggestion: str | None) -> list:
    """The figures of the essay a TA issue replaces: (position, value, kind)."""
    span = essay.span(quote) if suggestion else None
    if span is None:
        return []
    before = essay.inside(span)
    old = {value for _p, value, _k in before}
    new = {value for value, _kind in _figures(suggestion)}
    if not (old - new and new - old):
        return []  # only detail dropped or only figures added: not a replacement
    return [f for f in before if f[1] in old - new]


def _conflicts(essay: _Essay, span, suggestion: str, corrected: list) -> bool:
    kept, in_quote = _figures(suggestion), essay.inside(span)
    for figure in corrected:
        position, value, kind = figure
        covered = span[0] <= position < span[1]
        if not covered:
            sentence = essay.sentence_of(position)
            same = sentence and sentence[0] <= span[0] and span[1] <= sentence[1]
            alone = sentence and [f for f in essay.inside(sentence) if f[1:] == (value, kind)] == [
                figure
            ]
            if not (same and alone):
                continue
        uncorrected = sum(1 for f in in_quote if f[1:] == (value, kind) and f not in corrected)
        if kept[(value, kind)] > uncorrected:
            return True
    return False


def remove_conflicting(criteria: list[dict], essay: str, internal: dict) -> int:
    """Drop language suggestions that keep a figure Task Achievement corrected.

    internal[key] lists, in the order of that criterion's issues, the full verified
    quote and the suggestion as the model wrote it (see review._evidence_items).
    Returns how many suggestions were removed."""
    by_key = {c["key"]: c for c in criteria}
    task = by_key.get("task")
    if not task or task.get("state") != "scored":
        return 0
    placed = _Essay(essay)
    corrected = []
    for issue, raw in zip(task["issues"], internal.get("task") or [], strict=False):
        if not issue.get("quote_found"):
            continue
        figures = corrected_figures(placed, raw["quote"], raw["suggestion"])
        if not issue.get("suggestion"):  # removed: only figures the comment names count
            named = _figures(issue.get("comment"))
            figures = [f for f in figures if named[f[1:]]]
        corrected += figures
    if not corrected:
        return 0
    removed = 0
    for key in OTHER_CRITERIA:
        issues = (by_key.get(key) or {}).get("issues") or []
        for issue, raw in zip(issues, internal.get(key) or [], strict=False):
            if not (issue.get("quote_found") and issue.get("suggestion")):
                continue
            span = placed.span(raw["quote"])
            if span and _conflicts(placed, span, issue["suggestion"], corrected):
                issue.update(suggestion="", suggestion_removed=True, removed_reason=REASON)
                removed += 1
    return removed
