"""Advice that deletes text, checked against the minimum length.

2026-11-07: "delete the 23-word conclusion" would have taken a 172-word Task 1 to 149
(minimum 150) without a word about it. Three reviews of keyword-based readings
(2026-11-08) kept finding neighbouring gaps - negations that belonged to another verb,
partial deletions that lost their paragraph, ordinals in an unexpected format that fell
back to the issue's quote - so the reading now follows one rule: a number is given only
when every deletion in the advice is located exactly; otherwise at most a reminder to
check the length, never a guessed count.

1. Actions. Quoted passages are masked first (paired “…” "…" ‘…’ '…'; an apostrophe
   between letters is not a quotation mark), so quoted advice deletes nothing. Every
   deletion verb outside quotes is one action; sentences, clauses and words such as
   因为 / 并 / because / and end its object.
2. Negation belongs to the verb it stands right before: 不要删去, 别删, 避免把这一段删去,
   don't / shouldn't / cannot delete, rather than delete. "This paragraph is not
   necessary and you should delete the conclusion" deletes the conclusion.
3. The object is read token by token against a closed list (determiners, positions,
   ordinals in any common format, unit nouns, quoted passages, a few particles). An
   object with anything else in it is not reliable. An object with no passage, unit or
   position names nothing to delete ("删去后结构更紧凑") and is ignored.
4. Each action becomes word positions in the essay: a whole paragraph / sentence, or a
   quoted passage found exactly once within the unit the action names ("第二段中的
   'Country A'"). Positions of all actions are merged, so the same words count once.
5. A target that is stated but does not resolve to exactly one place - out of range,
   conflicting, a passage found nowhere or in several places - is never replaced by the
   issue's quote. The issue's quote is used only for "this paragraph / 这一段".
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
_QUOTE_RE = re.compile(
    r"“([^”]{1,300})”|\"([^\"]{1,300})\"|‘(.{1,300}?)’(?![A-Za-z0-9])|"
    r"(?<![A-Za-z0-9])'(?=\S)(.{1,300}?)(?<=\S)'(?![A-Za-z0-9])"
)
_HOLE_RE = re.compile("\x00(\\d+)\x00")
# Sentence and clause boundaries; an English full stop only before a space or the end.
_BOUNDARY_RE = re.compile(r"[。；;！!？?，,：:\n]|(?<!e\.g)(?<!i\.e)\.(?=\s|$)")
_CN_STOP_RE = re.compile(
    r"因为|由于|以便|以免|使得|使|让|来|并且|并|然后|再|而|但|如果|若|否则|从而|这样"
)
_EN_STOP_RE = re.compile(
    r"\b(?:because|since|so|to|and|but|while|if|for|as|or|then|which means)\b", re.I
)
_EN_ALTERNATIVE_RE = re.compile(r"^\s*or\s+(?:rewrite|shorten|merge|condense)\s+", re.I)
_CN_ALTERNATIVE_RE = re.compile(r"^或(?:改写|重写|合并|压缩|精简|修改|改)")

# Negation right before the verb (a few adverbs, or a 把-phrase, may stand between).
_CN_NEGATION_RE = re.compile(
    r"(?:不要|不用|不必|无需|无须|不需要|不应|不宜|不该|不能|不可|没必要|不建议|避免|而不是|"
    r"切勿|千万别|别|勿|不)(?:再|直接|随意|随便|轻易|急于|全部|就)?(?:把[^，。；,;\x00]{1,15})?\s*$"
)
_EN_NEGATION_RE = re.compile(
    r"\b(?:not|never|dont|cannot|[a-z]+n't|avoid|no need to|instead of|rather than)"
    r"\s+(?:[a-z']+\s+){0,2}$",
    re.I,
)

_CN_TOKEN_RE = re.compile(
    r"\x00\d+\x00|第\s*\d+|第[一二三四五六七八九十]+|这一|这个|这|该|本|此|那|整个|整|全|"
    r"结尾|最后|末尾|最末|末|首|开头|开篇|引言|结论|段落|段|句子|句|中的|里的|中|里|的|个|"
    r"两|三|几|一|词语|单词|短语|词|即可|就好|就行|也可以|亦可|吧|掉|了|也|还|直接|整体|\s+"
)
_EN_WORDS = {
    "the", "this", "that", "a", "an", "whole", "entire", "your", "its", "writer's",
    "essay's", "student's", "beginning", "starting", "begins", "starts", "with", "of",
    "essay", "also", "then", "only", "from", "in", "which", "entirely", "completely",
    "altogether", "simply", "just",
}  # fmt: skip
_EN_TOKEN_RE = re.compile(r"\x00\d+\x00|[A-Za-z0-9']+")

_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "one": 1, "two": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}  # fmt: skip
_CN_DIGITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_LAST = {"结尾", "最后", "末尾", "最末", "末", "结论", "final", "last", "concluding", "closing",
         "conclusion"}  # fmt: skip
_FIRST = {"首", "开头", "开篇", "引言", "opening", "introductory", "introduction"}
_PARAGRAPH_NOUNS = {"段", "段落", "结论", "引言", "paragraph", "paragraphs", "conclusion",
                    "introduction"}  # fmt: skip
_SENTENCE_NOUNS = {"句", "句子", "sentence", "sentences"}
_PARTIAL = {"中的", "里的", "中", "里", "个", "词", "词语", "单词", "短语", "only", "from", "in",
            "word", "words", "phrase", "phrases"}  # fmt: skip
_DEMONSTRATIVES = {"这一", "这个", "这", "该", "本", "此", "整个", "整", "this", "that", "the",
                   "whole", "entire"}  # fmt: skip


class Unreliable(Exception):
    """The advice deletes something that cannot be located exactly."""


@dataclass
class Deletion:
    """What an advice deletes: word positions in the essay (merged), the texts they come
    from (diagnostics), and whether some deletion could not be located (no number)."""

    positions: set = field(default_factory=set)
    parts: list = field(default_factory=list)
    unsure: bool = False
    units: set = field(default_factory=set)  # (("paragraph" | "sentence"), index)
    passages: list = field(default_factory=list)  # quoted passages deleted as words

    def texts(self, essay: str) -> list[str]:
        return list(self.parts)

    def words(self, essay: str) -> int:
        return len(self.positions)


class _Layout:
    """Word positions of the essay, its paragraphs and its sentences."""

    def __init__(self, essay: str):
        text = essay_lib.normalize_newlines(essay)
        self.words = [(m.start(), m.group().lower()) for m in essay_lib.WORD_RE.finditer(text)]
        spans, offset = [], 0
        for line in text.split("\n"):
            if line.strip():
                start = offset + len(line) - len(line.lstrip())
                spans.append((start, start + len(line.strip())))
            offset += len(line) + 1
        self.paragraphs = [self._between(a, b) for a, b in spans]
        self.sentences, cursor = [], {}
        for sentence in essay_lib.split_sentences(essay):
            low, high = spans[sentence.paragraph]
            start = text.find(sentence.text, cursor.get(sentence.paragraph, low), high)
            if start < 0:  # not found as such: its whole paragraph
                self.sentences.append(set(self.paragraphs[sentence.paragraph]))
                continue
            cursor[sentence.paragraph] = start + len(sentence.text)
            self.sentences.append(self._between(start, start + len(sentence.text)))

    def _between(self, start: int, end: int) -> set[int]:
        return {i for i, (pos, _w) in enumerate(self.words) if start <= pos < end}

    def units(self, kind: str) -> list[set[int]]:
        return self.paragraphs if kind == "paragraph" else self.sentences

    def occurrences(self, passage: str) -> list[set[int]]:
        wanted = [w.lower() for w in essay_lib.WORD_RE.findall(passage)]
        words = [w for _pos, w in self.words]
        return [
            set(range(i, i + len(wanted)))
            for i in range(len(words) - len(wanted) + 1)
            if wanted and words[i : i + len(wanted)] == wanted
        ]

    def text_of(self, positions: set[int]) -> str:
        ordered = sorted(positions)
        return " ".join(self.words[i][1] for i in ordered)


def _mask(advice: str) -> tuple[str, list[str]]:
    quoted: list[str] = []

    def hole(match):
        quoted.append(next(g for g in match.groups() if g is not None))
        return f"\x00{len(quoted) - 1}\x00"

    return _QUOTE_RE.sub(hole, advice), quoted


def _actions(masked: str) -> list[tuple[str, str]]:
    """[(text before the verb within its clause, the verb's object)]."""
    out = []
    for segment in _BOUNDARY_RE.split(masked):
        verbs = list(_VERB_RE.finditer(segment))
        for n, verb in enumerate(verbs):
            before = segment[verbs[n - 1].end() if n else 0 : verb.start()]
            after = segment[verb.end() : verbs[n + 1].start() if n + 1 < len(verbs) else None]
            out.append((before, after))
    return out


def _negated(before: str) -> bool:
    text = before.replace("’", "'")
    return bool(_CN_NEGATION_RE.search(text) or _EN_NEGATION_RE.search(text))


def _object(before: str, after: str) -> str:
    """The object of the verb: what follows it, cut at a clause word; for 把X删去 the X."""
    chinese = bool(re.search(r"[一-鿿]", before + after))
    if chinese:
        after = _CN_ALTERNATIVE_RE.sub("", after.strip())
        stop = _CN_STOP_RE.search(after)
        obj = after[: stop.start()] if stop else after
        ba = before.rfind("把")
        if not obj.strip() and ba >= 0:
            obj = before[ba + 1 :]
        return obj
    after = _EN_ALTERNATIVE_RE.sub("", after)
    stop = _EN_STOP_RE.search(after)
    return after[: stop.start()] if stop else after


def _tokens(obj: str) -> list[str]:
    """The object's tokens, or Unreliable if anything is outside the closed list."""
    if re.search(r"[一-鿿]", _HOLE_RE.sub("", obj)):
        pos, tokens = 0, []
        while pos < len(obj):
            match = _CN_TOKEN_RE.match(obj, pos)
            if not match:
                raise Unreliable(obj[pos:])
            if match.group().strip():
                tokens.append(re.sub(r"\s+", "", match.group()))
            pos = match.end()
        return tokens
    tokens = []
    for match in _EN_TOKEN_RE.finditer(obj.replace("’", "'")):
        token = match.group()
        low = token.lower()
        if (
            _HOLE_RE.fullmatch(token)
            or low in _EN_WORDS
            or low in _ORDINALS
            or low in _LAST
            or low in _FIRST
            or low in _PARAGRAPH_NOUNS
            or low in _SENTENCE_NOUNS
            or low in _PARTIAL
            or re.fullmatch(r"\d+(?:st|nd|rd|th)?", low)
        ):
            tokens.append(token if _HOLE_RE.fullmatch(token) else low)
        else:
            raise Unreliable(token)
    leftover = _EN_TOKEN_RE.sub("", obj.replace("’", "'"))
    if re.search(r"[^\s\-–—]", leftover):
        raise Unreliable(leftover)
    return tokens


def _number(token: str) -> int | None:
    token = re.sub(r"\s+", "", token)
    if token.startswith("第"):
        rest = token[1:]
        if rest.isdigit():
            return int(rest)
        if rest == "十":
            return 10
        if len(rest) == 2 and rest[0] == "十":
            return 10 + _CN_DIGITS.get(rest[1], 0)
        return _CN_DIGITS.get(rest)
    match = re.fullmatch(r"(\d+)(?:st|nd|rd|th)?", token)
    if match:
        return int(match.group(1))
    return _ORDINALS.get(token)


def _position(tokens: list[str], count: int) -> int | None:
    """The 0-based unit index the tokens name, None if none; Unreliable if several
    different ones or one that does not exist."""
    named = set()
    for n, token in enumerate(tokens):
        if token in _LAST:
            named.add(count - 1)
        elif token in _FIRST or token == "first":
            named.add(0)
        else:
            number = _number(token)
            if number is None:
                continue
            # "paragraph 9" / "the ninth paragraph" / "第九段"; a bare "two" in
            # "两个词" is not a position.
            follows_unit = n and tokens[n - 1] in _PARAGRAPH_NOUNS | _SENTENCE_NOUNS
            precedes_unit = n + 1 < len(tokens) and tokens[n + 1] in _PARAGRAPH_NOUNS | (
                _SENTENCE_NOUNS
            )
            if not (token.startswith("第") or follows_unit or precedes_unit):
                continue
            if not 1 <= number <= count:
                raise Unreliable(f"no such unit: {token}")
            named.add(number - 1)
    if len(named) > 1:
        raise Unreliable("several positions")
    return named.pop() if named else None


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_NAMING_RE = re.compile(
    r"段|句|结论|引言|结尾|开头|开篇|首|末|最后|第|"
    r"\b(?:paragraphs?|sentences?|conclusion|introduction|final|last|first|opening|"
    r"concluding|closing|introductory|\d+(?:st|nd|rd|th)|"
    r"second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b",
    re.I,
)


def _names_something(obj: str, quoted: list[str]) -> bool:
    """Whether the object names anything to delete: a quoted essay passage, a unit or a
    position. Anything that does must then be read exactly."""
    holes = [quoted[int(n)] for n in _HOLE_RE.findall(obj)]
    return any(_english_words(h) for h in holes) or bool(_NAMING_RE.search(_HOLE_RE.sub(" ", obj)))


def _english_words(passage: str) -> bool:
    return bool(essay_lib.WORD_RE.search(passage))


_FILLERS = {"即可", "就好", "就行", "也可以", "亦可", "吧", "掉", "了", "也", "还"}
_PASSAGE_HEADS = {"词", "词语", "单词", "短语", "word", "words", "phrase", "phrases"}


def _head_is_passage(tokens: list[str], chinese: bool) -> bool:
    """What the verb deletes: in Chinese the head noun ends the phrase (结尾的“X”这一段
    is a paragraph, 句子开头的“X” is X); in English the first noun after the verb does
    (the paragraph beginning "X" is a paragraph, "X" from this sentence is X)."""
    if chinese:
        content = [t for t in tokens if t not in _FILLERS]
        return bool(content) and (
            bool(_HOLE_RE.fullmatch(content[-1])) or content[-1] in _PASSAGE_HEADS
        )
    for token in tokens:
        if _HOLE_RE.fullmatch(token) or token in _PASSAGE_HEADS:
            return True
        if token in _PARAGRAPH_NOUNS or token in _SENTENCE_NOUNS:
            return False
    return False


def _resolve(tokens, quoted, quote, layout, chinese):
    """(word positions one action deletes, what they are), (None, None) if it names
    nothing to delete; Unreliable if it cannot be located exactly."""
    holes = [quoted[int(m.group(1))] for t in tokens if (m := _HOLE_RE.fullmatch(t))]
    holes = [h for h in holes if _english_words(h)]  # a Chinese description is not a quote
    words = [t for t in tokens if not _HOLE_RE.fullmatch(t)]
    paragraph = any(t in _PARAGRAPH_NOUNS for t in words)
    sentence = any(t in _SENTENCE_NOUNS for t in words)
    partial = any(t in _PARTIAL for t in words) and not chinese  # Chinese: the head noun
    has_position = any(t in _LAST or t in _FIRST or _number(t) for t in words)
    if not (holes or paragraph or sentence or has_position):
        return None, None  # "删去后结构更紧凑": nothing named
    if holes and (partial or not (paragraph or sentence) or _head_is_passage(tokens, chinese)):
        return _passages(holes, words, paragraph, sentence, quote, layout), ("passage", holes)
    if not (paragraph or sentence):
        raise Unreliable("a position without a unit")
    if paragraph and sentence:
        raise Unreliable("both paragraph and sentence")
    kind = "paragraph" if paragraph else "sentence"
    units = layout.units(kind)
    named = (
        _position(words, len(units)) if kind == "paragraph" else _sentence_position(words, units)
    )
    candidates = None
    for hole in holes:
        where = _units_with(hole, units, layout)
        candidates = where if candidates is None else candidates & where
    if named is not None:
        candidates = {named} if candidates is None else candidates & {named}
    if candidates is None:  # "这一段" / "this paragraph": the issue's own quote
        if not quote:
            return None, None  # an unverified issue quote: nothing to count
        candidates = _units_with(quote, units, layout)
        if not candidates:
            return None, None
    if len(candidates) != 1:
        raise Unreliable("not exactly one unit")
    index = candidates.pop()
    return set(units[index]), (kind, index)


def _sentence_position(words, units) -> int | None:
    if any(t in _LAST for t in words):
        return len(units) - 1
    if any(t in _FIRST or t == "first" for t in words):
        return 0
    if any(_number(t) for t in words):
        raise Unreliable("the Nth sentence of what?")
    return None


def _units_with(text: str, units: list[set[int]], layout: _Layout) -> set[int]:
    hits = layout.occurrences(text)
    return {i for i, unit in enumerate(units) for hit in hits if hit <= unit}


def _passages(holes, words, paragraph, sentence, quote, layout) -> set[int]:
    """Quoted words, each found exactly once inside the unit the action names."""
    scope = None  # word positions the passage must lie in; None: the whole essay
    if paragraph:
        named = _position(words, len(layout.paragraphs))
        if named is not None:
            scope = layout.paragraphs[named]
        elif any(t in _DEMONSTRATIVES for t in words):
            scope = _quote_unit(quote, layout.paragraphs, layout)
    elif sentence:
        scope = _quote_unit(quote, layout.sentences, layout)
    deleted: set[int] = set()
    for hole in holes:
        hits = [h for h in layout.occurrences(hole) if scope is None or h <= scope]
        if len(hits) != 1:
            raise Unreliable(f"{hole!r} found {len(hits)} times")
        deleted |= hits[0]
    return deleted


def _quote_unit(quote, units, layout) -> set[int]:
    where = _units_with(quote, units, layout) if quote else set()
    if len(where) != 1:
        raise Unreliable("the unit of the issue's quote")
    return set(units[where.pop()])


def analyse(advice: str | None, quote: str | None, essay: str) -> Deletion | None:
    """What the advice deletes, or None when it deletes nothing that can be named."""
    if not advice or not _VERB_RE.search(advice):
        return None
    masked, quoted = _mask(advice)
    layout = _Layout(essay)
    result, found = Deletion(), False
    for before, after in _actions(masked):
        if _negated(before):
            continue
        obj = _object(before, after)
        if not _names_something(obj, quoted):
            continue  # "删去后结构更紧凑"
        chinese = bool(_CJK_RE.search(_HOLE_RE.sub("", obj)))
        try:
            positions, what = _resolve(_tokens(obj), quoted, quote, layout, chinese)
        except Unreliable:
            result.unsure = found = True
            continue
        if positions is None:
            continue
        found = True
        result.positions |= positions
        result.parts.append(layout.text_of(positions))
        if what[0] == "passage":
            result.passages += what[1]
        else:
            result.units.add(what)
    return result if found else None


def note(advice: str, quote: str | None, essay: str, minimum: int) -> tuple[str | None, str]:
    """(advice with a length note, "sure" | "unsure"), or (None, "") if none is needed."""
    found = analyse(advice, quote, essay)
    if found is None:
        return None, ""
    remaining = essay_lib.count_words(essay) - found.words(essay)
    if found.unsure:
        largest = max((len(p) for p in _Layout(essay).paragraphs), default=0)
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
