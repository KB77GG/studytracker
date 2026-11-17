#!/usr/bin/env python3
"""Explicit, transactional checkpoint provenance migration; dry-run by default.

This script never imports app/config or reconstructs student learning history.
It preserves checkpoint IDs and existing allocation/event references. Run with
the policy globally OFF; db.create_all does not replace this migration.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.vocabulary_checkpoint_identity import checkpoint_selection_key  # noqa: E402

TABLE = "vocabulary_policy_checkpoint"
TEMP_TABLE = "vocabulary_policy_checkpoint__sources_migration"
OLD_COLUMNS = (
    "id",
    "student_id",
    "sense_id",
    "dimension",
    "cohort_key",
    "representative_word_id",
    "anchor_at",
    "interval_days",
    "due_local_date",
    "status",
    "created_at",
    "updated_at",
)
NEW_COLUMNS = ("source_kind", "source_key", "origin_event_id", "selection_key")
OLD_UNIQUE = ("student_id", "sense_id", "dimension", "cohort_key", "interval_days")
NEW_UNIQUE = (
    "student_id",
    "sense_id",
    "dimension",
    "cohort_key",
    "source_kind",
    "source_key",
    "interval_days",
)
INDEX_SQL = {
    "ix_vocab_checkpoint_select": "CREATE INDEX ix_vocab_checkpoint_select ON vocabulary_policy_checkpoint (student_id, cohort_key, status, due_local_date, selection_key, id)",
    "ix_vocab_error_paused": "CREATE INDEX ix_vocab_error_paused ON vocabulary_error_queue (student_id, cohort_key, status, pause_until_local_date, id)",
}
INDEX_COLUMNS = {
    "ix_vocab_checkpoint_select": (
        "student_id",
        "cohort_key",
        "status",
        "due_local_date",
        "selection_key",
        "id",
    ),
    "ix_vocab_error_paused": ("student_id", "cohort_key", "status", "pause_until_local_date", "id"),
}
CREATE_SQL = f"""CREATE TABLE {TEMP_TABLE} (
    id INTEGER NOT NULL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES user(id),
    sense_id INTEGER NOT NULL REFERENCES vocabulary_sense(id),
    dimension VARCHAR(32) NOT NULL,
    cohort_key VARCHAR(32) NOT NULL,
    representative_word_id INTEGER REFERENCES dictation_word(id),
    source_kind VARCHAR(24) NOT NULL DEFAULT 'first_correct',
    source_key VARCHAR(96) NOT NULL DEFAULT 'initial',
    origin_event_id INTEGER,
    selection_key VARCHAR(64) NOT NULL,
    anchor_at DATETIME NOT NULL,
    interval_days INTEGER NOT NULL,
    due_local_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    CONSTRAINT uq_vocab_checkpoint_cohort UNIQUE (student_id, sense_id, dimension, cohort_key, source_kind, source_key, interval_days),
    CONSTRAINT fk_vocab_checkpoint_origin FOREIGN KEY(origin_event_id) REFERENCES vocabulary_policy_event(id)
)"""


def inspect(connection):
    tables = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    required = {
        TABLE,
        "vocabulary_error_queue",
        "vocabulary_policy_allocation",
        "vocabulary_policy_event",
    }
    if not required.issubset(tables) or TEMP_TABLE in tables:
        raise ValueError("unsupported_checkpoint_schema")
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({TABLE})")}
    unique = [
        tuple(row[2] for row in connection.execute(f'PRAGMA index_info("{index[1]}")'))
        for index in connection.execute(f"PRAGMA index_list({TABLE})")
        if index[2]
    ]
    if columns == set(OLD_COLUMNS) and unique == [OLD_UNIQUE]:
        version = "legacy"
    elif columns == set(OLD_COLUMNS + NEW_COLUMNS) and unique == [NEW_UNIQUE]:
        version = "sources_v1"
    else:
        raise ValueError("unsupported_checkpoint_schema")
    indexes = {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    for name in set(INDEX_SQL) & indexes:
        actual = tuple(row[2] for row in connection.execute(f'PRAGMA index_info("{name}")'))
        if actual != INDEX_COLUMNS[name]:
            raise ValueError("unsupported_policy_index")
    return {
        "schema_version": version,
        "checkpoint_rows": connection.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0],
        "missing_indexes": sorted(set(INDEX_SQL) - indexes),
        "migration_required": version == "legacy" or not set(INDEX_SQL).issubset(indexes),
    }


def migrate_connection(connection, *, apply=False, fail_at=None):
    """Caller-owned connection; refuses active transactions, restores FK mode.

    fail_at is an in-process test hook, intentionally unavailable on the CLI.
    """
    if connection.in_transaction:
        raise ValueError("migration_requires_idle_connection")
    before = inspect(connection)
    if not apply or not before["migration_required"]:
        return {**before, "applied": False}
    foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
    connection.execute("PRAGMA foreign_keys=OFF")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 0:
        raise RuntimeError("cannot_disable_foreign_keys_outside_transaction")
    try:
        connection.execute("BEGIN IMMEDIATE")
        before = inspect(connection)  # Recheck after taking the SQLite writer.
        if before["schema_version"] == "legacy":
            dependent_sql = [
                row[0]
                for row in connection.execute(
                    "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name",
                    (TABLE,),
                )
            ]
            connection.execute(CREATE_SQL)
            connection.create_function(
                "checkpoint_key", 5, checkpoint_selection_key, deterministic=True
            )
            old_names = ", ".join(OLD_COLUMNS)
            connection.execute(
                f"INSERT INTO {TEMP_TABLE} ({old_names}, source_kind, source_key, origin_event_id, selection_key) "
                f"SELECT {old_names}, 'first_correct', 'initial', NULL, "
                f"checkpoint_key(student_id, cohort_key, sense_id, dimension, interval_days) FROM {TABLE}"
            )
            if fail_at == "after_copy":
                raise RuntimeError("injected_migration_failure")
            if (
                connection.execute(f"SELECT COUNT(*) FROM {TEMP_TABLE}").fetchone()[0]
                != before["checkpoint_rows"]
            ):
                raise RuntimeError("checkpoint_copy_count_mismatch")
            connection.execute(f"DROP TABLE {TABLE}")
            if fail_at == "after_drop":
                raise RuntimeError("injected_migration_failure")
            connection.execute(f"ALTER TABLE {TEMP_TABLE} RENAME TO {TABLE}")
            for sql in dependent_sql:
                connection.execute(sql)
        for name, sql in INDEX_SQL.items():
            if name in inspect(connection)["missing_indexes"]:
                connection.execute(sql)
        for table in (TABLE, "vocabulary_policy_allocation", "vocabulary_policy_event"):
            if connection.execute(f"PRAGMA foreign_key_check({table})").fetchone() is not None:
                raise RuntimeError("checkpoint_foreign_key_check_failed")
        after = inspect(connection)
        if after["schema_version"] != "sources_v1" or after["migration_required"]:
            raise RuntimeError("checkpoint_schema_verification_failed")
        if fail_at == "before_commit":
            raise RuntimeError("injected_migration_failure")
        connection.commit()
        return {**after, "applied": True, "preserved_checkpoint_rows": before["checkpoint_rows"]}
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.execute(f"PRAGMA foreign_keys={foreign_keys}")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != foreign_keys:
            raise RuntimeError("foreign_key_mode_not_restored")


def migrate(database, *, apply=False):
    path = Path(database).resolve(strict=True)
    if not path.is_file():
        raise ValueError("database_file_required")
    mode = "rw" if apply else "ro"
    connection = sqlite3.connect(
        "file:" + quote(str(path), safe="/") + "?mode=" + mode, uri=True, timeout=5
    )
    try:
        if not apply:
            connection.execute("PRAGMA query_only=ON")
        return migrate_connection(connection, apply=apply)
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = migrate(args.database, apply=args.apply)
    except Exception as error:
        print(json.dumps({"ok": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
