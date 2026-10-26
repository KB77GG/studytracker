#!/usr/bin/env python3
"""Manual text fixes for IELTS reading jijing passages.

The raw idictation download glues some sentences together ("these."Manufacturers)
and carries a few obvious typos. The fixes live in
``data/reading_jijing_text_fixes.json`` and are applied in two places so they
survive rebuilds from raw:

A fix edits one paragraph. With ``"questions": true`` the same replacement is also
made in that passage's question data (titles, central sentences, locating words),
which quote the passage; ``"paragraph_label": null`` marks a fix found only there.
In question data ``find`` only matches as whole words, also with curly apostrophes
(’) where the fix has straight ones; ``"exact": true`` (question data only) replaces
just the strings that equal ``find``, such as a one-word locating synonym.
``"at_end": true`` replaces ``find`` at the very end of the paragraph, for adding a
missing final full stop (there ``find`` is part of ``replace``).
``"at_start": true`` likewise replaces ``find`` at the very start, for restoring opening
text the raw data lost (``replace`` ends with ``find``).
``"summary": true`` edits the passage's Chinese summary (one string covering all
paragraphs; ``paragraph_label`` names the paragraph it summarises) instead of the text.

- ``build_reading_test_practice.py --source jijing`` applies them while building;
- this script patches the existing ``static/reading_jijing/*.json`` in place.

Usage:
    python scripts/reading_jijing_text_fixes.py            # patch static files
    python scripts/reading_jijing_text_fixes.py --check    # fail if any fix is unapplied
"""

from __future__ import annotations

import argparse
import json
import re
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
    where = f"{fix['passage_id']} {fix['paragraph_label']}"
    if fix.get("at_end"):
        if text.endswith(replace):
            return text, False
        if text.endswith(find):
            return text[: len(text) - len(find)] + replace, True
        raise TextFixError(f"{where}: paragraph does not end with {find!r}")
    if fix.get("at_start"):
        if text.startswith(replace):
            return text, False
        if text.startswith(find):
            return replace + text[len(find) :], True
        raise TextFixError(f"{where}: paragraph does not start with {find!r}")
    count = text.count(find)
    if count == 1:
        return text.replace(find, replace), True
    if count == 0 and replace in text:
        return text, False
    raise TextFixError(f"{where}: {find!r} occurs {count} times")


# Latin letters and digits; Chinese text right next to an English name is still a boundary.
WORD_CHAR = "0-9A-Za-zÀ-ÖØ-öø-ÿ"


def word_pattern(find: str) -> re.Pattern:
    """find, matching only where its letter/digit ends are not inside a longer word."""
    pattern = re.escape(find)
    if find[:1].isalnum():
        pattern = f"(?<![{WORD_CHAR}])" + pattern
    if find[-1:].isalnum():
        pattern += f"(?![{WORD_CHAR}])"
    return re.compile(pattern)


def replace_in_place(node, find: str, replace: str, exact: bool = False) -> tuple[int, bool]:
    """Replace in every string of nested lists/dicts, as whole words ("out side" leaves
    "out sidecar"), or with exact only strings equal to find. Returns (count, replace seen)."""
    pattern = None if exact else word_pattern(find)
    count, seen = 0, False
    items = node.items() if isinstance(node, dict) else enumerate(node)
    for key, value in list(items):
        if isinstance(value, str):
            if exact:
                hits = int(value == find)
                node[key] = replace if hits else value
                seen = seen or node[key] == replace
            else:
                node[key], hits = pattern.subn(lambda _match: replace, value)
                seen = seen or replace in node[key]
            count += hits
        elif isinstance(value, (dict, list)):
            sub_count, sub_seen = replace_in_place(value, find, replace, exact)
            count, seen = count + sub_count, seen or sub_seen
    return count, seen


def question_variants(find: str, replace: str) -> list[tuple[str, str]]:
    """The fix as written and, for straight apostrophes, the curly form question data uses."""
    pairs = [(find, replace)]
    if "'" in find:
        pairs.append((find.replace("'", "’"), replace.replace("'", "’")))
    return pairs


def check_fix_kind(passage_id: str, fix: dict) -> None:
    for flag in ("at_end", "at_start"):
        if fix.get("questions") and fix.get(flag):
            raise TextFixError(f"{passage_id}: an {flag} fix cannot also edit question data")
    if fix.get("exact") and (fix["paragraph_label"] is not None or not fix.get("questions")):
        raise TextFixError(f"{passage_id}: an exact fix edits question data only")
    if fix.get("summary") and (fix["paragraph_label"] is None or fix.get("questions")):
        raise TextFixError(f"{passage_id}: a summary fix edits the summary only")


def apply_passage_fixes(
    passage_id: str,
    paragraphs: list[dict],
    fixes: dict,
    groups: list | None = None,
    content: dict | None = None,
) -> int:
    """Apply all fixes for one passage in place. Returns how many changed text.

    content is the passage content holding the summary; without it summary fixes wait.
    """
    by_label = {row.get("label"): row for row in paragraphs}
    changed = 0
    for fix in fixes.get(passage_id, []):
        check_fix_kind(passage_id, fix)
        did_change, label = False, fix["paragraph_label"]
        if fix.get("summary"):
            if content is not None:
                content["summary"], did_change = apply_fix(content.get("summary") or "", fix)
        elif label is not None:
            row = by_label.get(label)
            if row is None:
                raise TextFixError(f"{passage_id}: no paragraph {label!r}")
            row["text"], did_change = apply_fix(row["text"], fix)
        if fix.get("questions") and groups is not None:
            count = seen = 0
            for find, replace in question_variants(fix["find"], fix["replace"]):
                hits, found = replace_in_place(groups, find, replace, fix.get("exact", False))
                count, seen = count + hits, seen or found
            if label is None and not count and not seen:
                raise TextFixError(f"{passage_id}: {fix['find']!r} not in question data")
            did_change = did_change or count > 0
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
            apply_passage_fixes(
                p["id"],
                p["content"]["paragraphs"],
                fixes,
                p.get("groups"),
                p["content"],
            )
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
