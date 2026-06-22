"""Answer normalization and accepted variants for vocabulary practice."""

import json
import re


REGIONAL_SPELLING_PAIRS = (
    ("behavior", "behaviour"),
    ("color", "colour"),
    ("favor", "favour"),
    ("favorite", "favourite"),
    ("flavor", "flavour"),
    ("harbor", "harbour"),
    ("honor", "honour"),
    ("humor", "humour"),
    ("labor", "labour"),
    ("neighbor", "neighbour"),
    ("rumor", "rumour"),
    ("center", "centre"),
    ("fiber", "fibre"),
    ("liter", "litre"),
    ("meter", "metre"),
    ("theater", "theatre"),
    ("catalog", "catalogue"),
    ("dialog", "dialogue"),
    ("gray", "grey"),
    ("jewelry", "jewellery"),
    ("license", "licence"),
    ("practice", "practise"),
    ("program", "programme"),
    ("traveling", "travelling"),
    ("traveled", "travelled"),
    ("traveler", "traveller"),
    ("modeling", "modelling"),
    ("modeled", "modelled"),
    ("canceled", "cancelled"),
    ("canceling", "cancelling"),
    ("analyze", "analyse"),
    ("organize", "organise"),
    ("recognize", "recognise"),
)

# Only include pairs that are interchangeable for a plain vocabulary prompt.
COMMON_SYNONYM_GROUPS = (
    ("bike", "bicycle"),
    ("bikes", "bicycles"),
)

_PART_OF_SPEECH_RE = re.compile(
    r"^(?:n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.\s*", re.IGNORECASE
)
_VARIANT_SPLIT_RE = re.compile(r"\s*(?:[/≈；;]|,(?=\s*[a-zA-Z]))\s*")


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
        without_part_of_speech = _PART_OF_SPEECH_RE.sub("", str(raw or "").strip())
        normalized = normalize_english_answer(without_part_of_speech)
        if normalized and normalized not in seen:
            variants.append(normalized)
            seen.add(normalized)
    return variants


def _expand_equivalent_groups(variants, groups):
    expanded = set(variants)
    changed = True
    while changed:
        changed = False
        for group in groups:
            normalized_group = {normalize_english_answer(item) for item in group}
            if expanded.intersection(normalized_group) and not normalized_group.issubset(expanded):
                expanded.update(normalized_group)
                changed = True
    return expanded


def accepted_english_answers(canonical, accepted_answers=None, allow_synonyms=False):
    variants = set(parse_answer_variants(canonical))
    variants.update(parse_answer_variants(accepted_answers))
    variants = _expand_equivalent_groups(variants, REGIONAL_SPELLING_PAIRS)
    if allow_synonyms:
        variants = _expand_equivalent_groups(variants, COMMON_SYNONYM_GROUPS)
    return sorted(variants)


def is_english_answer_correct(answer, canonical, accepted_answers=None, allow_synonyms=False):
    normalized = normalize_english_answer(answer)
    return bool(normalized) and normalized in accepted_english_answers(
        canonical,
        accepted_answers=accepted_answers,
        allow_synonyms=allow_synonyms,
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
