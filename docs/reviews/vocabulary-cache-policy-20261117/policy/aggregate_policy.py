#!/usr/bin/env python3
"""Bounded, stdlib-only, read-only vocabulary policy aggregate audit.

No identity, answers, words, question text, tokens, or per-person rows leave
the process. Nothing here creates/changes a review queue or learning state.
"""

import argparse
import json
import signal
import sqlite3
import time
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIMENSIONS = ("meaning_recall", "form_recall", "audio_form_recall", "context_use")
OFFSET = timedelta(hours=8)
MAX_ROWS = 500_000
TABLE_COLUMNS = {
    "dictation_record": {
        "student_id",
        "task_id",
        "attempt_id",
        "created_at",
        "is_first_attempt",
        "vocabulary_task_review_id",
        "vocabulary_dimension",
        "is_correct",
        "response_kind",
    },
    "vocabulary_learning_question": {
        "student_id",
        "task_id",
        "first_attempt_id",
        "sense_id",
        "dimension",
        "score_eligible",
        "remediation_kind",
        "first_is_correct",
    },
    "vocabulary_task_review": {"id", "student_id", "task_id", "sense_id", "dimension"},
    "vocabulary_review_attempt": {
        "student_id",
        "session_id",
        "item_id",
        "submitted_at",
        "is_first_attempt",
        "is_correct",
        "response_kind",
    },
    "vocabulary_review_item": {"id", "student_id", "sense_id", "dimension"},
    "vocabulary_review_session": {"student_id", "status", "settled_at"},
    "vocabulary_learning_flow": {"student_id", "task_id", "completed_at"},
    "vocabulary_task_settlement": {"student_id", "task_id", "settled_at"},
    "student_vocabulary_mastery": {"student_id", "sense_id"}
    | {
        f"{dim}_{suffix}"
        for dim in DIMENSIONS
        for suffix in ("stage", "next_due_at", "last_answered_at")
    },
}


class AuditLimitError(Exception):
    pass


def parse_time(raw):
    value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017 — Python 3.10
    return value


def local_date(value):
    return (value + OFFSET).date()


def distribution(values):
    values = sorted(float(value) for value in values)
    if not values:
        return {"n": 0, "median": None, "p75": None, "p90": None, "max": None}

    def quantile(fraction):
        position = (len(values) - 1) * fraction
        lo = int(position)
        hi = min(lo + 1, len(values) - 1)
        return round(values[lo] + (values[hi] - values[lo]) * (position - lo), 4)

    return {
        "n": len(values),
        "median": quantile(0.5),
        "p75": quantile(0.75),
        "p90": quantile(0.9),
        "max": round(values[-1], 4),
    }


class ReadOnlyAudit:
    def __init__(self, connection, query_seconds=3, total_seconds=20, max_rows=MAX_ROWS):
        self.connection = connection
        self.query_seconds = query_seconds
        self.total_deadline = time.monotonic() + total_seconds
        self.query_deadline = self.total_deadline
        self.max_rows = max_rows
        self.queries = 0
        self.denied = 0
        self.phase = "verify_readonly"
        connection.set_authorizer(self.authorize)
        connection.set_progress_handler(self.progress, 5000)

    def authorize(self, action, arg1, arg2, _database, _trigger):
        allowed = False
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
            allowed = True
        elif action == sqlite3.SQLITE_READ:
            allowed = arg1 in TABLE_COLUMNS and (arg2 in TABLE_COLUMNS[arg1] or arg2 == "")
        elif action == sqlite3.SQLITE_FUNCTION:
            allowed = (arg2 or "").lower() in {"coalesce", "count", "min", "max"}
        elif action == sqlite3.SQLITE_PRAGMA:
            allowed = arg1 == "query_only" and arg2 is None
        if not allowed:
            self.denied += 1
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY

    def progress(self):
        return int(time.monotonic() > min(self.query_deadline, self.total_deadline))

    def rows(self, query, parameters=()):
        if time.monotonic() > self.total_deadline:
            raise AuditLimitError("audit_time_budget_exceeded")
        self.queries += 1
        if self.queries > 16:
            raise AuditLimitError("audit_query_budget_exceeded")
        self.query_deadline = min(self.total_deadline, time.monotonic() + self.query_seconds)
        cursor = self.connection.execute(query, parameters)
        try:
            rows = cursor.fetchmany(self.max_rows + 1)
            if len(rows) > self.max_rows:
                raise AuditLimitError("audit_row_budget_exceeded")
            return rows
        finally:
            cursor.close()


@contextmanager
def open_readonly(path, **kwargs):
    path = Path(path).resolve(strict=True)
    # URI escaping is handled by as_uri; no immutable=1 shortcut on a live DB.
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.25)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA busy_timeout=250")
        guard = ReadOnlyAudit(connection, **kwargs)
        assert guard.rows("PRAGMA query_only")[0][0] == 1
        yield guard
        assert connection.total_changes == 0
    finally:
        connection.close()


def load_data(audit, start, end, snapshot_at):
    bounds = (start.isoformat(" "), end.isoformat(" "))
    audit.phase = "read_learning_events"
    learning = audit.rows(
        """
        SELECT r.student_id, r.task_id, q.sense_id, q.dimension,
               r.created_at AS at, r.is_correct, r.response_kind,
               q.score_eligible, q.remediation_kind
        FROM vocabulary_learning_question AS q
        CROSS JOIN dictation_record AS r
        WHERE q.student_id=r.student_id AND q.task_id=r.task_id
          AND q.first_attempt_id=r.attempt_id
          AND r.created_at>=? AND r.created_at<? AND r.is_first_attempt=1
          AND q.first_is_correct IS NOT NULL
    """,
        bounds,
    )
    audit.phase = "read_legacy_events"
    legacy = audit.rows(
        """
        SELECT r.student_id, r.task_id, q.sense_id, q.dimension,
               r.created_at AS at, r.is_correct, r.response_kind,
               1 AS score_eligible, NULL AS remediation_kind
        FROM dictation_record AS r
        JOIN vocabulary_task_review AS q ON q.id=r.vocabulary_task_review_id
         AND q.student_id=r.student_id AND q.task_id=r.task_id
        WHERE r.created_at>=? AND r.created_at<? AND r.is_first_attempt=1
    """,
        bounds,
    )
    audit.phase = "read_review_events"
    reviews = audit.rows(
        """
        SELECT a.student_id, a.session_id, i.sense_id, i.dimension,
               a.submitted_at AS at, a.is_correct, a.response_kind
        FROM vocabulary_review_attempt AS a
        JOIN vocabulary_review_item AS i ON i.id=a.item_id AND i.student_id=a.student_id
        WHERE a.submitted_at>=? AND a.submitted_at<? AND a.is_first_attempt=1
    """,
        bounds,
    )
    audit.phase = "read_review_settlements"
    settled = audit.rows(
        """
        SELECT student_id, settled_at AS at FROM vocabulary_review_session
        WHERE settled_at>=? AND settled_at<? AND status='settled'
    """,
        bounds,
    )
    audit.phase = "read_task_completions"
    completed = audit.rows(
        """
        SELECT student_id, task_id, completed_at AS at FROM vocabulary_learning_flow
        WHERE completed_at>=? AND completed_at<?
        UNION ALL
        SELECT t.student_id, t.task_id, t.settled_at AS at FROM vocabulary_task_settlement AS t
        LEFT JOIN vocabulary_learning_flow AS f
          ON f.student_id=t.student_id AND f.task_id=t.task_id
        WHERE t.settled_at>=? AND t.settled_at<? AND f.completed_at IS NULL
    """,
        bounds + bounds,
    )
    columns = ", ".join(
        f"{dim}_{suffix}"
        for dim in DIMENSIONS
        for suffix in ("stage", "next_due_at", "last_answered_at")
    )
    where = " OR ".join(f"{dim}_next_due_at<=?" for dim in DIMENSIONS)
    audit.phase = "read_mastery_snapshot"
    mastery = audit.rows(
        f"SELECT student_id, sense_id, {columns} FROM student_vocabulary_mastery WHERE {where}",
        (snapshot_at.isoformat(" "),) * len(DIMENSIONS),
    )
    audit.phase = "read_linkage_denominator"
    quality = audit.rows(
        """
        SELECT count(*) AS n FROM dictation_record
        WHERE created_at>=? AND created_at<? AND is_first_attempt=1
          AND vocabulary_dimension IS NOT NULL
    """,
        bounds,
    )[0][0]
    return learning, legacy, reviews, settled, completed, mastery, quality


def events_from_rows(rows, source, quality):
    result = []
    for row in rows:
        if row["dimension"] not in DIMENSIONS or row["is_correct"] not in (0, 1):
            quality["invalid_dimension_or_result"] += 1
            continue
        try:
            at = parse_time(row["at"])
        except (ValueError, TypeError):
            quality["invalid_event_time"] += 1
            continue
        response_kind = row["response_kind"] or "answer"
        if response_kind not in {"answer", "forgot"}:
            quality["unknown_response_kind"] += 1
            continue
        result.append(
            {
                "student": row["student_id"],
                "task": row["task_id"] if source == "learning" else None,
                "session": row["session_id"] if source == "review" else None,
                "sense": row["sense_id"],
                "dimension": row["dimension"],
                "at": at,
                "date": local_date(at),
                "correct": bool(row["is_correct"]) and response_kind != "forgot",
                "forgot": response_kind == "forgot",
                "source": source,
            }
        )
    return result


def task_errors(events):
    output = {}
    for dimension in ("all",) + DIMENSIONS:
        groups = defaultdict(lambda: defaultdict(list))
        for event in events:
            if dimension == "all" or dimension == event["dimension"]:
                groups[(event["student"], event["task"])][event["sense"]].append(event)
        per_student = defaultdict(list)
        wrong_counts, rates = [], []
        for (student, _), senses in groups.items():
            wrong = sum(any(not item["correct"] for item in answers) for answers in senses.values())
            rate = wrong / len(senses)
            per_student[student].append((wrong, rate, len(senses)))
            wrong_counts.append(wrong)
            rates.append(rate)
        output[dimension] = {
            "tasks_observed": len(groups),
            "students_observed": len(per_student),
            "task_wrong_senses": distribution(wrong_counts),
            "task_wrong_fraction": distribution(rates),
            "student_mean_wrong_senses_per_task": distribution(
                sum(row[0] for row in rows) / len(rows) for rows in per_student.values()
            ),
            "student_mean_task_wrong_fraction": distribution(
                sum(row[1] for row in rows) / len(rows) for rows in per_student.values()
            ),
            "tested_sense_task_pairs": sum(row[2] for rows in per_student.values() for row in rows),
            "wrong_sense_task_pairs": sum(wrong_counts),
        }
    return output


def backlog_snapshot(rows, snapshot_at, active_students):
    categories = (
        "stage0_answered_marker",
        "stage0_unanswered",
        "normal_consolidation",
        "stage6_maintenance",
        "invalid_state",
    )
    output = {}
    for population, include in (("all_due_students", None), ("active_28d", active_students)):
        per_student = defaultdict(Counter)
        dimensions = Counter()
        senses = Counter()
        overlaps = Counter()
        for row in rows:
            if include is not None and row["student_id"] not in include:
                continue
            memberships = set()
            for dimension in DIMENSIONS:
                raw_due = row[f"{dimension}_next_due_at"]
                if not raw_due or parse_time(raw_due) > snapshot_at:
                    continue
                stage = row[f"{dimension}_stage"]
                last = row[f"{dimension}_last_answered_at"]
                if stage == 0:
                    category = "stage0_answered_marker" if last else "stage0_unanswered"
                elif stage in range(1, 6):
                    category = "normal_consolidation"
                elif stage == 6:
                    category = "stage6_maintenance"
                else:
                    category = "invalid_state"
                dimensions[category] += 1
                memberships.add(category)
            if not memberships:
                continue
            per_student[row["student_id"]]["all_due_senses"] += 1
            for category in memberships:
                overlaps[category] += 1
                per_student[row["student_id"]][category] += 1
            # Exclusive sense composition: error marker > untested > consolidation > maintenance.
            senses[next(category for category in categories if category in memberships)] += 1
        output[population] = {
            "students_with_raw_due": len(per_student),
            "raw_due_dimension_count": sum(dimensions.values()),
            "raw_due_sense_count": sum(senses.values()),
            "dimension_composition": dict(dimensions),
            "sense_exclusive_priority_composition": dict(senses),
            "sense_overlapping_memberships": dict(overlaps),
            "student_due_sense_distribution": distribution(
                row["all_due_senses"] for row in per_student.values()
            ),
            "student_error_marker_sense_distribution": distribution(
                row["stage0_answered_marker"] for row in per_student.values()
            ),
            "student_error_marker_fraction": distribution(
                row["stage0_answered_marker"] / row["all_due_senses"]
                for row in per_student.values()
            ),
        }
    return output


def capacity(events, settled, completed, start_date, end_date):
    daily = defaultdict(lambda: Counter({"answers": 0, "batches": 0}))
    for event in events:
        daily[(event["student"], event["date"])]["answers"] += int(event["source"] == "review")
    for row in settled:
        day = local_date(parse_time(row["at"]))
        daily[(row["student_id"], day)]["batches"] += 1
    for row in completed:
        daily[(row["student_id"], local_date(parse_time(row["at"])))]["completed_tasks"] += 1
    students = {key[0] for key in daily}
    student_means = defaultdict(list)
    for (student, _), value in daily.items():
        student_means[student].append(value)
    calendar_days = (end_date - start_date).days
    output = {
        "active_students": len(students),
        "vocabulary_learning_student_days": len(daily),
        "calendar_student_days_including_zero": len(students) * calendar_days,
    }
    for metric in ("answers", "batches"):
        values = [row[metric] for row in daily.values()]
        output[metric] = {
            "total": sum(values),
            "on_vocabulary_learning_days": distribution(values),
            "on_review_positive_days": distribution(value for value in values if value > 0),
            "on_all_calendar_days": distribution(
                values + [0] * (len(students) * calendar_days - len(daily))
            ),
            "student_mean_on_learning_days": distribution(
                sum(row[metric] for row in rows) / len(rows) for rows in student_means.values()
            ),
            "student_mean_on_calendar_days": distribution(
                sum(row[metric] for row in rows) / calendar_days for rows in student_means.values()
            ),
        }
    return output, students


def elapsed_proxy(events):
    sessions = defaultdict(list)
    for event in events:
        if event["source"] == "review":
            sessions[(event["student"], event["session"])].append(event)
    gaps = []
    nonpositive = 0
    for (student, _), items in sessions.items():
        items.sort(key=lambda event: event["at"])
        for previous, current in zip(items, items[1:], strict=False):
            seconds = (current["at"] - previous["at"]).total_seconds()
            if seconds <= 0:
                nonpositive += 1
            else:
                gaps.append((student, seconds))
    output = {"positive_adjacent_pairs": len(gaps), "nonpositive_pairs_excluded": nonpositive}
    for cap in (30, 60, 120):
        retained = [(student, seconds) for student, seconds in gaps if seconds <= cap]
        by_student = defaultdict(list)
        for student, seconds in retained:
            by_student[student].append(seconds)
        output[f"max_gap_{cap}s"] = {
            "long_pauses_excluded": len(gaps) - len(retained),
            "seconds": distribution(seconds for _, seconds in retained),
            "student_median_seconds": distribution(
                distribution(values)["median"] for values in by_student.values()
            ),
        }
    return output


def delayed_results(events, end_date):
    by_key = defaultdict(lambda: defaultdict(list))
    for event in events:
        by_key[(event["student"], event["sense"], event["dimension"])][event["date"]].append(event)
    origins = []
    for (student, _, dimension), days in by_key.items():
        ordered_days = sorted(days)
        for index, day in enumerate(ordered_days):
            current = sorted(days[day], key=lambda event: event["at"])
            if not any(not event["correct"] for event in current):
                continue
            following = (
                min(days[ordered_days[index + 1]], key=lambda event: event["at"])
                if index + 1 < len(ordered_days)
                else None
            )
            origins.append((student, dimension, day, following, len(current)))
    output = {}
    for dimension in ("all",) + DIMENSIONS:
        selected = [row for row in origins if dimension == "all" or row[1] == dimension]
        measures = {
            "wrong_sense_dimension_days": len(selected),
            "wrong_days_with_multiple_formal_exposures": sum(row[4] > 1 for row in selected),
        }
        for gap in (1, 2, 3):
            # end_date is exclusive; target day must have fully elapsed.
            mature = [row for row in selected if row[2] + timedelta(days=gap) < end_date]
            returned = [
                row
                for row in mature
                if row[3] is not None and (row[3]["date"] - row[2]).days == gap
            ]
            correct = sum(row[3]["correct"] for row in returned)
            by_student = defaultdict(list)
            for row in returned:
                by_student[row[0]].append(row[3]["correct"])
            measures[f"first_later_day_gap_{gap}"] = {
                "eligible_error_days": len(mature),
                "observed_retests": len(returned),
                "correct": correct,
                "correct_fraction_among_retested": (
                    round(correct / len(returned), 4) if returned else None
                ),
                "observation_fraction": round(len(returned) / len(mature), 4) if mature else None,
                "students_retested": len(by_student),
                "retest_source_counts": dict(Counter(row[3]["source"] for row in returned)),
                "student_correct_fraction": distribution(
                    sum(values) / len(values) for values in by_student.values()
                ),
            }
        output[dimension] = measures
    return output


def weekly_activity(events, completed, start_date, end_date, students):
    weeks = max(1, (end_date - start_date).days // 7)
    counts = defaultdict(set)
    completed_counts = defaultdict(set)
    for event in events:
        if event["task"] is not None:
            week = (event["date"] - start_date).days // 7
            counts[(event["student"], week)].add(event["task"])
    for row in completed:
        week = (local_date(parse_time(row["at"])) - start_date).days // 7
        completed_counts[(row["student_id"], week)].add(row["task_id"])
    return {
        "rolling_seven_day_blocks": weeks,
        "active_students": len(students),
        "student_week_denominator_including_zero": len(students) * weeks,
        "tasks_with_formal_answer_per_student_week": distribution(
            len(counts[(student, week)]) for student in students for week in range(weeks)
        ),
        "completed_tasks_per_student_week": distribution(
            len(completed_counts[(student, week)]) for student in students for week in range(weeks)
        ),
        "student_mean_completed_tasks_per_week": distribution(
            sum(len(completed_counts[(student, week)]) for week in range(weeks)) / weeks
            for student in students
        ),
    }


def analyze(audit, snapshot_at):
    end_date = local_date(snapshot_at)
    end = datetime.combine(end_date, datetime.min.time()) - OFFSET
    start = end - timedelta(days=28)
    loaded = load_data(audit, start, end, snapshot_at)
    audit.phase = "validate_event_linkage"
    (
        learning_rows,
        legacy_rows,
        review_rows,
        settled_rows,
        completed_rows,
        mastery,
        raw_record_count,
    ) = loaded
    quality = Counter()
    # Guidance and within-task remedial encounters are separate from the first
    # scored task exposure. Remediation outcomes are not independent recall.
    base_rows = [
        row for row in learning_rows if row["score_eligible"] and not row["remediation_kind"]
    ]
    quality["excluded_guidance_or_remediation_learning_rows"] = len(learning_rows) - len(base_rows)
    quality["observed_first_vocabulary_dictation_records"] = raw_record_count
    quality["joined_learning_first_records"] = len(learning_rows) + len(legacy_rows)
    quality["unjoined_first_records"] = raw_record_count - len(learning_rows) - len(legacy_rows)
    if quality["unjoined_first_records"] < 0:
        raise AuditLimitError("duplicate_learning_record_join")
    learning = events_from_rows(base_rows + legacy_rows, "learning", quality)
    review = events_from_rows(review_rows, "review", quality)
    events = learning + review
    output = {
        "schema_version": 1,
        "snapshot_utc": snapshot_at.isoformat() + "Z",
        "timezone": "Asia/Shanghai",
        "complete_days_end_exclusive": end_date.isoformat(),
        "quality": dict(quality),
        "windows": {},
    }
    active28 = set()
    for days in (28, 7):
        audit.phase = "aggregate_28d" if days == 28 else "aggregate_7d"
        if time.monotonic() > audit.total_deadline:
            raise AuditLimitError("audit_time_budget_exceeded")
        window_start = end_date - timedelta(days=days)
        subset = [event for event in events if window_start <= event["date"] < end_date]
        filtered_settled = [
            row
            for row in settled_rows
            if window_start <= local_date(parse_time(row["at"])) < end_date
        ]
        filtered_completed = [
            row
            for row in completed_rows
            if window_start <= local_date(parse_time(row["at"])) < end_date
        ]
        volume, active = capacity(
            subset, filtered_settled, filtered_completed, window_start, end_date
        )
        if days == 28:
            active28 = active
        output["windows"][f"{days}d"] = {
            "start_inclusive": window_start.isoformat(),
            "end_exclusive": end_date.isoformat(),
            "task_first_errors": task_errors(
                [event for event in subset if event["source"] == "learning"]
            ),
            "daily_review_capacity": volume,
            "answer_interval_proxy": elapsed_proxy(subset),
            "delayed_first_retests": delayed_results(subset, end_date),
            "weekly_vocabulary_activity": weekly_activity(
                subset, filtered_completed, window_start, end_date, active
            ),
        }
    audit.phase = "aggregate_mastery"
    output["backlog_snapshot"] = backlog_snapshot(mastery, snapshot_at, active28)
    if time.monotonic() > audit.total_deadline:
        raise AuditLimitError("audit_time_budget_exceeded")
    output["safety"] = {
        "query_only": True,
        "uri_mode_ro": True,
        "write_authorizer_denied": True,
        "successful_changes": audit.connection.total_changes,
        "denied_statements": audit.denied,
        "queries": audit.queries,
        "per_query_seconds": audit.query_seconds,
        "row_cap_per_query": audit.max_rows,
        "explicit_read_transaction": False,
        "identity_or_answer_rows_exported": False,
    }
    return output


def failure_diagnostics(error, audit, started):
    """Export only fixed labels and counters, never raw exception/SQL text."""
    reason = "unexpected_audit_error"
    fixed_limits = {
        "audit_time_budget_exceeded",
        "audit_query_budget_exceeded",
        "audit_row_budget_exceeded",
        "audit_wall_clock_budget_exceeded",
        "duplicate_learning_record_join",
    }
    if isinstance(error, AuditLimitError) and str(error) in fixed_limits:
        reason = str(error)
    elif isinstance(error, sqlite3.Error):
        message = str(error).lower()
        if "interrupted" in message:
            reason = "sqlite_query_interrupted"
        elif audit is not None and audit.denied:
            reason = "authorizer_rejected_statement"
        elif message.startswith(("no such table:", "no such column:")):
            reason = "schema_mismatch"
        elif "locked" in message or "busy" in message:
            reason = "sqlite_lock_wait"
        else:
            reason = "sqlite_error"
    elif isinstance(error, OSError):
        reason = "database_open_or_io_error"
    elif isinstance(error, ValueError):
        reason = "invalid_aggregate_value"
    elif isinstance(error, AssertionError):
        reason = "readonly_assertion_failed"
    return {
        "ok": False,
        "error": "readonly_audit_failed_or_budget_exceeded",
        "diagnostic": {
            "error_class": type(error).__name__,
            "reason": reason,
            "phase": audit.phase if audit is not None else "open_readonly_database",
            "query_ordinal": audit.queries if audit is not None else 0,
            "denied_statements": audit.denied if audit is not None else 0,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()

    def stop_for_budget(_signal, _frame):
        raise AuditLimitError("audit_wall_clock_budget_exceeded")

    previous_handler = signal.signal(signal.SIGALRM, stop_for_budget)
    signal.setitimer(signal.ITIMER_REAL, 25)
    started = time.monotonic()
    audit = None
    try:
        snapshot_at = datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: UP017 — Python 3.10
        with open_readonly(args.database) as audit:
            result = analyze(audit, snapshot_at)
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (sqlite3.Error, AuditLimitError, ValueError, OSError, AssertionError) as error:
        # Never print exception strings: they may contain paths/SQL/data.
        print(json.dumps(failure_diagnostics(error, audit, started)))
        raise SystemExit(1) from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


if __name__ == "__main__":
    main()
