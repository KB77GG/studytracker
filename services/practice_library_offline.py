"""Shared helpers for temporarily removing practice Tests from public catalogs.

Offline Tests keep their source JSON in place so historical attempts and direct
review links remain recoverable. Public catalog builders and derived indexes must
filter them through the same manifest instead of deleting source material.
"""

from __future__ import annotations

import json
from pathlib import Path

OFFLINE_MANIFEST = "offline_tests.json"


def load_offline_test_ids(root: Path) -> frozenset[str]:
    """Return valid Test ids marked offline in ``root/OFFLINE_MANIFEST``."""

    path = root / OFFLINE_MANIFEST
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return frozenset()

    ids = {
        str(entry.get("id") or "").strip()
        for entry in payload.get("tests") or []
        if isinstance(entry, dict) and entry.get("status") == "offline"
    }
    return frozenset(test_id for test_id in ids if test_id)


def filter_offline_catalog_books(root: Path, books: list[dict]) -> list[dict]:
    """Copy a book catalog while removing Tests named by the offline manifest."""

    offline_ids = load_offline_test_ids(root)
    if not offline_ids:
        return books

    filtered = []
    for book in books:
        tests = [
            test
            for test in book.get("tests") or []
            if str(test.get("id") or "") not in offline_ids
        ]
        if tests:
            filtered.append({**book, "tests": tests})
    return filtered
