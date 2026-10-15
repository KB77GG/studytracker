#!/usr/bin/env python3
"""Add explicit vocabulary answer kinds to an existing SQLite database.

Run this additive migration before deploying a server that reads the new
columns. An explicit database path is required; importing the application is
intentionally unnecessary. It never changes historical scores or answers.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


COLUMNS = {
    "dictation_record": ("response_kind",),
    "vocabulary_learning_question": (
        "first_response_kind",
        "retry_response_kind",
    ),
    "vocabulary_review_item": ("first_response_kind",),
    "vocabulary_review_attempt": ("response_kind",),
}


def migrate(database: Path) -> list[str]:
    """Add missing columns and normalize historical nulls; safe to repeat."""
    if not database.is_file():
        raise ValueError(f"database does not exist: {database}")

    changed = []
    with sqlite3.connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for table, names in COLUMNS.items():
            if not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                raise ValueError(f"required table is missing: {table}")
            existing = {
                row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            for name in names:
                if name not in existing:
                    connection.execute(
                        f'ALTER TABLE "{table}" ADD COLUMN "{name}" '
                        "VARCHAR(16) NOT NULL DEFAULT 'answer'"
                    )
                    changed.append(f"{table}.{name}")
                else:
                    # Also handles a partially applied migration that left a
                    # nullable column without a default.
                    connection.execute(
                        f'UPDATE "{table}" SET "{name}" = ? WHERE "{name}" IS NULL',
                        ("answer",),
                    )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    try:
        changed = migrate(args.database)
    except (ValueError, sqlite3.DatabaseError) as exc:
        parser.exit(1, f"migration failed: {exc}\n")
    print("added: " + (", ".join(changed) if changed else "none (already current)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
