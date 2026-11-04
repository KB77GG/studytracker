"""Deterministic quality checks for a model rewrite (2026-11-04 real-model findings).

The model's own claims about its rewrite are not trusted:

- the word count shown is always the server's count; stated counts that disagree
  are removed;
- "this version reaches Band 7" is a target, not a verified score, so such claims
  are flagged (and the page labels the rationale as unverified self-description);
- every key change must describe wording that is actually in the essay: identical
  before/after pairs, quoted new wording that is absent, and claimed deletions of
  text that is still present are removed;
- a rewrite must answer the question that was asked (keyword coverage), and must
  not claim chart data is accurate when the chart could not be read.

Issues trigger the existing single silent retry; if the retry still has issues,
the rewrite is kept but marked as not passing quality, with every issue shown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import essay as essay_lib

UPPER_WORDS = {"task1": 220, "task2": 330}
MIN_PROMPT_COVERAGE = 0.4
MIN_PROMPT_TERMS = 3

# Instruction words and function words that say nothing about the topic.
GENERIC_PROMPT_WORDS = set(
    """a about above agree also an and any are argue as at be been being believe below between
    both by can chart comparisons could diagram disagree discuss do does example examples
    experience extent features for from give graph has have how in include information is it
    its knowledge main make many may might more most much new no not of on one opinion or
    other others own people per percentage proportion reasons relevant reporting selecting
    should show shown shows some such summarise summarize table than that the their there
    these they think this those to rather views what where whether which while who why will
    with would write you your below above""".split()
)

# One alternative per quote style, each closed by its own mark, so apostrophes inside
# “lion's share” do not end the quotation.
_QUOTE_STYLES = (("“", "”"), ("「", "」"), ("『", "』"), ('"', '"'), ("‘", "’"), ("'", "'"))
_Q = (
    "(?:"
    + "|".join(
        f"{re.escape(o)}([^{re.escape(c)}]{{1,240}}){re.escape(c)}" for o, c in _QUOTE_STYLES
    )
    + ")"
)
_CHANGE_VERB = r"(?:改为|改成|替换为|替换成|换成|变为|调整为|→|->|=>)"
# "改为更简洁的“X”" - allow a few words between the verb and the new quote.
CHANGE_PAIR_RE = re.compile(_Q + r"\s*" + _CHANGE_VERB + r"[^“「『\"‘'\n]{0,10}" + _Q)
QUOTED_RE = re.compile(_Q)


def _quoted(groups) -> str:
    return next((g for g in groups if g is not None), "")


def change_pairs(line: str) -> list[tuple[str, str]]:
    n = len(_QUOTE_STYLES)
    return [
        (_quoted(m.groups()[:n]), _quoted(m.groups()[n:])) for m in CHANGE_PAIR_RE.finditer(line)
    ]


def quoted_fragments(line: str) -> list[str]:
    return [_quoted(m.groups()) for m in QUOTED_RE.finditer(line)]


DELETE_RE = re.compile(r"删除|删去|去掉|移除|并入|removed?|deleted?|cut", re.IGNORECASE)
SUMMARY_PARAGRAPH_RE = re.compile(
    r"总结段|结尾段|结论段|summary paragraph|concluding paragraph", re.I
)
SUMMARY_START_RE = re.compile(
    r"^(?:in summary|to sum up|in conclusion|to summarise|overall)\b", re.I
)
COUNT_RE = re.compile(r"(\d{2,4})\s*(?:个)?\s*(?:英文)?(?:单)?(?:词|words?\b)", re.IGNORECASE)
BAND_CLAIM_RE = re.compile(
    r"(达到|达成|符合|满足|达标|已达|reach(?:es|ed)?|meet(?:s)?|achiev(?:es|ed))"
    r"[^。；;\n]{0,12}?(?:band|分数段)\s*\d",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(r"(未|没有|尚未|并未|不|not|never)\s*$", re.IGNORECASE)
DATA_CLAIM_RE = re.compile(
    r"数据(?:引用|使用)?(?:准确|正确|无误|可靠)|(?:accurate|correct|verified)\s+(?:data|figures)|"
    r"(?:data|figures)\s+(?:are|is)\s+(?:accurate|correct|verified)",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。；;！？!?])")


@dataclass(frozen=True)
class Issue:
    code: str
    message: str  # Chinese, shown to the user
    hint: str  # English, sent back to the model on retry


def _stem(word: str) -> str:
    word = word.lower().strip("'’")
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("es") and len(word) > 4 and not word.endswith("ses"):
        word = word[:-2]
    elif word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        word = word[:-1]
    return word[:5] if not word.isdigit() else word


def prompt_terms(prompt: str) -> set[str]:
    words = re.findall(r"[A-Za-z]+|\d{3,4}", prompt or "")
    return {_stem(w) for w in words if w.lower() not in GENERIC_PROMPT_WORDS and len(w) > 2}


def prompt_coverage(prompt: str, text: str) -> float | None:
    terms = prompt_terms(prompt)
    if len(terms) < MIN_PROMPT_TERMS:
        return None
    present = {_stem(w) for w in re.findall(r"[A-Za-z]+|\d{3,4}", text or "")}
    return len(terms & present) / len(terms)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().strip(".,;:!?")).lower()


def _count_claim_ok(number: int, actual: int, original: int, task_type: str) -> bool:
    tolerance = max(10, round(actual * 0.05))
    allowed = {essay_lib.MIN_WORDS[task_type], UPPER_WORDS[task_type], 150, 250}
    return abs(number - actual) <= tolerance or abs(number - original) <= 10 or number in allowed


def _wrong_count(text: str, actual: int, original: int, task_type: str) -> int | None:
    for match in COUNT_RE.finditer(text or ""):
        number = int(match.group(1))
        if not _count_claim_ok(number, actual, original, task_type):
            return number
    return None


def _band_claim(text: str) -> bool:
    for match in BAND_CLAIM_RE.finditer(text or ""):
        if not NEGATION_RE.search(text[: match.start()][-6:]):
            return True
    return False


def _change_problem(line: str, essay_text: str, last_paragraph: str) -> str | None:
    """Return a problem code if a key-change line contradicts the rewritten essay."""
    pairs = change_pairs(line)
    for old, new in pairs:
        if _norm(old) == _norm(new):
            return "noop_change"
    for _old, new in pairs:
        if len(new.split()) >= 2 and re.search(r"[A-Za-z]", new):
            if not essay_lib.contains_quote(essay_text, new):
                return "claim_absent"
    if DELETE_RE.search(line):
        new_parts = {_norm(new) for _old, new in pairs}
        for quoted in quoted_fragments(line):
            if _norm(quoted) in new_parts or not re.search(r"[A-Za-z]", quoted):
                continue
            if essay_lib.contains_quote(essay_text, quoted):
                return "deletion_mismatch"
        if SUMMARY_PARAGRAPH_RE.search(line) and SUMMARY_START_RE.search(last_paragraph):
            return "deletion_mismatch"
    return None


def check(result: dict, submission: dict, *, visual_available: bool) -> tuple[dict, list[Issue]]:
    """Return (cleaned result, issues). Never invents text; only removes false claims."""
    task_type = submission["task_type"]
    essay_text = result["essay"]
    words = result["word_count"]
    original_words = submission.get("word_count") or 0
    minimum = essay_lib.MIN_WORDS[task_type]
    upper = UPPER_WORDS[task_type]
    paragraphs = essay_lib.split_paragraphs(essay_text)
    last_paragraph = paragraphs[-1] if paragraphs else ""
    issues: list[Issue] = []

    if words < minimum:
        issues.append(
            Issue(
                "below_min",
                f"改写稿只有 {words} 词，低于 {minimum} 词要求",
                f"The essay you wrote has only {words} words; it must have at least {minimum} words "
                f"(aim for {minimum + 20}-{upper}).",
            )
        )

    coverage = prompt_coverage(submission.get("prompt_text", ""), essay_text)
    if coverage is not None and coverage < MIN_PROMPT_COVERAGE:
        issues.append(
            Issue(
                "off_prompt",
                f"改写稿与题目关键词的重合度只有 {coverage:.0%}，可能没有回应题目",
                "Your essay does not answer the question that was asked. Write an answer to the "
                "actual question, reusing the student's wording only where it is relevant.",
            )
        )

    kept, dropped = [], {}
    for line in result.get("key_changes") or []:
        problem = _change_problem(line, essay_text, last_paragraph)
        if problem is None and _wrong_count(line, words, original_words, task_type) is not None:
            problem = "count_claim"
        if problem:
            dropped[problem] = dropped.get(problem, 0) + 1
        else:
            kept.append(line)

    rationale_parts = [p for p in SENTENCE_SPLIT_RE.split(result.get("band_rationale") or "") if p]
    rationale_kept = []
    for part in rationale_parts:
        if _wrong_count(part, words, original_words, task_type) is not None:
            dropped["count_claim"] = dropped.get("count_claim", 0) + 1
        else:
            rationale_kept.append(part)
    rationale = "".join(rationale_kept).strip()

    labels = {
        "noop_change": (
            "条改动说明的原文和新写法完全相同",
            "Never list a change whose old and new wording are identical.",
        ),
        "claim_absent": (
            "条改动说明引用的新写法不在改写稿中",
            "Quote new wording exactly as it appears in your essay.",
        ),
        "deletion_mismatch": (
            "条说明声称删除的内容仍在改写稿中",
            "Do not claim to delete or merge text that is still in the essay.",
        ),
        "count_claim": ("处说明里的字数与改写稿实际字数不符", "Do not state any word counts."),
    }
    for code, count in dropped.items():
        label, hint = labels[code]
        issues.append(Issue(code, f"有 {count} {label}，已删除", hint))
    if not kept:
        issues.append(
            Issue(
                "no_changes",
                "没有可信的改动说明",
                "Provide 3-6 key changes that each match the essay exactly.",
            )
        )

    claims_text = " ".join(kept) + " " + rationale
    if _band_claim(claims_text):
        issues.append(
            Issue(
                "band_claim",
                "改写说明自称已经达到目标分数；这只是 AI 自述，没有经过评分验证",
                "Do not claim that the rewrite reaches, meets or achieves any band. Explain, per "
                "criterion, what was changed towards the target band.",
            )
        )
    if not visual_available and task_type == "task1" and DATA_CLAIM_RE.search(claims_text):
        issues.append(
            Issue(
                "data_claim",
                "题图没有核对，说明却声称数据准确",
                "The chart could not be checked: never claim that figures are accurate or verified.",
            )
        )

    cleaned = dict(result, key_changes=kept, band_rationale=rationale)
    return cleaned, issues


def retry_hint(issues: list[Issue]) -> str:
    return " ".join(issue.hint for issue in issues)
