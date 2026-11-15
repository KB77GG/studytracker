#!/usr/bin/env python3
"""Validate an uploaded public practice capture before atomically activating it."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.exam_sprint import (  # noqa: E402
    _local_target,
    load_mappings,
    publish_snapshot,
    validate_snapshot,
)

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


@contextmanager
def using_state_directory(directory):
    """Scope service resolution to this command's explicit runtime directory."""
    previous = os.environ.get("EXAM_SPRINT_STATE_DIR")
    os.environ["EXAM_SPRINT_STATE_DIR"] = str(directory)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("EXAM_SPRINT_STATE_DIR", None)
        else:
            os.environ["EXAM_SPRINT_STATE_DIR"] = previous


def validate_candidate(root: Path, snapshot: dict, state_dir: Path) -> dict:
    """Check the complete list and every open exercise against local release files.

    Source exams/sessions are deliberately absent on the serving machine. Imported
    source hashes are bound to immutable content receipts; reviewed legacy hashes
    must equal the mappings shipped in the current code release.
    """
    if any(
        (state_dir / name).is_symlink()
        for name in ("assets", "content", "content/reading", "content/listening")
    ):
        raise ValueError("Public runtime directories must not be symlinks")
    validate_snapshot(snapshot)
    manual = load_mappings(root)
    total, ready, imported = 0, 0, 0
    with using_state_directory(state_dir):
        for subject, groups in snapshot["subjects"].items():
            for group in groups:
                for row in group["items"]:
                    total += 1
                    if row.get("source_available") is not True or row.get("entry_mode") != "exam":
                        if row.get("mapping"):
                            raise ValueError("Closed source item must not have an enabled mapping")
                        continue
                    mapping = row.get("mapping")
                    if not isinstance(mapping, dict) or any(
                        mapping.get(key) != expected
                        for key, expected in (
                            ("subject", subject),
                            ("source_id", row["source_id"]),
                            ("source_title", row["title"]),
                            ("source_part_id", row.get("source_part_id")),
                        )
                    ):
                        raise ValueError("Source-open item has no matching practice identity")
                    if not isinstance(mapping.get("source_part_id"), str) or not re.fullmatch(
                        r"[0-9]{1,30}", mapping["source_part_id"]
                    ):
                        raise ValueError("Practice source part identity is missing")
                    if any(
                        not isinstance(mapping.get(key), str) or not SHA256.fullmatch(mapping[key])
                        for key in ("source_content_sha256", "target_sha256")
                    ):
                        raise ValueError("Practice source/content fingerprint is missing")
                    if mapping.get("target_kind") == "ninefen":
                        if mapping.get("part_number") != group["part"]:
                            raise ValueError("Imported practice has the wrong source part number")
                        imported += 1
                    elif (
                        mapping.get("target_kind") is not None
                        or manual.get((subject, row["source_id"])) != mapping
                    ):
                        raise ValueError("Reviewed mapping differs from the current code release")
                    if row.get("unavailable_reason") or _local_target(root, mapping) is None:
                        raise ValueError(
                            "Source-open practice content or media failed verification"
                        )
                    ready += 1
    if total != 140:
        raise ValueError("Expected exactly 140 ranked exercises")
    return {
        "total": total,
        "ready": ready,
        "imported": imported,
        "reviewed_legacy": ready - imported,
    }


def read_candidate(path: Path, expected_sha256: str) -> tuple[dict, bytes]:
    if not isinstance(expected_sha256, str) or not SHA256.fullmatch(expected_sha256):
        raise ValueError("Invalid snapshot SHA256")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        raise ValueError("Invalid incoming snapshot file")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Incoming snapshot fingerprint differs")
    return json.loads(raw), raw


def prepare_public_directories(root: Path) -> dict:
    """Prepare the fixed upload destinations without following directory symlinks."""
    root = Path(root).resolve()
    directories = [root / "instance", root / "instance/exam_sprint"]
    state = directories[-1]
    directories.extend(
        state / name
        for name in ("assets", "content", "content/reading", "content/listening", "incoming")
    )
    for directory in directories:
        if directory.is_symlink():
            raise ValueError("Public upload destination must not be a symlink")
        directory.mkdir(exist_ok=True)
    return {"prepared": True}


def activate(root: Path, incoming: Path, expected_sha256: str, *, state_dir=None, dry_run=False):
    root = Path(root).resolve()
    state = Path(state_dir) if state_dir is not None else root / "instance" / "exam_sprint"
    expected = state / "incoming" / f"{expected_sha256}.json"
    if (
        ".." in incoming.parts
        or incoming.resolve() != expected.resolve()
        or any(
            p.is_symlink()
            for p in (state, state / "incoming", state / "history", state / "current.json")
        )
    ):
        raise ValueError("Incoming snapshot must be inside the selected runtime incoming directory")
    snapshot, _raw = read_candidate(incoming, expected_sha256)
    if dry_run:
        return {**validate_candidate(root, snapshot, state), "activated": False, "dry_run": True}
    lock_path = state / ".sync.lock"
    if lock_path.is_symlink():
        raise ValueError("Invalid activation lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = validate_candidate(root, snapshot, state)
        publish_snapshot(state, snapshot)
    return {**result, "activated": True, "dry_run": False, "snapshot_sha256": expected_sha256}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--prepare-directories", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_directories and (args.snapshot or args.expected_sha256 or args.dry_run):
        parser.error("--prepare-directories cannot be combined with snapshot activation")
    if not args.prepare_directories and not (args.snapshot and args.expected_sha256):
        parser.error("--snapshot and --expected-sha256 are required")
    try:
        result = (
            prepare_public_directories(args.root)
            if args.prepare_directories
            else activate(args.root, args.snapshot, args.expected_sha256, dry_run=args.dry_run)
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        print("Sprint activation failed validation; previous capture retained.", file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
