#!/usr/bin/env python3
"""Offline review of .10 deletion advice through normalize_evaluation + copytext.

Reads committed synthetic formal-response fixtures only. No credentials, private
reasoning, models, network, business edits or historical-probe changes. Exit 1
means a desired-behaviour assertion found a product counterexample.
"""

import argparse
import copy
import hashlib
import json
import re
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
    from tools.ielts_writing_ai import copytext, essay, review

    bundle = repo / "docs/design/ielts-writing-ai-prompt9-high-20261107/continuation"
    data_path, calls_path = bundle / "run_data.json", bundle / "raw_calls.jsonl"
    data = json.loads(data_path.read_text())
    samples = {s["id"]: s for s in data["samples"]}
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    raw = {
        sid: json.loads(next(c["text"] for c in calls if c["sample"] == sid))
        for sid in ("t1-no-image", "t2-good")
    }
    checks, cases = [], []

    def check(name, passed, details=None):
        checks.append({"name": name, "passed": bool(passed), "details": details})

    def normalized(value, sub):
        before = copy.deepcopy((value, sub))
        result = review.normalize_evaluation(value, sub)
        copied = copytext.evaluation_text(result, {})
        unchanged = (value, sub) == before
        return result, copied, unchanged

    sub1 = samples["t1-no-image"]["submission"]
    paragraphs = essay.split_paragraphs(sub1["essay_text"])
    total = essay.count_words(sub1["essay_text"])
    counts = [essay.count_words(p) for p in paragraphs]
    check("real_input_counts", total == 172 and counts == [18, 36, 36, 59, 23], counts)
    original_result, original_copy, unchanged = normalized(copy.deepcopy(raw["t1-no-image"]), copy.deepcopy(sub1))
    cc = next(c for c in original_result["criteria"] if c["key"] == "coherence")
    original_advice = raw["t1-no-image"]["coherence"]["issues"][0]["suggestion"]
    check("real_two_advice_notes", original_result["length_notes"] == 2)
    check("real_CC_note_149_retains_advice", cc["issues"][0]["suggestion"].startswith(original_advice) and "约剩 149 词" in cc["issues"][0]["suggestion"])
    check("real_priority_note_149", "约剩 149 词" in original_result["priorities"][0])
    check("real_copy_both_notes", original_copy.count("约剩 149 词") == 2)
    check("real_top_warning_count", any("有 2 条建议" in w and "低于 150" in w for w in original_result["warnings"]))
    check("program_generated_numbers_not_removed_as_unsourced", original_result["suggestions_removed"]["total"] == 0)
    check("real_input_unchanged", unchanged)
    check("real_scores_unchanged", [c["band"] for c in original_result["criteria"]] == [None, 7.0, 7.5, 7.5])

    safe = "保留关键论点，并把比较关系表达清楚。"
    comment = "这处文字可以酌情调整，但需要保留文章已经给出的关键比较。"

    def run_case(name, advice, quote, expected_notes, expected_after=None,
                 group="positive", channel="criterion", sid="t1-no-image",
                 actual_removed_words=None, source_adjustment=None, expected_removed=0):
        value = copy.deepcopy(raw[sid])
        sub = copy.deepcopy(samples[sid]["submission"])
        if source_adjustment:
            sub["essay_text"] = source_adjustment(sub["essay_text"])
            sub["word_count"] = essay.count_words(sub["essay_text"])
        for key in ("task", "coherence", "lexical", "grammar"):
            if isinstance(value.get(key), dict):
                value[key]["issues"] = []
        value["priorities"] = [safe]
        if value.get("argument"):
            value["argument"]["problems"] = []
            value["argument"]["improvements"] = []
        entry = {"quote": quote, "comment": comment, "suggestion": advice}
        if channel == "criterion":
            value["coherence"]["issues"] = [entry]
        elif channel == "priority":
            value["priorities"] = [advice]
        elif channel == "argument_problem":
            value["argument"]["problems"] = [{**entry, "type": "overgeneralized"}]
        elif channel == "argument_improvement":
            value["argument"]["improvements"] = [entry]
        result, copied, unchanged = normalized(value, sub)
        if channel == "criterion":
            output_entry = next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0]
            shown = output_entry["suggestion"]
        elif channel == "priority":
            shown = result["priorities"][0] if result["priorities"] else ""
        else:
            slot = "problems" if channel == "argument_problem" else "improvements"
            shown = result["argument"][slot][0]["suggestion"] if result["argument"][slot] else ""
        note_count = result["length_notes"]
        length_warnings = [w for w in result["warnings"] if "条建议提到删去" in w]
        start = len(checks)
        check(name + ":notes", note_count == expected_notes, note_count)
        check(name + ":copy_note_count", len(re.findall(r"约剩 \d+ 词", copied)) == expected_notes)
        check(name + ":top_warning", len(length_warnings) == (1 if expected_notes else 0), length_warnings)
        if expected_notes:
            check(name + ":correct_remaining_count", f"约剩 {expected_after} 词" in shown, shown)
            check(name + ":correct_count_copied", f"约剩 {expected_after} 词" in copied)
        else:
            check(name + ":no_false_whole_unit_count", "约剩" not in shown, shown)
        check(name + ":advice_preserved_or_intentionally_filtered", shown == "" if expected_removed else shown.startswith(advice))
        check(name + ":numeric_filter_count", result["suggestions_removed"]["total"] == expected_removed, result["suggestions_removed"])
        check(name + ":input_not_mutated", unchanged)
        target = review._deletion_target(advice, quote, sub["essay_text"])
        diagnostic = {
            "selected_target": target,
            "selected_target_words": essay.count_words(target) if target else None,
            "after_selected_target": essay.count_words(sub["essay_text"]) - essay.count_words(target) if target else None,
        }
        cases.append({
            "name": name, "group": group, "sample_id": sid, "channel": channel,
            "input_quote": quote, "input_advice": advice,
            "essay_words": essay.count_words(sub["essay_text"]),
            "expected_notes": expected_notes, "expected_after_if_warned": expected_after,
            "actual_requested_removal_words": actual_removed_words,
            "actual_remaining_if_requested_edit_applied": essay.count_words(sub["essay_text"]) - actual_removed_words if actual_removed_words is not None else None,
            "normalized_advice": shown, "length_notes": note_count,
            "top_length_warnings": length_warnings,
            "copy_relevant_lines": [line for line in copied.splitlines() if "约剩" in line or "条建议提到删去" in line or (advice and advice in line)],
            "helper_diagnostic_not_used_as_oracle": diagnostic,
            "failed_checks": [c["name"] for c in checks[start:] if not c["passed"]],
        })

    last, first = paragraphs[-1], paragraphs[0]
    run_case("whole_paragraph_cn", "删去这一结尾段。", last, 1, 149, actual_removed_words=23)
    run_case("whole_paragraph_en", "Delete this paragraph.", last, 1, 149, actual_removed_words=23)
    run_case("whole_sentence_cn", "删除这一整句。", last, 1, 149, actual_removed_words=23)
    run_case("whole_sentence_en", "Remove this sentence.", last, 1, 149, actual_removed_words=23)
    run_case("priority_explicit_quote_cn", "删去结尾的“In summary”这一段。", None, 1, 149, channel="priority", actual_removed_words=23)
    run_case("priority_explicit_quote_en", 'Delete the paragraph beginning "In summary".', None, 1, 149, channel="priority", actual_removed_words=23)
    run_case("safe_whole_paragraph_removal", "删除这一段。", first, 0, actual_removed_words=18)
    run_case("at_exact_minimum", "删除这一段。", last, 0, actual_removed_words=23, source_adjustment=lambda text: "Clearly, " + text)
    run_case("rewrite_not_deletion", "把这一段改写得更紧凑，保留主要比较。", last, 0)
    run_case("word_edit_without_context_word", "删去“In summary”两个词。", last, 0, actual_removed_words=2)
    run_case("unverified_issue_quote", "删去这一段。", "This quote is absent from the essay.", 0)
    run_case("numeric_guard_runs_before_length_note", "Delete this paragraph and claim that 87% support this view.", last, 0, expected_removed=1)

    # Intent and scope: these are explicit negation/word-only edits, not ambiguous style.
    run_case("negative_cn", "不要删去这一段，应保留其比较信息。", last, 0, group="intent_scope", actual_removed_words=0)
    run_case("negative_en", "Do not delete this paragraph; retain the comparison.", last, 0, group="intent_scope", actual_removed_words=0)
    run_case("quoted_rejected_advice", "不要采用“删除这一段”的意见，应保留其中的比较信息。", last, 0, group="intent_scope", actual_removed_words=0)
    run_case("word_only_inside_sentence_cn", "删去这一句中的“In summary”两个词，保留其余内容。", last, 0, group="intent_scope", actual_removed_words=2)
    run_case("word_only_inside_sentence_en", 'Remove only "In summary" from this sentence, keeping the rest.', last, 0, group="intent_scope", actual_removed_words=2)

    # Explicit action target differs from the issue quote. First paragraph is 18 words,
    # last is 23: binding to the wrong quote changes whether a warning is necessary.
    run_case("explicit_target_last_despite_first_quote_cn", "删去结尾的“In summary”这一段。", first, 1, 149, group="target_binding", actual_removed_words=23)
    run_case("explicit_target_last_despite_first_quote_en", 'Delete the final paragraph beginning "In summary".', first, 1, 149, group="target_binding", actual_removed_words=23)
    run_case("explicit_target_first_despite_last_quote", "删去“The bar chart compares”这一引言段。", last, 0, group="target_binding", actual_removed_words=18)
    run_case("priority_retained_quote_before_deleted_quote", "保留“In summary”这一段，删去“The bar chart compares”这一引言段。", None, 0, group="target_binding", channel="priority", actual_removed_words=18)
    run_case("repeated_quote_explicit_final_paragraph", "删除最后这一段。", "Country A", 1, 149, group="target_binding", actual_removed_words=23)

    # Verify the other advertised paths without adding language/parser categories.
    good_sub = samples["t2-good"]["submission"]
    good_first = essay.split_paragraphs(good_sub["essay_text"])[0]
    after_good = essay.count_words(good_sub["essay_text"]) - essay.count_words(good_first)
    check("task2_positive_control_below_250", after_good < 250)
    for channel in ("argument_problem", "argument_improvement"):
        run_case(channel + "_positive", "Delete this paragraph.", good_first, 1, after_good,
                 channel=channel, sid="t2-good", actual_removed_words=essay.count_words(good_first))

    findings = []
    for group, title, lines, description in (
        ("intent_scope", "否定或句内删词建议被误判为整段/整句删除", [315, 322, 324, 338, 343, 507],
         "仅检查删除词和段/句字样，没有确认删除意图及动作宾语。不要删段或只删两个词仍追加149词，并在顶部确定宣称删后不足；后者实际剩170词。"),
        ("target_binding", "建议明确删除别段时仍优先使用issue.quote或第一条引文", [317, 318, 319, 328],
         "忽略明确动作目标，始终取found[0]的首个包含单元。首段quote+删结尾漏149词警告；结尾quote+删首段误报149；重复Country A+最后一段会算概述段，报136而非149。"),
    ):
        failing = [c for c in cases if c["group"] == group and c["failed_checks"]]
        if failing:
            findings.append({"priority": "P2", "title": title,
                             "file": "tools/ielts_writing_ai/review.py", "lines": lines,
                             "description": description, "case_ids": [c["name"] for c in failing]})

    output = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "source_status": subprocess.check_output(["git", "status", "--short", "--branch"], cwd=repo, text=True).strip(),
        "source_files": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (data_path, calls_path)},
        "privacy_scope": "Committed redacted synthetic formal answers only; no private results, .env, credentials, reasoning bodies, network or model calls.",
        "real_regression": {"before_words": total, "paragraph_words": counts, "after_delete_last": total-counts[-1], "length_notes": original_result["length_notes"], "CC_advice": cc["issues"][0]["suggestion"], "priority_1": original_result["priorities"][0], "warnings": original_result["warnings"], "copy_note_occurrences": original_copy.count("约剩 149 词")},
        "cases": cases,
        "checks": checks,
        "passed": sum(c["passed"] for c in checks), "total": len(checks),
        "all_checks_passed": all(c["passed"] for c in checks), "findings": findings,
        "limits": ["Expected targets/removal counts are stated from the actual instruction and original text, not copied from _deletion_target.", "Only explicit whole-unit/word-only/negative/bound-target examples and the requested duplicate-quote case; not claiming full natural-language coverage.", "All visible evidence runs normalize_evaluation and production evaluation_text; no browser rendering or full-suite claim.", "A length annotation does not validate the teaching advice itself. Scores and source text remain unchanged."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": output["passed"], "total": output["total"], "cases": len(cases), "findings": len(findings), "output": str(args.output)}, ensure_ascii=False))
    return 0 if output["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
