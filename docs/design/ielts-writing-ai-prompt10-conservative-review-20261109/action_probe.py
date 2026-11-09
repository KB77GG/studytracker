#!/usr/bin/env python3
"""Offline audit of the conservative deletion-action contract.

Only committed synthetic formal responses are read. New ambiguous structures may
produce an unsure reminder; they must not produce an incorrect definite count.
No credentials, model calls, network or product mutations.
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
    from tools.ielts_writing_ai import copytext, deletion, essay, review

    bundle = repo / "docs/design/ielts-writing-ai-prompt9-high-20261107/continuation"
    data_path, calls_path = bundle / "run_data.json", bundle / "raw_calls.jsonl"
    data = json.loads(data_path.read_text())
    submission = next(s["submission"] for s in data["samples"] if s["id"] == "t1-no-image")
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    raw = json.loads(next(c["text"] for c in calls if c["sample"] == "t1-no-image"))
    paragraphs = essay.split_paragraphs(submission["essay_text"])
    total = essay.count_words(submission["essay_text"])
    checks, cases = [], []

    def check(name, passed, observed=None):
        checks.append({"name": name, "passed": bool(passed), "observed": observed})

    def neutral():
        value = copy.deepcopy(raw)
        for key in ("task", "coherence", "lexical", "grammar"):
            if isinstance(value.get(key), dict):
                value[key]["issues"] = []
        value["priorities"] = ["保留原稿中的关键比较信息。"]
        return value

    baseline = review.normalize_evaluation(neutral(), copy.deepcopy(submission))
    bands = [c["band"] for c in baseline["criteria"]]
    check(
        "fixture_counts",
        total == 172
        and essay.count_words(paragraphs[0]) == 18
        and essay.count_words(paragraphs[-1]) == 23,
    )
    long_quote = (
        "delete the conclusion because it restates the overview without adding a useful comparison. "
        "The summary already explains the main differences between the countries and the body paragraphs "
        "give the relevant figures for each year. A shorter response could be easier to follow, provided "
        "that the introduction and body paragraphs continue to describe the key features clearly."
    )
    check("long_quote_exceeds_mask_limit", len(long_quote) > 300, len(long_quote))
    # (id, advice, allowed states, exact remaining if sure, group, extra priority path)
    scenarios = [
        ("simple_delete", "Delete the conclusion.", ["sure"], 149, "control", False),
        ("negative_delete", "Do not delete the conclusion.", ["none"], None, "control", False),
        (
            "negative_adverb",
            "You should not simply delete the conclusion.",
            ["none"],
            None,
            "control",
            False,
        ),
        (
            "property_long_positive",
            "This paragraph is not necessary and you should delete the conclusion.",
            ["sure"],
            149,
            "control",
            False,
        ),
        (
            "period_independent",
            "Do not remove the introduction. Delete the conclusion.",
            ["sure"],
            149,
            "control",
            False,
        ),
        (
            "but_independent",
            "Do not delete the introduction but remove the conclusion.",
            ["sure"],
            149,
            "control",
            False,
        ),
        (
            "explicit_two_verbs",
            "Delete the final paragraph and delete the first paragraph.",
            ["sure"],
            131,
            "control",
            False,
        ),
        ("cn_explicit_two_verbs", "删去最后一段并删去第一段。", ["sure"], 131, "control", False),
        ("unknown_object", "Delete the paragraph about cars.", ["unsure"], None, "control", False),
        (
            "unsupported_partial",
            "Delete only part of the final paragraph.",
            ["unsure"],
            None,
            "control",
            False,
        ),
        (
            "unsupported_exception",
            "Delete the final paragraph except the last sentence.",
            ["unsure"],
            None,
            "control",
            False,
        ),
        (
            "cn_coordinated_conservative",
            "删去最后一段和第一段。",
            ["sure", "unsure"],
            131,
            "control",
            False,
        ),
        (
            "coordinated_last_first",
            "Delete the final paragraph and the first paragraph.",
            ["sure", "unsure"],
            131,
            "truncated_object",
            True,
        ),
        (
            "coordinated_intro_conclusion",
            "Delete the introduction and conclusion.",
            ["sure", "unsure"],
            131,
            "truncated_object",
            False,
        ),
        (
            "alternative_objects",
            "Delete the final paragraph or the first paragraph.",
            ["unsure"],
            None,
            "truncated_object",
            False,
        ),
        (
            "shared_negation",
            "Do not delete the introduction or remove the conclusion.",
            ["none", "unsure"],
            None,
            "negation_scope",
            True,
        ),
        (
            "shared_negation_cn",
            "不要删除首段或删去结尾段。",
            ["none", "unsure"],
            None,
            "negation_scope",
            False,
        ),
        (
            "repeated_negation",
            "Do not delete the introduction and do not remove the conclusion.",
            ["none"],
            None,
            "control",
            False,
        ),
        (
            "repeated_negation_cn",
            "不要删除首段，也不要删去结尾段。",
            ["none"],
            None,
            "control",
            False,
        ),
        (
            "property_short_positive",
            "This paragraph is not needed so delete the conclusion.",
            ["sure", "unsure"],
            149,
            "negation_scope",
            False,
        ),
        (
            "property_short_necessary",
            "This paragraph is not necessary so delete the conclusion.",
            ["sure", "unsure"],
            149,
            "negation_scope",
            False,
        ),
        (
            "quoted_short_double",
            'Ignore the advice "delete the conclusion" and keep it.',
            ["none"],
            None,
            "control",
            False,
        ),
        (
            "quoted_short_single",
            "Ignore the advice 'delete the conclusion' and keep it.",
            ["none"],
            None,
            "control",
            False,
        ),
        (
            "quoted_long_double",
            'Ignore the advice "' + long_quote + '" and keep the conclusion.',
            ["none", "unsure"],
            None,
            "quote_limit",
            True,
        ),
        (
            "quoted_long_single",
            "Ignore the advice '" + long_quote + "' and keep the conclusion.",
            ["none", "unsure"],
            None,
            "quote_limit",
            False,
        ),
        (
            "quoted_long_curly",
            "Ignore the advice “" + long_quote + "” and keep the conclusion.",
            ["none", "unsure"],
            None,
            "quote_limit",
            False,
        ),
        (
            "apostrophe_positive",
            "Delete the writer's final paragraph.",
            ["sure"],
            149,
            "control",
            False,
        ),
    ]
    for name, advice, allowed, remaining, group, priority in scenarios:
        for channel in (["criterion", "priority"] if priority else ["criterion"]):
            value, sub = neutral(), copy.deepcopy(submission)
            if channel == "priority":
                value["priorities"] = [advice]
            else:
                value["coherence"]["issues"] = [
                    {
                        "quote": paragraphs[-1],
                        "comment": "请先判断建议实际删除的内容，无法可靠判断时不能声称确定的剩余字数。",
                        "suggestion": advice,
                    }
                ]
            before = copy.deepcopy((value, sub))
            result = review.normalize_evaluation(value, sub)
            copied = copytext.evaluation_text(result, {})
            shown = (
                result["priorities"][0]
                if channel == "priority"
                else next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0][
                    "suggestion"
                ]
            )
            numbers = re.findall(r"按建议删去后约剩 (\d+) 词", shown)
            state = "sure" if numbers else "unsure" if "无法确定" in shown else "none"
            expected_numbers = [str(remaining)] if state == "sure" and remaining is not None else []
            case_id, start = f"{name}/{channel}", len(checks)
            check(
                case_id + ":allowed_state", state in allowed, {"actual": state, "allowed": allowed}
            )
            check(case_id + ":only_correct_number", numbers == expected_numbers, numbers)
            check(
                case_id + ":copy_only_correct_number",
                re.findall(r"按建议删去后约剩 (\d+) 词", copied) == expected_numbers,
            )
            check(case_id + ":copy_keeps_warning", shown in copied)
            check(case_id + ":advice_preserved", shown.startswith(advice))
            check(case_id + ":no_numeric_filter", result["suggestions_removed"]["total"] == 0)
            check(case_id + ":input_unchanged", (value, sub) == before)
            check(case_id + ":scores_unchanged", [c["band"] for c in result["criteria"]] == bands)
            diag = deletion.analyse(
                advice, paragraphs[-1] if channel == "criterion" else None, sub["essay_text"]
            )
            cases.append(
                {
                    "id": case_id,
                    "group": group,
                    "advice": advice,
                    "channel": channel,
                    "allowed_states": allowed,
                    "remaining_if_sure": remaining,
                    "actual_state": state,
                    "shown": shown,
                    "length_notes": result["length_notes"],
                    "copy_lines": [
                        line
                        for line in copied.splitlines()
                        if advice in line or "约剩" in line or "条建议提到删去" in line
                    ],
                    "diagnostic_not_oracle": (
                        None
                        if diag is None
                        else {"deleted_words": diag.words(sub["essay_text"]), "unsure": diag.unsure}
                    ),
                    "failed_checks": [c["name"] for c in checks[start:] if not c["passed"]],
                }
            )
    definitions = [
        (
            "truncated_object",
            [49, 52, 192, 204, 205],
            "Coordinated or alternative objects are silently truncated before the closed-list check",
            "and/or may join another target rather than start an irrelevant clause. The second target is discarded, so the apparently exact answer is 149 instead of 131, or a required reminder disappears. The alternative must be unsure. An unsure reminder is accepted for these new constructions.",
        ),
        (
            "negation_scope",
            [63, 65, 175, 181, 187, 189],
            "Negation is neither propagated across coordinated negative verbs nor separated from short property clauses",
            "Do not delete A or remove B is parsed as deleting B, while not needed so delete B is skipped. Repeated-negation, but-positive, long-property and sentence-boundary controls pass. The issue is action scope, not an unenumerated synonym.",
        ),
        (
            "quote_limit",
            [42, 43, 44, 165, 172],
            "Quoted commands longer than 300 characters become executable deletion actions",
            "The masking regex ignores a complete paired quote when its text exceeds 300 characters. An explicitly rejected quoted recommendation then adds a definite 149-word warning. The 371-character quoted comment survives normalisation without truncation; short quotes and possessive-apostrophe controls pass.",
        ),
    ]
    findings = []
    for group, lines, title, description in definitions:
        failed = [c["id"] for c in cases if c["group"] == group and c["failed_checks"]]
        if failed:
            findings.append(
                {
                    "priority": "P2",
                    "title": title,
                    "file": "tools/ielts_writing_ai/deletion.py",
                    "lines": lines,
                    "description": description,
                    "cases": failed,
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
        "privacy": "Committed synthetic samples only; no credentials, private reasoning, models or network.",
        "long_quote_length": len(long_quote),
        "cases": cases,
        "checks": checks,
        "findings": findings,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "all_checks_passed": all(c["passed"] for c in checks),
        "limits": [
            "New ambiguous structures explicitly allow conservative unsure results.",
            "Only established simple syntax requires an exact count.",
            "All cases run normalize_evaluation and production evaluation_text; no browser or real model.",
            "The tests specify the literal advice outcome rather than using helper output as their oracle.",
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
                "findings": len(findings),
                "failed_cases": sum(bool(c["failed_checks"]) for c in cases),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0 if output["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
