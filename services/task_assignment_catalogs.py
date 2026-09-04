"""Small, cached catalogs used by the staff assignment drawer."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from werkzeug.utils import secure_filename


class ListeningExerciseNotFound(ValueError):
    pass


def _segment_rows(payload: dict) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    global_index = 0
    for part_index, part in enumerate(payload.get("parts") or []):
        part_name = part.get("name") or f"Part {part_index + 1}"
        for segment_index, segment in enumerate(part.get("segments") or []):
            content = str(segment.get("text") or "").strip()
            preview = content[:90] + ("..." if len(content) > 90 else "")
            rows.append(
                {
                    "id": global_index,
                    "sequence": global_index + 1,
                    "content": f"{part_name} · 第{segment_index + 1}句 · {preview}",
                }
            )
            global_index += 1
    return rows


@lru_cache(maxsize=4)
def _intensive_catalog(root_value: str) -> tuple[tuple[str, str, int], ...]:
    root = Path(root_value)
    rows: list[tuple[str, str, int]] = []
    if not root.exists():
        return ()
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if payload.get("hidden_from_catalog"):
            continue
        segment_count = sum(
            len(part.get("segments") or []) for part in payload.get("parts") or []
        )
        rows.append((path.stem, payload.get("title") or path.stem, segment_count))
    return tuple(rows)


def intensive_listening_catalog(root: Path) -> list[dict[str, int | str]]:
    return [
        {"id": exercise_id, "title": title, "segment_count": segment_count}
        for exercise_id, title, segment_count in _intensive_catalog(str(root.resolve()))
    ]


@lru_cache(maxsize=4)
def _test_catalog(root_value: str) -> tuple[tuple[str, str, int, int], ...]:
    root = Path(root_value)
    rows: list[tuple[str, str, int, int]] = []
    if not root.exists():
        return ()
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        sections = payload.get("sections") or []
        question_count = sum(
            len(group.get("questions") or [])
            for section in sections
            for group in section.get("groups") or []
        )
        rows.append((path.stem, payload.get("title") or path.stem, len(sections), question_count))
    return tuple(rows)


def listening_test_catalog(root: Path) -> list[dict[str, int | str]]:
    return [
        {
            "id": test_id,
            "title": title,
            "section_count": section_count,
            "question_count": question_count,
        }
        for test_id, title, section_count, question_count in _test_catalog(str(root.resolve()))
    ]


def load_intensive_listening_segments(root: Path, exercise_id: str) -> list[dict[str, int | str]]:
    candidate_id = str(exercise_id or "").strip()
    if not candidate_id or secure_filename(candidate_id) != candidate_id:
        raise ListeningExerciseNotFound("invalid listening exercise")
    resolved_root = root.resolve()
    path = (resolved_root / f"{candidate_id}.json").resolve()
    if path.parent != resolved_root or not path.is_file():
        raise ListeningExerciseNotFound("listening exercise not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ListeningExerciseNotFound("listening exercise not found") from exc
    if payload.get("hidden_from_catalog"):
        raise ListeningExerciseNotFound("listening exercise not found")
    return _segment_rows(payload)
