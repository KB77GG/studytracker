"""Small, explicit metric populations: no real identities or answer text."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from scripts.evaluate_vocabulary_error_pilot import evaluate, readonly
from services import vocabulary_pilot_metrics as metrics

START = "2026-11-01 00:00:00.000000"
NOW = datetime(2026, 11, 20, 4)
COHORT = "20261101T000000.000000"


def population():
    return {
        "enrollments": [
            {"student_id": 1, "starts_at": START},
            {"student_id": 2, "starts_at": START},
        ],
        "queues": [],
        "events": [],
        "allocations": [],
        "checkpoints": [],
        "teachers": [],
    }


def queue(identifier, student=1, sense=11, dimension="meaning_recall"):
    return {
        "id": identifier,
        "student_id": student,
        "sense_id": sense,
        "dimension": dimension,
        "cohort_key": COHORT,
        "opened_at": "2026-11-02 04:00:00",
    }


def event(
    identifier,
    *,
    queue_id=None,
    student=1,
    kind="answer",
    source="review",
    allocation_id=None,
    checkpoint_id=None,
    correct=False,
    day="2026-11-17",
    detail=None,
):
    return {
        "id": identifier,
        "student_id": student,
        "queue_id": queue_id,
        "checkpoint_id": checkpoint_id,
        "allocation_id": allocation_id,
        "kind": kind,
        "source": source,
        "occurred_at": day + " 04:00:00",
        "local_date": day,
        "is_correct": correct,
        "detail_code": detail,
    }


def slot(identifier, *, student=1, queue_id=None, checkpoint_id=None, kind="error"):
    return {
        "id": identifier,
        "student_id": student,
        "queue_id": queue_id,
        "checkpoint_id": checkpoint_id,
        "kind": kind,
        "sense_id": 11,
        "dimension": "meaning_recall",
    }


def checkpoint(identifier, source="graduation", interval=7, due="2026-11-17", status="pending"):
    return {
        "id": identifier,
        "student_id": 1,
        "sense_id": 11,
        "dimension": "meaning_recall",
        "cohort_key": COHORT,
        "source_kind": source,
        "source_key": f"synthetic-{identifier}",
        "origin_event_id": None,
        "anchor_at": "2026-11-10 04:00:00",
        "due_local_date": due,
        "interval_days": interval,
        "status": status,
    }


class PilotMetricsAggregationTest(unittest.TestCase):
    def test_reset_ratio_counts_actual_progress_resets_not_all_wrong_answers(self):
        rows = population()
        rows["queues"] = [queue(1), queue(2, sense=12), queue(3, student=2)]
        rows["allocations"] = [slot(1, queue_id=1), slot(2, queue_id=2), slot(3, queue_id=2)]
        rows["events"] = [
            event(1, queue_id=1, allocation_id=1),
            event(2, queue_id=2, allocation_id=2),
            event(3, queue_id=2, allocation_id=3),
            event(4, queue_id=2, allocation_id=3),  # Defensive replay dedupe.
            event(5, queue_id=1, kind="success_reset", source="system", detail="review_error"),
            event(6, queue_id=1, kind="success_reset", source="system", detail="learning_error"),
            event(7, queue_id=1, kind="correction", allocation_id=1, correct=True),
            event(8, queue_id=1, kind="success_reset", detail="review_error", day="2026-12-01"),
        ]
        result = metrics.aggregate(rows, as_of=NOW)["summary"]
        self.assertEqual(result["formal_reviews_per_error_ability"]["sum"], 3)
        self.assertEqual(result["formal_reviews_per_error_ability"]["mean"], 1)
        self.assertEqual(result["error_abilities_never_reviewed"], 1)
        resets = result["success_resets"]
        self.assertEqual(
            (resets["total"], resets["review_triggered"], resets["learning_triggered"]), (2, 1, 1)
        )
        self.assertEqual(
            resets["abilities_reset_at_least_twice"],
            {"numerator": 1, "denominator": 3, "ratio": 0.333333},
        )

    def test_weekly_teacher_workload_deduplicates_abilities_but_not_students(self):
        rows = population()
        rows["queues"] = [queue(1), queue(2, dimension="form_recall"), queue(3, student=2)]
        rows["events"] = [
            event(1, queue_id=1, kind="paused"),
            event(2, queue_id=2, kind="paused"),
            event(3, queue_id=3, student=2, kind="paused"),
            event(4, queue_id=1, kind="paused", day="2026-11-15"),
        ]
        rows["teachers"] = [
            {"student_id": 1, "teacher_id": 10},
            {"student_id": 1, "teacher_id": 10},
            {"student_id": 2, "teacher_id": 10},
            {"student_id": 2, "teacher_id": 11},
        ]
        result = metrics.aggregate(rows, as_of=NOW)
        self.assertEqual(result["student_weekly_paused_words"], {1: 1, 2: 1})
        pause = result["summary"]["weekly_pauses"]
        self.assertEqual((pause["student_words"], pause["events"]), (2, 3))
        self.assertEqual(pause["per_teacher_student_words"]["mean"], 1.5)

    def test_graduation_retention_separates_timing_coverage_and_original_sources(self):
        rows = population()
        rows["checkpoints"] = [
            checkpoint(1, status="answered"),
            checkpoint(2, status="answered"),
            checkpoint(3, status="missed"),
            checkpoint(4, due="2026-11-20"),
            checkpoint(5, due="2026-11-23"),
            checkpoint(6, source="first_correct", status="answered"),
            checkpoint(7, source="first_correct", interval=30, due="2026-12-10"),
        ]
        rows["allocations"] = [slot(i, checkpoint_id=i, kind="sample") for i in (1, 2, 6)]
        rows["events"] = [
            event(1, allocation_id=1, checkpoint_id=1, correct=True),
            event(2, allocation_id=2, checkpoint_id=2, day="2026-11-18"),
            event(3, allocation_id=6, checkpoint_id=6, correct=True),
        ]
        result = metrics.aggregate(rows, as_of=NOW)["summary"]
        graduation = result["retention"]["graduation_d7"]
        self.assertEqual(graduation["first_accuracy"]["ratio"], 0.5)
        self.assertEqual(
            graduation["on_time_first_accuracy"], {"numerator": 1, "denominator": 1, "ratio": 1}
        )
        self.assertEqual(graduation["coverage"], {"numerator": 2, "denominator": 4, "ratio": 0.5})
        self.assertEqual(
            (
                graduation["unobserved"],
                graduation["missed"],
                graduation["pending_today"],
                graduation["not_yet_due"],
            ),
            (2, 1, 1, 1),
        )
        self.assertEqual(graduation["late_observed"], 1)
        self.assertEqual(graduation["delay_days"]["max"], 1)
        self.assertEqual(result["retention"]["first_correct_d7"]["observed"], 1)
        self.assertIsNone(result["retention"]["first_correct_d30"]["first_accuracy"]["ratio"])
        self.assertFalse(result["interpretation"]["automatic_rule_change"])

    def test_answered_status_without_first_event_does_not_count_as_success(self):
        rows = population()
        rows["checkpoints"] = [checkpoint(1, status="answered")]
        result = metrics.aggregate(rows, as_of=NOW)["summary"]["retention"]["graduation_d7"]
        self.assertEqual((result["unobserved"], result["status_answered_without_event"]), (1, 1))
        self.assertIsNone(result["first_accuracy"]["ratio"])

    def test_foreign_binding_and_pre_enrollment_events_do_not_count(self):
        rows = population()
        rows["queues"] = [queue(1)]
        rows["allocations"] = [slot(1, student=2, queue_id=1)]
        rows["events"] = [
            event(1, queue_id=1, allocation_id=1),
            event(2, queue_id=1, kind="paused", student=2),
            event(3, queue_id=1, kind="success_reset", detail="review_error", day="2026-10-30"),
        ]
        result = metrics.aggregate(rows, as_of=NOW)["summary"]
        self.assertEqual(result["formal_reviews_per_error_ability"]["sum"], 0)
        self.assertEqual(result["weekly_pauses"]["events"], 0)
        self.assertEqual(result["success_resets"]["total"], 0)

    def test_empty_population_has_null_rates_not_perfect_retention(self):
        rows = {name: [] for name in population()}
        result = metrics.aggregate(rows, as_of=NOW)["summary"]
        self.assertIsNone(result["success_resets"]["abilities_reset_at_least_twice"]["ratio"])
        self.assertEqual(result["student_count"], 0)
        for group in result["retention"].values():
            self.assertIsNone(group["coverage"]["ratio"])

    def test_sample_and_maintenance_actual_resets_are_separate_causes(self):
        rows = population()
        rows["queues"] = [queue(1)]
        rows["events"] = [
            event(1, queue_id=1, kind="success_reset", detail="sample_error"),
            event(2, queue_id=1, kind="success_reset", detail="maintenance_error"),
        ]
        result = metrics.aggregate(rows, as_of=NOW)["summary"]["success_resets"]
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["by_trigger"]["sample_error"], 1)
        self.assertEqual(result["by_trigger"]["maintenance_error"], 1)
        self.assertEqual(result["abilities_review_reset_at_least_twice"]["numerator"], 0)

    def test_historical_snapshot_keeps_prior_cycle_after_later_reopening(self):
        rows = population()
        rows["queues"] = [queue(1)]
        rows["queues"][0]["opened_at"] = "2026-12-01 04:00:00"
        rows["allocations"] = [slot(1, queue_id=1)]
        rows["events"] = [event(1, queue_id=1, allocation_id=1)]
        result = metrics.aggregate(rows, as_of=NOW)["summary"]
        self.assertEqual(result["error_abilities"], 1)
        self.assertEqual(result["formal_reviews_per_error_ability"]["sum"], 1)


class PilotMetricsReadOnlyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pilot-metrics-")
        self.path = str(Path(self.temp.name) / "synthetic.sqlite")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            for table, columns in metrics.READ_COLUMNS.items():
                definitions = []
                for column in sorted(columns):
                    kind = (
                        "INTEGER"
                        if column == "id"
                        or column.endswith("_id")
                        or column
                        in {"enabled", "is_active", "is_deleted", "interval_days", "is_correct"}
                        else "TEXT"
                    )
                    definitions.append(column + " " + kind)
                connection.execute(f"CREATE TABLE {table} ({','.join(definitions)})")
            connection.execute("ALTER TABLE student_profile ADD COLUMN full_name TEXT")
            connection.execute(
                "INSERT INTO vocabulary_review_policy_enrollment VALUES (1, ?, 1)", (START,)
            )
            # Alphabetical column order is enabled, starts_at, student_id.
            connection.execute(
                "INSERT INTO vocabulary_review_policy_enrollment VALUES (1, ?, 2)", (START,)
            )
            connection.execute(
                "INSERT INTO student_profile(id,user_id,primary_teacher_id,is_deleted,full_name) VALUES(1,1,10,0,'PRIVATE-SYNTHETIC-NAME')"
            )
            connection.execute("INSERT INTO user(id,role,is_active) VALUES(10,'teacher',1)")

    def tearDown(self):
        self.temp.cleanup()

    def test_cli_exports_only_aggregates_without_identity_fields(self):
        result = evaluate(self.path, student_ids=[1], as_of=NOW)
        self.assertEqual(result["student_count"], 1)
        exported = json.dumps(result)
        self.assertNotIn("PRIVATE-SYNTHETIC-NAME", exported)
        self.assertNotIn('"student_id"', exported)
        self.assertNotIn('"teacher_id"', exported)

    def test_readonly_connection_rejects_mutation_and_identity_reads(self):
        before = Path(self.path).read_bytes()
        with readonly(self.path) as connection:
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("DELETE FROM vocabulary_review_policy_enrollment")
            with self.assertRaises(sqlite3.DatabaseError):
                connection.execute("SELECT full_name FROM student_profile").fetchall()
            self.assertEqual(connection.total_changes, 0)
        self.assertEqual(Path(self.path).read_bytes(), before)

    def test_enrollment_is_visible_at_exact_start_timestamp(self):
        result = evaluate(self.path, as_of=START)
        self.assertEqual(result["student_count"], 2)


if __name__ == "__main__":
    unittest.main()
