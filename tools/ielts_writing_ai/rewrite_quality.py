"""Deterministic quality checks for a model rewrite.

History: built from the 2026-11-04 real-model run, revised after that day's offline
review, and restructured after the second real run (iwa-2026-11-04.2), which showed
that guessing edits from free-text notes misfires ("cut air pollution" read as a
deletion; a removed "the" judged by other "the"s in the essay).

Principles:

- Change notes are structured data: ``{"before": exact text from the student's
  essay, "after": exact text from the rewrite, "why": explanation}``. A change is
  verified when ``before`` is in the original, ``after`` is in the rewrite, and the
  number of occurrences shows the edit really happened (``after`` appears more often
  in the rewrite, or ``before`` less often). Free-text notes are not verifiable and
  are not accepted as change notes.
- Two classes of issue. *Content* issues are about the essay itself (too short,
  still the off-topic essay). *Notes* issues are about the model's description of
  it (false change notes, word counts, self-scoring, answer map). Notes problems are
  repaired without regenerating the essay, so a good essay is never replaced
  because its notes were wrong.
- Self-scoring ("已达到雅思 7 分") is a target, not a verified score; negated,
  intentional and original-draft statements are not claims.
- Answering the question cannot be verified lexically. The answer map proves cited
  sentences exist. The one deterministic case: the model itself says the original
  is off-topic, yet the rewrite is still mostly the original's content and shares
  little with the question - then the rewrite is still off-topic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import essay as essay_lib

UPPER_WORDS = {"task1": 220, "task2": 330}
MIN_ANSWER_ITEMS = 2
LOW_OVERLAP_NOTE = 0.2  # below this, only an uncertainty note (never pass/fail)
MIN_PROMPT_TERMS = 3
# Still-off-topic: the model flags the original as off-topic, but the rewrite keeps
# most of the original's content words and few of the question's.
STILL_OFF_TOPIC_ORIGINAL_OVERLAP = 0.5
STILL_OFF_TOPIC_PROMPT_COVERAGE = 0.3

CONTENT_CODES = {"below_min", "still_off_topic"}

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

# Accepted spellings of the change-note fields (the model used {old, new} in the
# 2026-11-04 run).
CHANGE_FIELDS = {
    "before": ("before", "old", "original", "from", "原文", "原句"),
    "after": ("after", "new", "revised", "to", "改后", "新句"),
    "why": ("why", "reason", "explanation", "note", "说明", "原因"),
}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str  # Chinese, shown to the user
    hint: str  # English, sent back to the model on retry

    @property
    def kind(self) -> str:
        return "content" if self.code in CONTENT_CODES else "notes"


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


def content_stems(text: str) -> set[str]:
    return {
        _stem(w)
        for w in re.findall(r"[A-Za-z]+", text or "")
        if len(w) > 3 and w.lower() not in GENERIC_PROMPT_WORDS
    }


def original_overlap(rewrite: str, original: str) -> float:
    """Share of the rewrite's content words that come from the original essay."""
    mine = content_stems(rewrite)
    return len(mine & content_stems(original)) / len(mine) if mine else 0.0


# ---------------------------------------------------------------------------
# Claims in free text (why / rationale)
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


# ---------------------------------------------------------------------------
# Structured change notes
# ---------------------------------------------------------------------------


def _field(item: dict, name: str) -> str:
    for key in CHANGE_FIELDS[name]:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:600]
    return ""


def normalize_change(item) -> dict | None:
    """A change dict (accepting known field aliases), or None for free text."""
    if not isinstance(item, dict):
        return None
    return {
        "before": _field(item, "before"),
        "after": _field(item, "after"),
        "why": _field(item, "why"),
    }


def verify_change(change: dict, original: str, rewrite: str) -> str | None:
    """None if the change is verified, else the problem code."""
    before, after = change["before"], change["after"]
    if not before and not after:
        return "change_empty"
    if before and after and essay_lib.same_text(before, after):
        return "noop_change"
    if before and not essay_lib.contains_exact(original, before):
        return "change_unlocatable"
    if after and not essay_lib.contains_exact(rewrite, after):
        return "change_unlocatable"
    happened = (
        bool(after)
        and essay_lib.count_exact(rewrite, after) > essay_lib.count_exact(original, after)
    ) or (
        bool(before)
        and essay_lib.count_exact(rewrite, before) < essay_lib.count_exact(original, before)
    )
    return None if happened else "change_not_made"


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

CHANGE_LABELS = {
    "change_unstructured": (
        "条改动说明不是“原文 → 改后”的结构，无法核实",
        'Each key change must be an object {"before": exact text from the student\'s essay, '
        '"after": exact text from your essay, "why": reason}.',
    ),
    "change_empty": ("条改动说明没有给出原文或改后文字", "Give before and/or after text."),
    "noop_change": (
        "条改动说明的原文和改后完全相同",
        "Never list a change whose before and after are identical.",
    ),
    "change_unlocatable": (
        "条改动说明引用的文字在原稿或改写稿中找不到",
        "before must be copied exactly from the student's essay and after exactly from yours.",
    ),
    "change_not_made": (
        "条改动说明描述的修改在正文中并没有发生",
        "Only list changes that are really in your essay; if the essay needs no change, "
        "return key_changes [] and explain in unchanged_reason.",
    ),
    "count_claim": ("处说明里的字数与实际字数不符", "Do not state any word counts."),
}


@dataclass
class CheckResult:
    result: dict
    issues: list[Issue]
    notes: list[str] = field(default_factory=list)  # informational, never pass/fail

    @property
    def content_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.kind == "content"]

    @property
    def notes_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.kind == "notes"]


def check(
    result: dict,
    submission: dict,
    *,
    visual_available: bool,
    original_addresses_question: bool | None = None,
    unchanged_reason: str = "",
) -> CheckResult:
    """Never invents text: removes unverifiable claims, reports issues and notes."""
    task_type = submission["task_type"]
    original = submission.get("essay_text") or ""
    essay_text = result["essay"]
    words = result["word_count"]
    original_words = submission.get("word_count") or 0
    minimum = essay_lib.MIN_WORDS[task_type]
    upper = UPPER_WORDS[task_type]
    prompt = submission.get("prompt_text", "")
    issues: list[Issue] = []
    notes: list[str] = []

    # -- content ---------------------------------------------------------------
    if words < minimum:
        issues.append(
            Issue(
                "below_min",
                f"改写稿只有 {words} 词，低于 {minimum} 词要求",
                f"The essay you wrote has only {words} words; it must have at least {minimum} words "
                f"(aim for {minimum + 20}-{upper}).",
            )
        )
    coverage = prompt_coverage(prompt, essay_text)
    if original_addresses_question is False:
        notes.append(
            "AI 判断原文没有回应题目。改写稿是否已按题目重新作答，需要人工确认（见题目回应对照）。"
        )
        overlap = original_overlap(essay_text, original)
        if (
            coverage is not None
            and coverage < STILL_OFF_TOPIC_PROMPT_COVERAGE
            and overlap >= STILL_OFF_TOPIC_ORIGINAL_OVERLAP
        ):
            issues.append(
                Issue(
                    "still_off_topic",
                    f"改写稿仍主要沿用离题原文的内容（与原文内容词重合 {overlap:.0%}，与题干仅 "
                    f"{coverage:.0%}），没有按题目重新作答",
                    "The student's essay is off-topic and your rewrite still discusses the same "
                    "off-topic content. Write a new answer to the question that was actually asked.",
                )
            )
    if coverage is not None and coverage < LOW_OVERLAP_NOTE:
        notes.append(
            f"改写稿与题干用词重合很少（{coverage:.0%}）。这只是词面提示，不能据此判断是否切题；"
            "请对照“题目回应”人工确认。"
        )

    # -- answer map ---------------------------------------------------------------
    answers = normalize_answers(result.get("answers"))
    verified_answers = [a for a in answers if essay_lib.contains_exact(essay_text, a["quote"])]
    if len(verified_answers) < len(answers):
        issues.append(
            Issue(
                "answer_unverified",
                f"有 {len(answers) - len(verified_answers)} 条“题目要求 → 对应原句”引用的句子不在改写稿中，已删除",
                "Each answers[].quote must be copied exactly from your essay.",
            )
        )
    if len(verified_answers) < MIN_ANSWER_ITEMS:
        issues.append(
            Issue(
                "answer_map_missing",
                "没有给出足够的“题目要求 → 对应原句”对照，无法核对改写稿回应了题目的哪些要求",
                "Return answers: for each requirement of the question (at least two), quote the "
                "sentence of your essay that addresses it.",
            )
        )

    # -- change notes ---------------------------------------------------------------
    kept, dropped = [], {}
    for item in result.get("key_changes") or []:
        change = normalize_change(item)
        if change is None:
            problem = "change_unstructured"
        else:
            problem = verify_change(change, original, essay_text)
            if problem is None and false_count(change["why"], words, original_words) is not None:
                problem = "count_claim"
        if problem:
            dropped[problem] = dropped.get(problem, 0) + 1
        else:
            kept.append(change)

    rationale_kept = []
    for part in (p for p in SENTENCE_SPLIT_RE.split(result.get("band_rationale") or "") if p):
        if false_count(part, words, original_words) is not None:
            dropped["count_claim"] = dropped.get("count_claim", 0) + 1
        else:
            rationale_kept.append(part)
    rationale = "".join(rationale_kept).strip()

    for code, count in dropped.items():
        label, hint = CHANGE_LABELS[code]
        issues.append(Issue(code, f"有 {count} {label}，已删除", hint))

    unchanged = essay_lib.same_text(essay_text, original)
    if not kept:
        if unchanged and unchanged_reason:
            notes.append(f"模型认为原稿无需修改，改写稿与原稿相同：{unchanged_reason}")
        else:
            issues.append(
                Issue(
                    "no_changes",
                    "没有可核实的改动说明",
                    "Provide 1-6 key changes as {before, after, why} that match the two essays "
                    "exactly, or, if no change is needed, return the essay unchanged with key_changes "
                    "[] and unchanged_reason.",
                )
            )

    claims_text = "；".join(c["why"] for c in kept) + "；" + rationale
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

    cleaned = dict(
        result,
        key_changes=kept,
        band_rationale=rationale,
        answers=verified_answers,
        unchanged=unchanged,
    )
    return CheckResult(cleaned, issues, notes)


def retry_hint(issues: list[Issue]) -> str:
    return " ".join(issue.hint for issue in issues)
