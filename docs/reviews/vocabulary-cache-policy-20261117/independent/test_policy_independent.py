"""Independent B1 read-only fencing, real ORM schema, and denominator checks."""

import importlib.util
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from models import db

SCRIPT = Path(__file__).resolve().parents[1] / "policy" / "aggregate_policy.py"
SPEC = importlib.util.spec_from_file_location("policy_aggregate_independent", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def event(day, *, student=987654321, task=876543210, sense=765432109, correct=True,
          dimension="meaning_recall", source="learning"):
    at = datetime(2026, 11, day, 4)
    return {"student": student, "task": task if source == "learning" else None,
            "session": 654321098 if source == "review" else None,
            "sense": sense, "dimension": dimension, "at": at,
            "date": audit.local_date(at), "correct": correct, "forgot": False,
            "source": source}


class SafetyAndSchemaTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # URI escaping must preserve special path characters.
        self.path = Path(self.temporary.name) / "audit ?#& fixture.sqlite"
        engine = create_engine(URL.create("sqlite", database=str(self.path)))
        db.metadata.create_all(engine, tables=[db.metadata.tables[name] for name in audit.TABLE_COLUMNS])
        engine.dispose()

    def test_whitelisted_columns_exist_in_real_orm_and_empty_full_audit_runs(self):
        for table, columns in audit.TABLE_COLUMNS.items():
            self.assertTrue(columns <= set(db.metadata.tables[table].columns.keys()), table)
        with audit.open_readonly(self.path) as guard:
            result = audit.analyze(guard, datetime(2026, 11, 17, 4))
            self.assertEqual(result["safety"]["successful_changes"], 0)
            self.assertEqual(result["windows"]["28d"]["daily_review_capacity"]["active_students"], 0)
            self.assertFalse(result["safety"]["explicit_read_transaction"])

    def test_sensitive_columns_and_write_surfaces_are_denied(self):
        statements = [
            "SELECT student_answer FROM dictation_record",
            "SELECT answer_payload_json FROM vocabulary_review_item",
            "SELECT * FROM sqlite_master",
            "SELECT load_extension('irrelevant')",
            "DELETE FROM student_vocabulary_mastery",
            "UPDATE student_vocabulary_mastery SET meaning_recall_stage=1",
            "CREATE TABLE should_not_exist(value)",
            "PRAGMA query_only=OFF",
            "ATTACH DATABASE ':memory:' AS other",
        ]
        with audit.open_readonly(self.path) as guard:
            for statement in statements:
                with self.subTest(statement=statement):
                    with self.assertRaises(sqlite3.DatabaseError):
                        guard.connection.execute(statement)
            self.assertEqual(guard.connection.total_changes, 0)
            self.assertGreaterEqual(guard.denied, len(statements))

    def test_uri_readonly_remains_when_other_fences_are_disabled_in_synthetic_test(self):
        with audit.open_readonly(self.path) as guard:
            guard.connection.set_authorizer(lambda *_args: sqlite3.SQLITE_OK)
            guard.connection.execute("PRAGMA query_only=OFF")
            with self.assertRaises(sqlite3.OperationalError):
                guard.connection.execute("CREATE TABLE should_not_exist(value)")
            self.assertEqual(guard.connection.total_changes, 0)

    def test_row_and_time_budgets_stop_queries(self):
        with audit.open_readonly(self.path, max_rows=1) as guard:
            with self.assertRaises(audit.AuditLimitError):
                guard.rows("SELECT 1 UNION ALL SELECT 2")
        with self.assertRaises(audit.AuditLimitError):
            with audit.open_readonly(self.path, total_seconds=-1):
                pass


class MetricDenominatorTest(unittest.TestCase):
    def test_shanghai_boundary_is_not_utc_midnight(self):
        before = datetime(2026, 11, 16, 15, 59, 59)
        self.assertEqual(str(audit.local_date(before)), "2026-11-16")
        self.assertEqual(str(audit.local_date(before + timedelta(seconds=1))), "2026-11-17")

    def test_task_sense_dedup_and_dimension_separation(self):
        rows = [event(5, correct=False), event(5), event(5, dimension="form_recall")]
        result = audit.task_errors(rows)
        self.assertEqual(result["all"]["tested_sense_task_pairs"], 1)
        self.assertEqual(result["all"]["wrong_sense_task_pairs"], 1)
        self.assertEqual(result["meaning_recall"]["wrong_sense_task_pairs"], 1)
        self.assertEqual(result["form_recall"]["wrong_sense_task_pairs"], 0)
        encoded = json.dumps(result)
        for private_identifier in ("987654321", "876543210", "765432109"):
            self.assertNotIn(private_identifier, encoded)

    def test_capacity_counts_learning_days_with_zero_reviews_and_zero_calendar_days(self):
        rows = [event(5), event(6, source="review")]
        start, end = datetime(2026, 11, 5).date(), datetime(2026, 11, 12).date()
        result, students = audit.capacity(rows, [], [], start, end)
        self.assertEqual(len(students), 1)
        self.assertEqual(result["vocabulary_learning_student_days"], 2)
        self.assertEqual(result["calendar_student_days_including_zero"], 7)
        self.assertEqual(result["answers"]["on_vocabulary_learning_days"]["median"], .5)
        self.assertEqual(result["answers"]["on_all_calendar_days"]["median"], 0)

    def test_first_later_day_retest_is_not_every_later_correct_answer(self):
        rows = [event(5, correct=False), event(6), event(8),
                event(6, sense=888, correct=False),
                event(9, sense=999, correct=False)]
        result = audit.delayed_results(rows, datetime(2026, 11, 10).date())["all"]
        day1 = result["first_later_day_gap_1"]
        self.assertEqual(day1["eligible_error_days"], 2)
        self.assertEqual(day1["observed_retests"], 1)
        self.assertEqual(day1["observation_fraction"], .5)
        self.assertEqual(day1["correct_fraction_among_retested"], 1)
        day3 = result["first_later_day_gap_3"]
        self.assertEqual(day3["observed_retests"], 0)
        self.assertIsNone(day3["correct_fraction_among_retested"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
