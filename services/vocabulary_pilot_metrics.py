"""Read-only pilot evaluation. Export aggregates; keep identities in caller scope.

The loader accepts a DBAPI/SQLAlchemy adapter so the production CLI never needs
to import Flask, app.py, credentials, answer text or student names.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

MAX_ROWS = 100000
READ_COLUMNS = {
    "vocabulary_review_policy_enrollment": {"student_id", "enabled", "starts_at"},
    "vocabulary_error_queue": {
        "id",
        "student_id",
        "sense_id",
        "dimension",
        "cohort_key",
        "opened_at",
    },
    "vocabulary_policy_event": {
        "id",
        "student_id",
        "queue_id",
        "checkpoint_id",
        "allocation_id",
        "sense_id",
        "dimension",
        "kind",
        "source",
        "occurred_at",
        "local_date",
        "is_correct",
        "detail_code",
    },
    "vocabulary_policy_allocation": {
        "id",
        "student_id",
        "queue_id",
        "checkpoint_id",
        "kind",
        "sense_id",
        "dimension",
    },
    "vocabulary_policy_checkpoint": {
        "id",
        "student_id",
        "sense_id",
        "dimension",
        "cohort_key",
        "source_kind",
        "source_key",
        "origin_event_id",
        "anchor_at",
        "due_local_date",
        "interval_days",
        "status",
    },
    "student_profile": {"id", "user_id", "primary_teacher_id", "is_deleted"},
    "teacher_student_link": {"teacher_id", "student_id"},
    "user": {"id", "role", "is_active"},
}


class MetricsError(ValueError):
    pass


def utc_time(value=None):
    if value is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: UP017
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017
    return value


def local_day(value):
    return (utc_time(value) + timedelta(hours=8)).date()


def _day(value):
    return value if isinstance(value, date) else date.fromisoformat(value)


def _distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "sum": 0, "mean": None, "p50": None, "p90": None, "max": None}

    def quantile(fraction):
        position = (len(values) - 1) * fraction
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        return round(values[lower] + (values[upper] - values[lower]) * (position - lower), 3)

    return {
        "n": len(values),
        "sum": sum(values),
        "mean": round(sum(values) / len(values), 3),
        "p50": quantile(0.5),
        "p90": quantile(0.9),
        "max": max(values),
    }


def _rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "ratio": round(numerator / denominator, 6) if denominator else None,
    }


def load_rows(execute, *, student_ids=None, as_of=None):
    """execute(sql, named_parameters) returns dictionaries; only fixed SQL used."""
    now = utc_time(as_of)
    params = {"as_of": now.isoformat(sep=" ", timespec="microseconds")}
    selection = ""
    if student_ids is not None:
        ids = sorted(set(int(value) for value in student_ids))
        if any(value <= 0 for value in ids) or len(ids) > 500:
            raise MetricsError("invalid_selection")
        if not ids:
            return {
                name: []
                for name in (
                    "enrollments",
                    "queues",
                    "events",
                    "allocations",
                    "checkpoints",
                    "teachers",
                )
            }
        params.update({f"student_{index}": value for index, value in enumerate(ids)})
        selection = (
            " AND student_id IN ("
            + ",".join(f":student_{index}" for index in range(len(ids)))
            + ")"
        )
    enrollments = list(
        execute(
            "SELECT student_id,starts_at FROM vocabulary_review_policy_enrollment "
            "WHERE enabled=1 AND starts_at<=:as_of" + selection + " LIMIT 501",
            params,
        )
    )
    if len(enrollments) > 500:
        raise MetricsError("selection_too_large")
    if not enrollments:
        return {
            name: []
            for name in (
                "enrollments",
                "queues",
                "events",
                "allocations",
                "checkpoints",
                "teachers",
            )
        }
    scoped = {f"id_{index}": row["student_id"] for index, row in enumerate(enrollments)}
    placeholders = ",".join(f":{name}" for name in scoped)
    output = {"enrollments": enrollments}
    definitions = {
        "queues": (
            "vocabulary_error_queue",
            "id,student_id,sense_id,dimension,cohort_key,opened_at",
        ),
        "events": (
            "vocabulary_policy_event",
            "id,student_id,queue_id,checkpoint_id,allocation_id,sense_id,dimension,kind,source,occurred_at,local_date,is_correct,detail_code",
        ),
        "allocations": (
            "vocabulary_policy_allocation",
            "id,student_id,queue_id,checkpoint_id,kind,sense_id,dimension",
        ),
        "checkpoints": (
            "vocabulary_policy_checkpoint",
            "id,student_id,sense_id,dimension,cohort_key,source_kind,source_key,origin_event_id,anchor_at,due_local_date,interval_days,status",
        ),
    }
    for name, (table, columns) in definitions.items():
        rows = list(
            execute(
                f"SELECT {columns} FROM {table} WHERE student_id IN ({placeholders}) LIMIT {MAX_ROWS + 1}",
                scoped,
            )
        )
        if len(rows) > MAX_ROWS:
            raise MetricsError("metrics_row_budget_exceeded")
        output[name] = rows
    output["teachers"] = list(
        execute(
            "SELECT p.user_id student_id,u.id teacher_id FROM student_profile p "
            "JOIN user u ON u.id=p.primary_teacher_id WHERE p.is_deleted=0 "
            f"AND p.user_id IN ({placeholders}) AND u.role='teacher' AND u.is_active=1 "
            "UNION SELECT p.user_id student_id,u.id teacher_id FROM student_profile p "
            "JOIN teacher_student_link l ON l.student_id=p.id JOIN user u ON u.id=l.teacher_id "
            f"WHERE p.is_deleted=0 AND p.user_id IN ({placeholders}) AND u.role='teacher' AND u.is_active=1",
            scoped,
        )
    )
    return output


def _checkpoint_metrics(checkpoints, events, allocations, now):
    today = local_day(now)
    groups = {}
    for key in ("graduation_d7", "first_correct_d7", "first_correct_d30"):
        groups[key] = {
            "opportunities": 0,
            "due": 0,
            "not_yet_due": 0,
            "observed": 0,
            "on_time_observed": 0,
            "correct": 0,
            "on_time_correct": 0,
            "unobserved": 0,
            "missed": 0,
            "pending_today": 0,
            "late_observed": 0,
            "early_observed": 0,
            "status_answered_without_event": 0,
            "delay_days": [],
            "elapsed_days": [],
        }
    first_observations = {}
    for event in sorted(events, key=lambda row: (utc_time(row["occurred_at"]), row["id"])):
        allocation = allocations.get(event.get("allocation_id"))
        if (
            event["kind"] != "answer"
            or event["source"] != "review"
            or not allocation
            or allocation["kind"] != "sample"
            or allocation["student_id"] != event["student_id"]
            or allocation.get("checkpoint_id") != event.get("checkpoint_id")
        ):
            continue
        first_observations.setdefault((event["student_id"], event["checkpoint_id"]), event)
    for checkpoint in checkpoints:
        if utc_time(checkpoint["anchor_at"]) > now:
            continue
        key = f"{checkpoint['source_kind']}_d{checkpoint['interval_days']}"
        if key not in groups:
            continue
        bucket = groups[key]
        bucket["opportunities"] += 1
        due = _day(checkpoint["due_local_date"])
        if due > today:
            bucket["not_yet_due"] += 1
            continue
        bucket["due"] += 1
        observation = first_observations.get((checkpoint["student_id"], checkpoint["id"]))
        if not observation:
            bucket["unobserved"] += 1
            bucket["missed"] += int(due < today or checkpoint["status"] == "missed")
            bucket["pending_today"] += int(due == today and checkpoint["status"] == "pending")
            bucket["status_answered_without_event"] += int(checkpoint["status"] == "answered")
            continue
        answered_day = local_day(observation["occurred_at"])
        delay = (answered_day - due).days
        correct = observation["is_correct"] is True or observation["is_correct"] == 1
        bucket["observed"] += 1
        bucket["correct"] += int(correct)
        bucket["on_time_observed"] += int(delay == 0)
        bucket["on_time_correct"] += int(delay == 0 and correct)
        bucket["late_observed"] += int(delay > 0)
        bucket["early_observed"] += int(delay < 0)
        bucket["delay_days"].append(delay)
        bucket["elapsed_days"].append((answered_day - local_day(checkpoint["anchor_at"])).days)
    for bucket in groups.values():
        bucket["first_accuracy"] = _rate(bucket["correct"], bucket["observed"])
        bucket["on_time_first_accuracy"] = _rate(
            bucket["on_time_correct"], bucket["on_time_observed"]
        )
        bucket["coverage"] = _rate(bucket["observed"], bucket["due"])
        bucket["on_time_coverage"] = _rate(bucket["on_time_observed"], bucket["due"])
        bucket["delay_days"] = _distribution(bucket["delay_days"])
        bucket["elapsed_days"] = _distribution(bucket["elapsed_days"])
    return groups


def aggregate(rows, *, as_of=None, week=None):
    """Return anonymous summary plus internal student counters for authorized UI."""
    now = utc_time(as_of)
    today = local_day(now)
    week_day = _day(week) if week else today
    week_start = week_day - timedelta(days=week_day.weekday())
    week_end = week_start + timedelta(days=7)
    starts = {row["student_id"]: utc_time(row["starts_at"]) for row in rows["enrollments"]}
    cohorts = {student: start.strftime("%Y%m%dT%H%M%S.%f") for student, start in starts.items()}
    events = [
        row
        for row in rows["events"]
        if row["student_id"] in starts
        and starts[row["student_id"]] <= utc_time(row["occurred_at"]) <= now
    ]
    observed_queues = {(row["student_id"], row.get("queue_id")) for row in events}
    queues = {
        row["id"]: row
        for row in rows["queues"]
        if row["student_id"] in cohorts
        and row["cohort_key"] == cohorts[row["student_id"]]
        and (utc_time(row["opened_at"]) <= now or (row["student_id"], row["id"]) in observed_queues)
    }
    allocations = {row["id"]: row for row in rows["allocations"] if row["student_id"] in starts}
    checkpoints = [
        row
        for row in rows["checkpoints"]
        if row["student_id"] in cohorts and row["cohort_key"] == cohorts[row["student_id"]]
    ]
    attempts, resets, review_resets, learning_resets = Counter(), Counter(), Counter(), Counter()
    reset_causes = Counter()
    answered_slots = set()
    paused = defaultdict(set)
    pause_events = Counter()
    for event in events:
        queue = queues.get(event.get("queue_id"))
        if not queue or queue["student_id"] != event["student_id"]:
            continue
        allocation = allocations.get(event.get("allocation_id"))
        if (
            event["kind"] == "answer"
            and event["source"] == "review"
            and allocation
            and allocation["student_id"] == event["student_id"]
            and allocation["kind"] == "error"
            and allocation.get("queue_id") == queue["id"]
            and allocation["id"] not in answered_slots
        ):
            answered_slots.add(allocation["id"])
            attempts[queue["id"]] += 1
        if event["kind"] == "success_reset":
            resets[queue["id"]] += 1
            cause = (
                event["detail_code"]
                if event["detail_code"]
                in {"learning_error", "review_error", "sample_error", "maintenance_error"}
                else "other"
            )
            reset_causes[cause] += 1
            if cause == "review_error":
                review_resets[queue["id"]] += 1
            elif cause == "learning_error":
                learning_resets[queue["id"]] += 1
        if event["kind"] == "paused" and week_start <= _day(event["local_date"]) < week_end:
            paused[event["student_id"]].add(queue["sense_id"])
            pause_events[event["student_id"]] += 1
    teacher_words = defaultdict(set)
    for link in rows["teachers"]:
        if link["student_id"] in starts:
            teacher_words[link["teacher_id"]].update(
                (link["student_id"], sense) for sense in paused[link["student_id"]]
            )
    number = len(queues)
    public = {
        "as_of_utc": now.isoformat() + "Z",
        "cohort_to_date": True,
        "student_count": len(starts),
        "error_abilities": number,
        "formal_reviews_per_error_ability": _distribution([attempts[key] for key in queues]),
        "error_abilities_never_reviewed": sum(attempts[key] == 0 for key in queues),
        "success_resets": {
            "definition": "success_count>0 to 0 caused by an error; repeated 0-to-0 and new cycles excluded",
            "total": sum(resets.values()),
            "review_triggered": sum(review_resets.values()),
            "learning_triggered": sum(learning_resets.values()),
            "by_trigger": {
                cause: reset_causes[cause]
                for cause in (
                    "review_error",
                    "learning_error",
                    "sample_error",
                    "maintenance_error",
                    "other",
                )
            },
            "abilities_reset_at_least_twice": _rate(
                sum(resets[key] >= 2 for key in queues), number
            ),
            "abilities_review_reset_at_least_twice": _rate(
                sum(review_resets[key] >= 2 for key in queues), number
            ),
        },
        "weekly_pauses": {
            "week_start": week_start.isoformat(),
            "week_end": (week_end - timedelta(days=1)).isoformat(),
            "student_words": sum(len(paused[student]) for student in starts),
            "events": sum(pause_events.values()),
            "per_student_words": _distribution([len(paused[student]) for student in starts]),
            "per_teacher_student_words": _distribution(
                [len(words) for words in teacher_words.values()]
            ),
        },
        "retention": _checkpoint_metrics(checkpoints, events, allocations, now),
        "interpretation": {
            "reference_accuracy_band": [0.8, 0.85],
            "automatic_rule_change": False,
            "warning": "Small observed samples and incomplete coverage do not justify automatic rule changes.",
        },
    }
    return {
        "summary": public,
        "student_weekly_paused_words": {student: len(paused[student]) for student in starts},
    }
