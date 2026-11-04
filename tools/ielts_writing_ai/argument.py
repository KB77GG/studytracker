"""Task 2 argument-structure analysis: verification and labels.

The model maps the essay's argument (position, what each paragraph argues, and any
logic problems). Nothing is scored separately: the findings explain TR and CC, so the
band scale stays the official one. As with all evidence, every quote must be found
in the student's essay; unverifiable items are dropped and counted, never shown as
findings. Problem types come from a fixed list so they can be counted and compared.

Vocabulary follows the main system's model-topic library (论点 → 机制 → 例子 → 结果 →
边界), so students meet the same concepts in both places.
"""

from __future__ import annotations

from . import essay as essay_lib

PROBLEM_TYPES = {
    "unclear_position": "立场不清或前后不一致",
    "off_position": "分论点偏离立场或题目",
    "unsupported": "论点缺少解释或支撑",
    "example_not_linked": "例子没有回扣论点",
    "circular": "循环论证",
    "overgeneralized": "过度概括",
    "concession_unanswered": "让步后没有反驳",
    "concession_undermines": "让步削弱了自己的立场",
    "conclusion_inconsistent": "结尾与立场不一致",
    "irrelevant": "包含与论证无关的内容",
}
ROLES = {
    "introduction": "开头",
    "body": "主体段",
    "concession": "让步段",
    "conclusion": "结尾",
}
VERDICTS = {
    "supports": "服务于立场",
    "weak": "与立场关联偏弱",
    "off_position": "偏离立场或题目",
}
MAX_PARAGRAPHS = 8
MAX_PROBLEMS = 6
QUOTE_LIMIT = 400


class ArgumentInvalid(ValueError):
    pass


def _text(value, limit: int = 600) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def _enum(value, allowed: dict) -> str | None:
    """The value if it is one of the allowed strings. Model JSON may put a list or an
    object here; those must never reach a dict lookup (they are unhashable)."""
    return value if isinstance(value, str) and value in allowed else None


def _verified_quote(value, essay: str) -> str | None:
    """The quote, verified in full and only then shortened for display, so an
    invented ending after a real prefix is never accepted."""
    if not isinstance(value, str) or not value.strip():
        return None
    quote = value.strip()
    if not essay_lib.contains_quote(essay, quote):
        return None
    return quote[:QUOTE_LIMIT]


def _entries(value) -> tuple[list, int]:
    """(entries, malformed): missing/null means none; anything that is not a list
    (a bare object or string) counts as one malformed entry."""
    if value is None:
        return [], 0
    if isinstance(value, list):
        return value, 0
    return [], 1


def normalize(raw, essay: str) -> dict:
    """Validate the model's argument map against the essay.

    Every entry the model returned (the position, each paragraph, each problem) is
    counted exactly once, so returned == kept + dropped + duplicates + over_limit:
    - dropped: malformed (not an object, wrong type, unknown enum, missing text) or
      its quote is not in the essay;
    - duplicates: a problem repeated with the same type and quote;
    - over_limit: valid but beyond MAX_PARAGRAPHS / MAX_PROBLEMS.

    Raises ArgumentInvalid if the map is missing or has no verified paragraph (the
    evaluation is then retried like any other incomplete output). Invalid entries
    alone never reject the rest.
    """
    if not isinstance(raw, dict):
        raise ArgumentInvalid("缺少论证结构分析")
    returned = dropped = duplicates = 0

    position = None
    pos = raw.get("position")
    if pos is not None:
        returned += 1
        quote = _verified_quote(pos.get("quote"), essay) if isinstance(pos, dict) else None
        if quote:
            consistent = pos.get("consistent")
            position = {
                "quote": quote,
                "consistent": consistent if isinstance(consistent, bool) else None,
                "comment": _text(pos.get("comment")),
            }
        else:
            dropped += 1

    paragraphs = []
    entries, malformed = _entries(raw.get("paragraphs"))
    returned += len(entries) + malformed
    dropped += malformed
    for item in entries:
        item = item if isinstance(item, dict) else {}
        role = _enum(item.get("role"), ROLES)
        verdict = _enum(item.get("verdict"), VERDICTS)
        quote = _verified_quote(item.get("main_point"), essay) if role and verdict else None
        if not quote:
            dropped += 1
            continue
        paragraphs.append(
            {
                "role": role,
                "role_label": ROLES[role],
                "main_point": quote,
                "verdict": verdict,
                "verdict_label": VERDICTS[verdict],
                "comment": _text(item.get("comment")),
            }
        )

    problems = []
    entries, malformed = _entries(raw.get("problems"))
    returned += len(entries) + malformed
    dropped += malformed
    for item in entries:
        item = item if isinstance(item, dict) else {}
        kind = _enum(item.get("type"), PROBLEM_TYPES)
        comment = _text(item.get("comment"))
        quote = _verified_quote(item.get("quote"), essay) if kind and comment else None
        if not quote:
            dropped += 1
            continue
        if any(p["type"] == kind and p["quote"] == quote for p in problems):
            duplicates += 1  # same finding repeated; shown once, not an error
            continue
        problems.append(
            {
                "type": kind,
                "label": PROBLEM_TYPES[kind],
                "quote": quote,
                "comment": comment,
                "suggestion": _text(item.get("suggestion")),
            }
        )

    if not paragraphs:
        raise ArgumentInvalid("论证结构分析没有给出可核实的段落中心句")
    over_limit = max(0, len(paragraphs) - MAX_PARAGRAPHS) + max(0, len(problems) - MAX_PROBLEMS)
    paragraphs, problems = paragraphs[:MAX_PARAGRAPHS], problems[:MAX_PROBLEMS]
    kept = (1 if position else 0) + len(paragraphs) + len(problems)
    return {
        "position": position,
        "paragraphs": paragraphs,
        "problems": problems,
        "returned": returned,
        "kept": kept,
        "dropped": dropped,
        "duplicates": duplicates,
        "over_limit": over_limit,
    }


def problem_types(argument: dict | None) -> list[str]:
    return [p["type"] for p in (argument or {}).get("problems") or []]
