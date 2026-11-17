#!/usr/bin/env python3
"""Preview a private four/six-student first pilot; --apply only enrolls.

Never changes .env, restarts a service, or imports historical errors. A durable
private intent allows a retry to recognize a completed database commit even if
the final manifest update failed. Stdout contains only aggregate facts.
"""

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import sys
import tempfile
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import manage_vocabulary_error_pilot as manager
from scripts import migrate_vocabulary_checkpoint_sources as migration

FLAG = "VOCABULARY_ERROR_REVIEW_ENABLED"
APPROVED = {
    "daily_limit": 20,
    "sample_limit": 4,
    "maintenance_limit": 10,
    "success_interval_days": 2,
    "failure_limit": 3,
    "pause_days": 7,
    "overdue_days": 7,
}
MAX_MANIFEST_BYTES = 262144


class ActivationError(ValueError):
    pass


def _check_private(fd):
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid != os.geteuid()
        or info.st_nlink != 1
    ):
        raise ActivationError("private_manifest_permissions_invalid")


def _read_private(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, encoding="utf-8") as source:
        _check_private(source.fileno())
        text = source.read(MAX_MANIFEST_BYTES + 1)
        if len(text) > MAX_MANIFEST_BYTES:
            raise ActivationError("private_manifest_too_large")
        manifest = json.loads(text)
    ids = manifest.get("student_ids") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != 1
        or not isinstance(ids, list)
        or len(ids) not in (4, 6)
        or any(type(value) is not int or value <= 0 for value in ids)
        or len(set(ids)) != len(ids)
    ):
        raise ActivationError("four_or_six_unique_students_required")
    return manifest, sorted(ids)


def _write_private(path, manifest):
    """Atomic mode-0600 replacement; the separate flock remains held."""
    target = Path(path)
    fd, temporary = tempfile.mkstemp(prefix="." + target.name + ".", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(manifest, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _manifest_lock(path):
    # A distinct inode is needed: the manifest itself is atomically replaced.
    fd = os.open(str(path) + ".lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        _check_private(fd)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ActivationError("activation_in_progress") from error
        yield
    finally:
        os.close(fd)


def _effective_off(database):
    value = None
    env_file = Path(database).resolve(strict=True).parent / ".env"
    if env_file.exists():
        with env_file.open(encoding="utf-8") as source:
            for raw in source:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, raw_value = line.split("=", 1)
                if key.strip() == FLAG and value is None:
                    value = raw_value.strip().strip("'").strip('"')
    value = os.environ.get(FLAG, value)
    if value is not None and value.strip().lower() in {"1", "true", "yes", "on"}:
        raise ActivationError("global_switch_must_be_off")
    if manager.effective_policy_parameters(database) != APPROVED:
        raise ActivationError("approved_policy_parameters_required")


@contextmanager
def _readonly(database):
    connection = sqlite3.connect(
        Path(database).resolve(strict=True).as_uri() + "?mode=ro", uri=True, timeout=0.5
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        yield connection
        assert connection.total_changes == 0
    finally:
        connection.close()


def _selection_hash(ids):
    return hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()


def _check_state(connection, database, ids, starts_at, now, intent=None, *, require_empty=False):
    _effective_off(database)
    schema = migration.inspect(connection)
    if schema["schema_version"] != "sources_v1" or schema["migration_required"]:
        raise ActivationError("checkpoint_sources_schema_not_ready")
    checked = manager.preview(connection, student_ids=ids, starts_at=starts_at, now=now)
    if (
        checked["invalid_or_inactive_count"]
        or checked["unfinished_review_count"]
        or checked["active_student_count"] != len(ids)
    ):
        raise ActivationError("selected_students_not_ready")
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in manager.TABLES
    }
    if any(counts[table] for table in manager.TABLES[1:]):
        raise ActivationError("policy_state_not_empty")
    if intent is not None:
        if (
            intent.get("version") != 1
            or intent.get("state") not in {"pending", "enrolled"}
            or intent.get("selection_hash") != _selection_hash(ids)
            or intent.get("database_identity") != checked["database_identity"]
            or intent.get("policy_parameters") != APPROVED
        ):
            raise ActivationError("activation_intent_mismatch")
    if counts[manager.TABLES[0]]:
        if require_empty or intent is None:
            raise ActivationError("existing_pilot_state")
        rows = connection.execute(
            "SELECT student_id,enabled,starts_at FROM vocabulary_review_policy_enrollment"
        ).fetchall()
        if (
            len(rows) != len(ids)
            or {row[0] for row in rows} != set(ids)
            or any(row[1] != 1 or manager.parse_start(row[2]) != starts_at for row in rows)
        ):
            raise ActivationError("existing_pilot_does_not_match_intent")
        return checked, True
    if intent is not None and intent["state"] == "enrolled":
        raise ActivationError("recorded_enrollment_missing")
    if starts_at < now - timedelta(minutes=10) or starts_at > now:
        raise ActivationError("activation_preview_expired")
    if intent is not None and intent.get("preview_digest") != checked["preview_digest"]:
        raise ActivationError("activation_preview_changed")
    return checked, False


def _summary(checked, *, applied=False, already=False):
    return {
        "ok": True,
        "read_only_preview": not applied,
        "selected_count": checked["selected_count"],
        "enrolled_count": checked["selected_count"] if applied or already else 0,
        "enrollment_rows_created": checked["selected_count"] if applied and not already else 0,
        "already_applied": already,
        "starts_at_utc": checked["starts_at_utc"],
        "schema_version": "sources_v1",
        "policy_parameters": APPROVED,
        "preview_valid_for_seconds": 600,
        "global_switch_unchanged": True,
        "historical_error_rows_imported": 0,
        "initial_mandatory_rows_created": 0,
        "student_identity_rows_exported": False,
    }


def activate(database, selection, *, apply=False, now=None):
    now = now or manager.utc_now()
    database, selection = Path(database).resolve(strict=True), Path(selection).absolute()
    # Validate before even creating a lock file; preview never writes a file.
    manifest, ids = _read_private(selection)

    def execute(manifest, ids):
        intent = manifest.get("activation")
        if intent is not None and not isinstance(intent, dict):
            raise ActivationError("activation_intent_mismatch")
        starts_at = manager.parse_start(intent["starts_at_utc"]) if intent else now
        with _readonly(database) as connection:
            checked, already = _check_state(connection, database, ids, starts_at, now, intent)
        if not apply:
            return _summary(checked, already=already)
        if not already:
            if intent is None:
                intent = {
                    "version": 1,
                    "state": "pending",
                    "starts_at_utc": checked["starts_at_utc"],
                    "selection_hash": _selection_hash(ids),
                    "database_identity": checked["database_identity"],
                    "policy_parameters": APPROVED,
                    "preview_digest": checked["preview_digest"],
                }
                manifest["activation"] = intent
                _write_private(selection, manifest)

            def locked_check(connection):
                _check_state(connection, database, ids, starts_at, now, intent, require_empty=True)

            manager.apply_enrollment(
                database,
                student_ids=ids,
                starts_at=starts_at,
                expected_digest=intent["preview_digest"],
                now=now,
                locked_check=locked_check,
            )
        # Read back exact IDs/cohort while global OFF before recording success.
        with _readonly(database) as connection:
            checked, verified = _check_state(connection, database, ids, starts_at, now, intent)
        if not verified:
            raise ActivationError("enrollment_readback_failed")
        manifest["activation"].update(
            state="enrolled",
            verified_at_utc=manager.utc_now().isoformat() + "Z",
            enrolled_count=len(ids),
            historical_error_rows_imported=0,
            initial_mandatory_rows_created=0,
            global_switch_unchanged=True,
        )
        try:
            _write_private(selection, manifest)
        except OSError as error:
            raise ActivationError("activation_manifest_finalize_failed_retry_safe") from error
        return _summary(checked, applied=True, already=already)

    if not apply:
        return execute(manifest, ids)
    with _manifest_lock(selection):
        return execute(*_read_private(selection))


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ActivationError("invalid_arguments")


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--apply", action="store_true")
    try:
        args = parser.parse_args(argv)
        result = activate(args.database, args.selection, apply=args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ActivationError as error:
        print(
            json.dumps({"ok": False, "error": str(error), "student_identity_rows_exported": False})
        )
    except Exception:
        print(json.dumps({"ok": False, "error": "pilot_activation_failed_no_identities_exported"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
