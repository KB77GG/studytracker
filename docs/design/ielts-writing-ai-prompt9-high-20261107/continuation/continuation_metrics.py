#!/usr/bin/env python3
"""Independent offline audit of a sanitized high evaluation continuation.

Usage: python continuation_metrics.py --bundle /shared/continuation \
    --original /shared/interrupted --output audit.json
No credentials, private reasoning, student data or network are read.
"""
from __future__ import annotations

import argparse
from collections import Counter
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
    budget = 9 if stage == "continuation" else 14
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

    # The five planned argument checks are not silently passed when weak/strong
    # evaluation failed. Report availability separately from the one usable check.
    sanity = {}
    planned = (("t2-weak", "weak_has_problem", "论证问题 ≥"),
               ("t2-strong", "strong_at_most_one_problem", "论证问题 ≤"),
               ("t2-strong", "strong_no_false_contradiction_or_off_topic", "不应出现"),
               ("t2-strong", "strong_position_quote", "找到可核实的立场句"),
               ("t2-off-topic", "off_topic_identified", "应标出"))
    calculated = independent_sanity(data)
    for sid, key, label in planned:
        matches = [c for c in calculated if c["sample"] == sid and c["check"].startswith(label)]
        sanity[key] = matches[0]["ok"] if matches else None
    checks[f"{stage}.sanity_denominator"] = report["sanity"]["total"] == sum(c["ok"] is not None for c in report["sanity"]["checks"])
    checks[f"{stage}.sanity_pass_count"] = report["sanity"]["passed"] == sum(c["ok"] is True for c in report["sanity"]["checks"])
    return {"source_head": (report.get("audit") or {}).get("source_head"), "status": status, "usage": usage, "latency_and_budget": latency_stats, "evidence": dict(evidence), "argument": {**dict(argument), "problem_types": dict(types), "paragraph_verdicts": dict(verdicts)}, "suggestions_removed": {**dict(removals), "total": sum(removals.values())}, "argument_sanity": {"checks": sanity, "passed": sum(v is True for v in sanity.values()), "total_available": sum(v is not None for v in sanity.values()), "unavailable": sum(v is None for v in sanity.values()), "planned": len(sanity)}, "all_sanity": {k: report["sanity"][k] for k in ("passed", "total", "skipped")}, "samples": samples_out, "first_input_sha256": {c["sample"]: c.get("input_sha256") for c in first}}, calls


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




def independent_sanity(data):
    """Compute expectations from source samples/final payloads, without product imports."""
    rows = []
    def add(sample, label, ok):
        rows.append({"sample": sample, "check": label, "ok": ok})
    for sample in data["samples"]:
        expect = sample.get("expect") or {}
        if not expect:
            continue
        sid = sample["id"]
        generation = sample["generations"].get("evaluate") or {}
        result = generation.get("result") if generation.get("status") == "ready" else None
        if not result:
            add(sid, "评价已生成", False)
            continue
        score = {c["key"]: c.get("band") for c in result.get("criteria") or []}
        overall = result.get("overall_band")
        for field, label, predicate in (("overall_min", "总分 ≥", lambda a, b: a >= b), ("overall_max", "总分 ≤", lambda a, b: a <= b)):
            if field in expect:
                add(sid, f"{label} {expect[field]}", overall is not None and predicate(overall, expect[field]))
        if "task_max" in expect:
            add(sid, f"TR ≤ {expect['task_max']}（离题）", score.get("task") is not None and score["task"] <= expect["task_max"])
            add(sid, "离题样本：通过质量检查的改写必须已按题目重写", None)
        if expect.get("word_warning"):
            add(sid, "有字数不足提示", any("字数" in w for w in result.get("warnings") or []))
        arg = result.get("argument") or {}
        arg_expect = any(k in expect for k in ("argument_max_problems", "argument_min_problems", "argument_forbid", "argument_any_of", "argument_position"))
        if arg_expect and not arg:
            add(sid, "有论证结构分析", False)
        elif arg_expect:
            problem_types = [p["type"] for p in arg.get("problems") or []]
            signals = set(problem_types)
            if any(p.get("verdict") == "off_position" for p in arg.get("paragraphs") or []):
                signals.add("off_position")
            if (arg.get("position") or {}).get("consistent") is False:
                signals.add("inconsistent_position")
            if "argument_max_problems" in expect:
                n = expect["argument_max_problems"]
                add(sid, f"论证问题 ≤ {n} 条（强文不应被挑出很多问题）", len(problem_types) <= n)
            if "argument_min_problems" in expect:
                n = expect["argument_min_problems"]
                add(sid, f"论证问题 ≥ {n} 条（弱文应被指出问题）", len(problem_types) >= n)
            if "argument_forbid" in expect:
                add(sid, f"不应出现 {' / '.join(expect['argument_forbid'])}（问题类型、段落判定或立场一致性）", not (signals & set(expect["argument_forbid"])))
            if "argument_any_of" in expect:
                add(sid, f"应标出 {' / '.join(expect['argument_any_of'])}（问题类型或段落判定偏离）", bool(signals & set(expect["argument_any_of"])))
            if expect.get("argument_position"):
                add(sid, "找到可核实的立场句", bool(arg.get("position")))
        if "consistency_min" in expect:
            add(sid, f"指出文内数据矛盾 ≥ {expect['consistency_min']} 条（已知样本矛盾）", len(result.get("consistency_issues") or []) >= expect["consistency_min"])
        if expect.get("not_assessable"):
            add(sid, "缺图 TA / 总分不可评", overall is None and (result.get("criteria") or [{}])[0].get("state") == "not_assessable")
    leveled = sorted((s for s in data["samples"] if s.get("level") is not None), key=lambda s: s["level"])
    bands = [(s["generations"].get("evaluate", {}).get("result") or {}).get("overall_band") for s in leveled]
    if len(bands) >= 2 and all(b is not None for b in bands):
        add("分级样本", "总分随水平不降", all(a <= b for a, b in zip(bands, bands[1:])))
        add("分级样本", "最强与最弱相差 ≥ 1.5", bands[-1] - bands[0] >= 1.5)
    return rows




def main():
    parser = argparse.ArgumentParser(description="Offline continuation audit: stage metrics and linked cumulative budget.")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert all("results" not in p.resolve().parts for p in (args.bundle,args.original))
    def forbid(event,_args):
        if event in {"socket.connect","socket.bind","socket.getaddrinfo"}:
            raise RuntimeError("Offline audit forbids network")
    sys.addaudithook(forbid)
    checks={}
    stage,calls=audit_stage(args.bundle,"continuation",checks)
    data=read(args.bundle/"run_data.json")
    report=read(args.bundle/"report.json")
    ledger=read(args.bundle/"transport.json")
    original_bytes=(args.original/"transport.json").read_bytes()
    old=json.loads(original_bytes)
    interrupted=read(args.original/"interruption.json")
    import hashlib
    check=lambda key,value: checks.__setitem__(key,bool(value))
    source_hash=hashlib.sha256(original_bytes[:-1] if original_bytes.endswith(b"\n") else original_bytes).hexdigest()
    check("link.original_ledger_hash",ledger["original_ledger_sha256"]==interrupted["ledger_sha256"]==source_hash)
    check("link.business_hash_unchanged",ledger["tools_sha256"]==old["tools_sha256"]==old["business_sha256_before"]==interrupted["tools_sha256_after"]=="f0e3cec234a5b3fb09e923be9cf649223efa793267771755ea89785e451039bc" and ledger["tools_unchanged"])
    check("link.source_labels",data["audit"]["source_head"]==report["audit"]["source_head"]==ledger["source_head"])
    responses=ledger["responses"]
    old_n,new_n=len(old["responses"]),len(responses)
    cumulative=old_n+new_n
    check("budget.original5",old_n==old["request_attempts"]==ledger["original_attempts"]==5)
    check("budget.new8",new_n==len(calls)==ledger["request_attempts"]==report["calls"]==8)
    check("budget.cumulative13",cumulative==ledger["cumulative_request_attempts"]==report["audit"]["cumulative_actual_requests"]==13)
    check("budget.limit14",ledger["original_limit"]==old["limit"]==14 and cumulative<=14)
    check("budget.continuation_max9",data["max_calls"]==report["max_calls"]==9 and new_n<=14-old_n)
    check("budget.remaining1",14-cumulative==ledger["remaining_under_original_authorization"]==1)
    check("budget.global_sequence",[r["number"] for r in responses]==list(range(old_n+1,cumulative+1)))
    new_counts=Counter(c["sample"] for c in calls)
    sample_counts={sid:old["sample_counts"][sid]+new_counts[sid] for sid in old["sample_counts"]}
    check("budget.sample_counts",sample_counts==ledger["sample_counts"] and dict(new_counts)==ledger["new_sample_counts"])
    check("budget.sample_max2",all(n<=2 for n in sample_counts.values()))
    check("budget.local_global_attempts",all(r["local_attempt"]==c["attempt"] and r["cumulative_attempt"]==old["sample_counts"][c["sample"]]+c["attempt"] for c,r in zip(calls,responses)))
    check("budget.completed",ledger["completed"] is True and len(data["samples"])==7 and ledger["ready"]==stage["status"]["final_ready"])
    check("scope.high_flash_evaluate",ledger["mode"]=="high" and ledger["kind"]=="evaluate" and ledger["model"]=="deepseek-flash" and all(r["thinking"]=="high" and r["max_tokens"]==16000 and r["timeout"]==300 for r in responses))
    for raw_key,ledger_key in (("sample","sample"),("attempt","local_attempt"),("usage","usage"),("input_sha256","messages_sha256"),("http_status","http_status")):
        check("transport."+raw_key,[c.get(raw_key) for c in calls]==[r.get(ledger_key) for r in responses])
    check("transport.all8http200",all(r["http_status"]==200 for r in responses))
    check("transport.new_first_inputs_unchanged",all(r["messages_sha256"]==old["initial_messages_sha256"][r["sample"]] for r in responses if r["local_attempt"]==0))
    check("report.stage_not_original",report["audit"]["phase"]=="continuation_only" and report["audit"]["original_requests"]==5 and report["audit"]["original_usage_unknown_calls"]==5)
    check("report.no_fees",report["estimated_cost"] is None and report["cost_estimate"]["covered_cost"] is None)
    check("report.no_teacher_or_calibration",report["teacher_findings"] is None and report["calibration"] is None)
    check("report.all_sanity_recomputed",independent_sanity(data)==[{k:c[k] for k in ("sample","check","ok")} for c in report["sanity"]["checks"]])
    for tokenkey in ("prompt_tokens","completion_tokens","total_tokens"):
        check("usage.kind_"+tokenkey,stage["usage"]["tokens"][tokenkey]==report["kinds"]["evaluate"]["tokens"][tokenkey])
    check("usage.old_unknown5",all("usage" not in r for r in old["responses"]))
    check("usage.reasoning_record_consistency",all(c["reasoning_tokens"]==c["usage"]["completion_tokens_details"]["reasoning_tokens"] for c in calls))

    sample_by_id={s["id"]:s for s in data["samples"]}
    call_findings=[]
    for c in calls:
        item={"sample":c["sample"],"local_attempt":c["attempt"],"transport_status":c["http_status"],"client_ok":c["ok"],"client_error":c.get("error"),"strict_json":None,"json_error":None,"malformed_criterion_fields":[]}
        if c.get("ok"):
            parsed=strict_json(c.get("text"))
            item["strict_json"]=parsed is not None
            if parsed is None:
                try: json.loads(c.get("text") or "")
                except json.JSONDecodeError as exc:
                    item["json_error"]={"message":exc.msg,"position":exc.pos,"length":len(c.get("text") or ""),"at_eof":exc.pos==len(c.get("text") or "")}
            else:
                crit=parsed.get("criteria") if isinstance(parsed.get("criteria"),dict) else parsed
                item["malformed_criterion_fields"]=[{"field":k,"type":type(crit.get(k)).__name__,"value":crit.get(k)} for k in ("task","coherence","lexical","grammar") if not isinstance(crit.get(k),dict) and not (sample_by_id[c["sample"]]["task_type"]=="task1" and k=="task" and crit.get(k) is None)]
        call_findings.append(item)
    diagnosed={(c["sample"],c["local_attempt"]) for c in call_findings if c["strict_json"] is False}
    check("report.json_diagnostic_attempts",diagnosed=={(p["sample"],p["attempt"]) for p in report["kinds"]["evaluate"]["json_problems"]})
    first=[c for c in calls if c["attempt"]==0]
    check("report.first_rejection_denominator",sum(report["kinds"]["evaluate"]["first_attempt_rejections"].values())==len(first)-stage["status"]["first_valid"])
    mid=next(c for c in call_findings if c["sample"]=="t2-mid")
    check("failure.mid_task_numeric",any(x["field"]=="task" and x["value"]==7.0 for x in mid["malformed_criterion_fields"]))
    weak=calls[0]
    check("failure.weak_all_reasoning",weak["sample"]=="t2-weak" and weak["error"]=="truncated" and weak["usage"]["completion_tokens"]==weak["reasoning_tokens"]==16000 and not weak.get("text") and responses[0]["finish_reason"]=="length")
    rows=[];adopted=set();literal_differences=[]
    for sid,s in sample_by_id.items():
        g=s["generations"]["evaluate"]
        result=g.get("result") or {}
        ready=g["status"]=="ready"
        check("score."+sid+".failure_without_score",ready or g.get("result") is None)
        criteria=result.get("criteria") or []
        scores={c["key"]:c.get("band") for c in criteria}
        scored=[c["band"] for c in criteria if c["state"]=="scored"]
        mean=math.floor(sum(scored)/4*2+0.5+1e-9)/2 if len(scored)==4 else None
        check("score."+sid+".arithmetic",result.get("overall_band")==mean)
        matching=[c for c in calls if c["sample"]==sid]
        if ready: adopted.add((sid,matching[-1]["attempt"]))
        reason=g.get("error_code")
        if sid=="t2-mid": reason="task is 7.0, not a criterion object; validation retry blocked by original per-sample cap2"
        elif sid=="t2-strong": reason="formal reply is invalid JSON; validation retry blocked by original per-sample cap2"
        elif sid=="t2-under-length": reason="first reply invalid JSON; second reply accepted"
        elif sid=="t2-weak": reason="length at16000, all reported completion tokens are reasoning; no formal answer"
        rows.append({"id":sid,"status":g["status"],"final_error_code":g.get("error_code"),"reason":reason,"new_calls":len(matching),"cumulative_calls":sample_counts[sid],"remaining_for_this_sample":2-sample_counts[sid],"scores":scores,"overall":result.get("overall_band"),"consistency_issues":result.get("consistency_issues") or []})
        for criterion in criteria:
            for entry in (criterion.get("strengths") or [])+(criterion.get("issues") or []):
                q=entry.get("quote") or ""
                if q and q not in s["submission"]["essay_text"]:
                    literal_differences.append({"sample":sid,"criterion":criterion["key"],"quote":q,"normalized_match":found(s["submission"]["essay_text"],q)})
    check("failure.mid_strong_final_budget",all(sample_by_id[s]["generations"]["evaluate"]["error_code"]=="call_budget" and sample_counts[s]==2 for s in ("t2-mid","t2-strong")))
    check("failure.under_length_retry_succeeds",sample_by_id["t2-under-length"]["generations"]["evaluate"]["status"]=="ready" and new_counts["t2-under-length"]==2)
    not_adopted=[c for c in calls if (c["sample"],c["attempt"]) not in adopted]
    failed_samples=[c for c in calls if sample_by_id[c["sample"]]["generations"]["evaluate"]["status"]!="ready"]
    unknown_old=5
    total_summary={"actual_requests":cumulative,"original_limit":14,"remaining_global":14-cumulative,"sample_counts":sample_counts,"known_usage_subtotal":stage["usage"],"usage_unknown_calls":unknown_old+stage["usage"]["unreported_calls"]["completion_tokens"],"complete_token_usage":None,"complete_reasoning_tokens":None,"fees":None,"original_batch_first_json_rate":None,"original_batch_first_content_rate":None,"final_available_evaluation_coverage":{"numerator":stage["status"]["final_ready"],"denominator":7},"note":"Old five attempts remain in HTTP budget; absent usage is unknown, not zero. Continuation first-attempt rates use local attempt0, not original cumulative attempt0."}
    lat={"product_client_ok_only":{"calls":sum(bool(c["ok"]) for c in calls),"p50_ms":percentile([c["latency_ms"] for c in calls if c["ok"]],.5),"p90_ms":percentile([c["latency_ms"] for c in calls if c["ok"]],.9)},"all_eight_including_truncated":{"calls":len(calls),"p50_ms":percentile([c["latency_ms"] for c in calls],.5),"p90_ms":percentile([c["latency_ms"] for c in calls],.9)},"all_eight_transport_only":{"p50_ms":percentile([r["latency_ms"] for r in responses],.5),"p90_ms":percentile([r["latency_ms"] for r in responses],.9)}}
    output={"audit_network_calls":0,"reads_sanitized_only":True,"source_head":ledger["source_head"],"tools_sha256":ledger["tools_sha256"],"continuation":stage,"cumulative":total_summary,"per_sample":rows,"formal_reply_diagnostics":call_findings,"product_json_diagnostics":report["kinds"]["evaluate"]["json_problems"],"latency_definitions":lat,"not_adopted_usage_already_in_stage_total":usage_summary(not_adopted),"failed_samples_usage_already_in_stage_total":usage_summary(failed_samples),"literal_quote_differences":literal_differences,"sanity":independent_sanity(data),"checks":checks,"checks_passed":sum(checks.values()),"checks_total":len(checks),"mismatches":[k for k,v in checks.items() if not v]}
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    u=stage["usage"]["tokens"];e=stage["evidence"];a=stage["argument"]
    md=["# .9 high 续跑：独立统计审计","",f"检查 **{output['checks_passed']}/{output['checks_total']}**；差异：{output['mismatches'] or '无'}。仅脱敏资料，未调用模型。","",
        "- 新增 **8** 次 HTTP，全部200；关联旧 **5** 次，累计 **13/14**。每篇累计≤2；剩余1次仅在Task1样本配额内，不能用于weak/mid/strong。此次已完成，审计没有启动额外调用。",
        "- **续跑阶段**首轮严格JSON **4/7**，首轮内容通过 **3/7**，最终ready **4/7**。原批完整首轮率未知；不可用本阶段首轮率代替。",
        "- 原批已有3次500，另2次完成内容未知；不能因后续恢复就删除旧预算或将旧用量记0。",
        f"- 续跑已知token：输入 **{u['prompt_tokens']}**，输出 **{u['completion_tokens']}**，总量 **{u['total_tokens']}**；其中reasoning **{stage['usage']['reasoning_tokens']}**已包含输出。cache hit/miss **{u['prompt_cache_hit_tokens']}/{u['prompt_cache_miss_tokens']}**。这些只是累计13次中的已知小计；旧5次用量、完整累计用量和费用仍未知。",
        "- weak：16000输出token全部记为reasoning，finish_reason=length，没有正式回答；失败用量仍全部计入。mid：task值为7.0而不是带理由和证据的评分对象，校验先拒绝TR；strong：JSON括号错误。后二者需要校验重试，但各自在原批已用过1次，续跑再用1次即达到每篇2次，故最终状态call_budget。",
        "- under-length首稿仍有坏括号，第二次通过；其重试用量也计入。未修补任何正式输出或制造分数。",
        f"- 产品p50/p90（仅client.ok=True的7次，排除截断）**{lat['product_client_ok_only']['p50_ms']/1000:g}/{lat['product_client_ok_only']['p90_ms']/1000:g}秒**；含截断的全部8次为 **{lat['all_eight_including_truncated']['p50_ms']/1000:g}/{lat['all_eight_including_truncated']['p90_ms']/1000:g}秒**。输出峰值 **16000/16000=100%**。",
        f"- 最终评分引文规范化匹配 **{e.get('normalized_quotes',0)}/{e.get('quotes',0)}**，严格逐字 **{e.get('literal_quotes',0)}/{e.get('quotes',0)}**；论证条目 **{a.get('returned',0)}={a.get('kept',0)}采用+{a.get('dropped',0)}丢弃+{a.get('duplicates',0)}重复+{a.get('over_limit',0)}超限**。只证明位置匹配，不能证明批评和分数正确。",
        "- 全部合理性检查7/10，另跳过1项改写检查；原计划5项论证检查仅离题项有结果并通过，weak/strong相关4项不可评，不应写5/5。","",
        "| 样本 | 状态 | 原累计请求 | TR/TA | CC | LR | GRA | 总分 |","|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        vals=[r['scores'].get(k) for k in ('task','coherence','lexical','grammar')]
        md.append('| '+' | '.join(str(v) if v is not None else '—' for v in [r['id'],r['status'],r['cumulative_calls'],*vals,r['overall']])+' |')
    md += ["","本次只能确认本次续跑的8次已返回HTTP200；旧5次与本次续跑并非完整同条件首轮实验。不得把中断阶段的未知当作零用量，也不能以缺失结果证明评分准确或不准确。费用未估算。"]
    args.output.with_suffix('.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(json.dumps({k:output[k] for k in ('checks_passed','checks_total','mismatches')},ensure_ascii=False))
    if output['mismatches']: raise SystemExit(1)


if __name__=='__main__': main()
