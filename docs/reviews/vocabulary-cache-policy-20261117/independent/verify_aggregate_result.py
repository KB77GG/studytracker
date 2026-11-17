#!/usr/bin/env python3
"""Reproduce internal consistency checks on an existing aggregate JSON only."""

import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_RESULT = Path(__file__).resolve().parents[1] / "policy" / "production-aggregate.json"


def verify(data):
    passed = 0

    def check(condition, label):
        nonlocal passed
        if not condition:
            raise ValueError("aggregate_consistency_failed:" + label)
        passed += 1

    for label, window in data["windows"].items():
        capacity = window["daily_review_capacity"]
        days = int(label[:-1])
        check(
            capacity["calendar_student_days_including_zero"] == capacity["active_students"] * days,
            label + ":calendar_denominator",
        )
        tasks = window["task_first_errors"]
        check(
            tasks["all"]["wrong_sense_task_pairs"] <= tasks["all"]["tested_sense_task_pairs"],
            label + ":task_wrong_not_above_tested",
        )
        for metric in ("answers", "batches"):
            check(
                capacity[metric]["on_vocabulary_learning_days"]["n"]
                == capacity["vocabulary_learning_student_days"],
                label + ":" + metric + ":learning_day_denominator",
            )
            check(
                capacity[metric]["on_all_calendar_days"]["n"]
                == capacity["calendar_student_days_including_zero"],
                label + ":" + metric + ":all_day_denominator",
            )
        retests = window["delayed_first_retests"]
        dimensions = [value for key, value in retests.items() if key != "all"]
        check(
            retests["all"]["wrong_sense_dimension_days"]
            == sum(value["wrong_sense_dimension_days"] for value in dimensions),
            label + ":error_day_dimension_sum",
        )
        for gap in (1, 2, 3):
            key = f"first_later_day_gap_{gap}"
            for metric in ("eligible_error_days", "observed_retests", "correct"):
                check(
                    retests["all"][key][metric] == sum(value[key][metric] for value in dimensions),
                    label + ":" + key + ":" + metric + ":dimension_sum",
                )
            for dimension, value in retests.items():
                result = value[key]
                prefix = label + ":" + dimension + ":" + key
                check(
                    0 <= result["correct"] <= result["observed_retests"] <= result["eligible_error_days"],
                    prefix + ":count_order",
                )
                check(
                    sum(result["retest_source_counts"].values()) == result["observed_retests"],
                    prefix + ":source_sum",
                )
                correct_rate = (
                    round(result["correct"] / result["observed_retests"], 4)
                    if result["observed_retests"] else None
                )
                check(
                    result["correct_fraction_among_retested"] == correct_rate,
                    prefix + ":correct_fraction",
                )
                observation_rate = (
                    round(result["observed_retests"] / result["eligible_error_days"], 4)
                    if result["eligible_error_days"] else None
                )
                check(
                    result["observation_fraction"] == observation_rate,
                    prefix + ":observation_fraction",
                )
        elapsed = window["answer_interval_proxy"]
        for cap in (30, 60, 120):
            result = elapsed[f"max_gap_{cap}s"]
            check(
                result["seconds"]["n"] + result["long_pauses_excluded"]
                == elapsed["positive_adjacent_pairs"],
                label + f":gap_{cap}:retained_plus_excluded",
            )
    for population, backlog in data["backlog_snapshot"].items():
        check(
            sum(backlog["dimension_composition"].values()) == backlog["raw_due_dimension_count"],
            population + ":dimension_composition_sum",
        )
        check(
            sum(backlog["sense_exclusive_priority_composition"].values())
            == backlog["raw_due_sense_count"],
            population + ":exclusive_sense_composition_sum",
        )
    check(
        data["quality"]["observed_first_vocabulary_dictation_records"]
        == data["quality"]["joined_learning_first_records"],
        "observed_equals_joined_records_for_this_result",
    )
    check(
        data["safety"]["successful_changes"] == data["safety"]["denied_statements"] == 0,
        "zero_writes_and_denials",
    )
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", nargs="?", type=Path, default=DEFAULT_RESULT)
    args = parser.parse_args()
    raw = args.result.read_bytes()
    checks = verify(json.loads(raw))
    print(json.dumps({"ok": True, "checks_passed": checks,
                      "input_sha256": hashlib.sha256(raw).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
