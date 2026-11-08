#!/usr/bin/env python3
"""Offline prompt .10 final intent recheck; no model or network calls.

Run --repo PATH --output FILE. Assertions express the intended behaviour,
not current helper output. Uses committed synthetic samples only.
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
    from tools.ielts_writing_ai import copytext, deletion, essay, review

    bundle = repo / "docs/design/ielts-writing-ai-prompt9-high-20261107/continuation"
    data_path, calls_path = bundle / "run_data.json", bundle / "raw_calls.jsonl"
    data = json.loads(data_path.read_text())
    sub = next(s["submission"] for s in data["samples"] if s["id"] == "t1-no-image")
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    raw = json.loads(next(c["text"] for c in calls if c["sample"] == "t1-no-image"))
    final_paragraph = essay.split_paragraphs(sub["essay_text"])[-1]
    total = essay.count_words(sub["essay_text"])
    checks, cases = [], []

    def check(name, passed, observed=None):
        checks.append({"name": name, "passed": bool(passed), "observed": observed})

    def neutral():
        value = copy.deepcopy(raw)
        for key in ("task", "coherence", "lexical", "grammar"):
            if isinstance(value.get(key), dict):
                value[key]["issues"] = []
        value["priorities"] = ["保留原稿的关键比较信息。"]
        return value

    baseline = review.normalize_evaluation(neutral(), copy.deepcopy(sub))
    bands = [c["band"] for c in baseline["criteria"]]
    check("fixture_counts", total == 172 and essay.count_words(final_paragraph) == 23)
    scenarios = [
        ("affirmative", "Delete the conclusion.", 23, "control"),
        ("negative_ascii", "Don't delete the conclusion.", 0, "control"),
        ("negative_curly", "Don’t delete the conclusion.", 0, "control"),
        ("negative_shouldnt", "You shouldn't delete the conclusion.", 0, "control"),
        ("negative_cn", "别删去结尾段。", 0, "control"),
        ("negative_cannot", "You cannot delete the conclusion.", 0, "control"),
        (
            "negative_then_positive_period",
            "Do not remove the introduction. Delete the conclusion.",
            23,
            "sentence_boundary",
        ),
        (
            "negative_then_positive_semicolon",
            "Do not remove the introduction; delete the conclusion.",
            23,
            "control",
        ),
        (
            "positive_then_negative_period",
            "Delete the conclusion. Do not remove the introduction.",
            23,
            "sentence_boundary",
        ),
        (
            "positive_then_negative_semicolon",
            "Delete the conclusion; do not remove the introduction.",
            23,
            "control",
        ),
        (
            "quoted_words_then_positive_period",
            "Do not remove the words 'In summary'. Delete the conclusion.",
            23,
            "sentence_boundary",
        ),
        (
            "neutral_then_positive_period",
            "The conclusion repeats the overview. Delete the conclusion.",
            23,
            "control",
        ),
        (
            "negative_property_not_action",
            "This paragraph is not necessary and you should delete the conclusion.",
            23,
            "unrelated_negation",
        ),
        (
            "negative_need_not_action",
            "You do not need the conclusion so remove the conclusion.",
            23,
            "unrelated_negation",
        ),
        (
            "negative_retain_not_action",
            "There is no need to retain the conclusion so delete the conclusion.",
            23,
            "unrelated_negation",
        ),
        ("negative_cn_retain_not_action", "不要保留这一段并删去结尾段。", 23, "unrelated_negation"),
        ("negative_cn_repeat_not_action", "不要重复概述而应删去结尾段。", 23, "unrelated_negation"),
        ("negative_cn_separate", "不要保留这一段，删去结尾段。", 23, "control"),
        ("rejected_single_quote", "Ignore 'delete the conclusion' and keep it.", 0, "control"),
        ("rejected_curly_quote", "Ignore ‘delete the conclusion’ and keep it.", 0, "control"),
        (
            "quoted_negation_then_positive",
            "Ignore 'do not delete this paragraph' and delete the conclusion.",
            23,
            "control",
        ),
        ("possessive_apostrophe", "Remove the writer's concluding paragraph.", 23, "control"),
        ("phrase_single_quote", "Remove only 'In summary' from this sentence.", 2, "control"),
        ("phrase_curly_quote", "Remove only ‘In summary’ from this sentence.", 2, "control"),
    ]
    for name, advice, removed, group in scenarios:
        # Extra priority-path checks cover the two structural findings, without
        # assuming that every relative target can be located without an issue quote.
        channels = ["criterion"]
        if name in ("negative_then_positive_period", "negative_property_not_action", "affirmative"):
            channels.append("priority")
        for channel in channels:
            value = neutral()
            if channel == "priority":
                value["priorities"] = [advice]
            else:
                value["coherence"]["issues"] = [
                    {
                        "quote": final_paragraph,
                        "comment": "应先核对这条建议实际删去的内容，再确认是否低于字数下限。",
                        "suggestion": advice,
                    }
                ]
            submission = copy.deepcopy(sub)
            before = copy.deepcopy((value, submission))
            result = review.normalize_evaluation(value, submission)
            copied = copytext.evaluation_text(result, {})
            shown = (
                result["priorities"][0]
                if channel == "priority"
                else next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0][
                    "suggestion"
                ]
            )
            expected_remaining = total - removed
            expected_note = int(expected_remaining < 150)
            case_id = f"{name}/{channel}"
            start = len(checks)
            check(
                case_id + ":note_count",
                result["length_notes"] == expected_note,
                result["length_notes"],
            )
            check(
                case_id + ":exact_remaining",
                (
                    (f"约剩 {expected_remaining} 词" in shown)
                    if expected_note
                    else "约剩" not in shown
                ),
                shown,
            )
            check(case_id + ":not_unsure", "无法确定" not in shown, shown)
            check(case_id + ":copy_count", copied.count("约剩 149 词") == expected_note)
            check(case_id + ":advice_preserved", shown.startswith(advice))
            check(case_id + ":no_figure_removal", result["suggestions_removed"]["total"] == 0)
            check(case_id + ":input_unchanged", (value, submission) == before)
            check(case_id + ":scores_unchanged", [c["band"] for c in result["criteria"]] == bands)
            diagnostic = deletion.analyse(
                advice, final_paragraph if channel == "criterion" else None, sub["essay_text"]
            )
            cases.append(
                {
                    "id": case_id,
                    "group": group,
                    "advice": advice,
                    "channel": channel,
                    "expected_removed_words": removed,
                    "expected_remaining": expected_remaining,
                    "expected_note": expected_note,
                    "shown": shown,
                    "length_notes": result["length_notes"],
                    "copy_relevant_lines": [
                        line
                        for line in copied.splitlines()
                        if advice in line or "约剩" in line or "条建议提到删去" in line
                    ],
                    "diagnostic_not_oracle": (
                        None
                        if diagnostic is None
                        else {
                            "removed_words": diagnostic.words(sub["essay_text"]),
                            "unsure": diagnostic.unsure,
                        }
                    ),
                    "failed_checks": [c["name"] for c in checks[start:] if not c["passed"]],
                }
            )
    failures = [c for c in cases if c["failed_checks"]]
    findings = []
    if failures:
        findings.append(
            {
                "priority": "P2",
                "title": "Negation and target scope leak across independent actions",
                "file": "tools/ielts_writing_ai/deletion.py",
                "lines": [49, 222, 224, 239, 240, 241],
                "description": "The splitter omits English full stops and analyse processes only the first deletion verb. Negation is any earlier negative token, even when it negates retaining/necessity rather than deleting. Thus ordinary affirmative conclusion-deletion advice gets no 149-word warning; reversing the sentences can instead produce a spurious ambiguity. Semicolon and single-positive controls pass. The advice survives normalization and copying unchanged but lacks its required length warning.",
                "case_ids": [c["id"] for c in failures],
            }
        )
    output = {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "source_hashes": {
            str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (data_path, calls_path, repo / "tools/ielts_writing_ai/deletion.py")
        },
        "privacy": "Committed synthetic formal outputs only; no secrets, private reasoning, model or network calls.",
        "fixture_words": total,
        "cases": cases,
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "all_checks_passed": all(c["passed"] for c in checks),
        "findings": findings,
        "limits": [
            "Targeted common advice syntax, not exhaustive natural-language analysis.",
            "All scenarios use production normalize_evaluation and evaluation_text; no browser rendering.",
            "Expected deletion is specified from the literal advice, never inferred from product helper output.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": output["passed"],
                "total": output["total"],
                "cases": len(cases),
                "failed_cases": len(failures),
                "findings": len(findings),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if output["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
