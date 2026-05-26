"""Backfill usage_note_audited from reviewed batch data.

Marks rows audited when they either appeared in usage_note batch JSON files
or already have a non-empty usage_note. Dry-run by default; pass --commit to
write changes.
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import DictationWord, db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--glob", default="scripts/usage_note_batch*.json")
    args = parser.parse_args()

    files = sorted(glob.glob(args.glob))
    print(f"Found {len(files)} batch JSON files")
    ids_from_json = set()
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            print(f"  [SKIP] {path}: {exc}")
            continue
        for item in data:
            if "id" in item:
                ids_from_json.add(int(item["id"]))
    print(f"  unique ids across all batch JSONs: {len(ids_from_json)}")

    with app.app_context():
        from_json_count = (
            DictationWord.query.filter(DictationWord.id.in_(ids_from_json))
            .filter(DictationWord.usage_note_audited == False)  # noqa: E712
            .count()
        )
        from_filled_count = (
            DictationWord.query.filter(DictationWord.usage_note.isnot(None))
            .filter(DictationWord.usage_note != "")
            .filter(DictationWord.usage_note_audited == False)  # noqa: E712
            .count()
        )
        print(f"rows to flag from JSON ids:         {from_json_count}")
        print(f"rows to flag from filled usage_note: {from_filled_count}")

        if args.commit:
            (
                DictationWord.query.filter(DictationWord.id.in_(ids_from_json))
                .filter(DictationWord.usage_note_audited == False)  # noqa: E712
                .update(
                    {DictationWord.usage_note_audited: True},
                    synchronize_session=False,
                )
            )
            (
                DictationWord.query.filter(DictationWord.usage_note.isnot(None))
                .filter(DictationWord.usage_note != "")
                .filter(DictationWord.usage_note_audited == False)  # noqa: E712
                .update(
                    {DictationWord.usage_note_audited: True},
                    synchronize_session=False,
                )
            )
            db.session.commit()
            audited_total = DictationWord.query.filter_by(
                usage_note_audited=True
            ).count()
            print(f"COMMITTED. total audited rows now: {audited_total}")
        else:
            print("DRY-RUN: pass --commit to write")


if __name__ == "__main__":
    main()
