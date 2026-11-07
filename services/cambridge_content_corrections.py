"""Reviewed Cambridge errata shared by importers and read-only review copies.

The allowlist deliberately excludes answers, scores and question identities.
Callers displaying frozen tasks must copy first, then redact before returning
any pre-submission payload. The persisted snapshot and its hash stay intact.
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_QUESTION_FIELDS = frozenset(
    {
        "analysis",
        "central_sentences",
        "locating_words",
        "title",
        "start",
        "end",
        "answer_sentences",
    }
)
_SUBJECT_KEYS = {"listening": "sections", "reading": "passages"}


@lru_cache(maxsize=2)
def _load_corrections(subject: str) -> dict:
    if subject not in _SUBJECT_KEYS:
        raise ValueError(f"Unsupported Cambridge subject: {subject}")
    path = _ROOT / "data" / "cambridge_content_corrections" / f"{subject}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    tests = data["tests"]
    suffix = "_reading" if subject == "reading" else ""
    for test_id, correction in tests.items():
        if not re.fullmatch(r"ielts\d+_test\d+" + suffix, test_id):
            raise ValueError(f"Invalid Cambridge test id: {test_id}")
        for number, patch in correction.get("questions", {}).items():
            if not number.isdigit() or not 1 <= int(number) <= 40:
                raise ValueError(f"Invalid source question number: {test_id}/{number}")
            if not isinstance(patch, dict) or set(patch) - _QUESTION_FIELDS:
                raise ValueError(f"Non-editorial correction: {test_id}/{number}")
        for group_id, patch in correction.get("groups", {}).items():
            if not group_id.isdigit() or not isinstance(patch, dict):
                raise ValueError(f"Invalid group correction: {test_id}/{group_id}")
            if set(patch) != {"desc"} or not isinstance(patch["desc"], str):
                raise ValueError(f"Invalid group instruction: {test_id}/{group_id}")
        for number, patch in correction.get("passages", {}).items():
            if subject != "reading" or number not in {"1", "2", "3"}:
                raise ValueError(f"Invalid passage correction: {test_id}/{number}")
            if not isinstance(patch, dict) or not patch or set(patch) - {"introduction", "images"}:
                raise ValueError(f"Invalid passage correction: {test_id}/{number}")
            if "introduction" in patch and not isinstance(patch["introduction"], str):
                raise ValueError(f"Invalid passage introduction: {test_id}/{number}")
            if "images" in patch:
                images = patch["images"]
                if not isinstance(images, list) or not images:
                    raise ValueError(f"Invalid passage images: {test_id}/{number}")
                for image in images:
                    if not isinstance(image, dict) or set(image) != {
                        "url",
                        "alt",
                        "after_paragraph",
                    }:
                        raise ValueError(f"Invalid passage image: {test_id}/{number}")
                    if (
                        not isinstance(image["url"], str)
                        or not re.fullmatch(r"reading_tests/images/[A-Za-z0-9_.-]+", image["url"])
                        or not isinstance(image["alt"], str)
                        or type(image["after_paragraph"]) is not int
                        or not 0 <= image["after_paragraph"] <= 25
                    ):
                        raise ValueError(f"Invalid passage image asset: {test_id}/{number}")
    return tests


def _restore_introduction(unit: dict, correction: dict) -> None:
    passage = str(unit.get("passage") or "")
    passage_patch = correction.get("passages", {}).get(passage, {})
    if "images" in passage_patch:
        unit.setdefault("content", {})["images"] = copy.deepcopy(passage_patch["images"])
    introduction = passage_patch.get("introduction")
    if not introduction:
        return
    content = unit.setdefault("content", {})
    paragraphs = content.get("paragraphs") or []
    content["paragraphs"] = [{"label": "pre-A", "text": introduction}] + [
        row for row in paragraphs if row.get("label") != "pre-A"
    ]


def apply_content_corrections(payload: dict, subject: str) -> dict:
    """Apply vetted editorial fields in place, using original ids for snapshots.

    Regular tests use payload.id/question.number; specialty tasks retain
    source_test_id/source_number even when displayed ids and numbers change.
    Unknown tests and unrelated banks are unchanged. No live source fetches.
    """
    tests = _load_corrections(subject)
    for unit in payload.get(_SUBJECT_KEYS[subject]) or []:
        test_id = unit.get("source_test_id") or payload.get("id")
        correction = tests.get(test_id, {})
        if subject == "reading":
            _restore_introduction(unit, correction)
        for group in unit.get("groups") or []:
            source_meta = group.get("source_meta") or {}
            group_test = source_meta.get("test_id") or test_id
            group_correction = tests.get(group_test, {})
            group_id = source_meta.get("group_id") or group.get("group_id")
            group_patch = group_correction.get("groups", {}).get(str(group_id))
            if group_patch:
                group.update(copy.deepcopy(group_patch))
            patches = group_correction.get("questions", {})
            for question in group.get("questions") or []:
                number = question.get("source_number", question.get("number"))
                patch = patches.get(str(number))
                if patch:
                    question.update(copy.deepcopy(patch))
    return payload
