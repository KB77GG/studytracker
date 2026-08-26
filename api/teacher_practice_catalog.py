"""Catalog and resource loaders for teacher-assigned practice materials."""

from __future__ import annotations

import json
from pathlib import Path

from werkzeug.utils import secure_filename


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_listening_jijing_part(
    root: Path,
    part_id: str,
) -> tuple[dict | None, str]:
    """Load one listening-jijing Part without allowing path traversal."""

    safe_id = secure_filename(part_id or "")
    if not safe_id or safe_id != (part_id or "").strip():
        return None, safe_id
    return _load_json(root / "parts" / f"{safe_id}.json"), safe_id


def load_reading_jijing_test(
    root: Path,
    test_id: str,
) -> tuple[dict | None, str]:
    """Load one ZYZ reading-jijing Test and verify its declared source."""

    safe_id = secure_filename(test_id or "")
    if not safe_id or safe_id != (test_id or "").strip():
        return None, safe_id
    payload = _load_json(root / f"{safe_id}.json")
    if not payload or payload.get("source") != "idictation_reading_jijing":
        return None, safe_id
    return payload, safe_id


def build_listening_jijing_catalog(
    root: Path,
    *,
    collection: str = "xiahuar",
) -> list[dict]:
    """Return the compact teacher picker catalog for the requested collection."""

    catalog = _load_json(root / "catalog.json") or {}
    result = []
    for book in catalog.get("books") or []:
        if collection and book.get("collection") != collection:
            continue
        tests = []
        for test in book.get("tests") or []:
            parts = [
                {
                    "id": part.get("id"),
                    "number": part.get("part_number"),
                    "part_title": part.get("part_title") or "练习",
                    "question_name": part.get("question_name") or "",
                    "question_type": part.get("question_type") or "",
                    "question_count": int(part.get("question_count") or 0),
                }
                for part in test.get("parts") or []
                if part.get("id")
            ]
            if not parts:
                continue
            tests.append(
                {
                    "id": parts[0]["id"],
                    "title": test.get("test_name") or parts[0]["id"],
                    "test_name": test.get("test_name") or parts[0]["id"],
                    "parts": parts,
                }
            )
        if not tests:
            continue
        result.append(
            {
                "series": "jijing",
                "collection": book.get("collection") or collection,
                "label": book.get("collection_title") or book.get("label") or "虾滑听力",
                "title": book.get("title") or str(book.get("in_book") or "虾滑听力"),
                "group": book.get("in_book"),
                "tests": tests,
            }
        )
    return result


def build_listening_jijing_options(
    root: Path,
    *,
    collection: str = "xiahuar",
) -> list[dict]:
    """Flatten one listening-jijing collection for the web assignment picker."""

    options = []
    for book in build_listening_jijing_catalog(root, collection=collection):
        collection_label = book.get("label") or "虾滑听力"
        group_title = book.get("title") or str(book.get("group") or "")
        for test in book.get("tests") or []:
            test_title = test.get("test_name") or test.get("title") or "练习"
            for part in test.get("parts") or []:
                part_id = part.get("id")
                if not part_id:
                    continue
                options.append(
                    {
                        "id": part_id,
                        "title": " · ".join(
                            value for value in (collection_label, group_title, test_title) if value
                        ),
                        "resource_type": "jijing",
                        "question_count": int(part.get("question_count") or 0),
                        "group_title": group_title,
                        "test_title": test_title,
                    }
                )
    return options


def build_listening_jijing_assignment(
    root: Path,
    part_id: str,
    *,
    collection: str = "xiahuar",
) -> dict | None:
    """Validate one web assignment and return its canonical task metadata."""

    payload, safe_id = load_listening_jijing_part(root, part_id)
    if not payload or payload.get("collection") != collection:
        return None
    detail = " · ".join(
        value
        for value in (
            payload.get("collection_title") or "虾滑听力",
            payload.get("part_title"),
            payload.get("test_name"),
        )
        if value
    )
    return {
        "id": safe_id,
        "detail": detail or safe_id,
        "category": "雅思-听力-虾滑",
        "planned_minutes": 15,
    }


def build_reading_jijing_catalog(root: Path) -> list[dict]:
    """Return ZYZ reading Tests enriched with Passage picker metadata."""

    catalog = _load_json(root / "catalog.json") or {}
    result = []
    for book in catalog.get("books") or []:
        tests = []
        for catalog_test in book.get("tests") or []:
            payload, safe_id = load_reading_jijing_test(
                root,
                str(catalog_test.get("id") or ""),
            )
            if not payload:
                continue
            passages = []
            for passage in payload.get("passages") or []:
                passage_number = int(passage.get("passage") or len(passages) + 1)
                question_count = sum(
                    len(group.get("questions") or []) for group in passage.get("groups") or []
                )
                passages.append(
                    {
                        "number": passage_number,
                        "title": f"Passage {passage_number}",
                        "question_name": passage.get("question_name") or "",
                        "question_count": question_count,
                    }
                )
            tests.append(
                {
                    **catalog_test,
                    "id": safe_id,
                    "series": "jijing",
                    "title": payload.get("title") or safe_id,
                    "passages": passages,
                }
            )
        if not tests:
            continue
        book_number = book.get("book")
        result.append(
            {
                "series": "jijing",
                "book": book_number,
                "label": f"ZYZ {book_number}",
                "tests": tests,
            }
        )
    return result
