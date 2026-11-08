"""Advice that deletes text, checked against the minimum length.

2026-11-07: "delete the 23-word conclusion" would have taken a 172-word Task 1 to 149
(minimum 150) without a word about it. The first check (.10) only looked for a deletion
verb next to 段 / 句, so "do not delete this paragraph" or "remove only 'In summary' from
this sentence" were counted as whole-unit deletions, and the issue's own quote was used
even when the advice named another paragraph (review 2026-11-08).

Each clause of the advice is now read on its own:
- intent: a deletion verb outside quotation marks, with no negation before it
  (不要采用“删除这一段”的意见 quotes someone else's advice and deletes nothing);
- scope: what the verb deletes - in Chinese the head noun ends the phrase
  (结尾的“In summary”这一段 is a paragraph, 句子结尾的“respectively” is one word), in
  English it comes first after the verb (the paragraph beginning "In summary" is a
  paragraph, only "In summary" from this sentence is two words);
- target: a stated position (结尾 / 最后一段 / final paragraph, 首段 / 引言, 第 N 段) and
  passages the clause quotes come first; the issue's quote is used only when the clause
  names neither. A target that cannot be pinned down (conflicting, or a passage found in
  more than one place) gets no number, only "cannot tell which part" when it matters.
The advice text itself is never changed; a note is appended after it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import essay as essay_lib

_VERB_RE = re.compile(
    r"删去|删除|删掉|去掉|拿掉|省去|省略|(?<!增)删(?![改减])|\b(?:delete|remove|cut|drop|omit)\b",
    re.I,
)
# Matched on the whole clause (with ’ read as '), and counted when it starts before the
# verb: the lookahead of 别(?=删) has to see the verb (recheck 2026-11-08).
_NEGATION_RE = re.compile(
    r"不要|不用|不必|无需|无须|不需要|不应|不宜|不该|不能|不可|没必要|不建议|避免|而不是|切勿|"
    r"别(?=删|去掉|拿掉|省)|勿(?=删|去掉|拿掉|省)|"
    r"\b(?:do not|dont|never|avoid|no need to|instead of|rather than|not|cannot)\b|"
    r"\b[a-z]+n't\b",
    re.I,
)
# Paired quotation marks. A straight or closing single quote between two letters is an
# apostrophe (don't, the city's), never a quotation mark.
_QUOTE_RE = re.compile(
    r"“([^”]{1,300})”|\"([^\"]{1,300})\"|‘(.{1,300}?)’(?![A-Za-z0-9])|"
    r"(?<![A-Za-z0-9])'(?=\S)(.{1,300}?)(?<=\S)'(?![A-Za-z0-9])"
)
_CLAUSE_RE = re.compile(r"[。；;！!？?，,：:\n]")
_HOLE_RE = re.compile("\x00(\\d+)\x00")
_CJK_RE = re.compile(r"[一-鿿]")

# Chinese: the head noun closes the phrase.
_CN_TAIL_PASSAGE_RE = re.compile(r"(?:\x00\d+\x00|个词|词语|单词|短语|这个词)(?:即可|就好|吧)?\s*$")
_CN_TAIL_UNIT_RE = re.compile(r"(段落?|句子?|结论|引言)(?:即可|就好|吧)?\s*$")
_CN_PARTIAL_RE = re.compile(r"句中|句首|句末|句里|段中|段里|中的|里的")
# English: the head noun comes first after the verb.
_EN_HEAD_RE = re.compile(
    r"\x00\d+\x00|\b(words?|phrases?)\b|\b(paragraphs?|sentences?|conclusion|introduction)\b",
    re.I,
)
_PARAGRAPH_WORD_RE = re.compile(r"段|结论|引言|\b(?:paragraphs?|conclusion|introduction)\b", re.I)
_SENTENCE_WORD_RE = re.compile(r"句|\bsentences?\b", re.I)

_LAST_PARAGRAPH_RE = re.compile(
    r"结尾|结论|末段|最末段|最后(?:这)?一?段|\b(?:final|last|concluding) paragraph\b|\bconclusion\b",
    re.I,
)
_FIRST_PARAGRAPH_RE = re.compile(
    r"首段|开头(?:这)?一?段|第一段|引言|\b(?:first|opening|introductory) paragraph\b|\bintroduction\b",
    re.I,
)
_NTH_PARAGRAPH_RE = re.compile(
    r"第([二三四五六七八九十]|\d+)段|\bparagraph (\d+)\b|\b(second|third|fourth|fifth|sixth) paragraph\b",
    re.I,
)
_LAST_SENTENCE_RE = re.compile(r"最后一句|结尾句|末句|\b(?:final|last) sentence\b", re.I)
_FIRST_SENTENCE_RE = re.compile(r"第一句|首句|开头一句|\b(?:first|opening) sentence\b", re.I)
_CN_NUMBERS = {"二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_EN_ORDINALS = {"second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}


@dataclass
class Deletion:
    """What an advice deletes: whole units (("paragraph" | "sentence", index)), quoted
    passages, and the unit kind of a whole-unit deletion that could not be pinned down."""

    units: set = field(default_factory=set)
    passages: list = field(default_factory=list)
    unsure: str | None = None

    def texts(self, essay: str) -> list[str]:
        paragraphs = essay_lib.split_paragraphs(essay)
        sentences = [s.text for s in essay_lib.split_sentences(essay)]
        units = [paragraphs[i] if k == "paragraph" else sentences[i] for k, i in sorted(self.units)]
        return units + list(self.passages)

    def words(self, essay: str) -> int:
        """Words deleted, each counted once: everything is mapped to word positions in
        the essay and merged ("删去最后一段；删去最后一句" when the last paragraph is one
        sentence deletes 23 words, not 46 - recheck 2026-11-08)."""
        layout = _Layout(essay)
        deleted: set[int] = set()
        for kind, index in self.units:
            deleted |= layout.unit(kind, index)
        for passage in self.passages:
            deleted |= layout.passage(passage, deleted)
        return len(deleted)


class _Layout:
    """Word positions of the essay's paragraphs, sentences and passages."""

    def __init__(self, essay: str):
        text = essay_lib.normalize_newlines(essay)
        self.words = [(m.start(), m.group().lower()) for m in essay_lib.WORD_RE.finditer(text)]
        self.paragraphs, offset = [], 0
        for line in text.split("\n"):
            if line.strip():
                start = offset + len(line) - len(line.lstrip())
                self.paragraphs.append((start, start + len(line.strip())))
            offset += len(line) + 1
        self.sentences, cursor = [], {}
        for sentence in essay_lib.split_sentences(essay):
            low, high = self.paragraphs[sentence.paragraph]
            start = text.find(sentence.text, cursor.get(sentence.paragraph, low), high)
            if start < 0:
                start, end = low, high  # not found as such: its whole paragraph
            else:
                end = start + len(sentence.text)
                cursor[sentence.paragraph] = end
            self.sentences.append((start, end))

    def _between(self, start: int, end: int) -> set[int]:
        return {i for i, (pos, _w) in enumerate(self.words) if start <= pos < end}

    def unit(self, kind: str, index: int) -> set[int]:
        spans = self.paragraphs if kind == "paragraph" else self.sentences
        return self._between(*spans[index])

    def passage(self, passage: str, deleted: set[int]) -> set[int]:
        """One occurrence of the passage: inside what is already deleted if it is
        there, else the first one."""
        wanted = [w.lower() for w in essay_lib.WORD_RE.findall(passage)]
        if not wanted:
            return set()
        words = [w for _pos, w in self.words]
        hits = [
            set(range(i, i + len(wanted)))
            for i in range(len(words) - len(wanted) + 1)
            if words[i : i + len(wanted)] == wanted
        ]
        return next((h for h in hits if h <= deleted), hits[0] if hits else set())


def _clauses(advice: str) -> list[tuple[str, list[str]]]:
    """[(clause with each quoted passage replaced by a hole, the passages)]."""
    quoted: list[str] = []

    def hole(match):
        quoted.append(next(g for g in match.groups() if g is not None))
        return f"\x00{len(quoted) - 1}\x00"

    masked = _QUOTE_RE.sub(hole, advice)
    return [
        (clause, [quoted[int(n)] for n in _HOLE_RE.findall(clause)])
        for clause in _CLAUSE_RE.split(masked)
    ]


def _scope(clause: str, verb_end: int) -> str | None:
    """ "passage", "paragraph", "sentence", "mixed" (both unit words) or None."""
    tail = clause[verb_end:]
    if _CJK_RE.search(clause):
        if _CN_TAIL_PASSAGE_RE.search(tail):
            return "passage"
        unit = _CN_TAIL_UNIT_RE.search(tail)
        if unit:
            kind = "sentence" if unit.group(1).startswith("句") else "paragraph"
        elif _CN_PARTIAL_RE.search(tail) or _HOLE_RE.search(tail):
            return "passage"
        else:
            return None
    else:
        head = _EN_HEAD_RE.search(tail)
        if not head or not head.group(2):
            return "passage" if head else None
        kind = "sentence" if head.group(2).lower().startswith("sentence") else "paragraph"
    other = _PARAGRAPH_WORD_RE if kind == "sentence" else _SENTENCE_WORD_RE
    return "mixed" if other.search(_HOLE_RE.sub(" ", tail)) else kind


def _named(clause: str, kind: str, count: int):
    """The unit index a clause names: an int, None (none named), "conflict" (several)
    or "invalid" (one that does not exist, e.g. 第九段 in a five-paragraph essay)."""
    text = _HOLE_RE.sub(" ", clause)
    named, invalid = set(), False
    if kind == "paragraph":
        if _LAST_PARAGRAPH_RE.search(text):
            named.add(count - 1)
        if _FIRST_PARAGRAPH_RE.search(text):
            named.add(0)
        for cn, digits, english in _NTH_PARAGRAPH_RE.findall(text):
            n = _CN_NUMBERS.get(cn) or (int(cn) if cn.isdigit() else 0)
            n = n or (int(digits) if digits else 0) or _EN_ORDINALS.get(english.lower(), 0)
            if 1 <= n <= count:
                named.add(n - 1)
            else:
                invalid = True
    else:
        if _LAST_SENTENCE_RE.search(text):
            named.add(count - 1)
        if _FIRST_SENTENCE_RE.search(text):
            named.add(0)
    if invalid:
        return "invalid"
    if len(named) > 1:
        return "conflict"
    return named.pop() if named else None


def _negated(clause: str, verb_start: int) -> bool:
    text = clause.replace("’", "'")
    return any(m.start() < verb_start for m in _NEGATION_RE.finditer(text))


def _where(units: list[str], text: str) -> set[int]:
    return {i for i, unit in enumerate(units) if essay_lib.contains_quote(unit, text)}


def analyse(advice: str | None, quote: str | None, essay: str) -> Deletion | None:
    """What the advice deletes, or None when it deletes nothing that can be located."""
    if not advice or not _VERB_RE.search(advice):
        return None
    paragraphs = essay_lib.split_paragraphs(essay)
    sentences = [s.text for s in essay_lib.split_sentences(essay)]
    quote_ok = bool(quote) and essay_lib.contains_quote(essay, quote)
    result, found = Deletion(), False
    for clause, quoted in _clauses(advice):
        verb = _VERB_RE.search(clause)
        if not verb or _negated(clause, verb.start()):
            continue
        passages = [p for p in quoted if essay_lib.contains_quote(essay, p)]
        scope = _scope(clause, verb.end())
        if scope == "passage":
            result.passages += passages
            found = found or bool(passages)
            continue
        if scope == "mixed":  # "删去第二段的最后一句"
            result.unsure, found = "sentence", True
            continue
        if scope is None:
            continue  # "删去后结构更紧凑": nothing to delete is named
        units = paragraphs if scope == "paragraph" else sentences
        named = _named(clause, scope, len(units))
        candidates = None
        for passage in passages:
            where = _where(units, passage)
            candidates = where if candidates is None else candidates & where
        if named in ("conflict", "invalid"):
            candidates = set()  # a stated target is never replaced by another one
        elif named is not None:
            candidates = {named} if candidates is None else candidates & {named}
        elif quoted and not passages:
            candidates = set()  # it quotes a passage that is not in the essay
        if candidates is None:  # the clause names nothing: the issue's own quote
            if not quote_ok:
                continue
            candidates = _where(units, quote)
        if len(candidates) == 1:
            result.units.add((scope, candidates.pop()))
        else:
            result.unsure = scope
        found = True
    return result if found else None


def note(advice: str, quote: str | None, essay: str, minimum: int) -> tuple[str | None, str]:
    """(advice with a length note, "sure" | "unsure"), or (None, "") if none is needed."""
    found = analyse(advice, quote, essay)
    if found is None:
        return None, ""
    total = essay_lib.count_words(essay)
    remaining = total - found.words(essay)
    if found.unsure:
        units = (
            essay_lib.split_paragraphs(essay)
            if found.unsure == "paragraph"
            else [s.text for s in essay_lib.split_sentences(essay)]
        )
        largest = max((essay_lib.count_words(u) for u in units), default=0)
        if remaining - largest >= minimum:
            return None, ""
        return (
            f"{advice}（注意：如按建议删去整段 / 整句，请先确认删后仍不少于 {minimum} 词；"
            "本工具无法确定要删的是哪一部分，没有计算字数。）",
            "unsure",
        )
    if remaining >= minimum:
        return None, ""
    return (
        f"{advice}（注意：按本工具计数，按建议删去后约剩 {remaining} 词，低于 {minimum} "
        "词下限，应改写或合并，并保持字数。）",
        "sure",
    )


def annotate(criteria, argument, priorities: list[str], essay: str, minimum: int) -> dict:
    """Append length notes to every advice that would go below the minimum (in place).
    Returns {"sure": n, "unsure": m}."""
    counts = {"sure": 0, "unsure": 0}
    entries = [i for c in criteria for i in c["issues"]]
    if argument:
        entries += list(argument.get("problems") or []) + list(argument.get("improvements") or [])
    for entry in entries:
        updated, kind = note(entry.get("suggestion") or "", entry.get("quote"), essay, minimum)
        if updated:
            entry["suggestion"] = updated
            counts[kind] += 1
    for n, text in enumerate(priorities):
        updated, kind = note(text, None, essay, minimum)
        if updated:
            priorities[n] = updated
            counts[kind] += 1
    return counts
