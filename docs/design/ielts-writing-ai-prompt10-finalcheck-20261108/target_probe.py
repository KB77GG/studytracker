#!/usr/bin/env python3
"""Offline target/position checks for 9576333; desired contracts, no model calls.

python target_probe.py --repo /path/to/repo --output /path/to/target_probe.json
Only committed synthetic-response fixtures are read. Product files are not edited.
"""

from __future__ import annotations

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

    def no_network(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline probe forbids network")

    sys.addaudithook(no_network)
    from tools.ielts_writing_ai import copytext, deletion, essay, review
    from tools.ielts_writing_ai.llm import parse_strict_json

    fixture_path = repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261107_prompt9.json"
    original_bytes = fixture_path.read_bytes()
    fixture = json.loads(original_bytes)
    sub = fixture["submissions"]["t1-no-image"]
    raw = parse_strict_json(fixture["attempts"]["t1-no-image"][-1]["text"])
    paragraphs = essay.split_paragraphs(sub["essay_text"])
    checks, cases = {}, []

    def check(key, passed):
        checks[key] = bool(passed)

    check(
        "source_layout",
        essay.count_words(sub["essay_text"]) == 172
        and [essay.count_words(p) for p in paragraphs] == [18, 36, 36, 59, 23],
    )
    check(
        "repeated_country_a_has_unique_occurrence_in_each_target",
        paragraphs[1].count("Country A") == 1 and paragraphs[-1].count("Country A") == 1,
    )

    clean_raw = copy.deepcopy(raw)
    for key in essay.CRITERIA:
        if isinstance(clean_raw.get(key), dict):
            clean_raw[key]["issues"] = []
    clean_raw["priorities"] = ["保留关键论点，并把比较关系表达清楚。"]
    baseline = review.normalize_evaluation(copy.deepcopy(clean_raw), copy.deepcopy(sub))

    def run_case(
        name, advice, *, expected_remaining=None, unsure=False, channel="criterion", group="control"
    ):
        value, submission = copy.deepcopy(clean_raw), copy.deepcopy(sub)
        issue = {
            "quote": paragraphs[-1],
            "comment": "这处文字可以酌情调整，但需要保留文章已有的关键信息。",
            "suggestion": advice,
        }
        if channel in {"criterion", "both"}:
            value["coherence"]["issues"] = [issue]
        if channel in {"priority", "both"}:
            value["priorities"] = [advice]
        before = copy.deepcopy((value, submission))
        result = review.normalize_evaluation(value, submission)
        copied = copytext.evaluation_text(result, {})
        displayed = []
        if channel in {"criterion", "both"}:
            displayed.append(
                next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0][
                    "suggestion"
                ]
            )
        if channel in {"priority", "both"}:
            displayed.append(result["priorities"][0])
        expected_nums = (
            [expected_remaining] * len(displayed)
            if expected_remaining is not None and expected_remaining < 150
            else []
        )
        actual_nums = [int(n) for s in displayed for n in re.findall(r"约剩 (-?\d+) 词", s)]
        copied_nums = [int(n) for n in re.findall(r"约剩 (-?\d+) 词", copied)]
        check(name + ".correct_remainder", actual_nums == expected_nums)
        check(name + ".copy_matches_expected", copied_nums == expected_nums)
        check(name + ".advice_retained", all(s.startswith(advice) for s in displayed))
        check(name + ".annotation_count", result["length_notes"] == len(expected_nums))
        check(name + ".input_not_mutated", before == (value, submission))
        check(
            name + ".scores_not_changed",
            [c["band"] for c in result["criteria"]] == [c["band"] for c in baseline["criteria"]]
            and result["overall_band"] == baseline["overall_band"],
        )
        if unsure:
            check(
                name + ".no_numeric_fallback",
                all("无法确定" in s and "没有计算字数" in s for s in displayed),
            )
        diagnostic = deletion.analyse(
            advice, None if channel == "priority" else paragraphs[-1], sub["essay_text"]
        )
        detail = (
            None
            if diagnostic is None
            else {
                "units": sorted(diagnostic.units),
                "passages": diagnostic.passages,
                "unsure": diagnostic.unsure,
                "deleted_word_count": diagnostic.words(sub["essay_text"]),
            }
        )
        cases.append(
            {
                "name": name,
                "group": group,
                "channel": channel,
                "advice": advice,
                "expected_remaining": expected_remaining,
                "actual_remainders": actual_nums,
                "displayed": displayed,
                "analysis": detail,
                "checks_failed": [
                    k for k, v in checks.items() if k.startswith(name + ".") and not v
                ],
            }
        )

    # Positives preserve previous fixes and distinguish overlap from separate positions.
    run_case("control_second_paragraph", "删去第二段。", expected_remaining=136)
    run_case("control_fifth_paragraph", "删去第五段。", expected_remaining=149)
    run_case("control_english_second", "Delete the second paragraph.", expected_remaining=136)
    run_case(
        "control_paragraph_sentence_overlap", "删去最后一段；删去最后一句。", expected_remaining=149
    )
    run_case(
        "control_partial_same_last_paragraph",
        "删去最后一段；删去最后一段中的“Country A”两个词。",
        expected_remaining=149,
    )
    run_case(
        "control_partial_same_second_paragraph",
        "删去第二段；删去第二段中的“Country A”两个词。",
        expected_remaining=136,
    )
    run_case(
        "control_distinct_whole_paragraphs", "删去首段；删去最后一段。", expected_remaining=131
    )
    run_case(
        "control_independent_channels", "删去最后一段。", expected_remaining=149, channel="both"
    )
    run_case("control_missing_ninth_cn", "删去第九段。", unsure=True)
    run_case("control_missing_ninth_en", "Delete paragraph 9.", unsure=True)

    # The same wording in different paragraphs means different word positions.
    run_case(
        "partial_second_not_last_cn",
        "删去最后一段；删去第二段中的“Country A”两个词。",
        expected_remaining=147,
        group="partial_position_lost",
    )
    run_case(
        "partial_second_not_last_en",
        'Delete the last paragraph; remove only "Country A" from the second paragraph.',
        expected_remaining=147,
        group="partial_position_lost",
    )
    run_case(
        "partial_last_not_second",
        "删去第二段；删去最后一段中的“Country A”两个词。",
        expected_remaining=134,
        group="partial_position_lost",
    )
    run_case(
        "partial_first_in_advice",
        "删去第二段中的“Country A”两个词；删去最后一段。",
        expected_remaining=147,
        group="partial_position_lost",
    )
    run_case(
        "partial_priority",
        "删去最后一段；删去第二段中的“Country A”两个词。",
        expected_remaining=147,
        group="partial_position_lost",
        channel="priority",
    )

    # Ordinary formatting of an explicit ordinal must never become an unspecified target.
    run_case(
        "spaced_existing_paragraph",
        "删去第 2 段。",
        expected_remaining=136,
        group="ordinal_falls_back",
    )
    run_case(
        "spaced_nonexistent_paragraph", "删去第 9 段。", unsure=True, group="ordinal_falls_back"
    )
    run_case(
        "english_nonexistent_ninth",
        "Delete the ninth paragraph.",
        unsure=True,
        group="ordinal_falls_back",
    )
    run_case(
        "english_numeric_existing",
        "Delete the 2nd paragraph.",
        expected_remaining=136,
        group="ordinal_falls_back",
    )
    run_case(
        "english_numeric_nonexistent",
        "Delete the 9th paragraph.",
        unsure=True,
        group="ordinal_falls_back",
    )
    check("fixture_bytes_unchanged", original_bytes == fixture_path.read_bytes())
    findings = []
    if any(c["checks_failed"] for c in cases if c["group"] == "partial_position_lost"):
        findings.append(
            {
                "priority": "P2",
                "title": "Explicit location of a partial deletion is lost before union accounting",
                "locations": [
                    "tools/ielts_writing_ai/deletion.py:245-248",
                    "tools/ielts_writing_ai/deletion.py:141-153",
                ],
                "cause": "The passage branch stores only the quote, discarding its paragraph qualifier. Layout.passage then selects an occurrence already in deleted words, even when the advice explicitly points to another paragraph.",
                "example": "Delete last paragraph (23 words) plus Country A in paragraph 2 (two distinct words): 172-23-2=147, but normalized suggestion and copy both claim149.",
                "controls": "Same passage inside the already removed last paragraph remains149; same passage inside removed second paragraph remains136; distinct whole paragraphs remain131.",
                "recommendation": "Resolve each action to original offsets while its explicit position is available; union those offsets. If a passage occurrence is ambiguous, preserve uncertainty rather than selecting an occurrence for minimum deletion.",
            }
        )
    if any(c["checks_failed"] for c in cases if c["group"] == "ordinal_falls_back"):
        findings.append(
            {
                "priority": "P2",
                "title": "Unrecognized explicit ordinals still silently fall back to the issue quote",
                "locations": [
                    "tools/ielts_writing_ai/deletion.py:73-80",
                    "tools/ielts_writing_ai/deletion.py:193-219",
                    "tools/ielts_writing_ai/deletion.py:266-269",
                ],
                "cause": "Only a small set of ordinal spellings produces named/invalid. A space-formatted Chinese ordinal or English numeric ordinal is returned as None, indistinguishable from no named target.",
                "example": "In five paragraphs, 删去第 9 段 and Delete the ninth paragraph both claim149 by deleting the final paragraph. 删去第 2 段 should leave136 but also claims149.",
                "controls": "Canonical 第九段 and paragraph9 now yield uncertainty; 第二段 and second paragraph correctly leave136.",
                "recommendation": "First detect that any explicit positional expression is present; unsupported or invalid positions must not fall back. Normalize ordinary spaces and ordinal notation separately from target existence.",
            }
        )
    output = {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "network_calls": 0,
        "actual_model_requests": 0,
        "fixture_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "cases": cases,
        "findings": findings,
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "failures": [k for k, v in checks.items() if not v],
        "scope": "Each optional suggestion is independent; cases intentionally do not sum deletions across channels. Public synthetic essays only.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: output[k] for k in ("checks_passed", "checks_total", "findings")},
            ensure_ascii=False,
        )
    )
    return 1 if output["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
