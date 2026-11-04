#!/usr/bin/env python3
"""Independent offline audit of the sanitized thinking A/B result bundle.

Usage: python real_metrics_audit.py --bundle /shared/bundle --output audit.json
Optional --transport overrides bundle/transport.json. Partial bundles are supported;
smoke is always separate from the off/high comparison. No credentials or network.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(text):
    text = (text or "").translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-"}))
    return re.sub(r"\s+", " ", text).strip().lower()


def found(essay, quote):
    needle = norm(quote).strip(" .,;:!?\"'")
    return bool(needle) and needle in norm(essay)


def strict_json(text):
    value = (text or "").strip()
    fence = re.fullmatch(r"```(?:json|JSON)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```", value, re.S)
    if fence:
        value = fence.group(1).strip()
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, TypeError):
        return None


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def pct(n, d):
    return round(n / d, 3) if d else None


def percentile(values, quantile):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def usage_summary(calls):
    fields = ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
    known = {k: sum(c.get("usage", {}).get(k, 0) for c in calls if integer(c.get("usage", {}).get(k))) for k in fields}
    missing = {k: sum(not integer(c.get("usage", {}).get(k)) for c in calls) for k in fields}
    reasoning_values = [c.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens") for c in calls]
    reasoning_known = sum(v for v in reasoning_values if integer(v)) if any(integer(v) for v in reasoning_values) else None
    reasoning_unknown = sum((c.get("thinking") or "off") != "off" and not integer(v) for c, v in zip(calls, reasoning_values))
    complete_reasoning = reasoning_known if not reasoning_unknown else None
    cost_fields = ("prompt_cache_hit_tokens", "prompt_cache_miss_tokens", "completion_tokens")
    low = None
    if not any(missing[k] for k in cost_fields):
        low = (known[cost_fields[0]] * 0.003 + known[cost_fields[1]] * 0.15 + known[cost_fields[2]] * 0.6) / 1_000_000
    def failed(call):
        # The transport ledger says status='received', whereas run_data has ok.
        # Missing ok is not failure. Content/transport failure markers are explicit.
        return ("ok" in call and not call["ok"]) or bool(call.get("error")) or (call.get("http_status") or 0) >= 400 or call.get("finish_reason") == "length"
    failed_reasoning = [v for c, v in zip(calls, reasoning_values) if failed(c) and integer(v)]
    return {
        "calls": len(calls), "tokens": {k: known[k] if not missing[k] else None for k in fields},
        "known_subtotals": known, "unreported_calls": missing,
        "reasoning_tokens": complete_reasoning, "reasoning_known": reasoning_known,
        "reasoning_unreported_thinking_calls": reasoning_unknown,
        "failed_reasoning_known": sum(failed_reasoning),
        "estimated_usd_range": [round(low, 8), round(low * 2, 8)] if low is not None else None,
    }


def audit_stage(directory, stage, checks):
    data, report = read(directory / "run_data.json"), read(directory / "report.json")
    calls = data["calls"]
    assert all(not c.get("reasoning") for c in calls), "Only sanitized shared data may be audited"
    raw = [json.loads(line) for line in (directory / "raw_calls.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(not c.get("reasoning") for c in raw), "Raw shared calls must have reasoning prose removed"
    checks[f"{stage}.raw_calls_match_run_data"] = raw == calls
    checks[f"{stage}.evaluate_only"] = data["kinds"] == ["evaluate"] and all(c["kind"] == "evaluate" for c in calls)
    budget = 2 if stage in {"smoke", "smoke_high"} else 14
    checks[f"{stage}.within_stage_budget"] = len(calls) <= budget
    usage = usage_summary(calls)
    checks[f"{stage}.cache_components_equal_input"] = all((c.get("usage", {}).get("prompt_cache_hit_tokens", 0) + c.get("usage", {}).get("prompt_cache_miss_tokens", 0)) == c.get("usage", {}).get("prompt_tokens") for c in calls)
    checks[f"{stage}.token_components_equal_total"] = all((c.get("usage", {}).get("prompt_tokens", 0) + c.get("usage", {}).get("completion_tokens", 0)) == c.get("usage", {}).get("total_tokens") for c in calls)
    checks[f"{stage}.reasoning_subset_of_completion"] = all(0 <= c.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens", 0) <= c.get("usage", {}).get("completion_tokens", 0) for c in calls)
    report_kind = report["kinds"]["evaluate"]
    for raw_name, report_name in (("prompt_tokens", "prompt"), ("completion_tokens", "completion")):
        checks[f"{stage}.{raw_name}_total"] = usage["tokens"][raw_name] == report["usage"]["total"]["tokens"][report_name]
    for key, computed in (("calls", len(calls)), ("reasoning_tokens", usage["reasoning_tokens"]), ("reasoning_tokens_known", usage["reasoning_known"]), ("reasoning_unreported_calls", usage["reasoning_unreported_thinking_calls"])):
        checks[f"{stage}.report_{key}"] = report_kind[key] == computed

    by_sample = {s["id"]: s for s in data["samples"]}
    first = [c for c in calls if c["attempt"] == 0]
    ready = {sid for sid, s in by_sample.items() if s["generations"]["evaluate"]["status"] == "ready"}
    retried = {c["sample"] for c in calls if c["attempt"] > 0}
    first_json = sum(c["ok"] and strict_json(c["text"]) is not None for c in first)
    # Evaluation retries only rejected content. A final ready result without a
    # second attempt therefore proves the first output passed the live validator.
    first_valid = sum(c["ok"] and c["sample"] in ready and c["sample"] not in retried for c in first)
    status = {"samples": len(by_sample), "calls": len(calls), "first_json": first_json, "first_valid": first_valid, "final_ready": len(ready), "retried_samples": sorted(retried), "truncated": sum(c.get("error") == "truncated" for c in calls), "timeouts": sum(c.get("error") == "timeout" for c in calls), "http_statuses": dict(Counter(str(c.get("http_status")) for c in calls))}
    for key, value in (("first_attempt_json_ok", pct(first_json, len(first))), ("first_attempt_valid", pct(first_valid, len(first))), ("final_ready", pct(len(ready), len(by_sample))), ("truncated", status["truncated"]), ("timeouts", status["timeouts"])):
        checks[f"{stage}.report_{key}"] = report_kind[key] == value
    latency = [c["latency_ms"] for c in calls if c["ok"]]
    peak = max((c.get("usage", {}).get("completion_tokens", 0) for c in calls), default=None)
    latency_stats = {"successful_calls_p50_ms": percentile(latency, .5), "successful_calls_p90_ms": percentile(latency, .9), "all_calls_sum_ms": sum(c["latency_ms"] for c in calls), "completion_peak": peak, "output_budgets": sorted({c["max_tokens"] for c in calls}), "peak_budget_fraction": max((c.get("usage", {}).get("completion_tokens", 0) / c["max_tokens"] for c in calls), default=None)}
    checks[f"{stage}.latency_p50"] = report_kind["latency_ms_p50"] == latency_stats["successful_calls_p50_ms"]
    checks[f"{stage}.latency_p90"] = report_kind["latency_ms_p90"] == latency_stats["successful_calls_p90_ms"]
    checks[f"{stage}.completion_peak"] = report_kind["completion_tokens_max"] == peak
    evidence, argument, removals = Counter(), Counter(), Counter()
    types, verdicts = Counter(), Counter()
    samples_out, final_results = [], {}
    for sid, sample in by_sample.items():
        result = sample["generations"]["evaluate"].get("result") or {}
        final_results[sid] = result
        essay = sample["submission"]["essay_text"]
        for criterion in result.get("criteria") or []:
            if criterion.get("state") != "scored":
                continue
            evidence["scored_criteria"] += 1
            for entry in (criterion.get("strengths") or []) + (criterion.get("issues") or []):
                quote = entry.get("quote")
                if quote:
                    evidence["quotes"] += 1
                    evidence["literal_quotes"] += quote in essay
                    evidence["normalized_quotes"] += found(essay, quote)
        removed = result.get("suggestions_removed") or {}
        checks[f"{stage}.{sid}.removed_sum"] = removed.get("total", 0) == sum(v for k, v in removed.items() if k != "total")
        removals.update({k: v for k, v in removed.items() if k != "total"})
        evidence["count_corrections"] += len(result.get("count_corrections") or [])
        arg = result.get("argument") or {}
        item_out = {"id": sid, "status": sample["generations"]["evaluate"]["status"], "overall": result.get("overall_band"), "suggestions_removed": removed, "consistency_issues": len(result.get("consistency_issues") or []), "comparisons_checked": result.get("comparisons_checked")}
        if arg:
            argument["task2_evaluations"] += 1
            argument["with_argument"] += 1
            argument["with_position"] += bool(arg.get("position"))
            for field in ("paragraphs", "problems", "improvements"):
                argument[field] += len(arg.get(field) or [])
            for field in ("returned", "dropped", "duplicates", "over_limit", "self_conflicts", "suggestions_removed", "reclassified"):
                argument[field] += arg.get(field, 0)
            kept = int(bool(arg.get("position"))) + sum(len(arg.get(k) or []) for k in ("paragraphs", "problems", "improvements"))
            argument["kept"] += kept
            raw_last = next((strict_json(c["text"]) for c in reversed(calls) if c["sample"] == sid and c["ok"]), {}) or {}
            raw_arg = raw_last.get("argument") or {}
            raw_returned = int(raw_arg.get("position") is not None)
            for field in ("paragraphs", "problems", "improvements"):
                entries = raw_arg.get(field)
                raw_returned += len(entries) if isinstance(entries, list) else int(entries is not None)
            checks[f"{stage}.{sid}.returned_from_model"] = raw_returned == arg["returned"]
            checks[f"{stage}.{sid}.entry_partition"] = arg["returned"] == kept + arg["dropped"] + arg["duplicates"] + arg["over_limit"]
            quotes = ([arg["position"]["quote"]] if arg.get("position") else []) + [p["main_point"] for p in arg.get("paragraphs") or []] + [p["quote"] for p in arg.get("problems") or []] + [p["quote"] for p in arg.get("improvements") or []]
            pairs = [p["conflicts_with"] for p in arg.get("problems") or [] if p.get("conflicts_with")]
            supports = [q for p in arg.get("improvements") or [] for q in p.get("support") or []]
            for label, group in (("entry_quotes", quotes), ("paired_quotes", pairs), ("support_quotes", supports)):
                argument[label] += len(group)
                argument[label + "_literal"] += sum(q in essay for q in group)
                argument[label + "_verified"] += sum(found(essay, q) for q in group)
                checks[f"{stage}.{sid}.{label}"] = all(found(essay, q) for q in group)
            types.update(p["type"] for p in arg.get("problems") or [])
            verdicts.update(p["verdict"] for p in arg.get("paragraphs") or [])
            item_out.update({"argument_returned": arg["returned"], "argument_kept": kept, "problem_types": [p["type"] for p in arg.get("problems") or []], "reclassified": arg["reclassified"]})
        for issue in result.get("consistency_issues") or []:
            checks[f"{stage}.{sid}.consistency_evidence"] = found(essay, issue["quote"]) and all(found(essay, q) for q in issue.get("figures") or [])
        samples_out.append(item_out)
    for key in ("scored_criteria", "quotes", "count_corrections"):
        checks[f"{stage}.report_evidence_{key}"] = evidence[key] == report["evidence"][key]
    checks[f"{stage}.report_evidence_verified"] = pct(evidence["normalized_quotes"], evidence["quotes"]) == report["evidence"]["quotes_verified"]
    for key in ("task2_evaluations", "with_argument", "with_position", "paragraphs", "problems", "improvements", "returned", "kept", "dropped", "duplicates", "over_limit", "self_conflicts", "suggestions_removed", "reclassified"):
        checks[f"{stage}.report_argument_{key}"] = argument[key] == report["argument"][key]
    checks[f"{stage}.report_argument_types"] = dict(types) == report["argument"]["problem_types"]
    checks[f"{stage}.report_argument_verdicts"] = dict(verdicts) == report["argument"]["paragraph_verdicts"]
    for key in ("criteria", "priorities", "argument"):
        checks[f"{stage}.report_removed_{key}"] = removals[key] == report["evidence"]["suggestions_removed"].get(key, 0)

    sanity = {}
    def problems(sid):
        return (final_results[sid].get("argument") or {}).get("problems") or []
    if "t2-weak" in final_results:
        sanity["weak_has_problem"] = len(problems("t2-weak")) >= 1
    if "t2-strong" in final_results:
        strong = final_results["t2-strong"].get("argument") or {}
        forbidden = {"off_position", "unclear_position", "inconsistent_position", "conclusion_inconsistent"}
        sanity["strong_at_most_one_problem"] = len(problems("t2-strong")) <= 1
        sanity["strong_no_false_contradiction_or_off_topic"] = not any(p["type"] in forbidden for p in problems("t2-strong")) and not any(p["verdict"] == "off_position" for p in strong.get("paragraphs") or []) and (strong.get("position") or {}).get("consistent") is not False
        sanity["strong_position_quote"] = found(by_sample["t2-strong"]["submission"]["essay_text"], (strong.get("position") or {}).get("quote"))
    if "t2-off-topic" in final_results:
        off = final_results["t2-off-topic"].get("argument") or {}
        sanity["off_topic_identified"] = any(p["type"] in {"off_position", "irrelevant"} for p in off.get("problems") or []) or any(p["verdict"] == "off_position" for p in off.get("paragraphs") or [])
    sanity_labels = {"weak_has_problem": "论证问题 ≥ 1", "strong_at_most_one_problem": "论证问题 ≤ 1", "strong_no_false_contradiction_or_off_topic": "不应出现 off_position", "strong_position_quote": "找到可核实的立场句", "off_topic_identified": "应标出 off_position"}
    for key, value in sanity.items():
        matching = [c for c in report["sanity"]["checks"] if c["check"].startswith(sanity_labels[key])]
        checks[f"{stage}.sanity_{key}"] = len(matching) == 1 and matching[0]["ok"] == value
    checks[f"{stage}.sanity_denominator"] = report["sanity"]["total"] == sum(c["ok"] is not None for c in report["sanity"]["checks"])
    checks[f"{stage}.sanity_pass_count"] = report["sanity"]["passed"] == sum(c["ok"] is True for c in report["sanity"]["checks"])
    return {"source_head": (report.get("audit") or {}).get("source_head"), "status": status, "usage": usage, "latency_and_budget": latency_stats, "evidence": dict(evidence), "argument": {**dict(argument), "problem_types": dict(types), "paragraph_verdicts": dict(verdicts)}, "suggestions_removed": {**dict(removals), "total": sum(removals.values())}, "argument_sanity": {"checks": sanity, "passed": sum(sanity.values()), "total": len(sanity)}, "all_sanity": {k: report["sanity"][k] for k in ("passed", "total", "skipped")}, "samples": samples_out, "first_input_sha256": {c["sample"]: c.get("input_sha256") for c in first}}, calls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--transport", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    def forbid(event, _args):
        if event == "socket.connect":
            raise RuntimeError("Offline audit forbids network connections")
    sys.addaudithook(forbid)
    checks, stages, calls_by_stage = {}, {}, {}
    for stage in ("smoke_high", "smoke", "off", "high"):
        directory = args.bundle / stage
        if (directory / "run_data.json").is_file():
            stages[stage], calls_by_stage[stage] = audit_stage(directory, stage, checks)
    combined_ab = [c for stage in ("off", "high") for c in calls_by_stage.get(stage, [])]
    if "off" in stages and "high" in stages:
        checks["ab.seven_same_actual_first_inputs"] = len(stages["off"]["first_input_sha256"]) == 7 and stages["off"]["first_input_sha256"] == stages["high"]["first_input_sha256"] and all(stages["off"]["first_input_sha256"].values())
    compare_path = args.bundle / "comparison" / "compare.json"
    if compare_path.is_file():
        comparison = read(compare_path)
        checks["comparison.no_condition_warning"] = not comparison["warnings"]
        for key, name in (("a", "off"), ("b", "high")):
            summary, stage = comparison["summary"][key], stages[name]
            expected = {
                "calls": stage["status"]["calls"],
                "prompt_tokens": stage["usage"]["tokens"]["prompt_tokens"],
                "completion_tokens": stage["usage"]["tokens"]["completion_tokens"],
                "reasoning_tokens": stage["usage"]["reasoning_tokens"],
                "reasoning_tokens_known": stage["usage"]["reasoning_known"],
                "reasoning_unreported_calls": stage["usage"]["reasoning_unreported_thinking_calls"],
                "latency_ms_p50": stage["latency_and_budget"]["successful_calls_p50_ms"],
                "latency_ms_p90": stage["latency_and_budget"]["successful_calls_p90_ms"],
                "completion_tokens_max": stage["latency_and_budget"]["completion_peak"],
                "max_tokens": stage["latency_and_budget"]["output_budgets"],
                "problems": stage["argument"]["problems"],
                "reclassified": stage["argument"]["reclassified"],
                "self_conflicts": stage["argument"]["self_conflicts"],
                "suggestions_removed": stage["suggestions_removed"]["total"],
                "sanity": stage["all_sanity"],
            }
            for field, value in expected.items():
                checks[f"comparison.{name}.{field}"] = summary[field] == value
    transport_path = args.transport or args.bundle / "transport.json"
    transport_audit = None
    if transport_path.is_file():
        transport = read(transport_path)
        rows = transport.get("responses") or []
        counts = Counter(row["stage"] for row in rows)
        checks["transport.count_matches_rows"] = transport["request_attempts"] == len(rows)
        checks["transport.global_cap"] = transport["request_attempts"] <= transport["limit"] == 30
        checks["transport.stage_counts"] = dict(counts) == transport["stage_counts"]
        checks["transport.stage_caps"] = all(count <= transport["stage_caps"][stage] for stage, count in counts.items())
        checks["transport.every_request_completed"] = transport.get("completed") is True and len(rows) == transport["request_attempts"]
        checks["transport.business_sources_unchanged"] = transport.get("business_sha256_before") == transport.get("business_sha256_after")
        for stage, calls in calls_by_stage.items():
            name = "smoke_high" if stage == "smoke" else stage
            stage_rows = [row for row in rows if row["stage"] == name]
            checks[f"transport.{stage}.call_count"] = len(stage_rows) == len(calls)
            checks[f"transport.{stage}.usage_matches"] = [r.get("usage") or {} for r in stage_rows] == [c.get("usage") or {} for c in calls]
            checks[f"transport.{stage}.input_hash_matches"] = [r.get("messages_sha256") for r in stage_rows] == [c.get("input_sha256") for c in calls]
        transport_audit = {"request_attempts": transport["request_attempts"], "limit": transport["limit"], "stage_counts": dict(counts), "finish_reasons": dict(Counter(str(r.get("finish_reason")) for r in rows)), "usage": usage_summary(rows)}
    result = {"network_calls_by_audit": 0, "audit_only_reads_sanitized_bundle": str(args.bundle.resolve()), "stages": stages, "ab_only_usage": usage_summary(combined_ab), "transport": transport_audit, "fee_estimate_basis": {"source": "https://api-docs.deepseek.com/quick_start/pricing/", "checked_by_parent_on": "2026-11-04", "model": "deepseek-flash", "usd_per_million_offpeak": {"cache_hit": .003, "cache_miss": .15, "output": .6}, "peak_multiplier": 2, "caveat": "Estimate range only, not an invoice. Completion includes reasoning; reasoning is not added again. Smoke excluded from A/B totals."}, "checks": checks, "checks_passed": sum(checks.values()), "checks_total": len(checks), "mismatches": [k for k, v in checks.items() if not v]}
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps({"stages": list(stages), "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "mismatches": result["mismatches"]}, ensure_ascii=False))
    if result["mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
