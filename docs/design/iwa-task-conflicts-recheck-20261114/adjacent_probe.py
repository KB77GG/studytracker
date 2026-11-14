"""Independent synthetic full-normalizer cases for numeric conflict filtering.

No configuration, network, model client or actual database is used. Cases labelled
limitations are documented scope boundaries and do not fail the acceptance checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.repo).resolve()))

    def blocked(*_args, **_kwargs):
        raise AssertionError("Offline normalization only")

    socket.create_connection = blocked
    socket.socket.connect = blocked
    from tools.ielts_writing_ai import copytext, essay, review

    def case(name, text, tq, ts, lq, ls, chart, expect_removed, **extra):
        return dict(
            name=name,
            text=text,
            task_quote=tq,
            task_suggestion=ts,
            language_quote=lq,
            language_suggestion=ls,
            chart=chart,
            expect_removed=expect_removed,
            **extra,
        )

    cases = [
        case(
            "positive.same_entity",
            "Television reached 45% at 22:00.",
            "Television reached 45% at 22:00",
            "Television reached 40% at 22:00",
            "Television reached 45%",
            "Television attracted 45% at 22:00",
            "Television 22:00 = 40%",
            True,
        ),
        case(
            "positive.followed_correction",
            "Television reached 45% at 22:00.",
            "Television reached 45% at 22:00",
            "Television reached 40% at 22:00",
            "Television reached 45%",
            "Television attracted 40% at 22:00",
            "Television 22:00 = 40%",
            False,
        ),
        case(
            "positive.other_sentence",
            "Television reached 45%. Radio reached 45%.",
            "Television reached 45%",
            "Television reached 40%",
            "Radio reached 45%",
            "Radio attracted 45%",
            "Television = 40%; Radio = 45%",
            False,
        ),
        case(
            "P2.entity_collision",
            "Men accounted for 20%, while women accounted for 20%.",
            "Men accounted for 20%",
            "Men accounted for 30%",
            "women accounted for 20%",
            "women represented 20%",
            "Men = 30%; Women = 20%",
            False,
            problem="The valid women clause is deleted although only the men clause was corrected.",
        ),
        case(
            "P2.unit_collision",
            "The share was 45%, while the journey lasted 45 minutes.",
            "The share was 45%",
            "The share was 40%",
            "the journey lasted 45 minutes",
            "the journey took 45 minutes",
            "Share = 40%; Journey duration = 45 minutes",
            False,
            problem="A corrected percentage deletes an unrelated valid duration of the same numeral.",
        ),
        case(
            "P2.time_percent_collision",
            "Television peaked at 22:00, while radio reached 22%.",
            "Television peaked at 22:00",
            "Television peaked at 21:00",
            "radio reached 22%",
            "radio attracted 22%",
            "Television peak time = 21:00; Radio = 22%",
            False,
            problem="Correcting an hour deletes an unrelated valid percentage of the same numeral.",
        ),
        case(
            "P2.ambiguous_quote_first_occurrence",
            "Radio reached 45% at noon. Television reached 45% at night.",
            "Radio reached 45% at noon",
            "Radio reached 40% at noon",
            "reached 45%",
            "Television attracted 45% at night",
            "Radio noon = 40%; Television night = 45%",
            False,
            problem="A repeated short quotation is assigned to its first occurrence, despite the suggestion rewriting the other entity/sentence.",
        ),
        case(
            "positive.decimal_percent",
            "Television reached 4.5% at 22:00.",
            "Television reached 4.5%",
            "Television reached 4.8%",
            "Television reached 4.5%",
            "Television attracted 4.5%",
            "Television = 4.8%",
            True,
        ),
        case(
            "positive.minute_replacement",
            "Television peaked at 22:30.",
            "Television peaked at 22:30",
            "Television peaked at 22:45",
            "Television peaked at 22:30",
            "Television was most popular at 22:30",
            "Television peak time = 22:45",
            True,
        ),
        case(
            "positive.no_checked_source",
            "Television reached 45% at 22:00.",
            "Television reached 45%",
            "Television reached 40%",
            "Television reached 45%",
            "Television attracted 45%",
            "Television = 40%",
            False,
            checked=False,
        ),
        case(
            "positive.drifted_confirmation",
            "Television reached 45% at 22:00.",
            "Television reached 45%",
            "Television reached 40%",
            "Television reached 45%",
            "Television attracted 45%",
            "Television = 40%",
            False,
            drift=True,
        ),
        case(
            "positive.unsourced_TA_correction",
            "Television reached 45% at 22:00.",
            "Television reached 45%",
            "Television reached 43%",
            "Television reached 45%",
            "Television attracted 45%",
            "Television = 40%",
            False,
        ),
        case(
            "positive.only_adding_numbers",
            "Television reached 45% at 22:00.",
            "Television reached 45%",
            "Television reached 45%, compared with radio at 30%",
            "Television reached 45%",
            "Television attracted 45%",
            "Television = 45%; Radio = 30%",
            False,
        ),
        case(
            "positive.only_dropping_numbers",
            "Television reached 45% at 22:00.",
            "Television reached 45%",
            "Television reached its daily peak",
            "Television reached 45%",
            "Television attracted 45%",
            "Television = 45%",
            False,
        ),
        case(
            "limitation.small_hour",
            "Radio peaked at 08:00.",
            "Radio peaked at 08:00",
            "Radio peaked at 09:00",
            "Radio peaked at 08:00",
            "Radio was most popular at 08:00",
            "Radio peak time = 09:00",
            False,
            limitation="Plain values below 10 intentionally excluded; this also excludes early-hour corrections.",
        ),
        case(
            "limitation.swapped_set",
            "Television reached 45%, while radio reached 40%.",
            "Television reached 45%, while radio reached 40%",
            "Television reached 40%, while radio reached 45%",
            "Television reached 45%",
            "Television attracted 45%",
            "Television = 40%; Radio = 45%",
            False,
            limitation="A numeric set swap has no lost and new numeric value, so it is outside the implemented replacement rule.",
        ),
        case(
            "limitation.false_TA_advice",
            "Television reached 45%, while radio reached 40%.",
            "Television reached 45%",
            "Television reached 40%",
            "Television reached 45%",
            "Television attracted 45%",
            "Television = 45%; Radio = 40%",
            True,
            limitation="The TA suggestion is itself wrong but uses an elsewhere-sourced number. This rule is internal consistency, not an independent chart fact check.",
        ),
    ]
    long_quote = (
        "The television series, which is displayed in the chart alongside the other series, "
        "is discussed here with several descriptions of its presentation and its general "
        "context, including the way it is compared across different parts of the day and "
        "the importance of identifying its largest audience before reaching a conclusion, "
        "reached 45% at 22:00."
    )
    cases.append(
        case(
            "P2.truncated_TA_quote",
            long_quote,
            long_quote,
            long_quote.replace("45%", "40%"),
            "reached 45% at 22:00",
            "attracted 45% at 22:00",
            "Television 22:00 = 40%",
            True,
            problem="Full verified TA quotation is truncated to 300 before conflict detection, losing the replaced figure.",
        )
    )

    observations = []
    checks = []
    for spec in cases:
        reading = "Type: line_graph\nUnits: % / time / stated units\nData: " + spec["chart"]
        checked = spec.get("checked", True)
        sub = {
            "task_type": "task1",
            "prompt_text": "The chart shows audience measurements.",
            "essay_text": spec["text"],
            "word_count": essay.count_words(spec["text"]),
            "target_band": 7.0,
            "image_status": "ready",
            "image_description": reading,
            "image_check": (
                json.dumps(
                    {
                        "status": "confirmed",
                        "edited": False,
                        "at": "2026-11-14T00:00:00Z",
                        "reading_sha256": hashlib.sha256(reading.encode()).hexdigest(),
                    }
                )
                if checked
                else None
            ),
        }
        if spec.get("drift"):
            sub["image_description"] += " changed"
        criteria = {}
        for key in ("task", "coherence", "lexical", "grammar"):
            issues = []
            if key == "task":
                issues = [
                    {
                        "quote": spec["task_quote"],
                        "suggestion": spec["task_suggestion"],
                        "comment": "请核对本句涉及的数据，按题图改正对应信息。",
                    }
                ]
            elif key == "lexical":
                issues = [
                    {
                        "quote": spec["language_quote"],
                        "suggestion": spec["language_suggestion"],
                        "comment": "这里可改用更自然的表达，保留正确的信息。",
                    }
                ]
            criteria[key] = {
                "band": 6.0,
                "summary": "基本完成信息呈现，表达尚有可以进一步改善之处。",
                "strengths": [{"quote": spec["text"], "comment": "原文提供了具体信息。"}],
                "issues": issues,
            }
        raw = {
            "criteria": criteria,
            "comparisons": [],
            "overall_comment": "文章基本回应题目，修改时应保持各项信息一致。",
            "priorities": ["改善表达并核对信息"],
        }
        result = review.normalize_evaluation(raw, sub)
        lang = next(c for c in result["criteria"] if c["key"] == "lexical")["issues"][0]
        task = result["criteria"][0]
        removed = lang.get("removed_reason") == "task_conflict"
        copied = copytext.copies_for("evaluate", result, {}, sub)["evaluation"]
        ok = removed == spec["expect_removed"]
        checks.append({"name": spec["name"], "pass": ok})
        checks.append(
            {
                "name": spec["name"] + ".scores_unchanged",
                "pass": all(c["band"] == 6.0 for c in result["criteria"] if c["state"] == "scored"),
            }
        )
        checks.append(
            {
                "name": spec["name"] + ".comment_preserved",
                "pass": lang["comment"] == criteria["lexical"]["issues"][0]["comment"],
            }
        )
        checks.append(
            {
                "name": spec["name"] + ".counter_matches_removal",
                "pass": result.get("task_conflicts", 0) == int(removed),
            }
        )
        observations.append(
            {
                **spec,
                "actual_removed": removed,
                "pass": ok,
                "task_state": task["state"],
                "normalized_task_issues": task["issues"],
                "normalized_language_issue": lang,
                "copy_has_conflict_notice": (
                    copytext.CONFLICT_NOTE in copied
                    if hasattr(copytext, "CONFLICT_NOTE")
                    else False
                ),
                "copy_has_original_language_suggestion": spec["language_suggestion"] in copied,
                "task_conflicts": result.get("task_conflicts", 0),
                "unsourced_removed": result["suggestions_removed"],
                "original_task_quote_chars": len(spec["task_quote"]),
            }
        )
    payload = {
        "source": str(Path(args.repo).resolve()),
        "checks": checks,
        "passed": sum(c["pass"] for c in checks),
        "total": len(checks),
        "failed_cases": [o["name"] for o in observations if not o["pass"]],
        "observations": observations,
        "real_calls": 0,
        "live_service_touched": False,
        "private_data_read": False,
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {key: payload[key] for key in ("passed", "total", "failed_cases")}, ensure_ascii=False
        )
    )
    return int(payload["passed"] != payload["total"])


if __name__ == "__main__":
    raise SystemExit(main())
