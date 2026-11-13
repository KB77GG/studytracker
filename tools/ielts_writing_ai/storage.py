"""SQLite storage for the trial tool (stdlib only, its own database file).

Each call opens its own short-lived connection, so background job threads and
request threads never share a connection object.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import FORBIDDEN_DB_NAMES, ConfigError

SCHEMA_VERSION = 1
OWN_TABLES = {"iwa_meta", "trial_user", "submission", "generation", "usage_event"}
KINDS = ("evaluate", "refine", "rewrite")
ACTIVE_STATUSES = ("queued", "running")
SHANGHAI = timezone(timedelta(hours=8))
# timezone.utc rather than datetime.UTC: the tool must also run on Python 3.10.
UTC = timezone.utc  # noqa: UP017

SCHEMA = """
CREATE TABLE IF NOT EXISTS iwa_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trial_user (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    code_hash TEXT NOT NULL UNIQUE,
    code_hint TEXT NOT NULL,
    session_epoch INTEGER NOT NULL DEFAULT 1,
    daily_limit INTEGER,
    expires_at TEXT,
    disabled_at TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS submission (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES trial_user(id),
    task_type TEXT NOT NULL CHECK (task_type IN ('task1', 'task2')),
    prompt_text TEXT NOT NULL,
    essay_text TEXT NOT NULL,
    essay_sha256 TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    target_band REAL NOT NULL,
    image_path TEXT,
    image_mime TEXT,
    image_status TEXT NOT NULL DEFAULT 'none'
        CHECK (image_status IN ('none', 'pending', 'ready', 'failed', 'skipped')),
    image_description TEXT,
    image_error TEXT,
    image_check TEXT,
    copied_spans TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_submission_user ON submission(user_id, id);
CREATE TABLE IF NOT EXISTS generation (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submission(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('evaluate', 'refine', 'rewrite')),
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'ready', 'failed')),
    provider TEXT,
    model TEXT,
    prompt_version TEXT,
    result_json TEXT,
    error_code TEXT,
    error_message TEXT,
    latency_ms INTEGER,
    usage_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_generation_submission ON generation(submission_id, kind, id);
CREATE TABLE IF NOT EXISTS usage_event (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES trial_user(id),
    day TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_usage_user_day ON usage_event(user_id, day);
"""


ADDED_SUBMISSION_COLUMNS = ("copied_spans", "image_check")


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def shanghai_day(now: datetime | None = None) -> str:
    return (now or utcnow()).astimezone(SHANGHAI).strftime("%Y-%m-%d")


class Storage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        if self.db_path.name.lower() in FORBIDDEN_DB_NAMES:
            raise ConfigError(f"拒绝使用主应用数据库文件名：{self.db_path.name}")

    # -- connection & schema -------------------------------------------------

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Create tables, refusing any database that is not the tool's own."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            existing = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            foreign = existing - OWN_TABLES
            if foreign:
                raise ConfigError(
                    "该数据库包含非试用工具的表（例如 "
                    + ", ".join(sorted(foreign)[:3])
                    + "），拒绝使用。请为试用工具指定独立的数据库文件。"
                )
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
            # Columns added after the first release (nullable; existing rows unchanged):
            # confirmed copying (2026-11-13) and the person's check of a chart reading.
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(submission)")}
            for column in ADDED_SUBMISSION_COLUMNS:
                if column not in columns:
                    conn.execute(f"ALTER TABLE submission ADD COLUMN {column} TEXT")
            conn.execute(
                "INSERT OR IGNORE INTO iwa_meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    # -- trial users ---------------------------------------------------------

    def create_user(
        self,
        *,
        name: str,
        code_hash: str,
        code_hint: str,
        daily_limit: int | None = None,
        expires_at: datetime | None = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO trial_user(name, code_hash, code_hint, daily_limit, expires_at, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, code_hash, code_hint, daily_limit, iso(expires_at), iso(utcnow())),
            )
            return int(cur.lastrowid)

    def get_user(self, user_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM trial_user WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_code_hash(self, code_hash: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM trial_user WHERE code_hash = ?", (code_hash,)
            ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT u.*, (SELECT COUNT(*) FROM submission s WHERE s.user_id = u.id) AS submissions"
                " FROM trial_user u ORDER BY u.id"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_user(self, user_id: int, **fields) -> bool:
        allowed = {
            "name",
            "code_hash",
            "code_hint",
            "daily_limit",
            "expires_at",
            "disabled_at",
            "last_login_at",
        }
        sets = {k: v for k, v in fields.items() if k in allowed}
        bump_epoch = bool(fields.get("bump_epoch"))
        if not sets and not bump_epoch:
            return False
        clauses = [f"{key} = ?" for key in sets]
        if bump_epoch:
            clauses.append("session_epoch = session_epoch + 1")
        with self.connect() as conn:
            cur = conn.execute(
                f"UPDATE trial_user SET {', '.join(clauses)} WHERE id = ?",
                (*sets.values(), user_id),
            )
            return cur.rowcount == 1

    # -- quota ---------------------------------------------------------------

    def usage_today(self, user_id: int, now: datetime | None = None) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM usage_event WHERE user_id = ? AND day = ?",
                (user_id, shanghai_day(now)),
            ).fetchone()
        return int(row["n"])

    # -- submissions ---------------------------------------------------------

    def create_submission(
        self,
        *,
        public_id: str,
        user_id: int,
        task_type: str,
        prompt_text: str,
        essay_text: str,
        essay_sha256: str,
        word_count: int,
        target_band: float,
        image_path: str | None,
        image_mime: str | None,
        image_status: str,
        daily_limit: int,
        copied_spans: str | None = None,
    ) -> dict | None:
        """Create a submission with one queued generation per kind.

        Quota is checked and consumed inside the same write transaction, so two
        concurrent submissions cannot both slip under the daily limit.
        Returns None when the quota would be exceeded.
        """
        now = utcnow()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            used = conn.execute(
                "SELECT COUNT(*) AS n FROM usage_event WHERE user_id = ? AND day = ?",
                (user_id, shanghai_day(now)),
            ).fetchone()["n"]
            if used + len(KINDS) > daily_limit:
                return None
            cur = conn.execute(
                "INSERT INTO submission(public_id, user_id, task_type, prompt_text, essay_text,"
                " essay_sha256, word_count, target_band, image_path, image_mime, image_status,"
                " copied_spans, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    public_id,
                    user_id,
                    task_type,
                    prompt_text,
                    essay_text,
                    essay_sha256,
                    word_count,
                    target_band,
                    image_path,
                    image_mime,
                    image_status,
                    copied_spans,
                    iso(now),
                ),
            )
            submission_id = int(cur.lastrowid)
            generation_ids = {}
            for kind in KINDS:
                gen = conn.execute(
                    "INSERT INTO generation(submission_id, kind, status, created_at)"
                    " VALUES (?, ?, 'queued', ?)",
                    (submission_id, kind, iso(now)),
                )
                generation_ids[kind] = int(gen.lastrowid)
                conn.execute(
                    "INSERT INTO usage_event(user_id, day, kind, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, shanghai_day(now), kind, iso(now)),
                )
        return {"id": submission_id, "public_id": public_id, "generation_ids": generation_ids}

    def get_submission(self, submission_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM submission WHERE id = ?", (submission_id,)).fetchone()
        return dict(row) if row else None

    def get_owned_submission(self, public_id: str, user_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM submission WHERE public_id = ? AND user_id = ?",
                (public_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def list_submissions(self, user_id: int, *, limit: int = 30, before_id: int | None = None):
        params: list = [user_id]
        where = "s.user_id = ?"
        if before_id:
            where += " AND s.id < ?"
            params.append(before_id)
        params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT s.id, s.public_id, s.task_type, s.prompt_text, s.word_count,"
                " s.target_band, s.image_path IS NOT NULL AS has_image, s.created_at"
                f" FROM submission s WHERE {where} ORDER BY s.id DESC LIMIT ?",
                params,
            ).fetchall()
            items = [dict(row) for row in rows]
            for item in items:
                item["generations"] = self._latest_generations(conn, item["id"])
        return items

    def delete_submission(self, submission_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM submission WHERE id = ?", (submission_id,))

    def set_image_check(
        self, submission_id: int, check: dict, *, description: str | None = None
    ) -> bool:
        """Record, once, that a person confirmed (optionally correcting the text) or
        skipped checking a structurally usable chart reading. False if the reading is
        not ready or was already checked."""
        with self.connect() as conn:
            cur = conn.execute(
                "UPDATE submission SET image_check = ?,"
                " image_description = COALESCE(?, image_description)"
                " WHERE id = ? AND image_status = 'ready' AND image_check IS NULL",
                (json.dumps(check, ensure_ascii=False), description, submission_id),
            )
            return cur.rowcount == 1

    def queued_generation_ids(self, submission_id: int) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id FROM generation WHERE submission_id = ? AND status = 'queued'"
                " ORDER BY id",
                (submission_id,),
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def set_image_result(
        self, submission_id: int, *, status: str, description: str | None, error: str | None
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE submission SET image_status = ?, image_description = ?, image_error = ?"
                " WHERE id = ?",
                (status, description, error, submission_id),
            )

    # -- generations ---------------------------------------------------------

    @staticmethod
    def _latest_generations(conn, submission_id: int) -> dict:
        rows = conn.execute(
            "SELECT g.* FROM generation g JOIN ("
            "  SELECT kind, MAX(id) AS max_id FROM generation WHERE submission_id = ? GROUP BY kind"
            ") latest ON latest.max_id = g.id",
            (submission_id,),
        ).fetchall()
        result = {}
        for row in rows:
            item = dict(row)
            item["result"] = (
                json.loads(item.pop("result_json")) if item.get("result_json") else None
            )
            item["usage"] = json.loads(item.pop("usage_json")) if item.get("usage_json") else None
            result[item["kind"]] = item
        return result

    def latest_generations(self, submission_id: int) -> dict:
        with self.connect() as conn:
            return self._latest_generations(conn, submission_id)

    def get_generation(self, generation_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM generation WHERE id = ?", (generation_id,)).fetchone()
        return dict(row) if row else None

    def queue_regeneration(
        self, submission_id: int, kind: str, user_id: int, daily_limit: int
    ) -> tuple[int | None, str | None]:
        """Queue a new attempt for one kind; returns (generation_id, error_code)."""
        now = utcnow()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute(
                "SELECT 1 FROM generation WHERE submission_id = ? AND kind = ?"
                " AND status IN ('queued', 'running') LIMIT 1",
                (submission_id, kind),
            ).fetchone()
            if active:
                return None, "already_running"
            used = conn.execute(
                "SELECT COUNT(*) AS n FROM usage_event WHERE user_id = ? AND day = ?",
                (user_id, shanghai_day(now)),
            ).fetchone()["n"]
            if used + 1 > daily_limit:
                return None, "quota_exceeded"
            cur = conn.execute(
                "INSERT INTO generation(submission_id, kind, status, created_at)"
                " VALUES (?, ?, 'queued', ?)",
                (submission_id, kind, iso(now)),
            )
            conn.execute(
                "INSERT INTO usage_event(user_id, day, kind, created_at) VALUES (?, ?, ?, ?)",
                (user_id, shanghai_day(now), kind, iso(now)),
            )
            return int(cur.lastrowid), None

    def claim_generation(
        self, generation_id: int, *, provider: str, model: str, prompt_version: str
    ):
        """Atomically move queued -> running; returns False if someone else owns it."""
        with self.connect() as conn:
            cur = conn.execute(
                "UPDATE generation SET status = 'running', started_at = ?, provider = ?, model = ?,"
                " prompt_version = ? WHERE id = ? AND status = 'queued'",
                (iso(utcnow()), provider, model, prompt_version, generation_id),
            )
            return cur.rowcount == 1

    def finish_generation(
        self,
        generation_id: int,
        *,
        result: dict | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        latency_ms: int | None = None,
        usage: dict | None = None,
        model: str | None = None,
    ) -> None:
        status = "ready" if result is not None and not error_code else "failed"
        with self.connect() as conn:
            conn.execute(
                "UPDATE generation SET status = ?, result_json = ?, error_code = ?,"
                " error_message = ?, latency_ms = ?, usage_json = ?, finished_at = ?,"
                " model = COALESCE(?, model) WHERE id = ? AND status = 'running'",
                (
                    status,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    error_code,
                    (error_message or "")[:500] or None,
                    latency_ms,
                    json.dumps(usage, ensure_ascii=False) if usage else None,
                    iso(utcnow()),
                    model,
                    generation_id,
                ),
            )

    def fail_interrupted(self) -> int:
        """Mark work left over from a previous process as failed (call at startup).
        Generations waiting for a person to check a chart reading were never started
        and keep waiting."""
        now = iso(utcnow())
        with self.connect() as conn:
            cur = conn.execute(
                "UPDATE generation SET status = 'failed', error_code = 'interrupted',"
                " error_message = '服务重启导致生成中断，请重新生成', finished_at = ?"
                " WHERE status IN ('queued', 'running') AND NOT (status = 'queued' AND"
                " submission_id IN (SELECT id FROM submission WHERE image_status = 'ready'"
                " AND image_check IS NULL AND task_type = 'task1'))",
                (now,),
            )
            conn.execute(
                "UPDATE submission SET image_status = 'failed', image_error = 'interrupted'"
                " WHERE image_status = 'pending'"
            )
            return cur.rowcount
