"""目录与校验逻辑 for imported intensive listening exercises."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .listening_series import parse_intensive_id, parse_test_id

_EXERCISE_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _read_json(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _segment_count(payload: dict) -> int:
    return sum(
        len(part.get("segments") or [])
        for part in payload.get("parts") or []
        if isinstance(part, dict)
    )


def _first_part_name(payload: dict, fallback: str) -> str:
    parts = payload.get("parts") or []
    if isinstance(parts, list) and parts and isinstance(parts[0], dict):
        return str(parts[0].get("name") or fallback)
    return fallback


def build_intensive_catalog(root: Path) -> list[dict]:
    """Return imported exercises grouped as series -> book -> Test -> Part.

    Only registered ``*_sN`` filenames are exposed. Invalid JSON and files
    with an unregistered stem are intentionally ignored so a stray asset can
    never become a selectable homework source.
    """

    grouped: dict[tuple[int, int], dict] = {}
    for path in sorted(root.glob("*.json"), key=lambda item: item.name.lower()):
        info = parse_intensive_id(path.stem)
        if not info:
            continue
        payload = _read_json(path)
        if not payload:
            continue

        book_key = (info["order"], info["book"])
        book = grouped.setdefault(
            book_key,
            {
                "series": info["series"],
                "book": info["book"],
                "label": info["label"],
                "search_terms": info["search_terms"],
                "tests": {},
            },
        )
        test = book["tests"].setdefault(
            info["test"],
            {
                "id": info["test_key"],
                "key": info["test_key"],
                "series": info["series"],
                "book": info["book"],
                "test": info["test"],
                "title": parse_test_id(info["test_key"])["title"].removesuffix(
                    " Listening"
                ),
                "parts": [],
            },
        )
        test["parts"].append(
            {
                "id": path.stem,
                "exercise_id": path.stem,
                "number": info["section"],
                "section": info["section"],
                "title": payload.get("title") or info["title"],
                "part_title": _first_part_name(
                    payload,
                    f"Part {info['section']}",
                ),
                "segment_count": _segment_count(payload),
            }
        )

    books = []
    for book_key in sorted(grouped):
        book = grouped[book_key]
        tests = []
        for test_number in sorted(book["tests"]):
            test = book["tests"][test_number]
            test["parts"].sort(key=lambda item: (item["number"], item["id"]))
            test["part_count"] = len(test["parts"])
            test["section_count"] = test["part_count"]
            test["segment_count"] = sum(
                int(part.get("segment_count") or 0) for part in test["parts"]
            )
            # ``sections`` is a small compatibility convenience for clients
            # that already consume the Cambridge catalog shape.
            test["sections"] = list(test["parts"])
            tests.append(test)
        books.append(
            {
                **{key: value for key, value in book.items() if key != "tests"},
                "tests": tests,
                "test_count": len(tests),
                "part_count": sum(test["part_count"] for test in tests),
                "section_count": sum(test["section_count"] for test in tests),
            }
        )
    return books


def load_registered_intensive_exercise(
    root: Path, exercise_id: str | None
) -> tuple[dict | None, dict | None, str | None]:
    """Load an exercise only when its exact id is a registered static asset."""

    candidate = str(exercise_id or "")
    info = parse_intensive_id(candidate)
    if not candidate or not _EXERCISE_ID_RE.fullmatch(candidate) or not info:
        return None, None, None

    path = root / f"{candidate}.json"
    if path.parent != root or not path.is_file():
        return None, None, None
    payload = _read_json(path)
    if not payload:
        return None, None, None
    return payload, info, candidate
