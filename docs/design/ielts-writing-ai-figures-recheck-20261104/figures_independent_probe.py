"""Independent offline check of the two numeric-advice regressions and sources.

No credentials, network, application server or persistent trial database is used.
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
    from tools.ielts_writing_ai import argument, copytext, figures, review
    from tools.ielts_writing_ai.tests.test_review import evaluation, submission

    advice = "补充一个数字例子：公交使排放降低 80%。"
    whole_values = []
    for original, should_remove in (
        ("The city supports buses.", True),
        ("The city began its bus service in 1980.", True),
        ("The city operates 180 buses.", True),
        ("The city operates 80 buses.", True),
        ("The city reports an 80% reduction in emissions.", False),
        ("The city reports an 80 per cent reduction in emissions.", False),
    ):
        raw = {"paragraphs": [{"role": "body", "main_point": original, "verdict": "supports"}],
               "problems": [{"type": "unsupported", "quote": original, "comment": "需要说明。", "suggestion": advice}]}
        item = argument.normalize(raw, original)["problems"][0]
        assert item["suggestion_removed"] is should_remove
        assert item["suggestion"] == ("" if should_remove else advice)
        whole_values.append({"essay": original, "removed": item["suggestion_removed"], "correct": True})

    unit_cases = []
    for original, proposed, expected_missing in (
        ("We operate 80 buses.", "80% 的人", ["80%"]),
        ("We operate 80 buses.", "约 80 辆", []),
        ("75% of riders.", "75 percent", []),
        ("75% of riders.", "75％", []),
        ("1,500 riders.", "1500 riders", []),
        ("1,500 riders.", "15 riders", ["15"]),
        ("Nothing numeric.", "补 1 个例子，第 2 段", []),
        ("Nothing numeric.", "2.5% 的增长", ["2.5%"]),
    ):
        actual = figures.Sources(original).unsourced(proposed)
        assert actual == expected_missing
        unit_cases.append({"source": original, "advice": proposed, "unsourced": actual})

    sub = {"task_type": "task1", "essay_text": "Ownership rose.",
           "prompt_text": "Compare 2000 and 2020.", "word_count": 133,
           "image_status": "ready", "image_description": "Country C rose from 42% to 79%."}
    sources = figures.for_submission(sub)
    allowed = ["比较 2000 与 2020", "从 42% 升到 79%", "目前 133 词，至少写到 150 词"]
    assert all(not sources.unsourced(a) for a in allowed)
    unavailable = figures.for_submission(dict(sub, image_status="failed"))
    assert unavailable.unsourced("从 42% 升到 79%") == ["42%", "79%"]

    raw = evaluation()
    raw["criteria"]["task"]["issues"][0]["suggestion"] = advice
    raw["argument"]["problems"][0]["suggestion"] = advice
    raw["argument"]["improvements"] = [{"quote": raw["argument"]["position"]["quote"], "suggestion": advice}]
    raw["priorities"] = [advice, "补足因果解释", "至少写到 250 词"]
    result = review.normalize_evaluation(copy.deepcopy(raw), submission())
    expected_removed = {"criteria": 1, "priorities": 1, "argument": 2, "total": 4}
    assert result["suggestions_removed"] == expected_removed
    assert "80%" not in copytext.evaluation_text(result, {})
    assert copytext.REMOVED_NOTE in copytext.evaluation_text(result, {})
    assert not result["argument"]["improvements"]
    assert result["priorities"] == ["补足因果解释", "至少写到 250 词"]
    allowed_result = review.normalize_evaluation(copy.deepcopy(raw), submission(prompt_text="Assume an 80% reduction."))
    assert allowed_result["suggestions_removed"]["total"] == 0
    assert len(allowed_result["argument"]["improvements"]) == 1
    assert "80%" in copytext.evaluation_text(allowed_result, {})
    assert allowed_result["overall_band"] == result["overall_band"]

    fixture = json.loads((args.repo / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261104c.json").read_text())
    raw_mid = json.loads(fixture["evaluation_attempts"]["t2-mid"][-1])
    mid = review.normalize_evaluation(raw_mid, fixture["submissions"]["t2-mid"])
    copied_mid = copytext.evaluation_text(mid, {})
    assert mid["suggestions_removed"] == {"criteria": 1, "priorities": 0, "argument": 1, "total": 2}
    assert "80%" not in json.dumps(mid, ensure_ascii=False)
    assert "80%" not in copied_mid
    assert copied_mid.count(copytext.REMOVED_NOTE) == 2
    js = (args.repo / "tools/ielts_writing_ai/static/iwa.js").read_text()
    assert "issue.suggestion_removed" in js and "item.suggestion_removed" in js
    assert copytext.REMOVED_NOTE in js

    # Narrow representation observations, recorded separately from the fixed cases.
    # These do not test the impossible claim that a matching number validates its fact.
    representation_notes = [
        {"source": "No numeric data.", "advice": "排放减少百分之8。",
         "unsourced": figures.Sources("No numeric data.").unsourced("排放减少百分之8。"),
         "note": "Arabic digits after Chinese prefix are parsed as a plain number; under-10 exemption applies."},
        {"source": "排放下降百分之八十一。", "advice": "排放下降百分之八十。",
         "unsourced": figures.Sources("排放下降百分之八十一。").unsourced("排放下降百分之八十。"),
         "note": "Chinese percentages use literal phrase containment, not normalized numeric comparison."},
    ]
    report = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo, text=True).strip(),
        "network_calls": 0, "previous_two_regressions_fixed": True,
        "whole_value_cases": whole_values, "unit_and_format_cases": unit_cases,
        "allowed_sources": {"question_chart_word_count_minimum_passed": True,
                            "unavailable_chart_numbers_rejected": True},
        "all_four_advice_paths": {"removed": expected_removed, "copy_has_80percent": False,
                                 "known_prompt_figure_preserved_everywhere": True, "score_unchanged": True},
        "real_mid_replay": {"removed": mid["suggestions_removed"], "json_and_copy_have_80percent": False,
                            "copy_removal_notices": copied_mid.count(copytext.REMOVED_NOTE)},
        "ui_contract": "Static review confirms both criterion and argument paths display the same removal marker; no browser was run by this probe.",
        "representation_limitations": representation_notes,
        "limitations": "This is a numeric-source heuristic. Prose commentary is excluded, ordinary small numbers are exempt, and a sourced numeric value is not proof of the associated factual claim. Chinese number forms still have limited coverage.",
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
