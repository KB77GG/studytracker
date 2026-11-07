#!/usr/bin/env python3
"""Verify narrow reading changes and source rebuilds without writing the bank."""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def questions(payload):
    return {
        str(q["number"]): q
        for passage in payload["passages"]
        for group in passage["groups"]
        for q in group["questions"]
    }


def remove_reviewed_fields(payload, correction):
    cleaned = copy.deepcopy(payload)
    for passage in cleaned["passages"]:
        passage_patch = correction.get("passages", {}).get(str(passage["passage"]), {})
        if "introduction" in passage_patch:
            passage["content"]["paragraphs"] = [
                p for p in passage["content"]["paragraphs"] if p["label"] != "pre-A"
            ]
        if "images" in passage_patch:
            passage["content"].pop("images", None)
        for group in passage["groups"]:
            for field in correction.get("groups", {}).get(str(group["group_id"]), {}):
                group.pop(field, None)
            for question in group["questions"]:
                fields = correction.get("questions", {}).get(str(question["number"]), {})
                for field in fields:
                    question.pop(field, None)
    return cleaned


def main():
    from scripts.build_reading_test_practice import build_tests

    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--base", default="40cd8225db1b0a5da188b1dd99d4521dc5853328")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.raw.read_text())
    manifest = json.loads((ROOT / "data/cambridge_content_corrections/reading.json").read_text())
    # Image files are irrelevant to this content-only check; forbid downloads.
    with patch("scripts.build_reading_test_practice.localize_image", return_value=""):
        rebuilt = build_tests(raw, "academic")
    assert len(rebuilt) == 72
    for test_id, correction in manifest["tests"].items():
        payload = rebuilt[test_id]
        question_map = questions(payload)
        for number, fields in correction.get("questions", {}).items():
            for field, value in fields.items():
                assert question_map[number][field] == value, (test_id, number, field)
        for number, content in correction.get("passages", {}).items():
            passage = next(p for p in payload["passages"] if str(p["passage"]) == number)
            if "introduction" in content:
                assert passage["content"]["paragraphs"][0] == {
                    "label": "pre-A",
                    "text": content["introduction"],
                }
            if "images" in content:
                assert passage["content"]["images"] == content["images"]
        for group_id, fields in correction.get("groups", {}).items():
            group = next(
                g
                for p in payload["passages"]
                for g in p["groups"]
                if str(g["group_id"]) == group_id
            )
            for field, value in fields.items():
                assert group[field] == value
    changed = []
    question_count = 0
    for path in sorted((ROOT / "static/reading_tests").glob("ielts*_test*_reading.json")):
        relative = str(path.relative_to(ROOT))
        before = json.loads(
            subprocess.check_output(["git", "show", f"{args.base}:{relative}"], cwd=ROOT, text=True)
        )
        after = json.loads(path.read_text())
        correction = manifest["tests"].get(after["id"], {})
        assert remove_reviewed_fields(before, correction) == remove_reviewed_fields(
            after, correction
        ), relative
        question_count += len(questions(after))
        if before != after:
            changed.append(relative)
    assert {Path(path).stem for path in changed} == set(manifest["tests"])
    assert question_count == 2880
    result = {
        "base": args.base,
        "source_raw_sha256": hashlib.sha256(args.raw.read_bytes()).hexdigest(),
        "in_memory_rebuild_tests": len(rebuilt),
        "rebuilt_corrections_match": True,
        "changed_reading_files": changed,
        "all_2880_scoring_and_unreviewed_fields_unchanged": True,
        "preserved_original_letter_paragraphs": True,
        "notes": "In-memory rebuild only; mocked image localization; no bank writes or network.",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
