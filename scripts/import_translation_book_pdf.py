#!/usr/bin/env python3
"""Import a translation-style dictation book from a PDF into the database."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app
from api.dictation import _extract_pdf_text, _parse_vocab_pdf
from models import db, DictationBook, DictationWord, User


def resolve_creator_id(explicit_id=None):
    if explicit_id:
        user = User.query.get(int(explicit_id))
        if not user:
            raise SystemExit(f"creator id {explicit_id} not found")
        return user.id

    fallback = (
        User.query
        .filter(User.role.in_([User.ROLE_ADMIN, User.ROLE_ASSISTANT, User.ROLE_TEACHER]))
        .order_by(User.id.asc())
        .first()
    )
    if not fallback:
        raise SystemExit("no admin/assistant/teacher user available for created_by")
    return fallback.id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to the source PDF")
    parser.add_argument("--title", help="Book title; defaults to PDF filename")
    parser.add_argument("--description", help="Optional book description")
    parser.add_argument("--created-by", type=int, help="User id used as created_by")
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not write database")
    parser.add_argument("--replace", action="store_true", help="Soft-delete existing active book with the same title before import")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"pdf not found: {pdf_path}")

    title = (args.title or pdf_path.stem).strip()
    if not title:
        raise SystemExit("title must not be empty")

    with app.app_context():
        full_text = _extract_pdf_text(str(pdf_path))
        entries = _parse_vocab_pdf(full_text)
        if not entries:
            raise SystemExit("no entries parsed from pdf")

        if args.dry_run:
            print(f"dry-run: parsed {len(entries)} entries from {pdf_path.name}")
            for entry in entries[:20]:
                print(f"{entry['topic']}\t{entry['english']}\t{entry['chinese']}")
            return

        creator_id = resolve_creator_id(args.created_by)

        existing = DictationBook.query.filter_by(title=title, is_deleted=False).first()
        if existing and not args.replace:
            raise SystemExit(f"active book already exists with title: {title} (id={existing.id})")
        if existing and args.replace:
            existing.is_deleted = True
            existing.is_active = False

        description = (args.description or f"翻译练习 - 看中文写英文 ({len(entries)}词组)").strip()

        book = DictationBook(
            title=title,
            description=description,
            word_count=len(entries),
            created_by=creator_id,
            book_type="translation",
        )
        db.session.add(book)
        db.session.flush()

        for idx, entry in enumerate(entries, start=1):
            db.session.add(DictationWord(
                book_id=book.id,
                sequence=idx,
                word=entry["english"],
                translation=entry["chinese"],
                phonetic=entry.get("topic", ""),
            ))

        book.word_count = len(entries)
        db.session.commit()
        print(f"imported book id={book.id} title={book.title} word_count={book.word_count} created_by={creator_id}")


if __name__ == "__main__":
    main()
