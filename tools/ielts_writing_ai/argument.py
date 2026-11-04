"""Task 2 argument-structure analysis: verification, labels and self-consistency.

The model maps the essay's argument (position, what each paragraph argues, real logic
problems and optional improvements). Nothing is scored separately: the findings
explain TR and CC, so the band scale stays the official one. As with all evidence,
every quote must be found in the student's essay; unverifiable items are dropped and
counted, never shown as findings. Problem types come from a fixed list so they can be
counted and compared.

What the server enforces beyond quote checks (real run of 2026-11-04, prompt .4):
- a contradiction claim (inconsistent_position, conclusion_inconsistent) must quote
  BOTH passages that conflict; a one-sided claim is dropped;
- the map must agree with itself: "position consistent" next to a contradiction, an
  inconsistent position without a conflicting pair, or an off_position problem in a
  paragraph judged "supports" is surfaced for human review, not silently kept;
- paragraph entries are bound to the essay's real paragraphs (one entry each);
- a suggestion with a figure that is not in the student's input (e.g. "over 80%") is
  removed, so the tool never recommends unsourced statistics (see figures.py);
- "no support" / "example not linked" next to support the model itself quoted from
  the same paragraph becomes an optional improvement.

Vocabulary follows the main system's model-topic library (论点 → 机制 → 例子 → 结果 →
边界), so students meet the same concepts in both places.
"""

from __future__ import annotations

from . import essay as essay_lib
from . import figures as figures_lib

PROBLEM_TYPES = {
    "unclear_position": "立场不清",
    "inconsistent_position": "立场前后矛盾",
    "off_position": "分论点偏离立场或题目",
    "unsupported": "论点没有任何理由支撑",
    "example_not_linked": "例子没有回扣论点",
    "circular": "循环论证",
    "overgeneralized": "过度概括",
    "concession_unanswered": "让步后没有回到立场",
    "concession_undermines": "让步削弱了自己的立场",
    "conclusion_inconsistent": "结尾与立场矛盾",
    "irrelevant": "包含与论证无关的内容",
}
# Claims that two passages cannot both be true: both must be quoted and verified.
PAIRED_TYPES = ("inconsistent_position", "conclusion_inconsistent")
# "No support" judgements: the model must quote any support it found in the same
# paragraph ("support_found"). If it quotes verified support, the point is supported
# (briefly) and the finding becomes an optional improvement (real run 2026-11-04:
# reasons in the same paragraph or clause were still called "no reason at all").
SUPPORT_CHECKED = ("unsupported", "example_not_linked")
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
MAX_IMPROVEMENTS = 3
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


def _paragraph_of(quote: str, paragraphs: list[str], hint=None) -> int | None:
    """1-based number of the real paragraph containing the quote (the model's own
    number is used only to choose between paragraphs that both contain it)."""
    found = [n for n, text in enumerate(paragraphs, 1) if essay_lib.contains_quote(text, quote)]
    if not found:
        return None
    return (
        hint if isinstance(hint, int) and not isinstance(hint, bool) and hint in found else found[0]
    )


def unsourced_figures(text: str, essay: str) -> list[str]:
    """Figures in a suggestion that the essay itself never gives (whole values; a
    percentage needs the same percentage). See figures.Sources for the full rule."""
    return figures_lib.Sources(essay).unsourced(text)


def _distinct(a: str, b: str) -> bool:
    a, b = essay_lib.squash(a), essay_lib.squash(b)
    return a not in b and b not in a


def _suggestion(item: dict, sources: figures_lib.Sources) -> tuple[str, bool]:
    """(suggestion, removed): a suggestion containing figures absent from the
    student's input is removed rather than shown as advice."""
    suggestion = _text(item.get("suggestion"))
    if suggestion and sources.unsourced(suggestion):
        return "", True
    return suggestion, False


def normalize(raw, essay: str, sources: figures_lib.Sources | None = None) -> dict:
    """Validate the model's argument map against the essay.

    Every entry the model returned (the position, each paragraph, each problem, each
    improvement) is counted exactly once, so
    returned == kept + dropped + duplicates + over_limit:
    - dropped: malformed (not an object, wrong type, unknown enum, missing text), its
      quote is not in the essay, or a contradiction without both quotes;
    - duplicates: a second entry for the same real paragraph, or a problem repeated
      with the same type and quote;
    - over_limit: valid but beyond the caps.

    Raises ArgumentInvalid if the map is missing or has no verified paragraph (the
    evaluation is then retried like any other incomplete output). Invalid entries
    alone never reject the rest.
    """
    if not isinstance(raw, dict):
        raise ArgumentInvalid("缺少论证结构分析（argument 必须在顶层，与 criteria 同级）")
    real_paragraphs = essay_lib.split_paragraphs(essay)
    sources = sources or figures_lib.Sources(essay)
    returned = dropped = duplicates = removed_suggestions = 0
    notes = []

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

    by_number = {}
    entries, malformed = _entries(raw.get("paragraphs"))
    returned += len(entries) + malformed
    dropped += malformed
    for item in entries:
        item = item if isinstance(item, dict) else {}
        role = _enum(item.get("role"), ROLES)
        verdict = _enum(item.get("verdict"), VERDICTS)
        quote = _verified_quote(item.get("main_point"), essay) if role and verdict else None
        number = _paragraph_of(quote, real_paragraphs, item.get("p")) if quote else None
        if not number:
            dropped += 1
            continue
        if number in by_number:
            duplicates += 1  # one entry per real paragraph (e.g. sentences of one block)
            continue
        by_number[number] = {
            "p": number,
            "role": role,
            "role_label": ROLES[role],
            "main_point": quote,
            "verdict": verdict,
            "verdict_label": VERDICTS[verdict],
            "comment": _text(item.get("comment")),
        }
    paragraphs = [by_number[n] for n in sorted(by_number)]

    problems, reclassified = [], []
    entries, malformed = _entries(raw.get("problems"))
    returned += len(entries) + malformed
    dropped += malformed
    for item in entries:
        item = item if isinstance(item, dict) else {}
        kind = _enum(item.get("type"), PROBLEM_TYPES)
        comment = _text(item.get("comment"))
        quote = _verified_quote(item.get("quote"), essay) if kind and comment else None
        other = None
        if quote and kind in PAIRED_TYPES:
            other = _verified_quote(item.get("conflicts_with"), essay)
            if not (other and _distinct(quote, other)):
                quote = None  # a contradiction needs both passages
        if not quote:
            dropped += 1
            continue
        if any(p["type"] == kind and p["quote"] == quote for p in problems) or any(
            r["from_type"] == kind and r["quote"] == quote for r in reclassified
        ):
            duplicates += 1  # same finding repeated; shown once, not an error
            continue
        suggestion, removed = _suggestion(item, sources)
        removed_suggestions += 1 if removed else 0
        number = _paragraph_of(quote, real_paragraphs)
        support = (
            _support_found(item.get("support_found"), quote, number, essay, real_paragraphs)
            if kind in SUPPORT_CHECKED
            else []
        )
        if support:
            # The improvement's advice is the (already filtered) suggestion. Only when
            # the model gave none does its comment stand in, and then it goes through
            # the same figure check: a removed suggestion never comes back this way.
            if not suggestion and not removed and comment:
                if sources.unsourced(comment):
                    removed = True
                    removed_suggestions += 1
                else:
                    suggestion = comment
            reclassified.append(
                {
                    "quote": quote,
                    "suggestion": suggestion,
                    "suggestion_removed": removed,
                    "from_type": kind,
                    "from_label": PROBLEM_TYPES[kind],
                    "support": support,
                }
            )
            continue
        problems.append(
            {
                "type": kind,
                "label": PROBLEM_TYPES[kind],
                "quote": quote,
                "conflicts_with": other,
                "p": number,
                "comment": comment,
                "suggestion": suggestion,
                "suggestion_removed": removed,
                "needs_review": False,
            }
        )

    improvements = list(reclassified)  # shown first: they replace a problem
    entries, malformed = _entries(raw.get("improvements"))
    returned += len(entries) + malformed
    dropped += malformed
    for item in entries:
        item = item if isinstance(item, dict) else {}
        quote = _verified_quote(item.get("quote"), essay)
        suggestion, removed = _suggestion(item, sources)
        if not quote or not (suggestion or removed):
            dropped += 1
            continue
        if removed:
            # The whole point of an improvement is its suggestion: nothing left to show.
            removed_suggestions += 1
            dropped += 1
            continue
        improvements.append({"quote": quote, "suggestion": suggestion})

    if not paragraphs:
        raise ArgumentInvalid("论证结构分析没有给出可核实的段落中心句")
    over_limit = (
        max(0, len(paragraphs) - MAX_PARAGRAPHS)
        + max(0, len(problems) - MAX_PROBLEMS)
        + max(0, len(improvements) - MAX_IMPROVEMENTS)
    )
    paragraphs = paragraphs[:MAX_PARAGRAPHS]
    problems = problems[:MAX_PROBLEMS]
    improvements = improvements[:MAX_IMPROVEMENTS]

    self_conflicts = _check_consistency(position, paragraphs, problems, notes)
    if reclassified:
        notes.append(
            f"有 {len(reclassified)} 条“没有支撑 / 例子未回扣”的判断，AI 自己引用了同一段里的"
            "理由或论点，已改列为可选优化：简短的支撑不等于没有支撑。"
        )
    # Removed suggestions are reported once for the whole evaluation (review.py).
    if len(real_paragraphs) == 1:
        notes.append("原文只有 1 段，论证结构只能按整段分析（分段问题见 CC 的反馈）。")
    kept = (1 if position else 0) + len(paragraphs) + len(problems) + len(improvements)
    return {
        "position": position,
        "paragraphs": paragraphs,
        "problems": problems,
        "improvements": improvements,
        "reclassified": len(reclassified),
        "notes": notes,
        "self_conflicts": self_conflicts,
        "suggestions_removed": removed_suggestions,
        "real_paragraphs": len(real_paragraphs),
        "returned": returned,
        "kept": kept,
        "dropped": dropped,
        "duplicates": duplicates,
        "over_limit": over_limit,
    }


def _support_found(value, quote, number, essay, real_paragraphs) -> list[str]:
    """Verified spans the model quoted as support for a point: in the same paragraph,
    and not just the problem quote itself (a reason clause inside it counts)."""
    found = []
    for entry in value if isinstance(value, list) else []:
        span = _verified_quote(entry, essay)
        if not span or essay_lib.squash(span) == essay_lib.squash(quote):
            continue
        if number and _paragraph_of(span, real_paragraphs, number) == number:
            found.append(span)
    return found[:3]


def _check_consistency(position, paragraphs, problems, notes) -> int:
    """Surface places where the model's map contradicts itself. Nothing is silently
    resolved: the claim without evidence loses its status, and conflicting problems
    are kept but marked for human review."""
    conflicts = 0
    paired = [p for p in problems if p["type"] in PAIRED_TYPES]
    if position and position["consistent"] is True and paired:
        conflicts += 1
        position["consistent"] = None
        for problem in paired:
            problem["needs_review"] = True
        notes.append(
            "AI 一方面判断立场前后一致，另一方面又指出了前后矛盾，判断本身不一致：立场一致性"
            "不作结论，相关问题已标“需人工确认”。"
        )
    elif position and position["consistent"] is False and not paired:
        conflicts += 1
        position["consistent"] = None
        notes.append(
            "AI 判断立场前后不一致，但没有给出相互矛盾的两处原文，这一判断未采用；"
            "限定条件（如“优先 A，必要时 B”）本身不算矛盾。"
        )
    verdicts = {p["p"]: p["verdict"] for p in paragraphs}
    for problem in problems:
        if problem["type"] == "off_position" and verdicts.get(problem["p"]) == "supports":
            conflicts += 1
            problem["needs_review"] = True
            notes.append(
                f"AI 判断第 {problem['p']} 段服务于立场，却又说它偏离立场，这条问题已标"
                "“需人工确认”。"
            )
    return conflicts


def problem_types(argument: dict | None) -> list[str]:
    return [p["type"] for p in (argument or {}).get("problems") or []]
