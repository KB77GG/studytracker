#!/usr/bin/env python3
"""Compare old/new deletion modules inside current normalize -> copy, without editing product files.

Loads the old module using git show into an isolated module name and temporarily
patches review.deletion_lib only in this process. No credentials or network.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
import types
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default="c82ebbfc")
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))

    def no_network(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline comparison forbids network")

    sys.addaudithook(no_network)
    from tools.ielts_writing_ai import copytext, deletion, essay, review
    from tools.ielts_writing_ai.llm import parse_strict_json

    files = [
        repo / "tools/ielts_writing_ai" / name
        for name in (
            "deletion.py",
            "review.py",
            "copytext.py",
            "tests/fixtures/realcheck_20261107_prompt9.json",
        )
    ]
    before_hashes = {
        str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
    }
    old_source = subprocess.check_output(
        ["git", "show", args.baseline + ":tools/ielts_writing_ai/deletion.py"], cwd=repo, text=True
    )
    module_name = "tools.ielts_writing_ai._offline_baseline_deletion"
    old = types.ModuleType(module_name)
    old.__package__ = "tools.ielts_writing_ai"
    old.__file__ = "git:" + args.baseline + ":tools/ielts_writing_ai/deletion.py"
    sys.modules[module_name] = old
    exec(compile(old_source, old.__file__, "exec"), old.__dict__)
    fixture = json.loads(files[-1].read_bytes())
    source = fixture["submissions"]["t1-no-image"]
    raw = parse_strict_json(fixture["attempts"]["t1-no-image"][-1]["text"])
    for key in essay.CRITERIA:
        if isinstance(raw.get(key), dict):
            raw[key]["issues"] = []
    raw["priorities"] = ["保留关键论点，并把比较关系表达清楚。"]
    last = essay.split_paragraphs(source["essay_text"])[-1]
    cases = [
        (
            "partial_second_not_last_cn",
            "删去最后一段；删去第二段中的“Country A”两个词。",
            147,
            False,
        ),
        (
            "partial_second_not_last_en",
            'Delete the last paragraph; remove only "Country A" from the second paragraph.',
            147,
            False,
        ),
        (
            "threshold_partial_other_paragraph_173",
            "删去最后一段；删去第二段中的“Country A”两个词。",
            148,
            False,
        ),
        ("partial_last_not_second", "删去第二段；删去最后一段中的“Country A”两个词。", 134, False),
        ("partial_first_in_advice", "删去第二段中的“Country A”两个词；删去最后一段。", 147, False),
        ("true_partial_overlap", "删去最后一段；删去最后一段中的“Country A”两个词。", 149, False),
        ("true_unit_overlap", "删去最后一段；删去最后一句。", 149, False),
        ("different_whole_units", "删去首段；删去最后一段。", 131, False),
        (
            "negation_across_period",
            "Do not remove the introduction. Delete the conclusion.",
            149,
            False,
        ),
        ("spaced_existing_ordinal", "删去第 2 段。", 136, False),
        ("spaced_nonexistent_ordinal", "删去第 9 段。", None, True),
        ("english_ninth", "Delete the ninth paragraph.", None, True),
        ("canonical_nonexistent_ordinal", "删去第九段。", None, True),
    ]
    results = []
    try:
        for name, advice, expected_remaining, expected_unsure in cases:
            entry = {
                "name": name,
                "advice": advice,
                "expected_remaining": expected_remaining,
                "expected_unsure": expected_unsure,
            }
            for label, module in [("old", old), ("current", deletion)]:
                review.deletion_lib = module
                value, sub = copy.deepcopy(raw), copy.deepcopy(source)
                if name == "threshold_partial_other_paragraph_173":
                    sub["essay_text"] = sub["essay_text"].replace(
                        "The bar chart compares", "The bar chart clearly compares", 1
                    )
                    if "word_count" in sub:
                        sub["word_count"] = essay.count_words(sub["essay_text"])
                neutral_result = review.normalize_evaluation(copy.deepcopy(raw), copy.deepcopy(sub))
                value["coherence"]["issues"] = [
                    {
                        "quote": last,
                        "comment": "这处文字可以酌情调整，但需要保留文章已有的关键信息。",
                        "suggestion": advice,
                    }
                ]
                original_input = copy.deepcopy((value, sub))
                result = review.normalize_evaluation(value, sub)
                copied = copytext.evaluation_text(result, {})
                shown = next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0][
                    "suggestion"
                ]
                numbers = [int(n) for n in re.findall(r"约剩 (-?\d+) 词", shown)]
                copy_numbers = [int(n) for n in re.findall(r"约剩 (-?\d+) 词", copied)]
                expected_numbers = [] if expected_remaining is None else [expected_remaining]
                unsure = "无法确定" in shown and "没有计算字数" in shown
                analyse = module.analyse(advice, last, sub["essay_text"])
                entry[label] = {
                    "shown": shown,
                    "source_word_count": essay.count_words(sub["essay_text"]),
                    "same_source_baseline_scores_unchanged": [c["band"] for c in result["criteria"]]
                    == [c["band"] for c in neutral_result["criteria"]]
                    and result["overall_band"] == neutral_result["overall_band"],
                    "actual_remainders": numbers,
                    "copy_remainders": copy_numbers,
                    "unsure": unsure,
                    "matches_desired_behavior": numbers == copy_numbers == expected_numbers
                    and unsure == expected_unsure,
                    "raw_and_submission_unchanged": original_input == (value, sub),
                    "bands": [c["band"] for c in result["criteria"]],
                    "overall_band": result["overall_band"],
                    "analysis": (
                        None
                        if analyse is None
                        else {
                            "units": sorted(analyse.units),
                            "passages": analyse.passages,
                            "unsure": analyse.unsure,
                            "word_count": analyse.words(sub["essay_text"]),
                        }
                    ),
                }
            was_good, is_good = (
                entry["old"]["matches_desired_behavior"],
                entry["current"]["matches_desired_behavior"],
            )
            entry["classification"] = {
                (True, False): "observable_regression",
                (False, False): "preexisting_gap",
                (False, True): "fixed",
                (True, True): "unchanged_correct",
            }[(was_good, is_good)]
            entry["scores_unchanged_between_versions"] = (
                entry["old"]["bands"] == entry["current"]["bands"]
                and entry["old"]["overall_band"] == entry["current"]["overall_band"]
            )
            results.append(entry)
    finally:
        review.deletion_lib = deletion
        del sys.modules[module_name]
    after_hashes = {
        str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
    }
    report = {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "baseline_head": subprocess.check_output(
            ["git", "rev-parse", args.baseline], cwd=repo, text=True
        ).strip(),
        "baseline_module_sha256": hashlib.sha256(old_source.encode()).hexdigest(),
        "method": "Only deletion module changed in process; current review normalization and copy formatter remain fixed.",
        "network_calls": 0,
        "actual_model_requests": 0,
        "product_and_fixture_hashes": before_hashes,
        "files_unchanged": before_hashes == after_hashes,
        "results": results,
        "all_inputs_unchanged": all(
            r[v]["raw_and_submission_unchanged"] for r in results for v in ("old", "current")
        ),
        "all_scores_unchanged": all(r["scores_unchanged_between_versions"] for r in results),
        "all_same_source_baseline_scores_unchanged": all(
            r[v]["same_source_baseline_scores_unchanged"]
            for r in results
            for v in ("old", "current")
        ),
        "caveat": "Old partial deletion results are numerically correct in the distinct-position examples because old words() blindly sums texts. The old module also discards the qualifier and has no sound positional resolution; this is an observable output regression, not proof that the old targeting logic was correct.",
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "files_unchanged": report["files_unchanged"],
                "all_inputs_unchanged": report["all_inputs_unchanged"],
                "all_scores_unchanged": report["all_scores_unchanged"],
                "cases": [
                    {k: r[k] for k in ("name", "classification")}
                    | {
                        "old": r["old"]["actual_remainders"],
                        "current": r["current"]["actual_remainders"],
                    }
                    for r in results
                ],
            },
            ensure_ascii=False,
        )
    )
    return (
        0
        if report["files_unchanged"]
        and report["all_inputs_unchanged"]
        and report["all_scores_unchanged"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
