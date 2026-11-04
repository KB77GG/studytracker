"""Read-only offline review of argument rules at prompt .5; no model calls.

Records both passing contracts and reproduced findings. Exit 0 means the probe
executed, not that every observed behavior is correct.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    from tools.ielts_writing_ai import argument, copytext, review

    essay = "I support public transport.\nI oppose public transport."
    base = {
        "position": {"quote": "I support public transport.", "consistent": True,
                     "comment": "立场一致。"},
        "paragraphs": [
            {"p": 1, "role": "introduction", "main_point": "I support public transport.", "verdict": "supports"},
            {"p": 2, "role": "conclusion", "main_point": "I oppose public transport.", "verdict": "supports"},
        ],
        "problems": [],
    }
    pair = {"type": "conclusion_inconsistent", "quote": "I oppose public transport.",
            "conflicts_with": "I support public transport.", "comment": "两处支持与反对相反。"}
    controls = []
    for name, other, expected_kept in (
        ("valid_pair", "I support public transport.", True),
        ("same_passage", "I oppose public transport.", False),
        ("contained_passage", "oppose public transport", False),
        ("invented_other", "I strongly support roads.", False),
        ("missing_other", None, False),
    ):
        raw = copy.deepcopy(base)
        raw["problems"] = [dict(pair, conflicts_with=other)]
        result = argument.normalize(raw, essay)
        assert bool(result["problems"]) is expected_kept
        if expected_kept:
            assert result["position"]["consistent"] is None
            assert result["problems"][0]["needs_review"]
            assert result["self_conflicts"] == 1
        controls.append({"case": name, "problem_kept": bool(result["problems"]),
                         "dropped": result["dropped"], "self_conflicts": result["self_conflicts"]})
    raw = copy.deepcopy(base)
    raw["position"].update(consistent=False, comment="立场前后不一致。")
    result = argument.normalize(raw, essay)
    assert result["position"]["consistent"] is None
    assert any("这一判断未采用" in n for n in result["notes"])
    position_note = {"consistent": result["position"]["consistent"],
                     "original_comment_retained": result["position"]["comment"],
                     "notes": result["notes"],
                     "assessment": "Not a separate blocker: the copied/displayed notes explicitly say the judgment is not adopted."}
    raw = copy.deepcopy(base)
    raw["problems"] = [{"type": "off_position", "quote": "I oppose public transport.", "comment": "偏离。"}]
    result = argument.normalize(raw, essay)
    assert result["problems"][0]["p"] == 2 and result["problems"][0]["needs_review"]
    controls.append({"case": "off_position_vs_supports", "needs_review": True})
    raw = copy.deepcopy(base)
    raw["improvements"] = [{"quote": "I support public transport.", "suggestion": "可以补充一个明确标为假设的通勤场景。"}]
    result = argument.normalize(raw, essay)
    assert len(result["improvements"]) == 1 and not result["problems"]
    controls.append({"case": "optional_improvement", "improvements": 1, "problems": 0})

    fixture = json.loads((args.repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261104c.json").read_text())
    under = json.loads(fixture["evaluation_attempts"]["t2-under-length"][-1])
    mapped = argument.normalize(under["argument"], fixture["submissions"]["t2-under-length"]["essay_text"])
    assert len(mapped["paragraphs"]) == 1 and mapped["duplicates"] == 4
    controls.append({"case": "real_one_paragraph_output", "paragraphs": 1, "duplicates": 4})

    suggestion = "补充一个数字例子：公交使排放降低 80%。"
    numeric = []
    for original, should_remove in (
        ("The city supports buses.", True),
        ("The city began its bus service in 1980.", True),
        ("The city operates 180 buses.", True),
        ("The city reports an 80% reduction in emissions.", False),
    ):
        values = argument.unsourced_figures(suggestion, original)
        raw = {"paragraphs": [{"role": "body", "main_point": original, "verdict": "supports"}],
               "problems": [{"type": "unsupported", "quote": original, "comment": "需要说明。", "suggestion": suggestion}]}
        normalized = argument.normalize(raw, original)
        item = normalized["problems"][0]
        numeric.append({"essay": original, "suggestion": suggestion, "expected_remove": should_remove,
                        "detected_unsourced": values, "actually_removed": item["suggestion_removed"],
                        "displayed_suggestion": item["suggestion"],
                        "correct": item["suggestion_removed"] is should_remove})

    mid = json.loads(fixture["evaluation_attempts"]["t2-mid"][-1])
    result = review.normalize_evaluation(mid, fixture["submissions"]["t2-mid"])
    criterion_advice = [
        {"criterion": c["short"], "quote": i["quote"], "suggestion": i["suggestion"]}
        for c in result["criteria"] for i in c["issues"] if "80%" in i.get("suggestion", "")
    ]
    copied = copytext.evaluation_text(result, {})
    actual_fixture = {
        "sample": "t2-mid", "source": "actual previous DeepSeek output replayed unchanged",
        "argument_suggestions_removed": result["argument"]["suggestions_removed"],
        "criterion_80percent_advice_still_shown": criterion_advice,
        "copied_evaluation_still_contains_80percent": "80%" in copied,
        "original_essay_contains_80percent": "80%" in fixture["submissions"]["t2-mid"]["essay_text"],
    }
    summary = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo, text=True).strip(),
        "network_calls": 0, "passing_contracts": controls,
        "nonblocking_position_comment_observation": position_note,
        "numeric_token_probe": numeric,
        "real_output_advice_coverage": actual_fixture,
        "findings": [
            "P2: numeric source lookup uses digit-substring matching, so 1980/180 wrongly authorizes 80% advice.",
            "P2: only argument suggestions are filtered; actual mid fixture still exposes the same unsourced 80% in criterion advice and copied evaluation.",
        ],
        "scope_limit": "No claim that mere matching numeric tokens proves a statistical proposition. The defect is recognizing a different number as a source and leaving an already reproduced advice path unfiltered.",
    }
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
