"""Generation pipeline: build prompts, call the model, validate its output.

Model output is never trusted as-is.  Every result is normalised into a fixed
shape, original sentences always come from our own split of the student's
essay, and the student's original text is never modified.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from . import essay as essay_lib
from . import prompts, rewrite_quality, visual
from .llm import LLMError

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


def _evidence_items(value, essay: str, *, limit: int, with_suggestion: bool) -> list[dict]:
    """Normalise strengths/issues into {quote, quote_found, comment[, suggestion]}."""
    items = []
    for raw in value if isinstance(value, list) else []:
        if isinstance(raw, str):  # a bare claim with no quote: shown, but not evidence
            raw = {"comment": raw}
        if not isinstance(raw, dict):
            continue
        quote = _text(raw.get("quote"), 300)
        comment = _text(raw.get("comment"))
        if not (quote or comment):
            continue
        item = {
            "quote": quote,
            "quote_found": bool(quote) and essay_lib.contains_quote(essay, quote),
            "comment": comment,
        }
        if with_suggestion:
            item["suggestion"] = _text(raw.get("suggestion"))
        items.append(item)
    return items[:limit]


def normalize_evaluation(raw: dict, submission: dict) -> dict:
    """Validate a model evaluation; reject it unless every scored criterion has a real
    reason and at least one quote that can be found verbatim in the essay."""
    task_type = submission["task_type"]
    essay = submission["essay_text"]
    criteria_raw = raw.get("criteria")
    if not isinstance(criteria_raw, dict):
        raise InvalidOutput("缺少 criteria")
    task_ok = task_criterion_assessable(submission)

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
        issues = _evidence_items(item.get("issues"), essay, limit=5, with_suggestion=True)
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
    if not _meaningful(overall_comment):
        raise InvalidOutput("缺少总评")
    if not priorities:
        raise InvalidOutput("缺少提升重点")

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
    if task_type == "task1":
        # Internal consistency of the essay's own figures; judged without the chart.
        proposed = _evidence_items(
            raw.get("consistency_issues"), essay, limit=4, with_suggestion=False
        )
        # A contradiction is only reported when its quote is really in the essay;
        # model guesses that cannot be located are dropped, never turned into findings.
        consistency = [c for c in proposed if c["quote_found"] and c["comment"]]
        consistency_dropped = len(proposed) - len(consistency)
        if consistency:
            warnings.append(
                "AI 指出作文里有前后矛盾的数据或比较，引文已在原文中核实（只检查作文内部是否"
                "自洽，不是逐个数字的程序化校验，也不代表数据与题图一致）。"
            )
        if consistency_dropped:
            warnings.append(
                f"AI 另提出 {consistency_dropped} 条矛盾，但引文无法在原文中找到，已忽略。"
            )

    scored = [c["band"] for c in criteria if c["state"] == "scored"]
    overall = essay_lib.overall_band(scored) if len(scored) == len(essay_lib.CRITERIA) else None
    return {
        "overall_band": overall,
        "overall_state": "scored" if overall is not None else "not_assessable",
        "criteria": criteria,
        "overall_comment": overall_comment,
        "priorities": priorities,
        "consistency_issues": consistency,
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
    result = {
        "target_band": submission["target_band"],
        "essay": essay_text,
        "word_count": words,
        "key_changes": _text_list(raw.get("key_changes"), limit_items=6),
        "band_rationale": _text(raw.get("band_rationale"), 1500),
        "answers": rewrite_quality.normalize_answers(raw.get("answers")),
    }
    # The model's own claims (word counts, "reaches Band 7", change notes, which
    # sentence answers which requirement) are checked against the essay; false claims
    # are removed, every problem is reported, uncertainty notes never decide pass/fail.
    checked = rewrite_quality.check(result, submission, visual_available=visual)
    result, issues = checked.result, checked.issues
    warnings = [issue.message for issue in issues] + checked.notes
    if raw.get("original_addresses_question") is False:
        warnings.append("原文没有回应题目：改写稿按题目重新作答，没有保留原文的论点。")
    if not visual:
        warnings.append(
            f"{ta_unassessable_reason(submission)}：改写稿中的数据只能沿用原文和题干，"
            "没有与题图核对，可能不准确。"
        )
    result.update(
        warnings=warnings,
        quality_passed=not issues,
        quality_issues=[{"code": i.code, "message": i.message} for i in issues],
        _retry_hint=rewrite_quality.retry_hint(issues),
    )
    return result


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

    def _generate_valid(self, kind: str, submission: dict, sentences):
        messages, context = prompts.BUILDERS[kind](submission, sentences)
        problem = None
        best = None  # (normalized, result) with quality issues, if nothing clean arrives
        for attempt in range(self.VALIDATION_ATTEMPTS):
            if problem:
                messages = prompts.with_retry_note(messages, problem)
            try:
                result = self.client.complete(
                    messages,
                    json_mode=True,
                    max_tokens=prompts.MAX_TOKENS[kind],
                    temperature=self.settings.llm_temperature,
                    context={**context, "attempt": attempt},
                )
            except LLMError as exc:
                if best is None:
                    raise
                # The quality retry itself failed (timeout, truncation, 5xx, call
                # budget): keep the usable draft we already have, and say why.
                kept, kept_result = best
                kept["retry_error"] = exc.code
                kept["warnings"] = list(kept.get("warnings") or []) + [
                    f"质量重试没有完成（{exc.code}），保留了第一次生成的版本。"
                ]
                log.info("%s quality retry failed (%s); keeping first draft", kind, exc.code)
                return kept, kept_result
            try:
                raw = result.json()
                if kind == "evaluate":
                    normalized = normalize_evaluation(raw, submission)
                elif kind == "refine":
                    normalized = normalize_refinement(raw, sentences)
                else:
                    normalized = normalize_rewrite(raw, submission)
            except (InvalidOutput, LLMError) as exc:
                if isinstance(exc, LLMError) and exc.code != "invalid_json":
                    raise
                problem = exc.message if isinstance(exc, LLMError) else str(exc)
                log.info("%s attempt %s rejected: %s", kind, attempt + 1, problem)
                continue
            hint = normalized.pop("_retry_hint", "")
            if normalized.get("quality_passed", True):
                return normalized, result
            # Usable but with quality issues: retry once, then keep the better attempt.
            issues = len(normalized.get("quality_issues") or [])
            if best is None or issues <= len(best[0].get("quality_issues") or []):
                best = (normalized, result)
            problem = hint or "quality issues"
            log.info("%s attempt %s has quality issues: %s", kind, attempt + 1, problem)
        if best is not None:
            return best
        raise InvalidOutput(problem or "输出不合格")

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
