"""Capacity check for the proposed error-queue parameters (pure simulation, no data access).

Inputs are the anonymous aggregates in ../policy/production-aggregate.json (28-day window):
  * new first-attempt errors by ability in learning tasks: 4431 over 28 days / 20 students
    (mean about 55 per student-week); median task has 7 wrong senses, median student does 4 tasks a week
  * students review on about 54% of calendar days (303 learning days / 560), one batch of 20
  * first retest after an error was correct 34%-51% of the time (selection-biased)

Rule simulated (Codex's proposed trial values): first retest the next day; after a success the
next check is 2 days later; two successes on different days -> leaves the queue; any failure
resets successes and comes back next day; 3 consecutive failed review days -> paused for teaching;
at most CAP items per day, oldest due first.

Simplifications: every retest succeeds independently with probability p; new errors arrive
only on study days; no pre-existing backlog is imported.
"""

from __future__ import annotations

import json
import random
import statistics

DAYS = 28
RUNS = 400


def simulate(weekly_new_errors, study_day_share, p, cap, seed, gap_after_success=2, fail_limit=3):
    rng = random.Random(seed)
    per_study_day = weekly_new_errors / (7 * study_day_share)
    queue = []  # dicts: due, successes, fails
    served = late = exited = paused = 0
    late_days = []
    for day in range(DAYS):
        if rng.random() >= study_day_share:
            continue
        due = sorted((item for item in queue if item["due"] <= day), key=lambda item: item["due"])
        for item in due[:cap]:
            served += 1
            delay = day - item["due"]
            late_days.append(delay)
            late += delay > 0
            if rng.random() < p:
                item["successes"] += 1
                item["fails"] = 0
                if item["successes"] >= 2:
                    queue.remove(item)
                    exited += 1
                else:
                    item["due"] = day + gap_after_success
            else:
                item["successes"] = 0
                item["fails"] += 1
                if item["fails"] >= fail_limit:
                    queue.remove(item)
                    paused += 1
                else:
                    item["due"] = day + 1
        # today's task produces new errors, first retest tomorrow
        new = sum(1 for _ in range(int(per_study_day * 3) + 12) if rng.random() < per_study_day / (int(per_study_day * 3) + 12))
        queue.extend({"due": day + 1, "successes": 0, "fails": 0} for _ in range(new))
    overdue = sum(1 for item in queue if item["due"] < DAYS)
    return {
        "open_items_day28": len(queue),
        "overdue_items_day28": overdue,
        "served": served,
        "served_late_share": late / served if served else 0.0,
        "mean_days_late": statistics.mean(late_days) if late_days else 0.0,
        "paused_for_teacher_per_week": paused / (DAYS / 7),
        "exited_per_week": exited / (DAYS / 7),
    }


def summarise(**kwargs):
    runs = [simulate(seed=seed, **kwargs) for seed in range(RUNS)]
    return {key: round(statistics.median(run[key] for run in runs), 2) for key in runs[0]}


def main():
    scenarios = []
    for label, weekly in (("median student (about 30 new errors a week)", 30),
                          ("average student (about 55 a week)", 55),
                          ("heavier student (about 75 a week)", 75)):
        for share, share_label in ((0.54, "reviews on 54% of days (observed)"), (1.0, "reviews every day")):
            for p in (0.35, 0.5, 0.7):
                for cap in (20, 30, 40):
                    scenarios.append({
                        "student": label, "habit": share_label, "retest_success_rate": p, "daily_cap": cap,
                        **summarise(weekly_new_errors=weekly, study_day_share=share, p=p, cap=cap),
                    })
    print(json.dumps({"days": DAYS, "runs_per_scenario": RUNS, "scenarios": scenarios}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
