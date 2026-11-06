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


def split_en_numbers(text: str) -> list[tuple[int, int, str]]:
    """[(start, end, value)] for each separate number in a run of number words.

    A small grammar, not word-by-word addition (reviews of 1c865eb and 597b212):
    - a group is 1-999: "forty-two", "one hundred and twenty-five", "a hundred";
    - groups combine through strictly decreasing scale words ("one million two hundred
      and thirty-four thousand five hundred and sixty-seven");
    - "and" joins only the final part under 100 ("one hundred and twenty", "two
      thousand and twenty"). Anything else after "and" - or a part followed by its own
      "hundred" or scale word - starts a new number: "forty and fifty", "one hundred and
      two hundred", "one thousand and two thousand" are lists, never sums.
    """
    words = [(m.start(), m.end(), m.group().lower()) for m in re.finditer(r"[A-Za-z]+", text)]
    n = len(words)

    def word(i):
        return words[i][2] if i < n else ""

    def multiplier_at(i):
        return word(i) == "hundred" or word(i) in _EN_SCALES

    def below_hundred(i):
        """(value, next) for tens[-unit] | teen | unit, else None."""
        value = _EN_UNITS.get(word(i))
        if value is None:
            return None
        if 20 <= value <= 90 and value % 10 == 0:
            unit = _EN_UNITS.get(word(i + 1))
            if unit is not None and 1 <= unit <= 9:
                return value + unit, i + 2
        return value, i + 1

    def group(i):
        """(value 1-999, next) or None."""
        if word(i) == "a" and multiplier_at(i + 1):
            if word(i + 1) != "hundred":
                return 1, i + 1  # "a thousand": the scale is applied by the caller
            hundreds, k = 100, i + 2
        else:
            head = below_hundred(i)
            if head is None:
                return None
            value, k = head
            if word(k) != "hundred" or value > 99 or value == 0:
                return value, k
            hundreds, k = value * 100, k + 1
        # The tail of a hundred group: "and twenty", "five" - unless it is followed by
        # its own hundred / scale word, which makes it the start of another number.
        start = k + 1 if word(k) == "and" else k
        tail = below_hundred(start)
        if tail and word(tail[1]) != "hundred":  # "two hundred and thirty-four thousand"
            return hundreds + tail[0], tail[1]
        return hundreds, k

    numbers, i = [], 0
    while i < n:
        first = group(i)
        if first is None:
            i += 1  # "and", or a word that is not part of a number
            continue
        total, (value, j), last_scale = 0, first, None
        while True:
            scale = _EN_SCALES.get(word(j))
            if scale and (last_scale is None or scale < last_scale):
                total, last_scale, j = total + value * scale, scale, j + 1
                if word(j) == "and":  # only a final part under 100 may follow "and"
                    tail = below_hundred(j + 1)
                    if tail and not multiplier_at(tail[1]):
                        total, j = total + tail[0], tail[1]
                    break
                nxt = group(j)
                if nxt is None:
                    break
                after = _EN_SCALES.get(word(nxt[1]))
                if after and after >= last_scale:
                    break  # "one thousand two thousand": a new number
                value, j = nxt
                if not after:
                    total += value
                    break
                continue
            total += value
            break
        numbers.append((words[i][0], words[j - 1][1], str(total)))
        i = j
    return numbers


# A four-digit number is a year only with positive evidence - a temporal word before
# it ("in 2000", "from 1800 to 1900", "between 2000 and 2020"), 年 after it, a
# 2000-2020 range, or being joined to a year - and nothing marking it as a quantity:
# a plural noun or a Chinese measure word right after it ("2000 buses", "from 2000 to
# 2020 buses", "2000辆"); a quantity also makes the other end of its range a quantity.
_YEAR_BEFORE_RE = re.compile(
    r"\b(?:in|from|to|by|since|until|till|between|during|before|after|through|of|around)\s+$",
    re.IGNORECASE,
)
_RANGE_JOIN_RE = re.compile(r"^\s*(?:and|to|-|–|—|~|～|至|到|和|与)\s*$", re.IGNORECASE)
_NOT_PLURAL = {
    "was", "has", "is", "its", "this", "his", "as", "us", "thus", "plus", "less",
    "across", "always", "perhaps", "whereas", "besides", "towards", "afterwards",
    "onwards", "upwards", "downwards", "respectively",
}  # fmt: skip
_IRREGULAR_PLURAL = {"people", "children", "men", "women", "staff", "police", "cattle"}


def _counted_after(text: str, end: int) -> bool:
    """A count noun or measure word right after a number: it is a quantity."""
    follow = text[end : end + 40]
    if follow[:1] and "一" <= follow[0] <= "鿿":
        return follow[0] not in "年和与至到"
    match = re.match(r"\s+([A-Za-z]+)", follow)
    if not match:
        return False
    noun = match.group(1).lower()
    if noun in _IRREGULAR_PLURAL:
        return True
    return (
        len(noun) > 3 and noun.endswith("s") and not noun.endswith("ss") and noun not in _NOT_PLURAL
    )


def confirmed_years(text: str | None) -> set[int]:
    text = text or ""
    rows = []  # [start, end, value, evidence, quantity, joined_to_previous]
    for match in re.finditer(r"(?<![\d.,])\d{4}(?![\d.,]\d)", text):
        value = int(match.group())
        previous = rows[-1] if rows else None
        joined = bool(previous and _RANGE_JOIN_RE.match(text[previous[1] : match.start()]))
        evidence = (
            bool(_YEAR_BEFORE_RE.search(text[max(0, match.start() - 20) : match.start()]))
            or text[match.end() : match.end() + 1] == "年"
            or bool(re.match(r"\s*[-–—~～]\s*\d{4}\b", text[match.end() :]))
            or bool(joined and previous[3])
        )
        rows.append(
            [match.start(), match.end(), value, evidence, _counted_after(text, match.end()), joined]
        )
    for n in range(len(rows) - 1, 0, -1):  # a quantity at one end makes its range a quantity
        if rows[n][5] and rows[n][4]:
            rows[n - 1][4] = True
    for n in range(1, len(rows)):
        if rows[n][5] and rows[n - 1][4]:
            rows[n][4] = True
    return {
        value
        for _start, _end, value, evidence, quantity, _joined in rows
        if 1000 <= value <= 2100 and evidence and not quantity
    }


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
        # A coordinated run ("forty and fifty percent") shares what follows it.
        kind, shown_end = _kind(text, match.end(), text[: match.start()])
        parts = split_en_numbers(match.group())
        for n, (start, end, raw_value) in enumerate(parts):
            value, part_kind = _years(raw_value, kind)
            last = n == len(parts) - 1
            shown = text[match.start() + start : shown_end if last else match.start() + end]
            found.append((match.start() + start, value, part_kind, shown.strip()))
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
        # The task's own numbers (word count, minimum length) back word / plain targets
        # ("expand to 250 words") but never a time span: a 20-word essay is no source
        # for "twenty years later".
        self.task_numbers = {_value(str(n)) for n in numbers if n is not None}
        # Spans between two years the input gives ("2000 ... 2020" -> 20 years), so
        # "twenty years later" is derived from the source, not invented.
        years = sorted(confirmed_years(self.text))
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
                sourced = value in self.values or value in self.task_numbers or float(value) < SMALL
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
