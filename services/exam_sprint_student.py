"""Read immutable sprint assignments for existing student clients.

The current ranking is deliberately not consulted: a previously assigned version
must keep working after the next weekly update. No answers are serialized here.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

from services.exam_sprint import _valid_import_assets, state_directory
from services.exam_sprint_store import VERSIONED_ID, load_ninefen_document

IMAGE_PATH = re.compile(r"/practice/sprint/assets/([a-f0-9]{64}\.(?:png|jpg|jpeg|webp|gif))\Z")


def sprint_reading_image_url(root, value) -> str:
    """Expose only a verified, immutable image on our own asset route."""
    match = IMAGE_PATH.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        return ""
    filename = match.group(1)
    assets = state_directory(root) / "assets"
    path = assets / filename
    try:
        if assets.is_symlink() or path.is_symlink() or not path.is_file():
            return ""
        manifest = [
            {
                "filename": filename,
                "sha256": filename.split(".", 1)[0],
                "byte_count": path.stat().st_size,
            }
        ]
        if not _valid_import_assets(root, {"img_url": value}, manifest):
            return ""
    except (OSError, ValueError, TypeError, AttributeError):
        return ""
    return f"https://studytracker.xin{value}"


def load_student_ninefen_reading(root, test_id) -> dict | None:
    """Verify the stored version and every diagram before offering the exercise."""
    payload = load_ninefen_document(root, "reading", test_id)
    if payload is None:
        return None
    try:
        for passage in payload["passages"]:
            groups = passage.get("groups")
            if not isinstance(groups, list) or not groups:
                return None
            for group in groups:
                if not isinstance(group, dict) or not isinstance(group.get("questions"), list):
                    return None
                # Native imports use immutable local URLs, never arbitrary static
                # paths or third-party URLs accepted by older Cambridge data.
                if group.get("img_local"):
                    return None
                image = group.get("img_url")
                if image and not sprint_reading_image_url(root, image):
                    return None
    except (KeyError, TypeError, AttributeError):
        return None
    return payload


def ninefen_reading_task_path(root, task) -> str | None:
    """Build an exact task/token/passage URL; leave authorization to its route."""
    test_id = getattr(task, "reading_test_id", None)
    match = VERSIONED_ID.fullmatch(test_id) if isinstance(test_id, str) else None
    task_id = getattr(task, "id", None)
    token = getattr(task, "reading_access_token", None)
    if (
        match is None
        or match.group(3) is not None
        or type(task_id) is not int
        or task_id <= 0
        or not isinstance(token, str)
        or not token.strip()
    ):
        return None
    payload = load_student_ninefen_reading(root, test_id)
    if payload is None:
        return None
    query = {"task_id": task_id, "token": token}
    passage = getattr(task, "reading_passage_number", None)
    if passage is not None:
        if type(passage) is not int or passage not in {
            part["passage"] for part in payload["passages"]
        }:
            return None
        query["passage"] = passage
    return f"/reading/test/{test_id}?{urlencode(query)}"
