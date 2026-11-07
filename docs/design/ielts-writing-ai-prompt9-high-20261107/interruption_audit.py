#!/usr/bin/env python3
"""Offline audit of an interrupted, sanitized IELTS evaluation batch.

Usage: python interruption_audit.py --bundle SHARED_DIRECTORY --output audit.json
Only transport/interruption/provider-status and guard self-test records are read.
This does not contact the provider, resume a batch, read credentials or infer scores.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


EXPECTED_HEAD = "9b09562dad8b2e5f348ad8f9d649777543ef52d5"
EXPECTED_TOOLS = "f0e3cec234a5b3fb09e923be9cf649223efa793267771755ea89785e451039bc"
EXPECTED_SAMPLES = (
    "t2-weak", "t2-mid", "t2-good", "t2-strong", "t2-off-topic",
    "t2-under-length", "t1-no-image",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    bundle = args.bundle.resolve()
    assert "results" not in bundle.parts, "Private results/ must not be read"

    def deny_network(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline audit forbids network access")

    sys.addaudithook(deny_network)
    names = ("transport.json", "interruption.json", "provider-status.json",
             "runner-selftest.json", "runner-independent-audit.json")
    originals = {name: (bundle / name).read_bytes() for name in names}
    docs = {name: json.loads(value) for name, value in originals.items()}
    ledger = docs["transport.json"]
    interrupted = docs["interruption.json"]
    provider = docs["provider-status.json"]
    guards = [docs["runner-selftest.json"], docs["runner-independent-audit.json"]]
    responses = ledger["responses"]
    used = len(responses)
    count = Counter(r["sample"] for r in responses)
    remaining = 14 - used
    per_sample = {sid: {"already_attempted": count[sid], "remaining_max": 2 - count[sid],
                       "next_original_sample_attempt_index": count[sid]} for sid in EXPECTED_SAMPLES}
    http = Counter(str(r.get("http_status", "unknown")) for r in responses)
    checks = {}

    def check(name, value):
        checks[name] = bool(value)

    check("authorization.fixed_cap14", ledger["limit"] == interrupted["authorized_max_requests"] == 14)
    check("authorization.five_attempts_counted", used == ledger["request_attempts"] == interrupted["reserved_actual_attempts"] == 5)
    check("authorization.remaining9", remaining == interrupted["remaining_under_same_authorization"] == 9)
    check("authorization.cap_not_exceeded", used <= 14)
    check("authorization.sequence_numbers", [r["number"] for r in responses] == list(range(1, used + 1)))
    check("authorization.expected_sample_set", set(ledger["sample_counts"]) == set(EXPECTED_SAMPLES))
    check("authorization.per_sample_counts", dict(ledger["sample_counts"]) == {sid: count[sid] for sid in EXPECTED_SAMPLES})
    check("authorization.per_sample_at_most2", all(count[sid] <= 2 for sid in EXPECTED_SAMPLES))
    check("authorization.remaining_sample_cap_sum", sum(r["remaining_max"] for r in per_sample.values()) == remaining)
    check("authorization.first_attempts_only", all(r["attempt"] == 0 for r in responses))
    check("scope.high_evaluate_flash", ledger["mode"] == "high" and ledger["kind"] == "evaluate" and ledger["model"] == "deepseek-flash")
    check("scope.high16000_timeout300", all(r["thinking"] == "high" and r["max_tokens"] == 16000 and r["timeout"] == 300 for r in responses))
    check("scope.original_input_hashes", all(r["messages_sha256"] == ledger["initial_messages_sha256"][r["sample"]] for r in responses))
    check("source.head", ledger["source_head"] == interrupted["source_head"] == EXPECTED_HEAD)
    check("source.tools_unchanged", ledger["tools_sha256"] == ledger["business_sha256_before"] == interrupted["tools_sha256_after"] == EXPECTED_TOOLS)
    check("source.prompt9", ledger["prompt_version"] == "iwa-2026-11-06.9")
    check("source.guard_baseline", all(g["source_head"] == EXPECTED_HEAD and g["tools_sha256"] == EXPECTED_TOOLS for g in guards))
    check("transport.http500_three", http["500"] == interrupted["responses_http500"] == 3)
    check("transport.first_three_http_errors", all(r["status"] == "error" and r["http_status"] == 500 and r["error_type"] == "HTTPError" for r in responses[:3]))
    fourth = responses[3]
    check("transport.fourth_http200_metadata_unknown", fourth["http_status"] == 200 and fourth["response_metadata_unavailable"] is True and fourth["status"] == "received" and "usage" not in fourth and "finish_reason" not in fourth)
    check("transport.one_http200_unknown_completion", http["200"] == interrupted["response_http200_without_completion_metadata"] == 1)
    fifth = responses[4]
    check("transport.fifth_no_response_metadata", fifth["status"] == "sending" and "http_status" not in fifth and "usage" not in fifth and "finish_reason" not in fifth)
    check("transport.one_unknown_response", http["unknown"] == interrupted["inflight_interrupted_unknown_outcome"] == 1)
    check("interruption.exit130", interrupted["process_exit_code"] == 130)
    check("interruption.incomplete", ledger["completed"] is False)
    check("interruption.runner_disabled", interrupted["runner_disabled"] is True and all(g["paid_enabled"] is False for g in guards))
    check("accounting.no_provider_usage", all("usage" not in r for r in responses) and interrupted["provider_usage_reported"] is False)
    check("accounting.tokens_fees_unknown_not_zero", interrupted["token_usage"] is None and interrupted["cost"] is None)
    check("quality.no_artifacts", not any((bundle / name).exists() for name in ("run_data.json", "report.json", "report.md", "raw_calls.jsonl")))
    check("quality.no_evaluation_artifacts_claim", interrupted["completed_evaluations_available"] == 0 and interrupted["quality_assessment_possible"] is False)
    shared_ledger_hash = hashlib.sha256(originals["transport.json"]).hexdigest()
    # The exporter appended exactly one final newline to the source ledger.
    # Keep the exported-byte hash and the declared source hash separate.
    before_export_newline = originals["transport.json"][:-1] if originals["transport.json"].endswith(b"\n") else originals["transport.json"]
    no_final_newline_hash = hashlib.sha256(before_export_newline).hexdigest()
    check("ledger.source_hash_matches_without_export_newline", no_final_newline_hash == interrupted["ledger_sha256"])
    check("ledger.old_preserved", interrupted["ledger_retained_unchanged"] is True)
    check("guard.existing_ledger_refused", docs["runner-selftest.json"]["checks"]["old_ledger_refused"] is True and all(c["existing_ledger_refused"] for c in docs["runner-independent-audit.json"]["cases"]))
    check("guard.global_and_sample_cap_test_recorded", all(docs["runner-selftest.json"]["checks"][k] is True for k in ("cap14", "request15_blocked", "sample_cap2", "disk_reservation_before_send")))
    check("provider.incident_attribution_caveat", "does not independently prove" in provider["summary"])
    check("inputs.unchanged_after_audit", all((bundle / name).read_bytes() == value for name, value in originals.items()))

    output = {
        "source_head": EXPECTED_HEAD, "tools_sha256": EXPECTED_TOOLS,
        "prompt_version": ledger["prompt_version"], "audit_network_calls": 0,
        "reads_private_results": False, "reads_credentials": False,
        "actual_request_attempts": used, "original_authorized_limit": 14,
        "remaining_max_under_same_authorization": remaining,
        "per_sample_continuation_limits": per_sample,
        "transport": {"http_status_counts": dict(http), "http500_latency_ms": [r["latency_ms"] for r in responses[:3]],
                      "http200_completion_metadata": "unknown", "fifth_response_outcome": "unknown",
                      "process_exit_code": interrupted["process_exit_code"]},
        "token_usage": None, "reasoning_tokens": None, "fees": None,
        "first_json_rate": None, "first_content_pass_rate": None, "final_ready_rate": None,
        "scores": None, "completed_evaluation_artifacts_available": 0,
        "unknown_explanation": "No usage, formal replies or final evaluation artifacts survived the interrupted run. HTTP 200 alone does not prove a completed valid evaluation. Unknown is not zero.",
        "source_unchanged": checks["source.tools_unchanged"],
        "ledger_hashes": {"shared_exact_bytes": shared_ledger_hash,
                          "shared_without_one_export_newline": no_final_newline_hash,
                          "declared_source_bytes": interrupted["ledger_sha256"],
                          "export_difference": "The shared export adds one final newline; removing only that byte matches the declared source ledger SHA-256."},
        "provider_status_record": provider,
        "continuation_rule": "No new 14-request batch is authorized. Preserve this ledger; any later continuation must link prior five reservations, enforce total <=14 and per-original-sample <=2, keep source/model/prompt/scope unchanged, and make at most nine further HTTP attempts. This audit does not implement or launch continuation.",
        "checks": checks, "checks_passed": sum(checks.values()), "checks_total": len(checks),
        "mismatches": [key for key, value in checks.items() if not value],
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = ["# .9 / high 中断批次：独立账本审计", "",
        f"独立检查 **{output['checks_passed']}/{output['checks_total']}**；差异：{output['mismatches'] or '无'}。仅读取脱敏共享文件，审计网络请求 0。", "",
        "- 原授权最多 14 次；已计入 **5 次**，原授权内最多余 **9 次**。第 5 次即使没有响应状态，也已占用一次，不能退回预算。",
        "- 第 1–3 次均为 HTTP 500，耗时分别 15.165、15.144、15.134 秒。第 4 次 HTTP 200，但完成元信息不可得，既无 usage，也无 finish_reason。",
        "- 第 5 次在请求中途被 Ctrl-C 中断，进程退出码 130；账本仍为 sending，响应结果未知。不能声称该次必然未被服务端处理。",
        "- **token、reasoning token、费用均未知，不是 0。首轮 JSON 率、内容通过率、最终成功率和分数也未知。** 没有 run_data/report/raw_calls，不能编造正常验证报告；可用的完成评价文件为 0 不等于证明服务端生成成功数为 0。",
        f"- 源码 `{EXPECTED_HEAD}`；工具 SHA `{EXPECTED_TOOLS}` 前后相同。共享账本导出时多了一个末尾换行；仅去掉该字节后的 SHA 与 interruption 记录的原账本 SHA 一致。本审计未修改任一输入文件。",
        "- 离线复验通过与本次线上服务异常并不冲突。本批没有提供新的评分质量结论。", "",
        "官方状态记录在 2026-11-07 07:34 UTC 保存了 Monitoring / Partial Outage 公告（更新 07:11 UTC）。这佐证同一时段存在服务异常，不能独立证明每个请求的具体失败原因。本审计没有重新联网查询公告。来源：[DeepSeek 官方事件页](https://status.deepseek.com/incidents/7219383236287)。", "",
        "后续继续的预算约束：保留旧账本，必须有链接原账本的续跑守卫；累计全局不得超过 14 次，每个原样本累计不得超过 2 次。不能重置为新 14 次，也不能直接重跑拒绝旧账本的原 runner。本审计没有实现或启动续跑。", "",
        "| 原样本 | 已占用 | 后续最多 |", "|---|---:|---:|"]
    rows += [f"| {sid} | {r['already_attempted']} | {r['remaining_max']} |" for sid, r in per_sample.items()]
    args.output.with_suffix(".md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("checks_passed", "checks_total", "mismatches", "actual_request_attempts", "remaining_max_under_same_authorization")}, ensure_ascii=False))
    if output["mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
