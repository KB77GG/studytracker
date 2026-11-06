#!/usr/bin/env python3
"""Portable positive verification of the previously reported numeric defects.

Every old case is asserted independently against the correct result. A compound
`reproduced` flag becoming false cannot hide a partially unfixed case.
Usage: python figures_verification.py --repo CHECKOUT --output RESULT.json
"""
import argparse
import contextlib
import copy
import io
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
repo, output = args.repo.expanduser().resolve(), args.output.expanduser().resolve()
historical = repo / "docs/design/ielts-writing-ai-prompt8-recheck-20261105/figures_recheck.py"
with tempfile.TemporaryDirectory(prefix="iwa-figures-verified-") as tmp:
    baseline_path = Path(tmp) / "historical.json"
    argv = sys.argv
    sys.argv = [str(historical), "--repo", str(repo), "--output", str(baseline_path)]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            state = runpy.run_path(str(historical), run_name="__main__")
    finally:
        sys.argv = argv
    historical_result = json.loads(baseline_path.read_text())

from tools.ielts_writing_ai import copytext, essay, figures, review

checks = []


def check(name, condition, evidence=None):
    checks.append({"case": name, "passed": bool(condition), "evidence": evidence})
    assert condition, name


def assert_advice(name, result, should_remove):
    issue = result["normalized_issue"]
    check(name, issue["suggestion_removed"] == should_remove
          and issue["suggestion"] == ("" if should_remove else result["advice"])
          and result["advice_in_copy"] == (not should_remove)
          and result["removed_counts"]["total"] == int(should_remove)
          and result["removed_note_in_copy"] == should_remove
          and bool(result["missing"]) == should_remove, result)


original = state["old"]
for name, remove in {
    "valid_arabic_advice_deleted": False,
    "valid_english_advice_deleted": False,
    "invented_sum_advice_kept": True,
    "digit_source_does_not_allow_sum": True,
    "valid_compound_control": False,
}.items():
    assert_advice("original_tens:" + name, original["list_cases"][name], remove)
for name, remove in {
    "non_year_counts_allow_duration": True,
    "genuine_years_allow_duration": False,
    "wrong_span_still_rejected": True,
    "other_counts_do_not_allow_duration": True,
}.items():
    assert_advice("original_duration:" + name, original["duration_cases"][name], remove)
for name, remove in {
    "hundreds_valid_digits": False,
    "hundreds_valid_words": False,
    "hundreds_invented_merged_value": True,
    "hundreds_digit_source_blocks_merged_value": True,
    "thousands_valid_digits": False,
    "thousands_invented_sum": True,
    "genuine_compound_sentence": False,
}.items():
    assert_advice("hundreds_thousands:" + name, state["compound_cases"][name], remove)
for name, remove in {
    "quantity_rose_from_to": True,
    "quantity_fleet_of": True,
    "quantity_between_range": True,
    "quantity_without_temporal_adjacent_word": True,
    "genuine_in_years": False,
    "genuine_from_to_years": False,
    "wrong_duration_with_years": True,
}.items():
    assert_advice("context_duration:" + name, state["duration_cases"][name], remove)

for words, expected in (
    ("one hundred and two hundred", ["100", "200"]),
    ("one thousand and two thousand", ["1000", "2000"]),
    ("one hundred two hundred", ["100", "200"]),
    ("one thousand two thousand", ["1000", "2000"]),
    ("two hundred and sixty", ["260"]),
    ("one hundred and two thousand", ["102000"]),
    ("three hundred thousand", ["300000"]),
    ("nineteen hundred", ["1900"]),
):
    actual = [value for _start, _end, value in figures.split_en_numbers(words)]
    check("number_grammar:" + words, actual == expected, {"text": words, "values": actual})

# An actual 20-word essay with no dates or numeric facts. Its metadata count and
# task minimum must not authorize factual durations; writing targets still work.
twenty_word_essay = (
    "Governments should invest in public transport because buses help people travel "
    "efficiently and reduce congestion while keeping journeys generally affordable."
)
check("synthetic_essay_exactly_twenty_words", essay.count_words(twenty_word_essay) == 20)
short_submission = {
    "task_type": "task2", "prompt_text": "Should governments prioritise public transport?",
    "essay_text": twenty_word_essay, "word_count": 20, "target_band": 7,
    "image_status": "none",
}
criterion = {
    "band": 5.0, "summary": "本文立场可以识别，但论述篇幅很短，还需要更充分地解释和展开。",
    "strengths": [{"quote": "buses help people travel efficiently", "comment": "给出了公交出行效率的理由。"}],
    "issues": [],
}
short_raw = {
    "criteria": {key: copy.deepcopy(criterion) for key in ("task", "coherence", "lexical", "grammar")},
    "overall_comment": "文章有明确立场，但是篇幅过短，论证发展和段落组织需要进一步完善。",
    "priorities": ["扩写到260词以上，补充相关的原因和例子。"],
    "argument": {
        "position": {"quote": "Governments should invest in public transport", "consistent": True,
                     "comment": "支持投资公共交通的立场明确。"},
        "paragraphs": [{"p": 1, "role": "body", "main_point": twenty_word_essay,
                        "verdict": "supports", "comment": "给出公交效率和拥堵方面的简短理由。"}],
        "problems": [], "improvements": [],
    },
}
sources = figures.for_submission(short_submission)
check("task_numbers_kept_separate", "20" not in sources.values and "20" in sources.task_numbers
      and "250" in sources.task_numbers and not sources.year_spans,
      {"source_values": sorted(sources.values), "task_numbers": sorted(sources.task_numbers)})
for name, advice, should_remove in (
    ("word_count_not_twenty_years", "Twenty years later, public transport was more reliable.", True),
    ("minimum_not_two_hundred_fifty_years", "Two hundred and fifty years later, public transport was more reliable.", True),
    ("actual_word_count_plain_note", "原稿现在只有20，建议充分展开。", False),
    ("legitimate_word_target", "扩写到260词以上，并解释公交如何减少拥堵。", False),
):
    raw = copy.deepcopy(short_raw)
    raw["criteria"]["task"]["issues"] = [{"quote": twenty_word_essay,
        "comment": "建议进一步说明相关观点，并准确呈现已有信息。", "suggestion": advice}]
    result = review.normalize_evaluation(raw, short_submission)
    issue = result["criteria"][0]["issues"][0]
    copied = copytext.evaluation_text(result, {})
    assert_advice("twenty_word_full_pipeline:" + name, {
        "advice": advice, "normalized_issue": issue,
        "advice_in_copy": advice in copied,
        "removed_counts": result["suggestions_removed"],
        "removed_note_in_copy": copytext.REMOVED_NOTE in copied,
        "missing": sources.unsourced(advice),
    }, should_remove)

documented_source = "In 2000 sales rose; by 2020 sales fell."
known_conservative_result = {
    "source": documented_source,
    "confirmed_years": sorted(figures.confirmed_years(documented_source)),
    "missing": figures.Sources(documented_source).unsourced("Twenty years later"),
    "classification": "Already disclosed conservative false removal; accepted scope limitation, not a new blocker.",
}
report = {
    "source_head": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
    "passed": True,
    "scope": "Pure offline normalization and copy checks using committed redacted synthetic fixtures. No Key, student files, reasoning text, external network, model requests or business edits.",
    "historical_baseline_checks": historical_result["passed_baseline_checks"],
    "historical_additional_checks": historical_result["passed_additional_checks"],
    "positive_verification_checks": len(checks),
    "checks": checks,
    "findings": [],
    "closed": ["independent English counts no longer merge", "bus quantities no longer establish calendar durations",
               "20-word metadata and task minimum no longer source year durations"],
    "accepted_limitations": [known_conservative_result,
        {"forms": ["twice", "a third"], "classification": "Previously disclosed unsupported forms; not expanded in this review."}],
    "conclusion": "All specifically reported cases and retained positive controls pass individually. This reviewer scope no longer blocks the already-authorized high batch; parent must combine other review checks.",
    "network_attempts": original["network_attempts"],
}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed": True, "historical": 56 + 12, "positive_assertions": len(checks),
                  "head": report["source_head"], "output": str(output)}, ensure_ascii=False))
