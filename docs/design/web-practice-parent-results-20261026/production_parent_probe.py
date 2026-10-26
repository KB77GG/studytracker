"""Production parent-report GET probe; print only boolean/count diagnostics.

Run only after release-owner approval, from the deployed repository:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/probe.py --repo "$PWD" --database "$PWD/app.db"

No production config/secret, app.py, POST, migrations, or data writes are used.
The ephemeral JWT only works in this isolated Flask process. The sqlite creator
enforces mode=ro and query_only for every connection, including ORM connections.
Raw selected Task/attempt rows and their SHA-256 hashes remain in memory only.
"""

import argparse
import contextlib
import hashlib
import json
import logging
import os
import secrets
import sqlite3
import sys
import time
import warnings
from pathlib import Path

sys.dont_write_bytecode = True


def probe(repo, database, result):
    if not repo.is_dir() or not database.is_file():
        raise RuntimeError("invalid input")
    sys.path.insert(0, str(repo))
    import jwt
    from flask import Flask
    from sqlalchemy.pool import NullPool

    from api.miniprogram import mp_bp
    from models import db

    result["app_py_not_imported"] = "app" not in sys.modules
    if not result["app_py_not_imported"]:
        raise RuntimeError("unexpected app import")

    connections = []

    def readonly_connect():
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            connection.close()
            raise RuntimeError("read-only guard absent")
        connections.append(connection)
        return connection

    def select_one(connection, mode):
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT t.*, p.id AS probe_parent_id FROM task t "
            "JOIN parent_student_link l ON l.student_name=t.student_name AND l.is_active=1 "
            "JOIN user p ON p.id=l.parent_id AND p.role='parent' AND p.is_active=1 "
            "WHERE t.grading_mode=? AND t.cancelled_at IS NULL "
            "ORDER BY CASE WHEN t.status='done' THEN 0 ELSE 1 END, t.id DESC, p.id LIMIT 1",
            (mode,),
        ).fetchone()

    def snapshot(connection, selected):
        connection.row_factory = None
        digest = hashlib.sha256()
        for row in selected:
            task_id = row["id"]
            for table, clause, parameters in (
                ("task", "id=?", (task_id,)),
                ("question_type_practice_attempt", "task_id=?", (task_id,)),
            ):
                records = connection.execute(
                    f"SELECT * FROM {table} WHERE {clause} ORDER BY id", parameters,
                ).fetchall()
                digest.update(repr((table, records)).encode("utf-8"))
            current = connection.execute("SELECT question_ids FROM task WHERE id=?", (task_id,)).fetchone()
            payload = json.loads((current[0] if current else None) or "{}")
            ids = payload.get("writing_attempt_ids", []) if isinstance(payload, dict) else []
            ids = sorted({int(value) for value in ids if str(value).isdigit() and int(value) > 0})
            for attempt_id in ids:
                records = connection.execute(
                    "SELECT * FROM writing_typing_attempt WHERE id=?", (attempt_id,),
                ).fetchall()
                digest.update(repr(("writing_typing_attempt", records)).encode("utf-8"))
        return digest.digest()

    selected = []
    reader = readonly_connect()
    try:
        for mode in ("writing_practice", "question_type_practice"):
            row = select_one(reader, mode)
            result[mode] = {"selected_count": int(row is not None)}
            if row is not None:
                selected.append(dict(row))
        before = snapshot(reader, selected)
    finally:
        reader.close()

    app = Flask("production_parent_report_readonly_probe", static_folder=str(repo / "static"))
    ephemeral_secret = secrets.token_hex(32)
    app.config.update(
        SECRET_KEY=ephemeral_secret,
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"creator": readonly_connect, "poolclass": NullPool},
    )
    db.init_app(app)
    app.register_blueprint(mp_bp)

    def headers(user_id):
        token = jwt.encode(
            {"sub": str(user_id), "exp": int(time.time()) + 120},
            ephemeral_secret,
            algorithm="HS256",
        )
        return {"Authorization": "Bearer " + token}

    with app.app_context():
        try:
            client = app.test_client()
            for row in selected:
                checks = result[row["grading_mode"]]
                response = client.get(
                    f"/api/miniprogram/parent/tasks/{row['id']}",
                    headers=headers(row["probe_parent_id"]),
                )
                body = response.get_json(silent=True) or {}
                detail = body.get("detail") or {}
                expected = "question_type_practice"
                if row["grading_mode"] == "writing_practice":
                    payload = json.loads(row["question_ids"] or "{}")
                    expected = "writing_mother_topic" if payload.get("writing_resource_type") == "mother_topic" else "writing_typing"
                checks["response_200"] = response.status_code == 200
                checks["ok"] = body.get("ok") is True
                checks["kind_ok"] = detail.get("kind") == expected
                checks["summary_ok"] = isinstance(detail.get("summary"), dict) and isinstance(detail.get("summary_text"), str)
                raw_response = json.dumps(body)
                checks["no_writable_token"] = all(
                    key not in raw_response for key in ("access_token", "token=", "web_practice")
                ) and all(
                    not row.get(key) or str(row[key]) not in raw_response
                    for key in ("listening_access_token", "reading_access_token")
                )
                other_reader = readonly_connect()
                try:
                    other = other_reader.execute(
                        "SELECT p.id FROM user p WHERE p.role='parent' AND p.is_active=1 AND p.id<>? "
                        "AND NOT EXISTS (SELECT 1 FROM parent_student_link l WHERE l.parent_id=p.id "
                        "AND l.student_name=? AND l.is_active=1) ORDER BY p.id LIMIT 1",
                        (row["probe_parent_id"], row["student_name"]),
                    ).fetchone()
                finally:
                    other_reader.close()
                checks["unbound_parent_checked"] = other is not None
                if other is not None:
                    denied = client.get(f"/api/miniprogram/parent/tasks/{row['id']}", headers=headers(other[0]))
                    denied_body = denied.get_json(silent=True) or {}
                    checks["unbound_parent_403"] = denied.status_code == 403 and denied_body.get("error") == "student_not_bound"
        finally:
            db.session.remove()
            db.engine.dispose()

    after_reader = readonly_connect()
    try:
        result["selected_rows_unchanged"] = before == snapshot(after_reader, selected)
    finally:
        after_reader.close()
    result["read_only_connection_count"] = len(connections)
    result["selected_task_count"] = len(selected)
    result["student_get_count"] = 0
    result["post_count"] = 0
    result["all_checked_passed"] = result["app_py_not_imported"] and result["selected_rows_unchanged"] and all(
        all(value for key, value in result[row["grading_mode"]].items() if key != "unbound_parent_checked")
        for row in selected
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    result = {"probe_completed": False}
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    # Do not let imported libraries or exception details print private data.
    with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        try:
            probe(args.repo.resolve(), args.database.resolve(), result)
            result["probe_completed"] = True
        except Exception:
            result["all_checked_passed"] = False
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("probe_completed") and result.get("all_checked_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
