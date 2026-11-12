#!/usr/bin/env python3
"""Read-only, allowlisted numeric audit of the authorized 2026-11-12 main batch.

No project imports, subprocesses, network, configuration, datasets, raw calls,
run_data, compare files, blind sheets or blind keys. Only named authorization,
launcher-exit, ledger, report.json and summary.json files may be read. IDs are
used privately to join rows; no source IDs or free text are exported.

Use the main-tree .venv/bin/python; --public-out must be a new directory under
the main tree's docs/design or tmp. Output is provisional unless --final is
given AND completion/integrity checks pass. No model recommendation is made:
judgment-error decisions require the separate blinded review.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MAIN = Path("/Users/zhouxin/Desktop/studytracker")
PRIVATE = Path("/Users/zhouxin/iwa-compare-real-20261112")
HEAD = "c0d87c911b7d9000f6fc16c2c49a00edbe5738a1"
GROUPS = {"dev": 14, "teacher": 2, "rated_t2": 8, "ordering": 10, "lowband": 12}
MODELS = {"flash": "deepseek-flash", "pro": "deepseek-v4-pro"}
SCORES = ("overall", "task", "coherence", "lexical", "grammar")
TOKENS = ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens")
METRICS = (
    "calls",
    "first_attempts",
    "first_attempt_json_ok",
    "first_attempt_valid",
    "final_ready",
    "latency_ms_p50",
    "latency_ms_p90",
    "completion_tokens_max",
    "reasoning_tokens",
    "reasoning_tokens_known",
    "reasoning_tokens_max",
    "reasoning_unreported_calls",
    "truncated",
    "timeouts",
)
RATER = (
    "essays",
    "scored",
    "failed",
    "rater_gap_all",
    "rater_gap",
    "ai_gap",
    "ai_bias",
    "within_range",
)
SHANGHAI = ZoneInfo("Asia/Shanghai")


class AuditError(Exception):
    pass


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def count(value):
    return value if type(value) is int and value >= 0 else None


def numeric_map(data, fields):
    data = data if isinstance(data, dict) else {}
    return {key: number(data.get(key)) for key in fields}


def mean(values):
    return round(statistics.fmean(values), 6) if values else None


def rate(n, d):
    return round(n / d, 6) if d else None


def percentile(values, q):
    return sorted(values)[max(0, math.ceil(q * len(values)) - 1)] if values else None


def read_json(root, relative, optional=False):
    """Only explicit metadata/report names are accepted; resolve rejects symlinks."""
    allowed = {"authorization.json", "launcher_exit.json", "summary.json"}
    allowed.update(f"{g}-{m}/report.json" for g in GROUPS for m in MODELS)
    if relative not in allowed:
        raise AuditError("read_not_allowlisted")
    path = root / relative
    if path.is_symlink() or path.resolve().parent != path.absolute().parent:
        raise AuditError("source_symlink_refused")
    if optional and not path.exists():
        return None
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise AuditError("metadata_unreadable_or_incomplete") from None
    if not isinstance(obj, dict):
        raise AuditError("metadata_shape_invalid")
    return obj


def read_ledger(root):
    path = root / "ledger-main.jsonl"
    if path.is_symlink():
        raise AuditError("source_symlink_refused")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        raise AuditError("ledger_unreadable") from None
    rows, torn = [], 0
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            if index == len(lines) - 1:
                torn = 1
                continue
            raise AuditError("ledger_corrupt") from None
        if not isinstance(obj, dict):
            raise AuditError("ledger_shape_invalid")
        rows.append(obj)
    return rows, torn, text


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(SHANGHAI) if parsed.tzinfo else None
    except ValueError:
        return None


def peak(at):
    # User-specified weekday schedule, not a statutory-holiday calendar.
    return at.weekday() < 5 and (9 <= at.hour < 12 or 14 <= at.hour < 18)


def time_band(start, end):
    if start is None or end is None or end < start:
        return "time_unknown", 0.5, 1.0
    boundaries = []
    day = start.date()
    while day <= end.date():
        if day.weekday() < 5:
            for hour in (9, 12, 14, 18):
                boundary = datetime.combine(day, time(hour), SHANGHAI)
                if start < boundary <= end:
                    boundaries.append(boundary)
        day += timedelta(days=1)
    if boundaries:
        return "cross_boundary", 0.5, 1.0
    return ("peak", 1.0, 1.0) if peak(start) else ("off_peak", 0.5, 0.5)


def validate_auth(auth):
    expected = {
        "authorized_stage": "main",
        "authorized_text_request_cap": 184,
        "authorized_vision_requests": 0,
        "only_kind": "evaluate",
        "thinking": "high",
        "max_output_tokens_per_request": 32000,
        "timeout_seconds": 300,
        "source_head": HEAD,
    }
    if any(auth.get(k) != v for k, v in expected.items()):
        raise AuditError("authorization_scope_mismatch")
    if set(auth.get("models") or []) != set(MODELS.values()):
        raise AuditError("authorization_models_mismatch")
    prices = auth.get("peak_CNY_per_million") or {}
    off = auth.get("off_peak_CNY_per_million") or {}
    for model in MODELS:
        p, o = prices.get(model), off.get(model)
        if not isinstance(p, list) or not isinstance(o, list) or len(p) != 3 or len(o) != 3:
            raise AuditError("authorization_prices_invalid")
        if any(number(v) is None or v < 0 for v in p + o):
            raise AuditError("authorization_prices_invalid")
        if any(abs(p[i] / 2 - o[i]) > 1e-9 for i in range(3)):
            raise AuditError("authorization_half_price_mismatch")
    return prices


def index_ledger(rows):
    reserved, done, problems = {}, {}, Counter()
    fingerprints = set()
    for row in rows:
        typ = row.get("type")
        if typ == "header":
            fingerprints.add(row.get("code_sha256"))
            continue
        if typ not in ("reserve", "done") or not isinstance(row.get("id"), str):
            problems["unexpected_ledger_entry"] += 1
            continue
        target = reserved if typ == "reserve" else done
        if row["id"] in target:
            problems[f"duplicate_{typ}"] += 1
        target[row["id"]] = row
    problems["done_without_reservation"] = len(set(done) - set(reserved))
    runs = defaultdict(list)
    allowed_runs = {f"{g}-{m}" for g in GROUPS for m in MODELS}
    for rid, reserve in reserved.items():
        name = reserve.get("run")
        if name not in allowed_runs:
            problems["unexpected_run"] += 1
            continue
        model = name.rsplit("-", 1)[1]
        if reserve.get("kind") != "evaluate" or reserve.get("category") != "text":
            problems["unexpected_request_kind"] += 1
        if reserve.get("model") != MODELS[model] or reserve.get("cap") != 184:
            problems["request_authorization_mismatch"] += 1
        if count(reserve.get("attempt")) not in (0, 1):
            problems["unexpected_attempt"] += 1
        runs[name].append((reserve, done.get(rid)))
    return runs, problems, fingerprints, len(reserved)


def request_stats(rows, price):
    totals = dict.fromkeys(TOKENS, 0)
    missing = dict.fromkeys(TOKENS, 0)
    events, bands, latency, cost_bounds = Counter(), Counter(), [], [0.0, 0.0]
    peak_upper = 0.0
    first_ids, retry_ids = set(), set()
    for reserve, done in rows:
        attempt = count(reserve.get("attempt"))
        events["first_requests" if attempt == 0 else "retry_requests"] += 1
        (first_ids if attempt == 0 else retry_ids).add(reserve.get("sample"))
        events[
            (
                "outcome_unknown"
                if done is None
                else "request_ok" if done.get("ok") is True else "request_failed"
            )
        ] += 1
        start = timestamp(reserve.get("time"))
        end = timestamp((done or {}).get("time"))
        band, multiplier_low, multiplier_high = time_band(start, end)
        bands[band] += 1
        if start and end and end >= start:
            latency.append(round((end - start).total_seconds() * 1000))
        tokens = (done or {}).get("tokens") or {}
        p, c, h = [count(tokens.get(k)) for k in TOKENS]
        for key, value in zip(TOKENS, (p, c, h), strict=True):
            missing[key] += value is None
            totals[key] += value or 0
        events["usage_unknown_requests"] += p is None or c is None
        events["cache_unknown_requests"] += p is not None and h is None
        if p is not None and h is not None and h > p:
            raise AuditError("cache_tokens_exceed_prompt")
        input_low = (
            (p or 0) * price[1] if h is None else max((p or 0) - h, 0) * price[0] + h * price[1]
        )
        input_high = (p or 0) * price[0] if h is None else input_low
        low, high = input_low + (c or 0) * price[2], input_high + (c or 0) * price[2]
        cost_bounds[0] += low * multiplier_low / 1e6
        cost_bounds[1] += high * multiplier_high / 1e6
        peak_upper += high / 1e6
    unknown = events["usage_unknown_requests"]
    out = {
        "actual_reserved_requests": len(rows),
        **{
            k: events[k]
            for k in (
                "first_requests",
                "retry_requests",
                "request_ok",
                "request_failed",
                "outcome_unknown",
                "usage_unknown_requests",
                "cache_unknown_requests",
            )
        },
        "evaluations_with_retry": len(retry_ids),
        "distinct_first_evaluations": len(first_ids),
        "tokens_known_subtotal": totals,
        "tokens_complete_total": {k: totals[k] if missing[k] == 0 else None for k in TOKENS},
        "tokens_unreported_requests": missing,
        "completion_tokens_max_known": max(
            (
                count((d or {}).get("tokens", {}).get("completion_tokens"))
                for _, d in rows
                if count((d or {}).get("tokens", {}).get("completion_tokens")) is not None
            ),
            default=None,
        ),
        "completed_request_wall_ms_p50": percentile(latency, 0.5),
        "completed_request_wall_ms_p90": percentile(latency, 0.9),
        "completed_request_wall_ms_max": max(latency) if latency else None,
        "time_bands": {k: bands[k] for k in ("peak", "off_peak", "cross_boundary", "time_unknown")},
        "cost_cny": {
            "known_usage_lower": round(cost_bounds[0], 8),
            "known_usage_upper": round(cost_bounds[1], 8),
            "total_lower_bound": round(cost_bounds[0], 8),
            "total_upper_bound": round(cost_bounds[1], 8) if not unknown else None,
            "all_usage_known": not bool(unknown),
            "fixed_peak_known_usage_upper_estimate": round(peak_upper, 8),
            "is_provider_bill": False,
        },
    }
    return out


def recovered_count(value, denominator):
    if number(value) is None or count(denominator) is None:
        return None
    candidates = (
        [n for n in range(denominator + 1) if round(n / denominator, 3) == value]
        if denominator
        else []
    )
    return candidates[0] if len(candidates) == 1 else None


def project_report(report):
    if report is None:
        return None, {}
    ev = (report.get("kinds") or {}).get("evaluate") or {}
    samples = {}
    for row in report.get("per_sample") or []:
        sid = row.get("id")
        if not isinstance(sid, str) or sid in samples:
            raise AuditError("report_sample_identity_invalid")
        samples[sid] = {
            "scores": numeric_map(row.get("scores"), SCORES),
            "teacher": numeric_map(row.get("teacher"), SCORES),
            "ready": (row.get("statuses") or {}).get("evaluate") == "ready",
            "attempted": "evaluate" in (row.get("statuses") or {}),
        }
    spread = report.get("repeat_spread") or {}
    repeated = spread.get("samples") or []
    repeat = numeric_map(spread, ("overall_spread_mean", "overall_spread_max", "any_failed"))
    repeat["unique_essays"] = len(repeated)
    repeat["paired_successful_essays"] = sum(
        count(r.get("ready")) == count(r.get("runs")) and (count(r.get("ready")) or 0) >= 2
        for r in repeated
    )
    repeat["issue_overlap"] = None
    repeat["criteria"] = {}
    for key in SCORES:
        values = [number((r.get("spread") or {}).get(key)) for r in repeated]
        values = [v for v in values if v is not None]
        repeat["criteria"][key] = {
            "paired": len(values),
            "mean_abs_difference": mean(values),
            "max_abs_difference": max(values) if values else None,
        }
    ordering = []
    for order in (report.get("ordering") or {}).values():
        item = numeric_map(
            order, ("missing", "pairs", "inversions", "ties", "highest", "lowest", "spread")
        )
        item["chain"] = [numeric_map(row, ("nominal", "ai")) for row in order.get("rows") or []]
        item["complete"] = item["missing"] == 0
        item["monotonic_nonincreasing"] = item["inversions"] == 0 if item["complete"] else None
        item["highest_above_lowest"] = item["spread"] > 0 if item["spread"] is not None else None
        ordering.append(item)
    projected = {
        "report_present": True,
        "planned_evaluations": count(report.get("samples")),
        **numeric_map(ev, METRICS),
        "success_evaluations": sum(row["ready"] for row in samples.values()),
        "failed_evaluations": sum(
            row["attempted"] and not row["ready"] for row in samples.values()
        ),
        "unattempted_evaluations": sum(not row["attempted"] for row in samples.values()),
        "first_json_success_count": recovered_count(
            ev.get("first_attempt_json_ok"), count(ev.get("first_attempts"))
        ),
        "first_validation_success_count": recovered_count(
            ev.get("first_attempt_valid"), count(ev.get("first_attempts"))
        ),
        "repeat_variation": repeat,
        "ordering": ordering,
        "single_run_rater_agreement": {
            key: numeric_map(value, RATER)
            for key, value in (report.get("rater_agreement") or {}).items()
            if key in SCORES
        },
    }
    return projected, samples


def reconcile(report, projected, rows, requests, planned, summary_run, fingerprint):
    checks = {}
    if report is None:
        return {"report_present": False}
    checks["report_calls_match_ledger"] = count(report.get("calls")) == len(rows)
    checks["report_samples_match_ledger"] = {
        row.get("id") for row in report.get("per_sample") or []
    } == {reserve.get("sample") for reserve, _ in rows if reserve.get("attempt") == 0}
    checks["report_model_matches_ledger"] = bool(rows) and all(
        reserve.get("model") == report.get("model") for reserve, _ in rows
    )
    checks["report_planned_evaluations_match"] = projected["planned_evaluations"] == planned
    checks["report_first_requests_match_ledger"] = (
        projected["first_attempts"] == requests["first_requests"]
    )
    checks["report_evaluate_calls_match_ledger"] = projected["calls"] == len(rows)
    checks["report_source_matches_ledger"] = (
        report.get("code_sha256") in fingerprint and len(fingerprint) == 1
    )
    checks["no_unknown_request_outcome"] = requests["outcome_unknown"] == 0
    checks["all_evaluations_attempted"] = projected["unattempted_evaluations"] == 0
    checks["first_rate_counts_recoverable"] = (
        projected["first_json_success_count"] is not None
        and projected["first_validation_success_count"] is not None
    )
    checks["final_success_rate_matches"] = (
        recovered_count(
            projected["final_ready"],
            projected["success_evaluations"] + projected["failed_evaluations"],
        )
        == projected["success_evaluations"]
    )
    reported_usage = (report.get("usage") or {}).get("text") or {}
    known = reported_usage.get("known_tokens") or {}
    for report_key, ledger_key in (
        ("prompt", "prompt_tokens"),
        ("completion", "completion_tokens"),
    ):
        checks[f"{report_key}_tokens_match"] = (
            count(known.get(report_key)) == requests["tokens_known_subtotal"][ledger_key]
        )
    checks["cache_tokens_match"] = (
        count(reported_usage.get("cache_hit_tokens"))
        == requests["tokens_complete_total"]["prompt_cache_hit_tokens"]
    )
    if summary_run is not None:
        attempts = summary_run.get("attempts") or {}
        checks["summary_requests_match_ledger"] = count(attempts.get("requests")) == len(rows)
        summary_cost = number(attempts.get("estimated_cost"))
        requests["cost_cny"]["private_summary_fixed_peak_estimate"] = summary_cost
        requests["cost_cny"]["private_summary_marked_incomplete"] = (
            attempts.get("cost_is_lower_bound") is True
        )
        if requests["usage_unknown_requests"] == 0:
            checks["summary_fixed_peak_cost_matches"] = (
                summary_cost is not None
                and abs(
                    summary_cost - requests["cost_cny"]["fixed_peak_known_usage_upper_estimate"]
                )
                <= 0.000001
            )
        else:
            checks["summary_marks_unknown_cost_incomplete"] = (
                attempts.get("cost_is_lower_bound") is True
            )
        sf = summary_run.get("final") or {}
        checks["summary_quality_matches_report"] = all(
            number(sf.get(k)) == projected.get(k)
            for k in (
                "first_attempt_json_ok",
                "first_attempt_valid",
                "final_ready",
                "completion_tokens_max",
            )
        )
    else:
        checks["summary_run_present"] = False
    return checks


def common_scoring(a, b):
    """Per-criterion successful common subset; teacher refs must agree across models."""
    result = {}
    for criterion in SCORES:
        rows = []
        for sid in set(a) & set(b):
            ar, br = a[sid], b[sid]
            reference = ar["teacher"][criterion]
            if reference != br["teacher"][criterion]:
                raise AuditError("common_teacher_reference_mismatch")
            if reference is not None and ar["ready"] and br["ready"]:
                av, bv = ar["scores"][criterion], br["scores"][criterion]
                if av is not None and bv is not None:
                    rows.append((av, bv, reference))
        if not rows:
            continue
        metrics = {"common_successful_evaluations": len(rows)}
        for index, model in enumerate(MODELS):
            differences = [row[index] - row[2] for row in rows]
            metrics[model] = {
                "mae": mean([abs(d) for d in differences]),
                "bias": mean(differences),
                "within_0_5": rate(sum(abs(d) <= 0.5 for d in differences), len(rows)),
            }
        metrics["pro_mae_not_worse"] = metrics["pro"]["mae"] <= metrics["flash"]["mae"]
        result[criterion] = metrics
    return result


def project_common_raters(summary_group):
    value = (summary_group or {}).get("common_rater_agreement")
    if not isinstance(value, dict):
        return None
    # batch._compare always supplies flash as side a and pro as side b.
    out = {"common_successful_evaluations": count(value.get("essays"))}
    for side, model in (("a", "flash"), ("b", "pro")):
        out[model] = {
            k: numeric_map(v, RATER) for k, v in (value.get(side) or {}).items() if k in SCORES
        }
    out["descriptive_comparisons"] = {}
    for key in SCORES:
        a, b = out["flash"].get(key) or {}, out["pro"].get(key) or {}
        ag, bg = a.get("ai_gap"), b.get("ai_gap")
        if ag is None or bg is None:
            continue
        out["descriptive_comparisons"][key] = {
            "pro_ai_gap_not_worse": bg <= ag,
            "flash_gap_exceeds_rater_gap": (
                ag > a["rater_gap"] if a.get("rater_gap") is not None else None
            ),
            "pro_gap_exceeds_rater_gap": (
                bg > b["rater_gap"] if b.get("rater_gap") is not None else None
            ),
            "same_scored_denominator": a.get("scored") == b.get("scored"),
        }
    return out


def audit(root, final_requested=False):
    root = root.resolve()
    auth = read_json(root, "authorization.json")
    prices = validate_auth(auth)
    exit_meta = read_json(root, "launcher_exit.json", optional=True)
    summary = read_json(root, "summary.json", optional=True)
    ledger, torn, before = read_ledger(root)
    runs, problems, fingerprints, reserved_total = index_ledger(ledger)
    groups = {}
    for group, planned in GROUPS.items():
        item, sample_sets = {"models": {}}, {}
        summary_group = ((summary or {}).get("groups") or {}).get(group) or {}
        for model in MODELS:
            name = f"{group}-{model}"
            report = read_json(root, f"{name}/report.json", optional=True)
            projected, sample_sets[model] = project_report(report)
            req = request_stats(runs[name], prices[model])
            sr = (summary_group.get("runs") or {}).get(model)
            checks = reconcile(report, projected, runs[name], req, planned, sr, fingerprints)
            item["models"][model] = {
                "planned_evaluations": planned,
                "requests": req,
                "evaluation": projected,
                "reconciliation": checks,
            }
        item["common_teacher_scores"] = (
            common_scoring(sample_sets["flash"], sample_sets["pro"])
            if group in ("teacher", "rated_t2")
            else None
        )
        item["common_dual_raters_from_summary"] = project_common_raters(summary_group)
        groups[group] = item
    _, _, after = read_ledger(root)
    finished = exit_meta is not None and exit_meta.get("code") == 0
    reconcile_ok = all(
        all(m["reconciliation"].values()) for g in groups.values() for m in g["models"].values()
    )
    integrity = {
        "ledger_snapshot_stable": before == after,
        "torn_final_line": torn,
        "ledger_problem_counts": dict(problems),
        "cap_not_exceeded": reserved_total <= 184,
        "summary_present": summary is not None,
        "launcher_finished_successfully": finished,
        "all_reports_reconcile": reconcile_ok,
    }
    eligible = (
        finished
        and summary is not None
        and before == after
        and not torn
        and not any(problems.values())
        and reserved_total <= 184
        and reconcile_ok
    )
    totals = {}
    for model in MODELS:
        model_runs = [g["models"][model] for g in groups.values()]
        rows = [row for group in GROUPS for row in runs[f"{group}-{model}"]]
        totals[model] = request_stats(rows, prices[model])
        ready_reports = [r["evaluation"] for r in model_runs if r["evaluation"] is not None]
        totals[model]["reported_evaluations"] = sum(
            r["success_evaluations"] + r["failed_evaluations"] for r in ready_reports
        )
        for key in (
            "success_evaluations",
            "failed_evaluations",
            "first_json_success_count",
            "first_validation_success_count",
        ):
            totals[model][key] = sum(r[key] or 0 for r in ready_reports)
        totals[model]["report_count"] = len(ready_reports)
        for field in ("reasoning_tokens", "reasoning_tokens_known", "reasoning_unreported_calls"):
            values = [r.get(field) for r in ready_reports]
            totals[model][field + "_reported_runs"] = (
                sum(values) if values and all(v is not None for v in values) else None
            )
        totals[model]["reasoning_tokens_max_known"] = max(
            (
                r["reasoning_tokens_max"]
                for r in ready_reports
                if r["reasoning_tokens_max"] is not None
            ),
            default=None,
        )
        totals[model]["failure_rate_among_reported_evaluations"] = rate(
            totals[model]["failed_evaluations"], totals[model]["reported_evaluations"]
        )
    final = bool(final_requested and eligible)
    numeric_rules = {
        "enabled_after_complete_audit": final,
        "pro_final_failures_at_most_half_flash": (
            totals["pro"]["failed_evaluations"] <= totals["flash"]["failed_evaluations"] / 2
            if final
            else None
        ),
        "any_model_final_failure_rate_above_10_percent": (
            any((totals[m]["failure_rate_among_reported_evaluations"] or 0) > 0.1 for m in MODELS)
            if final
            else None
        ),
        "judgment_error_reduction_at_least_30_percent": None,
        "type_1_2_errors_more_than_one_per_essay": None,
        "recommend_switch_to_pro": None,
    }
    return {
        "schema_version": 1,
        "provisional": not final,
        "authorized_text_request_cap": 184,
        "planned_evaluations_per_model": sum(GROUPS.values()),
        "actual_reserved_requests": reserved_total,
        "integrity": integrity,
        "totals": totals,
        "groups": groups,
        "numeric_rule_checks": numeric_rules,
        "notes": [
            "Counts include all reserved requests, including retries and unknown outcomes; reservations are not proof the provider received a request.",
            "JSON/validation denominators are first attempts. Final failure rates use attempted evaluations; completion checks require all planned evaluations.",
            "Report p50/p90 covers successful transport calls, including retries; ledger wall times cover every completed request and have one-second timestamp resolution.",
            "Peak is Monday-Friday Beijing 09:00-12:00 and 14:00-18:00; other times are half price. No statutory-holiday calendar is inferred.",
            "Requests spanning a price boundary are separately counted and bounded at half/full price. Unknown usage makes total upper cost null, never zero.",
            "Missing cache usage is bounded using all-hit/all-miss input pricing. Reasoning tokens are included in completion tokens, never added twice.",
            "Private summary.json uses fixed peak rates: a conservative usage estimate, not the provider bill; unknown usage remains unpriced.",
            "Repeated scores are dependent measurements, not additional independent essays. Issue overlap is unavailable from the permitted numeric reports.",
            "Teacher and dual-rater groups are score references; ordering and synthetic lowband nominal levels are not calibrated ground truth.",
            "No acceptance threshold was predeclared for ranking inversions/spread; monotonicity and endpoint separation are descriptive checks.",
            "Common dual-rater metrics are read from summary only; raw raters are intentionally not read. Blind judgment-error rules and recommendation remain pending separate review.",
        ],
    }


def render(data):
    lines = [
        "# 真实比较：脱敏数字审计",
        "",
        "状态："
        + (
            "预备汇总，不作模型结论。"
            if data["provisional"]
            else "批次数字核对完成；判断质量仍需独立盲评。"
        ),
        "",
        "| 组 | 模型 | 请求 | 重试 | 成功评价 | 最终失败 | 首轮 JSON | 首轮校验 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for group, record in data["groups"].items():
        for model, item in record["models"].items():
            req, ev = item["requests"], item["evaluation"] or {}
            values = [
                req["actual_reserved_requests"],
                req["retry_requests"],
                ev.get("success_evaluations"),
                ev.get("failed_evaluations"),
                ev.get("first_json_success_count"),
                ev.get("first_validation_success_count"),
            ]
            lines.append(
                f"| {group} | {model} | "
                + " | ".join("—" if v is None else str(v) for v in values)
                + " |"
            )
    lines += [
        "",
        "完整延迟、token、费用区间、重复波动、共同评分子集、排序与账本核对见同目录 numeric_summary.json。",
        "",
        "",
    ]
    for model, item in data["totals"].items():
        cost = item["cost_cny"]
        upper = (
            "未知（缺用量）"
            if cost["total_upper_bound"] is None
            else str(cost["total_upper_bound"])
        )
        lines.append(
            f"- {model}：请求 {item['actual_reserved_requests']}；已知用量估算 {cost['known_usage_lower']}–{cost['known_usage_upper']} 元；全部请求费用上界 {upper}。非服务商账单。"
        )
    lines += ["", "## 口径与限制", ""]
    lines.extend(f"- {note}" for note in data["notes"])
    return "\n".join(lines) + "\n"


def output_directory(value):
    path = Path(value).expanduser().absolute()
    resolved = path.resolve()
    allowed = (MAIN / "tmp", MAIN / "docs/design")
    if not any(resolved.is_relative_to(parent) for parent in allowed) or path != resolved:
        raise AuditError("public_output_location_refused")
    if path.exists():
        raise AuditError("public_output_must_be_new_directory")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, default=PRIVATE)
    parser.add_argument("--public-out", required=True)
    parser.add_argument(
        "--final",
        action="store_true",
        help="enable numeric rule checks only if complete and reconciled",
    )
    args = parser.parse_args()
    try:
        out = output_directory(args.public_out)
        data = audit(args.private_root, final_requested=args.final)
        encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        out.mkdir(parents=True, exist_ok=False)
        (out / "numeric_summary.json").write_text(encoded, encoding="utf-8")
        (out / "numeric_summary.md").write_text(render(data), encoding="utf-8")
        print(
            json.dumps(
                {
                    "provisional": data["provisional"],
                    "actual_reserved_requests": data["actual_reserved_requests"],
                    "all_reports_reconcile": data["integrity"]["all_reports_reconcile"],
                    "files_written": 2,
                }
            )
        )
        return 2 if args.final and data["provisional"] else 0
    except AuditError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except Exception:
        # Never let private source objects, arbitrary error text or paths leak.
        print('{"error":"numeric_audit_failed_without_private_diagnostics"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
