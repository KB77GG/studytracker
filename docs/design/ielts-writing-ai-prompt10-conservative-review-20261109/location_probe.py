#!/usr/bin/env python3
"""Conservative deletion location checks through normalize -> copy.

A correct numeric remainder OR explicit uncertainty passes whenever the target can be
read. Unsupported/ambiguous targets must never acquire a guessed number. No model,
network, private configuration, or student data; only committed synthetic fixtures.
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

    path = repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261107_prompt9.json"
    original_bytes = path.read_bytes()
    fixture = json.loads(original_bytes)
    submission = fixture["submissions"]["t1-no-image"]
    raw = parse_strict_json(fixture["attempts"]["t1-no-image"][-1]["text"])
    for key in essay.CRITERIA:
        if isinstance(raw.get(key), dict):
            raw[key]["issues"] = []
    raw["priorities"] = ["保留关键论点，并把比较关系表达清楚。"]
    paragraphs = essay.split_paragraphs(submission["essay_text"])
    sentences = essay.split_sentences(submission["essay_text"])
    checks, cases = {}, []

    def check(name, passed):
        checks[name] = bool(passed)

    check("fixture_172_words", essay.count_words(submission["essay_text"]) == 172)
    check("five_paragraphs_eight_sentences", len(paragraphs) == 5 and len(sentences) == 8)
    check(
        "third_sentence_has_country_a_but_first_has_none",
        sentences[2].text.count("Country A") == 1 and "Country A" not in sentences[0].text,
    )

    def run_case(
        name, advice, expected=None, *, group="control", quote=None, priority=False, threshold=False
    ):
        value, sub = copy.deepcopy(raw), copy.deepcopy(submission)
        if threshold:
            sub["essay_text"] = sub["essay_text"].replace(
                "The bar chart compares", "The bar chart clearly compares", 1
            )
            if "word_count" in sub:
                sub["word_count"] = essay.count_words(sub["essay_text"])
        baseline = review.normalize_evaluation(copy.deepcopy(raw), copy.deepcopy(sub))
        target_quote = quote or paragraphs[-1]
        if priority:
            value["priorities"] = [advice]
        else:
            value["coherence"]["issues"] = [
                {
                    "quote": target_quote,
                    "comment": "这处文字可以酌情调整，但需要保留文章已有的关键信息。",
                    "suggestion": advice,
                }
            ]
        before = copy.deepcopy((value, sub))
        result = review.normalize_evaluation(value, sub)
        copied = copytext.evaluation_text(result, {})
        if priority:
            shown = result["priorities"][0]
            removed = False
        else:
            issue = next(c for c in result["criteria"] if c["key"] == "coherence")["issues"][0]
            shown = issue["suggestion"]
            removed = issue.get("suggestion_removed")
        nums = [int(n) for n in re.findall(r"约剩 (-?\d+) 词", shown)]
        copy_nums = [int(n) for n in re.findall(r"约剩 (-?\d+) 词", copied)]
        unsure = "无法确定" in shown and "没有计算字数" in shown
        numeric_expected = [expected] if expected is not None and expected < 150 else []
        # Deliberately accept the implementation's promised conservative outcome.
        correct = (not nums and unsure) or (
            expected is not None and nums == numeric_expected and (expected >= 150 or bool(nums))
        )
        check(name + ".correct_count_or_explicit_uncertainty", correct)
        check(name + ".copy_matches_result", copy_nums == nums and shown in copied)
        check(name + ".advice_not_filtered", not removed and shown.startswith(advice))
        check(name + ".annotation_count", result["length_notes"] == len(nums))
        check(name + ".no_number_when_unsure", not unsure or not nums)
        check(name + ".input_unchanged", before == (value, sub))
        check(
            name + ".scores_unchanged",
            [c["band"] for c in result["criteria"]] == [c["band"] for c in baseline["criteria"]]
            and result["overall_band"] == baseline["overall_band"],
        )
        found = deletion.analyse(advice, None if priority else target_quote, sub["essay_text"])
        detail = (
            None
            if found is None
            else {
                "units": sorted(found.units),
                "passages": found.passages,
                "unsure": found.unsure,
                "deleted_words": found.words(sub["essay_text"]),
                "remaining": essay.count_words(sub["essay_text"]) - found.words(sub["essay_text"]),
            }
        )
        cases.append(
            {
                "name": name,
                "group": group,
                "advice": advice,
                "issue_quote": None if priority else target_quote,
                "channel": "priority" if priority else "criterion",
                "source_words": essay.count_words(sub["essay_text"]),
                "expected_remaining_or_unsure": expected,
                "shown": shown,
                "actual_remainders": nums,
                "uncertainty": unsure,
                "analysis": detail,
                "failed_checks": [
                    k for k, v in checks.items() if k.startswith(name + ".") and not v
                ],
            }
        )

    # Existing correct and conservative contracts are retained.
    run_case("control_last_paragraph", "删去最后一段。", 149)
    run_case("control_spaced_second", "删去第 2 段。", 136)
    run_case("control_english_ordinal", "Delete the second paragraph.", 136)
    run_case("control_unit_overlap", "删去最后一段；删去最后一句。", 149)
    run_case(
        "control_scoped_partial_other_paragraph",
        "删去最后一段；删去第二段中的“Country A”两个词。",
        147,
    )
    run_case(
        "control_scoped_partial_same_paragraph",
        "删去最后一段；删去最后一段中的“Country A”两个词。",
        149,
    )
    run_case(
        "control_partial_this_sentence",
        'Delete the last paragraph; remove only "Country A" from this sentence.',
        149,
    )
    run_case("control_unknown_description", "删去复杂的段落。")
    run_case("control_missing_ninth", "删去第九段。")
    run_case("control_missing_nineteenth", "删去第十九段。")
    run_case("control_repeated_unscoped_quote", "删去“Country A”两个词。")
    run_case(
        "control_partial_last_sentence_matches_quote",
        "删去最后一段；删去最后一句中的“Country A”两个词。",
        149,
    )

    # Explicit sentence qualifiers must not be overwritten by the issue quote.
    run_case(
        "first_sentence_has_no_such_words_cn",
        "删去最后一段；删去第一句中的“Country A”两个词。",
        group="sentence_location_lost",
    )
    run_case(
        "first_sentence_has_no_such_words_en",
        'Delete the last paragraph; remove only "Country A" from the first sentence.',
        group="sentence_location_lost",
    )
    run_case(
        "third_sentence_distinct_position",
        "删去最后一段；删去第三句中的“Country A”两个词。",
        147,
        group="sentence_location_lost",
    )
    run_case(
        "last_sentence_not_issue_quote",
        "删去第二段；删去最后一句中的“Country A”两个词。",
        134,
        group="sentence_location_lost",
        quote=sentences[2].text,
    )
    run_case(
        "third_sentence_threshold_173",
        "删去最后一段；删去第三句中的“Country A”两个词。",
        148,
        group="sentence_location_lost",
        threshold=True,
    )
    run_case(
        "sentence_priority_is_conservative",
        "删去最后一段；删去第三句中的“Country A”两个词。",
        147,
        priority=True,
    )

    # Counts of units are not positions; without targets, a number is not justified.
    run_case("two_paragraphs_quantity_en", "Delete two paragraphs.", group="quantity_as_position")
    run_case("two_paragraphs_quantity_digit", "Delete 2 paragraphs.", group="quantity_as_position")
    run_case("two_paragraphs_quantity_cn", "删去两段。", group="quantity_as_position")
    run_case("three_paragraphs_quantity_cn", "删去三个段落。", group="quantity_as_position")
    run_case(
        "quantity_priority_en",
        "Delete two paragraphs.",
        group="quantity_as_position",
        priority=True,
    )

    # Accepted Chinese ordinal tokens beyond nineteen still require numeric resolution.
    run_case("missing_twentieth", "删去第二十段。", group="unparsed_ordinal_fallback")
    run_case("missing_twenty_first", "删去第二十一段。", group="unparsed_ordinal_fallback")
    run_case(
        "unparsed_ordinal_priority_is_conservative",
        "删去第二十段。",
        priority=True,
        group="unparsed_ordinal_fallback",
    )
    check("fixture_bytes_unchanged", path.read_bytes() == original_bytes)
    findings = []
    descriptions = {
        "sentence_location_lost": {
            "title": "Partial deletion ignores its explicit sentence location",
            "locations": [
                "tools/ielts_writing_ai/deletion.py:388-405",
                "tools/ielts_writing_ai/deletion.py:397-398",
            ],
            "cause": "Unlike paragraph scope, the sentence branch always resolves the issue quote and never checks first/last/ordinal sentence qualifiers. Explicit targets are silently overwritten.",
            "example": "173-word essay: delete final paragraph23 plus Country A in sentence3 (two separate words), expected148 or uncertainty; current merges into final sentence and computes150, so the warning disappears.",
        },
        "quantity_as_position": {
            "title": "Number of paragraphs is interpreted as a paragraph ordinal or falls back",
            "locations": [
                "tools/ielts_writing_ai/deletion.py:263-287",
                "tools/ielts_writing_ai/deletion.py:361-364",
            ],
            "cause": "Cardinal two/2 preceding plural paragraphs becomes index1; Chinese 两/三 is accepted but not a position, so the issue quote is used. Neither gives a unique target for deleting multiple paragraphs.",
            "example": "Delete two paragraphs produces136 by deleting paragraph2; 删去两段 produces149 by deleting the quoted last paragraph. Both should remain uncertain.",
        },
        "unparsed_ordinal_fallback": {
            "title": "An accepted Chinese ordinal that cannot be converted falls back to the issue quote",
            "locations": [
                "tools/ielts_writing_ai/deletion.py:69-74",
                "tools/ielts_writing_ai/deletion.py:244-258",
                "tools/ielts_writing_ai/deletion.py:361-364",
            ],
            "cause": "The tokenizer accepts 第二十/第二十一 but _number supports only single digits or 十-prefix teens. None is treated as no explicit position, so paragraph5 replaces nonexistent paragraph20/21.",
            "example": "删去第二十段 in a five-paragraph essay confidently reports149. The canonical 第十九段 control is uncertain.",
        },
    }
    for group, description in descriptions.items():
        failed = [c["name"] for c in cases if c["group"] == group and c["failed_checks"]]
        if failed:
            findings.append(
                {"priority": "P2", "group": group, **description, "failed_cases": failed}
            )
    report = {
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
        "contract": "Correct exact result or explicit uncertainty is accepted. Unsupported descriptions are not required to become exact. Each suggestion is independent.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: report[k] for k in ("checks_passed", "checks_total", "findings")},
            ensure_ascii=False,
        )
    )
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
