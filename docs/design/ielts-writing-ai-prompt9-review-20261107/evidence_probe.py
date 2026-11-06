#!/usr/bin/env python3
"""Offline .9 evidence-selection and comment-alias review.

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
    check("current_real_copy_keeps_decisive_pair", '对照：“around 70%”；“about 75%”；“nearly 80%”' in copied)
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
        "impact": "页面和复制的对照行只剩2000的70/55/40/15，决定2020矛盾的75/80又被[:4]截掉；解释正文仍正确，分数未因此改变。",
        "scope": "真实8数输入的紧邻变体；按数字是否在comment出现筛选，无法在超过4个匹配项时保证保留决定性比较。提示词要求最多4不等于旧格式/违规输出不会进入已接受路径。",
        "source_lines": ["tools/ielts_writing_ai/review.py:241-249", "tools/ielts_writing_ai/review.py:284", "tools/ielts_writing_ai/copytext.py:150-151", "tools/ielts_writing_ai/static/iwa.js:568"],
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
        check(name + "_at_most_four_deduplicated", len(got) <= 4 and len(set(got)) == len(got))
    no_match = copy.deepcopy(t1raw)
    next(c for c in no_match["comparisons"] if c["holds"] is False)["comment"] = "这一排名说法与后面的数据矛盾。"
    fallback, _ = normalize("t1-no-image", no_match)
    check("documented_no_numeric_match_falls_back_to_first_four", fallback["consistency_issues"][0]["figures"] == source_cmp["figures"][:4])

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

    findings = []
    if not required <= set(changed_issue["figures"]):
        findings.append({"priority": "P2", "title": "超过四个匹配数字时，旧年背景数据仍会占满对照列表并挤掉真正反例", "file": "tools/ielts_writing_ai/review.py", "lines": [247, 248, 249], "reproduction": counterexample, "qualification": "原真实输出已修复；这不是新解析崩溃或分数错误，是同类证据展示截断未完全关闭。保持模型顺序+固定[:4]不能保证完整关键证据。"})
    output = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "source_status": subprocess.check_output(["git", "status", "--short", "--branch"], cwd=repo, text=True).strip(),
        "sources": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (data_path, raw_path)},
        "privacy": "Only committed redacted synthetic formal answers; no .env, private results or reasoning, credentials, network/model calls or business mutations.",
        "old_attribution_correction": attribution,
        "real_good_result": {"argument": good["argument"], "warnings": good["warnings"]},
        "counterexample": counterexample,
        "comment_alias_matrix": cases,
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "all_checks_passed": all(c["passed"] for c in checks),
        "findings": findings,
        "boundary": "数字是否在comment出现是启发式，不证明年份/单位/比较语义；本探针仅确认真实修复和紧邻截断变体，不审定模型评分，不扩展数字语言覆盖。comment别名的正反、过滤、引文、计数、复制均使用完整normalize路径。",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": output["passed"], "total": output["total"], "findings": len(findings), "output": str(args.output)}, ensure_ascii=False))
    return 0 if output["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
