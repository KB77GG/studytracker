"""Generation pipeline: build prompts, call the model, validate its output.

Model output is never trusted as-is.  Every result is normalised into a fixed
shape, original sentences always come from our own split of the student's
essay, and the student's original text is never modified.
"""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path

from . import argument as argument_lib
from . import essay as essay_lib
from . import figures as figures_lib
from . import prompts, rewrite_quality, visual
from .llm import LLMError, parse_strict_json

log = logging.getLogger("iwa.review")

REFINE_TAGS = {
    "grammar",
    "vocabulary",
    "collocation",
    "cohesion",
    "punctuation",
    "spelling",
    "clarity",
    "task",
}
TEXT_LIMIT = 800


class InvalidOutput(Exception):
    pass


# Model output is untrusted data. A normaliser tripping over an unexpected shape (a
# list where a string belongs, ...) means the output is invalid, not that the service
# failed, so it is retried / reported like any other invalid output.
STRUCTURE_ERRORS = (TypeError, AttributeError, KeyError, IndexError, ValueError)


def checked(normalizer, *args):
    try:
        return normalizer(*args)
    except InvalidOutput:
        raise
    except STRUCTURE_ERRORS as exc:
        name = getattr(normalizer, "__name__", "normalizer")
        log.warning("%s: unexpected output structure", name, exc_info=True)
        raise InvalidOutput(f"模型输出结构异常（{type(exc).__name__}）") from None


def _text(value, limit: int = TEXT_LIMIT) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:limit]


def _text_list(value, *, limit_items: int, limit_chars: int = TEXT_LIMIT) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    items = [_text(item, limit_chars) for item in value if not isinstance(item, (dict, list))]
    return [item for item in items if item][:limit_items]


# ---------------------------------------------------------------------------
# Normalisers (pure; unit-tested directly)
# ---------------------------------------------------------------------------


MIN_REASON_CHARS = 12  # a criterion's "why this band" must be an actual sentence

# Why Task 1 Task Achievement cannot be judged, keyed by image_status.
TA_UNASSESSABLE_REASONS = {
    "none": "未上传题图",
    "skipped": "未配置识图模型",
    "failed": "题图识别失败",
    "pending": "题图尚未识别完成",
}


# Task 1 TA needs the chart data; only a successfully read image provides it.
task_criterion_assessable = prompts.visual_available


def ta_unassessable_reason(submission: dict) -> str:
    status = submission.get("image_status") or "none"
    error = submission.get("image_error") or ""
    if status == "failed" and ":" in error:
        code, detail = error.split(":", 1)
        if code in {"insufficient", "unstructured"}:
            return f"题图信息不足（{detail}）"
    return TA_UNASSESSABLE_REASONS.get(status, "题图不可用")


def _meaningful(text: str) -> bool:
    return len("".join(text.split())) >= MIN_REASON_CHARS


def _evidence_items(
    value, essay: str, *, limit: int, with_suggestion: bool, sources=None
) -> list[dict]:
    """Normalise strengths/issues into {quote, quote_found, comment[, suggestion]}."""
    items = []
    for raw in value if isinstance(value, list) else []:
        if isinstance(raw, str):  # a bare claim with no quote: shown, but not evidence
            raw = {"comment": raw}
        if not isinstance(raw, dict):
            continue
        full_quote = _text(raw.get("quote"), None)
        comment = _text(raw.get("comment"))
        if not (full_quote or comment):
            continue
        item = {
            "quote": full_quote[:300],  # verified in full first, then shortened
            "quote_found": bool(full_quote) and essay_lib.contains_quote(essay, full_quote),
            "comment": comment,
        }
        if with_suggestion:
            item["suggestion"] = _text(raw.get("suggestion"))
            # Advice must not introduce figures the student never gave (figures.py).
            item["suggestion_removed"] = bool(
                sources and item["suggestion"] and sources.unsourced(item["suggestion"])
            )
            if item["suggestion_removed"]:
                item["suggestion"] = ""
        items.append(item)
    return items[:limit]


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _nested_in(criteria_raw: dict, key: str) -> bool:
    return any(isinstance(item, dict) and key in item for item in criteria_raw.values())


def _require_chinese(criteria: list[dict], overall_comment: str) -> None:
    """Explanations are for Chinese learners: every reason and the overall comment
    must be Chinese (English quotes inside are fine), and so must most comments.
    The 2026-11-04 Task 1 run came back entirely in English despite the prompt."""
    scored = [c for c in criteria if c["state"] == "scored"]
    reasons = [c["summary"] for c in scored] + [overall_comment]
    comments = [e["comment"] for c in scored for e in c["strengths"] + c["issues"] if e["comment"]]
    english = [r for r in reasons if not _CJK_RE.search(r)]
    english_comments = [c for c in comments if not _CJK_RE.search(c)]
    if english or len(english_comments) * 2 > len(comments):
        raise InvalidOutput("解释必须使用简体中文（评分理由、总评或多数说明是英文）")


_CN_NUM = "一二两三四五六七八九十"
_PARAGRAPH_CLAIM_RE = re.compile(
    rf"([{_CN_NUM}]|\d+)\s*段式"
    rf"|(?:共|全文共?|全文只有|全文有|分为|分成)\s*([{_CN_NUM}]|\d+)\s*个?段"
    r"|(\d+)-paragraph"
)
_REPEAT_RE = re.compile(
    r"([A-Za-z][A-Za-z'-]{1,30})[”\"’']?\s*(?:一词|这个词|这一词|这个单词|一字)?\s*"
    r"(?:在(?:全)?文中|全文)?\s*(?:多次|反复|重复|频繁)(?:出现|使用)"
)


def _count_corrections(texts: list[str], essay: str) -> list[str]:
    """Counts the explanations state that can be checked against the essay itself
    (2026-11-04 Task 1 run: "四段式" for a five-paragraph essay, "figure 多次出现" for
    a word used once). Wrong ones get a visible correction; the text is not edited."""
    paragraphs = len(essay_lib.split_paragraphs(essay))
    notes = []
    for text in texts:
        for match in _PARAGRAPH_CLAIM_RE.finditer(text or ""):
            raw = next(g for g in match.groups() if g)
            stated = int(raw) if raw.isdigit() else int(figures_lib.cn_number(raw))
            if stated != paragraphs:
                notes.append(
                    f"评价中说原文是“{match.group().strip()}”，按换行计原文实际有 {paragraphs} 段，"
                    "请以原文为准。"
                )
        for match in _REPEAT_RE.finditer(text or ""):
            word = match.group(1)
            count = len(re.findall(rf"\b{re.escape(word)}(?:s|es)?\b", essay, re.IGNORECASE))
            if count < 2:
                notes.append(f"评价中说“{word}”多次出现，原文中只出现 {count} 次，请以原文为准。")
    return list(dict.fromkeys(notes))


MAX_COMPARISONS = 8


def _consistency(raw: dict, essay: str) -> tuple[list[dict], int, int]:
    """(issues, claims checked, dropped). A contradiction is reported only when its
    claim and at least one of the figures it conflicts with are really in the essay."""
    issues, dropped, checked = [], 0, 0
    comparisons = raw.get("comparisons")
    for item in comparisons if isinstance(comparisons, list) else []:
        if not isinstance(item, dict):
            dropped += 1
            continue
        claim = _text(item.get("claim"), None)
        if not (claim and essay_lib.contains_quote(essay, claim)):
            dropped += 1
            continue
        checked += 1
        if item.get("holds") is not False:
            continue
        figures = [
            f[:300]
            for f in (item.get("figures") if isinstance(item.get("figures"), list) else [])
            if isinstance(f, str)
            and f.strip()
            and essay_lib.contains_quote(essay, f.strip())
            and essay_lib.squash(f) not in essay_lib.squash(claim)
        ]
        comment = _text(item.get("comment"))
        if not (figures and comment):
            dropped += 1  # "contradicted" without the figures that contradict it
            continue
        issues.append(
            {"quote": claim[:300], "quote_found": True, "figures": figures[:3], "comment": comment}
        )
    # Older free list: kept only when its quote is really in the essay.
    proposed = _evidence_items(raw.get("consistency_issues"), essay, limit=4, with_suggestion=False)
    for entry in proposed:
        if not (entry["quote_found"] and entry["comment"]):
            dropped += 1
        elif not any(
            essay_lib.squash(i["quote"]) == essay_lib.squash(entry["quote"]) for i in issues
        ):
            issues.append({**entry, "figures": []})
    return issues[:MAX_COMPARISONS], checked, dropped


def normalize_evaluation(raw: dict, submission: dict) -> dict:
    """Validate a model evaluation; reject it unless every scored criterion has a real
    reason and at least one quote that can be found verbatim in the essay."""
    task_type = submission["task_type"]
    essay = submission["essay_text"]
    criteria_raw = raw.get("criteria")
    if not isinstance(criteria_raw, dict):
        raise InvalidOutput("缺少 criteria")
    task_ok = task_criterion_assessable(submission)
    sources = figures_lib.for_submission(submission)

    criteria = []
    for key in essay_lib.CRITERIA:
        short = essay_lib.CRITERION_SHORT[task_type][key]
        label = essay_lib.CRITERION_LABELS[task_type][key]
        if key == "task" and not task_ok:
            # Whatever the model said about data accuracy/coverage is unfounded: drop it.
            criteria.append(
                {
                    "key": key,
                    "short": short,
                    "label": label,
                    "band": None,
                    "state": "not_assessable",
                    "reason": f"{ta_unassessable_reason(submission)}，无法核对图表数据，"
                    f"{label} 不评分。",
                    "summary": "",
                    "strengths": [],
                    "issues": [],
                }
            )
            continue
        item = criteria_raw.get(key)
        if not isinstance(item, dict):
            raise InvalidOutput(f"缺少评分项 {short}")
        band = essay_lib.snap_band(item.get("band"))
        if band is None:
            raise InvalidOutput(f"评分项 {short} 的分数无效")
        summary = _text(item.get("summary"), 1200)
        if not _meaningful(summary):
            raise InvalidOutput(f"评分项 {short} 没有给出评分理由")
        strengths = _evidence_items(item.get("strengths"), essay, limit=4, with_suggestion=False)
        issues = _evidence_items(
            item.get("issues"), essay, limit=5, with_suggestion=True, sources=sources
        )
        if not any(entry["quote_found"] for entry in strengths + issues):
            raise InvalidOutput(f"评分项 {short} 没有任何能在原文中找到的证据")
        criteria.append(
            {
                "key": key,
                "short": short,
                "label": label,
                "band": band,
                "state": "scored",
                "summary": summary,
                "strengths": strengths,
                "issues": issues,
            }
        )

    overall_comment = _text(raw.get("overall_comment"), 1500)
    priorities = _text_list(raw.get("priorities"), limit_items=5)
    for key in ("overall_comment", "priorities", "argument", "comparisons"):
        if key not in raw and _nested_in(criteria_raw, key):
            raise InvalidOutput(f"{key} 放错了位置：必须在顶层、与 criteria 同级，只出现一次")
    if not _meaningful(overall_comment):
        raise InvalidOutput("缺少总评")
    if not priorities:
        raise InvalidOutput("缺少提升重点")
    _require_chinese(criteria, overall_comment)
    explanations = [overall_comment] + [
        text
        for c in criteria
        for text in [c["summary"]] + [e["comment"] for e in c["strengths"] + c["issues"]]
    ]
    count_corrections = _count_corrections(explanations, essay)
    kept_priorities = [p for p in priorities if not sources.unsourced(p)]
    removed = {
        "criteria": sum(1 for c in criteria for i in c["issues"] if i.get("suggestion_removed")),
        "priorities": len(priorities) - len(kept_priorities),
        "argument": 0,
    }
    priorities = kept_priorities

    warnings = []
    minimum = essay_lib.MIN_WORDS[task_type]
    if submission["word_count"] < minimum:
        warnings.append(
            f"字数 {submission['word_count']} 低于 {minimum} 词要求，实际考试中"
            f"{criteria[0]['label']}会因此受限。"
        )
    if not task_ok:
        warnings.append(
            f"{ta_unassessable_reason(submission)}：Task Achievement 无法核对数据，"
            "不评分，也不给总分；只保留 CC / LR / GRA 的语言反馈。"
        )
    unverified = sum(
        1
        for c in criteria
        for entry in c["strengths"] + c["issues"]
        if entry["quote"] and not entry["quote_found"]
    )
    if unverified:
        warnings.append(f"有 {unverified} 条引文没能在原文中找到，已标注，不作为评分依据。")

    consistency = []
    comparisons_checked = None
    if task_type == "task1":
        # Internal consistency of the essay's own figures; judged without the chart.
        # Every ranking/comparison claim is checked against the essay's own figures
        # ("comparisons"); the older free list ("consistency_issues") is still read.
        consistency, comparisons_checked, consistency_dropped = _consistency(raw, essay)
        if consistency:
            warnings.append(
                "AI 指出作文里有前后矛盾的数据或比较，引文已在原文中核实（只检查作文内部是否"
                "自洽，不是逐个数字的程序化校验，也不代表数据与题图一致）。"
            )
        if consistency_dropped:
            warnings.append(
                f"AI 另提出 {consistency_dropped} 条矛盾，但引文无法在原文中找到或缺少对照的数字，"
                "已忽略。"
            )

    argument = None
    if task_type == "task2":
        # Argument structure explains TR/CC; it is not scored separately. Every quote
        # is verified against the essay; a missing map is an incomplete evaluation.
        try:
            argument = argument_lib.normalize(raw.get("argument"), essay, sources)
        except argument_lib.ArgumentInvalid as exc:
            raise InvalidOutput(str(exc)) from None
        if argument["dropped"]:
            warnings.append(
                f"AI 的论证结构分析中有 {argument['dropped']} 条引文无法在原文中找到或格式不对，已忽略。"
            )

        removed["argument"] = argument["suggestions_removed"]
    removed["total"] = removed["criteria"] + removed["priorities"] + removed["argument"]
    if removed["total"]:
        parts = "、".join(
            f"{label} {removed[key]} 条"
            for key, label in (
                ("criteria", "评分项"),
                ("argument", "论证结构"),
                ("priorities", "提升重点"),
            )
            if removed[key]
        )
        warnings.append(
            f"有 {removed['total']} 条建议包含原文、题目和题图里都没有的具体数字或比例，已删去"
            f"（{parts}），避免把没有来源的数据当作改进方法。"
        )

    warnings += count_corrections

    scored = [c["band"] for c in criteria if c["state"] == "scored"]
    overall = essay_lib.overall_band(scored) if len(scored) == len(essay_lib.CRITERIA) else None
    return {
        "overall_band": overall,
        "overall_state": "scored" if overall is not None else "not_assessable",
        "criteria": criteria,
        "overall_comment": overall_comment,
        "priorities": priorities,
        "consistency_issues": consistency,
        "comparisons_checked": comparisons_checked,
        "argument": argument,
        "suggestions_removed": removed,
        "count_corrections": count_corrections,
        "warnings": warnings,
    }


def normalize_refinement(raw: dict, sentences: list[essay_lib.Sentence]) -> dict:
    items_raw = raw.get("sentences")
    if not isinstance(items_raw, list):
        raise InvalidOutput("缺少 sentences")
    by_index: dict[int, dict] = {}
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        by_index.setdefault(index, item)
    if not any(s.index in by_index for s in sentences):
        raise InvalidOutput("逐句结果与原文句子对不上")

    out = []
    missing = 0
    for sentence in sentences:
        item = by_index.get(sentence.index)
        revised = _text(item.get("revised"), 2000) if item else ""
        if item is None:
            missing += 1
        # Guard against the model dumping a paragraph into one slot.
        if revised and len(revised) > len(sentence.text) * 3 + 80:
            revised = ""
        changed = bool(revised) and not essay_lib.same_text(revised, sentence.text)
        tags = []
        if changed and item:
            raw_tags = item.get("tags") if isinstance(item.get("tags"), list) else []
            tags = [t for t in (str(x).strip().lower() for x in raw_tags) if t in REFINE_TAGS]
        out.append(
            {
                "i": sentence.index,
                "paragraph": sentence.paragraph,
                "original": sentence.text,
                "revised": revised if changed else sentence.text,
                "changed": changed,
                "tags": sorted(set(tags), key=tags.index),
                "explanation": _text(item.get("explanation")) if (changed and item) else "",
            }
        )
    refined = essay_lib.join_sentences(sentences, [entry["revised"] for entry in out])
    return {
        "sentences": out,
        "changed_count": sum(1 for entry in out if entry["changed"]),
        "missing_count": missing,
        "summary": _text(raw.get("summary"), 1200),
        "refined_essay": refined,
        "refined_word_count": essay_lib.count_words(refined),
    }


def normalize_rewrite(raw: dict, submission: dict) -> dict:
    essay_text = essay_lib.normalize_newlines(_text(raw.get("essay"), 8000))
    paragraphs = essay_lib.split_paragraphs(essay_text)
    essay_text = "\n\n".join(paragraphs)
    words = essay_lib.count_words(essay_text)
    if words < 60:
        raise InvalidOutput("改写结果过短")
    visual = task_criterion_assessable(submission)
    raw_changes = raw.get("key_changes")
    result = {
        "target_band": submission["target_band"],
        "essay": essay_text,
        "word_count": words,
        "key_changes": raw_changes[:8] if isinstance(raw_changes, list) else [],
        "band_rationale": _text(raw.get("band_rationale"), 1500),
        "answers": rewrite_quality.normalize_answers(raw.get("answers")),
    }
    # The model's own claims (change notes, word counts, "reaches Band 7", which
    # sentence answers which requirement) are verified against the two essays;
    # unverifiable claims are removed, every problem is reported, and uncertainty
    # notes never decide pass/fail.
    flag = raw.get("original_addresses_question")
    checked = rewrite_quality.check(
        result,
        submission,
        visual_available=visual,
        original_addresses_question=flag if isinstance(flag, bool) else None,
        unchanged_reason=_text(raw.get("unchanged_reason"), 400),
    )
    result, issues = checked.result, checked.issues
    warnings = [issue.message for issue in issues] + checked.notes
    if not visual:
        warnings.append(
            f"{ta_unassessable_reason(submission)}：改写稿中的数据只能沿用原文和题干，"
            "没有与题图核对，可能不准确。"
        )
    result.update(
        warnings=warnings,
        original_addresses_question=flag if isinstance(flag, bool) else None,
        quality_passed=not issues,
        content_passed=not checked.content_issues,
        quality_issues=[{"code": i.code, "message": i.message, "kind": i.kind} for i in issues],
        _retry_hint=rewrite_quality.retry_hint(issues),
    )
    return result


CROSS_CHECK_TASK_BAND = 4.5


def rewrite_cross_notes(evaluation_result: dict | None) -> list[str]:
    """When the evaluation scored the original's TR/TA very low, the rewrite needs a
    human check that it really answers the question (display-only, never pass/fail)."""
    criteria = (evaluation_result or {}).get("criteria") or []
    task = criteria[0] if criteria else {}
    band = task.get("band")
    if task.get("state") == "scored" and band is not None and band <= CROSS_CHECK_TASK_BAND:
        return [
            f"评价给原文的 {task.get('short')} 只有 {band:g}（可能离题或展开严重不足）。"
            "请人工确认改写稿是否完整回应了题目。"
        ]
    return []


def _rewrite_rank(candidate: dict, attempt: int) -> tuple[int, int, int]:
    """Lower is better: content problems first, then notes problems, then earlier
    attempt - a tie never replaces an earlier essay with a later one."""
    issues = candidate.get("quality_issues") or []
    content = sum(1 for i in issues if i.get("kind") == "content")
    return content, len(issues) - content, attempt


# ---------------------------------------------------------------------------
# Runners (called from background jobs)
# ---------------------------------------------------------------------------


class Generator:
    def __init__(self, storage, settings, client, vision_client=None):
        self.storage = storage
        self.settings = settings
        self.client = client
        self.vision_client = vision_client

    def describe_image(self, submission_id: int) -> None:
        submission = self.storage.get_submission(submission_id)
        if not submission or submission["image_status"] != "pending":
            return
        if self.vision_client is None:
            self.storage.set_image_result(
                submission_id, status="skipped", description=None, error="vision_disabled"
            )
            return
        try:
            path = Path(self.settings.upload_dir) / submission["image_path"]
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            data_url = f"data:{submission['image_mime']};base64,{encoded}"
            messages, context = prompts.build_describe_image(submission, data_url)
            result = self.vision_client.complete(
                messages,
                json_mode=False,
                max_tokens=prompts.MAX_TOKENS["describe_image"],
                temperature=0.0,
                context=context,
            )
            # A 200 response is not a usable reading: the server decides sufficiency.
            reading = visual.assess(result.text)
            if reading.sufficient:
                self.storage.set_image_result(
                    submission_id,
                    status="ready",
                    description=_text(reading.description, 2500),
                    error=None,
                )
            else:
                log.info("image for submission %s not usable: %s", submission_id, reading.reason)
                self.storage.set_image_result(
                    submission_id,
                    status="failed",
                    description=_text(reading.description, 2500) or None,
                    error=f"{reading.code}:{reading.reason}"[:300],
                )
        except LLMError as exc:
            log.warning("image description failed for submission %s: %s", submission_id, exc.code)
            self.storage.set_image_result(
                submission_id, status="failed", description=None, error=exc.code
            )
        except OSError:
            self.storage.set_image_result(
                submission_id, status="failed", description=None, error="image_missing"
            )

    VALIDATION_ATTEMPTS = 2  # one silent retry for malformed/incomplete output (same quota)

    def _thinking(self, kind: str) -> str:
        """Thinking mode applies to the evaluation only (refine/rewrite unchanged)."""
        mode = getattr(self.settings, "evaluate_thinking", "off") or "off"
        return mode if kind == "evaluate" else "off"

    def _call(self, messages, kind: str, context: dict, attempt: int, max_tokens: int):
        options = {}
        thinking = self._thinking(kind)
        if thinking != "off":
            # Separate, provisional budget and timeout: the defaults were measured
            # without thinking (see config.Settings).
            options = {
                "thinking": thinking,
                "timeout": self.settings.evaluate_thinking_timeout,
            }
            max_tokens = self.settings.evaluate_thinking_max_tokens
        return self.client.complete(
            messages,
            json_mode=True,
            max_tokens=max_tokens,
            temperature=self.settings.llm_temperature,
            context={**context, "attempt": attempt},
            **options,
        )

    def _generate_valid(self, kind: str, submission: dict, sentences):
        if kind == "rewrite":
            return self._generate_rewrite(submission, sentences)
        messages, context = prompts.BUILDERS[kind](submission, sentences)
        problem = None
        for attempt in range(self.VALIDATION_ATTEMPTS):
            if problem:
                messages = prompts.with_retry_note(messages, problem)
            result = self._call(messages, kind, context, attempt, prompts.MAX_TOKENS[kind])
            try:
                raw = result.json()
                if kind == "evaluate":
                    evaluation = checked(normalize_evaluation, raw, submission)
                    evaluation["thinking"] = self._thinking(kind)
                    return evaluation, result
                return checked(normalize_refinement, raw, sentences), result
            except (InvalidOutput, LLMError) as exc:
                if isinstance(exc, LLMError) and exc.code != "invalid_json":
                    raise
                problem = exc.message if isinstance(exc, LLMError) else str(exc)
                log.info("%s attempt %s rejected: %s", kind, attempt + 1, problem)
        raise InvalidOutput(problem or "输出不合格")

    # -- rewrite: content problems regenerate, notes problems only repair notes ----

    def _rewrite_attempt(self, messages, context, attempt, submission):
        """(normalized or None, model result, problem). LLMError propagates."""
        result = self._call(messages, "rewrite", context, attempt, prompts.MAX_TOKENS["rewrite"])
        try:
            return checked(normalize_rewrite, result.json(), submission), result, None
        except (InvalidOutput, LLMError) as exc:
            if isinstance(exc, LLMError) and exc.code != "invalid_json":
                raise
            return None, result, exc.message if isinstance(exc, LLMError) else str(exc)

    @staticmethod
    def _keep(candidate, result, reason: str, message: str):
        candidate["retry_error"] = reason
        candidate["warnings"] = list(candidate.get("warnings") or []) + [message]
        return candidate, result

    def _generate_rewrite(self, submission: dict, sentences):
        messages, context = prompts.build_rewrite(submission, sentences)
        first, first_result, problem = self._rewrite_attempt(messages, context, 0, submission)
        if first is None:  # unusable output: one full retry, nothing to keep
            second, second_result, problem = self._rewrite_attempt(
                prompts.with_retry_note(messages, problem), context, 1, submission
            )
            if second is None:
                raise InvalidOutput(problem or "输出不合格")
            second.pop("_retry_hint", None)
            return second, second_result
        hint = first.pop("_retry_hint", "")
        if first["quality_passed"]:
            return first, first_result

        if first["content_passed"]:
            # The essay is fine; only the notes are wrong. Keep this essay and ask for
            # corrected notes about it - never regenerate (and possibly regress) it.
            notes_messages, notes_context = prompts.build_rewrite_notes(
                submission, first["essay"], hint
            )
            try:
                notes_result = self._call(
                    notes_messages, "rewrite", notes_context, 1, prompts.MAX_TOKENS["rewrite_notes"]
                )
            except LLMError as exc:
                return self._keep(
                    first,
                    first_result,
                    exc.code,
                    f"说明修正没有完成（{exc.code}），保留了第一次的正文和已核实的说明。",
                )
            notes = parse_strict_json(notes_result.text)
            if notes is None:
                return self._keep(
                    first,
                    first_result,
                    "invalid_json",
                    "说明修正的输出不合格，保留了第一次的正文和已核实的说明。",
                )
            try:
                repaired = checked(
                    normalize_rewrite, {**notes, "essay": first["essay"]}, submission
                )
            except InvalidOutput:
                return self._keep(
                    first,
                    first_result,
                    "invalid_output",
                    "说明修正的输出不合格，保留了第一次的正文和已核实的说明。",
                )
            repaired.pop("_retry_hint", None)
            if _rewrite_rank(repaired, 0) < _rewrite_rank(first, 0):
                repaired["notes_repaired"] = True
                return repaired, notes_result
            return self._keep(
                first,
                first_result,
                "notes_not_improved",
                "说明修正没有改善，保留了第一次的正文和已核实的说明。",
            )

        # The essay itself has problems (too short, still off-topic): regenerate once.
        try:
            second, second_result, _problem = self._rewrite_attempt(
                prompts.with_retry_note(messages, hint), context, 1, submission
            )
        except LLMError as exc:
            return self._keep(
                first,
                first_result,
                exc.code,
                f"质量重试没有完成（{exc.code}），保留了第一次生成的版本。",
            )
        if second is None:
            return self._keep(
                first,
                first_result,
                "invalid_output",
                "质量重试的输出不合格，保留了第一次生成的版本。",
            )
        second.pop("_retry_hint", None)
        if _rewrite_rank(second, 1) < _rewrite_rank(first, 0):
            return second, second_result
        return first, first_result

    def run(self, generation_id: int) -> None:
        generation = self.storage.get_generation(generation_id)
        if not generation:
            return
        claimed = self.storage.claim_generation(
            generation_id,
            provider=getattr(self.client, "provider", "unknown"),
            model=getattr(self.client, "model", ""),
            prompt_version=prompts.PROMPT_VERSION,
        )
        if not claimed:
            return
        submission = self.storage.get_submission(generation["submission_id"])
        if not submission:
            return
        kind = generation["kind"]
        try:
            sentences = essay_lib.split_sentences(submission["essay_text"])
            normalized, result = self._generate_valid(kind, submission, sentences)
            self.storage.finish_generation(
                generation_id,
                result=normalized,
                latency_ms=result.latency_ms,
                usage=result.usage,
                model=result.model,
            )
        except LLMError as exc:
            log.warning("generation %s (%s) failed: %s", generation_id, kind, exc.code)
            self.storage.finish_generation(
                generation_id, error_code=exc.code, error_message=exc.message
            )
        except InvalidOutput as exc:
            log.warning("generation %s (%s) invalid output: %s", generation_id, kind, exc)
            self.storage.finish_generation(
                generation_id, error_code="invalid_output", error_message=f"模型输出不合格：{exc}"
            )
        except Exception:  # never leave a generation stuck in "running"
            log.exception("generation %s (%s) crashed", generation_id, kind)
            self.storage.finish_generation(
                generation_id, error_code="internal_error", error_message="生成时发生内部错误"
            )
