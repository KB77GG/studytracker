"""Adapted copy (2026-11-13, after review f46756f). The reviewer's original reproduced
the .13 behaviour (a similar sentence removed from the count and from credit); this copy
asserts the .14 behaviour instead: the same detector is only a hint (renamed
similar_to_prompt), the 152-word report stays 152 in the request and on the page, and
copying confirmed in the data is excluded in full even where the comparison misses it.

Offline copy-detection review. All question/essay/chart data below are synthetic.

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
            found = essay.similar_to_prompt(text, question)
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
        warnings = list(normalized["warnings"])
        hints = [w for w in warnings if "待确认" in w]
        checks.extend(
            [
                {"name": "full_t1_is_152_words", "passed": submission["word_count"] == 152},
                {
                    "name": "full_t1_request_has_no_copy_fields",
                    "passed": not any(
                        k in payload
                        for k in (
                            "copied_from_question",
                            "word_count_without_copied",
                            "copied_note",
                        )
                    ),
                },
                {"name": "full_t1_request_word_count_152", "passed": payload["word_count"] == 152},
                {
                    "name": "normalizer_excludes_nothing",
                    "passed": normalized["copied_from_question"] == [],
                },
                {
                    "name": "normalizer_hints_the_overview",
                    "passed": normalized["similar_to_question"] == [{"p": 2, "words": 14}],
                },
                {
                    "name": "one_hint_without_deduction",
                    "passed": len(hints) == 1 and "本工具没有因此扣字数" in hints[0],
                },
                {
                    "name": "no_underlength_or_138_warning",
                    "passed": not any(
                        "去掉后" in w or "138" in w or "低于 150" in w for w in warnings
                    ),
                },
                {
                    "name": "original_essay_preserved",
                    "passed": submission["essay_text"] == FULL_T1 and payload["essay"] == FULL_T1,
                },
            ]
        )

        # Confirmed copying, with a misspelled copied sentence the comparison misses.
        copied = (
            "Governments should spend more money on roads than on public transport.\n"
            "Govermants shuold spnd mor mony on rods then on publik transprot.\n"
        )
        own = "I disagree, because buses and trains move more people for each dollar spent."
        text = copied + own
        confirmed = {
            "task_type": "task2",
            "prompt_text": QUESTION_T2,
            "essay_text": text,
            "word_count": essay.count_words(text),
            "target_band": 7.0,
            "copied_spans": json.dumps(
                {
                    "spans": essay.resolve_copied(text, [{"paragraph": 1}, {"paragraph": 2}]),
                    "source": "synthetic",
                }
            ),
        }
        found = sum(h["words"] for h in essay.similar_to_prompt(text, QUESTION_T2))
        c_messages, c_context = prompts.build_evaluate(confirmed, essay.split_sentences(text))
        c_payload = json.JSONDecoder().raw_decode(c_messages[1]["content"].split("\n", 1)[1])[0]
        c_normalized = review.normalize_evaluation(FakeClient._evaluate(c_context), confirmed)
        copied_words = essay.count_words(copied)
        checks.extend(
            [
                {"name": "comparison_alone_misses_copied_words", "passed": found < copied_words},
                {
                    "name": "confirmed_request_excludes_all_copied_words",
                    "passed": c_payload.get("word_count_without_copied") == essay.count_words(own),
                },
                {
                    "name": "confirmed_result_counts_all_copied_words",
                    "passed": sum(s["words"] for s in c_normalized["copied_from_question"])
                    == copied_words,
                },
                {
                    "name": "confirmed_source_not_sent",
                    "passed": "synthetic" not in c_messages[1]["content"],
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
        "purpose": "Check the .14 behaviour: similarity is a hint, confirmed copying is excluded.",
        "cases": results,
        "full_task1": {
            "submission": submission,
            "payload_word_count": payload["word_count"],
            "normalized_copied_from_question": normalized["copied_from_question"],
            "normalized_similar_to_question": normalized["similar_to_question"],
            "normalized_hints": hints,
        },
        "checks": checks,
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_total": len(checks),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "checks_passed": evidence["checks_passed"],
                "checks_total": len(checks),
                "real_model_calls": 0,
                "output": str(args.out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if all(check["passed"] for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
