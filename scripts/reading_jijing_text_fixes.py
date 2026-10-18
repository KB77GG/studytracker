#!/usr/bin/env python3
"""Manual text fixes for IELTS reading jijing passages.

The raw idictation download glues some sentences together ("these."Manufacturers)
and carries a few obvious typos. The fixes live in
``data/reading_jijing_text_fixes.json`` and are applied in two places so they
survive rebuilds from raw:

- ``build_reading_test_practice.py --source jijing`` applies them while building;
- this script patches the existing ``static/reading_jijing/*.json`` in place.

Usage:
    python scripts/reading_jijing_text_fixes.py            # patch static files
    python scripts/reading_jijing_text_fixes.py --check    # fail if any fix is unapplied
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXES_PATH = ROOT / "data" / "reading_jijing_text_fixes.json"
STATIC_DIR = ROOT / "static" / "reading_jijing"


class TextFixError(ValueError):
    """A fix no longer matches its paragraph (stale or ambiguous)."""


def load_fixes(path: Path = FIXES_PATH) -> dict[str, list[dict]]:
    """Return fixes grouped by passage_id."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for fix in json.loads(path.read_text(encoding="utf-8"))["fixes"]:
        grouped[fix["passage_id"]].append(fix)
    return dict(grouped)


def apply_fix(text: str, fix: dict) -> tuple[str, bool]:
    """Apply one fix to a paragraph text. Returns (text, changed)."""
    find, replace = fix["find"], fix["replace"]
    count = text.count(find)
    if count == 1:
        return text.replace(find, replace), True
    if count == 0 and replace in text:
        return text, False
    where = f"{fix['passage_id']} {fix['paragraph_label']}"
    raise TextFixError(f"{where}: {find!r} occurs {count} times")


def apply_passage_fixes(passage_id: str, paragraphs: list[dict], fixes: dict) -> int:
    """Apply all fixes for one passage in place. Returns how many changed text."""
    by_label = {row.get("label"): row for row in paragraphs}
    changed = 0
    for fix in fixes.get(passage_id, []):
        row = by_label.get(fix["paragraph_label"])
        if row is None:
            raise TextFixError(f"{passage_id}: no paragraph {fix['paragraph_label']!r}")
        row["text"], did_change = apply_fix(row["text"], fix)
        changed += did_change
    return changed


def patch_static_files(fixes: dict, static_dir: Path = STATIC_DIR, write: bool = True) -> int:
    """Patch every static test file that has fixes. Returns changed fix count."""
    total = 0
    test_ids = sorted({passage_id.rsplit("_p", 1)[0] for passage_id in fixes})
    for test_id in test_ids:
        path = static_dir / f"{test_id}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        changed = sum(
            apply_passage_fixes(p["id"], p["content"]["paragraphs"], fixes)
            for p in payload["passages"]
        )
        if changed and write:
            # Same serialisation as build_reading_test_practice.py, so diffs stay minimal.
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        total += changed
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="report unapplied fixes, write nothing"
    )
    args = parser.parse_args()
    fixes = load_fixes()
    pending = patch_static_files(fixes, write=not args.check)
    if args.check:
        print(f"{pending} fix(es) not yet applied")
        return 1 if pending else 0
    print(f"applied {pending} fix(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
