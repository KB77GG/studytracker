#!/usr/bin/env python3
"""Independent offline arithmetic audit of the exported .12 evaluation group.

Only sanitized shared-evidence is read. No credentials, response binary files,
private reasoning, model calls, or production data are needed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path


def strict_object(text):
    text = (text or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, flags=re.S)
    if match:
        text = match.group(1)
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def ratio(n, d):
    return round(n / d, 3) if d else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).parent / "shared-evidence")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_suffix(".json"))
    parser.add_argument('--group', choices=('A', 'B'), required=True)
    args = parser.parse_args()
    requested_samples, cap = (7, 14) if args.group == 'A' else (1, 2)

    def forbid(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline audit forbids network")

    sys.addaudithook(forbid)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo.resolve()))
    from tools.ielts_writing_ai import review

    names = ("run_data.json", "report.json", "transport.json", "formal_responses.json")
    snapshots = {name: (args.evidence / name).read_bytes() for name in names}
    data, report, ledger, formal = [json.loads(snapshots[name]) for name in names]
    if not ledger.get("completed") and not ledger.get("circuit"):
        raise RuntimeError("Batch still active; audit a complete checkpoint")
    checks = []

    def check(name, actual, expected=True):
        checks.append(
            {"name": name, "ok": actual == expected, "actual": actual, "expected": expected}
        )

    def private_fields(value):
        if isinstance(value, dict):
            return any(
                k in {"reasoning", "reasoning_content", "llm_api_key", "authorization"}
                or private_fields(v)
                for k, v in value.items()
            )
        if isinstance(value, list):
            return any(private_fields(v) for v in value)
        return False

    check(
        "sanitized_inputs", not any(private_fields(obj) for obj in (data, report, ledger, formal))
    )
    calls, entries, samples = data["calls"], ledger["responses"], data["samples"]
    by_id = {s["id"]: s for s in samples}
    check("unique_sample_ids", len(by_id), len(samples))
    check("requested_samples", data.get("audit", {}).get("requested_samples"), requested_samples)
    check("http_budget", len(entries) <= cap)
    check("ledger_total", ledger["request_attempts"], len(entries))
    check(
        "sequential_reservations", [e["number"] for e in entries], list(range(1, len(entries) + 1))
    )
    counts = Counter(e["sample"] for e in entries)
    check("per_sample_cap2", all(n <= 2 for n in counts.values()))
    for sid, count in ledger["sample_counts"].items():
        check("ledger_per_sample." + sid, count, counts[sid])
    check("evaluation_only", data["kinds"], ["evaluate"])
    check("call_count", len(calls), len(entries))
    check("report_calls", report["calls"], len(calls))
    check("report_samples", report["samples"], len(samples))
    check("report_max_calls", report["max_calls"], cap)
    check(
        "transport_options",
        all(
            e["thinking"] == "high" and e["max_tokens"] == 32000 and e["timeout"] == 300
            for e in entries
        ),
    )
    check(
        "recorded_options",
        all(
            c["kind"] == "evaluate" and c["thinking"] == "high" and c["max_tokens"] == 32000
            for c in calls
        ),
    )
    check("no_vision", report["vision_calls"], 0)
    formal_by_number = {f["number"]: f for f in formal}
    for e, c in zip(entries, calls, strict=True):
        check(
            f"call_alignment.{e['number']}",
            (e["sample"], e["attempt"]),
            (c["sample"], c["attempt"]),
        )
        check(f"usage_alignment.{e['number']}", e.get("usage") or {}, c.get("usage") or {})
        check(f"messages_alignment.{e['number']}", e["messages_sha256"], c["input_sha256"])
        if c.get("ok"):
            check(
                f"formal_text_alignment.{e['number']}",
                formal_by_number[e["number"]]["formal_text"],
                c["text"],
            )

    first = [c for c in calls if c["attempt"] == 0]
    json_n = valid_n = 0
    validation = []
    for c in first:
        raw = strict_object(c.get("text")) if c.get("ok") else None
        json_n += raw is not None
        valid = False
        problem = c.get("error") if not c.get("ok") else "invalid_json"
        if raw is not None:
            try:
                review.normalize_evaluation(
                    copy.deepcopy(raw), copy.deepcopy(by_id[c["sample"]]["submission"])
                )
                valid, problem = True, None
            except Exception as exc:
                problem = str(exc)
        valid_n += valid
        validation.append(
            {"sample": c["sample"], "json_ok": raw is not None, "valid": valid, "problem": problem}
        )
    ready = [s for s in samples if s["generations"]["evaluate"]["status"] == "ready"]
    metrics = report["kinds"]["evaluate"]
    check("first_attempt_count", metrics["first_attempts"], len(first))
    check("first_json_rate", metrics["first_attempt_json_ok"], ratio(json_n, len(first)))
    check("first_valid_rate", metrics["first_attempt_valid"], ratio(valid_n, len(first)))
    check("final_ready_rate", metrics["final_ready"], ratio(len(ready), len(samples)))
    check("thinking_modes", metrics["thinking"], ["high"])
    check("token_budget", metrics["max_tokens"], [32000])
    totals = Counter()
    reason_values, output_values = [], []
    unknown_usage = missing_reason = 0
    for e in entries:
        usage = e.get("usage") or {}
        unknown_usage += not all(
            type(usage.get(k)) is int for k in ("prompt_tokens", "completion_tokens")
        )
        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if type(usage.get(k)) is int:
                totals[k] += usage[k]
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        if type(reasoning) is int:
            reason_values.append(reasoning)
        else:
            missing_reason += 1
        if type(usage.get("completion_tokens")) is int:
            output_values.append(usage["completion_tokens"])
    check("kind_usage_totals", metrics["tokens"], dict(totals))
    check(
        "reasoning_known",
        metrics["reasoning_tokens_known"],
        sum(reason_values) if reason_values else None,
    )
    check("reasoning_missing", metrics["reasoning_unreported_calls"], missing_reason)
    check(
        "reasoning_total",
        metrics["reasoning_tokens"],
        sum(reason_values) if reason_values and not missing_reason else None,
    )
    check(
        "reasoning_peak",
        metrics["reasoning_tokens_max"],
        max(reason_values) if reason_values else None,
    )
    check(
        "output_peak",
        metrics["completion_tokens_max"],
        max(output_values) if output_values else None,
    )
    for k, source in (("prompt", "prompt_tokens"), ("completion", "completion_tokens")):
        complete = all(type((e.get("usage") or {}).get(source)) is int for e in entries)
        check(
            "report_token_total." + k, report["tokens"].get(k), totals[source] if complete else None
        )
        check(
            "report_known_token_total." + k,
            report["usage"]["total"]["known_tokens"][k],
            totals[source],
        )
    check("unknown_usage_calls", report["usage"]["total"]["unknown_usage_calls"], unknown_usage)
    trunc = sum(e.get("finish_reason") == "length" for e in entries)
    timeouts = sum(c.get("error") == "timeout" for c in calls)
    check("truncated", metrics["truncated"], trunc)
    check("timeouts", metrics["timeouts"], timeouts)
    max_ms = max((e.get("latency_ms", 0) for e in entries), default=0)
    check("audit_max_latency", report["audit"]["max_transport_latency_ms"], max_ms)
    successful_ms = sorted(c["latency_ms"] for c in calls if c.get("ok"))
    for q, key in ((0.5, "latency_ms_p50"), (0.9, "latency_ms_p90")):
        expected = successful_ms[math.ceil(len(successful_ms) * q) - 1] if successful_ms else None
        check(key, metrics[key], expected)

    arg_sums = Counter()
    types, verdicts = Counter(), Counter()
    for s in samples:
        r = s["generations"]["evaluate"].get("result") or {}
        if s["task_type"] != "task2" or not r:
            continue
        arg_sums["task2_evaluations"] += 1
        a = r.get("argument")
        if not a:
            continue
        arg_sums["with_argument"] += 1
        arg_sums["with_position"] += bool(a.get("position"))
        for out, field in (
            ("paragraphs", "paragraphs"),
            ("problems", "problems"),
            ("improvements", "improvements"),
        ):
            arg_sums[out] += len(a.get(field) or [])
        for key in (
            "returned",
            "dropped",
            "duplicates",
            "over_limit",
            "self_conflicts",
            "suggestions_removed",
            "reclassified",
        ):
            arg_sums[key] += a.get(key) or 0
        types.update(p["type"] for p in a.get("problems") or [])
        verdicts.update(p["verdict"] for p in a.get("paragraphs") or [])
    arg_sums["kept"] = sum(
        arg_sums[k] for k in ("with_position", "paragraphs", "problems", "improvements")
    )
    for key, value in arg_sums.items():
        check("argument." + key, report["argument"][key], value)
    check(
        "argument_accounting",
        arg_sums["returned"],
        sum(arg_sums[k] for k in ("kept", "dropped", "duplicates", "over_limit")),
    )
    check(
        "argument_drop_rate",
        report["argument"]["dropped_rate"],
        ratio(arg_sums["dropped"], arg_sums["returned"]),
    )
    check("argument_types", report["argument"]["problem_types"], dict(types))
    check("argument_verdicts", report["argument"]["paragraph_verdicts"], dict(verdicts))
    quotes = verified = scored = corrections = 0
    removed = Counter()
    for sample in samples:
        result_data = sample["generations"]["evaluate"].get("result") or {}
        removed.update(
            {
                k: v
                for k, v in (result_data.get("suggestions_removed") or {}).items()
                if k != "total"
            }
        )
        corrections += len(result_data.get("count_corrections") or [])
        for criterion in result_data.get("criteria") or []:
            if criterion.get("state") != "scored":
                continue
            scored += 1
            for entry in (criterion.get("strengths") or []) + (criterion.get("issues") or []):
                if isinstance(entry, dict) and entry.get("quote"):
                    quotes += 1
                    verified += bool(entry.get("quote_found"))
    for key, value in {
        "scored_criteria": scored,
        "quotes": quotes,
        "quotes_verified": ratio(verified, quotes),
        "suggestions_removed": {**dict(removed), "total": sum(removed.values())},
        "count_corrections": corrections,
    }.items():
        check("evidence." + key, report["evidence"][key], value)
    for row in report["per_sample"]:
        result_data = by_id[row["id"]]["generations"]["evaluate"].get("result") or {}
        scores = {
            "overall": result_data.get("overall_band"),
            **{c["key"]: c["band"] for c in result_data.get("criteria") or []},
        }
        check("sample_scores." + row["id"], row["scores"], scores)

    sanity = report["sanity"]
    check("sanity_passed", sanity["passed"], sum(c["ok"] is True for c in sanity["checks"]))
    check("sanity_total", sanity["total"], sum(c["ok"] is not None for c in sanity["checks"]))
    check("sanity_skipped", sanity["skipped"], sum(c["ok"] is None for c in sanity["checks"]))
    # Validate each sanity flag from final results and declared sample expectations.
    for n, row in enumerate(sanity["checks"]):
        if row["sample"] == "分级样本":
            leveled = sorted(
                (s for s in samples if s.get("level") is not None), key=lambda s: s["level"]
            )
            bands = [s["generations"]["evaluate"]["result"]["overall_band"] for s in leveled]
            expected = (
                all(a <= b for a, b in zip(bands, bands[1:], strict=False))
                if row["check"] == "总分随水平不降"
                else bands[-1] - bands[0] >= 1.5
            )
        else:
            sample = by_id[row["sample"]]
            exp = sample.get("expect") or {}
            r = sample["generations"]["evaluate"].get("result") or {}
            label = row["check"]
            a = r.get("argument") or {}
            issues = a.get("problems") or []
            signals = {p["type"] for p in issues}
            if any(p["verdict"] == "off_position" for p in a.get("paragraphs") or []):
                signals.add("off_position")
            if (a.get("position") or {}).get("consistent") is False:
                signals.add("inconsistent_position")
            overall = r.get("overall_band")
            if label == "评价已生成":
                expected = bool(r)
            elif label.startswith("总分 ≥"):
                expected = overall is not None and overall >= exp["overall_min"]
            elif label.startswith("总分 ≤"):
                expected = overall is not None and overall <= exp["overall_max"]
            elif label.startswith("TR ≤"):
                task_band = next((c["band"] for c in r["criteria"] if c["key"] == "task"), None)
                expected = task_band is not None and task_band <= exp["task_max"]
            elif label == "有字数不足提示":
                expected = any("字数" in w for w in r.get("warnings") or [])
            elif label == "有论证结构分析":
                expected = bool(a)
            elif label.startswith("论证问题 ≤"):
                expected = len(issues) <= exp["argument_max_problems"]
            elif label.startswith("论证问题 ≥"):
                expected = len(issues) >= exp["argument_min_problems"]
            elif label.startswith("不应出现 "):
                expected = not (signals & set(exp["argument_forbid"]))
            elif label.startswith("应标出 "):
                expected = bool(signals & set(exp["argument_any_of"]))
            elif label == "找到可核实的立场句":
                expected = a.get("position") is not None
            elif label.startswith("指出文内数据矛盾"):
                expected = len(r.get("consistency_issues") or []) >= exp["consistency_min"]
            elif label == "缺图 TA / 总分不可评":
                expected = overall is None and r["criteria"][0]["state"] == "not_assessable"
            elif "改写" in label and "rewrite" not in sample["generations"]:
                expected = None
            else:
                raise AssertionError("Unknown sanity label: " + label)
        check("sanity_flag." + str(n), row["ok"], expected)
    check(
        "input_files_unchanged",
        all((args.evidence / name).read_bytes() == content for name, content in snapshots.items()),
    )
    result = {
        "source_head": ledger["source_head"],
        "input_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in snapshots.items()},
        "actual_requests": len(entries),
        "requested_samples": requested_samples,
        "processed_samples": len(samples),
        "ready": len(ready),
        "unconditional_ready_rate": ratio(len(ready), requested_samples),
        "first_json": json_n,
        "first_valid": valid_n,
        "first_attempts": len(first),
        "first_attempt_validation": validation,
        "usage": dict(totals),
        "reasoning_known": sum(reason_values),
        "reasoning_missing": missing_reason,
        "usage_missing": unknown_usage,
        "truncated": trunc,
        "timeouts": timeouts,
        "max_transport_latency_ms": max_ms,
        "sanity_failures": [c for c in sanity["checks"] if c["ok"] is False],
        "checks": checks,
        "passed": sum(c["ok"] for c in checks),
        "total": len(checks),
        "failures": [c for c in checks if not c["ok"]],
        "limitations": [
            "Arithmetic and production-validator replay, not independent human scoring.",
            "Completed and aborted batches retain requested-group denominator separately.",
            "Only sanitized shared evidence read; no private reasoning or credentials.",
        ],
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: result[k] for k in ("actual_requests", "ready", "passed", "total", "failures")},
            ensure_ascii=False,
        )
    )
    return bool(result["failures"])


if __name__ == "__main__":
    raise SystemExit(main())
