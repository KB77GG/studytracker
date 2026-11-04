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

from . import access, review
from . import essay as essay_lib
from . import samples as builtin_samples
from .llm import LLMError, build_client, parse_strict_json
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
            "json_mode": bool(kwargs.get("json_mode")),
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
            review.normalize_evaluation(raw, submission)
        elif kind == "refine":
            review.normalize_refinement(raw, essay_lib.split_sentences(submission["essay_text"]))
        elif kind == "rewrite":
            rewrite = review.normalize_rewrite(raw, submission)
            if not rewrite["quality_passed"]:
                # Usable but triggers the quality retry: report it as a first-attempt miss.
                return "质量检查：" + "；".join(
                    sorted({i["code"] for i in rewrite["quality_issues"]})
                )
    except review.InvalidOutput as exc:
        return str(exc)
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
    return {
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
    quotes = verified = criteria = 0
    for sample in run_data["samples"]:
        result = (sample["generations"].get("evaluate") or {}).get("result") or {}
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
    }


def _refine_rewrite_metrics(run_data: dict) -> dict:
    sentences = missing = changed = 0
    requested = generated = meeting = quality_ok = retry_failed = 0
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
    return {"checks": checks, "passed": sum(1 for c in checks if c["ok"]), "total": len(checks)}


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
        "demo": run_data["settings"]["llm_provider"] == "fake",
        "samples": len(run_data["samples"]),
        "calls": len(run_data["calls"]),
        "max_calls": run_data["max_calls"],
        "aborted": run_data["aborted"],
        "connectivity": _connectivity(first_call),
        "kinds": kinds,
        "vision_calls": len(vision_calls),
        "evidence": _evidence_metrics(run_data),
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


def render_markdown(report: dict) -> str:
    lines = [
        "# 写作 AI 真实模型小样本验证",
        "",
        f"- 时间：{report['started_at']}",
        f"- 模型：{report['provider']} / {report['model']} · 提示词 {report['prompt_version']}",
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
    ev, rr = report["evidence"], report["refine_rewrite"]
    lines += [
        "",
        "## 证据与内容",
        "",
        f"- 评分项 {ev['scored_criteria']} 个，引文 {ev['quotes']} 条，能在原文中找到 "
        f"{_pct(ev['quotes_verified'])}",
        f"- 精修：共 {rr['refine_sentences']} 句，缺句率 {_pct(rr['refine_missing_rate'])}，"
        f"改动率 {_pct(rr['refine_changed_rate'])}",
        f"- 改写：请求 {rr['rewrite_requested']} 篇，生成 {rr['rewrite_generated']} 篇，"
        f"通过质量检查 {rr['rewrite_quality_passed_count']} 篇；"
        f"**占全部请求 {_pct(rr['rewrite_quality_passed_of_requested'])}**（验收口径，"
        f"生成失败计为未通过），占已生成 {_pct(rr['rewrite_quality_passed_of_generated'])}；"
        f"达到字数下限占全部请求 {_pct(rr['rewrite_meets_min_words_of_requested'])}"
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
        "",
        "## 分数合理性（宽松区间，不是真实分数）",
        "",
        f"通过 {report['sanity']['passed']} / {report['sanity']['total']}",
        "",
    ]
    for check in report["sanity"]["checks"]:
        mark = "✓" if check["ok"] else "✗"
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
        "| 样本 | 总分 | TR/TA | CC | LR | GRA | 状态 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["per_sample"]:
        s = row["scores"]
        status = " ".join(f"{k}:{v}" for k, v in row["statuses"].items())
        lines.append(
            f"| {row['id']} | {s.get('overall') or '—'} | {s.get('task') or '—'} | "
            f"{s.get('coherence') or '—'} | {s.get('lexical') or '—'} | {s.get('grammar') or '—'} "
            f"| {status} |"
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
    with (out_dir / "raw_calls.jsonl").open("w", encoding="utf-8") as handle:
        for call in run_data["calls"]:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")
    return out_dir / "report.md"
