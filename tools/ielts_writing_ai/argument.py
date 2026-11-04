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


class ArgumentInvalid(ValueError):
    pass


def _text(value, limit: int = 600) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def normalize(raw, essay: str) -> dict:
    """Validate the model's argument map against the essay.

    Raises ArgumentInvalid if the map is missing or has no usable structure (the
    evaluation is then retried like any other incomplete output).
    """
    if not isinstance(raw, dict):
        raise ArgumentInvalid("缺少论证结构分析")
    dropped = 0

    position = None
    pos = raw.get("position")
    if isinstance(pos, dict) and _text(pos.get("quote")):
        if essay_lib.contains_quote(essay, pos["quote"]):
            position = {
                "quote": _text(pos["quote"], 400),
                "consistent": (
                    pos.get("consistent") if isinstance(pos.get("consistent"), bool) else None
                ),
                "comment": _text(pos.get("comment")),
            }
        else:
            dropped += 1

    paragraphs = []
    for item in raw.get("paragraphs") if isinstance(raw.get("paragraphs"), list) else []:
        if not isinstance(item, dict):
            continue
        quote = _text(item.get("main_point"), 400)
        role = item.get("role") if item.get("role") in ROLES else None
        verdict = item.get("verdict") if item.get("verdict") in VERDICTS else None
        if not (quote and role and verdict):
            dropped += 1
            continue
        if not essay_lib.contains_quote(essay, quote):
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
    for item in raw.get("problems") if isinstance(raw.get("problems"), list) else []:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        quote = _text(item.get("quote"), 400)
        comment = _text(item.get("comment"))
        if kind not in PROBLEM_TYPES or not quote or not comment:
            dropped += 1
            continue
        if not essay_lib.contains_quote(essay, quote):
            dropped += 1
            continue
        if any(p["type"] == kind and p["quote"] == quote for p in problems):
            continue  # same finding repeated; not an error worth a warning
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
    return {
        "position": position,
        "paragraphs": paragraphs[:MAX_PARAGRAPHS],
        "problems": problems[:MAX_PROBLEMS],
        "dropped": dropped,
    }


def problem_types(argument: dict | None) -> list[str]:
    return [p["type"] for p in (argument or {}).get("problems") or []]
