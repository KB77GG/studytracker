#!/usr/bin/env python3
"""Offline .10 metrics/fixture review; never calls a model or reads credentials.

Usage: python metrics_probe.py --repo /path/to/repo --output probe.json
Replays historical .9 formal replies under current validation. This cannot measure
the live effect of .10 prompts or establish why an earlier run performed worse.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


def differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            target = path + "/" + key
            if key not in a or key not in b:
                out.append(target)
            else:
                out.extend(differences(a[key], b[key], target))
        return out
    if isinstance(a, list) and isinstance(b, list):
        out = []
        for i in range(max(len(a), len(b))):
            target = path + "/" + str(i)
            if i >= len(a) or i >= len(b):
                out.append(target)
            else:
                out.extend(differences(a[i], b[i], target))
        return out
    return [] if a == b else [path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    sys.dont_write_bytecode = True

    def forbid(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline probe forbids network")

    sys.addaudithook(forbid)
    logging.disable(logging.CRITICAL)
    from tools.ielts_writing_ai import copytext, essay, prompts, realcheck, review
    from tools.ielts_writing_ai.llm import LLMError, LLMResult, parse_strict_json

    shared = repo / "docs/design/ielts-writing-ai-prompt9-high-20261107/continuation"
    fixture_path = repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261107_prompt9.json"
    paths = [fixture_path, shared / "run_data.json", shared / "report.json", shared / "raw_calls.jsonl"]
    original_bytes = {p: p.read_bytes() for p in paths}
    fixture = json.loads(original_bytes[fixture_path])
    data = json.loads(original_bytes[shared / "run_data.json"])
    original_report = json.loads(original_bytes[shared / "report.json"])
    raw_calls = [json.loads(line) for line in original_bytes[shared / "raw_calls.jsonl"].splitlines() if line.strip()]
    assert all(not c.get("reasoning") for c in raw_calls), "Sanitized formal replies only"
    calls = data["calls"]
    by_sample = {s["id"]: s for s in data["samples"]}
    checks, observations = {}, {}

    def check(key, value):
        checks[key] = bool(value)

    check("fixture.eight_shared_calls", len(raw_calls) == len(calls) == 8 and raw_calls == calls)
    check("fixture.seven_samples", set(fixture["submissions"]) == set(by_sample) and len(by_sample) == 7)
    check("fixture.eight_attempts", sum(len(v) for v in fixture["attempts"].values()) == 8)
    fixture_rows = []
    for sid, sample in by_sample.items():
        check(f"fixture.{sid}.submission_exact", fixture["submissions"][sid] == sample["submission"])
        selected = [c for c in calls if c["sample"] == sid]
        check(f"fixture.{sid}.attempt_count", len(selected) == len(fixture["attempts"][sid]))
        for n, (fx, call) in enumerate(zip(fixture["attempts"][sid], selected)):
            expected = {"text": call["text"], "error": call.get("error"),
                        "completion_tokens": call["usage"]["completion_tokens"],
                        "reasoning_tokens": call["reasoning_tokens"]}
            check(f"fixture.{sid}.{n}.exact_reply_and_accounting", fx == expected)
            fixture_rows.append({"sample": sid, "attempt": n,
                                 "formal_text_sha256": hashlib.sha256(fx["text"].encode()).hexdigest(),
                                 "formal_text_characters": len(fx["text"]),
                                 "error": fx["error"]})
    observations["fixture"] = fixture_rows

    class HistoricalClient:
        provider, model = "offline-replay", "deepseek-flash"

        def __init__(self, sample):
            self.available = [c for c in calls if c["sample"] == sample]
            self.consumed = 0
            self.messages = []
            self.options = []
            self.guard_rejections = 0

        def complete(self, messages, **options):
            self.messages.append(copy.deepcopy(messages))
            self.options.append(copy.deepcopy(options))
            if self.consumed >= len(self.available):
                self.guard_rejections += 1
                raise LLMError("call_budget", "Historical per-sample allocation is exhausted")
            call = self.available[self.consumed]
            self.consumed += 1
            assert options["context"]["attempt"] == call["attempt"]
            if not call["ok"]:
                raise LLMError(call["error"], usage=copy.deepcopy(call["usage"]),
                               response_received=call["response_received"], http_status=call["http_status"])
            return LLMResult(call["text"], call["model"], call["latency_ms"], copy.deepcopy(call["usage"]))

    settings = SimpleNamespace(evaluate_thinking="high", evaluate_thinking_max_tokens=16000,
                               evaluate_thinking_timeout=300, llm_temperature=.2)
    replay_data = copy.deepcopy(data)
    results, consumed, rejected_guards = {}, 0, 0
    for replay_sample in replay_data["samples"]:
        sid = replay_sample["id"]
        client = HistoricalClient(sid)
        generator = review.Generator(None, settings, client)
        submission = copy.deepcopy(replay_sample["submission"])
        before = copy.deepcopy(submission)
        error, result = None, None
        try:
            result, _ = generator._generate_valid("evaluate", submission, essay.split_sentences(submission["essay_text"]))
        except (LLMError, review.InvalidOutput) as exc:
            error = getattr(exc, "code", "invalid_output")
        previous = by_sample[sid]["generations"]["evaluate"]
        check(f"replay.{sid}.status", ("ready" if result else "failed") == previous["status"])
        check(f"replay.{sid}.failure_code", error == previous.get("error_code"))
        check(f"replay.{sid}.submission_unchanged", before == submission)
        check(f"replay.{sid}.budget_options", all(o["thinking"] == "high" and o["max_tokens"] == 16000 and o["timeout"] == 300 for o in client.options))
        consumed += client.consumed
        rejected_guards += client.guard_rejections
        change_paths = []
        if result:
            replay_sample["generations"]["evaluate"]["result"] = result
            change_paths = differences(previous["result"], result)
            old_scores = {c["key"]: c.get("band") for c in previous["result"]["criteria"]}
            new_scores = {c["key"]: c.get("band") for c in result["criteria"]}
            check(f"replay.{sid}.scores_unchanged", old_scores == new_scores and previous["result"]["overall_band"] == result["overall_band"])
            check(f"replay.{sid}.evidence_and_argument_accounting", previous["result"]["suggestions_removed"] == result["suggestions_removed"] and previous["result"]["argument"] == result["argument"])
            expected_paths = ["/length_notes"]
            if sid == "t1-no-image":
                expected_paths += ["/criteria/1/issues/0/suggestion", "/priorities/0", "/warnings/2"]
            check(f"replay.{sid}.only_expected_changes", sorted(change_paths) == sorted(expected_paths))
            normalized_again = review.normalize_evaluation(parse_strict_json(fixture["attempts"][sid][-1]["text"]), copy.deepcopy(submission))
            normalized_again["thinking"] = "high"
            check(f"replay.{sid}.repeat_normalization_stable", normalized_again == result)
        elif sid in {"t2-mid", "t2-strong"}:
            check(f"replay.{sid}.guard_blocks_extra_response", client.guard_rejections == 1)
            if sid == "t2-mid":
                check("replay.mid_retry_accurate_reason", "评分项 TR 写成了数字 7.0" in client.messages[-1][-1]["content"])
        results[sid] = {"status": "ready" if result else "failed", "error": error,
                        "responses_consumed": client.consumed, "guard_rejections": client.guard_rejections,
                        "length_notes": result.get("length_notes") if result else None,
                        "changed_paths": change_paths}
    check("replay.consumes_exact_eight_responses", consumed == 8)
    check("replay.exhausted_mid_strong_no_third", rejected_guards == 2)
    check("replay.saved_call_text_and_usage_unchanged", replay_data["calls"] == data["calls"])
    observations["replay"] = results

    report = realcheck.build_report(replay_data)
    unchanged_sections = ("connectivity", "evidence", "argument", "refine_rewrite", "sanity",
                          "tokens", "usage", "per_sample", "calibration", "teacher_findings")
    for key in unchanged_sections:
        check("report.unchanged_" + key, report[key] == original_report[key])
    new_kind, old_kind = report["kinds"]["evaluate"], original_report["kinds"]["evaluate"]
    for key in old_kind:
        if key != "first_attempt_rejections":
            check("report.unchanged_evaluate_" + key, new_kind[key] == old_kind[key])
    expected_rejections = copy.deepcopy(old_kind["first_attempt_rejections"])
    missing_tr = expected_rejections.pop("缺少评分项 TR")
    numeric_reason = "评分项 TR 写成了数字 7.0：每个评分项必须是包含 band、summary、strengths、issues 的对象"
    expected_rejections[numeric_reason] = missing_tr
    check("report.only_rejection_label_changes", new_kind["first_attempt_rejections"] == expected_rejections)
    observations["report"] = {"historical_prompt": original_report["prompt_version"],
                              "current_validator_prompt": prompts.PROMPT_VERSION,
                              "historical_calls": len(calls), "first_json": new_kind["first_attempt_json_ok"],
                              "first_content": new_kind["first_attempt_valid"], "final_ready": new_kind["final_ready"],
                              "tokens": new_kind["tokens"], "reasoning_tokens": new_kind["reasoning_tokens"],
                              "rejections": new_kind["first_attempt_rejections"],
                              "interpretation": "Historical .9 outputs replayed offline, not a live .10 run; first rates remain continuation-only, not the interrupted original full-batch rates."}

    task1_result = next(s for s in replay_data["samples"] if s["id"] == "t1-no-image")["generations"]["evaluate"]["result"]
    sub = fixture["submissions"]["t1-no-image"]
    total = essay.count_words(sub["essay_text"])
    last_count = essay.count_words(essay.split_paragraphs(sub["essay_text"])[-1])
    copied = copytext.evaluation_text(task1_result, {})
    check("length.task1_counts", (total, last_count, total-last_count) == (172, 23, 149))
    check("length.two_notes", task1_result["length_notes"] == 2)
    check("length.copy_has_both_notes", copied.count("约剩 149 词，低于 150 词下限") == 2)
    check("length.copy_has_warning", "有 2 条建议提到删去整段或整句" in copied)
    check("length.task1_not_assessable_preserved", task1_result["overall_band"] is None and task1_result["criteria"][0]["state"] == "not_assessable")
    observations["length_notes"] = {"before_words": total, "target_words": last_count,
                                    "after_words": total-last_count, "notes": task1_result["length_notes"],
                                    "copy_advice_mentions": copied.count("约剩 149 词"),
                                    "counts_are_advice_entries_not_distinct_deletions": True,
                                    "scores_original_and_report_metrics_unchanged": True}

    prompt_notes = []
    for task_type, visual in (("task2", True), ("task1", False), ("task1", True)):
        shape = prompts._root_schema(task_type, visual)
        example = prompts.evaluate_example(task_type, visual)
        key = f"{task_type}_{visual}"
        check("prompt."+key+".priorities_3to5", "priorities = [str (Chinese), ...3-5" in shape)
        check("prompt."+key+".three_example_priorities", len(example["priorities"]) == 3)
        check("prompt."+key+".nested_example_present", json.dumps(example, ensure_ascii=False) in shape and isinstance(example["criteria"], dict))
        prompt_notes.append({"task": task_type, "visual": visual, "priorities_rule_restored": True})
    observations["prompt"] = {"variants": prompt_notes,
                              "priorities_scope": "3–5 is restored in the prompt; the existing validator still permits fewer priorities. No new enforcement was claimed or added.",
                              "causality": "The .9 run coincided with bare-number/brace failures; these samples do not establish that flattening caused regression. This offline replay cannot establish that .10 improves model compliance."}
    check("inputs.shared_and_fixture_bytes_unchanged", all(p.read_bytes() == b for p,b in original_bytes.items()))
    output = {"source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
              "prompt_version": prompts.PROMPT_VERSION, "network_calls": 0, "actual_model_requests": 0,
              "reads_private_reasoning": False, "observations": observations, "checks": checks,
              "checks_passed": sum(checks.values()), "checks_total": len(checks),
              "failures": [k for k,v in checks.items() if not v]}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:output[k] for k in ("checks_passed", "checks_total", "failures")}, ensure_ascii=False))
    if output["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
