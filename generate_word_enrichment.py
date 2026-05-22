#!/usr/bin/env python3
"""Batch-generate vocabulary enrichment for dictation words using Qwen."""

import argparse
from datetime import datetime
from pathlib import Path
import re
import sys

from sqlalchemy import or_

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from api.qwen import generate_vocab_enrichment  # noqa: E402
from models import db, DictationBook, DictationWord  # noqa: E402


SKIP_STATUSES = {"generated", "reviewed", "edited"}
FAILED_LOG = ROOT / "failed_words.log"
VERBISH_RE = re.compile(r"(^|[\s;；,，])(?:v|vt|vi)\.|动词|及物|不及物", re.IGNORECASE)


def _chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _is_verbish(word):
    text = f"{word.translation or ''} {word.core_meaning_zh or ''}"
    return bool(VERBISH_RE.search(text))


def _parse_ids(raw_ids):
    if not raw_ids:
        return None
    ids = []
    for item in raw_ids.split(","):
        item = item.strip()
        if not item:
            continue
        ids.append(int(item))
    return ids or None


def _query_words(book_id=None, limit=None, refresh_generated=False, verbish_only=False, ids=None):
    query = DictationWord.query.join(DictationBook, DictationWord.book_id == DictationBook.id)
    query = query.filter(DictationBook.is_deleted == False)  # noqa: E712
    if book_id:
        query = query.filter(DictationWord.book_id == book_id)
    if ids:
        query = query.filter(DictationWord.id.in_(ids))
    if refresh_generated:
        query = query.filter(DictationWord.vocab_ai_status == "generated")
    else:
        query = query.filter(
            or_(
                DictationWord.vocab_ai_status == None,  # noqa: E711
                ~DictationWord.vocab_ai_status.in_(SKIP_STATUSES),
            )
        )
    query = query.order_by(DictationWord.book_id.asc(), DictationWord.sequence.asc())
    words = query.all() if (verbish_only or ids) else query.limit(limit).all() if limit else query.all()
    if verbish_only:
        words = [word for word in words if _is_verbish(word)]
    if limit:
        words = words[:limit]
    return words


def _payload(word):
    return {
        "id": word.id,
        "word": word.word,
        "translation": word.translation or "",
        "phonetic": word.phonetic or "",
    }


def _apply_result(word, result, now):
    word.core_meaning_zh = result.get("core_meaning_zh") or None
    word.usage_pattern = result.get("usage_pattern") or None
    word.example_en = result.get("example_en") or None
    word.example_zh = result.get("example_zh") or None
    word.usage_note = result.get("usage_note") or None
    word.vocab_ai_status = "generated"
    word.vocab_ai_model = result.get("model")
    word.vocab_ai_generated_at = now
    word.vocab_reviewed_at = None
    if word.vocab_report_count is None:
        word.vocab_report_count = 0


def _mark_failed(words, reason):
    timestamp = datetime.utcnow().isoformat()
    with FAILED_LOG.open("a", encoding="utf-8") as fh:
        for word in words:
            word.vocab_ai_status = "failed"
            fh.write(f"{timestamp}\t{word.id}\t{word.word}\t{reason}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book-id", type=int, help="Only generate words in this book")
    parser.add_argument("--limit", type=int, help="Maximum number of words to process")
    parser.add_argument("--batch-size", type=int, default=10, help="Words per Qwen request")
    parser.add_argument("--ids", help="Comma-separated word ids to process")
    parser.add_argument(
        "--refresh-generated",
        action="store_true",
        help="Overwrite existing AI-generated rows. Reviewed/edited rows are still skipped.",
    )
    parser.add_argument(
        "--verbish-only",
        action="store_true",
        help="Only process entries whose translation/core meaning looks like a verb sense.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Generate and print examples without writing database")
    args = parser.parse_args()

    with app.app_context():
        words = _query_words(
            book_id=args.book_id,
            limit=args.limit,
            refresh_generated=args.refresh_generated,
            verbish_only=args.verbish_only,
            ids=_parse_ids(args.ids),
        )
        if args.dry_run and args.limit is None and not args.ids:
            words = words[:5]
        if not words:
            print("No words need enrichment.")
            return

        print(f"Preparing to enrich {len(words)} words.")
        processed = 0
        for batch in _chunks(words, max(args.batch_size, 1)):
            try:
                results = generate_vocab_enrichment([_payload(word) for word in batch])
            except RuntimeError as exc:
                print(f"Batch failed: {exc}", flush=True)
                if not args.dry_run:
                    _mark_failed(batch, str(exc))
                    db.session.commit()
                continue

            result_by_id = {int(item["id"]): item for item in results}
            now = datetime.utcnow()
            for word in batch:
                result = result_by_id.get(word.id)
                if not result:
                    if not args.dry_run:
                        _mark_failed([word], "missing_result")
                    print(f"Missing result: {word.id} {word.word}", flush=True)
                    continue
                if args.dry_run:
                    print(f"\n{word.word} | {word.translation or ''}")
                    print(f"核心义: {result.get('core_meaning_zh')}")
                    print(f"搭配: {result.get('usage_pattern')}")
                    print(f"例句: {result.get('example_en')}")
                    print(f"译文: {result.get('example_zh')}")
                    print(f"用法: {result.get('usage_note') or '-'}")
                    print(f"需复核: {result.get('needs_review')}")
                else:
                    _apply_result(word, result, now)
                processed += 1
                if processed % 20 == 0:
                    print(f"Processed {processed}/{len(words)}", flush=True)

            if not args.dry_run:
                db.session.commit()

            if processed >= len(words) and processed % 20 != 0:
                print(f"Processed {processed}/{len(words)}", flush=True)

        print("Dry run completed." if args.dry_run else "Word enrichment completed.", flush=True)


if __name__ == "__main__":
    main()
