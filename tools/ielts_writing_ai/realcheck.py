"""Small-sample check of a real model through the exact production pipeline.

``python -m tools.ielts_writing_ai realcheck`` runs synthetic (or user-provided,
teacher-scored) essays through the same Generator the web app uses - same prompts,
strict JSON, evidence rules and the one silent retry - against a throwaway database,
and writes a report: connectivity, first-attempt / final pass rates, quote
verification, refine/rewrite quality, latency, tokens, score sanity and (with teacher
scores) calibration error.

It never touches the trial database or anyone's quota, never prints the API key,
caps the number of model calls, and stops at once on an authentication or network
failure. Calling a paid model requires --confirm-paid.
"""

from __future__ import annotations

import dataclasses
import json
import math
import statistics
import tempfile
import time
from collections import Counter
from pathlib import Path

from . import access, review, rewrite_quality
from . import essay as essay_lib
from . import samples as builtin_samples
from .llm import LLMError, build_client, parse_strict_json, reasoning_tokens
from .storage import KINDS, Storage, utcnow

ABORT_CODES = {"missing_api_key", "http_401", "http_403", "network", "timeout"}
CRITERION_KEYS = ("task", "coherence", "lexical", "grammar")


class RealCheckError(ValueError):
    pass


def validate_max_calls(value: int) -> int:
    if type(value) is not int or value <= 0:
        raise RealCheckError("max_calls / --max-calls 必须为正整数")
    return value


# ---------------------------------------------------------------------------
# Recording client
# ---------------------------------------------------------------------------


class Recorder:
    def __init__(self, max_calls: int):
        self.max_calls = validate_max_calls(max_calls)
        self.records: list[dict] = []
        self.sample_id = ""
        self.abort: LLMError | None = None

    @property
    def calls(self) -> int:
        return len(self.records)


class RecordingClient:
    """Wraps a model client, recording every call (never the API key)."""

    def __init__(self, inner, recorder: Recorder):
        self.inner = inner
        self.recorder = recorder
        self.provider = getattr(inner, "provider", "unknown")
        self.model = getattr(inner, "model", "")

    def complete(self, messages, **kwargs):
        rec = self.recorder
        context = kwargs.get("context") or {}
        if rec.abort is not None:
            raise rec.abort
        if rec.calls >= rec.max_calls:
            raise LLMError("call_budget", "已达到本次验证的调用上限")
        entry = {
            "sample": rec.sample_id,
            "kind": context.get("kind", ""),
            "attempt": int(context.get("attempt") or 0),
            "mode": context.get("mode") or "full",  # "notes": notes-only repair of a rewrite
            "json_mode": bool(kwargs.get("json_mode")),
            # Same prompt, different thinking mode is what an A/B comparison varies.
            "thinking": kwargs.get("thinking") or "off",
            "max_tokens": kwargs.get("max_tokens"),
            "provider": self.provider,
            "model": self.model,
            "ok": False,
            "error": "client_error",
            "usage": {},
            "text": "",
        }
        # Every invocation has one transport attempt: the content-validation retry
        # uses this same budget; the underlying HTTP client must not retry silently.
        kwargs["retries"] = 0
        # Reserve before dispatch, also covering unexpected client exceptions.
        rec.records.append(entry)
        started = time.monotonic()
        try:
            result = self.inner.complete(messages, **kwargs)
        except LLMError as exc:
            entry.update(
                error=exc.code,
                latency_ms=_ms(started),
                usage=getattr(exc, "usage", None) or {},
                response_received=getattr(exc, "response_received", False),
                http_status=getattr(exc, "http_status", None),
            )
            if exc.code in ABORT_CODES and rec.calls == 1:
                rec.abort = exc  # first call failed on credentials/network: stop at once
            raise
        entry.update(
            ok=True,
            error=None,
            latency_ms=result.latency_ms or _ms(started),
            usage=result.usage or {},
            model=result.model,
            response_received=True,
            http_status=200,
            text=result.text,
            json_ok=(parse_strict_json(result.text) is not None) if entry["json_mode"] else None,
            reasoning_tokens=reasoning_tokens(result.usage),
            reasoning_chars=len(getattr(result, "reasoning", "") or ""),
            # Kept only in the local raw_calls.jsonl, for reviewing what the model weighed.
            reasoning=getattr(result, "reasoning", "") or "",
        )
        return result


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


# ---------------------------------------------------------------------------
# Samples
# ---------------------------------------------------------------------------


def load_samples(source: str, limit: int | None = None) -> list[dict]:
    if source == "builtin":
        items = [dict(item) for item in builtin_samples.SAMPLES]
    else:
        path = Path(source)
        if not path.is_file():
            raise RealCheckError(f"找不到样本文件：{source}")
        items = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except ValueError as exc:
                raise RealCheckError(f"第 {number} 行不是合法 JSON：{exc}") from None
            if not isinstance(item, dict):
                raise RealCheckError(f"第 {number} 行必须是 JSON 对象")
            for field in ("task_type", "prompt", "essay"):
                if not item.get(field):
                    raise RealCheckError(f"第 {number} 行缺少 {field}")
            if item["task_type"] not in essay_lib.MIN_WORDS:
                raise RealCheckError(f"第 {number} 行 task_type 只能是 task1 / task2")
            item.setdefault("id", f"line-{number}")
            if item.get("image"):
                image = (path.parent / item["image"]).resolve()
                if not image.is_file():
                    raise RealCheckError(f"第 {number} 行的题图不存在：{item['image']}")
                item["image"] = str(image)
            items.append(item)
    if not items:
        raise RealCheckError("没有样本")
    _validate_sample_ids(items)
    return items[:limit] if limit else items


def _validate_sample_ids(items: list[dict]) -> None:
    seen = set()
    for number, item in enumerate(items, 1):
        sample_id = item.get("id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise RealCheckError(f"第 {number} 个样本的 id 必须是非空字符串")
        if sample_id in seen:
            raise RealCheckError(f"样本 id 重复：{sample_id}")
        seen.add(sample_id)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def _image_mime(path: Path) -> str | None:
    head = path.read_bytes()[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def run(
    settings,
    items: list[dict],
    *,
    client=None,
    vision_client=None,
    kinds=KINDS,
    max_calls: int = 50,
    target_band: float = 7.0,
) -> dict:
    """Run every sample and return the raw run data (see build_report)."""
    recorder = Recorder(max_calls)
    _validate_sample_ids(items)
    text_client = RecordingClient(client or build_client(settings), recorder)
    vision = vision_client if vision_client is not None else build_client(settings, vision=True)
    vision = RecordingClient(vision, recorder) if vision is not None else None
    started_at = utcnow()

    with tempfile.TemporaryDirectory(prefix="iwa-realcheck-") as tmp:
        # A throwaway database/upload dir: the trial database is never opened.
        temp_settings = dataclasses.replace(
            settings,
            data_dir=Path(tmp),
            db_path=Path(tmp) / "realcheck.sqlite3",
            upload_dir=Path(tmp) / "uploads",
            job_mode="inline",
        )
        temp_settings.ensure_dirs()
        storage = Storage(temp_settings.db_path)
        storage.init_schema()
        code = access.generate_code()
        user_id = storage.create_user(
            name="realcheck", code_hash=access.hash_code(code), code_hint=access.code_hint(code)
        )
        generator = review.Generator(storage, temp_settings, text_client, vision)
        results = []
        for number, item in enumerate(items, 1):
            if recorder.abort is not None:
                break
            recorder.sample_id = item["id"]
            results.append(
                _run_sample(
                    item,
                    number,
                    storage,
                    generator,
                    temp_settings,
                    user_id,
                    kinds,
                    target_band,
                    use_vision=vision is not None,
                )
            )
    return {
        "started_at": started_at.isoformat(),
        "settings": settings.public_summary(),
        "kinds": list(kinds),
        "max_calls": max_calls,
        "aborted": (
            {"code": recorder.abort.code, "message": recorder.abort.message}
            if recorder.abort
            else None
        ),
        "samples": results,
        "calls": recorder.records,
    }


def _run_sample(
    item, number, storage, generator, settings, user_id, kinds, target_band, *, use_vision
):
    essay = essay_lib.normalize_newlines(item["essay"]).strip()
    image_path = image_mime = None
    image_status = "none"
    if item.get("image") and item["task_type"] == "task1":
        source = Path(item["image"])
        image_mime = _image_mime(source)
        if image_mime:
            image_path = f"sample-{number}{source.suffix.lower()}"
            (Path(settings.upload_dir) / image_path).write_bytes(source.read_bytes())
            image_status = "pending"
    created = storage.create_submission(
        public_id=f"rc{number}",
        user_id=user_id,
        task_type=item["task_type"],
        prompt_text=item["prompt"].strip(),
        essay_text=essay,
        essay_sha256="-",
        word_count=essay_lib.count_words(essay),
        target_band=float(item.get("target_band") or target_band),
        image_path=image_path,
        image_mime=image_mime,
        image_status=image_status,
        daily_limit=10**9,
    )
    if image_status == "pending":
        if use_vision:
            generator.describe_image(created["id"])
        else:
            storage.set_image_result(
                created["id"], status="skipped", description=None, error="vision_disabled"
            )
    for kind in kinds:
        generator.run(created["generation_ids"][kind])
    submission = storage.get_submission(created["id"])
    generations = storage.latest_generations(created["id"])
    return {
        "id": item["id"],
        "task_type": item["task_type"],
        "word_count": submission["word_count"],
        "image_status": submission["image_status"],
        "image_error": submission.get("image_error"),
        "level": item.get("level"),
        "expect": item.get("expect") or {},
        "teacher": item.get("teacher") or {},
        "submission": {
            k: submission[k]
            for k in (
                "prompt_text",
                "task_type",
                "essay_text",
                "word_count",
                "target_band",
                "image_status",
                "image_error",
            )
        },
        "generations": {
            kind: {
                "status": g["status"],
                "error_code": g.get("error_code"),
                "error_message": g.get("error_message"),
                "result": g.get("result"),
            }
            for kind, g in generations.items()
            if kind in kinds
        },
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def _percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]


def _first_attempt_problem(kind: str, text: str, sample: dict) -> str | None:
    """Why the first attempt was rejected (re-runs the production validators)."""
    raw = parse_strict_json(text)
    if raw is None:
        return "JSON 之外有文字或不是 JSON 对象"
    submission = sample["submission"]
    try:
        if kind == "evaluate":
            review.checked(review.normalize_evaluation, raw, submission)
        elif kind == "refine":
            sentences = essay_lib.split_sentences(submission["essay_text"])
            review.checked(review.normalize_refinement, raw, sentences)
        elif kind == "rewrite":
            rewrite = review.checked(review.normalize_rewrite, raw, submission)
            if not rewrite["quality_passed"]:
                # Usable but triggers the quality retry: report it as a first-attempt miss.
                return "质量检查：" + "；".join(
                    sorted({i["code"] for i in rewrite["quality_issues"]})
                )
    except review.InvalidOutput as exc:
        return str(exc)
    except Exception as exc:  # the report must still be written for any stored output
        return f"复核时出错（{type(exc).__name__}）"
    return None


def _kind_metrics(kind: str, run_data: dict) -> dict:
    by_sample = {s["id"]: s for s in run_data["samples"]}
    calls = [c for c in run_data["calls"] if c["kind"] == kind]
    first = [c for c in calls if c["attempt"] == 0]
    first_valid = 0
    rejections = Counter()
    for call in first:
        if not call["ok"]:
            rejections[f"调用失败：{call['error']}"] += 1
            continue
        problem = _first_attempt_problem(kind, call["text"], by_sample.get(call["sample"], {}))
        if problem is None:
            first_valid += 1
        else:
            rejections[problem] += 1
    finals = [s["generations"].get(kind) for s in run_data["samples"]]
    finals = [g for g in finals if g]
    ready = [g for g in finals if g["status"] == "ready"]
    final_errors = Counter(g["error_code"] for g in finals if g["status"] != "ready")
    ok_latency = [c["latency_ms"] for c in calls if c["ok"]]
    usage = Counter()
    for call in calls:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = call.get("usage", {}).get(key)
            if isinstance(value, (int, float)):
                usage[key] += int(value)
    completions = [
        c["usage"]["completion_tokens"]
        for c in calls
        if isinstance((c.get("usage") or {}).get("completion_tokens"), int)
    ]
    reasoning = [c["reasoning_tokens"] for c in calls if isinstance(c.get("reasoning_tokens"), int)]
    budgets = sorted({c["max_tokens"] for c in calls if isinstance(c.get("max_tokens"), int)})
    return {
        "thinking": sorted({c.get("thinking") or "off" for c in calls}),
        # Output budget per call and the largest output actually used: the budget for
        # a thinking evaluation must be set from these, not carried over.
        "max_tokens": budgets,
        "completion_tokens_max": max(completions) if completions else None,
        # None: the provider did not report reasoning tokens (not zero).
        "reasoning_tokens": sum(reasoning) if reasoning else None,
        "reasoning_tokens_max": max(reasoning) if reasoning else None,
        "truncated": sum(1 for c in calls if c.get("error") == "truncated"),
        "timeouts": sum(1 for c in calls if c.get("error") == "timeout"),
        "calls": len(calls),
        "first_attempts": len(first),
        "first_attempt_json_ok": _rate(sum(1 for c in first if c.get("json_ok")), len(first)),
        "first_attempt_valid": _rate(first_valid, len(first)),
        "first_attempt_rejections": dict(rejections.most_common()),
        "final_ready": _rate(len(ready), len(finals)),
        "final_failures": dict(final_errors),
        "latency_ms_p50": _percentile(ok_latency, 0.5),
        "latency_ms_p90": _percentile(ok_latency, 0.9),
        "tokens": dict(usage),
    }


def _evidence_metrics(run_data: dict) -> dict:
    quotes = verified = criteria = corrections = 0
    removed = Counter()
    for sample in run_data["samples"]:
        result = (sample["generations"].get("evaluate") or {}).get("result") or {}
        removed.update(
            {k: v for k, v in (result.get("suggestions_removed") or {}).items() if k != "total"}
        )
        corrections += len(result.get("count_corrections") or [])
        for criterion in result.get("criteria") or []:
            if criterion.get("state") != "scored":
                continue
            criteria += 1
            for entry in (criterion.get("strengths") or []) + (criterion.get("issues") or []):
                if isinstance(entry, dict) and entry.get("quote"):
                    quotes += 1
                    verified += 1 if entry.get("quote_found") else 0
    return {
        "scored_criteria": criteria,
        "quotes": quotes,
        "quotes_verified": _rate(verified, quotes),
        # Every advice path of every evaluation (criteria, argument, priorities).
        "suggestions_removed": {**dict(removed), "total": sum(removed.values())},
        "count_corrections": corrections,
    }


def _argument(sample: dict) -> dict | None:
    result = (sample["generations"].get("evaluate") or {}).get("result") or {}
    return result.get("argument")


def _argument_metrics(run_data: dict) -> dict:
    """Task 2 argument map over the evaluations finally adopted, plus how many
    evaluation attempts were rejected outright because of the map."""
    evaluated = mapped = positions = paragraphs = problems = 0
    returned = dropped = duplicates = over_limit = 0
    self_conflicts = removed = improvements = reclassified = 0
    types = Counter()
    verdicts = Counter()
    by_id = {}
    for sample in run_data["samples"]:
        if sample["task_type"] != "task2":
            continue
        by_id[sample["id"]] = sample
        if not (sample["generations"].get("evaluate") or {}).get("result"):
            continue
        evaluated += 1
        argument = _argument(sample)
        if not argument:
            continue
        mapped += 1
        kept = (
            (1 if argument.get("position") else 0)
            + len(argument.get("paragraphs") or [])
            + len(argument.get("problems") or [])
        )
        positions += 1 if argument.get("position") else 0
        paragraphs += len(argument.get("paragraphs") or [])
        problems += len(argument.get("problems") or [])
        dropped += argument.get("dropped") or 0
        self_conflicts += argument.get("self_conflicts") or 0
        reclassified += argument.get("reclassified") or 0
        removed += argument.get("suggestions_removed") or 0
        improvements += len(argument.get("improvements") or [])
        duplicates += argument.get("duplicates") or 0
        over_limit += argument.get("over_limit") or 0
        returned += argument.get("returned", kept + (argument.get("dropped") or 0))
        types.update(p["type"] for p in argument.get("problems") or [])
        verdicts.update(p["verdict"] for p in argument.get("paragraphs") or [])
    attempts = rejected = 0
    for call in run_data.get("calls") or []:
        if call["kind"] != "evaluate" or call.get("sample") not in by_id or not call.get("ok"):
            continue
        attempts += 1
        problem = _first_attempt_problem("evaluate", call.get("text") or "", by_id[call["sample"]])
        rejected += 1 if problem and "论证结构" in problem else 0
    return {
        "task2_evaluations": evaluated,
        "with_argument": mapped,
        "with_position": positions,
        "paragraphs": paragraphs,
        "problems": problems,
        # Entry accounting over the adopted evaluations; every entry the model returned
        # (position, each paragraph, each problem) counts once:
        # returned == kept + dropped + duplicates + over_limit.
        "returned": returned,
        "kept": positions + paragraphs + problems + improvements,
        "improvements": improvements,
        # The model's map contradicting itself (surfaced as "需人工确认"), and suggestions
        # removed for figures the essay never gives.
        "self_conflicts": self_conflicts,
        "suggestions_removed": removed,
        # "No support" findings next to support the model itself quoted (same paragraph),
        # moved to optional improvements.
        "reclassified": reclassified,
        "dropped": dropped,  # malformed, unknown enum, missing text or quote not found
        "duplicates": duplicates,
        "over_limit": over_limit,
        "dropped_rate": _rate(dropped, returned),
        # Whole evaluation attempts (first tries and retries) rejected because the map
        # was missing or had no verified paragraph; not part of the entry counts.
        "evaluate_attempts": attempts,
        "attempts_rejected_for_argument": rejected,
        "problem_types": dict(types.most_common()),
        "paragraph_verdicts": dict(verdicts.most_common()),
    }


def _refine_rewrite_metrics(run_data: dict) -> dict:
    sentences = missing = changed = 0
    requested = generated = meeting = quality_ok = retry_failed = content_ok = 0
    quality_codes = Counter()
    for sample in run_data["samples"]:
        refine = (sample["generations"].get("refine") or {}).get("result")
        if refine:
            sentences += len(refine.get("sentences") or [])
            missing += refine.get("missing_count") or 0
            changed += refine.get("changed_count") or 0
        generation = sample["generations"].get("rewrite")
        if generation is None:
            continue  # rewrite not requested for this run
        requested += 1
        rewrite = generation.get("result") if generation.get("status") == "ready" else None
        if not rewrite:
            continue  # failed generation: counts as requested but not passed
        generated += 1
        minimum = essay_lib.MIN_WORDS[sample["task_type"]]
        meeting += 1 if (rewrite.get("word_count") or 0) >= minimum else 0
        quality_ok += 1 if rewrite.get("quality_passed", True) else 0
        content_ok += 1 if rewrite.get("content_passed", True) else 0
        retry_failed += 1 if rewrite.get("retry_error") else 0
        quality_codes.update(i["code"] for i in rewrite.get("quality_issues") or [])
    return {
        "refine_sentences": sentences,
        "refine_missing_rate": _rate(missing, sentences),
        "refine_changed_rate": _rate(changed, sentences),
        # Counts, so no sample can disappear from a rate's denominator.
        "rewrite_requested": requested,
        "rewrite_generated": generated,
        "rewrite_quality_passed_count": quality_ok,
        "rewrite_retry_failed": retry_failed,
        # Unconditional (acceptance) rates: failed generations count as not passed.
        "rewrite_quality_passed_of_requested": _rate(quality_ok, requested),
        "rewrite_meets_min_words_of_requested": _rate(meeting, requested),
        # Conditional rates, only over rewrites that were generated.
        "rewrite_quality_passed_of_generated": _rate(quality_ok, generated),
        "rewrite_meets_min_words_of_generated": _rate(meeting, generated),
        "rewrite_quality_issues": dict(quality_codes.most_common()),
        # Essay itself OK (length, not still off-topic) even if the notes failed.
        "rewrite_content_passed_count": content_ok,
        "rewrite_content_passed_of_requested": _rate(content_ok, requested),
        "rewrite_full_retries": sum(
            1
            for c in run_data["calls"]
            if c["kind"] == "rewrite" and c["attempt"] == 1 and c.get("mode", "full") == "full"
        ),
        "rewrite_notes_repairs": sum(
            1 for c in run_data["calls"] if c["kind"] == "rewrite" and c.get("mode") == "notes"
        ),
    }


def _scores(sample: dict) -> dict:
    result = (sample["generations"].get("evaluate") or {}).get("result") or {}
    scores = {"overall": result.get("overall_band")}
    for criterion in result.get("criteria") or []:
        scores[criterion["key"]] = criterion.get("band")
    scores["_warnings"] = result.get("warnings") or []
    scores["_ta_state"] = ((result.get("criteria") or [{}])[0]).get("state")
    scores["_ready"] = bool(result)
    return scores


def _sanity(run_data: dict) -> dict:
    checks = []
    for sample in run_data["samples"]:
        expect = sample.get("expect") or {}
        if not expect:
            continue
        s = _scores(sample)
        if not s["_ready"]:
            checks.append(
                {
                    "sample": sample["id"],
                    "check": "评价已生成",
                    "ok": False,
                    "detail": "评价失败，无法检查",
                }
            )
            continue
        overall = s["overall"]
        if "overall_min" in expect:
            ok = overall is not None and overall >= expect["overall_min"]
            checks.append(
                {
                    "sample": sample["id"],
                    "check": f"总分 ≥ {expect['overall_min']}",
                    "ok": ok,
                    "detail": overall,
                }
            )
        if "overall_max" in expect:
            ok = overall is not None and overall <= expect["overall_max"]
            checks.append(
                {
                    "sample": sample["id"],
                    "check": f"总分 ≤ {expect['overall_max']}",
                    "ok": ok,
                    "detail": overall,
                }
            )
        if "task_max" in expect:
            ok = s.get("task") is not None and s["task"] <= expect["task_max"]
            checks.append(
                {
                    "sample": sample["id"],
                    "check": f"TR ≤ {expect['task_max']}（离题）",
                    "ok": ok,
                    "detail": s.get("task"),
                }
            )
            checks.append(_off_topic_rewrite_check(sample))
        if expect.get("word_warning"):
            ok = any("字数" in w for w in s["_warnings"])
            checks.append(
                {
                    "sample": sample["id"],
                    "check": "有字数不足提示",
                    "ok": ok,
                    "detail": s["_warnings"][:1],
                }
            )
        checks += _argument_checks(sample, expect)
        if "consistency_min" in expect:
            result = (sample["generations"].get("evaluate") or {}).get("result") or {}
            found = [c["quote"] for c in result.get("consistency_issues") or []]
            checks.append(
                {
                    "sample": sample["id"],
                    "check": f"指出文内数据矛盾 ≥ {expect['consistency_min']} 条（已知样本矛盾）",
                    "ok": len(found) >= expect["consistency_min"],
                    "detail": {
                        "issues": found,
                        "claims_checked": result.get("comparisons_checked"),
                    },
                }
            )
        if expect.get("not_assessable"):
            ok = overall is None and s["_ta_state"] == "not_assessable"
            checks.append(
                {
                    "sample": sample["id"],
                    "check": "缺图 TA / 总分不可评",
                    "ok": ok,
                    "detail": overall,
                }
            )
    leveled = sorted(
        (sample for sample in run_data["samples"] if sample.get("level") is not None),
        key=lambda sample: sample["level"],
    )
    bands = [(sample["id"], _scores(sample)["overall"]) for sample in leveled]
    if len(bands) >= 2 and all(band is not None for _, band in bands):
        ordered = all(bands[i][1] <= bands[i + 1][1] for i in range(len(bands) - 1))
        spread = bands[-1][1] - bands[0][1]
        checks.append(
            {"sample": "分级样本", "check": "总分随水平不降", "ok": ordered, "detail": bands}
        )
        checks.append(
            {
                "sample": "分级样本",
                "check": "最强与最弱相差 ≥ 1.5",
                "ok": spread >= 1.5,
                "detail": spread,
            }
        )
    return {
        "checks": checks,
        "passed": sum(1 for c in checks if c["ok"] is True),
        "total": sum(1 for c in checks if c["ok"] is not None),
        "skipped": sum(1 for c in checks if c["ok"] is None),
    }


def _argument_signals(argument: dict) -> tuple[set, dict]:
    """Every finding category the map shows, from all three places: problem types,
    paragraph verdicts (off_position) and an inconsistent position."""
    problems = [p["type"] for p in argument.get("problems") or []]
    off = [p["role"] for p in argument.get("paragraphs") or [] if p["verdict"] == "off_position"]
    position = argument.get("position")
    consistent = position.get("consistent") if position else None
    signals = set(problems)
    if off:
        signals.add("off_position")
    if consistent is False:  # kept only when backed by a verified contradiction pair
        signals.add("inconsistent_position")
    detail = {
        "problems": problems,
        "off_position_paragraphs": off,
        "position_consistent": consistent,
    }
    return signals, detail


ARGUMENT_EXPECT_KEYS = (
    "argument_max_problems",
    "argument_min_problems",
    "argument_forbid",
    "argument_any_of",
    "argument_position",
)


def _argument_checks(sample: dict, expect: dict) -> list[dict]:
    if not any(key in expect for key in ARGUMENT_EXPECT_KEYS):
        return []
    argument = _argument(sample)
    if not argument:
        return [{"sample": sample["id"], "check": "有论证结构分析", "ok": False, "detail": None}]
    signals, detail = _argument_signals(argument)
    found = detail["problems"]
    checks = []

    def add(check, ok, value):
        checks.append({"sample": sample["id"], "check": check, "ok": ok, "detail": value})

    # Counts look at the problem list only; categories look at every signal.
    if "argument_max_problems" in expect:
        limit = expect["argument_max_problems"]
        add(f"论证问题 ≤ {limit} 条（强文不应被挑出很多问题）", len(found) <= limit, found)
    if "argument_min_problems" in expect:
        limit = expect["argument_min_problems"]
        add(f"论证问题 ≥ {limit} 条（弱文应被指出问题）", len(found) >= limit, found)
    if "argument_forbid" in expect:
        hits = sorted(signals & set(expect["argument_forbid"]))
        add(
            f"不应出现 {' / '.join(expect['argument_forbid'])}（问题类型、段落判定或立场一致性）",
            not hits,
            {**detail, "hits": hits},
        )
    if "argument_any_of" in expect:
        hits = sorted(signals & set(expect["argument_any_of"]))
        add(
            f"应标出 {' / '.join(expect['argument_any_of'])}（问题类型或段落判定偏离）",
            bool(hits),
            {**detail, "hits": hits},
        )
    if expect.get("argument_position"):
        position = argument.get("position")
        add("找到可核实的立场句", position is not None, position and position["quote"])
    return checks


def _off_topic_rewrite_check(sample: dict) -> dict:
    """The off-topic sample's rewrite may only pass quality if it no longer is the
    off-topic essay (independent of the model's own off-topic flag)."""
    generation = sample["generations"].get("rewrite") or {}
    result = generation.get("result") if generation.get("status") == "ready" else None
    check = {"sample": sample["id"], "check": "离题样本：通过质量检查的改写必须已按题目重写"}
    if not result:
        # Not run in this batch, or failed (counted in the rewrite metrics): this check
        # has nothing to look at, so it is skipped rather than counted as passed.
        detail = "本批未运行改写" if not generation else "改写未生成（见改写指标）"
        return {**check, "ok": None, "detail": detail}
    sub = sample["submission"]
    coverage = rewrite_quality.prompt_coverage(sub.get("prompt_text", ""), result["essay"])
    overlap = rewrite_quality.original_overlap(result["essay"], sub["essay_text"])
    still_off = (
        coverage is not None
        and coverage < rewrite_quality.STILL_OFF_TOPIC_PROMPT_COVERAGE
        and overlap >= rewrite_quality.STILL_OFF_TOPIC_ORIGINAL_OVERLAP
    )
    ok = not (result.get("quality_passed") and still_off)
    detail = (
        f"题干重合 {coverage:.0%}，原文重合 {overlap:.0%}，质量通过={result.get('quality_passed')}"
    )
    return {**check, "ok": ok, "detail": detail}


def _calibration(run_data: dict) -> dict | None:
    pairs = {key: [] for key in ("overall",) + CRITERION_KEYS}
    for sample in run_data["samples"]:
        teacher = sample.get("teacher") or {}
        if not teacher:
            continue
        ai = _scores(sample)
        for key in pairs:
            t = teacher.get(key)
            a = ai.get(key)
            if isinstance(t, (int, float)) and a is not None:
                pairs[key].append((float(a), float(t)))
    if not any(pairs.values()):
        return None
    out = {}
    for key, values in pairs.items():
        if not values:
            continue
        diffs = [a - t for a, t in values]
        out[key] = {
            "n": len(values),
            "mae": round(statistics.fmean(abs(d) for d in diffs), 3),
            "bias": round(statistics.fmean(diffs), 3),
            "within_0_5": _rate(sum(1 for d in diffs if abs(d) <= 0.5), len(diffs)),
            "exact": _rate(sum(1 for d in diffs if d == 0), len(diffs)),
        }
    return out


def _usage_summary(calls: list[dict]) -> dict:
    """Known subtotals remain useful, but missing usage is never a measured zero."""
    known = {"prompt": 0, "completion": 0}
    complete = {key: True for key in known}
    unknown_calls = 0
    for call in calls:
        usage = call.get("usage") or {}
        call_known = True
        for short, field in (("prompt", "prompt_tokens"), ("completion", "completion_tokens")):
            value = usage.get(field)
            if type(value) is int and value >= 0:
                known[short] += value
            else:
                complete[short] = False
                call_known = False
        unknown_calls += not call_known
    return {
        "calls": len(calls),
        "unknown_usage_calls": unknown_calls,
        "complete": unknown_calls == 0,
        "tokens": {key: known[key] if complete[key] else None for key in known},
        "known_tokens": known,
    }


def _connectivity(first_call: dict | None) -> dict:
    if not first_call:
        return {
            "ok": False,
            "error": None,
            "response_received": False,
            "authenticated": None,
            "generation_ok": False,
            "generation_error": None,
        }
    error = first_call.get("error")
    status = first_call.get("http_status")
    if status is None and isinstance(error, str) and error.startswith("http_"):
        try:
            status = int(error.removeprefix("http_"))
        except ValueError:
            pass
    received = bool(first_call.get("response_received") or status or first_call["ok"])
    authenticated = None
    if status in {401, 403}:
        authenticated = False
    elif first_call["ok"] or (status is not None and 200 <= status < 300):
        authenticated = True
    connected = received and authenticated is True
    return {
        "ok": connected,
        "error": None if connected else error,
        "response_received": received,
        "authenticated": authenticated,
        "generation_ok": first_call["ok"],
        "generation_error": error if not first_call["ok"] else None,
    }


def build_report(
    run_data: dict, *, price_in: float | None = None, price_out: float | None = None
) -> dict:
    kinds = {kind: _kind_metrics(kind, run_data) for kind in run_data["kinds"]}
    calls = run_data["calls"]
    text_calls = [c for c in calls if c["kind"] != "describe_image"]
    vision_calls = [c for c in run_data["calls"] if c["kind"] == "describe_image"]
    usage = {
        "total": _usage_summary(calls),
        "text": _usage_summary(text_calls),
        "vision": _usage_summary(vision_calls),
    }
    models = {}
    for call in calls:
        identity = (call.get("provider", "unknown"), call.get("model", "unknown"))
        models.setdefault(identity, []).append(call)
    usage["by_model"] = [
        {"provider": provider, "model": model, **_usage_summary(group)}
        for (provider, model), group in models.items()
    ]
    text_cost = None
    if price_in is not None and price_out is not None and usage["text"]["complete"]:
        tokens = usage["text"]["tokens"]
        text_cost = round(
            tokens["prompt"] / 1e6 * price_in + tokens["completion"] / 1e6 * price_out, 6
        )
    # CLI prices describe the text model. Even complete vision usage cannot be
    # priced with that pair without a separately supplied vision-model price.
    cost = text_cost if not vision_calls else None
    cost_estimate = {
        "scope": "text",
        "covered_cost": text_cost,
        "coverage": (
            "complete"
            if cost is not None
            else ("text_only" if text_cost is not None else "unknown")
        ),
        "vision_cost": None if vision_calls else 0.0,
        "unknown_usage_calls": usage["total"]["unknown_usage_calls"],
        "note": "单价仅用于文本模型；识图费用未估算。缺少 usage 时费用未知，不能视为零账单。",
    }
    first_call = calls[0] if calls else None
    return {
        "started_at": run_data["started_at"],
        "provider": run_data["settings"]["llm_provider"],
        "model": run_data["settings"]["llm_model"],
        "prompt_version": review.prompts.PROMPT_VERSION,
        "evaluate_thinking": run_data["settings"].get("evaluate_thinking", "off"),
        "demo": run_data["settings"]["llm_provider"] == "fake",
        "samples": len(run_data["samples"]),
        "calls": len(run_data["calls"]),
        "max_calls": run_data["max_calls"],
        "aborted": run_data["aborted"],
        "connectivity": _connectivity(first_call),
        "kinds": kinds,
        "vision_calls": len(vision_calls),
        "evidence": _evidence_metrics(run_data),
        "argument": _argument_metrics(run_data),
        "refine_rewrite": _refine_rewrite_metrics(run_data),
        "sanity": _sanity(run_data),
        "calibration": _calibration(run_data),
        "tokens": usage["total"]["tokens"],
        "usage": usage,
        "estimated_cost": cost,
        "cost_estimate": cost_estimate,
        "per_sample": [
            {
                "id": s["id"],
                "scores": {k: v for k, v in _scores(s).items() if not k.startswith("_")},
                "teacher": s.get("teacher") or {},
                "image_status": s["image_status"],
                "argument_problems": [
                    p["type"] for p in (_argument(s) or {}).get("problems") or []
                ],
                "statuses": {k: g["status"] for k, g in s["generations"].items()},
                "errors": {
                    k: g["error_code"] for k, g in s["generations"].items() if g["error_code"]
                },
            }
            for s in run_data["samples"]
        ],
    }


def _pct(value) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def _removed_line(removed: dict) -> str:
    labels = (("criteria", "评分项"), ("argument", "论证结构"), ("priorities", "提升重点"))
    parts = "、".join(f"{label} {removed.get(key, 0)}" for key, label in labels)
    return (
        f"- 建议因含原文、题目和题图都没有的数字被删去（整份评价合计）：{removed.get('total', 0)} 条"
        f"（{parts}）"
    )


def _argument_markdown(argument: dict | None) -> list[str]:
    if not argument or not (argument["task2_evaluations"] or argument.get("evaluate_attempts")):
        return []
    types = "；".join(f"{k} ×{v}" for k, v in argument["problem_types"].items()) or "无"
    verdicts = "；".join(f"{k} ×{v}" for k, v in argument["paragraph_verdicts"].items()) or "无"
    return [
        "",
        "## 论证结构（Task 2，不单独计分）",
        "",
        f"- 最终采用的 Task 2 评价 {argument['task2_evaluations']} 篇，有论证结构分析 "
        f"{argument['with_argument']} 篇，找到可核实立场句 {argument['with_position']} 篇",
        f"- Task 2 评价请求 {argument['evaluate_attempts']} 次（含重试），其中 "
        f"{argument['attempts_rejected_for_argument']} 次因缺少论证结构或没有可核实的段落被整份"
        "拒绝（这些不计入下面的条目统计）",
        f"- 段落中心句 {argument['paragraphs']} 条（判定：{verdicts}）；论证问题 "
        f"{argument['problems']} 条（{types}）；可选优化 {argument.get('improvements', 0)} 条"
        "（不是错误，不计入问题数）",
        f"- AI 判断自相矛盾 {argument.get('self_conflicts', 0)} 处（已标需人工确认）；“没有支撑”"
        f"但 AI 自己引用了同段支撑、改列可选优化 {argument.get('reclassified', 0)} 条；论证部分的"
        f"建议因含无来源数字被删去 {argument.get('suggestions_removed', 0)} 条（整份评价的合计见"
        "“证据与内容”）",
        f"- 条目统计（只看最终采用的评价，立场、每段、每条问题、每条可选优化各计 1 条）：模型给出 "
        f"{argument['returned']} 条 = 采用 {argument['kept']} + 格式不对或无法核实而丢弃 "
        f"{argument['dropped']} + 重复 {argument['duplicates']} + 超出上限 "
        f"{argument['over_limit']}；**丢弃率 {_pct(argument['dropped_rate'])}**",
    ]


def render_markdown(report: dict) -> str:
    lines = [
        "# 写作 AI 真实模型小样本验证",
        "",
        f"- 时间：{report['started_at']}",
        f"- 模型：{report['provider']} / {report['model']} · 提示词 {report['prompt_version']}"
        f" · 评价思考模式 {report.get('evaluate_thinking', 'off')}",
        f"- 样本 {report['samples']} 篇 · 模型调用 {report['calls']} 次（上限 {report['max_calls']}）",
    ]
    if report["demo"]:
        lines.append("- **演示模式（fake）：结果不代表任何真实模型**")
    conn = report["connectivity"]
    auth = {True: "通过", False: "失败", None: "未知"}[conn["authenticated"]]
    lines += [
        f"- 传输：{'已收到模型服务响应' if conn['response_received'] else '未收到模型服务响应'}；鉴权：{auth}",
        f"- 首个内容输出：{'已返回' if conn['generation_ok'] else '失败（' + str(conn['generation_error']) + '）'}；内容合格率另见下表。",
    ]
    if report["aborted"]:
        lines.append(f"- **已中止**：{report['aborted']['message']}（{report['aborted']['code']}）")
    lines += [
        "",
        "## 合格率",
        "",
        "| 类型 | 首轮纯 JSON | 首轮通过校验 | 最终成功 | p50 / p90 延迟 | 首轮被拒原因 |",
        "|---|---|---|---|---|---|",
    ]
    names = {"evaluate": "原稿评价", "refine": "逐句精修", "rewrite": "整篇改写"}
    for kind, m in report["kinds"].items():
        reasons = "；".join(f"{r} ×{n}" for r, n in m["first_attempt_rejections"].items()) or "—"
        latency = f"{m['latency_ms_p50'] or '—'} / {m['latency_ms_p90'] or '—'} ms"
        lines.append(
            f"| {names.get(kind, kind)} | {_pct(m['first_attempt_json_ok'])} | "
            f"{_pct(m['first_attempt_valid'])} | {_pct(m['final_ready'])} | {latency} | {reasons} |"
        )
    lines += ["", "## 输出预算与思考模式", ""]
    for kind, m in report["kinds"].items():
        reasoning = (
            "未报告"
            if m.get("reasoning_tokens") is None
            else f"合计 {m['reasoning_tokens']}，单次最多 {m['reasoning_tokens_max']}"
        )
        lines.append(
            f"- {names.get(kind, kind)}：思考模式 {' / '.join(m.get('thinking') or ['off'])}；"
            f"输出上限 {' / '.join(str(b) for b in m.get('max_tokens') or []) or '—'}；"
            f"单次输出峰值 {m.get('completion_tokens_max') or '—'}；思考 token {reasoning}；"
            f"截断 {m.get('truncated', 0)} 次、超时 {m.get('timeouts', 0)} 次"
        )
    ev, rr = report["evidence"], report["refine_rewrite"]
    lines += [
        "",
        "## 证据与内容",
        "",
        f"- 评分项 {ev['scored_criteria']} 个，引文 {ev['quotes']} 条，能在原文中找到 "
        f"{_pct(ev['quotes_verified'])}",
        _removed_line(ev.get("suggestions_removed") or {}),
        f"- 评价中与原文不符、已附更正的计数说法（段落数、某词出现次数）："
        f"{ev.get('count_corrections', 0)} 处",
        f"- 精修：共 {rr['refine_sentences']} 句，缺句率 {_pct(rr['refine_missing_rate'])}，"
        f"改动率 {_pct(rr['refine_changed_rate'])}",
        f"- 改写：请求 {rr['rewrite_requested']} 篇，生成 {rr['rewrite_generated']} 篇，"
        f"通过质量检查 {rr['rewrite_quality_passed_count']} 篇；"
        f"**占全部请求 {_pct(rr['rewrite_quality_passed_of_requested'])}**（验收口径，"
        f"生成失败计为未通过），占已生成 {_pct(rr['rewrite_quality_passed_of_generated'])}；"
        f"达到字数下限占全部请求 {_pct(rr['rewrite_meets_min_words_of_requested'])}"
        + f"；正文通过（字数、未仍离题）占全部请求 {_pct(rr.get('rewrite_content_passed_of_requested'))}"
        + f"；整篇重写重试 {rr.get('rewrite_full_retries', 0)} 次、只修说明 {rr.get('rewrite_notes_repairs', 0)} 次"
        + (
            f"；质量重试未完成 {rr['rewrite_retry_failed']} 篇"
            if rr["rewrite_retry_failed"]
            else ""
        )
        + (
            "（未通过项："
            + "；".join(f"{k} ×{v}" for k, v in rr["rewrite_quality_issues"].items())
            + "）"
            if rr.get("rewrite_quality_issues")
            else ""
        ),
    ]
    lines += _argument_markdown(report.get("argument"))
    lines += [
        "",
        "## 分数合理性（宽松区间，不是真实分数）",
        "",
        f"通过 {report['sanity']['passed']} / {report['sanity']['total']}"
        + (
            f"（另有 {report['sanity']['skipped']} 项本批未运行，不计入）"
            if report["sanity"].get("skipped")
            else ""
        ),
        "",
    ]
    for check in report["sanity"]["checks"]:
        mark = {True: "✓", False: "✗", None: "–"}[check["ok"]]
        lines.append(f"- {mark} {check['sample']}：{check['check']}（实际：{check['detail']}）")
    if report["calibration"]:
        lines += [
            "",
            "## 与老师评分对比",
            "",
            "| 项目 | 样本数 | 平均绝对误差 | 平均偏差（AI−老师） | ±0.5 以内 | 完全一致 |",
            "|---|---|---|---|---|---|",
        ]
        for key, m in report["calibration"].items():
            lines.append(
                f"| {key} | {m['n']} | {m['mae']} | {m['bias']:+} | {_pct(m['within_0_5'])} | "
                f"{_pct(m['exact'])} |"
            )
    lines += [
        "",
        "## 逐篇结果",
        "",
        "| 样本 | 总分 | TR/TA | CC | LR | GRA | 论证问题 | 状态 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in report["per_sample"]:
        s = row["scores"]
        status = " ".join(f"{k}:{v}" for k, v in row["statuses"].items())
        problems = ", ".join(row.get("argument_problems") or []) or "—"
        lines.append(
            f"| {row['id']} | {s.get('overall') or '—'} | {s.get('task') or '—'} | "
            f"{s.get('coherence') or '—'} | {s.get('lexical') or '—'} | {s.get('grammar') or '—'} "
            f"| {problems} | {status} |"
        )
    tokens = report["tokens"]

    def token_text(value):
        return "未知" if value is None else str(value)

    lines += [
        "",
        f"总 token（含识图）：输入 {token_text(tokens['prompt'])} · 输出 {token_text(tokens['completion'])}",
    ]
    for kind, label in (("text", "文本"), ("vision", "识图")):
        measured = report["usage"][kind]
        counts = measured["tokens"]
        lines.append(
            f"- {label}：输入 {token_text(counts['prompt'])} · 输出 {token_text(counts['completion'])}；"
            f"缺少用量的调用 {measured['unknown_usage_calls']} 次"
        )
    if not report["usage"]["total"]["complete"]:
        known = report["usage"]["total"]["known_tokens"]
        lines.append(
            f"已知用量小计：输入 {known['prompt']} · 输出 {known['completion']}（不是完整账单用量）。"
        )
    if report["estimated_cost"] is not None:
        lines.append(f"按输入的单价估算费用：{report['estimated_cost']}")
    else:
        lines.append("完整费用：未知（不能视为零费用）。")
        covered = report["cost_estimate"]["covered_cost"]
        if covered is not None:
            lines.append(f"仅文本部分按输入单价估算：{covered}；识图费用未估算。")
    lines += ["", "原始调用记录见同目录 `raw_calls.jsonl`（含模型原文，仅保存在本机）。"]
    return "\n".join(lines) + "\n"


def write_report(run_data: dict, report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    # Full results for realcheck-compare (synthetic essays and model output; no key).
    (out_dir / "run_data.json").write_text(
        json.dumps(run_data, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    with (out_dir / "raw_calls.jsonl").open("w", encoding="utf-8") as handle:
        for call in run_data["calls"]:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")
    return out_dir / "report.md"
