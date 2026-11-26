#!/usr/bin/env python3
"""Collect, validate and atomically publish a complete weekly practice library."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.exam_sprint import _atomic_json, publish_snapshot, state_directory  # noqa: E402
from services.exam_sprint_import import prepare_complete_snapshot, ranked_rows  # noqa: E402
from services.ninefen_source import (
    fetch_public_exam,
    fetch_public_hotlist,
    parse_public_hotlist,
)  # noqa: E402

ERROR_CODES = {
    "CollectionError": "official_collection_failed",
    "NewAttemptRequired": "new_attempt_required",
    "UncertainSubmission": "uncertain_submission",
    "ReviewMismatch": "review_mismatch",
    "NinefenSourceError": "public_source_failed",
    "NinefenAssetError": "media_failed",
    "NinefenContentError": "conversion_failed",
    "SprintStoreError": "store_failed",
    "IncompleteSprintError": "incomplete_snapshot",
    "OSError": "local_io_failed",
    "ValueError": "invalid_data",
    "KeyError": "missing_field",
    "TypeError": "invalid_type",
    "RuntimeError": "runtime_failed",
    "AttributeError": "invalid_attribute",
}
DIAGNOSTIC_MODULES = {
    "scripts/sync_exam_sprint.py",
    "services/exam_sprint.py",
    "services/exam_sprint_import.py",
    "services/exam_sprint_store.py",
    "services/ninefen_source.py",
    "services/ninefen_session.py",
    "services/ninefen_content.py",
    "services/ninefen_assets.py",
    "services/practice_library_offline.py",
}


def sync_event(name, *, stream=None, **fields):
    print(json.dumps({"diagnostic_version": 1, "event": name, **fields}), file=stream, flush=True)


def report_failure(exc, stage):
    """Emit code locations and enumerated metadata, never exception text or locals."""
    kind = type(exc).__name__
    if kind not in ERROR_CODES:
        kind = next(
            (base.__name__ for base in type(exc).__mro__ if base.__name__ in ERROR_CODES),
            "UnknownError",
        )
    record = {
        "stage": stage,
        "error_code": ERROR_CODES.get(kind, "unexpected_error"),
        "exception_type": kind,
    }
    from services.ninefen_session import CollectionError

    status = exc.http_status if isinstance(exc, CollectionError) else None
    if type(status) is int and 100 <= status <= 599:
        record["http_status"] = status
        if status in (401, 403):
            record["error_code"] = "session_rejected"
    trace = exc.__traceback__
    while trace is not None:
        filename = Path(trace.tb_frame.f_code.co_filename)
        for module in DIAGNOSTIC_MODULES:
            if filename == ROOT / module:
                record["location"] = {"module": module, "line": trace.tb_lineno}
                break
        trace = trace.tb_next
    sync_event("sprint_sync_failed", stream=sys.stderr, **record)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=Path, help="Read a saved public albums response")
    parser.add_argument("--fetched-at", help="Original capture time, required with --from-file")
    parser.add_argument("--output-dir", type=Path, default=state_directory(ROOT))
    parser.add_argument("--exam-dir", type=Path, help="Use saved public papers instead of fetching")
    parser.add_argument("--session-file", type=Path, help="Owned mode-600 local Ninefen session")
    parser.add_argument(
        "--allow-new-attempts",
        action="store_true",
        help="Explicit permission to submit missing or changed papers",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate without publishing")
    args = parser.parse_args(argv)
    if bool(args.from_file) != bool(args.fetched_at):
        parser.error("--from-file and --fetched-at must be used together")
    if args.allow_new_attempts and not args.session_file:
        parser.error("--allow-new-attempts requires --session-file")
    if args.from_file and not args.exam_dir:
        parser.error("Offline feed requires --exam-dir")
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        lock_file = (args.output_dir / ".sync.lock").open("a")
    except OSError as exc:
        report_failure(exc, "local_setup")
        return 1
    with lock_file as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sync_event("sprint_sync_busy", stream=sys.stderr)
            return 1
        except OSError as exc:
            report_failure(exc, "local_setup")
            return 1
        stage = "hotlist"
        try:
            feed = (
                parse_public_hotlist(
                    json.loads(args.from_file.read_text()),
                    fetched_at=datetime.fromisoformat(args.fetched_at.replace("Z", "+00:00")),
                )
                if args.from_file
                else fetch_public_hotlist()
            )
            exams = {}
            for _subject, row in ranked_rows(feed):
                unit = row["source_id"]
                if row.get("source_available") is not True or row.get("entry_mode") != "exam":
                    continue
                if args.exam_dir:
                    stage = "exam_read"
                    exams[unit] = json.loads((args.exam_dir / f"{unit}.json").read_text())
                else:
                    stage = "exam_fetch"
                    exams[unit] = fetch_public_exam(unit)
                    stage = "exam_cache"
                    _atomic_json(state_directory(ROOT) / "exams" / f"{unit}.json", exams[unit])

            def progress(index, unit, action):
                sync_event("sprint_sync_progress", processed=index, action=action, unit_id=unit)

            if args.session_file:
                stage = "session"
                from services.ninefen_session import (
                    AnswerCollector,
                    NinefenSession,
                    collection_lock,
                )

                ids = sorted(exams)
                digest = hashlib.sha256(json.dumps(ids).encode()).hexdigest()
                private = state_directory(ROOT) / "private"
                allow = args.allow_new_attempts and not args.dry_run
                session = NinefenSession(args.session_file, allow_new_attempts=allow)
                stage = "collection_lock"
                with collection_lock(private):
                    stage = "collector"
                    collector = AnswerCollector(
                        session,
                        private,
                        ids,
                        digest,
                        scope="weekly_new_or_changed",
                        allow_new_attempts=allow,
                    )
                    stage = "prepare"
                    snapshot = prepare_complete_snapshot(
                        ROOT, feed, exams, answer_provider=collector.collect, progress=progress
                    )
            else:
                stage = "prepare"
                snapshot = prepare_complete_snapshot(ROOT, feed, exams, progress=progress)
            if not args.dry_run:
                stage = "publish"
                publish_snapshot(args.output_dir, snapshot)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError) as exc:
            report_failure(exc, stage)
            return 1
    total = sum(len(g["items"]) for groups in snapshot["subjects"].values() for g in groups)
    ready = sum(
        bool(row.get("mapping")) and not row.get("unavailable_reason")
        for groups in snapshot["subjects"].values()
        for g in groups
        for row in g["items"]
    )
    sync_event(
        "sprint_sync_completed",
        ok=True,
        dry_run=args.dry_run,
        total=total,
        verified_practice_links=ready,
        fetched_at=snapshot["fetched_at"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
