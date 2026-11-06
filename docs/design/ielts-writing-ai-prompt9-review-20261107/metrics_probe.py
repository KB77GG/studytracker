#!/usr/bin/env python3
"""Offline prompt .9 metrics/flat-schema review. No secrets or model calls.

Replays committed synthetic-sample formal answers and accounting metadata only.
All writes are disposable SQLite files or the explicitly requested --output JSON.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    sys.dont_write_bytecode = True
    def deny_network(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline probe forbids network")
    sys.addaudithook(deny_network)
    logging.disable(logging.CRITICAL)
    from tools.ielts_writing_ai import copytext, prompts, realcheck, realcheck_compare, review, web
    from tools.ielts_writing_ai.config import Settings
    from tools.ielts_writing_ai.llm import FakeClient, LLMError, LLMResult, parse_strict_json

    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    checks = {}
    observations = {}
    def check(name, actual):
        checks[name] = bool(actual)

    shared = repo / "docs/design/ielts-writing-ai-prompt8-high-20261106"
    old_data = json.loads((shared / "run_data.json").read_text(encoding="utf-8"))
    old_report = json.loads((shared / "report.json").read_text(encoding="utf-8"))
    old_calls = old_data["calls"]
    assert all("reasoning" not in c for c in old_calls), "Only sanitized formal-answer records are permitted"
    checks["fixture_has_nine_formal_answers"] = len(old_calls) == 9
    items = realcheck.load_samples("builtin")
    assert [s["id"] for s in items] == [s["id"] for s in old_data["samples"]]

    class Replay:
        provider, model = "deepseek", "deepseek-flash"
        def __init__(self, calls):
            self.source = copy.deepcopy(calls)
            self.requests = []
        def complete(self, messages, **kwargs):
            index = len(self.requests)
            source = self.source[index]
            self.requests.append({"messages": copy.deepcopy(messages), "options": copy.deepcopy(kwargs)})
            assert kwargs["context"]["attempt"] == source["attempt"]
            return LLMResult(source["text"], self.model, source["latency_ms"], copy.deepcopy(source["usage"]))

    class SyntheticFlat(FakeClient):
        def __init__(self, scenario):
            super().__init__()
            self.scenario = scenario
            self.requests = []
        def complete(self, messages, **kwargs):
            self.requests.append({"messages": copy.deepcopy(messages), "options": copy.deepcopy(kwargs)})
            attempt = kwargs["context"]["attempt"]
            if self.scenario == "transport_truncated":
                raise LLMError("truncated", usage={"prompt_tokens": 100, "completion_tokens": 16000, "total_tokens": 16100, "completion_tokens_details": {"reasoning_tokens": 15900}}, response_received=True, http_status=200)
            result = super().complete(messages, **kwargs)
            nested = json.loads(result.text)
            flat = {**nested.pop("criteria"), **nested}
            if self.scenario == "content_bad_then_good" and attempt == 0:
                flat["grammar"]["strengths"] = []
                flat["grammar"]["issues"] = []
            result.text = json.dumps(flat, ensure_ascii=False)
            if self.scenario == "always_json_bad" or (self.scenario == "json_bad_then_good" and attempt == 0):
                block = json.dumps(flat["grammar"], ensure_ascii=False)
                result.text = result.text.replace(block, block[:-1], 1)
            result.usage = {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300, "completion_tokens_details": {"reasoning_tokens": 75}}
            result.latency_ms = 10 + attempt
            return result

    with tempfile.TemporaryDirectory(prefix="iwa-p9-metrics-") as tmp_str:
        tmp = Path(tmp_str)
        def settings(name):
            return Settings(data_dir=tmp / name, job_mode="inline", evaluate_thinking="high", evaluate_thinking_max_tokens=16000, evaluate_thinking_timeout=300)
        replay = Replay(old_calls)
        data = realcheck.run(settings("replay-unused"), items, client=replay, kinds=("evaluate",), max_calls=14)
        report = realcheck.build_report(data)
        metric = report["kinds"]["evaluate"]
        for field in ("calls", "first_attempts", "first_attempt_json_ok", "first_attempt_valid", "final_ready", "final_failures", "latency_ms_p50", "latency_ms_p90", "tokens", "completion_tokens_max", "reasoning_tokens", "reasoning_tokens_known", "reasoning_unreported_calls", "reasoning_tokens_max", "truncated", "timeouts"):
            check(f"historical_replay.unchanged_{field}", metric[field] == old_report["kinds"]["evaluate"][field])
        check("historical_replay.all_usage_preserved", [c["usage"] for c in data["calls"]] == [c["usage"] for c in old_calls])
        check("historical_replay.all_answer_text_preserved", [c["text"] for c in data["calls"]] == [c["text"] for c in old_calls])
        check("historical_replay.all_transport_retries_disabled", all(r["options"]["retries"] == 0 for r in replay.requests))
        check("historical_replay.only_evaluation_high16000", all(c["kind"] == "evaluate" and c["thinking"] == "high" and c["max_tokens"] == 16000 for c in data["calls"]))
        diagnoses = {(p["sample"], p["attempt"]): p["problem"] for p in metric["json_problems"]}
        check("historical_replay.three_attempt_diagnoses", set(diagnoses) == {("t2-off-topic", 0), ("t2-under-length", 0), ("t2-under-length", 1)})
        check("historical_replay.first_rejections_only_two", metric["first_attempt_rejections"] == {"JSON 括号或结构错误": 2})
        check("historical_replay.off_topic_outside_priorities", "priorities 落在了 JSON 之外" in diagnoses[("t2-off-topic", 0)])
        check("historical_replay.both_short_nested_diagnoses", all("被写进了 criteria 里面" in diagnoses[("t2-under-length", n)] for n in (0, 1)))
        check("historical_replay.retry_receives_diagnosis", all("JSON 结构错误" in request["messages"][-1]["content"] for request in replay.requests if request["options"]["context"]["attempt"] == 1))
        result_by_id = {s["id"]: s for s in data["samples"]}
        failed = result_by_id["t2-under-length"]["generations"]["evaluate"]
        check("historical_replay.short_stays_failed_without_score", failed["status"] == "failed" and failed["error_code"] == "invalid_output" and failed["result"] is None)
        check("historical_replay.only_off_topic_recovers", result_by_id["t2-off-topic"]["generations"]["evaluate"]["status"] == "ready")
        markdown = realcheck.render_markdown(report)
        check("historical_replay.markdown_three_diagnoses", sum("JSON 结构错误：" in line for line in markdown.splitlines()) == 3)
        check("historical_replay.argument_partition", report["argument"]["returned"] == sum(report["argument"][k] for k in ("kept", "dropped", "duplicates", "over_limit")))
        check("historical_replay.good_comment_now_preserved", len(result_by_id["t2-good"]["generations"]["evaluate"]["result"]["argument"]["improvements"]) == 3)
        observations["historical_replay"] = {"calls": len(data["calls"]), "first_json_rate": metric["first_attempt_json_ok"], "first_valid_rate": metric["first_attempt_valid"], "final_ready_rate": metric["final_ready"], "tokens": metric["tokens"], "reasoning_tokens": metric["reasoning_tokens"], "diagnostics": metric["json_problems"], "argument": {k: report["argument"][k] for k in ("returned", "kept", "dropped", "duplicates", "over_limit")}, "statuses": {s["id"]: s["generations"]["evaluate"]["status"] for s in data["samples"]}}

        scenarios = {}
        for scenario, limit in (("valid", 2), ("json_bad_then_good", 2), ("content_bad_then_good", 2), ("always_json_bad", 2), ("always_json_bad", 1), ("transport_truncated", 2)):
            key = scenario + "_budget" + str(limit)
            client = SyntheticFlat(scenario)
            run_data = realcheck.run(settings(key), [items[0]], client=client, kinds=("evaluate",), max_calls=limit)
            run_report = realcheck.build_report(run_data)
            m = run_report["kinds"]["evaluate"]
            generation = run_data["samples"][0]["generations"]["evaluate"]
            expected = {
                "valid": (1, 1.0, 1.0, 1.0, 0),
                "json_bad_then_good": (2, 0.0, 0.0, 1.0, 1),
                "content_bad_then_good": (2, 1.0, 0.0, 1.0, 0),
                "always_json_bad": (limit, 0.0, 0.0, 0.0, limit),
                "transport_truncated": (1, 0.0, 0.0, 0.0, 0),
            }[scenario]
            actual = (m["calls"], m["first_attempt_json_ok"], m["first_attempt_valid"], m["final_ready"], len(m["json_problems"]))
            check(key + ".metrics", actual == expected)
            check(key + ".hard_budget", len(client.requests) == len(run_data["calls"]) <= limit)
            check(key + ".all_retry_usage_counted", m["tokens"]["completion_tokens"] == sum(c["usage"]["completion_tokens"] for c in run_data["calls"]))
            check(key + ".all_reasoning_counted", m["reasoning_tokens"] == sum(c["usage"]["completion_tokens_details"]["reasoning_tokens"] for c in run_data["calls"]))
            if generation["status"] != "ready":
                check(key + ".no_result_on_failure", generation["result"] is None)
            api_generation = {**generation, "id": 1, "kind": "evaluate", "created_at": None}
            api = web._generation_view(api_generation, run_data["samples"][0]["submission"])
            check(key + ".api_score_gate", (api["result"] is None and api["copy"] is None) if generation["status"] != "ready" else isinstance(api["result"]["criteria"], list) and bool(api["copy"]))
            scenarios[key] = {"calls": actual[0], "first_json_rate": actual[1], "first_content_rate": actual[2], "final_ready_rate": actual[3], "json_diagnostics": actual[4], "failure_code": generation.get("error_code"), "completion_tokens": m["tokens"]["completion_tokens"], "reasoning_tokens": m["reasoning_tokens"], "first_rejections": m["first_attempt_rejections"]}
        observations["synthetic_metrics"] = scenarios

        # Every successful historical task form must produce the unchanged consumer
        # contract. Browser code consumes this normalized API list, not model JSON.
        compatibility = []
        old_samples = {s["id"]: s for s in old_data["samples"]}
        for sample_id, sample in old_samples.items():
            source = next((c for c in reversed(old_calls) if c["sample"] == sample_id and parse_strict_json(c["text"]) is not None), None)
            if source is None:
                continue
            raw = parse_strict_json(source["text"])
            flat = {**raw["criteria"], **{k: v for k, v in raw.items() if k != "criteria"}}
            nested_result = review.normalize_evaluation(copy.deepcopy(raw), sample["submission"])
            flat_result = review.normalize_evaluation(copy.deepcopy(flat), sample["submission"])
            check(sample_id + ".flat_nested_normalized_equal", flat_result == nested_result)
            check(sample_id + ".criterion_list_contract", isinstance(flat_result["criteria"], list) and [c["key"] for c in flat_result["criteria"]] == ["task", "coherence", "lexical", "grammar"])
            check(sample_id + ".copy_text_equal", copytext.evaluation_text(flat_result, {}) == copytext.evaluation_text(nested_result, {}))
            pair = []
            for result in (flat_result, nested_result):
                candidate = {**sample, "generations": {"evaluate": {"status": "ready", "result": result}}}
                pair.append((realcheck._scores(candidate), realcheck_compare.sample_view({"calls": []}, candidate)))
            check(sample_id + ".scores_and_compare_equal", pair[0] == pair[1])
            flat_first = realcheck._first_attempt_problem("evaluate", json.dumps(flat, ensure_ascii=False), sample)
            check(sample_id + ".first_pass_flat_accepted", flat_first is None)
            both = {**flat, "criteria": raw["criteria"]}
            rejected = realcheck._first_attempt_problem("evaluate", json.dumps(both, ensure_ascii=False), sample)
            check(sample_id + ".mixed_forms_rejected", rejected is not None and "评分项只能出现一次" in rejected)
            compatibility.append({"sample": sample_id, "flat_and_nested_identical": flat_result == nested_result, "overall": flat_result["overall_band"], "ta_state": flat_result["criteria"][0]["state"], "mixed_form_rejection": rejected})
        observations["consumer_compatibility"] = compatibility
        prompt_notes = []
        for task in ("task1", "task2"):
            sample = next(s for s in old_data["samples"] if s["task_type"] == task)
            system = prompts.build_evaluate(sample["submission"], [])[0][0]["content"]
            prompt_notes.append({"task": task, "flat_model_shape": '"criteria":' not in system, "priorities_three_to_five_still_present": "...3-5" in system, "explanatory_schema_aliases_still_present": '"coherence": C' in system and '"overall_comment": str (Chinese)' in system})
        observations["prompt_design_notes"] = {"facts": prompt_notes, "classification": "Existing unimplemented design suggestions; not a newly reproduced correctness bug or proof of model quality."}

    output = {"source_head": head, "prompt_version": prompts.PROMPT_VERSION, "network_calls": 0, "actual_model_requests": 0, "student_materials_read": False, "private_reasoning_read": False, "checks": checks, "checks_passed": sum(checks.values()), "checks_total": len(checks), "failures": [name for name, value in checks.items() if not value], "observations": observations}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks_passed": output["checks_passed"], "checks_total": output["checks_total"], "failures": output["failures"]}, ensure_ascii=False))
    if output["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
