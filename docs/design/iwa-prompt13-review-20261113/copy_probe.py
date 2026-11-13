"""Offline copy-detection review. All question/essay/chart data below are synthetic.

This exercises the real detector, prompt builder and result normalizer. It never
loads settings, opens a database, reads private samples or calls a model. The
demo evaluator supplies only a structurally valid normalization fixture; its
scores are deliberately omitted from the evidence and prove no grading effect.
"""

from __future__ import annotations

import argparse
import difflib
import json
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

QUESTION_T1 = (
    "The chart below shows the percentage of people who travelled to work by car, "
    "bus and bicycle in Newtown in 2000 and 2020."
)
QUESTION_T2 = (
    "Governments should spend more money on roads than on public transport. "
    "To what extent do you agree or disagree?"
)
OVERVIEW = "Overall, the percentage of people who travelled to work by car in Newtown increased."
FULL_T1 = (
    "The two sets of figures compare three commuting methods over a twenty year period "
    "in Newtown.\n"
    + OVERVIEW
    + "\nCars accounted for 40% of journeys initially, rising to 70% by the end of the "
    "period. This was the largest change among the three categories, and motoring "
    "remained the leading choice in both years. By contrast, the share for buses "
    "declined from 35% to 20%, placing this mode second throughout. Cycling also became "
    "less common, falling from 25% to just 10%.\n"
    "At the beginning, the gap between cars and buses was only five percentage points. "
    "By the final year, it had widened to fifty points. Meanwhile, the combined share "
    "for the two smaller categories dropped from 60% to 30%. These comparisons "
    "indicate a clear shift towards private vehicles, alongside reduced use of both "
    "alternatives. The ranking of the categories nevertheless stayed unchanged."
)
SYNTHETIC_VISUAL = (
    "Synthetic bar chart: commuting modes in Newtown; percentages; 2000 and 2020. "
    "Cars: 40% then 70%; buses: 35% then 20%; bicycles: 25% then 10%. "
    "Cars were the largest category in both years and increased; buses and bicycles declined."
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    from tools.ielts_writing_ai import essay, prompts, review
    from tools.ielts_writing_ai.llm import FakeClient

    cases = [
        (
            "exact_copy",
            QUESTION_T2,
            "Governments should spend more money on roads than on public transport.",
            True,
            False,
        ),
        (
            "one_typo_copy",
            QUESTION_T2,
            "Governments should spend more mony on roads than on public transport.",
            True,
            False,
        ),
        (
            "paraphrase",
            QUESTION_T2,
            "I favour better buses because they offer an affordable alternative to driving.",
            False,
            False,
        ),
        ("short_overlap", QUESTION_T2, "Governments should spend more money.", False, False),
        ("unrelated", QUESTION_T2, "My favourite meals are cooked at home.", False, False),
        (
            "opposing_position",
            QUESTION_T2,
            "Governments should not spend more money on roads than on public transport.",
            True,
            True,
        ),
        (
            "task1_new_increase",
            QUESTION_T1,
            "The percentage of people who travelled to work by car increased.",
            True,
            True,
        ),
        (
            "task1_new_decrease",
            QUESTION_T1,
            "The percentage of people who travelled to work by car decreased.",
            True,
            True,
        ),
        (
            "task1_new_data_value",
            QUESTION_T1,
            "The percentage of people who travelled to work by car reached 70% in 2020.",
            True,
            True,
        ),
        ("task1_new_overview", QUESTION_T1, OVERVIEW, True, True),
    ]

    results = []
    checks = []
    # Guard the probe itself against accidental network access.
    with patch.object(socket.socket, "connect", side_effect=AssertionError("offline only")):
        for name, question, text, expected_detected, adds_new_content in cases:
            found = essay.copied_from_prompt(text, question)
            tokens = essay._copy_tokens(text)
            question_tokens = essay._copy_tokens(question)
            blocks = difflib.SequenceMatcher(
                None, tokens, question_tokens, autojunk=False
            ).get_matching_blocks()
            matched = sum(block.size for block in blocks)
            checks.append(
                {"name": name + "_observed_behavior", "passed": bool(found) == expected_detected}
            )
            results.append(
                {
                    "name": name,
                    "question": question,
                    "essay": text,
                    "words": essay.count_words(text),
                    "token_count": len(tokens),
                    "matched_tokens": matched,
                    "matched_share": matched / len(tokens),
                    "longest_run": max(block.size for block in blocks),
                    "detected": found,
                    "adds_new_propositional_content": adds_new_content,
                    "tokens_not_in_question": [t for t in tokens if t not in question_tokens],
                }
            )

        submission = {
            "task_type": "task1",
            "prompt_text": QUESTION_T1,
            "essay_text": FULL_T1,
            "word_count": essay.count_words(FULL_T1),
            "target_band": 7.0,
            "image_status": "ready",
            "image_description": SYNTHETIC_VISUAL,
        }
        messages, context = prompts.build_evaluate(submission, essay.split_sentences(FULL_T1))
        payload = json.JSONDecoder().raw_decode(messages[1]["content"].split("\n", 1)[1])[0]
        normalized = review.normalize_evaluation(FakeClient._evaluate(context), submission)
        warnings = [w for w in normalized["warnings"] if "与题目几乎逐字相同" in w]
        expected_copy = [{"p": 2, "sentence": OVERVIEW}]
        checks.extend(
            [
                {"name": "full_t1_is_152_words", "passed": submission["word_count"] == 152},
                {
                    "name": "full_t1_overview_is_the_only_flagged_sentence",
                    "passed": payload.get("copied_from_question") == expected_copy,
                },
                {
                    "name": "full_t1_payload_removes_all_14_overview_words",
                    "passed": payload.get("word_count_without_copied") == 138,
                },
                {
                    "name": "payload_forbids_credit_for_new_content",
                    "passed": "do not credit them for task response, development, vocabulary or "
                    "grammar" in payload.get("copied_note", ""),
                },
                {
                    "name": "normalizer_repeats_14_word_exclusion",
                    "passed": normalized["copied_from_question"] == [{"p": 2, "words": 14}],
                },
                {
                    "name": "normalizer_claims_underlength_after_excluding_new_overview",
                    "passed": len(warnings) == 1
                    and "去掉后约 138 词，低于 150 词要求" in warnings[0],
                },
                {
                    "name": "original_essay_preserved",
                    "passed": submission["essay_text"] == FULL_T1 and payload["essay"] == FULL_T1,
                },
            ]
        )

    evidence = {
        "source": str(source),
        "source_head": subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
        ).strip(),
        "prompt_version": prompts.PROMPT_VERSION,
        "data_origin": "All question/essay/chart strings are synthetic and authored for this probe.",
        "real_model_calls": 0,
        "private_files_read": 0,
        "purpose": "Reproduce observed code behavior, including the incorrect blanket exclusion; "
        "passing checks mean reproducibility, not that product behavior is correct.",
        "cases": results,
        "full_task1": {
            "submission": submission,
            "payload_copied_from_question": payload.get("copied_from_question"),
            "payload_word_count_without_copied": payload.get("word_count_without_copied"),
            "payload_copied_note": payload.get("copied_note"),
            "normalized_copied_from_question": normalized["copied_from_question"],
            "normalized_copy_warnings": warnings,
        },
        "checks": checks,
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_total": len(checks),
        "confirmed_findings": [
            {
                "severity": "P2",
                "title": "Shared task vocabulary makes new stance/trend/data content lose all credit",
                "mechanism": "The 85% token heuristic marks entire sentences. Both the prompt and "
                "normalizer treat every word and idea in those sentences as copied, even the "
                "new predicate, negation or data value absent from the question.",
                "demonstrated_effect": "A synthetic 152-word Task 1 report loses its correct "
                "14-word overview, sends 138 to the model as effective length, instructs the "
                "model to withhold credit, and displays an underlength warning.",
                "not_demonstrated": "No real model was called, so the magnitude of any score "
                "change is unmeasured. Demo scores are not evidence.",
            }
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "checks_passed": evidence["checks_passed"],
                "checks_total": len(checks),
                "confirmed_findings": len(evidence["confirmed_findings"]),
                "real_model_calls": 0,
                "output": str(args.out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if all(check["passed"] for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
