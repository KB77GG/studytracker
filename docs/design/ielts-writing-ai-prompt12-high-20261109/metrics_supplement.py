#!/usr/bin/env python3
"""Offline A-only supplement: group/source identity, omitted checks, usage inputs.

Reads only shared-evidence/A and tracked tool source. Never imports the paid
runner, reads private artifacts, or accesses a credential or model endpoint.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

HEAD = "817c4c4be172fa5603048a12085e60e4c99dfa38"
TOOLS_SHA = "f0178c720a8ecbe3796952122fb219453695ef93bd6ee073df4893f5d8ce39fd"
VERSION = "iwa-2026-11-10.12"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.evidence.resolve().parts[-2:] != ("shared-evidence", "A"):
        raise ValueError("Only public shared-evidence/A is authorized for this audit")

    def offline(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline audit forbids network")

    sys.addaudithook(offline)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo.resolve()))
    from metrics_audit import strict_object
    from tools.ielts_writing_ai import essay, prompts, realcheck, review

    names = ("run_data.json", "report.json", "transport.json", "formal_responses.json")
    snapshots = {n: (args.evidence / n).read_bytes() for n in names}
    data, report, ledger, formal = [json.loads(snapshots[n]) for n in names]
    checks = []

    def check(name, actual, expected=True):
        checks.append(
            {"name": name, "ok": actual == expected, "actual": actual, "expected": expected}
        )

    def git(*command):
        return subprocess.check_output(["git", *command], cwd=args.repo)

    check("source_current_head", git("rev-parse", "HEAD").decode().strip(), HEAD)
    check("source_current_clean", git("status", "--porcelain").decode(), "")
    paths = git("ls-files", "tools/ielts_writing_ai").splitlines()
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path + b"\0" + (args.repo / os.fsdecode(path)).read_bytes())
    check("source_current_tools_sha", digest.hexdigest(), TOOLS_SHA)
    check("source_prompt_version", prompts.PROMPT_VERSION, VERSION)
    for source, obj in (
        ("ledger", ledger),
        ("data_audit", data["audit"]),
        ("report_audit", report["audit"]),
    ):
        check(source + ".group", obj.get("group"), "A")
        check(source + ".source_head", obj.get("source_head"), HEAD)
        check(source + ".tools_sha", obj.get("tools_sha256"), TOOLS_SHA)
        check(source + ".limit", obj.get("limit"), 14)
    check("ledger.completed", ledger.get("completed"), True)
    check("ledger.circuit", ledger.get("circuit"), None)
    check("ledger.total_limit", ledger.get("total_limit"), 16)
    check("ledger.teacher_hash", ledger.get("teacher_file_sha256"), None)
    for key in ("business_sha256_before", "business_sha256_after"):
        check(key, ledger.get(key), TOOLS_SHA)
    check("ledger.prompt_version", ledger.get("prompt_version"), VERSION)
    check("report.prompt_version", report.get("prompt_version"), VERSION)
    check(
        "report.model",
        (report.get("provider"), report.get("model")),
        ("deepseek", "deepseek-flash"),
    )
    check("entries_group", {e.get("group") for e in ledger["responses"]} == {"A"})

    builtin = realcheck.load_samples("builtin")
    samples = data["samples"]
    by_id = {s["id"]: s for s in samples}
    check("builtin_sample_order", [s["id"] for s in samples], [s["id"] for s in builtin])
    for item in builtin:
        sample = by_id[item["id"]]
        text = essay.normalize_newlines(item["essay"]).strip()
        expected = {
            "task_type": item["task_type"],
            "prompt_text": item["prompt"].strip(),
            "essay_text": text,
            "word_count": essay.count_words(text),
            "target_band": float(item.get("target_band") or 7.0),
            "image_status": "none",
            "image_error": None,
            "image_description": None,
        }
        check("builtin_submission." + item["id"], sample["submission"], expected)
        check("builtin_expect." + item["id"], sample.get("expect") or {}, item.get("expect") or {})
        check("builtin_level." + item["id"], sample.get("level"), item.get("level"))
        check(
            "no_teacher." + item["id"],
            not sample.get("teacher") and not sample.get("teacher_findings"),
        )
        messages, _ = prompts.build_evaluate(expected, essay.split_sentences(text))
        fingerprint = hashlib.sha256(
            json.dumps(messages, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        # Serialization is intentionally reproduced independently of _messages_sha.
        check(
            "initial_messages." + item["id"],
            ledger["initial_messages_sha256"][item["id"]],
            fingerprint,
        )

    task2_calls = [
        c
        for c in data["calls"]
        if c["kind"] == "evaluate" and c.get("ok") and by_id[c["sample"]]["task_type"] == "task2"
    ]
    rejection_details = []
    argument_rejections = 0
    for call in task2_calls:
        raw = strict_object(call.get("text"))
        error = "invalid_json" if raw is None else None
        if raw is not None:
            try:
                review.normalize_evaluation(
                    copy.deepcopy(raw), copy.deepcopy(by_id[call["sample"]]["submission"])
                )
            except Exception as exc:
                error = str(exc)
        argument_rejections += bool(error and "论证结构" in error)
        if error:
            rejection_details.append(
                {"sample": call["sample"], "attempt": call["attempt"], "problem": error}
            )
    check("argument.evaluate_attempts", report["argument"]["evaluate_attempts"], len(task2_calls))
    check(
        "argument.attempts_rejected_for_argument",
        report["argument"]["attempts_rejected_for_argument"],
        argument_rejections,
    )

    # Build the required set of checks from sample expectations, independently of
    # report._sanity; checking existing rows alone misses a silently omitted row.
    expected_rows = []
    unavailable = []
    for sample in samples:
        exp, sid = sample.get("expect") or {}, sample["id"]
        generation = sample["generations"]["evaluate"]
        result = generation.get("result") or {}
        if not exp:
            continue
        if generation["status"] != "ready":
            expected_rows.append((sid, "评价已生成"))
            unavailable.append({"sample": sid, "expectations_not_evaluated": list(exp)})
            continue
        for key, label in (
            ("overall_min", "总分 ≥"),
            ("overall_max", "总分 ≤"),
            ("task_max", "TR ≤"),
        ):
            if key in exp:
                expected_rows.append((sid, label))
        if "task_max" in exp:
            expected_rows.append((sid, "离题样本："))
        if exp.get("word_warning"):
            expected_rows.append((sid, "有字数不足提示"))
        argkeys = (
            "argument_max_problems",
            "argument_min_problems",
            "argument_forbid",
            "argument_any_of",
            "argument_position",
        )
        if any(k in exp for k in argkeys):
            if not result.get("argument"):
                expected_rows.append((sid, "有论证结构分析"))
            else:
                for key, label in zip(
                    argkeys,
                    ("论证问题 ≤", "论证问题 ≥", "不应出现 ", "应标出 ", "找到可核实的立场句"),
                    strict=True,
                ):
                    if key in exp and (key != "argument_position" or exp[key]):
                        expected_rows.append((sid, label))
        if "consistency_min" in exp:
            expected_rows.append((sid, "指出文内数据矛盾"))
        if exp.get("not_assessable"):
            expected_rows.append((sid, "缺图 TA / 总分不可评"))
    levels = [s for s in samples if s.get("level") is not None]
    all_level_scores = all(
        (s["generations"]["evaluate"].get("result") or {}).get("overall_band") is not None
        for s in levels
    )
    if len(levels) >= 2 and all_level_scores:
        expected_rows += [("分级样本", "总分随水平不降"), ("分级样本", "最强与最弱相差")]
    else:
        unavailable.append(
            {
                "sample": "分级样本",
                "expectations_not_evaluated": ["总分随水平不降", "最强与最弱相差 ≥ 1.5"],
            }
        )
    rows = report["sanity"]["checks"]
    check("sanity_expected_row_count", len(rows), len(expected_rows))
    for sid, prefix in expected_rows:
        matching = [r for r in rows if r["sample"] == sid and r["check"].startswith(prefix)]
        check("sanity_required." + sid + "." + prefix, len(matching), 1)

    usage = Counter()
    formal_map = {f["number"]: f for f in formal}
    for entry in ledger["responses"]:
        u = entry.get("usage") or {}
        check("formal_usage." + str(entry["number"]), formal_map[entry["number"]].get("usage"), u)
        hit, miss = u.get("prompt_cache_hit_tokens"), u.get("prompt_cache_miss_tokens")
        check("cache_accounting." + str(entry["number"]), hit + miss, u["prompt_tokens"])
        check(
            "cache_detail." + str(entry["number"]),
            u.get("prompt_tokens_details", {}).get("cached_tokens"),
            hit,
        )
        reasoning = u.get("completion_tokens_details", {}).get("reasoning_tokens")
        check(
            "reasoning_within_output." + str(entry["number"]),
            0 <= reasoning <= u["completion_tokens"],
        )
        check(
            "total_tokens." + str(entry["number"]),
            u["total_tokens"],
            u["prompt_tokens"] + u["completion_tokens"],
        )
        usage.update(
            input_cache_hit=hit,
            input_cache_miss=miss,
            output=u["completion_tokens"],
            reasoning=reasoning,
            non_reasoning_output=u["completion_tokens"] - reasoning,
        )
    check(
        "input_files_unchanged",
        all((args.evidence / n).read_bytes() == raw for n, raw in snapshots.items()),
    )
    answer = {
        "group": "A",
        "source_head": HEAD,
        "tools_sha256": digest.hexdigest(),
        "input_sha256": {n: hashlib.sha256(raw).hexdigest() for n, raw in snapshots.items()},
        "checks": checks,
        "passed": sum(c["ok"] for c in checks),
        "total": len(checks),
        "failures": [c for c in checks if not c["ok"]],
        "price_inputs_tokens": dict(usage),
        "started_at_utc": data["started_at"],
        "task2_attempt_rejections": rejection_details,
        "sanity_checks_unavailable": unavailable,
        "limitations": [
            "A only; B and its private materials were not inspected.",
            "Usage is provider-reported; no invoice was accessed.",
            "No independent human rescoring; quotation and accounting checks do not prove judgment accuracy.",
        ],
    }
    args.output.write_text(json.dumps(answer, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: answer[k] for k in ("passed", "total", "failures", "price_inputs_tokens")},
            ensure_ascii=False,
        )
    )
    return bool(answer["failures"])


if __name__ == "__main__":
    raise SystemExit(main())
