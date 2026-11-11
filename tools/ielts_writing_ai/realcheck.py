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
import hashlib
import json
import math
import statistics
import tempfile
import time
from collections import Counter
from pathlib import Path

from . import access, jsonshape, review, rewrite_quality
from . import essay as essay_lib
from . import samples as builtin_samples
from .ledger import LedgerError
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
    def __init__(self, max_calls: int, ledger=None):
        self.max_calls = validate_max_calls(max_calls)
        self.records: list[dict] = []
        self.sample_id = ""
        self.abort: LLMError | None = None
        # A persistent batch ledger (ledger.Ledger): every request is reserved there,
        # fsync'd, before it is sent, so a killed run still counts what it sent.
        self.ledger = ledger

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
            # Fingerprint of exactly what the model was sent (options such as thinking,
            # budget and timeout are not part of it), for same-condition comparisons.
            "input_sha256": _messages_sha(messages),
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
        if rec.ledger is not None:
            # Persistent reservation before dispatch; a refusal stops the whole run.
            try:
                entry["ledger_id"] = rec.ledger.reserve(
                    sample=rec.sample_id,
                    kind=entry["kind"],
                    model=self.model,
                    attempt=entry["attempt"],
                )
            except LedgerError as exc:
                rec.abort = LLMError(exc.code, exc.message)
                raise rec.abort from None
        # Reserve before dispatch, also covering unexpected client exceptions.
        rec.records.append(entry)
        started = time.monotonic()
        try:
            try:
                result = self.inner.complete(messages, **kwargs)
            except LLMError as exc:
                usage = getattr(exc, "usage", None) or {}
                entry.update(
                    error=exc.code,
                    latency_ms=_ms(started),
                    usage=usage,
                    # Failed responses (e.g. truncated while thinking) are billed too.
                    reasoning_tokens=reasoning_tokens(usage),
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
                json_ok=(
                    (parse_strict_json(result.text) is not None) if entry["json_mode"] else None
                ),
                reasoning_tokens=reasoning_tokens(result.usage),
                reasoning_chars=len(getattr(result, "reasoning", "") or ""),
                # Kept only in the local raw_calls.jsonl, for reviewing what the model weighed.
                reasoning=getattr(result, "reasoning", "") or "",
            )
            return result
        finally:
            if entry.get("ledger_id"):
                rec.ledger.complete(
                    entry["ledger_id"], ok=entry["ok"], error=entry["error"], usage=entry["usage"]
                )


def _messages_sha(messages) -> str:
    text = json.dumps(messages, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
            _validate_teacher_findings(item, number)
            _validate_raters(item, number)
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


def _validate_teacher_findings(item: dict, number: int) -> None:
    """Optional teacher annotations: [{"quote": verbatim span, "note": teacher's comment}].
    Quotes must be in the essay so they can be matched against the AI's findings."""
    findings = item.get("teacher_findings")
    if findings is None:
        return
    if not isinstance(findings, list):
        raise RealCheckError(f"第 {number} 行 teacher_findings 必须是列表")
    for n, entry in enumerate(findings, 1):
        quote = entry.get("quote") if isinstance(entry, dict) else None
        if not isinstance(quote, str) or not quote.strip():
            raise RealCheckError(f"第 {number} 行 teacher_findings 第 {n} 条缺少 quote")
        if not essay_lib.contains_quote(item["essay"], quote):
            raise RealCheckError(
                f"第 {number} 行 teacher_findings 第 {n} 条的 quote 不在作文里：{quote[:40]}"
            )


SCORE_KEYS = ("overall",) + CRITERION_KEYS


def _validate_raters(item: dict, number: int) -> None:
    """Optional fields for held-out sets:
    - "teachers": [{"rater": "A", "overall": 7, "task": 7, ...}, ...] - several human
      raters of the same essay; "teacher" (used for the calibration table) defaults to
      their mean, and the report compares the AI with the raters' own disagreement;
    - "group" + "nominal_band": essays written to descending target levels on one
      question; only their order is checked, the nominal bands are not a score baseline;
    - "image_description": a chart reading made earlier, used instead of calling the
      vision model (so two runs judge exactly the same reading)."""
    raters = item.get("teachers")
    if raters is not None:
        if not isinstance(raters, list) or not all(isinstance(r, dict) for r in raters):
            raise RealCheckError(f"第 {number} 行 teachers 必须是对象列表")
        for rater in raters:
            for key in SCORE_KEYS:
                if key in rater and not _is_band(rater[key]):
                    raise RealCheckError(f"第 {number} 行 teachers 的 {key} 必须是 0–9 的数字")
        if raters and not item.get("teacher"):
            item["teacher"] = {
                key: round(statistics.fmean(r[key] for r in raters if key in r), 3)
                for key in SCORE_KEYS
                if any(key in r for r in raters)
            }
    if item.get("nominal_band") is not None and not _is_band(item["nominal_band"]):
        raise RealCheckError(f"第 {number} 行 nominal_band 必须是 0–9 的数字")
    if item.get("group") is not None and not isinstance(item["group"], str):
        raise RealCheckError(f"第 {number} 行 group 必须是字符串")
    description = item.get("image_description")
    if description is not None and not (isinstance(description, str) and description.strip()):
        raise RealCheckError(f"第 {number} 行 image_description 必须是非空字符串")


def _is_band(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 9


def expand_repeats(items: list[dict], repeat: int) -> list[dict]:
    """Each sample `repeat` times (ids x, x#r2, x#r3 ...), to see run-to-run variation."""
    if type(repeat) is not int or repeat < 1:
        raise RealCheckError("--repeat 必须为正整数")
    out = []
    for item in items:
        for n in range(1, repeat + 1):
            copy = dict(item, repeat_of=item["id"])
            if n > 1:
                copy["id"] = f"{item['id']}#r{n}"
            out.append(copy)
    return out if repeat > 1 else items


IMAGE_FILE_VERSION = 2


def image_file(outcomes: dict) -> dict:
    """image_descriptions.json: every essay's reading or failure, so a later run (the
    other model) gets exactly the same image input, including a failure."""
    return {"version": IMAGE_FILE_VERSION, "images": outcomes}


def load_image_outcomes(path) -> dict:
    """{sample id: {"status", "description", "error"}} from image_descriptions.json
    (version 2, or the older {sample id: reading} form)."""
    path = Path(path)
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RealCheckError(f"读不了题图识别结果文件 {path}：{exc}") from None
    if not isinstance(stored, dict):
        raise RealCheckError("题图识别结果文件必须是 JSON 对象")
    if stored.get("version") == IMAGE_FILE_VERSION:
        images = stored.get("images")
        if not isinstance(images, dict):
            raise RealCheckError("题图识别结果文件缺少 images")
        out = {}
        for key, value in images.items():
            if not (isinstance(value, dict) and value.get("status") in ("ready", "failed")):
                raise RealCheckError(f"题图识别结果 {key} 的状态无效")
            if value["status"] == "ready" and not (
                isinstance(value.get("description"), str) and value["description"].strip()
            ):
                raise RealCheckError(f"题图识别结果 {key} 标为可用但没有内容")
            out[key] = value
        return out
    return {
        key: {"status": "ready", "description": value, "error": None}
        for key, value in stored.items()
        if isinstance(value, str) and value.strip()
    }


def apply_image_descriptions(items: list[dict], path, *, require_ready: bool = False) -> int:
    """Reuse the chart readings (or failures) saved by an earlier run. Returns how many
    samples got one. With require_ready, every Task 1 sample with an image must have a
    usable reading, otherwise nothing is run."""
    outcomes = load_image_outcomes(path)
    used, missing = 0, []
    for item in items:
        if item["task_type"] != "task1":
            continue
        outcome = outcomes.get(item.get("repeat_of") or item["id"])
        if require_ready and item.get("image") and (not outcome or outcome["status"] != "ready"):
            missing.append(item["id"])
            continue
        if not outcome:
            continue
        if outcome["status"] == "ready":
            item["image_description"] = outcome["description"]
        else:
            item["image_frozen"] = outcome
        used += 1
    if missing:
        raise RealCheckError("这些样本没有可用的题图识别结果：" + "、".join(missing))
    return used


def final_failures(run_data: dict, planned: int) -> int:
    """Planned samples without a ready result for every requested kind (samples that
    were never run, e.g. after an abort, count as failures)."""
    kinds = run_data["kinds"]
    ready = sum(
        1
        for s in run_data["samples"]
        if all((s["generations"].get(k) or {}).get("status") == "ready" for k in kinds)
    )
    return planned - ready


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
    ledger=None,
) -> dict:
    """Run every sample and return the raw run data (see build_report)."""
    recorder = Recorder(max_calls, ledger)
    _validate_sample_ids(items)
    if ledger is not None:
        try:
            ledger.check()
        except LedgerError as exc:
            raise RealCheckError(exc.message) from None
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
        # One chart reading per essay - success or failure - shared by its repeats: a
        # failed reading is not retried, so every run of the essay sees the same input
        # and the image calls stay at one per essay (review 2026-11-11).
        images: dict[str, dict] = {}
        for number, item in enumerate(items, 1):
            if recorder.abort is not None:
                break
            recorder.sample_id = item["id"]
            base = item.get("repeat_of") or item["id"]
            if (
                base in images
                and not item.get("image_description")
                and not item.get("image_frozen")
            ):
                item = dict(item, image_frozen=images[base])
            sample = _run_sample(
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
            if item["task_type"] == "task1" and sample["image_status"] in ("ready", "failed"):
                images.setdefault(
                    base,
                    {
                        "status": sample["image_status"],
                        "description": sample["submission"]["image_description"],
                        "error": sample["image_error"],
                    },
                )
            results.append(sample)
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
        "image_outcomes": images,
        "image_descriptions": {
            k: v["description"] for k, v in images.items() if v["status"] == "ready"
        },
        "code_sha256": code_fingerprint(),
    }


def _run_sample(
    item, number, storage, generator, settings, user_id, kinds, target_band, *, use_vision
):
    essay = essay_lib.normalize_newlines(item["essay"]).strip()
    image_path = image_mime = None
    image_status = "none"
    frozen = item.get("image_frozen") if item["task_type"] == "task1" else None
    if not frozen and item["task_type"] == "task1" and item.get("image_description"):
        frozen = {"status": "ready", "description": item["image_description"], "error": None}
    reused = frozen
    if frozen:
        pass  # an earlier reading or failure: no image upload, no vision call
    elif item.get("image") and item["task_type"] == "task1":
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
    if frozen:
        ready = frozen["status"] == "ready"
        storage.set_image_result(
            created["id"],
            status=frozen["status"],
            description=frozen.get("description") if ready else None,
            error=None if ready else frozen.get("error"),
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
        "teachers": item.get("teachers") or [],
        "teacher_findings": item.get("teacher_findings") or [],
        "group": item.get("group"),
        "nominal_band": item.get("nominal_band"),
        "repeat_of": item.get("repeat_of"),
        "image_reused": bool(reused),
        "submission": {
            k: submission.get(k)
            for k in (
                "prompt_text",
                "task_type",
                "essay_text",
                "word_count",
                "target_band",
                "image_status",
                "image_error",
                "image_description",  # the chart reading also reaches the model
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
        if jsonshape.unwrap(text).startswith("{"):
            return "JSON 括号或结构错误"  # the details: metrics["json_problems"]
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
    # Every attempt whose reply was not one JSON object, with what exactly was wrong
    # (the same diagnosis the retry note gives the model).
    json_problems = [
        {
            "sample": c["sample"],
            "attempt": c["attempt"],
            "problem": review.json_problem(
                kind, c.get("text"), (by_sample.get(c["sample"]) or {}).get("submission") or {}
            ),
        }
        for c in calls
        if c["ok"] and c.get("json_mode") and parse_strict_json(c.get("text")) is None
    ]
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
    # Thinking calls whose response did not report reasoning tokens (including calls
    # with no response at all): with any of these the known sum is only a subtotal.
    unreported = sum(
        1
        for c in calls
        if (c.get("thinking") or "off") != "off" and not isinstance(c.get("reasoning_tokens"), int)
    )
    budgets = sorted({c["max_tokens"] for c in calls if isinstance(c.get("max_tokens"), int)})
    return {
        "thinking": sorted({c.get("thinking") or "off" for c in calls}),
        # Output budget per call and the largest output actually used: the budget for
        # a thinking evaluation must be set from these, not carried over.
        "max_tokens": budgets,
        "completion_tokens_max": max(completions) if completions else None,
        # Over every call, failed ones included. reasoning_tokens is the complete total,
        # or None when some thinking call did not report (then see the known subtotal
        # and the number of unreported calls); None never means zero.
        "reasoning_tokens_known": sum(reasoning) if reasoning else None,
        "reasoning_unreported_calls": unreported,
        "reasoning_tokens": sum(reasoning) if reasoning and not unreported else None,
        "reasoning_tokens_max": max(reasoning) if reasoning else None,
        "truncated": sum(1 for c in calls if c.get("error") == "truncated"),
        "timeouts": sum(1 for c in calls if c.get("error") == "timeout"),
        "calls": len(calls),
        "first_attempts": len(first),
        "first_attempt_json_ok": _rate(sum(1 for c in first if c.get("json_ok")), len(first)),
        "first_attempt_valid": _rate(first_valid, len(first)),
        "first_attempt_rejections": dict(rejections.most_common()),
        "json_problems": json_problems,
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


def ai_spans(result: dict) -> list[str]:
    """Every essay span the evaluation points at as a problem or a place to improve."""
    spans = [i.get("quote") for c in result.get("criteria") or [] for i in c.get("issues") or []]
    argument = result.get("argument") or {}
    for problem in argument.get("problems") or []:
        spans += [problem.get("quote"), problem.get("conflicts_with")]
    spans += [i.get("quote") for i in argument.get("improvements") or []]
    spans += [c.get("quote") for c in result.get("consistency_issues") or []]
    return [s for s in spans if s]


YES, NO, UNSURE = "yes", "no", "uncertain"


def _strip(text: str) -> str:
    return essay_lib.squash(text).strip(" .,;:!?\"'")


def _locate(essay: str, quote: str) -> list[tuple[int, int]]:
    """Character ranges (in the comparison form of the essay) where the quote occurs."""
    hay, needle = essay_lib.squash(essay), _strip(quote)
    found, start = [], hay.find(needle) if needle else -1
    while start != -1:
        found.append((start, start + len(needle)))
        start = hay.find(needle, start + 1)
    return found


def span_relation(essay: str, a: str, b: str) -> str:
    """Whether two quotes point at the same place in the essay: their character
    ranges intersect. Shared words are not a shared place (review of 1c865eb).
    'uncertain' when a quote occurs more than once and only some occurrences meet."""
    ranges_a, ranges_b = _locate(essay, a), _locate(essay, b)
    if not ranges_a or not ranges_b:
        return NO
    hits = [x[0] < y[1] and y[0] < x[1] for x in ranges_a for y in ranges_b]
    return YES if all(hits) else UNSURE if any(hits) else NO


def spans_overlap(a: str, b: str, essay: str | None = None) -> bool:
    """Same place in the essay. With the essay: intersecting character ranges. Without
    it, only when one quote contains the other."""
    if essay:
        return span_relation(essay, a, b) == YES
    sa, sb = _strip(a), _strip(b)
    return bool(sa and sb) and (sa in sb or sb in sa)


def _relation(essay: str, a: str, b: str) -> str:
    return span_relation(essay, a, b) if essay else (YES if spans_overlap(a, b) else NO)


def teacher_coverage(sample: dict) -> dict | None:
    """Per teacher annotation: did the AI point at the same place? Samples whose
    evaluation did not succeed stay in the count, marked as not evaluated."""
    findings = sample.get("teacher_findings") or []
    if not findings:
        return None
    essay = (sample.get("submission") or {}).get("essay_text") or ""
    generation = sample["generations"].get("evaluate") or {}
    result = generation.get("result") if generation.get("status") == "ready" else None
    if not result:
        return {
            "evaluated": False,
            "status": generation.get("status") or "missing",
            "findings": [{**f, "covered": None, "coverage": "not_evaluated"} for f in findings],
            "covered": 0,
            "uncertain": 0,
            "total": len(findings),
            "ai_spans": 0,
            "ai_spans_not_marked_by_teacher": 0,
        }
    spans = ai_spans(result)
    rows = []
    for finding in findings:
        relations = [_relation(essay, finding["quote"], span) for span in spans]
        state = YES if YES in relations else UNSURE if UNSURE in relations else NO
        rows.append({**finding, "covered": state == YES, "coverage": state})
    extra = [
        span for span in spans if all(_relation(essay, f["quote"], span) == NO for f in findings)
    ]
    return {
        "evaluated": True,
        "status": "ready",
        "findings": rows,
        "covered": sum(1 for r in rows if r["coverage"] == YES),
        "uncertain": sum(1 for r in rows if r["coverage"] == UNSURE),
        "total": len(rows),
        "ai_spans": len(spans),
        "ai_spans_not_marked_by_teacher": len(extra),
    }


def _teacher_findings_metrics(run_data: dict) -> dict | None:
    per_sample = {}
    for sample in run_data["samples"]:
        coverage = teacher_coverage(sample)
        if coverage:
            per_sample[sample["id"]] = coverage
    if not per_sample:
        return None
    evaluated = [c for c in per_sample.values() if c["evaluated"]]
    covered = sum(c["covered"] for c in per_sample.values())
    total = sum(c["total"] for c in per_sample.values())
    evaluated_total = sum(c["total"] for c in evaluated)
    return {
        # Over every requested annotation: a failed evaluation counts as not covered.
        "covered": covered,
        "total": total,
        "rate": _rate(covered, total),
        "uncertain": sum(c["uncertain"] for c in per_sample.values()),
        # Conditional view, only over the evaluations that succeeded.
        "evaluated_samples": len(evaluated),
        "evaluated_total": evaluated_total,
        "rate_evaluated": _rate(covered, evaluated_total),
        "failed_samples": [k for k, c in per_sample.items() if not c["evaluated"]],
        "samples": per_sample,
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


def _pair_gap(values: list[float]) -> float:
    return statistics.fmean(abs(a - b) for i, a in enumerate(values) for b in values[i + 1 :])


def rater_agreement(samples: list[dict], ids: set[str] | None = None) -> dict | None:
    """The AI against several human raters of the same essays. The yardstick is the
    raters' own disagreement - on the *same* essays: rater_gap and ai_gap use only the
    essays the AI scored (review 2026-11-11: a failed essay with split raters had
    widened the yardstick without adding to the AI's error). The raters' gap over all
    planned essays is kept separately as rater_gap_all. ids restricts the rows (two
    models are compared on the essays both scored)."""
    rows = {key: [] for key in SCORE_KEYS}
    for sample in samples:
        if ids is not None and sample["id"] not in ids:
            continue
        raters = sample.get("teachers") or []
        ai = _scores(sample)
        for key in SCORE_KEYS:
            human = [float(r[key]) for r in raters if _is_band(r.get(key))]
            if len(human) >= 2:
                rows[key].append((ai.get(key), human))
    out = {}
    for key, values in rows.items():
        if not values:
            continue
        scored = [(float(ai), h) for ai, h in values if ai is not None]
        out[key] = {
            "essays": len(values),
            "scored": len(scored),
            "failed": len(values) - len(scored),
            "rater_gap_all": round(statistics.fmean(_pair_gap(h) for _ai, h in values), 3),
            "rater_gap": (
                round(statistics.fmean(_pair_gap(h) for _ai, h in scored), 3) if scored else None
            ),
            "ai_gap": (
                round(statistics.fmean(abs(ai - statistics.fmean(h)) for ai, h in scored), 3)
                if scored
                else None
            ),
            "ai_bias": (
                round(statistics.fmean(ai - statistics.fmean(h) for ai, h in scored), 3)
                if scored
                else None
            ),
            "within_range": _rate(
                sum(1 for ai, h in scored if min(h) - 0.5 <= ai <= max(h) + 0.5), len(scored)
            ),
        }
    return out or None


def _rater_agreement(run_data: dict) -> dict | None:
    return rater_agreement(run_data["samples"])


def _ordering(run_data: dict) -> dict | None:
    """Groups of essays written to descending target levels on one question: does the
    AI's overall band follow the order? (The nominal bands are not certified scores.)
    The spread is between the planned highest and lowest levels; when either end has
    no score it is None - it is never taken between surviving middle levels (review
    2026-11-11)."""
    groups: dict[str, list] = {}
    for sample in run_data["samples"]:
        if sample.get("group") and _is_band(sample.get("nominal_band")):
            groups.setdefault(sample["group"], []).append(
                (float(sample["nominal_band"]), _scores(sample).get("overall"), sample["id"])
            )
    out = {}
    for name, rows in groups.items():
        rows.sort(key=lambda r: (-r[0], r[2]))
        scored = [(nominal, float(ai)) for nominal, ai, _id in rows if ai is not None]
        pairs = [
            (hi, lo)
            for i, (n_hi, hi) in enumerate(scored)
            for n_lo, lo in scored[i + 1 :]
            if n_hi > n_lo
        ]
        highest, lowest = rows[0][0], rows[-1][0]
        top = [ai for nominal, ai in scored if nominal == highest]
        bottom = [ai for nominal, ai in scored if nominal == lowest]
        out[name] = {
            "rows": [{"id": i, "nominal": n, "ai": ai} for n, ai, i in rows],
            "missing": len(rows) - len(scored),
            "pairs": len(pairs),
            "inversions": sum(1 for hi, lo in pairs if hi < lo),
            "ties": sum(1 for hi, lo in pairs if hi == lo),
            "highest": highest,
            "lowest": lowest,
            "spread": (
                round(statistics.fmean(top) - statistics.fmean(bottom), 3)
                if top and bottom and highest > lowest
                else None
            ),
        }
    return out or None


def _repeat_spread(run_data: dict) -> dict | None:
    """Run-to-run variation for samples run several times (--repeat)."""
    groups: dict[str, list] = {}
    for sample in run_data["samples"]:
        if sample.get("repeat_of"):
            groups.setdefault(sample["repeat_of"], []).append(_scores(sample))
    rows = []
    for base, runs in groups.items():
        if len(runs) < 2:
            continue
        bands = {key: [float(r[key]) for r in runs if r.get(key) is not None] for key in SCORE_KEYS}
        rows.append(
            {
                "id": base,
                "runs": len(runs),
                "ready": sum(1 for r in runs if r["_ready"]),
                "overall": bands["overall"],
                "spread": {
                    key: round(max(v) - min(v), 3) for key, v in bands.items() if len(v) >= 2
                },
            }
        )
    if not rows:
        return None
    overall = [r["spread"]["overall"] for r in rows if "overall" in r["spread"]]
    return {
        "samples": rows,
        "overall_spread_mean": round(statistics.fmean(overall), 3) if overall else None,
        "overall_spread_max": max(overall) if overall else None,
        "any_failed": sum(1 for r in rows if r["ready"] < r["runs"]),
    }


def _usage_summary(calls: list[dict]) -> dict:
    """Known subtotals remain useful, but missing usage is never a measured zero."""
    known = {"prompt": 0, "completion": 0}
    complete = {key: True for key in known}
    unknown_calls = 0
    cache_hits, cache_reported = 0, bool(calls)
    for call in calls:
        usage = call.get("usage") or {}
        hit = _cache_hit_tokens(usage)
        cache_hits += hit or 0
        cache_reported = cache_reported and hit is not None
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
        # Input tokens served from the provider's cache (billed at a lower price);
        # None when any call did not report them.
        "cache_hit_tokens": cache_hits if cache_reported else None,
    }


def _cache_hit_tokens(usage: dict) -> int | None:
    """DeepSeek reports prompt_cache_hit_tokens, OpenAI-style APIs
    prompt_tokens_details.cached_tokens; None when neither is there."""
    for value in (
        usage.get("prompt_cache_hit_tokens"),
        (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
    ):
        if type(value) is int and value >= 0:
            return value
    return None


def text_cost(text_usage: dict, prices: dict | None) -> tuple[float | None, str | None]:
    """(cost, basis) of the text calls. With a cache-hit price and reported cache hits
    the input is split (hit / miss); otherwise every input token is charged the normal
    input price, which overstates the cost when the cache was hit. Thinking tokens are
    part of the completion tokens and are not added again."""
    prices = prices or {}
    tokens = (text_usage or {}).get("tokens") or {}
    if prices.get("in") is None or prices.get("out") is None:
        return None, None
    if tokens.get("prompt") is None or tokens.get("completion") is None:
        return None, None
    hits = (text_usage or {}).get("cache_hit_tokens")
    if prices.get("cached_in") is not None and hits is not None:
        miss = max(tokens["prompt"] - hits, 0)
        cost = miss * prices["in"] + hits * prices["cached_in"]
        basis = "cache_split"
    else:
        cost = tokens["prompt"] * prices["in"]
        basis = "input_at_full_price"
    return round((cost + tokens["completion"] * prices["out"]) / 1e6, 6), basis


def code_fingerprint() -> str:
    """sha256 over the tool's own source files (not the tests): two runs compared as
    "same conditions" should have been produced by the same code."""
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


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
    run_data: dict,
    *,
    price_in: float | None = None,
    price_out: float | None = None,
    price_cached_in: float | None = None,
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
    prices = {"in": price_in, "cached_in": price_cached_in, "out": price_out}
    covered, basis = text_cost(usage["text"], prices)
    # CLI prices describe the text model. Even complete vision usage cannot be
    # priced with that pair without a separately supplied vision-model price.
    cost = covered if not vision_calls else None
    cost_estimate = {
        "scope": "text",
        "covered_cost": covered,
        "basis": basis,
        "coverage": (
            "complete" if cost is not None else ("text_only" if covered is not None else "unknown")
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
        "rater_agreement": _rater_agreement(run_data),
        "ordering": _ordering(run_data),
        "repeat_spread": _repeat_spread(run_data),
        "teacher_findings": _teacher_findings_metrics(run_data),
        "tokens": usage["total"]["tokens"],
        "usage": usage,
        "estimated_cost": cost,
        "cost_estimate": cost_estimate,
        "prices": prices,
        # What the provider says answered (may be a dated version of the configured
        # model) and which code produced this run: both belong to the conditions.
        "served_models": sorted(
            {str(c["model"]) for c in text_calls if c.get("ok") and c.get("model")}
        ),
        "code_sha256": run_data.get("code_sha256"),
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


def _reasoning_text(m: dict) -> str:
    known, missing = m.get("reasoning_tokens_known"), m.get("reasoning_unreported_calls", 0)
    if known is None:
        return f"未报告（{missing} 次思考调用没有报告）" if missing else "未报告"
    text = f"合计 {known}，单次最多 {m['reasoning_tokens_max']}"
    if missing:
        text = f"已知小计 {known}（另有 {missing} 次思考调用没有报告，合计不完整），单次最多 {m['reasoning_tokens_max']}"
    return text


def _removed_line(removed: dict) -> str:
    labels = (("criteria", "评分项"), ("argument", "论证结构"), ("priorities", "提升重点"))
    parts = "、".join(f"{label} {removed.get(key, 0)}" for key, label in labels)
    return (
        f"- 建议因含原文、题目和题图都没有的数字被删去（整份评价合计）：{removed.get('total', 0)} 条"
        f"（{parts}）"
    )


def _teacher_markdown(tf: dict | None) -> list[str]:
    if not tf:
        return []
    lines = []
    failed = tf.get("failed_samples") or []
    failed_findings = sum(tf["samples"][k]["total"] for k in failed)
    lines += [
        "",
        "## 与老师批注对照（只看位置是否重合）",
        "",
        f"老师批注共 {tf['total']} 处，来自 {len(tf['samples'])} 篇作文"
        + (
            f"，其中 {len(failed)} 篇评价没有成功，它们的 {failed_findings} 处批注无法对照，"
            "计为未覆盖"
            if failed
            else ""
        )
        + f"。AI 也指出了同一位置的有 {tf['covered']} 处，占全部 {_pct(tf['rate'])}；"
        f"只看评价成功的作文为 {tf['covered']}/{tf.get('evaluated_total', tf['total'])}"
        f"（{_pct(tf.get('rate_evaluated', tf['rate']))}）。",
        f"另有 {tf.get('uncertain', 0)} 处因引文在原文中出现不止一次、位置不确定，未计为覆盖。"
        "“同一位置”指两段引文在原文中的字符区间相交；位置重合不等于判断相同，AI 指出、"
        "老师没批的地方也不一定是误判，要人工看。",
        "",
        "| 样本 | 老师批注 | AI 覆盖 | 不确定 | AI 其他位置 | 没覆盖的老师批注 |",
        "|---|---|---|---|---|---|",
    ]
    for sample_id, c in tf["samples"].items():
        if not c.get("evaluated", True):
            lines.append(
                f"| {sample_id} | {c['total']} | 评价未成功（{c.get('status')}） | — | — | 全部 |"
            )
            continue
        missed = (
            "；".join(
                f"{f['quote'][:30]}（{f.get('note') or '—'}）"
                for f in c["findings"]
                if f.get("coverage", "yes" if f["covered"] else "no") == "no"
            )
            or "—"
        )
        lines.append(
            f"| {sample_id} | {c['total']} | {c['covered']} | {c.get('uncertain', 0)} | "
            f"{c['ai_spans_not_marked_by_teacher']} | {missed} |"
        )
    return lines


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
    for kind, m in report["kinds"].items():
        for item in m.get("json_problems") or []:
            lines.append(
                f"- {names.get(kind, kind)} · {item['sample']} 第 {item['attempt'] + 1} 次：{item['problem']}"
            )
    lines += ["", "## 输出预算与思考模式", ""]
    for kind, m in report["kinds"].items():
        reasoning = _reasoning_text(m)
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
    lines += _teacher_markdown(report.get("teacher_findings"))
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
    lines += _holdout_markdown(report)
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
    basis = report["cost_estimate"].get("basis")
    hits = report["usage"]["text"].get("cache_hit_tokens")
    if basis == "cache_split":
        lines.append(f"输入按缓存命中 {hits} token 与未命中分别计价；思考 token 已含在输出里。")
    elif basis == "input_at_full_price":
        lines.append(
            "全部输入按普通输入单价计算（没有提供缓存命中单价，或服务商没有报告命中量），"
            "有缓存命中时会偏高；思考 token 已含在输出里。"
        )
    served = "、".join(report.get("served_models") or []) or "—"
    code = (report.get("code_sha256") or "")[:16] or "—"
    lines.append(f"服务商返回的模型名：{served}；工具源码指纹：{code}。")
    lines += ["", "原始调用记录见同目录 `raw_calls.jsonl`（含模型原文，仅保存在本机）。"]
    return "\n".join(lines) + "\n"


_SCORE_NAMES = {
    "overall": "总分",
    "task": "TR/TA",
    "coherence": "CC",
    "lexical": "LR",
    "grammar": "GRA",
}


def _holdout_markdown(report: dict) -> list[str]:
    lines = []
    agreement = report.get("rater_agreement")
    if agreement:
        lines += [
            "",
            "## 与多位评委对比",
            "",
            "参照线是评委之间的差距：AI 与评委均值的差距不大于它，就和“再多一位评委”差不多。"
            "两者都只算 AI 已出分的作文；没出分的作文单列，它们的评委差距另列在最后一栏，不进比较。"
            "“区间内”指 AI 的分数落在评委最低分 − 0.5 到最高分 + 0.5 之间。",
            "",
            "| 项目 | 计划篇数 | 已出分 | 未出分 | 评委之间平均差（已出分） | AI 与评委均值平均差 "
            "| AI 偏差（AI − 均值） | 区间内 | 评委之间平均差（全部计划） |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for key, m in agreement.items():
            bias = "—" if m["ai_bias"] is None else f"{m['ai_bias']:+}"
            gap = "—" if m["ai_gap"] is None else m["ai_gap"]
            rater = "—" if m["rater_gap"] is None else m["rater_gap"]
            lines.append(
                f"| {_SCORE_NAMES[key]} | {m['essays']} | {m['scored']} | {m['failed']} | {rater} "
                f"| {gap} | {bias} | {_pct(m['within_range'])} | {m['rater_gap_all']} |"
            )
    ordering = report.get("ordering")
    if ordering:
        lines += [
            "",
            "## 排序检查（同题、不同目标档位的作文）",
            "",
            "标称档位不是认证分数，只看顺序：标称更高的作文，AI 总分不应更低。"
            "“最高档 − 最低档”取计划里的最高、最低标称档；任一端没出分时为“—”，不用中间档代替。",
            "",
            "| 组 | 标称档位 → AI 总分 | 可比较的对数 | 逆序 | 同分 | 最高档 − 最低档 | 未出分 |",
            "|---|---|---|---|---|---|---|",
        ]
        for name, m in ordering.items():
            chain = "；".join(
                f"{r['nominal']:g} → {'—' if r['ai'] is None else format(r['ai'], 'g')}"
                for r in m["rows"]
            )
            spread = "—" if m["spread"] is None else f"{m['spread']:+}"
            lines.append(
                f"| {name} | {chain} | {m['pairs']} | {m['inversions']} | {m['ties']} | {spread} | "
                f"{m['missing']} |"
            )
    spread = report.get("repeat_spread")
    if spread:
        lines += [
            "",
            "## 重复运行波动",
            "",
            f"同一篇作文多次运行的总分差：平均 {spread['overall_spread_mean']}，最大 "
            f"{spread['overall_spread_max']}；有 {spread['any_failed']} 篇至少一次没有出分。"
            "上面与老师、评委的对比把每次运行各算一次。",
            "",
            "| 样本 | 次数 | 出分次数 | 各次总分 | 各项最大差 |",
            "|---|---|---|---|---|",
        ]
        for row in spread["samples"]:
            parts = "；".join(f"{_SCORE_NAMES[k]} {v:g}" for k, v in row["spread"].items()) or "—"
            overall = " / ".join(f"{v:g}" for v in row["overall"]) or "—"
            lines.append(f"| {row['id']} | {row['runs']} | {row['ready']} | {overall} | {parts} |")
    return lines


def write_report(run_data: dict, report: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    if run_data.get("image_outcomes"):
        # Chart readings (and failures) of this run, for --image-descriptions later.
        (out_dir / "image_descriptions.json").write_text(
            json.dumps(image_file(run_data["image_outcomes"]), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
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
