"""Immutable, versioned practice documents; no database or network access.

Content and integrity receipts are published without replacement. The active
weekly mapping may move forward while an older student's exercise ID stays valid.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from werkzeug.utils import secure_filename

VERSIONED_ID = re.compile(r"ninefen_([0-9]{1,30})_([0-9a-f]{12})(?:_p([1-4]))?\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_ID = re.compile(r"[0-9]{1,30}\Z")
SUBJECTS = {"reading", "listening"}


class SprintStoreError(ValueError):
    """The candidate is inconsistent or would replace an immutable document."""


def _sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _source_id(value):
    return isinstance(value, str) and SOURCE_ID.fullmatch(value) is not None


def _json_bytes(payload):
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def content_directory(root: str | Path) -> Path:
    # Lazy import allows the weekly-list service to use this store as well.
    from services.exam_sprint import state_directory

    return state_directory(root) / "content"


def _document_path(root, subject, target_id):
    if subject not in SUBJECTS or not isinstance(target_id, str):
        raise SprintStoreError("Invalid practice subject or ID")
    match = VERSIONED_ID.fullmatch(target_id)
    if not match or (subject == "listening") != bool(match.group(3)):
        raise SprintStoreError("Invalid versioned practice ID")
    base = content_directory(root)
    folder = base / subject
    path = folder / f"{target_id}.json"
    receipt = path.with_suffix(".meta.json")
    # The configured state root is trusted; children may never redirect reads.
    if any(p.is_symlink() for p in (base, folder, path, receipt)):
        raise SprintStoreError("Symlink practice content is not permitted")
    if folder.resolve().parent != base.resolve():
        raise SprintStoreError("Practice path escapes content directory")
    return path


def _validate_payload(subject, target_id, payload):
    match = VERSIONED_ID.fullmatch(target_id)
    if (
        not isinstance(payload, dict)
        or not match
        or payload.get("id") != target_id
        or payload.get("source") != "ninefen"
        or payload.get("source_id") != match.group(1)
        or not _sha(payload.get("source_content_sha256"))
        or payload["source_content_sha256"][:12] != match.group(2)
        or not isinstance(payload.get("source_version_title"), str)
        or not payload["source_version_title"].strip()
    ):
        raise SprintStoreError("Practice source ID or version is inconsistent")
    if subject == "reading":
        parts = payload.get("passages")
        if not isinstance(parts, list) or not 1 <= len(parts) <= 3:
            raise SprintStoreError("Reading document has no valid passages")
        if [p.get("passage") for p in parts if isinstance(p, dict)] != list(
            range(1, len(parts) + 1)
        ):
            raise SprintStoreError("Reading passage order is inconsistent")
    else:
        parts = [payload]
        if payload.get("part_number") != int(match.group(3)):
            raise SprintStoreError("Listening part number is inconsistent")
    seen, numbers = set(), set()
    for part in parts:
        part_id = part.get("source_part_id")
        number = part.get("source_part_number")
        if (
            not _source_id(part_id)
            or part_id in seen
            or type(number) is not int
            or not 1 <= number <= (3 if subject == "reading" else 4)
            or number in numbers
            or any(
                part.get(key) != payload[key]
                for key in ("source", "source_id", "source_content_sha256")
            )
        ):
            raise SprintStoreError("Practice source part is inconsistent")
        seen.add(part_id)
        numbers.add(number)
        if subject == "reading" and (
            part.get("id") != f"{target_id}_p{number}" or part.get("part_id") != part_id
        ):
            raise SprintStoreError("Reading source passage identity is inconsistent")
        if subject == "listening" and number != int(match.group(3)):
            raise SprintStoreError("Listening source part number is inconsistent")
        if subject == "listening" and part.get("paper_id") != part_id:
            raise SprintStoreError("Listening source part identity is inconsistent")


def _receipt(subject, target_id, payload, raw):
    return {
        "schema_version": 1,
        "subject": subject,
        "target_id": target_id,
        "target_sha256": hashlib.sha256(raw).hexdigest(),
        "source": "ninefen",
        "source_id": payload["source_id"],
        "source_content_sha256": payload["source_content_sha256"],
    }


def _immutable_bytes(path, raw):
    """Atomically create, or reuse identical bytes; never replace an old version."""
    if path.is_symlink():
        raise SprintStoreError("Symlink practice content is not permitted")
    if path.exists():
        if path.read_bytes() != raw:
            raise SprintStoreError("Immutable practice document already has different content")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != raw:
                raise SprintStoreError("Concurrent immutable practice content conflict") from None
    finally:
        os.unlink(temporary)


def save_converted_documents(root: str | Path, converted: dict) -> list[dict]:
    """Save converter output and return metadata for explicit reviewed mappings.

    No active mapping is published here. Callers publish it only after every
    document and asset is available. A failed batch may leave unreferenced files.
    """
    if not isinstance(converted, dict):
        raise SprintStoreError("Invalid conversion")
    subject = converted.get("subject")
    documents = converted.get("documents")
    if not isinstance(documents, list) or not documents:
        raise SprintStoreError("Conversion has no documents")
    candidates, seen = [], set()
    for document in documents:
        if not isinstance(document, dict):
            raise SprintStoreError("Invalid converted document")
        target_id, payload = document.get("id"), document.get("payload")
        path = _document_path(root, subject, target_id)
        _validate_payload(subject, target_id, payload)
        relative_path = f"{subject}/{target_id}.json"
        if (
            target_id in seen
            or document.get("relative_path") != relative_path
            or any(
                converted.get(key) != payload[key]
                for key in ("source", "source_id", "source_content_sha256")
            )
        ):
            raise SprintStoreError("Converted document metadata is inconsistent")
        seen.add(target_id)
        raw = _json_bytes(payload)
        receipt = _receipt(subject, target_id, payload, raw)
        parts = payload["passages"] if subject == "reading" else [payload]
        part = parts[0] if len(parts) == 1 else {}
        result = {
            **receipt,
            "target_kind": "ninefen",
            "source_title": payload["source_version_title"],
            "source_part_id": part.get("source_part_id"),
            "part_number": part.get("source_part_number"),
            "passage": part.get("passage") if subject == "reading" else None,
            "relative_path": relative_path,
            "passages": (
                [
                    {key: p[key] for key in ("passage", "source_part_id", "source_part_number")}
                    for p in parts
                ]
                if subject == "reading"
                else []
            ),
        }
        candidates.append((path, raw, receipt, result))
    for path, raw, receipt, _result in candidates:
        _immutable_bytes(path, raw)
        _immutable_bytes(path.with_suffix(".meta.json"), _json_bytes(receipt))
    return [result for _path, _raw, _receipt_data, result in candidates]


def _load_document(
    root, subject, target_id, *, expected_sha256=None, source_id=None, source_content_sha256=None
):
    path = _document_path(root, subject, target_id)
    raw = path.read_bytes()
    payload = json.loads(raw)
    _validate_payload(subject, target_id, payload)
    receipt = json.loads(path.with_suffix(".meta.json").read_bytes())
    if receipt != _receipt(subject, target_id, payload, raw):
        raise SprintStoreError("Practice content integrity check failed")
    for expected, actual in (
        (expected_sha256, receipt["target_sha256"]),
        (source_id, payload["source_id"]),
        (source_content_sha256, payload["source_content_sha256"]),
    ):
        if expected is not None and expected != actual:
            raise SprintStoreError("Practice mapping does not match stored content")
    return payload, path


def load_ninefen_document(
    root, subject, target_id, *, expected_sha256=None, source_id=None, source_content_sha256=None
) -> dict | None:
    """Read a versioned document only if its identity and integrity receipt match."""
    try:
        return _load_document(
            root,
            subject,
            target_id,
            expected_sha256=expected_sha256,
            source_id=source_id,
            source_content_sha256=source_content_sha256,
        )[0]
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return None


def resolve_ninefen_document_path(root, subject, target_id) -> Path | None:
    """Return an integrity-checked path for existing legacy render/grade handlers."""
    try:
        return _load_document(root, subject, target_id)[1]
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return None


def load_mapping_target(root, mapping) -> tuple[dict, Path] | None:
    """Check every reviewed identity field before enabling a weekly practice link."""
    if not isinstance(mapping, dict) or mapping.get("target_kind") != "ninefen":
        return None
    if not _source_id(mapping.get("source_id")) or not _source_id(mapping.get("source_part_id")):
        return None
    if not all(_sha(mapping.get(k)) for k in ("target_sha256", "source_content_sha256")):
        return None
    try:
        subject = mapping.get("subject")
        payload, path = _load_document(
            root,
            subject,
            mapping.get("target_id"),
            expected_sha256=mapping["target_sha256"],
            source_id=mapping["source_id"],
            source_content_sha256=mapping["source_content_sha256"],
        )
        if mapping.get("source_title") != payload["source_version_title"]:
            return None
        if subject == "reading":
            number = mapping.get("passage")
            if type(number) is not int or not 1 <= number <= len(payload["passages"]):
                return None
            part = payload["passages"][number - 1]
        else:
            part = payload
        if mapping.get("source_part_id") != part["source_part_id"]:
            return None
        if any(
            key in mapping and mapping[key] != part["source_part_number"]
            for key in ("part_number", "source_part_number")
        ):
            return None
        return payload, path
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        return None


def resolve_listening_part_path(root, legacy_root, part_id) -> Path | None:
    """Preserve legacy filenames while requiring exact IDs for imported content."""
    if not isinstance(part_id, str):
        return None
    if part_id.startswith("ninefen_") or secure_filename(part_id).startswith("ninefen_"):
        return resolve_ninefen_document_path(root, "listening", part_id)
    return Path(legacy_root) / "parts" / f"{secure_filename(part_id)}.json"
