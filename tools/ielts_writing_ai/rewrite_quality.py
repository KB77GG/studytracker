"""Deterministic quality checks for a model rewrite.

Built from the 2026-11-04 real-model run and revised after the offline review of the
same day. The model's own claims about its rewrite are not trusted:

- word counts: the count shown is always the server's. Each number in the notes is
  classified by its clause as describing the original draft, a target/limit, or the
  current rewrite; only target/limit mentions are exempt, and claims about the
  original or the rewrite must match the real counts;
- self-scoring: "this version reaches Band 7" / "已达到雅思7分" is a target, not a
  verified score. Negated ("未达到") and intentional ("为了达到…") wording is not a
  claim; the page always labels the rationale as unverified self-description;
- change notes: "changed" means changed case-sensitively (i -> I is a real change);
  identical before/after pairs, claimed new wording that is not in the essay, and
  claimed deletions of text still present are removed;
- answering the question: lexical overlap cannot decide this (a paraphrase can score
  lower than an off-topic essay stuffed with keywords), so it is only an uncertainty
  note. The verifiable part is the model's answer map - each requirement of the
  question must point to a sentence that exists in the rewrite. That proves the
  cited sentences exist, not that they truly answer the question;
- Task 1 without a readable chart: positive claims that figures are accurate are
  flagged; honest statements that accuracy cannot be confirmed are not.

Issues trigger the existing single silent retry; if the retry still has issues,
the better attempt is kept, marked as not passing quality, with every issue shown.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import essay as essay_lib

UPPER_WORDS = {"task1": 220, "task2": 330}
MIN_ANSWER_ITEMS = 2
LOW_OVERLAP_NOTE = 0.2  # below this, only an uncertainty note (never pass/fail)
MIN_PROMPT_TERMS = 3

# Procedural exam instructions are not part of what the question is about.
INSTRUCTION_SENTENCE_RE = re.compile(
    r"[^.?!]*\b(?:you should spend|write at least|give reasons for your answer|include any "
    r"relevant examples|summari[sz]e the information|make comparisons where relevant|write "
    r"about the following topic)\b[^.?!]*[.?!]?",
    re.IGNORECASE,
)
# Instruction words and function words that say nothing about the topic.
GENERIC_PROMPT_WORDS = set(
    """a about above agree also an and any are argue as at be been being believe below between
    both by can chart comparisons could diagram disagree discuss do does example examples
    experience extent features for from give graph has have how in include information is it
    its knowledge main make many may might more most much new no not of on one opinion or
    other others own people per percentage proportion reasons relevant reporting selecting
    should show shown shows some such summarise summarize table than that the their there
    these they think this those to rather views what where whether which while who why will
    with would write you your""".split()
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
DELETE_RE = re.compile(r"删除|删去|去掉|移除|并入|removed?|deleted?|cut", re.IGNORECASE)
SUMMARY_PARAGRAPH_RE = re.compile(
    r"总结段|结尾段|结论段|summary paragraph|concluding paragraph", re.I
)
SUMMARY_START_RE = re.compile(
    r"^(?:in summary|to sum up|in conclusion|to summarise|overall)\b", re.I
)

# Clause boundaries for context decisions (negation, intent, what a number refers to).
CLAUSE_BOUNDARY_RE = re.compile(r"[，,。；;：:！？!?\n（）()]")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。；;！？!?])")

COUNT_RE = re.compile(r"(\d{2,4})\s*(?:个)?\s*(?:英文)?(?:单)?(?:词|words?\b)", re.IGNORECASE)
ORIGINAL_RE = re.compile(
    r"原稿|原文|学生原|原作文|原来的|original|student'?s (?:essay|draft)|the draft", re.I
)
CURRENT_RE = re.compile(
    r"改写稿|改写后|改写版|改后|新稿|本稿|本篇|本文|全文|现稿|当前|现在|扩展到|扩充到|增加到|增至|"
    r"缩减到|压缩到|共|长度|篇幅|this version|the rewrite|rewritten|\bnow\b|in total|totals?",
    re.I,
)
TARGET_RE = re.compile(
    r"下限|上限|要求|至少|最少|不少于|不低于|以上|以内|目标|应|需|须|minimum|at least|limit|"
    r"target|required|requirement|no fewer|or more",
    re.I,
)

BAND_CLAIM_RES = (
    re.compile(
        r"(?:达到|达成|符合|满足|达标|已达|拿到|获得|得到|可得|能得|足以|属于|算得上|称得上|"
        r"提升到|提高到|升至|"
        r"reach(?:es|ed)?|meet(?:s)?|achiev(?:es|ed)|deserv(?:es|ed)|"
        r"(?:would|will|could|should)\s+(?:score|get|receive|earn))"
        r"[^。；;\n]{0,15}?(?:band\s*\d|\d(?:\.\d)?\s*分|分数段)",
        re.I,
    ),
    re.compile(
        r"(?:是|为(?!了)|属于?|即|堪称)[^。；;\n，,]{0,6}?(?:band\s*\d(?:\.\d)?|\d(?:\.\d)?\s*分)"
        r"(?:的)?(?:作文|文章|水平|标准|档|范文)",
        re.I,
    ),
    re.compile(
        r"\b(?:is|are)\s+(?:a\s+)?band\s*\d(?:\.\d)?\s+(?:essay|response|answer|level)", re.I
    ),
)
DATA_CLAIM_RE = re.compile(
    r"数据(?:引用|使用)?(?:准确|正确|无误|可靠)|(?:accurate|correct|verified)\s+(?:data|figures)|"
    r"(?:data|figures)\s+(?:are|is)\s+(?:accurate|correct|verified)",
    re.IGNORECASE,
)
# Negation / uncertainty: the clause is a limitation, not a claim.
NEGATION_RE = re.compile(
    r"未|没有|尚未|并未|并不|不能|不可|不会|不是|不敢|不保证|不足以|不一定|不确定|无法|无从|没法|难以|"
    r"\bnot\b|\bnever\b|cannot|can't|unable|unverified|uncertain|isn't|aren't",
    re.I,
)
# Intent: "为了达到 Band 7 …" describes a goal, not an achieved score.
INTENT_RE = re.compile(
    r"为了|以便|旨在|争取|力求|朝|向|目标|希望|试图|\baim|toward|towards|in order to|so as to|"
    r"\btarget",
    re.I,
)


@dataclass(frozen=True)
class Issue:
    code: str
    message: str  # Chinese, shown to the user
    hint: str  # English, sent back to the model on retry


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _clause_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = 0
    for match in CLAUSE_BOUNDARY_RE.finditer(text, 0, start):
        left = match.end()
    right_match = CLAUSE_BOUNDARY_RE.search(text, end)
    return left, right_match.start() if right_match else len(text)


def _stem(word: str) -> str:
    word = word.lower().strip("'’")
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    elif word.endswith("es") and len(word) > 4 and not word.endswith("ses"):
        word = word[:-2]
    elif word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
        word = word[:-1]
    return word[:5] if not word.isdigit() else word


def topic_text(prompt: str) -> str:
    """The question without procedural exam instructions."""
    return INSTRUCTION_SENTENCE_RE.sub(" ", prompt or "")


def prompt_terms(prompt: str) -> set[str]:
    words = re.findall(r"[A-Za-z]+|\d{3,4}", topic_text(prompt))
    return {_stem(w) for w in words if w.lower() not in GENERIC_PROMPT_WORDS and len(w) > 2}


def prompt_coverage(prompt: str, text: str) -> float | None:
    """Lexical overlap only - an uncertainty signal, never a relevance verdict."""
    terms = prompt_terms(prompt)
    if len(terms) < MIN_PROMPT_TERMS:
        return None
    present = {_stem(w) for w in re.findall(r"[A-Za-z]+|\d{3,4}", text or "")}
    return len(terms & present) / len(terms)


def _quoted(groups) -> str:
    return next((g for g in groups if g is not None), "")


def change_pairs(line: str) -> list[tuple[str, str]]:
    n = len(_QUOTE_STYLES)
    return [
        (_quoted(m.groups()[:n]), _quoted(m.groups()[n:])) for m in CHANGE_PAIR_RE.finditer(line)
    ]


def quoted_fragments(line: str) -> list[str]:
    return [_quoted(m.groups()) for m in QUOTED_RE.finditer(line)]


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


def count_role(text: str, start: int, end: int) -> str:
    """What a word count in ``text[start:end]`` refers to: original, target or current."""
    left, right = _clause_bounds(text, start, end)
    if TARGET_RE.search(text[end:right][:8]):
        return "target"  # "250 词下限", "250 词以上"
    before = text[left:start]
    nearest = None
    for role, regex in (("original", ORIGINAL_RE), ("current", CURRENT_RE), ("target", TARGET_RE)):
        for match in regex.finditer(before):
            if nearest is None or match.end() >= nearest[0]:
                nearest = (match.end(), role)
    return nearest[1] if nearest else "current"


def false_count(text: str, actual: int, original: int) -> int | None:
    """The first stated count about the rewrite or the original that is wrong."""
    for match in COUNT_RE.finditer(text or ""):
        number = int(match.group(1))
        role = count_role(text, match.start(), match.end())
        if role == "target":
            continue
        reference = original if role == "original" else actual
        if reference and abs(number - reference) > max(10, round(reference * 0.05)):
            return number
    return None


def band_claim(text: str) -> bool:
    """True for an assertion that the rewrite has reached a score."""
    text = text or ""
    for regex in BAND_CLAIM_RES:
        for match in regex.finditer(text):
            left, _right = _clause_bounds(text, match.start(), match.end())
            context = text[left : match.start()]
            if NEGATION_RE.search(context) or INTENT_RE.search(context):
                continue
            if ORIGINAL_RE.search(context):
                continue  # about the student's draft, not a self-assessment
            return True
    return False


def data_claim(text: str) -> bool:
    """True for a positive claim that chart figures are accurate (not 'cannot confirm')."""
    text = text or ""
    for match in DATA_CLAIM_RE.finditer(text):
        left, right = _clause_bounds(text, match.start(), match.end())
        if not NEGATION_RE.search(text[left:right]):
            return True
    return False


def _change_problem(line: str, essay_text: str, last_paragraph: str) -> str | None:
    """Return a problem code if a key-change line contradicts the rewritten essay."""
    pairs = change_pairs(line)
    for old, new in pairs:
        # Case- and punctuation-sensitive: "i" -> "I" is a real change.
        if essay_lib.same_text(old, new):
            return "noop_change"
    for _old, new in pairs:
        if re.search(r"[A-Za-z]", new) and not essay_lib.contains_exact(essay_text, new):
            return "claim_absent"
    if DELETE_RE.search(line):
        new_parts = [new for _old, new in pairs]
        for quoted in quoted_fragments(line):
            if not re.search(r"[A-Za-z]", quoted):
                continue
            if any(essay_lib.same_text(quoted, new) for new in new_parts):
                continue
            if essay_lib.contains_exact(essay_text, quoted):
                return "deletion_mismatch"
        if SUMMARY_PARAGRAPH_RE.search(line) and SUMMARY_START_RE.search(last_paragraph):
            return "deletion_mismatch"
    return None


def normalize_answers(value) -> list[dict]:
    items = []
    for raw in value if isinstance(value, list) else []:
        if not isinstance(raw, dict):
            continue
        part = str(raw.get("part") or "").strip()[:200]
        quote = str(raw.get("quote") or "").strip()[:400]
        if part and quote:
            items.append({"part": part, "quote": quote})
    return items[:8]


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    result: dict
    issues: list[Issue]
    notes: list[str]  # informational, never decide pass/fail


def check(result: dict, submission: dict, *, visual_available: bool) -> CheckResult:
    """Never invents text: removes false claims, reports issues and uncertainty notes."""
    task_type = submission["task_type"]
    essay_text = result["essay"]
    words = result["word_count"]
    original_words = submission.get("word_count") or 0
    minimum = essay_lib.MIN_WORDS[task_type]
    upper = UPPER_WORDS[task_type]
    paragraphs = essay_lib.split_paragraphs(essay_text)
    last_paragraph = paragraphs[-1] if paragraphs else ""
    issues: list[Issue] = []
    notes: list[str] = []

    if words < minimum:
        issues.append(
            Issue(
                "below_min",
                f"改写稿只有 {words} 词，低于 {minimum} 词要求",
                f"The essay you wrote has only {words} words; it must have at least {minimum} words "
                f"(aim for {minimum + 20}-{upper}).",
            )
        )

    # Answering the question: a verifiable map, plus an uncertainty note only.
    answers = normalize_answers(result.get("answers"))
    verified = [a for a in answers if essay_lib.contains_exact(essay_text, a["quote"])]
    if len(verified) < len(answers):
        issues.append(
            Issue(
                "answer_unverified",
                f"有 {len(answers) - len(verified)} 条“题目要求 → 对应原句”引用的句子不在改写稿中，已删除",
                "Each answers[].quote must be copied exactly from your essay.",
            )
        )
    if len(verified) < MIN_ANSWER_ITEMS:
        issues.append(
            Issue(
                "answer_map_missing",
                "没有给出足够的“题目要求 → 对应原句”对照，无法核对改写稿回应了题目的哪些要求",
                "Return answers: for each requirement of the question (at least two), quote the "
                "sentence of your essay that addresses it.",
            )
        )
    coverage = prompt_coverage(submission.get("prompt_text", ""), essay_text)
    if coverage is not None and coverage < LOW_OVERLAP_NOTE:
        notes.append(
            f"改写稿与题干用词重合很少（{coverage:.0%}）。这只是词面提示，不能据此判断是否切题；"
            "请对照“题目回应”人工确认。"
        )

    kept, dropped = [], {}
    for line in result.get("key_changes") or []:
        problem = _change_problem(line, essay_text, last_paragraph)
        if problem is None and false_count(line, words, original_words) is not None:
            problem = "count_claim"
        if problem:
            dropped[problem] = dropped.get(problem, 0) + 1
        else:
            kept.append(line)

    rationale_kept = []
    for part in (p for p in SENTENCE_SPLIT_RE.split(result.get("band_rationale") or "") if p):
        if false_count(part, words, original_words) is not None:
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
        "count_claim": ("处说明里的字数与实际字数不符", "Do not state any word counts."),
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

    claims_text = "；".join(kept) + "；" + rationale
    if band_claim(claims_text):
        issues.append(
            Issue(
                "band_claim",
                "改写说明自称已经达到某个分数；这只是 AI 自述，没有经过评分验证",
                "Do not claim that the rewrite reaches, meets or achieves any band or score. "
                "Explain, per criterion, what was changed towards the target band.",
            )
        )
    if not visual_available and task_type == "task1" and data_claim(claims_text):
        issues.append(
            Issue(
                "data_claim",
                "题图没有核对，说明却声称数据准确",
                "The chart could not be checked: never claim that figures are accurate or verified.",
            )
        )

    cleaned = dict(result, key_changes=kept, band_rationale=rationale, answers=verified)
    return CheckResult(cleaned, issues, notes)


def retry_hint(issues: list[Issue]) -> str:
    return " ".join(issue.hint for issue in issues)
