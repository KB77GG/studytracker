"""File-backed migration safety, including nonempty referenced checkpoints."""

import importlib.util
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sqlalchemy import create_engine

from models import VocabularyPolicyCheckpoint, VocabularyPolicyEvent, db
from services.vocabulary_checkpoint_identity import checkpoint_selection_key
from tests import test_vocabulary_error_queue as fixtures

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "checkpoint_migration", ROOT / "scripts/migrate_vocabulary_checkpoint_sources.py"
)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)

LEGACY_DDL = """CREATE TABLE vocabulary_policy_checkpoint (
id INTEGER NOT NULL PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES user(id),
sense_id INTEGER NOT NULL REFERENCES vocabulary_sense(id), dimension VARCHAR(32) NOT NULL,
cohort_key VARCHAR(32) NOT NULL, representative_word_id INTEGER REFERENCES dictation_word(id),
anchor_at DATETIME NOT NULL, interval_days INTEGER NOT NULL, due_local_date DATE NOT NULL,
status VARCHAR(16) NOT NULL, created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL,
CONSTRAINT uq_vocab_checkpoint_cohort UNIQUE(student_id,sense_id,dimension,cohort_key,interval_days))"""


class CheckpointMigrationTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="checkpoint-migration-")
        self.path = Path(self.folder.name) / "fixture.sqlite"
        self.database_uri = "sqlite:///" + str(self.path)
        fixtures.VocabularyErrorPolicyCoreTest.setUp(self)
        student_id, sense_id, word_id = self.user.id, self.words[0].sense_id, self.words[0].id
        book_id = self.book.id
        db.session.remove()
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("DROP TABLE vocabulary_policy_checkpoint")
            connection.execute(LEGACY_DDL)
            connection.execute(
                "CREATE INDEX ix_vocab_checkpoint_due ON vocabulary_policy_checkpoint(student_id,cohort_key,status,due_local_date)"
            )
            connection.execute(
                "CREATE INDEX ix_vocabulary_policy_checkpoint_created_at ON vocabulary_policy_checkpoint(created_at)"
            )
            connection.execute(
                "CREATE INDEX ix_vocabulary_policy_checkpoint_updated_at ON vocabulary_policy_checkpoint(updated_at)"
            )
            connection.execute("DROP INDEX ix_vocab_error_paused")
            for row_id, interval, status in ((101, 7, "answered"), (102, 30, "pending")):
                connection.execute(
                    "INSERT INTO vocabulary_policy_checkpoint VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        row_id,
                        student_id,
                        sense_id,
                        "meaning_recall",
                        "synthetic-cohort",
                        word_id,
                        "2026-11-01 00:00:00",
                        interval,
                        "2026-12-01",
                        status,
                        "2026-11-01 00:00:00",
                        "2026-11-01 00:00:00",
                    ),
                )
            # Preserve genuine foreign-key references on both dependent tables.
            connection.execute(
                "INSERT INTO vocabulary_review_session(id,student_id,review_date,status,session_token,queue_token,batch_limit,started_at,created_at,updated_at) VALUES(201,?,'2026-11-01','settled','synthetic','synthetic',20,'2026-11-01','2026-11-01','2026-11-01')",
                (student_id,),
            )
            connection.execute(
                "INSERT INTO vocabulary_review_item(id,session_id,student_id,book_id,word_id,sense_id,dimension,due_at,stage_at_claim,queue_index,question_id,question_snapshot_json,answer_payload_json,created_at,updated_at,first_response_kind,correction_count,correction_exhausted,deferred_to_review,state_applied) VALUES(301,201,?,?,?,?, 'meaning_recall','2026-11-01',0,0,'synthetic','{}','{}','2026-11-01','2026-11-01','answer',0,0,0,0)",
                (student_id, book_id, word_id, sense_id),
            )
            connection.execute(
                "INSERT INTO vocabulary_policy_allocation(id,student_id,local_date,mode,ordinal,kind,checkpoint_id,session_id,item_id,sense_id,dimension,status,created_at,updated_at) VALUES(401,?,'2026-11-01','mandatory',1,'sample',101,201,301,?,'meaning_recall','answered','2026-11-01','2026-11-01')",
                (student_id, sense_id),
            )
            connection.execute(
                "INSERT INTO vocabulary_policy_event(id,student_id,source_key,checkpoint_id,allocation_id,sense_id,dimension,kind,source,occurred_at,local_date,is_correct,created_at,updated_at) VALUES(501,?,'synthetic-sample',101,401,?,'meaning_recall','answer','review','2026-11-01','2026-11-01',1,'2026-11-01','2026-11-01')",
                (student_id, sense_id),
            )
            connection.commit()

    def tearDown(self):
        fixtures.VocabularyErrorPolicyCoreTest.tearDown(self)
        self.folder.cleanup()

    def snapshot(self, connection):
        schema = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
        ).fetchall()
        tables = [row[1] for row in schema if row[0] == "table"]
        data = {
            name: connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall()
            for name in tables
        }
        return schema, data

    def test_default_dry_run_is_read_only_and_missing_file_not_created(self):
        before = self.path.read_bytes()
        result = migration.migrate(self.path)
        self.assertFalse(result["applied"])
        self.assertEqual(result["checkpoint_rows"], 2)
        self.assertEqual(self.path.read_bytes(), before)
        missing = self.path.with_name("missing.sqlite")
        with self.assertRaises(FileNotFoundError):
            migration.migrate(missing)
        self.assertFalse(missing.exists())

    def test_nonempty_rebuild_preserves_ids_references_and_all_other_tables(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            schema_before, rows_before = self.snapshot(connection)
            result = migration.migrate_connection(connection, apply=True)
            self.assertTrue(result["applied"])
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            schema_after, rows_after = self.snapshot(connection)

            def old_filter(row):
                return row[2] != migration.TABLE and row[1] != "ix_vocab_error_paused"

            self.assertEqual(
                list(filter(old_filter, schema_before)), list(filter(old_filter, schema_after))
            )
            for table, rows in rows_before.items():
                if table != migration.TABLE:
                    self.assertEqual(rows_after[table], rows, table)
            names = ",".join(migration.OLD_COLUMNS)
            preserved = connection.execute(
                f"SELECT {names} FROM {migration.TABLE} ORDER BY id"
            ).fetchall()
            self.assertEqual(preserved, rows_before[migration.TABLE])
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            added = connection.execute(
                "SELECT student_id,cohort_key,sense_id,dimension,interval_days,source_kind,source_key,origin_event_id,selection_key FROM vocabulary_policy_checkpoint ORDER BY id"
            ).fetchall()
            for row in added:
                self.assertEqual(row[5:8], ("first_correct", "initial", None))
                self.assertEqual(row[8], checkpoint_selection_key(*row[:5]))
            after_first = self.snapshot(connection)
            second = migration.migrate_connection(connection, apply=True)
            self.assertFalse(second["applied"])
            self.assertEqual(self.snapshot(connection), after_first)

    def test_injected_failure_rolls_back_ddl_rows_and_restores_foreign_keys(self):
        for stage in ("after_copy", "after_drop", "before_commit"):
            for foreign_keys in (0, 1):
                with (
                    self.subTest(stage=stage, foreign_keys=foreign_keys),
                    closing(sqlite3.connect(self.path)) as connection,
                ):
                    connection.execute(f"PRAGMA foreign_keys={foreign_keys}")
                    before = self.snapshot(connection)
                    with self.assertRaisesRegex(RuntimeError, "injected_migration_failure"):
                        migration.migrate_connection(connection, apply=True, fail_at=stage)
                    self.assertEqual(
                        connection.execute("PRAGMA foreign_keys").fetchone()[0], foreign_keys
                    )
                    self.assertFalse(connection.in_transaction)
                    self.assertEqual(self.snapshot(connection), before)

    def test_migration_refuses_partial_schema_and_active_transaction(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("BEGIN")
            with self.assertRaisesRegex(ValueError, "idle_connection"):
                migration.migrate_connection(connection, apply=True)
            connection.rollback()
            connection.execute(
                "ALTER TABLE vocabulary_policy_checkpoint ADD COLUMN source_kind VARCHAR(24)"
            )
            with self.assertRaisesRegex(ValueError, "unsupported_checkpoint_schema"):
                migration.migrate_connection(connection, apply=True)

    def test_cli_defaults_to_read_only_and_errors_do_not_print_database_path(self):
        before = self.path.read_bytes()
        command = [
            sys.executable,
            str(ROOT / "scripts/migrate_vocabulary_checkpoint_sources.py"),
            "--database",
        ]
        result = subprocess.run(
            command + [str(self.path)], text=True, capture_output=True, check=True
        )
        self.assertIn('"applied": false', result.stdout)
        self.assertNotIn(str(self.path), result.stdout + result.stderr)
        self.assertEqual(self.path.read_bytes(), before)
        missing = self.path.with_name("private-database-name.sqlite")
        failed = subprocess.run(command + [str(missing)], text=True, capture_output=True)
        self.assertEqual(failed.returncode, 1)
        self.assertNotIn("private-database-name", failed.stdout + failed.stderr)
        self.assertFalse(missing.exists())

    def test_named_index_with_wrong_shape_is_rejected(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "CREATE INDEX ix_vocab_error_paused ON vocabulary_error_queue(student_id)"
            )
            with self.assertRaisesRegex(ValueError, "unsupported_policy_index"):
                migration.migrate_connection(connection, apply=True)

    def test_empty_existing_policy_tables_migrate_without_creating_students(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("DELETE FROM vocabulary_policy_event")
            connection.execute("DELETE FROM vocabulary_policy_allocation")
            connection.execute("DELETE FROM vocabulary_policy_checkpoint")
            connection.commit()
            before = connection.execute('SELECT * FROM "user" ORDER BY id').fetchall()
            result = migration.migrate_connection(connection, apply=True)
            self.assertEqual(result["checkpoint_rows"], 0)
            self.assertEqual(
                connection.execute('SELECT * FROM "user" ORDER BY id').fetchall(), before
            )

    def test_migrated_table_matches_new_model_and_allows_repeated_d7_sources(self):
        migration.migrate(self.path, apply=True)
        expected_engine = create_engine("sqlite://")
        try:
            db.metadata.create_all(expected_engine)
            with (
                expected_engine.connect() as expected,
                closing(sqlite3.connect(self.path)) as actual,
            ):
                expected_columns = [
                    tuple(row[1:])
                    for row in expected.exec_driver_sql(
                        "PRAGMA table_info(vocabulary_policy_checkpoint)"
                    )
                ]
                actual_columns = [
                    tuple(row[1:])
                    for row in actual.execute("PRAGMA table_info(vocabulary_policy_checkpoint)")
                ]
                self.assertEqual(actual_columns, expected_columns)
                expected_fks = sorted(
                    tuple(row[2:])
                    for row in expected.exec_driver_sql(
                        "PRAGMA foreign_key_list(vocabulary_policy_checkpoint)"
                    )
                )
                actual_fks = sorted(
                    tuple(row[2:])
                    for row in actual.execute(
                        "PRAGMA foreign_key_list(vocabulary_policy_checkpoint)"
                    )
                )
                self.assertEqual(actual_fks, expected_fks)
        finally:
            expected_engine.dispose()
        db.session.remove()
        prior = db.session.get(VocabularyPolicyCheckpoint, 101)
        for index in (1, 2):
            event = VocabularyPolicyEvent(
                student_id=prior.student_id,
                source_key=f"closed:{index}",
                kind="closed",
                source="system",
                occurred_at=self.now,
                local_date=self.now.date(),
                sense_id=prior.sense_id,
                dimension=prior.dimension,
                detail_code="two_delayed_successes",
            )
            db.session.add(event)
            db.session.flush()
            db.session.add(
                VocabularyPolicyCheckpoint(
                    student_id=prior.student_id,
                    sense_id=prior.sense_id,
                    dimension=prior.dimension,
                    cohort_key=prior.cohort_key,
                    representative_word_id=prior.representative_word_id,
                    source_kind="graduation",
                    source_key=f"graduation:{event.id}",
                    origin_event_id=event.id,
                    anchor_at=self.now,
                    interval_days=7,
                    due_local_date=self.now.date(),
                    status="pending",
                )
            )
        db.session.commit()
        self.assertEqual(VocabularyPolicyCheckpoint.query.count(), 4)
        self.assertEqual(
            VocabularyPolicyCheckpoint.query.filter_by(source_kind="graduation").count(), 2
        )


if __name__ == "__main__":
    unittest.main()
