#!/usr/bin/env python3
"""Restore six reviewed instructions and four original, byte-preserved figures."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.build_reading_test_practice import localize_image, unwrap_part  # noqa: E402

INSTRUCTIONS = [
    ("ielts14_test2_reading", 153, [("Reading Passage 1", "Reading Passage 3")]),
    ("ielts9_test4_reading", 331, [("Reading Passage 2", "Reading Passage 1")]),
    ("ielts12_test5_reading", 204, [("Reading Passage 3", "Reading Passage 1")]),
    ("ielts13_test2_reading", 181, [("Reading Passage 3", "Reading Passage 1")]),
    ("ielts5_test3_reading", 464, [("Reading Passage 1", "Reading Passage 3")]),
    ("ielts10_test3_reading", 285, [("paragraphs S -E", "paragraphs B-E"), ("i-v ii", "i-viii")]),
]
FIGURES = [
    (
        "ielts4_test1_reading",
        3,
        0,
        "Figure 1. A line of motion within a circle.",
        "b127cd430e07ace8bcde8af97f478b2b225c64c94649af02e2fac86c365bdeee",
    ),
    (
        "ielts4_test1_reading",
        3,
        1,
        "Figure 2. Word-pair associations with circles and squares and agreement percentages.",
        "703003baafe78a850caecf10ce3c48567bd82eee317fe93ab5e4b174819c289c",
    ),
    (
        "ielts7_test4_reading",
        3,
        0,
        "Table 1. Proofreading errors under predictable and unpredictable noise.",
        "730424b44d7e625a10f2d9bce6774f4d9b2aa878b1f8287aa88b6658841c019c",
    ),
    (
        "ielts10_test3_reading",
        3,
        0,
        "Map of Pacific islands discussed in the passage.",
        "2f5474337470470fbe03f16a3d14bb7d521d22d5280cc59ab0d34de04e7bb10c",
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.raw.read_text())
    manifest_path = ROOT / "data/cambridge_content_corrections/reading.json"
    manifest = json.loads(manifest_path.read_text())
    figures_by_passage = {}
    evidence = {"instructions": [], "figures": []}
    for test_id, group_id, replacements in INSTRUCTIONS:
        payload = json.loads((ROOT / "static/reading_tests" / f"{test_id}.json").read_text())
        group = next(
            g for p in payload["passages"] for g in p["groups"] if g["group_id"] == group_id
        )
        desc = group["desc"]
        for old, new in replacements:
            assert old in desc or new in desc, (test_id, group_id, old)
            desc = desc.replace(old, new)
        manifest["tests"].setdefault(test_id, {}).setdefault("groups", {})[str(group_id)] = {
            "desc": desc
        }
        evidence["instructions"].append(
            {"test": test_id, "group_id": group_id, "replacements": replacements}
        )
    for test_id, passage_no, image_index, alt, expected_hash in FIGURES:
        payload = json.loads((ROOT / "static/reading_tests" / f"{test_id}.json").read_text())
        passage = next(p for p in payload["passages"] if p["passage"] == passage_no)
        part = unwrap_part(raw["parts"], "academic", passage["part_id"])
        source_image = part["content"]["paragraph_img"][image_index]
        localized = localize_image(source_image["img_url"], passage["id"])
        path = ROOT / "static" / localized
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected_hash, (test_id, path)
        image = {"url": localized, "alt": alt, "after_paragraph": source_image["paragraph"]}
        figures_by_passage.setdefault((test_id, passage_no), []).append(image)
        evidence["figures"].append(
            {
                "test": test_id,
                "passage": passage_no,
                "source_url": source_image["img_url"],
                **image,
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
        )
    for (test_id, passage_no), images in figures_by_passage.items():
        manifest["tests"].setdefault(test_id, {}).setdefault("passages", {}).setdefault(
            str(passage_no), {}
        )["images"] = images
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    from services.cambridge_content_corrections import apply_content_corrections

    for test_id in manifest["tests"]:
        path = ROOT / "static/reading_tests" / f"{test_id}.json"
        payload = json.loads(path.read_text())
        apply_content_corrections(payload, "reading")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    Path(__file__).with_suffix(".json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "instruction_groups": len(INSTRUCTIONS),
                "figures": len(FIGURES),
                "figure_passages": len(figures_by_passage),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
