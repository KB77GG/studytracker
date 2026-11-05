#!/usr/bin/env python3
"""Offline recheck of the two numeric-provenance fixes and adjacent normal cases.

Usage: python figures_recheck.py --repo CHECKOUT --output RESULT.json
Uses the committed historical probe as an immutable baseline. No model/config/key
access; all new examples are explicitly synthetic source/advice mutations.
"""
import argparse
import contextlib
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
repo = args.repo.expanduser().resolve()
output = args.output.expanduser().resolve()
old_probe = repo / "docs/design/ielts-writing-ai-prompt8-review-20261105/figures_probe.py"
with tempfile.TemporaryDirectory(prefix="iwa-figures-recheck-") as temporary:
    baseline_output = Path(temporary) / "baseline.json"
    saved_argv = sys.argv
    sys.argv = [str(old_probe), "--repo", str(repo), "--output", str(baseline_output)]
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            old = runpy.run_path(str(old_probe), run_name="__main__")
    finally:
        sys.argv = saved_argv
    baseline = json.loads(baseline_output.read_text())

figures, evaluate = old["figures"], old["evaluate"]
checks = []


def check(name, condition, evidence=None):
    checks.append({"case": name, "passed": bool(condition), "evidence": evidence})
    assert condition, name


old_list = old["list_cases"]
check("original_forty_fifty_cases_closed", all([
    old_list["valid_arabic_advice_deleted"]["advice_in_copy"],
    old_list["valid_english_advice_deleted"]["advice_in_copy"],
    old_list["invented_sum_advice_kept"]["normalized_issue"]["suggestion_removed"],
    old_list["digit_source_does_not_allow_sum"]["normalized_issue"]["suggestion_removed"],
    old_list["valid_compound_control"]["advice_in_copy"],
]), old_list)
old_duration = old["duration_cases"]
check("original_quantity_without_preposition_case_closed", all([
    old_duration["non_year_counts_allow_duration"]["normalized_issue"]["suggestion_removed"],
    old_duration["genuine_years_allow_duration"]["advice_in_copy"],
    old_duration["wrong_span_still_rejected"]["normalized_issue"]["suggestion_removed"],
]), old_duration)

# Genuine compound numbers and coordinated tens remain ordinary positive controls.
for words, expected in (
    ("forty-two", ["42"]),
    ("one hundred and twenty", ["120"]),
    ("one hundred and twenty-five", ["125"]),
    ("one thousand two hundred", ["1200"]),
    ("two thousand and twenty", ["2020"]),
    ("a hundred", ["100"]),
    ("one million two hundred and thirty-four thousand five hundred and sixty-seven", ["1234567"]),
    ("forty and fifty", ["40", "50"]),
    ("forty fifty", ["40", "50"]),
):
    actual = [v for _start, _end, v in figures.split_en_numbers(words)]
    check("ordinary_number:" + words, actual == expected, {"text": words, "values": actual})
check("coordinated_percent_unit_preserved", figures.Sources("The values were forty and fifty percent.").unsourced("Use 40% and 50%.") == [])

# Adjacent versions of the original conjunction defect. The correct independent
# values and the erroneous merged value are tested through normalize + copy.
compound_cases = {
    "hundreds_valid_digits": evaluate("The buses carry 100 and 200 passengers respectively.",
        "The two buses carry one hundred and two hundred passengers respectively."),
    "hundreds_valid_words": evaluate("The buses carry one hundred and two hundred passengers respectively.",
        "The two buses carry 100 and 200 passengers respectively."),
    "hundreds_invented_merged_value": evaluate("One bus carries 10200 passengers.",
        "The two buses carry one hundred and two hundred passengers respectively."),
    "hundreds_digit_source_blocks_merged_value": evaluate("One bus carries 10200 passengers.",
        "The two buses carry 100 and 200 passengers respectively."),
    "thousands_valid_digits": evaluate("The two fleets contain 1000 and 2000 buses respectively.",
        "The two fleets contain one thousand and two thousand buses respectively."),
    "thousands_invented_sum": evaluate("One fleet contains 3000 buses.",
        "The two fleets contain one thousand and two thousand buses respectively."),
    "genuine_compound_sentence": evaluate("The train carries 125 passengers.",
        "The train carries one hundred and twenty-five passengers."),
}
compound_bug = all([
    compound_cases["hundreds_valid_digits"]["normalized_issue"]["suggestion_removed"],
    compound_cases["hundreds_valid_words"]["normalized_issue"]["suggestion_removed"],
    compound_cases["hundreds_invented_merged_value"]["advice_in_copy"],
    compound_cases["hundreds_digit_source_blocks_merged_value"]["normalized_issue"]["suggestion_removed"],
    compound_cases["thousands_valid_digits"]["normalized_issue"]["suggestion_removed"],
    compound_cases["thousands_invented_sum"]["advice_in_copy"],
    compound_cases["genuine_compound_sentence"]["advice_in_copy"],
])

# Prepositions are not intrinsically temporal. These are normal descriptions of
# quantities, with explicit buses units; none says when the counts were measured.
duration_cases = {
    "quantity_rose_from_to": evaluate("Twenty years later, there were 2020 buses.",
        "The number of buses rose from 2000 to 2020 buses."),
    "quantity_fleet_of": evaluate("Twenty years later, there were 2020 buses.",
        "The sample consisted of 2000 buses and another fleet of 2020 buses."),
    "quantity_between_range": evaluate("Twenty years later, there were 2020 buses.",
        "Between 2000 and 2020 buses were recorded in the two cities."),
    "quantity_without_temporal_adjacent_word": evaluate("Twenty years later, there were 2020 buses.",
        "In numbers of buses, City A and City B recorded 2000 and 2020 respectively."),
    "genuine_in_years": evaluate("Twenty years later, public transport was more reliable.",
        "Public transport was compared in 2000 and 2020."),
    "genuine_from_to_years": evaluate("Twenty years later, public transport was more reliable.",
        "The study ran from 2000 to 2020."),
    "wrong_duration_with_years": evaluate("Thirty years later, public transport was more reliable.",
        "The study ran from 2000 to 2020."),
}
for result in duration_cases.values():
    result["confirmed_years_from_source_sentence"] = sorted(figures.confirmed_years(result["source_sentence"]))
duration_bug = all([
    duration_cases["quantity_rose_from_to"]["advice_in_copy"],
    duration_cases["quantity_fleet_of"]["advice_in_copy"],
    duration_cases["quantity_between_range"]["advice_in_copy"],
    duration_cases["quantity_without_temporal_adjacent_word"]["normalized_issue"]["suggestion_removed"],
    duration_cases["genuine_in_years"]["advice_in_copy"],
    duration_cases["genuine_from_to_years"]["advice_in_copy"],
    duration_cases["wrong_duration_with_years"]["normalized_issue"]["suggestion_removed"],
])

report = {
    "source_head": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
    "scope": "Offline redacted historical synthetic fixtures and pure normalizers. No Key, student material, reasoning, config, model or network access. Historical files untouched.",
    "historical_baseline": baseline,
    "additional_passing_checks": checks,
    "passed_baseline_checks": baseline["passed_baseline_checks"],
    "passed_additional_checks": len(checks),
    "original_exact_examples_closed": True,
    "findings": [
        {"id": "conjunction_after_scale_still_merges_independent_counts", "priority": "P2",
         "reproduced": compound_bug,
         "source_lines": ["tools/ielts_writing_ai/figures.py:147", "tools/ielts_writing_ai/figures.py:173", "tools/ielts_writing_ai/figures.py:176"],
         "assessment": "Tens example fixed, same defect persists for coordinated hundreds/thousands: 100 and 200 becomes 10200, 1000 and 2000 becomes 3000. Legitimate advice is deleted and invented values survive full normalization and copy. Normal genuine compound numbers work.",
         "cases": compound_cases},
        {"id": "quantity_prepositions_still_confirm_fake_years", "priority": "P2",
         "reproduced": duration_bug,
         "source_lines": ["tools/ielts_writing_ai/figures.py:189", "tools/ielts_writing_ai/figures.py:202", "tools/ielts_writing_ai/figures.py:304"],
         "assessment": "The context rule treats from/to/of/between as positive year evidence even with explicit buses units. Normal count descriptions still authorize an invented 20-year duration. Genuine years and wrong-duration controls remain correct.",
         "cases": duration_cases},
    ],
    "recommendation": "Offline numeric-provenance review is not passed; do not claim the original two defect classes are closed or start a batch conditional on offline approval until resolved.",
    "limits": [
        "This is the same two defect classes in adjacent normal contexts, not an unbounded expansion to exotic numeral forms.",
        "The year rule may be heuristic, but an explicit buses quantity is not evidence of a calendar year. This test does not require general semantic truth verification.",
        "No new paid or network requests; historical fixture replay does not establish prompt .8 model quality.",
    ],
    "network_attempts": old["network_attempts"],
}
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"source_head": report["source_head"], "baseline": report["passed_baseline_checks"],
                  "additional": len(checks), "exact_old_cases_closed": True,
                  "remaining_P2": [f["id"] for f in report["findings"] if f["reproduced"]],
                  "output": str(output)}, ensure_ascii=False))
