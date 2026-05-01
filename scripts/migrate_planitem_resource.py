#!/usr/bin/env python3
"""Add PlanItem resource binding and Task bridge columns.

This is an idempotent hand-rolled migration for the current SQLite setup.
It only changes schema and does not backfill data.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app, db
from sqlalchemy import inspect, text


def _add_column(table: str, column: str, ddl: str) -> bool:
    inspector = inspect(db.engine)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        print(f"{table}.{column} already exists")
        return False
    with db.engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
    print(f"added {table}.{column}")
    return True


def _add_index(table: str, column: str, index_name: str) -> None:
    inspector = inspect(db.engine)
    indexes = {idx["name"] for idx in inspector.get_indexes(table)}
    if index_name in indexes:
        print(f"{index_name} already exists")
        return
    with db.engine.begin() as conn:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})"))
    print(f"added {index_name}")


def main() -> int:
    with app.app_context():
        inspector = inspect(db.engine)
        tables = set(inspector.get_table_names())
        if "plan_item" not in tables or "task" not in tables:
            print("plan_item/task table missing; run base table migration first")
            return 1

        _add_column("plan_item", "resource_type", "VARCHAR(32)")
        _add_column("plan_item", "resource_id", "VARCHAR(120)")
        _add_column("plan_item", "access_token", "VARCHAR(64)")
        _add_column("plan_item", "resource_metadata", "TEXT")
        _add_column("task", "plan_item_id", "INTEGER")

        _add_index("plan_item", "resource_type", "ix_plan_item_resource_type")
        _add_index("plan_item", "resource_id", "ix_plan_item_resource_id")
        _add_index("plan_item", "access_token", "ix_plan_item_access_token")
        _add_index("task", "plan_item_id", "ix_task_plan_item_id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
