"""Build a complete versioned week before the active snapshot is replaced."""

from __future__ import annotations

import json
from pathlib import Path

from services.exam_sprint import (
    _load_snapshot,
    _local_target,
    content_digest,
    load_mappings,
    prepare_snapshot,
    state_directory,
    validate_snapshot,
)
from services.exam_sprint_store import save_converted_documents
from services.ninefen_assets import cache_unit_media
from services.ninefen_content import convert_ninefen_unit


class IncompleteSprintError(ValueError):
    """At least one ranked exercise lacks a complete validated import."""


def ranked_rows(feed):
    for subject, groups in feed["subjects"].items():
        for group in groups:
            for row in group["items"]:
                yield subject, row


def saved_answer_key(root, unit_id, digest):
    state = state_directory(root)
    for path in (
        state / "private" / "answers" / f"{unit_id}.json",
        state / "answers" / f"{unit_id}.json",
        Path(root) / "data" / "exam_sprint" / "answers" / f"{unit_id}.json",
    ):
        if not path.is_file() or path.is_symlink():
            continue
        payload = json.loads(path.read_text())
        if payload.get("source_content_sha256") != digest:
            continue
        if payload.get("unit_id", payload.get("source_id")) != unit_id:
            raise IncompleteSprintError("Saved answer key belongs to another unit")
        if isinstance(payload.get("answers_by_question_id"), dict):
            return payload["answers_by_question_id"]
        answers = payload.get("answers")
        if isinstance(answers, list):
            result = {row["question_id"]: row["answer"] for row in answers}
            if len(result) != len(answers):
                raise IncompleteSprintError("Saved answer key has duplicate questions")
            return result
    return None


def existing_imports(root):
    previous = _load_snapshot(Path(root))
    if not previous:
        return {}
    return {
        (subject, row["source_id"]): row["mapping"]
        for subject, row in ranked_rows(previous)
        if row.get("mapping", {}).get("target_kind") == "ninefen"
    }


def _media(root, exam):
    state = state_directory(root)
    return cache_unit_media(exam, state / "assets", state / "media")[0]


def prepare_complete_snapshot(root, feed, exams, *, answer_provider=None, progress=None):
    """Only return a candidate if every source-open ranked item is playable.

    A provider may collect official answers under explicit authorization. The
    publication service itself never reads credentials or submits source attempts.
    """
    root = Path(root)
    validate_snapshot({**feed, "schema_version": 1})
    manual = load_mappings(root)
    previous = existing_imports(root)
    imported = {}
    for index, (subject, row) in enumerate(ranked_rows(feed), 1):
        if row.get("source_available") is not True or row.get("entry_mode") != "exam":
            continue
        unit, key = row["source_id"], (subject, row["source_id"])
        exam = exams[unit]
        if exam["data"]["channel"] != subject:
            raise IncompleteSprintError("Source subject differs from ranking")
        digest = content_digest(exam)
        old = next(
            (
                candidate
                for candidate in (previous.get(key), manual.get(key))
                if candidate
                and candidate.get("source_content_sha256") == digest
                and candidate.get("source_title") == row["title"]
                and candidate.get("source_part_id", row["source_part_id"]) == row["source_part_id"]
                and _local_target(root, candidate)
            ),
            None,
        )
        if old:
            if old.get("target_kind") == "ninefen":
                imported[key] = old
            if progress:
                progress(index, unit, "reused")
            continue
        answers = saved_answer_key(root, unit, digest)
        if answers is None and answer_provider:
            answer_provider(unit, exam)
            answers = saved_answer_key(root, unit, digest)
        if answers is None:
            raise IncompleteSprintError(f"Official answers unavailable for unit {unit}")
        media = _media(root, exam)
        converted = convert_ninefen_unit(
            exam,
            answers_by_question_id=answers,
            media_map=media["media_map"],
            expected_source_sha256=digest,
        )
        mappings = save_converted_documents(root, converted)
        candidates = [m for m in mappings if m.get("source_part_id") == row["source_part_id"]]
        if len(candidates) != 1:
            raise IncompleteSprintError("Ranked source part has no unique practice document")
        mapping = candidates[0]
        mapping["assets"] = [
            {key: asset[key] for key in ("filename", "sha256", "byte_count")}
            for asset in media["assets"]
        ]
        imported[key] = mapping
        if progress:
            progress(index, unit, "imported")
    snapshot = prepare_snapshot(root, feed, exams.__getitem__, imported_mappings=imported)
    incomplete = [
        row["source_id"]
        for _, row in ranked_rows(snapshot)
        if row.get("source_available") is True
        and row.get("entry_mode") == "exam"
        and row.get("unavailable_reason")
    ]
    if incomplete:
        raise IncompleteSprintError(f"Incomplete practices: {len(incomplete)}")
    return snapshot
