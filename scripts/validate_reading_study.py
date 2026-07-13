#!/usr/bin/env python3
"""Validate Reading Study JSON against the complete reading corpus."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = (
    (ROOT / "static" / "reading_tests", "reading_test"),
    (ROOT / "static" / "reading_jijing", "reading_jijing"),
)
DEFAULT_OUTPUT = ROOT / "data" / "reading_study"
TOP_LEVEL_KEYS = {
    "schema_version",
    "generation_standard",
    "source_kind",
    "test_id",
    "passage_id",
    "passage_title",
    "difficulty",
    "sentences",
}
SENTENCE_KEYS = {
    "id",
    "paragraph_label",
    "sentence_index",
    "sentence",
    "translation",
    "structure",
    "difficult_points",
    "expressions",
}


def normalize_space(value: str) -> str:
    return " ".join(str(value or "").split())


def load_source_passages(source_path: Path | None = None) -> dict[str, dict]:
    paths: list[tuple[Path, str]] = []
    if source_path:
        source_kind = (
            "reading_jijing" if source_path.parent.name == "reading_jijing" else "reading_test"
        )
        paths.append((source_path, source_kind))
    else:
        for root, source_kind in SOURCE_ROOTS:
            paths.extend(
                (path, source_kind)
                for path in sorted(root.glob("*.json"))
                if path.name != "catalog.json"
            )

    passages: dict[str, dict] = {}
    for path, source_kind in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for passage in payload.get("passages") or []:
            passage_id = passage.get("id")
            if not passage_id:
                continue
            if passage_id in passages:
                raise ValueError(f"Duplicate source passage id: {passage_id}")
            passages[passage_id] = {
                "passage": passage,
                "source_kind": source_kind,
                "test_id": payload.get("id"),
                "source_path": path,
            }
    return passages


def validate_sample(sample_path: Path, source_passages: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    try:
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"{sample_path.name}: unreadable JSON ({exc})"]
    passage_id = sample.get("passage_id")
    source_meta = source_passages.get(passage_id)
    if not source_meta:
        return [f"{sample_path.name}: unknown passage_id {passage_id!r}"]
    source = source_meta["passage"]
    if set(sample) != TOP_LEVEL_KEYS:
        errors.append(f"{sample_path.name}: top-level keys differ from fixed schema")
    if sample.get("schema_version") != 1:
        errors.append(f"{sample_path.name}: schema_version must be 1")
    if sample.get("generation_standard") != "reading_study_v1":
        errors.append(f"{sample_path.name}: generation_standard must be reading_study_v1")
    if sample.get("source_kind") != source_meta["source_kind"]:
        errors.append(f"{sample_path.name}: source_kind does not match source corpus")
    if sample.get("test_id") != source_meta["test_id"]:
        errors.append(f"{sample_path.name}: test_id does not match source corpus")
    if sample.get("passage_title") != (source.get("content") or {}).get("title"):
        errors.append(f"{sample_path.name}: passage_title does not match source")

    source_paragraphs = {
        str(row.get("label") or ""): normalize_space(row.get("text"))
        for row in (source.get("content") or {}).get("paragraphs") or []
    }
    sample_paragraphs: dict[str, list[str]] = defaultdict(list)
    seen_ids: set[str] = set()
    sentences = sample.get("sentences")
    if not isinstance(sentences, list) or not sentences:
        return [f"{sample_path.name}: sentences must be a non-empty list"]

    for expected_index, row in enumerate(sentences, start=1):
        prefix = f"{sample_path.name}: sentence {expected_index}"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        if set(row) != SENTENCE_KEYS:
            errors.append(f"{prefix}: keys differ from fixed schema")
        if row.get("sentence_index") != expected_index:
            errors.append(f"{prefix}: sentence_index is not sequential")
        sentence_id = str(row.get("id") or "")
        if not sentence_id or sentence_id in seen_ids:
            errors.append(f"{prefix}: missing or duplicate id")
        seen_ids.add(sentence_id)

        label = str(row.get("paragraph_label") or "")
        sentence = str(row.get("sentence") or "")
        if label not in source_paragraphs:
            errors.append(f"{prefix}: unknown paragraph label {label!r}")
        sample_paragraphs[label].append(sentence)
        if not str(row.get("translation") or "").strip():
            errors.append(f"{prefix}: translation is empty")

        structure = row.get("structure")
        if not isinstance(structure, list) or not structure:
            errors.append(f"{prefix}: structure must be a non-empty list")
        else:
            for part in structure:
                if not isinstance(part, dict) or set(part) != {"text", "role", "level"}:
                    errors.append(f"{prefix}: invalid structure item")
                    continue
                text = normalize_space(part.get("text"))
                if not text or text not in normalize_space(sentence):
                    errors.append(f"{prefix}: structure text is not an exact sentence span")
                if not re.fullmatch(r"[a-z][a-z0-9_]*", str(part.get("role") or "")):
                    errors.append(f"{prefix}: structure role must be snake_case")
                if not isinstance(part.get("level"), int) or part["level"] < 0:
                    errors.append(f"{prefix}: structure level must be a non-negative integer")

        difficult_points = row.get("difficult_points")
        if not isinstance(difficult_points, list) or not 2 <= len(difficult_points) <= 4:
            errors.append(f"{prefix}: difficult_points must contain 2-4 items")
        elif any(not str(item or "").strip() for item in difficult_points):
            errors.append(f"{prefix}: difficult_points contains an empty item")

        expressions = row.get("expressions")
        if not isinstance(expressions, list) or len(expressions) > 4:
            errors.append(f"{prefix}: expressions must contain 0-4 items")
        else:
            for expression in expressions:
                if (
                    not isinstance(expression, dict)
                    or set(expression) != {"text", "meaning_zh"}
                    or not str(expression.get("text") or "").strip()
                    or not str(expression.get("meaning_zh") or "").strip()
                ):
                    errors.append(f"{prefix}: invalid expression item")

    for label, source_text in source_paragraphs.items():
        generated_text = normalize_space(" ".join(sample_paragraphs.get(label, [])))
        if generated_text != source_text:
            errors.append(f"{sample_path.name}: paragraph {label} does not reproduce source text")
    extra_labels = set(sample_paragraphs) - set(source_paragraphs)
    if extra_labels:
        errors.append(f"{sample_path.name}: unexpected paragraph labels {sorted(extra_labels)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--list-missing", type=int, default=0)
    parser.add_argument(
        "--only",
        help="validate a single passage id (skips coverage checks); "
        "pair with --source for a fast per-file check",
    )
    args = parser.parse_args()

    source_passages = load_source_passages(args.source)
    if args.only:
        sample_paths = [args.output_dir / f"{args.only}.json"]
        if not sample_paths[0].exists():
            print(f"ERROR {sample_paths[0].name}: file not found")
            return 1
    else:
        sample_paths = sorted(args.output_dir.glob("*.json"))
    if not sample_paths:
        print(f"No Reading Study files found in {args.output_dir}")
        return 1

    errors: list[str] = []
    ready_ids: set[str] = set()
    for sample_path in sample_paths:
        sample_errors = validate_sample(sample_path, source_passages)
        if sample_errors:
            errors.extend(sample_errors)
        else:
            payload = json.loads(sample_path.read_text(encoding="utf-8"))
            ready_ids.add(payload["passage_id"])
            print(f"OK {sample_path.name}: {len(payload['sentences'])} sentences")
    missing_ids = sorted(set(source_passages) - ready_ids)
    print(
        f"Coverage: {len(ready_ids)}/{len(source_passages)} ready, " f"{len(missing_ids)} missing"
    )
    if args.list_missing:
        for passage_id in missing_ids[: args.list_missing]:
            meta = source_passages[passage_id]
            print(f"MISSING {passage_id} | {meta['source_kind']} | " f"{meta['source_path'].name}")
    if args.require_complete and missing_ids:
        errors.append(f"corpus incomplete: {len(missing_ids)} passages missing")
    if errors:
        print("\n".join(f"ERROR {message}" for message in errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
