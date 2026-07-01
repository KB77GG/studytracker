#!/usr/bin/env python3
"""Pre-bake dictation TTS cache for every word in every dictation book.

Run once after deploying the new TTS pipeline (or whenever
DICTATION_TTS_PROVIDER_ORDER / provider settings invalidate the cache key).
Subsequent uploads / task assignments are covered by the in-app background
prewarm hooks; this script is the one-shot backfill for existing data.
Config changes create new cache keys; older cache files remain harmless until
they are removed by a separate cleanup step.

Usage:
    python scripts/prewarm_dictation_tts.py              # all non-deleted dictation books
    python scripts/prewarm_dictation_tts.py --book 12    # one book
    python scripts/prewarm_dictation_tts.py --dry-run    # just print plan
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so `import app` works when run from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app  # noqa: E402
from models import DictationBook, DictationWord  # noqa: E402
from api.dictation import (  # noqa: E402
    _dictation_tts_cache_candidates,
    _dictation_tts_text,
    _generate_tts_to_cache,
)


def collect_words(book_ids: list[int] | None) -> list[tuple[int, str, str]]:
    query = DictationBook.query.filter_by(is_deleted=False)
    if book_ids:
        query = query.filter(DictationBook.id.in_(book_ids))
    books = query.all()

    out: list[tuple[int, str, str]] = []
    for book in books:
        # Translation books never play audio — skip.
        if (book.book_type or "dictation").lower() == "translation":
            continue
        words = (
            DictationWord.query.filter_by(book_id=book.id)
            .order_by(DictationWord.sequence)
            .all()
        )
        for w in words:
            text = (w.word or "").strip()
            if text:
                out.append((book.id, book.title or f"book#{book.id}", text))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--book",
        type=int,
        action="append",
        help="Limit to a specific DictationBook id (repeatable).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be generated without invoking TTS providers.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate current-key cache files even if they already exist; stale older-key files are not pruned.",
    )
    args = parser.parse_args()

    with app.app_context():
        targets = collect_words(args.book)
        if not targets:
            print("No dictation words found.")
            return 0

        # Deduplicate by tts_text so each unique phrase is generated once.
        seen: dict[str, tuple[int, str, str]] = {}
        for book_id, title, word in targets:
            tts_text = _dictation_tts_text(word)
            if tts_text and tts_text not in seen:
                seen[tts_text] = (book_id, title, word)

        total = len(seen)
        print(f"Books: {len({t[0] for t in targets})}, unique TTS phrases: {total}")
        if args.dry_run:
            for i, (tts_text, (book_id, title, word)) in enumerate(seen.items(), 1):
                print(f"  [{i}/{total}] book {book_id} {title!r}: {word!r}")
            return 0

        started = time.time()
        generated = 0
        skipped = 0
        failed = 0

        for i, (tts_text, (book_id, title, word)) in enumerate(seen.items(), 1):
            cache_candidates = _dictation_tts_cache_candidates(word, tts_text)
            cache_hit = any(path.exists() for _, path in cache_candidates)
            if cache_hit and not args.force:
                skipped += 1
                continue
            if args.force and cache_hit:
                for _, path in cache_candidates:
                    if not path.exists():
                        continue
                    try:
                        path.unlink()
                    except OSError:
                        pass

            t0 = time.time()
            result = _generate_tts_to_cache(word, tts_text)
            dt = time.time() - t0
            if result:
                generated += 1
                tag = result.name.split("_dict_", 1)[0]
                print(f"  [{i}/{total}] {word!r} → {tag} ({dt:.2f}s)")
            else:
                failed += 1
                print(f"  [{i}/{total}] {word!r} → FAILED", file=sys.stderr)

        elapsed = time.time() - started
        print(
            f"Done in {elapsed:.1f}s. generated={generated} skipped={skipped} failed={failed}"
        )
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
