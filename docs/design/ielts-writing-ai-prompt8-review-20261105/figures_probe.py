#!/usr/bin/env python3
"""Portable offline review of English figures and source-derived durations.

Reuses the old English-number probe's real response and percentage controls with
correct expectations. Added cases are explicitly synthetic, not new model output.
Usage: python figures_probe.py --repo CHECKOUT --output RESULT.json
"""
import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
repo = args.repo.expanduser().resolve()
sys.path.insert(0, str(repo))
sys.dont_write_bytecode = True
network_attempts = 0


def forbid_network(event, _args):
    global network_attempts
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
        network_attempts += 1
        raise AssertionError("Offline probe may not use network or DNS")


sys.addaudithook(forbid_network)
from tools.ielts_writing_ai import copytext, essay, figures, review
from tools.ielts_writing_ai.llm import parse_strict_json

bundle = repo / "docs/design/ielts-writing-ai-thinking-ab-20261104"
high_run = json.loads((bundle / "high/run_data.json").read_text())
sample = next(s for s in high_run["samples"] if s["id"] == "t2-mid")
calls = [json.loads(line) for line in (bundle / "high/raw_calls.jsonl").read_text().splitlines()]
call = next(c for c in calls if c["sample"] == "t2-mid" and c["kind"] == "evaluate" and c["ok"])
base = parse_strict_json(call["text"])
index, old_issue = next((i, issue) for i, issue in enumerate(base["criteria"]["task"]["issues"])
                        if "forty times" in issue.get("suggestion", ""))
submission = sample["submission"]
checks = []


def check(name, condition, evidence=None):
    checks.append({"case": name, "passed": bool(condition), "evidence": evidence})
    assert condition, name


def matching(result, quote):
    return next(i for c in result["criteria"] if c["key"] == "task"
                for i in c["issues"] if i["quote"] == quote)


def evaluate(advice, source_sentence=None):
    raw, sub = copy.deepcopy(base), copy.deepcopy(submission)
    issue = raw["criteria"]["task"]["issues"][index]
    issue["suggestion"] = advice
    if source_sentence is not None:
        sub["essay_text"] += "\n\n" + source_sentence
        sub["word_count"] = essay.count_words(sub["essay_text"])
        issue["quote"] = source_sentence
        issue["comment"] = "建议用下面的完整句准确描述这组公交数量或时间数据。"
    result = review.normalize_evaluation(raw, sub)
    current = matching(result, issue["quote"])
    copied = copytext.evaluation_text(result, {})
    return {
        "advice": advice, "source_sentence": source_sentence,
        "source_figures": figures.figures(source_sentence or sub["essay_text"]),
        "advice_figures": figures.figures(advice),
        "source_year_spans": sorted(figures.for_submission(sub).year_spans),
        "missing": figures.for_submission(sub).unsourced(advice),
        "normalized_issue": current, "removed_counts": result["suggestions_removed"],
        "advice_in_copy": advice in copied,
        "removed_note_in_copy": copytext.REMOVED_NOTE in copied,
    }


real = evaluate(old_issue["suggestion"])
check("historical_real_call_success", call["ok"] and call["http_status"] == 200)
check("real_source_has_no_40", not re.search(r"\b(?:40|forty)\b", submission["essay_text"], re.I))
check("old_real_forty_times_removed", real["normalized_issue"]["suggestion_removed"] is True
      and real["normalized_issue"]["suggestion"] == "" and not real["advice_in_copy"]
      and real["removed_counts"]["total"] == 1 and real["removed_note_in_copy"], real)
arabic = evaluate(old_issue["suggestion"].replace("forty times", "40 times"))
check("same_real_advice_arabic_control_removed", arabic["normalized_issue"]["suggestion_removed"] is True
      and not arabic["advice_in_copy"] and arabic["removed_counts"]["total"] == 1, arabic)

# Old probe's percentage table, now asserting desired behavior, plus equivalent
# spelling/unit controls and the previously fixed source-boundary cases.
controls = [
    ("arabic_unsourced_percent", "Buses help.", "Reduce emissions by 40 percent.", True),
    ("english_unsourced_percent", "Buses help.", "Reduce emissions by forty percent.", True),
    ("arabic_sourced_percent", "Emissions fell by 40 percent.", "Reduce emissions by 40%.", False),
    ("english_source_arabic_advice", "Emissions fell by forty percent.", "Reduce emissions by 40%.", False),
    ("different_percent", "Emissions fell by 41%.", "Reduce emissions by forty percent.", True),
    ("arabic_source_english_advice", "The value is 42%.", "Use forty-two percent.", False),
    ("english_compound_number", "The count was 120.", "There were one hundred and twenty passengers.", False),
    ("scale_equivalent", "There were 1500000 residents.", "There were 1.5 million residents.", False),
    ("unsourced_scaled_number", "Buses help.", "There are 1.5 million passengers.", True),
    ("plain_not_multiplier", "There are 40 buses.", "A train carries forty times as many people.", True),
    ("multiplier_equivalent", "It has 40 times the capacity.", "It offers forty-fold capacity.", False),
    ("small_multiplier_no_exemption", "Buses help.", "It carries three times as many people.", True),
    ("english_word_target", "Buses help.", "Expand to two hundred and sixty words.", False),
    ("arabic_word_target", "Buses help.", "扩写到260词以上。", False),
    ("english_year_span", "Ownership in 2000 and 2020.", "Twenty years later, ownership rose.", False),
    ("arabic_year_span", "Ownership in 2000 and 2020.", "20 years later, ownership rose.", False),
    ("decade_span", "Ownership in 2000 and 2020.", "Over the two decades, ownership rose.", False),
    ("wrong_year_span", "Ownership in 2000 and 2020.", "Thirty years later, ownership rose.", True),
    ("new_year_rejected", "Ownership in 2000 and 2020.", "In 1990, ownership rose.", True),
    ("year_not_percent", "The service opened in 1980.", "Reduce emissions by eighty percent.", True),
    ("count_not_percent", "There are 180 buses.", "Reduce emissions by eighty percent.", True),
    ("chinese_percent", "Emissions fell by 80%.", "降低百分之八十。", False),
    ("chinese_small_percent", "Buses help.", "降低百分之8。", True),
    ("different_chinese_percent", "降低百分之八十一。", "降低百分之八十。", True),
]
for name, source, advice, remove in controls:
    missing = figures.Sources(source).unsourced(advice)
    check(name, bool(missing) == remove,
          {"source": source, "advice": advice, "parsed": figures.figures(advice), "missing": missing})

# All fourteen historical responses: only the real forty-times suggestion should
# be removed. Does not prove new prompt quality; these are fixed .6 outputs.
fx_path = repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261104e.json"
fx = json.loads(fx_path.read_text())
replay = []
for mode, outputs in fx["evaluations"].items():
    shared_calls = [json.loads(line) for line in (bundle / mode / "raw_calls.jsonl").read_text().splitlines()]
    for sid, text in outputs.items():
        original = next(c["text"] for c in shared_calls if c["sample"] == sid and c["kind"] == "evaluate" and c["ok"])
        check(f"real_fixture_exact:{mode}:{sid}", text == original)
        result = review.normalize_evaluation(parse_strict_json(text), fx["submissions"][sid])
        removed = result["suggestions_removed"]["total"]
        check(f"real_replay_removals:{mode}:{sid}", removed == int(mode == "high" and sid == "t2-mid"))
        replay.append({"mode": mode, "sample": sid, "removed": removed})

# New material boundary 1: conjunction separates independent counts, not always
# one compound number. This is not the known limitation of semantic fact checking.
word_source = "The two buses carry forty and fifty passengers respectively."
digit_source = "The two buses carry 40 and 50 passengers respectively."
list_cases = {
    "valid_arabic_advice_deleted": evaluate("The buses carry 40 and 50 passengers respectively.", word_source),
    "valid_english_advice_deleted": evaluate("The buses carry forty and fifty passengers respectively.", digit_source),
    "invented_sum_advice_kept": evaluate("One bus carries 90 passengers.", word_source),
    "digit_source_does_not_allow_sum": evaluate("One bus carries 90 passengers.", digit_source),
    "valid_compound_control": evaluate("The train carries 120 passengers.", "The train carries one hundred and twenty passengers."),
}
list_bug = all([
    list_cases["valid_arabic_advice_deleted"]["normalized_issue"]["suggestion_removed"],
    list_cases["valid_english_advice_deleted"]["normalized_issue"]["suggestion_removed"],
    list_cases["invented_sum_advice_kept"]["advice_in_copy"],
    list_cases["digit_source_does_not_allow_sum"]["normalized_issue"]["suggestion_removed"],
    list_cases["valid_compound_control"]["advice_in_copy"],
])

# New material boundary 2: count values in the year-shaped numeric range must not
# manufacture a duration. Identical values with genuine calendar context remain a
# positive control. Both paths go through full normalization and generated copy.
duration_cases = {
    "non_year_counts_allow_duration": evaluate("Twenty years later, there were 2020 buses.",
        "There are 2000 buses in City A and 2020 buses in City B."),
    "genuine_years_allow_duration": evaluate("Twenty years later, public transport was more reliable.",
        "Public transport was compared in 2000 and 2020."),
    "wrong_span_still_rejected": evaluate("Thirty years later, public transport was more reliable.",
        "Public transport was compared in 2000 and 2020."),
    "other_counts_do_not_allow_duration": evaluate("Twenty years later, there were 2200 buses.",
        "There are 2200 buses in City A and 2220 buses in City B."),
}
duration_bug = all([
    duration_cases["non_year_counts_allow_duration"]["advice_in_copy"],
    duration_cases["genuine_years_allow_duration"]["advice_in_copy"],
    duration_cases["wrong_span_still_rejected"]["normalized_issue"]["suggestion_removed"],
    duration_cases["other_counts_do_not_allow_duration"]["normalized_issue"]["suggestion_removed"],
])

report = {
    "source_head": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
    "scope": "Offline pure normalizers and committed redacted synthetic fixtures only. No config, Key, student PDF, reasoning, model or network access.",
    "old_P2_closed": True,
    "baseline_checks": checks,
    "passed_baseline_checks": len(checks),
    "historical_replay": replay,
    "findings": [
        {"id": "english_conjunction_merges_independent_counts", "priority": "P2", "reproduced": list_bug,
         "source_lines": ["tools/ielts_writing_ai/figures.py:93", "tools/ielts_writing_ai/figures.py:115"],
         "correct_requirement": "Respect independent counts in 'forty and fifty passengers respectively'; keep equivalent 40/50 advice and reject an invented 90 count.",
         "observed": "The parser adds forty and fifty to 90. Full evaluation deletes both legitimate forms and retains the invented sum in copy text.",
         "cases": list_cases},
        {"id": "non_year_counts_create_year_span", "priority": "P2", "reproduced": duration_bug,
         "source_lines": ["tools/ielts_writing_ai/figures.py:108", "tools/ielts_writing_ai/figures.py:206", "tools/ielts_writing_ai/figures.py:219"],
         "correct_requirement": "Derive time spans from source calendar years, not arbitrary counts whose values lie between 1000 and 2100.",
         "observed": "2000/2020 buses in different cities create year_spans={20}; a fabricated twenty-years-later sentence remains visible. Genuine year span and wrong-span controls behave as intended.",
         "cases": duration_cases},
    ],
    "limits": [
        "No new model outputs or claims of prompt .8 accuracy; historical outputs are from .6.",
        "twice/a third are already disclosed unsupported forms; not reported as new defects.",
        "Parser checks provenance of numbers, not general factual or logical truth. The two findings are concrete numeric parsing/derivation errors, not demands for a semantic oracle.",
        "Only own new evidence files were written; business code and historical reports remain unchanged.",
    ],
    "network_attempts": network_attempts,
}
output = args.output.expanduser().resolve()
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"baseline_checks": len(checks), "old_P2_closed": True,
                  "new_findings_reproduced": [f["id"] for f in report["findings"] if f["reproduced"]],
                  "output": str(output)}, ensure_ascii=False))
