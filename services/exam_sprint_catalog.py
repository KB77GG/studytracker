"""Verified current sprint resources for staff pickers, without DB access.

Selections bind the immutable local resource and (for reading) its passage.
Existing tasks retain those IDs independently of later weekly catalog changes.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from services.exam_sprint import _local_target, load_sprint_view


def _question_count(payload, subject, passage):
    if subject == "listening":
        return sum(len(group.get("items") or []) for group in payload.get("groups") or [])
    units = [unit for unit in payload.get("passages") or [] if unit.get("passage") == passage]
    if len(units) != 1:
        return 0
    return sum(len(group.get("questions") or []) for group in units[0].get("groups") or [])


def load_sprint_catalog(root: str | Path, subject: str) -> dict:
    """Return metadata only for currently verified, playable ranking entries."""
    view = load_sprint_view(root, subject)
    groups = []
    for group in view["groups"]:
        items = []
        for row in group["items"]:
            if not row.get("practice_url"):
                continue
            mapping = row["mapping"]
            target = _local_target(Path(root), mapping)
            if target is None:
                continue
            passage = mapping.get("passage") if subject == "reading" else None
            count = _question_count(target[0], subject, passage)
            if not count:
                continue
            target_id = mapping["target_id"]
            selection_id = f"{target_id}@{passage}" if subject == "reading" else target_id
            items.append(
                {
                    "source_id": row["source_id"],
                    "source_part_id": mapping.get("source_part_id"),
                    "subject": subject,
                    "part": group["part"],
                    "rank": row["rank"],
                    "title": row["title"],
                    "title_zh": row.get("title_zh") or "",
                    "label": f"7天热榜 · P{group['part']} #{row['rank']} · {row['title']}",
                    "target_id": target_id,
                    "target_kind": mapping.get("target_kind") or "legacy",
                    "selection_id": selection_id,
                    "passage": passage,
                    "question_count": count,
                    "practice_url": target[1],
                    "mapping": deepcopy(mapping),
                }
            )
        groups.append({"part": group["part"], "items": items})
    return {
        "available": view["available"],
        "updated_at_label": view["updated_at_label"],
        "stale": view["stale"],
        "groups": groups,
        "total": sum(len(group["items"]) for group in groups),
    }


def sprint_assignment(root, subject, selection_id) -> dict | None:
    """Revalidate a staff selection immediately before creating a task."""
    if not isinstance(selection_id, str) or not selection_id or len(selection_id) > 160:
        return None
    matches = [
        item
        for group in load_sprint_catalog(root, subject)["groups"]
        for item in group["items"]
        if item["selection_id"] == selection_id
    ]
    if len(matches) != 1:
        return None
    item = matches[0]
    return {
        "id": item["target_id"],
        "passage": item["passage"],
        "detail": item["label"],
        "category": f"雅思-{'阅读' if subject == 'reading' else '听力'}-7天热榜",
        "planned_minutes": 20 if subject == "reading" else 10,
    }


def sprint_assignment_options(root) -> dict:
    """Adapt the shared catalog to the existing /tasks form's two pickers."""
    listening = load_sprint_catalog(root, "listening")
    reading = load_sprint_catalog(root, "reading")
    return {
        "catalogs": {"listening": listening, "reading": reading},
        "listening": [
            {
                "id": f"sprint:{item['target_id']}",
                "target_id": item["target_id"],
                "title": item["label"],
                "resource_type": "jijing",
                "catalog_source": "exam_sprint",
                "question_count": item["question_count"],
            }
            for group in listening["groups"]
            for item in group["items"]
        ],
        "reading": [
            {
                "id": item["selection_id"],
                "target_id": item["target_id"],
                "title": item["label"],
                "source_label": "7天热榜",
                "passage_count": 1,
                "question_count": item["question_count"],
            }
            for group in reading["groups"]
            for item in group["items"]
        ],
        "reading_passages": {
            item["selection_id"]: [
                {"number": item["passage"], "label": f"热榜 P{item['part']} · 本篇"}
            ]
            for group in reading["groups"]
            for item in group["items"]
        },
    }
