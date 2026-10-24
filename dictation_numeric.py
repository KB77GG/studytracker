"""Conservative, version-one answer rules for *new* numeric dictation snapshots.

This module never rewrites a catalog word or an existing answer snapshot. Callers
opt in by saving ``answer_type=numeric`` with its kind. Ordinary English keeps
the existing vocabulary parser. Unsupported numeric text uses literal matching.
"""

import calendar
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from dictation_answers import parse_vocabulary_word_variants

_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = ("zero ten twenty thirty forty fifty sixty seventy eighty ninety").split()
_ORDINAL = {
    1: "first",
    2: "second",
    3: "third",
    4: "fourth",
    5: "fifth",
    6: "sixth",
    7: "seventh",
    8: "eighth",
    9: "ninth",
    10: "tenth",
    11: "eleventh",
    12: "twelfth",
    13: "thirteenth",
    14: "fourteenth",
    15: "fifteenth",
    16: "sixteenth",
    17: "seventeenth",
    18: "eighteenth",
    19: "nineteenth",
    20: "twentieth",
    30: "thirtieth",
}
_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
_MONTHS["sept"] = 9
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_NUMBER = re.compile(r"^[+-]?(?:(?:\d+|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?|\.\d+)$")
_CURRENCY = {
    "$": ("USD", "dollar", "cent"),
    "usd": ("USD", "dollar", "cent"),
    "dollar": ("USD", "dollar", "cent"),
    "dollars": ("USD", "dollar", "cent"),
    "£": ("GBP", "pound", "penny"),
    "gbp": ("GBP", "pound", "penny"),
    "pound": ("GBP", "pound", "penny"),
    "pounds": ("GBP", "pound", "penny"),
    "€": ("EUR", "euro", "cent"),
    "eur": ("EUR", "euro", "cent"),
    "euro": ("EUR", "euro", "cent"),
    "euros": ("EUR", "euro", "cent"),
}
_CURRENCY_RE = "|".join(re.escape(k) for k in sorted(_CURRENCY, key=len, reverse=True))
_HINTS = {
    "number": "输入数字，保留小数点及负号；可省略千位分隔逗号。",
    "percentage": "输入百分数，保留 % 或 percent。",
    "currency": "输入金额和货币符号或名称。",
    "date": "输入明确月份名的日期；有年份时也可用 YYYY-MM-DD。",
    "time": "输入时间；上午、下午可用 AM/PM 或对应的24小时制。",
    "digit_sequence": "逐位输入完整号码，保留开头的0；可使用空格或连字符分组。",
    "literal": "按原格式输入，保留数字、单位和标点；不自动推断歧义格式。",
}


def _text(value):
    raw = "" if value is None else str(value)
    # Fullwidth ASCII is only presentation. NFKC is too broad: it turns 10²
    # into 102 and circled digits into ordinary digits, changing the answer.
    narrow = "".join(chr(ord(c) - 0xFEE0) if "\uff01" <= c <= "\uff5e" else c for c in raw)
    return " ".join(narrow.split())


def _integer_words(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")
    for size, label in (
        (10**12, "trillion"),
        (10**9, "billion"),
        (10**6, "million"),
        (1000, "thousand"),
        (100, "hundred"),
    ):
        if n >= size:
            return (
                _integer_words(n // size)
                + " "
                + label
                + (" " + _integer_words(n % size) if n % size else "")
            )
    raise ValueError("Invalid integer")


def _number(value):
    text = _text(value)
    if not _NUMBER.fullmatch(text) or len(text) > 100:
        return None
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None


def _number_words(value):
    text = _text(value).replace(",", "")
    sign = "minus " if text.startswith("-") else ""
    text = text.lstrip("+-")
    whole, dot, fraction = text.partition(".")
    spoken = sign + _integer_words(int(whole or "0"))
    return spoken + (" point " + " ".join(_ONES[int(d)] for d in fraction) if dot else "")


def _digit_sequence(value):
    text = _text(value)
    if not re.fullmatch(r"\+?(?:\([0-9]+\)|[0-9]+)(?:[ -]*(?:\([0-9]+\)|[0-9]+))*", text):
        return None
    compact = re.sub(r"[ ()-]", "", text)
    digits = compact.lstrip("+")
    if len(digits) >= 8 or (len(digits) > 1 and digits.startswith("0")):
        return compact
    return None


def _percentage(value):
    match = re.fullmatch(r"(.+?)\s*(?:%|percent|per cent)", _text(value), re.I)
    return _number(match[1]) if match else None


def _currency(value):
    text = _text(value)
    match = re.fullmatch(rf"({_CURRENCY_RE})\s*(.+)", text, re.I)
    if match:
        unit, amount = match[1].lower(), match[2]
    else:
        match = re.fullmatch(rf"(.+?)\s*({_CURRENCY_RE})", text, re.I)
        if not match:
            return None
        amount, unit = match[1], match[2].lower()
    number = _number(amount)
    return (_CURRENCY[unit][0], number, amount, _CURRENCY[unit][1:]) if number is not None else None


def _date(value):
    text = _text(value)
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        year, month, day = map(int, iso.groups())
    else:
        match = re.fullmatch(
            rf"({_MONTH_RE})\.?\s+(\d{{1,2}})(st|nd|rd|th)?(?:,?\s+(\d{{4}}))?", text, re.I
        )
        if match:
            month_text, day_text, suffix, year_text = match.groups()
        else:
            match = re.fullmatch(
                rf"(\d{{1,2}})(st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})\.?(?:,?\s+(\d{{4}}))?",
                text,
                re.I,
            )
            if not match:
                return None
            day_text, suffix, month_text, year_text = match.groups()
        day, month = int(day_text), _MONTHS[month_text.lower()]
        year = int(year_text) if year_text else None
        wanted_suffix = (
            "th" if 10 < day % 100 < 14 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        )
        if suffix and suffix.lower() != wanted_suffix:
            return None
    try:
        date(2000 if year is None else year, month, day)
    except ValueError:
        return None
    return year, month, day


def _time(value):
    text = _text(value).lower()
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))\s*([ap]\.?m\.?)?", text)
    if match:
        hour, minute, meridian = int(match[1]), int(match[2]), match[3]
    else:
        match = re.fullmatch(r"(\d{1,4})(?:\.(\d{2}))?\s*([ap]\.?m\.?)", text)
        if not match:
            return None
        digits, minutes, meridian = match.groups()
        if minutes is not None and len(digits) <= 2:
            hour, minute = int(digits), int(minutes)
        elif minutes is None:
            hour, minute = (
                (int(digits), 0) if len(digits) <= 2 else (int(digits[:-2]), int(digits[-2:]))
            )
        else:
            return None
    if minute > 59 or (meridian and not 1 <= hour <= 12) or (not meridian and hour > 23):
        return None
    if meridian:
        hour = hour % 12 + (12 if meridian.startswith("p") else 0)
    return hour, minute


def _date_words(parsed):
    year, month, day = parsed
    ordinal = _ORDINAL.get(day) or _TENS[day // 10] + " " + _ORDINAL[day % 10]
    return calendar.month_name[month] + " " + ordinal + (" " + _integer_words(year) if year else "")


def _time_words(value, parsed):
    hour, minute = parsed
    meridian = re.search(r"([ap])\.?m\.?$", _text(value), re.I)
    if meridian:
        hour = hour % 12 or 12
    result = _integer_words(hour)
    if minute:
        result += " " + ("oh " if minute < 10 else "") + _integer_words(minute)
    elif not meridian:
        result += " o'clock"
    if meridian:
        result += " " + meridian[1].lower() + " m"
    return result


def _currency_words(parsed):
    _, number, amount, names = parsed
    major, minor = names
    raw = amount.replace(",", "").lstrip("+-")
    whole, dot, fraction = raw.partition(".")
    if len(fraction) > 2:
        return _number_words(amount) + " " + major + "s"
    integer = int(whole or "0")
    cents = int(fraction.ljust(2, "0")) if dot else 0
    result = (
        ("minus " if number < 0 else "")
        + _integer_words(integer)
        + " "
        + major
        + ("" if integer == 1 else "s")
    )
    if cents:
        plural = "pence" if minor == "penny" and cents != 1 else minor + ("" if cents == 1 else "s")
        result += " " + _integer_words(cents) + " " + plural
    return result


def _literal_speech(text):
    if re.fullmatch(r"\d{1,4}(?:[/:.-]\d{1,4}){1,2}", text):
        names = {"/": "slash", ":": "colon", ".": "point", "-": "dash"}
        return " ".join(_ONES[int(c)] if c.isdigit() else names[c] for c in text)
    return text


def classify_numeric_dictation(value):
    """Classify numeric answers without guessing locale, units or missing digits.

    ``canonical`` is the source answer, not a lossy key. Treat this metadata as
    server-only except for ``kind`` and ``input_hint``. No answer text may be
    included in a public question payload.
    """
    text = _text(value)
    if not text or len(text) > 100 or not re.search(r"[0-9]", text):
        return None
    parsed_date = _date(text)
    parsed_time = _time(text)
    parsed_currency = _currency(text)
    sequence = _digit_sequence(text)
    percentage = _percentage(text)
    if parsed_date is not None:
        kind, speech = "date", _date_words(parsed_date)
    elif parsed_time is not None:
        kind, speech = "time", _time_words(text, parsed_time)
    elif parsed_currency is not None:
        kind, speech = "currency", _currency_words(parsed_currency)
    elif re.fullmatch(r"\d{1,4}[-/]\d{1,2}(?:[-/]\d{1,4})?", text):
        # Invalid/ambiguous dates must not fall through to a digit identifier.
        kind, speech = "literal", _literal_speech(text)
    elif percentage is not None:
        number_text = re.sub(r"\s*(%|percent|per cent)$", "", text, flags=re.I)
        kind, speech = "percentage", _number_words(number_text) + " percent"
    elif sequence is not None:
        kind = "digit_sequence"
        speech = ("plus " if sequence.startswith("+") else "") + " ".join(
            _ONES[int(d)] for d in sequence.lstrip("+")
        )
    elif _number(text) is not None:
        kind, speech = "number", _number_words(text)
    elif parse_vocabulary_word_variants(text):
        return None
    else:
        # Unknown punctuation keeps its meaning; do not let TTS infer a locale
        # for short numeric strings that look like invalid dates or times.
        kind, speech = "literal", _literal_speech(text)
    return {"kind": kind, "canonical": text, "tts_text": speech, "input_hint": _HINTS[kind]}


def is_numeric_answer_correct(answer, canonical, kind=None):
    """Compare only clearly equivalent forms for the stored numeric kind.

    Explicit kind prevents a candidate from selecting a more permissive rule.
    There is no arbitrary punctuation deletion and no inferred alternatives.
    """
    expected, supplied = _text(canonical), _text(answer)
    if not supplied or len(supplied) > 200:
        return False
    classification = classify_numeric_dictation(expected)
    if classification is None or (kind is not None and kind != classification["kind"]):
        return False
    kind = classification["kind"]
    parsers = {
        "number": _number,
        "percentage": _percentage,
        "date": _date,
        "time": _time,
        "digit_sequence": _digit_sequence,
    }
    if kind in parsers:
        correct, received = parsers[kind](expected), parsers[kind](supplied)
        return received is not None and correct == received
    if kind == "currency":
        correct, received = _currency(expected), _currency(supplied)
        return received is not None and correct[:2] == received[:2]
    return expected.casefold() == supplied.casefold()
