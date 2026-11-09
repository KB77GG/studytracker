"""Advice that mentions deleting text gets a reminder to recount.

2026-11-07: "delete the 23-word conclusion" would have taken a 172-word Task 1 to 149
(minimum 150) without a word about it. From 2026-11-08 the tool tried to work out the
remaining length from the advice text; four reviews in a row found that free-text
advice (negations shared by two verbs, "A and/or B", "two paragraphs" vs "the second
paragraph", quoted advice, positions inside sentences) could not be read reliably
enough to state a number, and a wrong number is worse than none (review 2026-11-09).

So no remaining length is computed from advice any more. When an advice mentions
deleting text and the essay is close enough to the minimum for that to
matter, a conditional reminder with the two known numbers - the essay's word count and
the minimum - is appended. It says nothing about what the advice deletes. The word
count of an actual revised essay is checked where one exists (rewrite).
"""

from __future__ import annotations

import re

from . import essay as essay_lib

# Chinese advice: any deleting verb. English: "delete" / "omit" anywhere (they hardly
# occur in model sentences about the essay's topic); "remove" / "cut" / "drop" only as
# an instruction - at the start of a sentence, after "please", or with "you" + a modal /
# "do not" - so that model sentences in a suggestion ("Building roads can cut traffic",
# "Car ownership dropped") do not count. Shortening words (精简 / 压缩) are left out:
# advice such as 压缩段落数量 rarely removes words.
_CN_RE = re.compile(r"删|去掉|拿掉|省去|省略|砍掉")
_EN_ANYWHERE_RE = re.compile(r"\b(?:delete[sd]?|deleting|omit(?:s|ted|ting)?)\b", re.I)
_EN_VERBS = r"(?:remove|cut|drop)"
_EN_RE = re.compile(
    rf"(?:^|[.;:!?。；：！？，,]\s*)(?:please\s+|(?:also|then|just|simply)\s+)?{_EN_VERBS}\b|"
    rf"\bplease\s+{_EN_VERBS}\b|"
    rf"\byou\s+(?:should|could|can|may|might|must|need to|have to|do not|don't|don’t|"
    rf"shouldn't|shouldn’t|never)\s+(?:\w+\s+)?{_EN_VERBS}\b|"
    rf"(?:^|[.;:!?。；：！？]\s*)(?:do not|don't|don’t|never)\s+{_EN_VERBS}\b",
    re.I,
)


def mentions_deletion(advice: str | None) -> bool:
    """Whether the advice mentions deleting text (in any sense: the reminder is
    conditional, so "do not delete" may get it too)."""
    if not advice:
        return False
    return bool(_CN_RE.search(advice) or _EN_ANYWHERE_RE.search(advice) or _EN_RE.search(advice))


def may_matter(essay: str, minimum: int) -> bool:
    """Deleting one paragraph could take the essay below the minimum (or it is below)."""
    total = essay_lib.count_words(essay)
    largest = max((essay_lib.count_words(p) for p in essay_lib.split_paragraphs(essay)), default=0)
    return total - minimum <= largest


def reminder(essay: str, minimum: int) -> str:
    total = essay_lib.count_words(essay)
    return (
        f"（提示：这条建议提到删减。如果按删减修改，请核对修改后的字数：原文 {total} 词，"
        f"字数下限 {minimum} 词。本工具不推算删后字数。）"
    )


def annotate(criteria, argument, priorities: list[str], essay: str, minimum: int) -> int:
    """Append the reminder to every advice that mentions deletion (in place), when the
    length may matter. Returns how many were annotated."""
    if not may_matter(essay, minimum):
        return 0
    note = reminder(essay, minimum)
    added = 0
    entries = [i for c in criteria for i in c["issues"]]
    if argument:
        entries += list(argument.get("problems") or []) + list(argument.get("improvements") or [])
    for entry in entries:
        if mentions_deletion(entry.get("suggestion")):
            entry["suggestion"] += note
            added += 1
    for n, text in enumerate(priorities):
        if mentions_deletion(text):
            priorities[n] = text + note
            added += 1
    return added
