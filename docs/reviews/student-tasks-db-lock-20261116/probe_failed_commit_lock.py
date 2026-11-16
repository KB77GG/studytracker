"""Synthetic-only: what happens to a pooled SQLite connection after COMMIT fails?

No project code is imported; this isolates SQLAlchemy + pysqlite behaviour on a
throwaway database file.  In rollback-journal mode a COMMIT must wait for every
reader to finish; if a reader outlives the busy timeout the COMMIT raises
"database is locked" while SQLite keeps the transaction (and its PENDING lock)
open.  The question is whether the usual clean-up paths release that lock.

Usage: python -B probe_failed_commit_lock.py [--output file.json]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

import sqlalchemy
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

TIMEOUT = 0.5  # production uses pysqlite's default 5 s; only the wait is shortened


def _try(path: Path, write: bool) -> str:
    raw = sqlite3.connect(path, timeout=TIMEOUT, isolation_level=None)
    try:
        if write:
            raw.execute("BEGIN IMMEDIATE")
            raw.execute("ROLLBACK")
        else:
            raw.execute("SELECT count(*) FROM t").fetchone()
        return "ok"
    except sqlite3.OperationalError as error:
        return str(error)
    finally:
        raw.close()


def run(journal_mode: str, cleanup: str, reset_guard: bool) -> dict:
    path = Path(tempfile.mkdtemp(prefix="studytracker-commit-probe-")) / "synthetic.db"
    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA journal_mode={journal_mode}")
    raw.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    raw.executemany("INSERT INTO t (v) VALUES (?)", [("original",)] * 500)
    raw.commit()
    raw.close()

    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": TIMEOUT})
    if reset_guard:
        @event.listens_for(engine, "reset")
        def _rollback_leftover_transaction(dbapi_connection, _record, _state):
            if dbapi_connection.in_transaction:
                dbapi_connection.rollback()

    session = sessionmaker(engine)()
    out = {"journal_mode": journal_mode, "cleanup": cleanup, "reset_guard": reset_guard}

    # A reader that is still fetching a large result keeps its SHARED lock.
    reader = sqlite3.connect(path, timeout=TIMEOUT)
    cursor = reader.execute("SELECT * FROM t")
    cursor.fetchone()

    session.execute(text("UPDATE t SET v='from_failed_request' WHERE id=1"))
    try:
        session.commit()
        out["commit"] = "ok"
    except Exception as error:
        out["commit"] = str(getattr(error, "orig", error))
        if cleanup == "rollback_then_close":
            session.rollback()
    session.close()  # Flask-SQLAlchemy teardown: scoped_session.remove()
    cursor.close()
    reader.close()   # the slow reader is gone now

    out["connections_checked_out"] = engine.pool.checkedout()
    out["later_read_on_other_connection"] = _try(path, write=False)
    out["later_write_on_other_connection"] = _try(path, write=True)

    with engine.connect() as connection:  # the next request gets the pooled connection
        out["reused_connection_still_in_transaction"] = connection.connection.dbapi_connection.in_transaction
        out["value_visible_to_next_request"] = connection.execute(text("SELECT v FROM t WHERE id=1")).scalar()
    out["read_after_connection_was_reused"] = _try(path, write=False)
    engine.dispose()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    report = {
        "synthetic_only": True,
        "sqlalchemy": sqlalchemy.__version__,
        "sqlite": sqlite3.sqlite_version,
        "busy_timeout_s": TIMEOUT,
        "cases": [
            run(mode, cleanup, guard)
            for mode in ("delete", "wal")
            for cleanup in ("close_only", "rollback_then_close")
            for guard in (False, True)
        ],
    }
    text_out = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text_out + "\n", encoding="utf-8")
    print(text_out)


if __name__ == "__main__":
    main()
