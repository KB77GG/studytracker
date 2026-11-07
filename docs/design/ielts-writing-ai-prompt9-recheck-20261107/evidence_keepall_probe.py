#!/usr/bin/env python3
"""Offline .9 keep-all evidence recheck, boundary and comment-alias review.

Only reads committed synthetic .8 formal answers; no credentials, private reasoning,
model calls, files from private results, or business mutations. Exit 1 means a
recorded desired-behaviour check failed, not that the harness could not run.
"""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai import copytext, review

    bundle = repo / "docs/design/ielts-writing-ai-prompt8-high-20261106"
    data_path, raw_path = bundle / "run_data.json", bundle / "raw_calls.jsonl"
    data = json.loads(data_path.read_text())
    samples = {s["id"]: s for s in data["samples"]}
    # Access only the formal-response text from the already redacted shared file.
    calls = [json.loads(line) for line in raw_path.read_text().splitlines()]
    raw = {
        sid: json.loads(next(c["text"] for c in calls if c["sample"] == sid))
        for sid in ("t1-no-image", "t2-good", "t2-strong")
    }
    checks, cases = [], []

    def check(name, condition, details=None):
        checks.append({"name": name, "passed": bool(condition), "details": details})

    def normalize(sid, value):
        output = review.normalize_evaluation(copy.deepcopy(value), samples[sid]["submission"])
        return output, copytext.evaluation_text(output, {})

    def flat(value):
        return {**value["criteria"], **{k: v for k, v in value.items() if k != "criteria"}}

    # Reattribute the old issue from raw answer -> historical normalization -> new one.
    t1raw = raw["t1-no-image"]
    source_cmp = next(c for c in t1raw["comparisons"] if c["holds"] is False)
    historical = samples["t1-no-image"]["generations"]["evaluate"]["result"]
    result, copied = normalize("t1-no-image", t1raw)
    current = result["consistency_issues"][0]
    old_issue = historical["consistency_issues"][0]
    required = {"about 75%", "nearly 80%"}
    check("raw_real_answer_included_eight_figures_and_decisive_pair", len(source_cmp["figures"]) == 8 and required <= set(source_cmp["figures"]))
    check("historical_normalized_list_is_raw_first_three", old_issue["figures"] == source_cmp["figures"][:3])
    old_source = subprocess.check_output(["git", "show", "76214fe2:tools/ielts_writing_ai/review.py"], cwd=repo, text=True)
    check("old_source_proves_first_three_truncation", '"figures": figures[:3]' in old_source)
    check("current_real_output_keeps_decisive_pair", required <= set(current["figures"]), current)
    check("current_real_copy_keeps_all_verified_figures", "对照：" + "；".join(f"“{v}”" for v in source_cmp["figures"]) in copied)
    flat_result, flat_copy = normalize("t1-no-image", flat(t1raw))
    check("flat_and_nested_real_task1_outputs_identical", result == flat_result and copied == flat_copy)
    attribution = {
        "raw_model_comparison": source_cmp,
        "old_normalized_issue": old_issue,
        "new_normalized_issue": current,
        "correction": "原模型返回8个数，含75/80；旧程序 figures[:3] 丢掉关键2020证据。主要原因是程序截断，不能归为模型只选择了错年数字。",
    }

    # Natural adjacent case: the same true explanation includes all four old-year
    # values before explaining the decisive new-year contradiction.
    expanded_comment = (
        "2000年A的70%高于B的55%、C的40%和D的15%；"
        "但2020年C的80%高于A的75%，所以both years不成立。"
    )
    variant = copy.deepcopy(t1raw)
    entry = next(c for c in variant["comparisons"] if c["holds"] is False)
    entry["comment"] = expanded_comment
    changed, changed_copy = normalize("t1-no-image", variant)
    changed_issue = changed["consistency_issues"][0]
    evidence_lines = [line.strip() for line in changed_copy.splitlines() if line.strip().startswith("对照：")]
    check("expanded_correct_comment_keeps_both_decisive_figures", required <= set(changed_issue["figures"]), changed_issue)
    check("expanded_correct_comment_copy_keeps_both_decisive_figures", bool(evidence_lines) and all(value in evidence_lines[0] for value in required), evidence_lines)
    counterexample = {
        "change": "只展开原正确comment，补出2000另外三国数值；原稿、claim、8个figures、评分全部不变。",
        "raw_comparison": entry,
        "normalized_issue": changed_issue,
        "copy_evidence_lines": evidence_lines,
        "correct_comment_still_visible": expanded_comment in changed_copy,
        "impact": "旧缺陷复验：应完整保留8个已核实数字，包含决定2020矛盾的75/80；本轮payload和复制均已做到。",
        "scope": "上一轮真实8数输入的展开comment变体；本轮只修改已过时的最多4条约定，保留两项关键数字完整性正确行为断言。",
        "source_lines": ["tools/ielts_writing_ai/review.py:242-260", "tools/ielts_writing_ai/copytext.py:149-151", "tools/ielts_writing_ai/static/iwa.js:568-571"],
    }
    # Positive controls: obey four-figure contract, or rank decisive evidence first.
    for name, selected in (
        ("four_candidates", ["around 70%", "roughly 55%", "about 75%", "nearly 80%"]),
        ("decisive_candidates_first", ["about 75%", "nearly 80%", *source_cmp["figures"]]),
    ):
        value = copy.deepcopy(variant)
        next(c for c in value["comparisons"] if c["holds"] is False)["figures"] = selected
        out, text = normalize("t1-no-image", value)
        got = out["consistency_issues"][0]["figures"]
        check(name + "_keeps_pair_in_output_and_copy", required <= set(got) and all(f'“{v}”' in text for v in required), got)
        check(name + "_all_unique_candidates_retained_in_order", got == list(dict.fromkeys(selected)))
    no_match = copy.deepcopy(t1raw)
    next(c for c in no_match["comparisons"] if c["holds"] is False)["comment"] = "这一排名说法与后面的数据矛盾。"
    fallback, _ = normalize("t1-no-image", no_match)
    check("no_numeric_match_still_keeps_all_verified_figures", fallback["consistency_issues"][0]["figures"] == source_cmp["figures"])

    # Real good output: all three real quotes/advice fields must survive aliasing.
    good, good_copy = normalize("t2-good", raw["t2-good"])
    original_improvements = raw["t2-good"]["argument"]["improvements"]
    check("real_good_all_three_aliases_keep_exact_quote_and_advice", good["argument"]["improvements"] == [{"quote": i["quote"], "suggestion": i["comment"]} for i in original_improvements])
    check("real_good_copy_has_all_three_advice_texts", all(i["comment"] in good_copy for i in original_improvements))
    check("real_good_no_longer_drops_three_valid_improvements", good["argument"]["dropped"] == 0 and good["argument"]["returned"] == good["argument"]["kept"] == 9)
    good_flat, good_flat_copy = normalize("t2-good", flat(raw["t2-good"]))
    check("flat_and_nested_real_good_identical", good == good_flat and good_copy == good_flat_copy)

    # Full normalization and copy, not only the helper. Base has 1 position + 5 paragraphs.
    quote = original_improvements[0]["quote"]
    safe = "可补一句解释已有机制，并保留原文的限定立场。"
    second_safe = "可以保留现有论证，只把表达写得更清楚。"
    unsafe = "建议加入调查显示80%的乘客支持公交这一证据。"
    missing = object()
    specs = [
        ("comment_only_safe", missing, safe, quote, safe, 0),
        ("empty_suggestion_safe_comment", "", safe, quote, safe, 0),
        ("whitespace_suggestion_safe_comment", "   ", safe, quote, safe, 0),
        ("null_suggestion_safe_comment", None, safe, quote, safe, 0),
        ("list_suggestion_safe_comment", [], safe, quote, safe, 0),
        ("object_suggestion_safe_comment", {"bad": "type"}, safe, quote, safe, 0),
        ("integer_suggestion_safe_comment", 7, safe, quote, safe, 0),
        ("boolean_suggestion_safe_comment", True, safe, quote, safe, 0),
        ("both_valid_suggestion_wins", safe, second_safe, quote, safe, 0),
        ("safe_suggestion_unsafe_comment_unused", safe, unsafe, quote, safe, 0),
        ("unsafe_suggestion_safe_comment_no_revival", unsafe, safe, quote, None, 1),
        ("both_unsafe_removed_once", unsafe, unsafe, quote, None, 1),
        ("unsafe_comment_only_filtered", missing, unsafe, quote, None, 1),
        ("empty_suggestion_unsafe_comment_filtered", "", unsafe, quote, None, 1),
        ("wrong_type_suggestion_unsafe_comment_filtered", [], unsafe, quote, None, 1),
        ("comment_empty_no_advice", missing, "", quote, None, 0),
        ("comment_null_rejected", missing, None, quote, None, 0),
        ("comment_list_rejected", missing, [safe], quote, None, 0),
        ("comment_object_rejected", missing, {"suggestion": safe}, quote, None, 0),
        ("comment_number_rejected", missing, 80, quote, None, 0),
        ("comment_boolean_rejected", missing, True, quote, None, 0),
        ("bad_quote_comment_not_adopted", missing, safe, "This sentence does not occur in the essay.", None, 0),
        ("real_quote_with_invented_suffix_rejected", missing, safe, quote + " (invented ending)", None, 0),
        ("bad_quote_and_unsafe_comment_drop_once", missing, unsafe, "This sentence does not occur in the essay.", None, 0),
    ]
    for name, suggestion, comment, chosen_quote, expected_advice, removed in specs:
        value = copy.deepcopy(raw["t2-good"])
        improvement = {"quote": chosen_quote, "comment": comment}
        if suggestion is not missing:
            improvement["suggestion"] = suggestion
        value["argument"]["improvements"] = [improvement]
        out, text = normalize("t2-good", value)
        a = out["argument"]
        expected = [] if expected_advice is None else [{"quote": chosen_quote, "suggestion": expected_advice}]
        check(name + "_adopted_payload", a["improvements"] == expected, a["improvements"])
        check(name + "_counts", a["returned"] == 7 and a["kept"] == 6 + len(expected) and a["dropped"] == 1 - len(expected) and a["duplicates"] == a["over_limit"] == 0)
        check(name + "_removal_counts", a["suggestions_removed"] == removed and out["suggestions_removed"]["argument"] == removed and out["suggestions_removed"]["total"] == removed)
        check(name + "_no_unsafe_copy", unsafe not in text)
        if expected_advice is not None:
            check(name + "_exact_safe_advice_in_copy", expected_advice in text)
        else:
            check(name + "_no_alias_resurrection_in_copy", safe not in text and unsafe not in text)
        if removed:
            check(name + "_removed_count_visible_in_copy", "论证结构 1 条" in text and "已删去" in text)
        cases.append({"name": name, "input_improvement": improvement, "normalized_improvements": a["improvements"], "argument_counts": {k: a[k] for k in ("returned", "kept", "dropped", "duplicates", "over_limit", "suggestions_removed")}, "global_suggestions_removed": out["suggestions_removed"], "warnings": out["warnings"], "copy_optional_section": text[text.find("可选优化"):text.find("总评：")] if "可选优化" in text else None})

    # Regression with authentic forbidden advice, under both field names.
    strong_first = raw["t2-strong"]["argument"]["improvements"][0]
    for field in ("suggestion", "comment"):
        value = copy.deepcopy(raw["t2-strong"])
        value["argument"]["improvements"][0] = {"quote": strong_first["quote"], field: strong_first["suggestion"]}
        out, text = normalize("t2-strong", value)
        check("real_strong_forty_" + field + "_filtered_with_counts", out["suggestions_removed"]["argument"] == 1 and out["argument"]["dropped"] == 1 and "forty passengers" not in text)

    inherited_count = len(checks)
    check("inherited_check_count_is_144", inherited_count == 144, inherited_count)
    boundary_cases = []
    values = [f"Group G{n:02d} recorded {n}.5%." for n in range(1, 32)]
    extra_text = "\n\n" + " ".join(values)
    claim = source_cmp["claim"]

    def task1_case(name, supplied, expected, omitted, appended=extra_text):
        value = copy.deepcopy(t1raw)
        value["comparisons"] = [dict(source_cmp, figures=supplied)]
        sub = copy.deepcopy(samples["t1-no-image"]["submission"])
        sub["essay_text"] += appended
        out = review.normalize_evaluation(value, sub)
        text = copytext.evaluation_text(out, {})
        issues = out["consistency_issues"]
        rows = [line.strip() for line in text.splitlines() if line.strip().startswith("对照：")]
        got = issues[0]["figures"] if issues else []
        omitted_got = issues[0].get("figures_omitted", 0) if issues else 0
        check(name + "_normalized_values_in_order", got == expected, got)
        check(name + "_omitted_count", omitted_got == omitted, omitted_got)
        if expected:
            expected_line = "对照：" + "；".join(f"“{v}”" for v in expected)
            if omitted:
                expected_line += f"（另有 {omitted} 个数字未列出）"
            check(name + "_copy_exactly_agrees", rows == [expected_line], rows)
        else:
            check(name + "_no_unverified_contradiction_or_copy", not issues and not rows, {"issues": issues, "copy": rows})
        check(name + "_omission_notice_iff_required", ("未列出" in text) == bool(omitted))
        boundary_cases.append({"name": name, "input_figures": supplied, "expected_figures": expected, "expected_omitted": omitted, "normalized_issues": issues, "copy_evidence_lines": rows, "warnings": out["warnings"]})
        return out, text

    task1_case("thirty_unique", values[:30], values[:30], 0)
    task1_case("thirty_one_unique", values, values[:30], 1)
    task1_case("thirty_with_duplicate_variants", [values[0], "  " + values[0] + "  ", values[0].upper(), *values[1:30], values[29]], values[:30], 0)
    invalids = [None, False, 65, [], {}, "", "   ", "invented 99.9%", claim, "highest level of ownership"]
    task1_case("thirty_one_with_duplicates_invalids_and_claims", [*invalids, values[0], values[0], *values[1:], values[30], *invalids], values[:30], 1)
    task1_case("invalid_candidates_do_not_consume_capacity", [*invalids, *values[:30], *invalids], values[:30], 0)
    task1_case("reverse_model_order_kept", list(reversed(values)), list(reversed(values))[:30], 1)
    task1_case("only_invalid_or_claim_fragments", invalids, [], 0)
    task1_case("not_a_list", {"figure": values[0]}, [], 0)
    task1_case("blank_list", [], [], 0)
    task1_case("short_forged_quote_rejected", ["about 75%, INVENTED: Country Z reached 99.9%."], [], 0, appended="")

    # Full-quote verification before display clipping: exact adjacent code regression.
    real_long = samples["t1-no-image"]["submission"]["essay_text"].split("\n\n")[3]
    check("positive_long_quote_exceeds_display_limit", len(real_long) > 300, len(real_long))
    forged = real_long[:300] + " INVENTED: Country Z reached 99.9%."
    source_essay = samples["t1-no-image"]["submission"]["essay_text"]
    check("forged_long_quote_has_true_prefix_but_false_whole", real_long[:300] in source_essay and forged not in source_essay)
    task1_case("genuine_full_long_quote_kept", [real_long], [real_long[:300]], 0, appended="")
    bad_out, bad_copy = task1_case("forged_long_quote_must_be_rejected", [forged], [], 0, appended="")
    task1_case("thirty_valid_plus_forged_does_not_add_omitted", [*values[:30], forged], values[:30], 0)
    task1_case("thirty_one_valid_plus_forged_counts_only_one_omitted", [*values, forged], values[:30], 1)

    baseline_src = subprocess.check_output(["git", "show", "478461a8:tools/ielts_writing_ai/review.py"], cwd=repo, text=True)
    baseline = types.ModuleType("tools.ielts_writing_ai._probe_baseline_review")
    baseline.__package__ = "tools.ielts_writing_ai"
    baseline.__file__ = str(repo / "tools/ielts_writing_ai/review.py")
    exec(compile(baseline_src, "git:478461a8/tools/ielts_writing_ai/review.py", "exec"), baseline.__dict__)
    prior_input = copy.deepcopy(t1raw)
    prior_input["comparisons"] = [dict(source_cmp, figures=[forged])]
    before = baseline.normalize_evaluation(prior_input, samples["t1-no-image"]["submission"])
    before_copy = copytext.evaluation_text(before, {})
    check("baseline_rejects_same_forged_long_quote_end_to_end", not before["consistency_issues"] and "对照：" not in before_copy)
    prior_input["comparisons"][0]["figures"] = [real_long]
    before_valid = baseline.normalize_evaluation(prior_input, samples["t1-no-image"]["submission"])
    check("baseline_accepts_genuine_long_quote_positive_control", before_valid["consistency_issues"][0]["figures"] == [real_long[:300]])
    long_quote_regression = {"source_paragraph_length": len(real_long), "valid_full_quote": real_long, "forged_full_quote": forged, "forged_found_in_essay": forged in source_essay, "true_prefix_length": 300, "baseline_head": "478461a8", "baseline_normalized_issues": before["consistency_issues"], "baseline_warnings": before["warnings"], "current_normalized_issues": bad_out["consistency_issues"], "current_copy_evidence_lines": [line.strip() for line in bad_copy.splitlines() if line.strip().startswith("对照：")], "current_warnings": bad_out["warnings"], "effect": "唯一候选的全文不存在，但其真实前300字符先被截出并通过核实；本应忽略的未经核实证据被采用为矛盾对照。相同输入在基线被拒绝。加入30条真实证据后，还会把该无效候选算入figures_omitted。"}

    findings = []
    if not required <= set(changed_issue["figures"]):
        findings.append({"priority": "P2", "title": "超过四个匹配数字时，旧年背景数据仍会占满对照列表并挤掉真正反例", "file": "tools/ielts_writing_ai/review.py", "lines": [247, 248, 249], "reproduction": counterexample, "qualification": "原真实输出已修复；这不是新解析崩溃或分数错误，是同类证据展示截断未完全关闭。保持模型顺序+固定[:4]不能保证完整关键证据。"})
    if bad_out["consistency_issues"]:
        findings.append({"priority": "P2", "title": "新证据保留函数在完整核实前截300字符，接受真实前缀加编造结尾的引用", "file": "tools/ielts_writing_ai/review.py", "lines": [253, 257], "evidence": long_quote_regression, "suggestion": "先对完整strip后的原引用做contains_quote，成功后才截短显示；去重与容量计数也只处理完整核实的候选。保持本轮全部真实证据保留与30上限提示。"})
    output = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "source_status": subprocess.check_output(["git", "status", "--short", "--branch"], cwd=repo, text=True).strip(),
        "sources": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (data_path, raw_path)},
        "privacy": "Only committed redacted synthetic formal answers; no .env, private results or reasoning, credentials, network/model calls or business mutations.",
        "old_attribution_correction": attribution,
        "real_good_result": {"argument": good["argument"], "warnings": good["warnings"]},
        "old_counterexample_recheck": counterexample,
        "boundary_cases": boundary_cases,
        "long_quote_regression": long_quote_regression,
        "inherited_checks": {"passed": sum(c["passed"] for c in checks[:inherited_count]), "total": inherited_count},
        "additional_checks": {"passed": sum(c["passed"] for c in checks[inherited_count:]), "total": len(checks) - inherited_count},
        "comment_alias_matrix": cases,
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "all_checks_passed": all(c["passed"] for c in checks),
        "findings": findings,
        "boundary": "原144项只把已过时的最大4条/匹配筛选精确行/无匹配前4条改为完整去重保留；新增30/31边界、无效与重复计数、claim排除、顺序及完整长引文核实。所有材料为合成或既有脱敏正式回答；未调用模型。未做实际浏览器检查，复制使用正式copytext函数。",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": output["passed"], "total": output["total"], "findings": len(findings), "output": str(args.output)}, ensure_ascii=False))
    return 0 if output["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
