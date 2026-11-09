#!/usr/bin/env python3
"""Offline audit of the conditional-only deletion reminder (no credentials or API).

Uses committed synthetic sample responses, the public normalizer and copy exporter.
The contract intentionally permits notes on negated or quoted deletion mentions.
"""

import argparse
import copy
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

    fixture = json.loads(
        (repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261107_prompt9.json").read_text()
    )
    checks, cases = [], []

    def check(name, passed, value=None):
        checks.append({"name": name, "passed": bool(passed), "observed": value})

    def neutral(sample):
        raw = json.loads(fixture["attempts"][sample][-1]["text"])
        for key in essay.CRITERIA:
            if isinstance(raw.get(key), dict):
                raw[key]["issues"] = []
        raw["priorities"] = ["保留主要比较和清晰的表达。"]
        if raw.get("argument"):
            raw["argument"]["problems"] = []
            raw["argument"]["improvements"] = []
        return raw

    long_quote = "delete the conclusion because " + "the overview is clear. " * 17
    scenarios = [
        ("plain_cn", "删去结尾段。", True),
        ("plain_en", "Delete the conclusion.", True),
        ("coordinated", "Delete the final paragraph and the first paragraph.", True),
        ("alternative", "Delete the final paragraph or the first paragraph.", True),
        ("shared_negation", "Do not delete the introduction or remove the conclusion.", True),
        ("property_negation", "This paragraph is not needed so delete the conclusion.", True),
        ("long_quoted_advice", f'Ignore the advice "{long_quote}" and keep it.', True),
        ("explicit_sentence", "删去最后一段；删去第三句中的“Country A”两个词。", True),
        ("quantity", "Delete two paragraphs.", True),
        ("unknown_ordinal", "删去第二十一段。", True),
        ("negated", "不要删去这一段。", True),
        ("please_remove", "Please remove this paragraph.", True),
        ("modal_cut", "You should cut this paragraph.", True),
        ("imperative_drop", "Drop this sentence.", True),
        ("omit", "Omit the repeated conclusion.", True),
        ("rewrite", "把这一段改写得更紧凑，保留主要比较。", False),
        ("example_cut", "改为：Building more roads can cut traffic.", False),
        ("example_drop", "改为：Car ownership dropped sharply.", False),
        ("example_remove", "改为：The policy can remove barriers to public transport.", False),
        ("compression", "压缩段落数量：把引言与概述合并。", False),
        ("concise", "精简表达，保留全部比较信息。", False),
    ]

    for ident, advice, expected in scenarios:
        for channel in ("criterion", "priority"):
            name = f"{ident}.{channel}"
            sub = copy.deepcopy(fixture["submissions"]["t1-no-image"])
            raw = neutral("t1-no-image")
            quote = essay.split_paragraphs(sub["essay_text"])[-1]
            if channel == "criterion":
                raw["coherence"]["issues"] = [
                    {"quote": quote, "comment": "需要核对表达是否重复。", "suggestion": advice}
                ]
            else:
                raw["priorities"] = [advice]
            before_raw, before_sub = copy.deepcopy(raw), copy.deepcopy(sub)
            result = review.normalize_evaluation(raw, sub)
            baseline = review.normalize_evaluation(neutral("t1-no-image"), sub)
            copied = copytext.evaluation_text(result, {})
            shown = (
                next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0][
                    "suggestion"
                ]
                if channel == "criterion"
                else result["priorities"][0]
            )
            note = (
                "（提示：这条建议提到删减。如果按删减修改，请核对修改后的字数："
                "原文 172 词，字数下限 150 词。本工具不推算删后字数。）"
            )
            check(name + ".exact_append", shown == advice + (note if expected else ""), shown)
            check(name + ".count", result["length_notes"] == int(expected))
            check(name + ".copy", shown in copied)
            check(name + ".no_remaining", not re.search(r"约剩|删后约|剩\s*\d+\s*词", copied))
            check(name + ".unmutated", raw == before_raw and sub == before_sub)
            check(
                name + ".scores",
                [c["band"] for c in result["criteria"]] == [c["band"] for c in baseline["criteria"]]
                and result["overall_band"] == baseline["overall_band"],
            )
            summary = [w for w in result["warnings"] if "条建议提到删减" in w]
            check(name + ".summary", len(summary) == int(expected))
            if expected:
                check(name + ".known_numbers", re.findall(r"\d+", note) == ["172", "150"])
            cases.append({"id": name, "expected_note": expected, "shown": shown})

    # Task 2 argument and optional-improvement paths, not only criterion/priority.
    for key in ("problems", "improvements"):
        sub = copy.deepcopy(fixture["submissions"]["t2-under-length"])
        raw = neutral("t2-under-length")
        quote = raw["argument"]["position"]["quote"]
        entry = {
            "quote": quote,
            "comment": "这里的表达可以进一步检查。",
            "suggestion": "删去这句话。",
        }
        if key == "problems":
            entry["type"] = "irrelevant"
        raw["argument"][key] = [entry]
        result = review.normalize_evaluation(raw, sub)
        copied = copytext.evaluation_text(result, {})
        entries = result["argument"][key]
        check(key + ".kept", len(entries) == 1, entries)
        check(key + ".known_count", "原文 97 词，字数下限 250 词" in copied)
        check(key + ".one_note", result["length_notes"] == 1)
        check(key + ".no_remaining", not re.search(r"约剩|删后约|剩\s*\d+\s*词", copied))

    # Gate-only synthetic paragraphs: explicitly accepts the inclusive equality boundary.
    for sizes, minimum, expected in (
        ((120, 120, 120), 250, True),
        ((100, 100, 100, 100), 250, False),
        ((100, 100, 100), 200, True),
        ((97,), 250, True),
        ((75, 75, 75, 75), 150, False),
    ):
        content = "\n\n".join(" ".join(["word"] * size) + "." for size in sizes)
        items = [{"issues": [{"suggestion": "删去一段。"}]}]
        count = deletion.annotate(items, None, [], content, minimum)
        text = items[0]["issues"][0]["suggestion"]
        name = f"gate.{sizes}.{minimum}"
        check(name, count == int(expected), text)
        if expected:
            check(name + ".numbers", re.findall(r"\d+", text) == [str(sum(sizes)), str(minimum)])
    check(
        "no_old_inference_api",
        not hasattr(deletion, "analyse") and not hasattr(review, "_deletion_target"),
    )
    output = {
        "source_head": subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip(),
        "cases": cases,
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "findings": [c for c in checks if not c["passed"]],
        "limits": [
            "No exhaustive linguistic coverage claim; negated/quoted deletion mentions intentionally may receive conditional notes.",
            "Only program-added notes are guaranteed not to infer remaining words; model-authored prose is preserved.",
            "No model, network, private configuration, browser, or production access.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: output[k] for k in ("source_head", "passed", "total", "findings")},
            ensure_ascii=False,
        )
    )
    return bool(output["findings"])


if __name__ == "__main__":
    raise SystemExit(main())
