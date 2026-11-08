#!/usr/bin/env python3
"""Offline deletion-target review through normalize_evaluation -> copytext.

Usage: python target_probe.py --repo /path/to/repo --output target_probe.json
Public synthetic-response fixtures only. No model calls, credentials or business edits.
Exit 1 means desired-behaviour assertions reproduced a product counterexample.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))

    def forbid(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline probe forbids network")

    sys.addaudithook(forbid)
    from tools.ielts_writing_ai import copytext, deletion, essay, review
    from tools.ielts_writing_ai.llm import parse_strict_json

    with tempfile.TemporaryDirectory(prefix="iwa-target-metrics-") as scratch:
        metrics_path = Path(scratch) / "metrics.json"
        run = subprocess.run([sys.executable, str(repo / "docs/design/ielts-writing-ai-prompt10-review-20261108/metrics_probe.py"), "--repo", str(repo), "--output", str(metrics_path)], capture_output=True, text=True)
        old_metrics = json.loads(metrics_path.read_text())
        old_metric_summary = {k: old_metrics[k] for k in ("checks_passed", "checks_total", "failures")}

    path = repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261107_prompt9.json"
    original_bytes = path.read_bytes()
    fixture = json.loads(original_bytes)
    raw = {sid: parse_strict_json(fixture["attempts"][sid][-1]["text"]) for sid in ("t1-no-image", "t2-good")}
    checks, cases = {}, []

    def check(key, value):
        checks[key] = bool(value)

    check("old_metrics_120", run.returncode == 0 and old_metric_summary == {"checks_passed": 120, "checks_total": 120, "failures": []})
    sub1 = fixture["submissions"]["t1-no-image"]
    paragraphs = essay.split_paragraphs(sub1["essay_text"])
    check("source_counts", essay.count_words(sub1["essay_text"]) == 172 and [essay.count_words(p) for p in paragraphs] == [18, 36, 36, 59, 23])
    check("last_paragraph_is_last_sentence", paragraphs[-1] == essay.split_sentences(sub1["essay_text"])[-1].text)

    def run_case(name, advice, *, expected_after, quote=None, channel="criterion", sid="t1-no-image", unsure=False, group="control"):
        value = copy.deepcopy(raw[sid])
        sub = copy.deepcopy(fixture["submissions"][sid])
        for key in essay.CRITERIA:
            if isinstance(value.get(key), dict):
                value[key]["issues"] = []
        value["priorities"] = ["保留关键论点，并把比较关系表达清楚。"]
        if value.get("argument"):
            value["argument"]["problems"] = []
            value["argument"]["improvements"] = []
        target_quote = quote or essay.split_paragraphs(sub["essay_text"])[-1]
        item = {"quote": target_quote, "comment": "这处文字可以酌情调整，但需要保留文章已有的关键信息。", "suggestion": advice}
        if channel in {"criterion", "criterion_priority"}:
            value["coherence"]["issues"] = [copy.deepcopy(item)]
        if channel in {"priority", "criterion_priority"}:
            value["priorities"] = [advice]
        if channel == "improvement":
            value["argument"]["improvements"] = [{"quote": target_quote, "suggestion": advice}]
        original_input = copy.deepcopy((value, sub))
        result = review.normalize_evaluation(value, sub)
        copied = copytext.evaluation_text(result, {})
        shown = []
        if channel in {"criterion", "criterion_priority"}:
            shown.append(next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0]["suggestion"])
        if channel in {"priority", "criterion_priority"}:
            shown.append(result["priorities"][0])
        if channel == "improvement":
            shown.append(result["argument"]["improvements"][0]["suggestion"])
        afters = [int(n) for s in shown for n in re.findall(r"约剩 (-?\d+) 词", s)]
        expected = [expected_after] * len(shown) if expected_after is not None else []
        check(name + ".correct_numeric_remainder", afters == expected)
        check(name + ".copy_numeric_remainder", [int(n) for n in re.findall(r"约剩 (-?\d+) 词", copied)] == expected)
        check(name + ".advice_retained", all(s.startswith(advice) for s in shown))
        check(name + ".length_notes_are_advice_count", result["length_notes"] == (len(shown) if expected_after is not None else 0))
        check(name + ".raw_and_source_unchanged", original_input == (value, sub))
        baseline = review.normalize_evaluation(copy.deepcopy(raw[sid]), copy.deepcopy(sub))
        check(name + ".scores_unchanged", [c["band"] for c in result["criteria"]] == [c["band"] for c in baseline["criteria"]] and result["overall_band"] == baseline["overall_band"])
        if unsure:
            check(name + ".uncertainty_not_fabricated_count", all("无法确定" in s and "没有计算字数" in s for s in shown))
        analysed = deletion.analyse(advice, None if channel == "priority" else target_quote, sub["essay_text"])
        diagnostic = None if analysed is None else {"units": sorted(analysed.units), "passages": analysed.passages, "unsure": analysed.unsure, "words_summed_by_product": analysed.words(sub["essay_text"])}
        cases.append({"name": name, "group": group, "channel": channel, "sample": sid,
                      "advice": advice, "issue_quote": target_quote, "source_words": essay.count_words(sub["essay_text"]),
                      "expected_remainder": expected_after, "actual_remainders": afters,
                      "shown": shown, "length_notes": result["length_notes"],
                      "warnings": result["warnings"], "analysis": diagnostic,
                      "failed_checks": [k for k,v in checks.items() if k.startswith(name + ".") and not v]})

    run_case("single_last_paragraph", "删去最后一段。", expected_after=149)
    run_case("single_last_sentence", "删去最后一句。", expected_after=149)
    run_case("distinct_first_and_last", "删去第一段；删去最后一段。", expected_after=131)
    run_case("repeat_same_paragraph", "删去最后一段；删去最后一段。", expected_after=149)
    run_case("same_advice_two_channels", "删去最后一段。", expected_after=149, channel="criterion_priority")
    run_case("paragraph_sentence_overlap", "删去最后一段；删去最后一句。", expected_after=149, group="overlapping_actions")
    run_case("sentence_paragraph_overlap", "删去最后一句；删去最后一段。", expected_after=149, group="overlapping_actions")
    run_case("paragraph_passage_overlap", "删去最后一段；删去“In summary”两个词。", expected_after=149, group="overlapping_actions")
    run_case("english_overlap", "Delete the last paragraph; delete the last sentence.", expected_after=149, group="overlapping_actions")
    run_case("priority_overlap", "删去最后一段；删去最后一句。", expected_after=149, channel="priority", group="overlapping_actions")
    sub2 = fixture["submissions"]["t2-good"]
    last2 = essay.split_paragraphs(sub2["essay_text"])[-1]
    expected2 = essay.count_words(sub2["essay_text"]) - essay.count_words(last2)
    run_case("improvement_overlap", "删去最后一段；删去最后一句。", expected_after=expected2, sid="t2-good", channel="improvement", group="overlapping_actions")
    run_case("outside_existing_paragraph_range", "删去第九段。", expected_after=None, unsure=True, group="out_of_range_target")
    run_case("out_of_range_priority_with_quote", f"删去第九段“{paragraphs[-1]}”这一段。", expected_after=None, channel="priority", unsure=True, group="out_of_range_target")
    run_case("two_named_units_same_clause_unsure", "删去首段和末段。", expected_after=None, unsure=True)
    run_case("mixed_location_unsure", "删去第二段的最后一句。", expected_after=None, unsure=True)
    run_case("repeated_quote_unsure", "删去这一段。", expected_after=None, quote="Country A", unsure=True)
    run_case("contradictory_position_and_quote", f"删去第一段“{paragraphs[-1]}”这一段。", expected_after=None, channel="priority", unsure=True)
    check("fixture_bytes_unchanged", path.read_bytes() == original_bytes)
    findings = []
    if any(c["failed_checks"] for c in cases if c["group"] == "overlapping_actions"):
        findings.append({"priority": "P2", "title": "Overlapping deletion actions are counted more than once", "locations": ["tools/ielts_writing_ai/deletion.py:83", "tools/ielts_writing_ai/deletion.py:89", "tools/ielts_writing_ai/deletion.py:209"], "cause": "The unit set deduplicates only identical (kind,index) keys. words() sums paragraph, sentence and quoted passage texts without resolving their overlapping original spans.", "example": "Task1 has172 words; its final paragraph is also its final sentence (23 words). Deleting both descriptions removes23 words once, so149 remain; the product says126. The wrong number survives normalize and copy.", "positive_control": "Separate first18 and final23 word paragraphs correctly leave131; repeating the identical paragraph target is deduplicated."})
    if any(c["failed_checks"] for c in cases if c["group"] == "out_of_range_target"):
        findings.append({"priority": "P2", "title": "Out-of-range explicit target silently falls back to another passage", "locations": ["tools/ielts_writing_ai/deletion.py:142", "tools/ielts_writing_ai/deletion.py:151", "tools/ielts_writing_ai/deletion.py:191"], "cause": "A parsed ordinal outside1..count is discarded and returned as None (no target named). analyse then uses issue.quote or quoted content even though the advice explicitly named an impossible paragraph.", "example": "Delete paragraph九 in a five-paragraph essay, with the issue quoting the final paragraph: product confidently says149 remain by deleting paragraph5. This target cannot be located and should not get a numeric remainder.", "positive_control": "Conflicting valid first-paragraph position and final-paragraph quote already produces a nonnumeric uncertainty note."})
    output = {"source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
              "network_calls": 0, "actual_model_requests": 0, "fixture_sha256": hashlib.sha256(original_bytes).hexdigest(),
              "old_metrics": old_metric_summary, "cases": cases, "findings": findings, "checks": checks,
              "checks_passed": sum(checks.values()), "checks_total": len(checks), "failures": [k for k,v in checks.items() if not v],
              "scope_note": "Each suggestion is checked on its own; no assumption is made that separate optional suggestions across channels must be cumulatively applied."}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("checks_passed", "checks_total", "findings")}, ensure_ascii=False))
    if output["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
