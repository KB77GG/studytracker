#!/usr/bin/env python3
"""Batch-generate vocabulary enrichment for dictation words using Qwen."""

import argparse
from datetime import datetime
from pathlib import Path
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


def _chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _query_words(book_id=None, limit=None):
    query = DictationWord.query.join(DictationBook, DictationWord.book_id == DictationBook.id)
    query = query.filter(DictationBook.is_deleted == False)  # noqa: E712
    if book_id:
        query = query.filter(DictationWord.book_id == book_id)
    query = query.filter(
        or_(
            DictationWord.vocab_ai_status == None,  # noqa: E711
            ~DictationWord.vocab_ai_status.in_(SKIP_STATUSES),
        )
    )
    query = query.order_by(DictationWord.book_id.asc(), DictationWord.sequence.asc())
    if limit:
        query = query.limit(limit)
    return query.all()


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
    parser.add_argument("--batch-size", type=int, default=50, help="Words per Qwen request")
    parser.add_argument("--dry-run", action="store_true", help="Generate and print examples without writing database")
    args = parser.parse_args()

    with app.app_context():
        words = _query_words(book_id=args.book_id, limit=args.limit)
        if args.dry_run:
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
                print(f"Batch failed: {exc}")
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
                    print(f"Missing result: {word.id} {word.word}")
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
                    print(f"Processed {processed}/{len(words)}")

            if not args.dry_run:
                db.session.commit()

            if processed >= len(words) and processed % 20 != 0:
                print(f"Processed {processed}/{len(words)}")

        print("Dry run completed." if args.dry_run else "Word enrichment completed.")


if __name__ == "__main__":
    main()
