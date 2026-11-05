#!/usr/bin/env python3
"""Offline review of model comparison and teacher annotation metrics.

Only original synthetic text/FakeClient is used. No student files, .env, credentials,
network, or paid calls. Defect observations are recorded rather than asserted as
correct behavior; positive controls and fixture validity are asserted.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))

    def no_network(event, _args):
        if event == "socket.connect":
            raise RuntimeError("Offline probe forbids network connections")

    sys.addaudithook(no_network)
    from tools.ielts_writing_ai import realcheck, realcheck_compare as compare
    from tools.ielts_writing_ai.config import Settings
    from tools.ielts_writing_ai.llm import FakeClient, LLMError

    source_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    observations = {}
    controls = {}
    q1 = "Urban tram services reduce traffic congestion during commuting hours."
    q2 = "Volcanic rocks contain minerals beneath distant mountains."
    q3 = "Marine turtles consume algae near tropical reefs."
    base = {"id": "synthetic-one", "task_type": "task2", "prompt": "Should governments invest more in urban transport?", "essay": " ".join((q1, q2, q3))}
    findings = [{"quote": q1, "note": "检查交通结论的依据。"}, {"quote": q2, "note": "这一句偏离交通题目。"}]

    class NamedClient(FakeClient):
        def __init__(self, model="offline-A", provider="deepseek", fail_second=False):
            super().__init__(model=model)
            self.provider = provider
            self.fail_second = fail_second
            self.call_count = 0

        def complete(self, messages, **kwargs):
            self.call_count += 1
            if self.fail_second and self.call_count == 2:
                raise LLMError("http_500", "Synthetic failure", response_received=True, http_status=500)
            result = super().complete(messages, **kwargs)
            result.usage = {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
            return result

    with tempfile.TemporaryDirectory(prefix="iwa-prompt8-compare-") as temp:
        tmp = Path(temp)

        def run(name, items, *, client=None, thinking="off"):
            # Explicit settings bypass all env/config loading.
            client = client or NamedClient()
            settings = Settings(data_dir=tmp / (name + "-unused"), job_mode="inline", evaluate_thinking=thinking, llm_provider=client.provider, llm_model=client.model)
            source = tmp / (name + ".jsonl")
            source.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in items), encoding="utf-8")
            loaded = realcheck.load_samples(str(source))
            data = realcheck.run(settings, loaded, client=client, kinds=("evaluate",), max_calls=6)
            report = realcheck.build_report(data)
            assert report["provider"] == client.provider and report["model"] == client.model
            directory = tmp / name
            realcheck.write_report(data, report, directory)
            return data, report, directory

        annotated = {**base, "teacher_findings": findings}
        a_data, a_report, a_dir = run("model-a", [annotated], thinking="high")
        b_data, b_report, b_dir = run("model-b", [annotated], client=NamedClient("offline-B", "qwen"), thinking="off")
        assert a_data["samples"][0]["generations"]["evaluate"]["status"] == "ready"
        default_rejection = None
        try:
            compare.compare(a_dir, b_dir)
        except compare.CompareError as exc:
            default_rejection = str(exc)
        assert default_rejection and "模型不同" in default_rejection and "服务商不同" in default_rejection
        allowed = compare.compare(a_dir, b_dir, allow_model_change=True)
        assert any("对照的是两个模型" in w for w in allowed["warnings"])
        assert any("不能单独归因" in w for w in allowed["warnings"])
        rendered, sheet = compare.render_markdown(allowed), compare.render_manual_review(allowed)
        assert all(name in rendered and name in sheet for name in ("offline-A", "offline-B"))
        cond_a = compare.conditions(compare.load_run(a_dir))
        cond_b = compare.conditions(compare.load_run(b_dir))
        versions = copy.deepcopy(cond_b)
        versions["prompt_version"] = "deliberately-different-prompt"
        version_errors, _ = compare.check_same_conditions(cond_a, versions, allow_model_change=True)
        inputs = copy.deepcopy(cond_b)
        inputs["evaluate_inputs"][base["id"]] = "different-actual-message-sha"
        input_errors, _ = compare.check_same_conditions(cond_a, inputs, allow_model_change=True)
        sample_change = copy.deepcopy(cond_b)
        sample_change["samples"][base["id"]] = "different-sample-fingerprint"
        sample_errors, _ = compare.check_same_conditions(cond_a, sample_change, allow_model_change=True)
        assert any("提示词版本不同" in error for error in version_errors)
        assert any("实际发送给评价模型的输入不同" in error for error in input_errors)
        assert any("题目、作文或题图识别结果不同" in error for error in sample_errors)
        controls["model_change"] = {"default_rejection": default_rejection, "allowed_warnings": allowed["warnings"], "both_model_labels_in_report_and_manual_sheet": True, "changed_version_errors": version_errors, "changed_input_errors": input_errors, "changed_sample_errors": sample_errors}

        # A clean first success then a failed second sample: the requested annotation
        # denominator must not be confused with the successful-generation denominator.
        two = [{**base, "id": "success", "teacher_findings": [findings[0]]}, {**base, "id": "failed", "teacher_findings": [findings[0]]}]
        fail_data, fail_report, fail_dir = run("one-failed", two, client=NamedClient(fail_second=True))
        states = {s["id"]: s["generations"]["evaluate"]["status"] for s in fail_data["samples"]}
        assert states == {"success": "ready", "failed": "failed"}
        assert len(fail_data["calls"]) == 2 and fail_data["calls"][1]["error"] == "http_500"
        metrics = fail_report["teacher_findings"]
        assert metrics["covered"] == 1  # The successful fixture has a real overlapping quote.
        md = (fail_dir / "report.md").read_text(encoding="utf-8")
        observations["failed_sample_denominator"] = {"requested_teacher_findings": 2, "generation_states": states, "report_metric": metrics, "unconditional_rate": .5, "report_lines": [line for line in md.splitlines() if "老师批注的" in line], "failed_sample_visible_in_teacher_metric": "failed" in metrics["samples"], "defect_observed": metrics["total"] == 1 and metrics["rate"] == 1.0, "priority": "P2", "impact": "Coverage silently excludes failed evaluations and can display 100% for one success and one failed annotated sample."}

        # Two genuinely distinct positions with many common words: token overlap is
        # not a location overlap, even though both quotes are verbatim in the essay.
        school = "The school is in the city and it needs repairs."
        hospital = "The hospital is in the village and it needs doctors."
        overlap_sample = {"id": "disjoint-positions", "task_type": "task2", "submission": {"essay_text": school + "\n\n" + hospital}, "teacher_findings": [{"quote": school, "note": "检查学校修缮主张。"}], "generations": {"evaluate": {"status": "ready", "result": {"criteria": [{"key": "task", "issues": [{"quote": hospital, "comment": "检查医院主张。"}]}]}}}}
        essay = overlap_sample["submission"]["essay_text"]
        offsets = {"teacher": [essay.index(school), essay.index(school) + len(school)], "ai": [essay.index(hospital), essay.index(hospital) + len(hospital)]}
        assert offsets["teacher"][1] < offsets["ai"][0]
        positional_coverage = realcheck.teacher_coverage(overlap_sample)
        controls["exact_contained_span_overlaps"] = realcheck.spans_overlap(school, "it needs repairs")
        controls["unrelated_words_do_not_overlap"] = not realcheck.spans_overlap(q2, q3)
        assert controls["exact_contained_span_overlaps"] and controls["unrelated_words_do_not_overlap"]
        observations["disjoint_position_false_coverage"] = {"teacher_quote": school, "ai_quote": hospital, "character_offsets": offsets, "actual_character_ranges_overlap": False, "coverage": positional_coverage, "defect_observed": positional_coverage["covered"] == 1, "priority": "P2", "impact": "The metric claims the same essay position was covered although the teacher and AI selected different paragraphs."}

        # The annotations are not model input, so merely reordering them keeps
        # messages identical; the comparison must still align labels by identity.
        reordered = {**base, "teacher_findings": list(reversed(findings))}
        r_data, r_report, r_dir = run("teacher-reordered", [reordered], thinking="off")
        same_cmp = compare.compare(a_dir, r_dir)
        a_cov = same_cmp["samples"][0]["a"]["teacher_coverage"]
        b_cov = same_cmp["samples"][0]["b"]["teacher_coverage"]
        assert [r["covered"] for r in a_cov["findings"]] == [True, False]
        assert [r["covered"] for r in b_cov["findings"]] == [False, True]
        rows = [line for line in compare.render_manual_review(same_cmp).splitlines() if line.startswith("| 老师批注 |")]
        observations["annotation_order_misalignment"] = {"comparison_warnings": same_cmp["warnings"], "a_findings": a_cov["findings"], "b_findings": b_cov["findings"], "manual_rows": rows, "same_actual_input": same_cmp["conditions"]["a"]["evaluate_inputs"] == same_cmp["conditions"]["b"]["evaluate_inputs"], "expected_for_each_quote": "A and B should agree: q1 both covered; q2 neither covered.", "defect_observed": len(rows) == 2 and "A 覆盖：是 / B 覆盖：否" in rows[0] and "A 覆盖：否 / B 覆盖：是" in rows[1], "priority": "P2", "impact": "Reordering otherwise identical teacher annotations makes the manual A/B sheet claim a model difference that does not exist."}

        controls["model_calls_are_fake"] = True

    result = {"source_head": source_head, "network_calls": 0, "actual_model_requests": 0, "student_materials_read": False, "positive_controls": controls, "observations": observations}
    result["confirmed_defects"] = [name for name, value in observations.items() if value.get("defect_observed")]
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
