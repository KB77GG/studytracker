#!/usr/bin/env python3
"""Import Reading Study passage analyses into the database (create tables + upsert).

Runs standalone with a *minimal* Flask app (never ``from app import app``) so it
adds zero model-loading memory pressure on the production box. Idempotent and
incremental: re-running only writes passages whose content actually changed.

Usage:
    python scripts/import_reading_study.py --create-tables   # first run: DDL + import
    python scripts/import_reading_study.py                   # later runs: incremental
    python scripts/import_reading_study.py --dry-run         # report only, no writes
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = Path(__file__).resolve().parent
for _path in (str(ROOT), str(SCRIPTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from flask import Flask  # noqa: E402

from api.reading_study_glossary import resolve_role  # noqa: E402
from config import Config  # noqa: E402
from models import ReadingPassageAnalysis, db  # noqa: E402
from validate_reading_study import (  # noqa: E402
    DEFAULT_OUTPUT,
    TOP_LEVEL_KEYS,
    load_source_passages,
    normalize_space,
    validate_sample,
)

STATUS_KEYS = ("created", "updated", "skipped", "failed", "ignored")


def make_app(database_uri: str | None = None) -> Flask:
    """Minimal Flask app bound only to the SQLAlchemy extension."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if database_uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
    db.init_app(app)
    return app


def compute_content_hash(source_passage: dict) -> str:
    """sha256 of the source paragraphs (normalize_space, sorted by label)."""
    paragraphs = (source_passage.get("content") or {}).get("paragraphs") or []
    parts = sorted(
        (str(row.get("label") or ""), normalize_space(row.get("text"))) for row in paragraphs
    )
    joined = "\n".join(f"{label}\t{text}" for label, text in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def normalize_payload(sample: dict) -> dict:
    """Augment each structure item with concept/label_zh/label_en (keep role)."""
    payload = copy.deepcopy(sample)
    for sentence in payload.get("sentences") or []:
        for item in sentence.get("structure") or []:
            resolved = resolve_role(item.get("role"))
            item["concept"] = resolved["concept"]
            item["label_zh"] = resolved["zh"]
            item["label_en"] = resolved["en"]
    return payload


def _load_analysis(path: Path) -> dict | None:
    """Return the parsed analysis dict, or None if the file is not one."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or set(data) != TOP_LEVEL_KEYS:
        return None
    return data


def import_one(path: Path, source_passages: dict[str, dict], *, dry_run: bool) -> tuple[str, str]:
    """Validate + upsert a single file. Returns (status, message)."""
    data = _load_analysis(path)
    if data is None:
        return "ignored", f"{path.name}: not a Reading Study analysis file"

    errors = validate_sample(path, source_passages)
    if errors:
        return "failed", f"{path.name}: {len(errors)} validation error(s)"

    passage_id = data["passage_id"]
    source_passage = source_passages[passage_id]["passage"]
    content_hash = compute_content_hash(source_passage)
    normalized = normalize_payload(data)
    payload_json = json.dumps(normalized, ensure_ascii=False)
    sentence_count = len(normalized["sentences"])

    fields = dict(
        test_id=data["test_id"],
        source_kind=data["source_kind"],
        passage_title=data["passage_title"],
        difficulty=data["difficulty"],
        schema_version=data["schema_version"],
        generation_standard=data["generation_standard"],
        content_hash=content_hash,
        sentence_count=sentence_count,
        status="ready",
        payload_json=payload_json,
    )

    existing = ReadingPassageAnalysis.query.filter_by(passage_id=passage_id).first()
    if existing is None:
        if not dry_run:
            db.session.add(ReadingPassageAnalysis(passage_id=passage_id, **fields))
        return "created", passage_id

    if existing.content_hash == content_hash and existing.payload_json == payload_json:
        return "skipped", passage_id

    if not dry_run:
        for key, value in fields.items():
            setattr(existing, key, value)
    return "updated", passage_id


def run_import(
    data_dir: Path,
    source_passages: dict[str, dict],
    *,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """Import every ``*.json`` under ``data_dir``. Runs inside an app context."""
    summary = {key: 0 for key in STATUS_KEYS}
    for path in sorted(Path(data_dir).glob("*.json")):
        status, message = import_one(path, source_passages, dry_run=dry_run)
        summary[status] += 1
        if verbose and status in {"created", "updated", "failed"}:
            print(f"{status.upper()} {message}")
    if not dry_run:
        db.session.commit()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-tables", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--database-uri", help="override SQLALCHEMY_DATABASE_URI (defaults to config)"
    )
    args = parser.parse_args()

    app = make_app(args.database_uri)
    with app.app_context():
        if args.create_tables:
            db.create_all()
            print("Tables ensured (db.create_all).")
        source_passages = load_source_passages()
        summary = run_import(args.data_dir, source_passages, dry_run=args.dry_run)
        ready_total = (
            None if args.dry_run else ReadingPassageAnalysis.query.filter_by(status="ready").count()
        )

    mode = "DRY-RUN " if args.dry_run else ""
    print(f"{mode}Summary: " + ", ".join(f"{key}={summary[key]}" for key in STATUS_KEYS))
    if ready_total is not None:
        print(f"Total ready passages in DB: {ready_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
