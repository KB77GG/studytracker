#!/usr/bin/env python3
"""Collect official answers with explicit session and approval; read-only by default."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ninefen_session import (  # noqa: E402
    AnswerCollector,
    CollectionError,
    NinefenSession,
    _exam_questions,
    collection_lock,
    load_approval,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session-file",
        type=Path,
        required=True,
        help="Explicit owned mode-600 JSON containing token",
    )
    parser.add_argument(
        "--approval-file",
        type=Path,
        required=True,
        help="Explicit one_time_blank_submission or weekly_new_or_changed approval JSON",
    )
    parser.add_argument(
        "--exam-dir", type=Path, required=True, help="Public exam responses named <unit_id>.json"
    )
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument(
        "--allow-new-attempts",
        action="store_true",
        help="Permit one blank attempt per approved unit/content version if no review matches",
    )
    args = parser.parse_args(argv)
    try:
        unit_ids, approval_digest, scope = load_approval(args.approval_file)
        exams = {}
        for unit_id in unit_ids:
            path = args.exam_dir / f"{unit_id}.json"
            if path.stat().st_size > 8 * 1024 * 1024:
                raise CollectionError("Public exam exceeds size limit")
            exam = json.loads(path.read_text(encoding="utf-8"))
            _exam_questions(exam, unit_id)
            exams[unit_id] = exam
        session = NinefenSession(
            args.session_file, args.timeout, allow_new_attempts=args.allow_new_attempts
        )
        directory = ROOT / "instance" / "exam_sprint" / "private"
        with collection_lock(directory):
            collector = AnswerCollector(
                session,
                directory,
                unit_ids,
                approval_digest,
                scope=scope,
                allow_new_attempts=args.allow_new_attempts,
            )
            for index, unit_id in enumerate(unit_ids, 1):
                collector.collect(unit_id, exams[unit_id])
                print(
                    json.dumps({"completed": index, "total": len(unit_ids), "unit_id": unit_id}),
                    flush=True,
                )
                if index != len(unit_ids):
                    time.sleep(1)
        return 0
    except CollectionError as exc:
        print(f"Collection stopped: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError):
        print("Collection stopped: local input is unavailable or invalid", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
