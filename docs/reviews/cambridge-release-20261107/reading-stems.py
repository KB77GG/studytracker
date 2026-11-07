#!/usr/bin/env python3
"""Reproduce the Cambridge 4–21 reading stem audit from the local source export.

Default is read-only except the JSON report. --apply-headings persists only the
explicit source heading targets in the editorial manifest and static payloads.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts import build_reading_test_practice as builder  # noqa: E402

BASE = "40cd8225db1b0a5da188b1dd99d4521dc5853328"
DISPLAY_FIELDS = (
    "title",
    "question_title",
    "desc",
    "table",
    "collect",
    "collect_option",
    "img_url",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--apply-headings", action="store_true")
    args = parser.parse_args()
    raw = json.loads(args.raw.read_text())
    manifest_path = ROOT / "data/cambridge_content_corrections/reading.json"
    manifest = json.loads(manifest_path.read_text())
    report = {
        "baseline": BASE,
        "raw_sha256": hashlib.sha256(args.raw.read_bytes()).hexdigest(),
        "coverage": {"tests": 0, "passages": 0, "groups": 0, "questions": 0},
        "headings": [],
        "structural_errors": [],
        "raw_display_differences": [],
        "paired_blanks": [],
        "word_limit_candidates": [],
        "omitted_passage_context": [],
        "boundary": "Structure and source-field comparison cover the full bank; candidate review is not a semantic certification of all 2880 questions.",
    }
    baseline_heading_counts = collections.Counter()
    for path in sorted((ROOT / "static/reading_tests").glob("ielts*_test*_reading.json")):
        payload = json.loads(path.read_text())
        baseline = json.loads(
            subprocess.check_output(["git", "show", f"{BASE}:{path.relative_to(ROOT)}"], cwd=ROOT)
        )
        baseline_questions = {
            q["number"]: q
            for p in baseline["passages"]
            for g in p["groups"]
            for q in g["questions"]
        }
        all_questions = [
            q for p in payload["passages"] for g in p["groups"] for q in g["questions"]
        ]
        report["coverage"]["tests"] += 1
        if sorted(q["number"] for q in all_questions) != list(range(1, 41)):
            report["structural_errors"].append({"test": path.stem, "kind": "question_numbers"})
        if len({q["id"] for q in all_questions}) != 40:
            report["structural_errors"].append(
                {"test": path.stem, "kind": "duplicate_question_ids"}
            )
        for passage in payload["passages"]:
            report["coverage"]["passages"] += 1
            raw_part = builder.unwrap_part(raw["parts"], "academic", passage["part_id"])
            assert raw_part, passage["id"]
            content = raw_part["content"]
            source_groups = {str(g["group_id"]): g for g in raw_part["question"]}
            for field in ("sub_title", "notes", "paragraph_img", "image", "paragraph_title"):
                if content.get(field):
                    report["omitted_passage_context"].append(
                        {
                            "test": path.stem,
                            "passage": passage["passage"],
                            "field": field,
                            "source": content[field],
                            "restored_by_release": field == "paragraph_img"
                            and bool(passage["content"].get("images")),
                        }
                    )
            for group in passage["groups"]:
                report["coverage"]["groups"] += 1
                report["coverage"]["questions"] += len(group["questions"])
                source_group = source_groups[str(group["group_id"])]
                source_questions = {str(q["id"]): q for q in source_group["list"]}
                ref = {"test": path.stem, "passage": passage["passage"], "group": group["group_id"]}
                with patch.object(builder, "localize_image", return_value=""):
                    generated = builder.build_group(
                        source_group, passage["id"], content.get("paragraph_title")
                    )
                for field in DISPLAY_FIELDS:
                    if group.get(field) != generated.get(field):
                        reviewed = (
                            manifest["tests"]
                            .get(path.stem, {})
                            .get("groups", {})
                            .get(str(group["group_id"]), {})
                        )
                        report["raw_display_differences"].append(
                            {
                                **ref,
                                "field": field,
                                "reviewed": reviewed.get(field) == group.get(field),
                            }
                        )
                holders = re.findall(
                    r"\$([^$\s]+)\$",
                    (group.get("collect") or "") + json.dumps(group.get("table") or ""),
                )
                holder_counts = collections.Counter(holders)
                ids = {str(q["id"]) for q in group["questions"]}
                unknown = sorted(set(holders) - ids)
                missing = sorted(ids - set(holders)) if holders else []
                if unknown or missing:
                    report["structural_errors"].append(
                        {**ref, "kind": "placeholder_map", "unknown": unknown, "missing": missing}
                    )
                if group.get("img_local") and not (ROOT / "static" / group["img_local"]).is_file():
                    report["structural_errors"].append(
                        {**ref, "kind": "missing_question_image", "path": group["img_local"]}
                    )
                for index, question in enumerate(group["questions"]):
                    source_question = source_questions[str(question["id"])]
                    if question["number"] != source_question["number"]:
                        report["structural_errors"].append(
                            {**ref, "kind": "source_number_mismatch", "number": question["number"]}
                        )
                    if str(group["type"]) == "6":
                        target = builder.clean_text(source_question.get("sub_essay_code"))
                        assert re.fullmatch("[A-Z]", target), (ref, question)
                        assert target in {p["label"] for p in passage["content"]["paragraphs"]}
                        title = generated["questions"][index]["title"]
                        before = baseline_questions[question["number"]]["title"]
                        if not before and re.search(
                            r"heading\s+for\s+each\s+(?:paragraph|section)",
                            " ".join(group.get(k, "") for k in ("desc", "question_title", "title")),
                            re.I,
                        ):
                            before = f"Paragraph {chr(65 + index)}"
                        old_target = re.search(r"(?:Paragraph|Section) ([A-Z])", before)
                        status = (
                            "correct"
                            if old_target and old_target[1] == target
                            else "wrong_paragraph" if old_target else "blank_prompt"
                        )
                        baseline_heading_counts[status] += 1
                        report["headings"].append(
                            {
                                **ref,
                                "number": question["number"],
                                "source_code": target,
                                "title": title,
                                "baseline_status": status,
                            }
                        )
                        if args.apply_headings:
                            manifest["tests"].setdefault(path.stem, {}).setdefault(
                                "questions", {}
                            ).setdefault(str(question["number"]), {})["title"] = title
                    if holder_counts[str(question["id"])] > 1:
                        report["paired_blanks"].append(
                            {
                                **ref,
                                "number": question["number"],
                                "id": question["id"],
                                "occurrences": holder_counts[str(question["id"])],
                                "answer": question["answer"],
                            }
                        )
                    limit = re.search(
                        r"(?:NO MORE THAN |ONLY )?(ONE|TWO|THREE|FOUR) WORD", group["desc"], re.I
                    )
                    if limit:
                        max_words = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4}[limit[1].upper()]
                        variants = re.split(r"\s*/\s*|\s+or\s+", question["answer"], flags=re.I)
                        if all(len(v.split()) > max_words for v in variants):
                            report["word_limit_candidates"].append(
                                {
                                    **ref,
                                    "number": question["number"],
                                    "limit": max_words,
                                    "answer": question["answer"],
                                    "numeric_allowance": bool(
                                        re.search(r"A NUMBER", group["desc"])
                                    ),
                                    "paired": holder_counts[str(question["id"])] > 1,
                                }
                            )
    report["heading_baseline_counts"] = dict(baseline_heading_counts)
    report["omitted_context_counts"] = dict(
        collections.Counter(r["field"] for r in report["omitted_passage_context"])
    )
    if args.apply_headings:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        from services.cambridge_content_corrections import apply_content_corrections

        for test_id in manifest["tests"]:
            path = ROOT / "static/reading_tests" / f"{test_id}.json"
            payload = json.loads(path.read_text())
            corrected = apply_content_corrections(payload, "reading")
            path.write_text(json.dumps(corrected, ensure_ascii=False, indent=2))
    Path(__file__).with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "coverage": report["coverage"],
                "heading_baseline_counts": report["heading_baseline_counts"],
                "structural_errors": len(report["structural_errors"]),
                "source_display_differences": len(report["raw_display_differences"]),
                "unreviewed_source_display_differences": sum(
                    not row["reviewed"] for row in report["raw_display_differences"]
                ),
                "paired_blanks": report["paired_blanks"],
                "word_limit_candidates": report["word_limit_candidates"],
                "omitted_context_counts": report["omitted_context_counts"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
