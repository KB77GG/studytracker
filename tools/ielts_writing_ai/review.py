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
from . import prompts
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


def normalize_evaluation(raw: dict, submission: dict) -> dict:
    task_type = submission["task_type"]
    essay = submission["essay_text"]
    criteria_raw = raw.get("criteria")
    if not isinstance(criteria_raw, dict):
        raise InvalidOutput("缺少 criteria")
    criteria = []
    for key in essay_lib.CRITERIA:
        item = criteria_raw.get(key)
        if not isinstance(item, dict):
            raise InvalidOutput(f"缺少评分项 {key}")
        band = essay_lib.snap_band(item.get("band"))
        if band is None:
            raise InvalidOutput(f"评分项 {key} 的分数无效")
        issues = []
        for issue in item.get("issues") if isinstance(item.get("issues"), list) else []:
            if not isinstance(issue, dict):
                continue
            quote = _text(issue.get("quote"), 300)
            comment = _text(issue.get("comment"))
            suggestion = _text(issue.get("suggestion"))
            if not (quote or comment):
                continue
            issues.append(
                {
                    "quote": quote,
                    "quote_found": bool(quote) and essay_lib.contains_quote(essay, quote),
                    "comment": comment,
                    "suggestion": suggestion,
                }
            )
        criteria.append(
            {
                "key": key,
                "short": essay_lib.CRITERION_SHORT[task_type][key],
                "label": essay_lib.CRITERION_LABELS[task_type][key],
                "band": band,
                "summary": _text(item.get("summary"), 1200),
                "strengths": _text_list(item.get("strengths"), limit_items=4),
                "issues": issues[:5],
            }
        )
    minimum = essay_lib.MIN_WORDS[task_type]
    warnings = []
    if submission["word_count"] < minimum:
        warnings.append(
            f"字数 {submission['word_count']} 低于 {minimum} 词要求，实际考试中"
            f"{criteria[0]['label']}会因此受限。"
        )
    image_status = submission.get("image_status")
    if task_type == "task1" and image_status == "skipped":
        warnings.append("未配置识图模型，本次评价没有核对图表数据的准确性。")
    elif task_type == "task1" and image_status == "failed":
        warnings.append("题图识别失败，本次评价没有核对图表数据的准确性。")
    return {
        "overall_band": essay_lib.overall_band([c["band"] for c in criteria]),
        "criteria": criteria,
        "overall_comment": _text(raw.get("overall_comment"), 1500),
        "priorities": _text_list(raw.get("priorities"), limit_items=5),
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
    minimum = essay_lib.MIN_WORDS[submission["task_type"]]
    warnings = []
    if words < minimum:
        warnings.append(f"改写稿只有 {words} 词，低于 {minimum} 词要求，可重新生成。")
    return {
        "target_band": submission["target_band"],
        "essay": essay_text,
        "word_count": words,
        "key_changes": _text_list(raw.get("key_changes"), limit_items=6),
        "band_rationale": _text(raw.get("band_rationale"), 1500),
        "warnings": warnings,
    }


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
            self.storage.set_image_result(
                submission_id, status="ready", description=_text(result.text, 2500), error=None
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
            messages, context = prompts.BUILDERS[kind](submission, sentences)
            result = self.client.complete(
                messages,
                json_mode=True,
                max_tokens=prompts.MAX_TOKENS[kind],
                temperature=self.settings.llm_temperature,
                context=context,
            )
            raw = result.json()
            if kind == "evaluate":
                normalized = normalize_evaluation(raw, submission)
            elif kind == "refine":
                normalized = normalize_refinement(raw, sentences)
            else:
                normalized = normalize_rewrite(raw, submission)
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
