#!/usr/bin/env python3
"""Create only the three optional integrity tables. Standard library only.

Use an explicit local SQLite path. --dry-run does not open or create the DB.
Existing tables are never altered, and the script never imports the application.
"""

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

STATEMENTS = [
    "CREATE TABLE IF NOT EXISTS exam_integrity_policy (\n\tid INTEGER NOT NULL, \n\texam_kind VARCHAR(32) NOT NULL, \n\texam_ref VARCHAR(64) NOT NULL, \n\tmode VARCHAR(16) NOT NULL, \n\tmax_leaves INTEGER NOT NULL, \n\tmax_hidden_seconds INTEGER NOT NULL, \n\tupdated_by INTEGER, \n\tcreated_at DATETIME NOT NULL, \n\tupdated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_integrity_policy_exam UNIQUE (exam_kind, exam_ref)\n)",
    "CREATE TABLE IF NOT EXISTS exam_integrity_state (\n\tid INTEGER NOT NULL, \n\texam_kind VARCHAR(32) NOT NULL, \n\texam_ref VARCHAR(64) NOT NULL, \n\tsession_ref VARCHAR(64) NOT NULL, \n\tdevice_hash VARCHAR(64), \n\tacked_at DATETIME, \n\tlast_seen_at DATETIME, \n\tcurrent_section VARCHAR(20), \n\tcurrent_page_id VARCHAR(96), \n\thidden_at DATETIME, \n\thidden_page_id VARCHAR(96), \n\thidden_section VARCHAR(20), \n\thidden_client_ts FLOAT, \n\tlast_visible_client_ts FLOAT, \n\tdiscard_visible_page_id VARCHAR(96), \n\tleave_count INTEGER NOT NULL, \n\thidden_seconds FLOAT NOT NULL, \n\tblur_count INTEGER NOT NULL, \n\tcopy_attempt_count INTEGER NOT NULL, \n\tpaste_attempt_count INTEGER NOT NULL, \n\tcopy_blocked_count INTEGER NOT NULL, \n\tpaste_blocked_count INTEGER NOT NULL, \n\tdevice_conflict_count INTEGER NOT NULL, \n\tdevice_conflict_at DATETIME, \n\tis_locked BOOLEAN NOT NULL, \n\tlocked_reason VARCHAR(120), \n\tlocked_at DATETIME, \n\tlocked_section VARCHAR(20), \n\tunlock_count INTEGER NOT NULL, \n\tunlocked_at DATETIME, \n\tunlocked_by INTEGER, \n\tunlock_leave_count INTEGER NOT NULL, \n\tunlock_hidden_seconds FLOAT NOT NULL, \n\texempt BOOLEAN NOT NULL, \n\texempt_by INTEGER, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_integrity_state_session UNIQUE (exam_kind, session_ref)\n)",
    "CREATE INDEX IF NOT EXISTS ix_exam_integrity_state_exam_ref ON exam_integrity_state (exam_ref)",
    "CREATE TABLE IF NOT EXISTS exam_integrity_event (\n\tid INTEGER NOT NULL, \n\tstate_id INTEGER NOT NULL, \n\texam_kind VARCHAR(32) NOT NULL, \n\texam_ref VARCHAR(64) NOT NULL, \n\ttype VARCHAR(32) NOT NULL, \n\tsection VARCHAR(20), \n\tquestion_ref VARCHAR(64), \n\tduration_seconds FLOAT, \n\tdetail_json TEXT, \n\tclient_ts VARCHAR(64), \n\tcreated_at DATETIME NOT NULL, \n\tPRIMARY KEY (id)\n)",
    "CREATE INDEX IF NOT EXISTS ix_exam_integrity_event_exam_ref ON exam_integrity_event (exam_ref)",
    "CREATE INDEX IF NOT EXISTS ix_exam_integrity_event_state_id ON exam_integrity_event (state_id)",
]


def create_tables(database, dry_run=False):
    if dry_run:
        return list(STATEMENTS)
    path = Path(database).expanduser().resolve()
    if not path.is_file():
        raise ValueError("Database must already exist; refusing to create a wrong-path database")
    with closing(sqlite3.connect(str(path), timeout=5)) as conn, conn:
        for statement in STATEMENTS:
            conn.execute(statement)
    return list(STATEMENTS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    statements = create_tables(args.database, args.dry_run)
    if args.dry_run:
        print(";\n\n".join(statements) + ";")
    else:
        print("Integrity tables ready (existing exam tables unchanged).")


if __name__ == "__main__":
    main()
