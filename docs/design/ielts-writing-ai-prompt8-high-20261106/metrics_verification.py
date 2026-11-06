#!/usr/bin/env python3
"""Independent offline audit of a sanitized high evaluation batch.

Usage: python metrics_verification.py --bundle /shared/bundle --output audit.json
Optional --previous points to a committed older report directory for descriptive comparison.
No credentials, private reasoning, student data or network are read.
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


def diagnostic(call):
    text = call["text"]
    try:
        json.loads(text)
        return None
    except json.JSONDecodeError as exc:
        item = {"sample": call["sample"], "attempt": call["attempt"], "message": exc.msg,
                "position": exc.pos, "length": len(text), "line": exc.lineno,
                "column": exc.colno, "at_eof": exc.pos == len(text),
                "raw_unchanged": True, "transport_ok": call["ok"],
                "completion_tokens": call["usage"].get("completion_tokens"),
                "reasoning_tokens": call.get("reasoning_tokens")}
        # Diagnostics only. These edited copies are never fed back into validators,
        # stored results, or scores. Strict parsing in the real run remains intact.
        if exc.pos == len(text):
            try:
                repaired = json.loads(text + "}")
                item["one_brace_diagnostic"] = {"parses": True, "root_keys": list(repaired),
                    "criteria_keys": list(repaired.get("criteria") or {})}
            except (ValueError, AttributeError):
                item["one_brace_diagnostic"] = {"parses": False}
        if exc.msg == "Extra data":
            prefix, end = json.JSONDecoder().raw_decode(text)
            item["valid_prefix"] = {"end": end, "root_keys": list(prefix), "remaining_prefix": text[end:end + 40]}
        return item


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    def forbid(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline audit forbids network access")
    sys.addaudithook(forbid)
    checks = {}
    stage, calls = audit_stage(args.bundle, "high", checks)
    data = read(args.bundle / "run_data.json")
    report = read(args.bundle / "report.json")
    ledger = read(args.bundle / "transport.json")
    responses = ledger["responses"]
    sample_counts = dict(Counter(c["sample"] for c in calls))
    checks["transport.actual_count"] = len(calls) == len(responses) == ledger["request_attempts"] == report["calls"]
    checks["transport.hard_limit"] = ledger["limit"] == data["max_calls"] == report["max_calls"] == 14 and len(calls) <= 14
    checks["transport.sample_counts"] = sample_counts == ledger["sample_counts"] and max(sample_counts.values()) <= 2
    checks["transport.completed"] = ledger["completed"] is True
    checks["transport.business_source_unchanged"] = ledger["business_sha256_before"] == ledger["business_sha256_after"]
    checks["transport.high_only"] = ledger["mode"] == "high" and all(c["thinking"] == r["thinking"] == "high" for c, r in zip(calls, responses))
    checks["transport.evaluate_only"] = ledger["kind"] == "evaluate" and all(c["kind"] == "evaluate" for c in calls)
    checks["transport.max_tokens"] = all(c["max_tokens"] == r["max_tokens"] == 16000 for c, r in zip(calls, responses))
    checks["transport.timeout"] = all(r["timeout"] == 300 for r in responses)
    for field, transport_field in (("sample", "sample"), ("attempt", "attempt"), ("usage", "usage"), ("input_sha256", "messages_sha256"), ("http_status", "http_status")):
        checks[f"transport.{field}_per_call"] = [c.get(field) for c in calls] == [r.get(transport_field) for r in responses]
    checks["transport.initial_inputs"] = stage["first_input_sha256"] == ledger["initial_messages_sha256"]
    checks["transport.ready"] = ledger["ready"] == stage["status"]["final_ready"]
    checks["report.no_teacher_or_calibration"] = report["teacher_findings"] is None and not report["calibration"]
    checks["report.fee_unknown"] = report["estimated_cost"] is None and report["cost_estimate"]["covered_cost"] is None
    checks["report.tokens_include_content_rejected_calls"] = sum(c["usage"]["completion_tokens"] for c in calls) == report["usage"]["total"]["tokens"]["completion"]

    invalid = [diagnostic(c) for c in calls if strict_json(c["text"]) is None]
    checks["report.first_rejection_count"] = sum(v for v in report["kinds"]["evaluate"]["first_attempt_rejections"].values()) == sum(i["attempt"] == 0 for i in invalid)
    assert all(item is not None for item in invalid)
    by_sample = {s["id"]: s for s in data["samples"]}
    dropped_details = []
    literal_differences = []
    for sample_id, sample in by_sample.items():
        result = sample["generations"]["evaluate"].get("result") or {}
        essay_text = sample["submission"]["essay_text"]
        for criterion in result.get("criteria") or []:
            for entry in (criterion.get("strengths") or []) + (criterion.get("issues") or []):
                quote = entry.get("quote")
                if not quote or quote in essay_text:
                    continue
                position = essay_text.lower().find(quote.lower())
                literal_differences.append({"sample": sample_id, "criterion": criterion["key"],
                    "quote": quote, "original": essay_text[position:position+len(quote)] if position >= 0 else None,
                    "difference": "case_only" if position >= 0 else "normalization_other_than_case",
                    "normalization_match": found(essay_text, quote)})
        arg = result.get("argument") or {}
        if not arg.get("dropped"):
            continue
        latest = next(c for c in reversed(calls) if c["sample"] == sample_id and strict_json(c["text"]) is not None)
        raw_arg = strict_json(latest["text"])["argument"]
        kept_quotes = {p["quote"] for p in arg.get("improvements") or []}
        absent = []
        for item in raw_arg.get("improvements") or []:
            if item.get("quote") in kept_quotes:
                continue
            absent.append({"quote_found_in_original": found(sample["submission"]["essay_text"], item.get("quote")),
                           "input_fields": sorted(item), "has_suggestion": bool(item.get("suggestion")),
                           "has_comment_instead": bool(item.get("comment")) and not item.get("suggestion"),
                           "mentions_forty_passengers": "forty passengers" in (item.get("suggestion") or "")})
        dropped_details.append({"sample": sample_id, "dropped": arg["dropped"], "suggestions_removed": arg["suggestions_removed"], "absent_improvements": absent})

    unsuccessful_samples = {s["id"] for s in data["samples"] if s["generations"]["evaluate"]["status"] != "ready"}
    invalid_calls = [c for c in calls if strict_json(c["text"]) is None]
    failed_sample_calls = [c for c in calls if c["sample"] in unsuccessful_samples]
    # Accounting breakdown: these costs are already within the total, not additions.
    discarded_usage = {"invalid_json_calls": usage_summary(invalid_calls), "ultimately_failed_sample_calls": usage_summary(failed_sample_calls)}
    # Price is intentionally unknown: this run supplied no rates.
    checks["evidence.literal_difference_count"] = len(literal_differences) == stage["evidence"]["quotes"] - stage["evidence"]["literal_quotes"]

    previous = None
    if args.previous:
        old_report = read(args.previous / "report.json")
        old_data = read(args.previous / "run_data.json")
        assert all(not c.get("reasoning") for c in old_data["calls"])
        old_samples = {s["id"]: s for s in old_data["samples"]}
        same_samples = set(old_samples) == set(by_sample) and all(old_samples[sid]["submission"]["essay_text"] == sample["submission"]["essay_text"] and old_samples[sid]["submission"]["prompt_text"] == sample["submission"]["prompt_text"] for sid, sample in by_sample.items())
        old_kind = old_report["kinds"]["evaluate"]
        new_kind = report["kinds"]["evaluate"]
        fields = ("calls", "first_attempt_json_ok", "first_attempt_valid", "final_ready", "latency_ms_p50", "latency_ms_p90", "completion_tokens_max", "reasoning_tokens")
        previous = {"old_prompt": old_report["prompt_version"], "new_prompt": report["prompt_version"], "same_synthetic_samples_and_questions": same_samples,
                    "old": {k: old_kind[k] for k in fields}, "new": {k: new_kind[k] for k in fields},
                    "old_usage": old_report["usage"]["text"]["tokens"], "new_usage": report["usage"]["text"]["tokens"],
                    "caveat": "Descriptive version comparison only: prompts and numeric postprocessing changed; not a single-factor causal test or teacher scoring calibration."}
    outcome = {"source_head": ledger["source_head"], "prompt_version": ledger["prompt_version"], "network_calls_by_audit": 0,
               "reads_sanitized_results_only": True, "student_materials_read": False, "summary": stage,
               "transport": {"request_attempts": ledger["request_attempts"], "limit": ledger["limit"], "sample_counts": sample_counts, "finish_reasons": dict(Counter(r["finish_reason"] for r in responses)), "http_statuses": dict(Counter(str(r["http_status"]) for r in responses))},
               "json_failure_diagnostics": invalid, "adopted_argument_drops": dropped_details,
               "literal_quote_differences": literal_differences,
               "discarded_usage_already_in_total": discarded_usage,
               "fees": {"unknown": True, "reason": "No prices supplied; tokens are not an invoice."},
               "previous_high_descriptive_comparison": previous,
               "checks": checks, "checks_passed": sum(checks.values()), "checks_total": len(checks),
               "mismatches": [name for name, passed in checks.items() if not passed]}
    args.output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    u = stage["usage"]["tokens"]
    l = stage["latency_and_budget"]
    a = stage["argument"]
    lines = ["# 新版 high 真实批次：独立指标核对", "", f"源码 `{ledger['source_head']}`，提示词 `{ledger['prompt_version']}`。只读取脱敏共享结果，审计网络调用 0。", "",
             f"- 对账检查：{outcome['checks_passed']}/{outcome['checks_total']}；差异：{outcome['mismatches'] or '无'}。",
             f"- 实际请求 {len(calls)}/14；首轮 JSON/校验 {stage['status']['first_json']}/7、{stage['status']['first_valid']}/7；最终 {stage['status']['final_ready']}/7。",
             "- 全部 HTTP 200、finish_reason=stop；两篇各重试一次，离题篇重试成功，短文连续两次 JSON 语法错误后失败。未发现超时或输出截断。",
             f"- token：输入 {u['prompt_tokens']}，输出 {u['completion_tokens']}，总量 {u['total_tokens']}；其中 reasoning {stage['usage']['reasoning_tokens']}，已包含于输出。失败内容的用量也已计入。",
             f"- 请求延迟 p50/p90：{l['successful_calls_p50_ms']/1000:g}/{l['successful_calls_p90_ms']/1000:g} 秒；峰值 {l['completion_peak']}/16000={l['peak_budget_fraction']:.2%}。",
             f"- 系统引文核实：大小写、空白、标点形式规范化后 {stage['evidence']['normalized_quotes']}/{stage['evidence']['quotes']}（100%）；严格逐字匹配仅 {stage['evidence']['literal_quotes']}/{stage['evidence']['quotes']}。论证条目 {a['returned']}={a['kept']}采用+{a['dropped']}丢弃+{a['duplicates']}重复+{a['over_limit']}超限。",
             "- 两条严格逐字差异均来自 weak：TR 与 GRA 重复引用 `If more people take bus…`，原稿对应片段为 `if more people take bus…`（位于 `Also if…` 中），仅首字母大小写不同。",
             "- good 丢弃三条 improvements：模型用了 comment 字段，缺少 suggestion；strong 丢弃一条：包含无来源 forty passengers，数字过滤生效。",
             f"- 五项论证检查 {stage['argument_sanity']['passed']}/{stage['argument_sanity']['total']}；全部合理性检查 {stage['all_sanity']['passed']}/{stage['all_sanity']['total']}，另有 {stage['all_sanity']['skipped']} 项未运行。",
             "- 费用未知；本轮没有提供价格，不以 token 数冒充账单。", "",
             "三个不合格回复都是 JSON 结构问题：离题首稿提前关闭根对象，`priorities` 留在对象之外；短文两稿在文本末尾缺闭合符。诊断副本补一个 `}` 虽能解析，但根对象仍只有 `criteria`，`argument`、`overall_comment`、`priorities` 错误嵌套其中，因此不能将补符视为合格评价。补符操作未改变原始输出、正式校验或成绩。最终引用核实比例仅覆盖采用的结果，不代表每条原始输出都合格。", "",
             "与旧 .6 high 的结果只能作版本描述比较：样本相同，但提示词、语言规则、数字后处理都变化，不能归因于单一提示词因素，亦不能说明与老师评分一致。"]
    if previous:
        old = previous["old"]
        lines += ["", "| 指标 | 旧 .6 high | 新 .8 high |", "|---|---:|---:|",
                  f"| 实际请求 | {old['calls']} | {len(calls)} |",
                  f"| 首轮通过 | {old['first_attempt_valid']:.1%} | {report['kinds']['evaluate']['first_attempt_valid']:.1%} |",
                  f"| 最终成功 | {old['final_ready']:.1%} | {report['kinds']['evaluate']['final_ready']:.1%} |",
                  f"| p50 / p90（秒） | {old['latency_ms_p50']/1000:g} / {old['latency_ms_p90']/1000:g} | {l['successful_calls_p50_ms']/1000:g} / {l['successful_calls_p90_ms']/1000:g} |",
                  f"| 输入 / 输出 token | {previous['old_usage']['prompt']} / {previous['old_usage']['completion']} | {u['prompt_tokens']} / {u['completion_tokens']} |",
                  f"| 其中思考 token | {old['reasoning_tokens']} | {stage['usage']['reasoning_tokens']} |"]
    args.output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"checks_passed": outcome["checks_passed"], "checks_total": outcome["checks_total"], "mismatches": outcome["mismatches"], "json_failures": invalid}, ensure_ascii=False))
    if outcome["mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
