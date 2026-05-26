"""Import low-risk vocab field backfills.

Reads a JSON array of {"id": int, "word": str, "<field>": str} and updates
DictationWord rows. Empty usage_note values mark a row as audited without
overwriting the user-facing field. Dry-run by default; pass --commit to write.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import DictationWord, db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    parser.add_argument(
        "--field",
        required=True,
        choices=["usage_pattern", "usage_note"],
    )
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    with open(args.json, "r", encoding="utf-8") as handle:
        items = json.load(handle)

    print(f"Loaded {len(items)} items from {args.json}")
    print(f"Target field: {args.field}")
    print(f"Mode: {'COMMIT' if args.commit else 'DRY-RUN (no writes)'}")
    print("=" * 70)

    audits_field = "usage_note_audited" if args.field == "usage_note" else None

    with app.app_context():
        updated = intentional_blank = skipped_filled = not_found = 0
        audit_flag_added = 0
        for item in items:
            word_id = item["id"]
            new_value = item.get(args.field, "")
            row = db.session.get(DictationWord, word_id)
            if row is None:
                print(f"  [NOT_FOUND] id={word_id}")
                not_found += 1
                continue
            current = getattr(row, args.field)
            already_audited = (
                bool(getattr(row, audits_field)) if audits_field else False
            )

            if new_value == "":
                intentional_blank += 1
                if audits_field and not already_audited:
                    if args.commit:
                        setattr(row, audits_field, True)
                    audit_flag_added += 1
                continue
            if current and current.strip():
                print(
                    f"  [SKIP_FILLED] id={word_id} "
                    f"word={row.word!r} current={current!r}"
                )
                skipped_filled += 1
                if audits_field and not already_audited:
                    if args.commit:
                        setattr(row, audits_field, True)
                    audit_flag_added += 1
                continue
            print(f"  [UPDATE]    id={word_id} word={row.word!r}")
            print(f"              {args.field}: {new_value!r}")
            if args.commit:
                setattr(row, args.field, new_value)
                if audits_field:
                    setattr(row, audits_field, True)
            updated += 1

        if args.commit:
            db.session.commit()
            print("=" * 70)
            print(f"COMMITTED {updated} updates")
        else:
            db.session.rollback()
            print("=" * 70)
            print(f"DRY-RUN: would update {updated} rows")
        print(f"  intentional-blank (audit flag set): {intentional_blank}")
        print(f"  already-filled (skipped):           {skipped_filled}")
        print(f"  audit-flag added (any reason):      {audit_flag_added}")
        print(f"  not-found:                          {not_found}")


if __name__ == "__main__":
    main()
