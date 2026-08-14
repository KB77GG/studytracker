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


def _generate_target(
    target: tuple[int, int, str], provider: str, force: bool, retries: int
) -> tuple[int, int, str, Path, str]:
    word_id, sequence, word = target
    with app.app_context():
        tts_text = _dictation_tts_text(word)
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
        "--apply",
        action="store_true",
        help="Generate files and commit audio paths; otherwise only print the plan.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.start < 1 or (args.end is not None and args.end < args.start):
        raise SystemExit("invalid sequence range")
    workers = min(6, max(1, args.workers))
    retries = min(3, max(0, args.retries))

    with app.app_context():
        book = db.session.get(DictationBook, args.book)
        if book is None or book.is_deleted:
            raise SystemExit(f"active dictation book not found: {args.book}")
        query = DictationWord.query.filter(
            DictationWord.book_id == args.book,
            DictationWord.sequence >= args.start,
        )
        if args.end is not None:
            query = query.filter(DictationWord.sequence <= args.end)
        rows = query.order_by(DictationWord.sequence.asc(), DictationWord.id.asc()).all()
        targets = [(row.id, row.sequence, (row.word or "").strip()) for row in rows]
        if not targets or any(not word for _word_id, _sequence, word in targets):
            raise SystemExit("selected range is empty or contains a blank word")

        plan = {
            "apply": args.apply,
            "book_id": book.id,
            "book_title": book.title,
            "bind_field": args.bind_field,
            "provider": args.provider,
            "sequence_start": targets[0][1],
            "sequence_end": targets[-1][1],
            "target_count": len(targets),
            "workers": workers,
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
