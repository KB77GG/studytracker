"""Offline percentage-point review using public synthetic answers only."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo))
    sys.dont_write_bytecode = True
    from tools.ielts_writing_ai import copytext, figures, review

    rows = []

    def check(name, actual, expected):
        rows.append(dict(name=name, ok=actual == expected, actual=actual, expected=expected))

    data = json.loads((args.evidence / "run_data.json").read_text())
    sample = next(s for s in data["samples"] if s["id"] == "t1-no-image")
    responses = json.loads((args.evidence / "formal_responses.json").read_text())
    formal = next(r for r in responses if r["sample"] == "t1-no-image")
    raw = json.loads(formal["formal_text"])
    submission = sample["submission"]
    source_before = json.dumps(submission, sort_keys=True)
    result = review.normalize_evaluation(copy.deepcopy(raw), submission)
    previous = sample["generations"]["evaluate"]["result"]
    target = next(p for p in raw["priorities"] if "5 percentage points" in p)
    check("real.priority_retained", target in result["priorities"], True)
    check("real.copy_retained", target in copytext.evaluation_text(result, {}), True)
    check("real.previous_removal_count", previous["suggestions_removed"]["total"], 1)
    check("real.current_removal_count", result["suggestions_removed"]["total"], 0)
    check("real.criteria_unchanged", result["criteria"], previous["criteria"])
    for key in ("overall_band", "overall_state", "consistency_issues", "length_notes"):
        check(f"real.{key}_unchanged", result[key], previous[key])
    check("real.submission_unmodified", json.dumps(submission, sort_keys=True), source_before)

    # Baseline controls: ordinary percentages remain exact-type checks.
    sources = figures.Sources("The percentage rose from 70% to 75%.")
    for advice in (
        "It rose by 5 percentage points.",
        "It rose by five percentage points.",
        "It saw a 5-percentage-point rise.",
        "上升了 5 个百分点。",
    ):
        check("controls.keep." + advice, sources.unsourced(advice), [])
    for advice, expected in (
        ("It rose by 5%.", ["5%"]),
        ("It rose by 7 percentage points.", ["7 percentage points"]),
        ("上升了 7 个百分点。", ["7 个百分点"]),
    ):
        check("controls.reject." + advice, sources.unsourced(advice), expected)
    stated = figures.Sources("The difference was zero percentage points.")
    check("controls.explicit_zero", stated.unsourced("0 percentage points"), [])
    decimal = figures.Sources("The share rose from 10.01% to 10.03%.")
    check("controls.two_decimal_gap", decimal.unsourced("0.02 percentage points"), [])

    # Test a small pure-arithmetic boundary independently of entity/claim semantics.
    arithmetic_cases = (
        (
            "zero_difference",
            "The figure was 70% in 2000 and 70% in 2020.",
            "The change was zero percentage points.",
            [],
        ),
        (
            "precise_difference",
            "The figure rose from 70.125% to 75.25%.",
            "The figure rose by exactly 5.125 percentage points.",
            [],
        ),
        (
            "rounded_wrong_exact_difference",
            "The figure rose from 70.125% to 75.25%.",
            "The figure rose by exactly 5.12 percentage points.",
            ["5.12 percentage points"],
        ),
        (
            "small_nonzero_difference",
            "The figure rose from 10.001% to 10.005%.",
            "The figure rose by exactly 0.004 percentage points.",
            [],
        ),
        (
            "small_nonzero_false_zero",
            "The figure rose from 10.001% to 10.005%.",
            "The figure changed by exactly zero percentage points.",
            ["zero percentage points"],
        ),
    )
    arithmetic = []
    for name, source, advice, expected in arithmetic_cases:
        src = figures.Sources(source)
        got = src.unsourced(advice)
        check("arithmetic." + name, got, expected)
        arithmetic.append(
            dict(
                name=name,
                source=source,
                advice=advice,
                derived_points=sorted(src.point_spans),
                missing=got,
                expected_missing=expected,
            )
        )

    # Carry deterministic failures through the real normalizer and copy formatter.
    # The synthetic article's percentages are replaced consistently in raw quotes too.
    def replay_with_percentages(mapping, advice):
        sub_text = json.dumps(submission, ensure_ascii=False)
        raw_text = json.dumps(raw, ensure_ascii=False)
        for old, new in mapping.items():
            sub_text = sub_text.replace(old, new)
            raw_text = raw_text.replace(old, new)
        sub, answer = json.loads(sub_text), json.loads(raw_text)
        answer["priorities"] = [advice]
        normalized = review.normalize_evaluation(answer, sub)
        return normalized, copytext.evaluation_text(normalized, {})

    pipeline = []
    for name, mapping, advice, expected_retained in (
        (
            "zero_difference",
            {"75%": "70%"},
            "Write that Country A changed by zero percentage points between the two years.",
            True,
        ),
        (
            "precise_difference",
            {"70%": "70.125%", "75%": "75.25%"},
            "Write that Country A rose by exactly 5.125 percentage points.",
            True,
        ),
        (
            "rounded_wrong_exact_difference",
            {"70%": "70.125%", "75%": "75.25%"},
            "Write that Country A rose by exactly 5.12 percentage points.",
            False,
        ),
        (
            "small_nonzero_false_zero",
            {"70%": "10.001%", "75%": "10.005%"},
            "Write that Country A changed by exactly zero percentage points.",
            False,
        ),
    ):
        normalized, copied = replay_with_percentages(mapping, advice)
        retained = advice in normalized["priorities"]
        copied_advice = advice in copied
        check("pipeline.retained." + name, retained, expected_retained)
        check("pipeline.copy." + name, copied_advice, expected_retained)
        pipeline.append(
            dict(
                name=name,
                advice=advice,
                retained=retained,
                copied=copied_advice,
                expected_retained=expected_retained,
                removed=normalized["suggestions_removed"],
            )
        )

    # This is a declared source-only limitation, deliberately not a new defect.
    arbitrary = figures.Sources("Country A rose from 70% to 75%. Country B rose from 20% to 30%.")
    wrong_entity = "Country A rose by 10 percentage points."
    limitation = dict(
        advice=wrong_entity,
        missing=arbitrary.unsourced(wrong_entity),
        explanation="10 is a numerical difference in the input, but for Country B, not A. "
        "This matches the documented source-only contract; it does not verify the claim.",
    )
    check("declared_limit.source_only", limitation["missing"], [])

    findings = [
        dict(
            id="zero_gap_lost",
            severity="P2",
            location="tools/ielts_writing_ai/figures.py:365-368",
            cause="Unique-percentage set discards repeated equal observations, so zero is never derived.",
            reproduced=any(
                not row["ok"] and row["name"] == "arithmetic.zero_difference" for row in rows
            ),
        ),
        dict(
            id="forced_two_decimal_gap",
            severity="P2",
            location="tools/ielts_writing_ai/figures.py:367",
            cause="round(b-a, 2) changes the source difference, rejecting exact arithmetic and allowing rounded or zero differences as exact.",
            reproduced=any(
                not row["ok"] and row["name"] == "arithmetic.precise_difference" for row in rows
            ),
        ),
    ]
    report = dict(
        head=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.repo, text=True
        ).strip(),
        source_sha256=hashlib.sha256(
            (args.repo / "tools/ielts_writing_ai/figures.py").read_bytes()
        ).hexdigest(),
        real_model_calls=0,
        private_material_read=False,
        passed=sum(row["ok"] for row in rows),
        total=len(rows),
        checks=rows,
        arithmetic=arithmetic,
        pipeline=pipeline,
        declared_limitation=limitation,
        findings=findings,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("head", "passed", "total", "findings")}))
    return 0 if all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
