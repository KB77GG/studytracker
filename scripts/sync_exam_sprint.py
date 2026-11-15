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
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / ".sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another sprint sync is running; no changes made.", file=sys.stderr)
            return 1
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
                    exams[unit] = json.loads((args.exam_dir / f"{unit}.json").read_text())
                else:
                    exams[unit] = fetch_public_exam(unit)
                    _atomic_json(state_directory(ROOT) / "exams" / f"{unit}.json", exams[unit])

            def progress(index, unit, action):
                print(
                    json.dumps({"processed": index, "action": action, "unit_id": unit}), flush=True
                )

            if args.session_file:
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
                with collection_lock(private):
                    collector = AnswerCollector(
                        session,
                        private,
                        ids,
                        digest,
                        scope="weekly_new_or_changed",
                        allow_new_attempts=allow,
                    )
                    snapshot = prepare_complete_snapshot(
                        ROOT, feed, exams, answer_provider=collector.collect, progress=progress
                    )
            else:
                snapshot = prepare_complete_snapshot(ROOT, feed, exams, progress=progress)
            if not args.dry_run:
                publish_snapshot(args.output_dir, snapshot)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError) as exc:
            print(
                f"Sprint sync failed ({type(exc).__name__}); previous capture retained.",
                file=sys.stderr,
            )
            return 1
    total = sum(len(g["items"]) for groups in snapshot["subjects"].values() for g in groups)
    ready = sum(
        bool(row.get("mapping")) and not row.get("unavailable_reason")
        for groups in snapshot["subjects"].values()
        for g in groups
        for row in g["items"]
    )
    print(
        json.dumps(
            {
                "ok": True,
                "dry_run": args.dry_run,
                "total": total,
                "verified_practice_links": ready,
                "fetched_at": snapshot["fetched_at"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
