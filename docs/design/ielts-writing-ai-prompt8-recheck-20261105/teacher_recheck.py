#!/usr/bin/env python3
"""Offline recheck of model comparison and teacher annotation metric fixes.

Only original synthetic text/FakeClient is used. No student files, .env, credentials,
network, or paid calls. Forked from the historical review probe, which is unchanged.
Corrected behavior and direct regression cases are now asserted.
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
        observations["failed_sample_denominator"] = {"requested_teacher_findings": 2, "generation_states": states, "report_metric": metrics, "unconditional_rate": .5, "report_lines": [line for line in md.splitlines() if "老师批注共" in line], "failed_sample_visible_in_teacher_metric": "failed" in metrics["samples"], "defect_observed": metrics["total"] == 1 and metrics["rate"] == 1.0}
        assert metrics["total"] == 2 and metrics["rate"] == .5
        assert metrics["evaluated_total"] == 1 and metrics["rate_evaluated"] == 1
        assert metrics["failed_samples"] == ["failed"]
        assert metrics["samples"]["failed"]["findings"][0]["coverage"] == "not_evaluated"
        assert "占全部 50%" in md and "只看评价成功的作文为 1/1" in md

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
        observations["disjoint_position_false_coverage"] = {"teacher_quote": school, "ai_quote": hospital, "character_offsets": offsets, "actual_character_ranges_overlap": False, "coverage": positional_coverage, "defect_observed": positional_coverage["covered"] == 1}
        assert positional_coverage["covered"] == 0
        assert positional_coverage["findings"][0]["coverage"] == "no"

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
        observations["annotation_order_misalignment"] = {"comparison_warnings": same_cmp["warnings"], "a_findings": a_cov["findings"], "b_findings": b_cov["findings"], "manual_rows": rows, "same_actual_input": same_cmp["conditions"]["a"]["evaluate_inputs"] == same_cmp["conditions"]["b"]["evaluate_inputs"], "expected_for_each_quote": "A and B should agree: q1 both covered; q2 neither covered.", "defect_observed": len(rows) == 2 and "A 覆盖：是 / B 覆盖：否" in rows[0] and "A 覆盖：否 / B 覆盖：是" in rows[1]}
        assert not same_cmp["warnings"]
        assert len(rows) == 2 and "A 覆盖：是 / B 覆盖：是" in rows[0] and "A 覆盖：否 / B 覆盖：否" in rows[1]

        # Annotation removal must not turn into a negative AI judgment.
        _, _, missing_dir = run("teacher-missing", [{**base, "teacher_findings": [findings[0]]}], thinking="off")
        missing_cmp = compare.compare(a_dir, missing_dir)
        missing_rows = [line for line in compare.render_manual_review(missing_cmp).splitlines() if line.startswith("| 老师批注 |")]
        assert any("老师批注不同" in warning for warning in missing_cmp["warnings"])
        assert len(missing_rows) == 2 and "A 覆盖：否 / B 覆盖：无此批注" in missing_rows[1]
        # Also check the reverse direction: a B-only annotation remains visible.
        reverse_cmp = compare.compare(missing_dir, a_dir)
        reverse_rows = [line for line in compare.render_manual_review(reverse_cmp).splitlines() if line.startswith("| 老师批注 |")]
        assert len(reverse_rows) == 2 and "A 覆盖：无此批注 / B 覆盖：否" in reverse_rows[1]
        _, _, no_notes_dir = run("teacher-no-notes", [base], thinking="off")
        no_notes_cmp = compare.compare(a_dir, no_notes_dir)
        no_notes_rows = [line for line in compare.render_manual_review(no_notes_cmp).splitlines() if line.startswith("| 老师批注 |")]
        assert len(no_notes_rows) == 2 and all("B 覆盖：无此批注" in line for line in no_notes_rows)
        observations["missing_annotations"] = {"warnings": missing_cmp["warnings"], "manual_rows": missing_rows, "reverse_manual_rows": reverse_rows, "all_missing_manual_rows": no_notes_rows, "passed": True}

        # Repeated short quotations do not reveal which occurrence the teacher or
        # AI intended. Count these as uncertain, not covered and not definitely new.
        repeated_essay = "Shared sentence. First detail.\n\nShared sentence. Second detail."
        relations = {
            "repeated_vs_one_occurrence": realcheck.span_relation(repeated_essay, "Shared sentence.", "Shared sentence. First detail."),
            "same_repeated_quote": realcheck.span_relation(repeated_essay, "Shared sentence.", "Shared sentence."),
            "unique_contained_quote": realcheck.span_relation(repeated_essay, "First detail", "Shared sentence. First detail."),
            "unique_disjoint_quotes": realcheck.span_relation(repeated_essay, "First detail", "Second detail"),
            "all_occurrences_inside_long_span": realcheck.span_relation(repeated_essay, "Shared sentence.", repeated_essay),
        }
        assert relations == {"repeated_vs_one_occurrence": "uncertain", "same_repeated_quote": "uncertain", "unique_contained_quote": "yes", "unique_disjoint_quotes": "no", "all_occurrences_inside_long_span": "yes"}
        repeated_sample = {"id": "repeated", "task_type": "task2", "submission": {"essay_text": repeated_essay}, "teacher_findings": [{"quote": "Shared sentence.", "note": "需澄清这一句的理由。"}], "generations": {"evaluate": {"status": "ready", "result": {"criteria": [{"key": "task", "issues": [{"quote": "Shared sentence. First detail."}]}]}}}}
        repeated_coverage = realcheck.teacher_coverage(repeated_sample)
        assert (repeated_coverage["covered"], repeated_coverage["uncertain"], repeated_coverage["total"]) == (0, 1, 1)
        assert repeated_coverage["findings"][0]["coverage"] == "uncertain"
        repeated_view = compare.sample_view({"calls": []}, repeated_sample)
        repeated_cmp = {"conditions": {"a": {"evaluate_thinking": "off"}, "b": {"evaluate_thinking": "high"}}, "samples": [{"a": repeated_view, "b": repeated_view}]}
        repeated_sheet = compare.render_manual_review(repeated_cmp)
        assert "A 覆盖：不确定 / B 覆盖：不确定" in repeated_sheet
        observations["repeated_quote_uncertainty"] = {"relations": relations, "coverage": repeated_coverage, "manual_uncertainty_label": True, "passed": True}

        # Multiple failed examples with unequal annotation counts. No successful
        # denominator may accidentally replace the full requested denominator.
        success_sample = copy.deepcopy(a_data["samples"][0])
        failed_two = copy.deepcopy(success_sample)
        failed_two.update(id="failed-two", teacher_findings=copy.deepcopy(findings))
        failed_two["generations"]["evaluate"] = {"status": "failed", "error_code": "timeout", "result": None}
        failed_three = copy.deepcopy(failed_two)
        failed_three.update(id="failed-three", teacher_findings=copy.deepcopy(findings) + [{"quote": q3, "note": "检查海龟句。"}])
        multi = realcheck._teacher_findings_metrics({"samples": [success_sample, failed_two, failed_three]})
        assert (multi["covered"], multi["total"], multi["rate"]) == (1, 7, .143)
        assert (multi["evaluated_total"], multi["rate_evaluated"]) == (2, .5)
        assert set(multi["failed_samples"]) == {"failed-two", "failed-three"}
        multi_md = "\n".join(realcheck._teacher_markdown(multi))
        assert "其中 2 篇评价没有成功，它们的 5 处批注无法对照" in multi_md
        all_failed = realcheck._teacher_findings_metrics({"samples": [failed_two, failed_three]})
        assert (all_failed["covered"], all_failed["total"], all_failed["rate"], all_failed["evaluated_total"], all_failed["rate_evaluated"]) == (0, 5, 0, 0, None)
        all_failed_md = "\n".join(realcheck._teacher_markdown(all_failed))
        assert "只看评价成功的作文为 0/0（—）" in all_failed_md
        failed_view = compare.sample_view({"calls": []}, failed_two)
        failed_cmp = {"conditions": {"a": {"evaluate_thinking": "off"}, "b": {"evaluate_thinking": "high"}}, "samples": [{"a": compare.sample_view({"calls": []}, success_sample), "b": failed_view}]}
        assert "B 覆盖：未评价" in compare.render_manual_review(failed_cmp)
        observations["multiple_failed_samples"] = {"all_requested": {k: multi[k] for k in ("covered", "total", "rate", "evaluated_total", "rate_evaluated", "failed_samples")}, "all_failed": {k: all_failed[k] for k in ("covered", "total", "rate", "evaluated_total", "rate_evaluated", "failed_samples")}, "failed_report_message": [line for line in multi_md.splitlines() if "老师批注共" in line], "manual_not_evaluated_label": True, "passed": True}

        controls["model_calls_are_fake"] = True

    result = {"source_head": source_head, "network_calls": 0, "actual_model_requests": 0, "student_materials_read": False, "positive_controls": controls, "observations": observations}
    result["confirmed_defects"] = [name for name, value in observations.items() if value.get("defect_observed")]
    assert not result["confirmed_defects"]
    result["passed"] = True
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        args.output.with_suffix(".md").write_text(
            "# 老师批注三项修复独立复核\n\n"
            + f"基线 `{source_head}`。全部合成样本，网络/模型请求 0，未读 Key 或学生材料。\n\n"
            + "结论：本范围通过，未发现阻断已授权内置样本实测的问题。\n\n"
            + "- 失败篇保留在全部请求分母，1/2=50%；成功口径另列1/1。\n"
            + "- 多失败：1/7=14.3%，成功口径1/2；全部失败0/5，成功口径未知而非100%。\n"
            + "- 不同段相似句不覆盖；唯一引文区间交叠才覆盖，重复引文只部分交叠标不确定。\n"
            + "- 批注倒序仍正确对齐；缺失及单边批注标无此批注；失败评价标未评价。\n"
            + "- 默认模型隔离、显式允许模型变化后的版本/实际消息/样本检查和归因标签仍通过。\n\n"
            + "旧探针与业务文件未修改。详细输入、返回值和断言结果见同名 JSON；此处不验证老师判断或评分准确度。\n",
            encoding="utf-8",
        )
    print(text)


if __name__ == "__main__":
    main()
