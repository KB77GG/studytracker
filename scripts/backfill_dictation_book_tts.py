#!/usr/bin/env python3
"""Generate and bind cached TTS audio for a range in one dictation book.

The command is dry-run by default. With ``--apply`` it generates every missing
clip first, validates the MP3 payloads, and only then commits the selected
``DictationWord`` audio field in one database transaction. Generated cache
files are harmless if a provider fails before the database commit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("STUDYTRACKER_ROOT") or Path(__file__).resolve().parent.parent
).resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.dictation import (  # noqa: E402
    _dictation_tts_cache_path,
    _dictation_tts_text,
    _tts_provider_audio,
)
from app import app  # noqa: E402
from models import DictationBook, DictationWord, db  # noqa: E402

VALID_PROVIDERS = ("dashscope", "kokoro", "piper", "youdao")
VALID_FIELDS = ("audio_us", "audio_uk")


def _looks_like_mp3(data: bytes) -> bool:
    if not data or len(data) < 1024:
        return False
    if data.startswith(b"ID3"):
        return True
    limit = min(len(data) - 1, 4096)
    return any(data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0 for i in range(limit))


def _valid_mp3_file(path: Path) -> bool:
    try:
        return _looks_like_mp3(path.read_bytes())
    except OSError:
        return False


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
            handle.write(data)
            temp_name = handle.name
        os.replace(temp_name, path)
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def _one_pass_tts_text(text: str) -> str:
    """Normalize an audited pronunciation override without repeating it."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        raise ValueError("spoken_text must not be blank")
    return cleaned if cleaned.endswith((".", "!", "?")) else f"{cleaned}."


def _load_spoken_text_overrides(
    path: Path,
) -> tuple[int, str, dict[int, tuple[str, str]]]:
    """Load an exact book/sequence/word to spoken-text pronunciation map."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read pronunciation map {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("pronunciation map must be a JSON object")
    book_id = payload.get("book_id")
    if isinstance(book_id, bool) or not isinstance(book_id, int) or book_id < 1:
        raise ValueError("pronunciation map book_id must be a positive integer")
    book_title = str(payload.get("book_title") or "").strip()
    if not book_title:
        raise ValueError("pronunciation map book_title must not be blank")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("pronunciation map items must be a non-empty list")

    overrides: dict[int, tuple[str, str]] = {}
    for offset, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"pronunciation map item {offset} must be an object")
        sequence = item.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError(f"pronunciation map item {offset} has invalid sequence")
        if sequence in overrides:
            raise ValueError(f"duplicate pronunciation sequence: {sequence}")
        word = str(item.get("word") or "").strip()
        if not word:
            raise ValueError(f"pronunciation map sequence {sequence} has a blank word")
        spoken_text = _one_pass_tts_text(item.get("spoken_text"))
        overrides[sequence] = (word, spoken_text)
    return book_id, book_title, overrides


def _generate_target(
    target: tuple[int, int, str, str], provider: str, force: bool, retries: int
) -> tuple[int, int, str, Path, str]:
    word_id, sequence, word, tts_text = target
    with app.app_context():
        cache_path = _dictation_tts_cache_path(provider, word, tts_text)
        if not force and _valid_mp3_file(cache_path):
            return word_id, sequence, word, cache_path, "reused"

        for attempt in range(retries + 1):
            audio = _tts_provider_audio(provider, tts_text)
            if _looks_like_mp3(audio or b""):
                _write_atomic(cache_path, audio)
                return word_id, sequence, word, cache_path, "generated"
            if attempt < retries:
                time.sleep(attempt + 1)

    raise RuntimeError(f"provider returned no valid MP3 for sequence {sequence}: {word!r}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--book", type=int, required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int)
    parser.add_argument("--provider", choices=VALID_PROVIDERS, default="dashscope")
    parser.add_argument("--bind-field", choices=VALID_FIELDS, default="audio_us")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--spoken-text-map",
        type=Path,
        help=(
            "JSON map that pins exact book/sequence/word values to audited spoken text; "
            "cannot be combined with a partial sequence range."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Generate files and commit audio paths; otherwise only print the plan.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.start < 1 or (args.end is not None and args.end < args.start):
        raise SystemExit("invalid sequence range")
    if args.spoken_text_map and (args.start != 1 or args.end is not None):
        raise SystemExit("--spoken-text-map cannot be combined with --start/--end")
    workers = min(6, max(1, args.workers))
    retries = min(3, max(0, args.retries))

    override_path = args.spoken_text_map.expanduser().resolve() if args.spoken_text_map else None
    override_book_id = None
    override_book_title = None
    spoken_overrides: dict[int, tuple[str, str]] = {}
    if override_path:
        try:
            override_book_id, override_book_title, spoken_overrides = _load_spoken_text_overrides(
                override_path
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if override_book_id != args.book:
            raise SystemExit(
                f"pronunciation map is pinned to book {override_book_id}, not {args.book}"
            )

    with app.app_context():
        book = db.session.get(DictationBook, args.book)
        if book is None or book.is_deleted:
            raise SystemExit(f"active dictation book not found: {args.book}")
        if override_book_title is not None and book.title != override_book_title:
            raise SystemExit(
                "pronunciation map title mismatch: "
                f"expected {override_book_title!r}, found {book.title!r}"
            )

        query = DictationWord.query.filter(DictationWord.book_id == args.book)
        if spoken_overrides:
            query = query.filter(DictationWord.sequence.in_(spoken_overrides))
        else:
            query = query.filter(DictationWord.sequence >= args.start)
            if args.end is not None:
                query = query.filter(DictationWord.sequence <= args.end)
        rows = query.order_by(DictationWord.sequence.asc(), DictationWord.id.asc()).all()
        if not rows or any(not (row.word or "").strip() for row in rows):
            raise SystemExit("selected range is empty or contains a blank word")

        targets: list[tuple[int, int, str, str]] = []
        if spoken_overrides:
            rows_by_sequence = {row.sequence: row for row in rows}
            missing_sequences = sorted(set(spoken_overrides) - set(rows_by_sequence))
            if missing_sequences:
                raise SystemExit(
                    f"pronunciation map sequences not found in book: {missing_sequences}"
                )
            for sequence, (expected_word, spoken_text) in spoken_overrides.items():
                row = rows_by_sequence[sequence]
                word = (row.word or "").strip()
                if word != expected_word:
                    raise SystemExit(
                        f"pronunciation map word mismatch at sequence {sequence}: "
                        f"expected {expected_word!r}, found {word!r}"
                    )
                targets.append((row.id, sequence, word, spoken_text))
        else:
            targets = [
                (row.id, row.sequence, (row.word or "").strip(), _dictation_tts_text(row.word))
                for row in rows
            ]

        plan = {
            "apply": args.apply,
            "book_id": book.id,
            "book_title": book.title,
            "bind_field": args.bind_field,
            "provider": args.provider,
            "sequence_start": targets[0][1],
            "sequence_end": targets[-1][1],
            "target_sequences": [target[1] for target in targets],
            "target_count": len(targets),
            "workers": workers,
            "spoken_text_map": str(override_path) if override_path else None,
        }
        print(json.dumps(plan, ensure_ascii=False), flush=True)
        if not args.apply:
            return 0

    completed: dict[int, tuple[int, int, str, Path, str]] = {}
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(_generate_target, target, args.provider, args.force, retries): target
            for target in targets
        }
        for future in as_completed(future_map):
            target = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                failures.append(str(exc))
                print(f"FAILED sequence={target[1]} word={target[2]!r}: {exc}", flush=True)
                continue
            completed[result[0]] = result
            print(
                f"{result[4].upper()} sequence={result[1]} word={result[2]!r} "
                f"file={result[3].name}",
                flush=True,
            )

    if failures or len(completed) != len(targets):
        print(
            json.dumps(
                {
                    "ok": False,
                    "generated_or_reused": len(completed),
                    "failed": len(failures),
                    "errors": failures,
                    "database_committed": False,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1

    with app.app_context():
        rows_by_id = {
            row.id: row for row in DictationWord.query.filter(DictationWord.id.in_(completed)).all()
        }
        for word_id, _sequence, _word, cache_path, _status in completed.values():
            try:
                relative_path = cache_path.resolve().relative_to(PROJECT_ROOT).as_posix()
            except ValueError as exc:
                raise RuntimeError(f"cache path is outside project root: {cache_path}") from exc
            row = rows_by_id[word_id]
            existing = getattr(row, args.bind_field)
            if existing and existing != relative_path and not args.force:
                db.session.rollback()
                raise RuntimeError(
                    f"refusing to overwrite {args.bind_field} for word id {word_id}: {existing}"
                )
            setattr(row, args.bind_field, relative_path)
        db.session.commit()

    generated = sum(result[4] == "generated" for result in completed.values())
    print(
        json.dumps(
            {
                "ok": True,
                "generated": generated,
                "reused": len(completed) - generated,
                "bound": len(completed),
                "database_committed": True,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
