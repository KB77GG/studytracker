import hashlib
import importlib.util
import json
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("aggregate_policy.py")
SPEC = importlib.util.spec_from_file_location("aggregate_policy", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def event(
    student,
    sense,
    date,
    correct,
    *,
    dimension="meaning_recall",
    source="review",
    session=1,
    task=None,
):
    at = datetime.fromisoformat(date)
    return {
        "student": student,
        "sense": sense,
        "dimension": dimension,
        "at": at,
        "date": audit.local_date(at),
        "correct": correct,
        "forgot": False,
        "source": source,
        "session": session,
        "task": task,
    }


class AggregatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fixture.db"
        self.db = sqlite3.connect(self.path)
        self.counter = 0
        for table, columns in audit.TABLE_COLUMNS.items():
            declarations = []
            for column in sorted(columns):
                number = (
                    column.endswith("_id")
                    and column != "attempt_id"
                    and column != "first_attempt_id"
                )
                number |= column.endswith("_stage") or column in {
                    "is_correct",
                    "first_is_correct",
                    "is_first_attempt",
                    "score_eligible",
                    "id",
                }
                declarations.append(f'"{column}" {"INTEGER" if number else "TEXT"}')
            if table == "dictation_record":
                declarations.append("student_answer TEXT")
            self.db.execute(f"CREATE TABLE {table} ({', '.join(declarations)})")
        self.db.execute("CREATE TABLE user (id INTEGER, name TEXT)")
        self.db.execute("INSERT INTO user VALUES (90210, 'PRIVATE_NAME_CANARY')")
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def insert(self, table, **values):
        columns = ",".join(values)
        marks = ",".join("?" for _ in values)
        self.db.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(values.values()))

    def learning(
        self,
        *,
        student=90210,
        task=80123,
        sense=70123,
        at="2026-11-10 12:00:00",
        correct=0,
        eligible=1,
        remediation=None,
        first=1,
        dimension="meaning_recall",
        forgot=False,
    ):
        self.counter += 1
        attempt = f"PRIVATE_ATTEMPT_{self.counter}"
        self.insert(
            "vocabulary_learning_question",
            student_id=student,
            task_id=task,
            sense_id=sense,
            dimension=dimension,
            first_attempt_id=attempt,
            score_eligible=eligible,
            remediation_kind=remediation,
            first_is_correct=correct,
        )
        self.insert(
            "dictation_record",
            student_id=student,
            task_id=task,
            created_at=at,
            is_correct=correct,
            response_kind="forgot" if forgot else "answer",
            is_first_attempt=first,
            attempt_id=attempt,
            vocabulary_dimension=dimension,
            student_answer="PRIVATE_ANSWER_CANARY",
        )

    def review(
        self,
        *,
        student=90210,
        sense=70123,
        at="2026-11-11 12:00:00",
        correct=1,
        first=1,
        session=60123,
    ):
        self.counter += 1
        self.insert(
            "vocabulary_review_item",
            id=self.counter,
            student_id=student,
            sense_id=sense,
            dimension="meaning_recall",
        )
        self.insert(
            "vocabulary_review_attempt",
            student_id=student,
            session_id=session,
            item_id=self.counter,
            submitted_at=at,
            is_first_attempt=first,
            is_correct=correct,
            response_kind="answer",
        )

    def test_readonly_and_column_privacy_guards_reject_mutations_and_identity(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with audit.open_readonly(self.path) as guard:
            for sql in (
                "UPDATE dictation_record SET is_correct=1",
                "DELETE FROM dictation_record",
                "CREATE TABLE illegal (id INTEGER)",
                "PRAGMA query_only=OFF",
                "ATTACH DATABASE ':memory:' AS other",
                "SELECT name FROM user",
                "SELECT student_answer FROM dictation_record",
                "SELECT load_extension('x')",
            ):
                with self.subTest(sql=sql), self.assertRaises(sqlite3.DatabaseError):
                    guard.connection.execute(sql)
            self.assertEqual(guard.connection.total_changes, 0)
        self.assertEqual(before, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_row_and_time_budgets_fail_closed(self):
        self.learning()
        self.learning(task=80124)
        self.db.commit()
        with audit.open_readonly(self.path, max_rows=1) as guard:
            with self.assertRaises(audit.AuditLimitError):
                guard.rows("SELECT student_id FROM dictation_record")
        with audit.open_readonly(self.path) as guard:
            guard.total_deadline = 0
            with self.assertRaises(audit.AuditLimitError):
                guard.rows("SELECT student_id FROM dictation_record")

    def test_failure_diagnostics_never_export_exception_sql_or_values(self):
        with audit.open_readonly(self.path) as guard:
            guard.phase = "read_learning_events"
            samples = [
                (
                    sqlite3.OperationalError("no such column: PRIVATE_COLUMN_CANARY"),
                    "schema_mismatch",
                ),
                (sqlite3.OperationalError("interrupted"), "sqlite_query_interrupted"),
                (
                    audit.AuditLimitError("duplicate_learning_record_join"),
                    "duplicate_learning_record_join",
                ),
                (ValueError("PRIVATE_ANSWER_CANARY"), "invalid_aggregate_value"),
            ]
            for error, reason in samples:
                result = audit.failure_diagnostics(error, guard, time.monotonic())
                self.assertEqual(result["diagnostic"]["reason"], reason)
                self.assertEqual(result["diagnostic"]["phase"], "read_learning_events")
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_cross_join_matches_original_with_shared_attempts_and_exclusions(self):
        self.learning(student=90210, task=80123, sense=70123)
        self.learning(student=90211, task=80124, sense=70124, correct=1)
        # Attempt id is only unique inside one student; cross-student collisions
        # must not attach one student's result to the other student's question.
        self.db.execute(
            "UPDATE dictation_record SET attempt_id='shared' WHERE student_id IN (90210,90211)"
        )
        self.db.execute(
            "UPDATE vocabulary_learning_question SET first_attempt_id='shared' WHERE student_id IN (90210,90211)"
        )
        self.insert(
            "vocabulary_learning_question",
            student_id=90210,
            task_id=89999,
            sense_id=79999,
            dimension="meaning_recall",
            first_attempt_id="shared",
            score_eligible=1,
            first_is_correct=0,
        )
        self.learning(sense=70125, eligible=0)  # Guidance retained for downstream filtering.
        self.learning(sense=70126, remediation="related")
        self.learning(sense=70127, first=0)  # Retry excluded from first records.
        self.learning(sense=70128, correct=None)  # Missing first result excluded.
        self.learning(sense=70129, at="2026-11-09 12:00:00")
        self.learning(sense=70130, at="2026-11-12 00:00:00")
        self.db.execute(
            "CREATE UNIQUE INDEX uq_dictation_record_student_attempt ON dictation_record(student_id,attempt_id)"
        )
        self.db.execute(
            "CREATE INDEX ix_dictation_record_created_at ON dictation_record(created_at)"
        )
        self.db.execute(
            "CREATE INDEX ix_vocabulary_learning_question_student_id ON vocabulary_learning_question(student_id)"
        )
        self.db.commit()
        start, end = datetime(2026, 11, 10), datetime(2026, 11, 12)
        original = """
            SELECT r.student_id, r.task_id, q.sense_id, q.dimension,
                   r.created_at AS at, r.is_correct, r.response_kind,
                   q.score_eligible, q.remediation_kind
            FROM dictation_record AS r
            JOIN vocabulary_learning_question AS q
              ON q.student_id=r.student_id AND q.task_id=r.task_id
             AND q.first_attempt_id=r.attempt_id
            WHERE r.created_at>=? AND r.created_at<? AND r.is_first_attempt=1
              AND q.first_is_correct IS NOT NULL
        """
        with audit.open_readonly(self.path) as guard:
            expected = guard.rows(original, (start.isoformat(" "), end.isoformat(" ")))
            actual = audit.load_data(guard, start, end, end)[0]
        self.assertEqual(len(actual), 4)
        self.assertEqual(
            sorted(map(tuple, actual), key=repr), sorted(map(tuple, expected), key=repr)
        )

    def test_full_audit_excludes_corrections_guidance_and_today_and_exports_no_ids(self):
        self.learning()
        self.learning(sense=70124, correct=1)
        self.learning(sense=70125, eligible=0)
        self.learning(sense=70126, remediation="related")
        self.learning(sense=70127, first=0)
        self.learning(student=90211, task=80125, sense=70128, correct=1)
        self.learning(sense=70129, at="2026-11-16 16:00:00")  # Shanghai today excluded.
        self.review()
        self.review(sense=70124, at="2026-11-11 12:00:10")
        self.review(sense=70123, correct=0, first=0, at="2026-11-11 12:00:20")
        self.insert(
            "vocabulary_review_session",
            student_id=90210,
            status="settled",
            settled_at="2026-11-11 12:00:30",
        )
        self.db.commit()
        with audit.open_readonly(self.path) as guard:
            result = audit.analyze(guard, datetime(2026, 11, 17, 4))
        metric = result["windows"]["28d"]["task_first_errors"]["all"]
        self.assertEqual(metric["tested_sense_task_pairs"], 3)
        self.assertEqual(metric["wrong_sense_task_pairs"], 1)
        self.assertEqual(result["windows"]["28d"]["daily_review_capacity"]["answers"]["total"], 2)
        self.assertEqual(result["quality"]["excluded_guidance_or_remediation_learning_rows"], 2)
        serialized = json.dumps(result)
        for secret in (
            "90210",
            "80123",
            "70123",
            "60123",
            "PRIVATE_NAME",
            "PRIVATE_ANSWER",
            "PRIVATE_ATTEMPT",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(result["safety"]["successful_changes"], 0)
        self.assertEqual(result["safety"]["denied_statements"], 0)

    def test_zero_review_days_are_in_learning_and_calendar_denominators(self):
        events = [
            event(1, 1, "2026-11-10 12:00:00", False, source="learning", task=1),
            event(1, 1, "2026-11-11 12:00:00", True),
            event(2, 2, "2026-11-10 12:00:00", True, source="learning", task=2),
        ]
        start = datetime(2026, 11, 10).date()
        output, students = audit.capacity(events, [], [], start, start + timedelta(days=7))
        self.assertEqual(students, {1, 2})
        self.assertEqual(output["vocabulary_learning_student_days"], 3)
        self.assertEqual(output["answers"]["on_vocabulary_learning_days"]["median"], 0)
        self.assertEqual(output["answers"]["on_all_calendar_days"]["n"], 14)
        self.assertEqual(output["answers"]["on_review_positive_days"]["n"], 1)

    def test_completed_flow_wins_over_cross_day_legacy_settlement(self):
        self.insert(
            "vocabulary_learning_flow",
            student_id=90210,
            task_id=80123,
            completed_at="2026-11-10 12:00:00",
        )
        self.insert(
            "vocabulary_task_settlement",
            student_id=90210,
            task_id=80123,
            settled_at="2026-11-11 12:00:00",
        )
        self.db.commit()
        with audit.open_readonly(self.path) as guard:
            result = audit.analyze(guard, datetime(2026, 11, 17, 4))
        capacity = result["windows"]["28d"]["daily_review_capacity"]
        self.assertEqual(capacity["vocabulary_learning_student_days"], 1)
        weekly = result["windows"]["28d"]["weekly_vocabulary_activity"]
        self.assertEqual(weekly["completed_tasks_per_student_week"]["max"], 1)

    def test_delayed_retest_is_first_on_later_day_and_reports_censoring(self):
        events = [
            event(1, 1, "2026-11-10 15:59:00", False),
            event(1, 1, "2026-11-10 15:59:30", True),  # same-day success not delayed
            event(1, 1, "2026-11-10 16:01:00", False),  # Shanghai next day
            event(1, 1, "2026-11-10 16:02:00", True),  # later same day not first
            event(2, 2, "2026-11-10 12:00:00", False),  # no return, stays denominator
            event(3, 3, "2026-11-16 12:00:00", False),
        ]  # immature day excluded
        result = audit.delayed_results(events, datetime(2026, 11, 17).date())["all"]
        one = result["first_later_day_gap_1"]
        self.assertEqual(one["eligible_error_days"], 3)
        self.assertEqual(one["observed_retests"], 1)
        self.assertEqual(one["correct"], 0)
        self.assertEqual(result["wrong_days_with_multiple_formal_exposures"], 2)

    def test_elapsed_proxy_uses_same_session_and_caps_long_pauses(self):
        events = [
            event(1, 1, "2026-11-10 12:00:00", True),
            event(1, 2, "2026-11-10 12:00:10", True),
            event(1, 3, "2026-11-10 12:05:00", True),
            event(1, 4, "2026-11-10 12:05:10", True, session=2),
        ]
        result = audit.elapsed_proxy(events)
        self.assertEqual(result["positive_adjacent_pairs"], 2)
        self.assertEqual(result["max_gap_120s"]["seconds"]["median"], 10)
        self.assertEqual(result["max_gap_120s"]["long_pauses_excluded"], 1)

    def test_backlog_counts_senses_once_but_preserves_dimension_mix(self):
        row = {"student_id": 1, "sense_id": 1}
        for index, dimension in enumerate(audit.DIMENSIONS):
            row.update(
                {
                    f"{dimension}_stage": (0, 0, 3, 6)[index],
                    f"{dimension}_next_due_at": "2026-11-10 12:00:00",
                    f"{dimension}_last_answered_at": None if index == 1 else "2026-11-09 12:00:00",
                }
            )
        output = audit.backlog_snapshot([row], datetime(2026, 11, 17), {1})["active_28d"]
        self.assertEqual(output["raw_due_dimension_count"], 4)
        self.assertEqual(output["raw_due_sense_count"], 1)
        self.assertEqual(
            output["sense_exclusive_priority_composition"], {"stage0_answered_marker": 1}
        )
        self.assertEqual(output["sense_overlapping_memberships"]["stage6_maintenance"], 1)


if __name__ == "__main__":
    unittest.main()
