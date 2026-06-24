"""Answer normalization and accepted variants for vocabulary practice."""

import json
import re


_PART_OF_SPEECH_RE = re.compile(
    r"^(?:n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.\s*", re.IGNORECASE
)
_PART_OF_SPEECH_PREFIX_RE = re.compile(
    r"^(?:(?:n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.\s*"
    r"(?:(?:[/／,，;；、&])|\bor\b)?\s*)+",
    re.IGNORECASE,
)
_VARIANT_SPLIT_RE = re.compile(r"\s*(?:[/≈；;]|,(?=\s*[a-zA-Z]))\s*")


def strip_part_of_speech_prefix(value):
    text = str(value or "").strip()
    cleaned = _PART_OF_SPEECH_PREFIX_RE.sub("", text).strip()
    cleaned = re.sub(r"^(?:[/／,，;；、-]\s*)+", "", cleaned).strip()
    return cleaned


def normalize_english_answer(value):
    text = str(value or "").strip().lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = re.sub(r"\.{3,}|…+", " ", text)
    text = re.sub(r"[，,。.!！？?；;：:()（）]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_answer_variants(value):
    """Parse a JSON list or a delimiter-separated answer string."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        source = str(value).strip()
        if not source:
            return []
        raw_items = None
        if source.startswith("["):
            try:
                decoded = json.loads(source)
                if isinstance(decoded, list):
                    raw_items = decoded
            except (TypeError, ValueError):
                pass
        raw_items = raw_items if raw_items is not None else _VARIANT_SPLIT_RE.split(source)

    variants = []
    seen = set()
    for raw in raw_items:
        without_part_of_speech = strip_part_of_speech_prefix(raw)
        normalized = normalize_english_answer(without_part_of_speech)
        if normalized and normalized not in seen:
            variants.append(normalized)
            seen.add(normalized)
    return variants


def accepted_english_answers(canonical, accepted_answers=None):
    variants = set(parse_answer_variants(canonical))
    variants.update(parse_answer_variants(accepted_answers))
    return sorted(variants)


def is_english_answer_correct(answer, canonical, accepted_answers=None):
    normalized = normalize_english_answer(answer)
    return bool(normalized) and normalized in accepted_english_answers(
        canonical,
        accepted_answers=accepted_answers,
    )


def normalize_chinese_answer(value):
    text = str(value or "").strip().lower()
    text = _PART_OF_SPEECH_RE.sub("", text)
    text = re.sub(r"[()（）【】\[\]「」『』\"'`]", "", text)
    text = re.sub(r"[，,。.!！？?：:\s]", "", text)
    return text


def is_chinese_answer_correct(answer, translation):
    normalized = normalize_chinese_answer(answer)
    if not normalized:
        return False
    source = str(translation or "").replace("\r", "").replace("\n", "；")
    variants = {
        normalize_chinese_answer(part)
        for part in re.split(r"\s*(?:[；;、/]|,(?=[\u4e00-\u9fff]))\s*", source)
    }
    variants.discard("")
    full = normalize_chinese_answer(source)
    if full:
        variants.add(full)
    return any(
        normalized == variant
        or (
            len(normalized) >= 2
            and (normalized in variant or variant in normalized)
        )
        for variant in variants
    )


def serialize_answer_variants(value):
    variants = parse_answer_variants(value)
    return json.dumps(variants, ensure_ascii=True) if variants else None
