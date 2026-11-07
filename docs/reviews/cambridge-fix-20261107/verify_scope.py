#!/usr/bin/env python3
"""Independently bound the Cambridge data change to the reviewed errata.

Reads all 144 tracked Cambridge test JSONs from the fixed Git baseline, applies
the production helper to copies, and compares complete payloads to disk. It also
checks invariants without trusting the helper's own field allowlist.
"""

import argparse
import collections
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
BASE = "40cd8225db1b0a5da188b1dd99d4521dc5853328"

LISTENING_ANALYSIS = {
    "ielts5_test1": (27, 29),
    "ielts6_test1": (34,),
    "ielts6_test4": (17,),
    "ielts7_test1": (21,),
    "ielts7_test2": (37, 39),
    "ielts10_test2": (1, 10),
    "ielts10_test3": (39,),
    "ielts10_test4": (38,),
    "ielts11_test1": (37,),
    "ielts11_test4": (5,),
    "ielts12_test6": (2, 3, 9, 34),
    "ielts12_test7": (34, 35),
    "ielts13_test1": (37,),
    "ielts13_test3": (40,),
    "ielts16_test1": (33,),
    "ielts17_test2": (2,),
    "ielts18_test1": (3, 23, 40),
}
LISTENING_TIMING = {
    "ielts4_test3": (4,),
    "ielts10_test2": (1,),
    "ielts18_test1": (14, 15, 23, 29, 30),
}
READING_QUESTIONS = {
    "ielts4_test3_reading": (5,),
    "ielts7_test4_reading": (34,),
    "ielts12_test5_reading": (29,),
    "ielts14_test1_reading": (34,),
    "ielts9_test2_reading": (31, 32),
}
READING_INTRODUCTIONS = {
    "ielts4_test3_reading": "2",
    "ielts6_test2_reading": "1",
    "ielts6_test3_reading": "2",
    "ielts9_test1_reading": "2",
    "ielts20_test4_reading": "3",
}
# Explicit source paragraph codes, independently transcribed before manifest edits.
HEADING_TARGETS = [
    (4, 3, 14, "ABCD"),
    (4, 4, 28, "ACDE"),
    (5, 3, 14, "BDEF"),
    (5, 4, 1, "ABC"),
    (6, 1, 27, "BCDEFG"),
    (6, 2, 1, "ABCDE"),
    (6, 3, 14, "BCDEF"),
    (6, 4, 1, "ABCDEFG"),
    (6, 4, 27, "ABCD"),
    (7, 1, 14, "ACDEFGH"),
    (7, 2, 27, "BCEF"),
    (7, 3, 14, "ABCDEF"),
    (8, 1, 14, "ACDEFG"),
    (8, 2, 14, "BDEF"),
    (8, 2, 27, "ABCDEF"),
    (8, 3, 27, "BCDEFG"),
    (8, 4, 1, "BCDEF"),
    (9, 1, 14, "BCDE"),
    (9, 4, 27, "BCDE"),
    (10, 1, 14, "ABCDEGHI"),
    (10, 2, 1, "ABCDEFG"),
    (10, 3, 1, "BCDE"),
    (11, 2, 14, "ABCDEFG"),
    (11, 4, 27, "ABCDEF"),
    (12, 5, 27, "ABCDEF"),
    (12, 6, 14, "ABCDEFG"),
    (12, 7, 1, "ABCDEFG"),
    (12, 8, 27, "ABCDEFG"),
    (13, 1, 14, "ABCDEF"),
    (14, 2, 27, "ABCDEFGH"),
    (15, 3, 14, "ABCDEFG"),
    (16, 1, 14, "ABCDEFG"),
    (16, 4, 27, "ABCDEF"),
    (18, 3, 14, "ABCDEFG"),
    (20, 3, 14, "ABCDEF"),
]
LISTENING_NEW_TITLES = {"ielts5_test3": (13, 14, 15), "ielts15_test4": (8,), "ielts6_test2": (40,)}
LISTENING_GROUP_RANGES = {
    "ielts11_test2": {"209": (1, 10), "217": (31, 40)},
    "ielts12_test6": {"184": (1, 10), "189": (31, 40)},
    "ielts13_test2": {"156": (1, 10), "162": (31, 40)},
    "ielts16_test3": {"85": (31, 40)},
    "ielts17_test2": {"43": (8, 10)},
    "ielts18_test3": {"19": (5, 10)},
}
READING_GROUP_REPLACEMENTS = {
    "ielts14_test2_reading": {"153": [("Reading Passage 1", "Reading Passage 3")]},
    "ielts9_test4_reading": {"331": [("Reading Passage 2", "Reading Passage 1")]},
    "ielts12_test5_reading": {"204": [("Reading Passage 3", "Reading Passage 1")]},
    "ielts13_test2_reading": {"181": [("Reading Passage 3", "Reading Passage 1")]},
    "ielts5_test3_reading": {"464": [("Reading Passage 1", "Reading Passage 3")]},
    "ielts10_test3_reading": {"285": [("paragraphs S -E", "paragraphs B-E"), ("i-v ii", "i-viii")]},
}
READING_IMAGES = {
    "ielts4_test1_reading": [
        (
            "ielts4_test1_p3_essay_4_1_3_1.png",
            1,
            "b127cd430e07ace8bcde8af97f478b2b225c64c94649af02e2fac86c365bdeee",
            "Figure 1. A line of motion within a circle.",
        ),
        (
            "ielts4_test1_p3_essay_4_1_3_2.png",
            9,
            "703003baafe78a850caecf10ce3c48567bd82eee317fe93ab5e4b174819c289c",
            "Figure 2. Word-pair associations with circles and squares and agreement percentages.",
        ),
    ],
    "ielts7_test4_reading": [
        (
            "ielts7_test4_p3_essay_7_4_3.png",
            3,
            "730424b44d7e625a10f2d9bce6774f4d9b2aa878b1f8287aa88b6658841c019c",
            "Table 1. Proofreading errors under predictable and unpredictable noise.",
        ),
    ],
    "ielts10_test3_reading": [
        (
            "ielts10_test3_p3_essay_10_3_3.jpg",
            2,
            "2f5474337470470fbe03f16a3d14bb7d521d22d5280cc59ab0d34de04e7bb10c",
            "Map of Pacific islands discussed in the passage.",
        ),
    ],
}
# These four targets alone may change answer/answers; every variant is a whole pair.
ANSWER_PARTS = {
    "ielts4_test1": {"11": (21802, ["coal"], ["firewood"], True)},
    "ielts6_test1": {
        "7": (1578, ["10", "10 am"], ["4.30", "4.30 pm"], False),
        "19": (1590, ["Monday"], ["Thursday"], True),
        "32": (1602, ["metal"], ["leather"], True),
    },
}
QUESTION_EDITORIAL_FIELDS = {
    "analysis",
    "central_sentences",
    "locating_words",
    "title",
    "start",
    "end",
    "answer_sentences",
}


def expected_question_fields(subject):
    result = collections.defaultdict(dict)

    def add(mapping, fields):
        for test_id, numbers in mapping.items():
            for number in numbers:
                result[test_id].setdefault(str(number), set()).update(fields)

    if subject == "listening":
        add(LISTENING_ANALYSIS, {"analysis"})
        add(LISTENING_TIMING, {"start", "end", "answer_sentences"})
        add({"ielts18_test1": (33, 34)}, {"title"})
        add(LISTENING_NEW_TITLES, {"title"})
    else:
        add(READING_QUESTIONS, {"central_sentences"})
        add(
            {
                k: v
                for k, v in READING_QUESTIONS.items()
                if k not in {"ielts14_test1_reading", "ielts9_test2_reading"}
            },
            {"analysis", "locating_words"},
        )
        add({"ielts14_test1_reading": (34,), "ielts9_test2_reading": (32,)}, {"locating_words"})
        for book, test_no, first, codes in HEADING_TARGETS:
            add(
                {f"ielts{book}_test{test_no}_reading": tuple(range(first, first + len(codes)))},
                {"title"},
            )
    return result


def expected_heading_titles():
    result = collections.defaultdict(dict)
    point_names = {"B": "Two", "C": "Three", "D": "Four", "E": "Five", "F": "Six"}
    for book, test_no, first, codes in HEADING_TARGETS:
        for offset, code in enumerate(codes):
            title = f"Paragraph {code}"
            if (book, test_no) == (6, 3):
                title += f" (Key Point {point_names[code]})"
            result[f"ielts{book}_test{test_no}_reading"][str(first + offset)] = title
    assert sum(len(rows) for rows in result.values()) == 200
    return result


def expected_groups(subject):
    return LISTENING_GROUP_RANGES if subject == "listening" else READING_GROUP_REPLACEMENTS


def answer_variants(test_id, number):
    _, first, second, either_order = ANSWER_PARTS[test_id][number]
    pairs = [(a, b) for a in first for b in second]
    if either_order:
        pairs += [(b, a) for a in first for b in second]
    joins = (" and ", " ") if either_order else (" to ", " and ", " ")
    return {a + joiner + b for a, b in pairs for joiner in joins}


def verify_answer_manifest():
    path = ROOT / "data/cambridge_content_corrections/listening_answers.json"
    manifest = json.loads(path.read_text())
    assert set(manifest) == {"tests"} and set(manifest["tests"]) == set(ANSWER_PARTS)
    for test_id, correction in manifest["tests"].items():
        assert set(correction) == {"questions"}
        assert set(correction["questions"]) == set(ANSWER_PARTS[test_id])
        for number, patch in correction["questions"].items():
            assert set(patch) == {"answer"}
            alternatives = [part.strip() for part in patch["answer"].split("/")]
            assert len(alternatives) == len(set(alternatives))
            assert set(alternatives) == answer_variants(test_id, number), (test_id, number)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def all_questions(payload, unit_key):
    return [
        question
        for unit in payload[unit_key]
        for group in unit["groups"]
        for question in group["questions"]
    ]


def labelled_paragraphs(rows):
    return [p for p in rows if re.fullmatch(r"[A-Z]", p["label"])]


def without_reviewed_fields(payload, subject, correction):
    """Independent comparison: all unapproved fields must remain byte-value equal."""
    result = copy.deepcopy(payload)
    unit_key = "sections" if subject == "listening" else "passages"
    for unit in result[unit_key]:
        if subject == "reading":
            patch = correction.get("passages", {}).get(str(unit["passage"]), {})
            if "introduction" in patch:
                unit["content"]["paragraphs"] = [
                    row for row in unit["content"]["paragraphs"] if row["label"] != "pre-A"
                ]
            if "images" in patch:
                unit["content"].pop("images", None)
        for group in unit["groups"]:
            for field in correction.get("groups", {}).get(str(group["group_id"]), {}):
                group.pop(field, None)
            for question in group["questions"]:
                fields = correction.get("questions", {}).get(str(question["number"]), {})
                for field in fields:
                    question.pop(field, None)
                if subject == "listening" and str(question["number"]) in ANSWER_PARTS.get(
                    payload["id"], {}
                ):
                    question.pop("answer", None)
                    question.pop("answers", None)
    return result


def verify_manifest(subject, manifest):
    expected = expected_question_fields(subject)
    expected_tests = set(expected)
    expected_tests.update(expected_groups(subject))
    if subject == "reading":
        expected_tests.update(READING_INTRODUCTIONS)
        expected_tests.update(READING_IMAGES)
    assert set(manifest) == {"tests"}
    assert set(manifest["tests"]) == expected_tests, (subject, "test scope changed")
    for test_id, correction in manifest["tests"].items():
        assert set(correction) <= {"questions", "groups", "passages"}
        fields = correction.get("questions", {})
        assert set(fields) == set(expected.get(test_id, {})), (test_id, "question scope changed")
        for number, patch in fields.items():
            assert set(patch) == expected[test_id][number], (test_id, number, "field scope changed")
            assert set(patch) <= QUESTION_EDITORIAL_FIELDS
            heading = expected_heading_titles().get(test_id, {}).get(number)
            if heading:
                assert patch["title"] == heading, (test_id, number, "heading target changed")
        groups = correction.get("groups", {})
        assert set(groups) == set(expected_groups(subject).get(test_id, {}))
        assert all(set(patch) == {"desc"} for patch in groups.values())
        passages = correction.get("passages", {})
        intro_number = READING_INTRODUCTIONS.get(test_id) if subject == "reading" else None
        expected_passages = {intro_number} if intro_number else set()
        if subject == "reading" and test_id in READING_IMAGES:
            expected_passages.add("3")
        assert set(passages) == expected_passages, (
            test_id,
            "passage scope changed",
        )
        for number, patch in passages.items():
            fields = {"introduction"} if number == intro_number else set()
            if test_id in READING_IMAGES and number == "3":
                fields.add("images")
                expected_images = [
                    {"url": f"reading_tests/images/{name}", "after_paragraph": position, "alt": alt}
                    for name, position, _, alt in READING_IMAGES[test_id]
                ]
                assert patch["images"] == expected_images, (
                    test_id,
                    "image source/position changed",
                )
            assert set(patch) == fields
            if "introduction" in patch:
                assert isinstance(patch["introduction"], str) and patch["introduction"]


def verify_reviewed_text_values(before, correction, subject):
    units = before["sections" if subject == "listening" else "passages"]
    groups = {str(group["group_id"]): group for unit in units for group in unit["groups"]}
    test_id = before["id"]
    for group_id, patch in correction.get("groups", {}).items():
        desc = groups[group_id]["desc"]
        if subject == "listening":
            first, last = LISTENING_GROUP_RANGES[test_id][group_id]
            old = f"Questions {first} and {last}"
            assert old in desc
            desc = desc.replace(old, f"Questions {first}-{last}")
            if (test_id, group_id) == ("ielts11_test2", "209"):
                desc = desc.replace("Complete th notes", "Complete the notes")
        else:
            for old, new in READING_GROUP_REPLACEMENTS[test_id][group_id]:
                assert old in desc
                desc = desc.replace(old, new)
        assert patch["desc"] == desc, (test_id, group_id, "instruction exceeds reviewed edit")
    if subject == "listening":
        questions = {
            q["number"]: q for unit in units for group in unit["groups"] for q in group["questions"]
        }
        for number in LISTENING_NEW_TITLES.get(test_id, ()):
            title = questions[number]["title"]
            if test_id == "ielts5_test3":
                title = title.replace("thesame", "the same")
            elif test_id == "ielts15_test4":
                title = title.replace("wasprovided", "was provided")
            else:
                title = "Subtitles were added to The Lights of New York because of its 【   】."
            assert correction["questions"][str(number)]["title"] == title


def audit_subject(subject, base):
    from services.cambridge_answer_corrections import apply_listening_answer_corrections
    from services.cambridge_content_corrections import apply_content_corrections

    manifest_path = ROOT / "data/cambridge_content_corrections" / f"{subject}.json"
    manifest = json.loads(manifest_path.read_text())
    verify_manifest(subject, manifest)
    directory = ROOT / "static" / f"{subject}_tests"
    pattern = r"ielts\d+_test\d+" + ("_reading" if subject == "reading" else "") + r"\.json"
    files = sorted(
        path for path in directory.glob("ielts*.json") if re.fullmatch(pattern, path.name)
    )
    assert len(files) == 72, (subject, len(files))
    unit_key = "sections" if subject == "listening" else "passages"
    changed_files = []
    changed_questions = []
    field_counts = collections.Counter()
    introductions = []
    changed_groups = []
    changed_image_passages = []
    score_corrections = []
    unchanged_score_questions = 0
    question_count = 0
    preserved_letter_paragraphs = 0
    hashes = []
    for path in files:
        relative = str(path.relative_to(ROOT))
        baseline_bytes = subprocess.check_output(["git", "show", f"{base}:{relative}"], cwd=ROOT)
        before = json.loads(baseline_bytes)
        after = json.loads(path.read_text())
        expected = apply_content_corrections(copy.deepcopy(before), subject)
        if subject == "listening":
            apply_listening_answer_corrections(expected)
        assert expected == after, (relative, "current payload differs from reviewed correction")
        reapplied = apply_content_corrections(copy.deepcopy(after), subject)
        if subject == "listening":
            apply_listening_answer_corrections(reapplied)
        assert reapplied == after, (
            relative,
            "not idempotent",
        )
        correction = manifest["tests"].get(before["id"], {})
        verify_reviewed_text_values(before, correction, subject)
        assert without_reviewed_fields(before, subject, correction) == without_reviewed_fields(
            after, subject, correction
        ), (relative, "non-reviewed field changed")
        old_questions = all_questions(before, unit_key)
        new_questions = all_questions(after, unit_key)
        assert len(old_questions) == len(new_questions) == 40, relative
        question_count += len(new_questions)
        for old, new in zip(old_questions, new_questions, strict=True):
            # Includes id, number, answer(s), options, input_mode and any score fields.
            answer_patch = subject == "listening" and str(old["number"]) in ANSWER_PARTS.get(
                before["id"], {}
            )
            editable = QUESTION_EDITORIAL_FIELDS | (
                {"answer", "answers"} if answer_patch else set()
            )
            protected_old = {k: v for k, v in old.items() if k not in editable}
            protected_new = {k: v for k, v in new.items() if k not in editable}
            assert protected_old == protected_new, (
                relative,
                old["number"],
                "scoring/identity changed",
            )
            if answer_patch:
                number = str(old["number"])
                assert new["id"] == ANSWER_PARTS[before["id"]][number][0]
                assert new["answers"] == [part.strip() for part in new["answer"].split("/")]
                assert set(new["answers"]) == answer_variants(before["id"], number)
                assert old["answer"] != new["answer"] and old["answers"] != new["answers"]
                score_corrections.append(
                    {
                        "test": before["id"],
                        "number": old["number"],
                        "id": old["id"],
                        "before_answer": old["answer"],
                        "after_answer": new["answer"],
                        "complete_pair_variants": len(new["answers"]),
                    }
                )
            else:
                unchanged_score_questions += 1
            changed_fields = sorted(k for k in set(old) | set(new) if old.get(k) != new.get(k))
            approved_fields = set(correction.get("questions", {}).get(str(old["number"]), {}))
            if answer_patch:
                approved_fields.update({"answer", "answers"})
            assert set(changed_fields) == approved_fields, (
                relative,
                old["number"],
                "actual changed question fields differ from declared scope",
            )
            if changed_fields:
                changed_questions.append(
                    {"test": before["id"], "number": old["number"], "fields": changed_fields}
                )
                field_counts.update(changed_fields)
        for old_unit, new_unit in zip(before[unit_key], after[unit_key], strict=True):
            for old_group, new_group in zip(old_unit["groups"], new_unit["groups"], strict=True):
                changes = sorted(
                    key
                    for key in set(old_group) | set(new_group)
                    if key != "questions" and old_group.get(key) != new_group.get(key)
                )
                if changes:
                    assert changes == ["desc"]
                    changed_groups.append(
                        {"test": before["id"], "group_id": old_group["group_id"], "fields": changes}
                    )
        if subject == "reading":
            for old, new in zip(before["passages"], after["passages"], strict=True):
                old_paras = old["content"]["paragraphs"]
                new_paras = new["content"]["paragraphs"]
                assert labelled_paragraphs(old_paras) == labelled_paragraphs(new_paras), (
                    relative,
                    old["passage"],
                    "A–Z changed",
                )
                preserved_letter_paragraphs += len(labelled_paragraphs(old_paras))
                if old["content"].get("images") != new["content"].get("images"):
                    assert old["content"].get("images") is None
                    changed_image_passages.append(
                        {
                            "test": before["id"],
                            "passage": old["passage"],
                            "image_count": len(new["content"]["images"]),
                        }
                    )
                if old_paras != new_paras:
                    assert new_paras[0]["label"] == "pre-A" and new_paras[1:] == old_paras
                    introductions.append(
                        {
                            "test": before["id"],
                            "passage": old["passage"],
                            "characters": len(new_paras[0]["text"]),
                        }
                    )
        if before != after:
            changed_files.append(relative)
        hashes.append(
            {
                "path": relative,
                "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
                "current_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    assert question_count == 2880
    expected_tests = set(manifest["tests"]) | (
        set(ANSWER_PARTS) if subject == "listening" else set()
    )
    assert {Path(path).stem for path in changed_files} == expected_tests
    assert len(changed_questions) == (42 if subject == "listening" else 205)
    assert len(changed_groups) == (9 if subject == "listening" else 6)
    assert len(introductions) == (0 if subject == "listening" else 5)
    assert len(changed_image_passages) == (0 if subject == "listening" else 3)
    assert len(score_corrections) == (4 if subject == "listening" else 0)
    return {
        "test_files": len(files),
        "questions": question_count,
        "changed_test_file_count": len(changed_files),
        "changed_test_files": changed_files,
        "changed_question_count": len(changed_questions),
        "changed_questions": changed_questions,
        "changed_field_counts": dict(sorted(field_counts.items())),
        "changed_group_count": len(changed_groups),
        "changed_groups": changed_groups,
        "score_unchanged_question_count": unchanged_score_questions,
        "reviewed_score_correction_count": len(score_corrections),
        "reviewed_score_corrections": score_corrections,
        "restored_introduction_count": len(introductions),
        "restored_introductions": introductions,
        "restored_image_passage_count": len(changed_image_passages),
        "restored_image_count": sum(row["image_count"] for row in changed_image_passages),
        "restored_image_passages": changed_image_passages,
        "preserved_letter_paragraph_count": preserved_letter_paragraphs,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "hashes": hashes,
    }


def verify_image_resources():
    from PIL import Image

    resources = []
    for test_id, images in READING_IMAGES.items():
        for filename, position, digest, _ in images:
            path = ROOT / "static/reading_tests/images" / filename
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual == digest, (path, "original image bytes changed")
            with Image.open(path) as image:
                dimensions = image.size
                image.verify()
            resources.append(
                {
                    "test": test_id,
                    "path": str(path.relative_to(ROOT)),
                    "after_paragraph": position,
                    "sha256": actual,
                    "bytes": path.stat().st_size,
                    "dimensions": dimensions,
                }
            )
    assert len(resources) == 4
    return resources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/reviews/cambridge-release-20261107/release-scope.json",
    )
    args = parser.parse_args()
    assert args.base == BASE, "This review is explicitly bound to the production baseline."
    historical_path = Path(__file__).with_name("scope-verification.json")
    historical_hash = hashlib.sha256(historical_path.read_bytes()).hexdigest()
    assert (
        args.output.resolve() != historical_path.resolve()
    ), "Keep the original scope report as historical evidence."
    answer_manifest_hash = verify_answer_manifest()
    resources = verify_image_resources()
    subjects = {subject: audit_subject(subject, args.base) for subject in ("listening", "reading")}
    assert sum(row["score_unchanged_question_count"] for row in subjects.values()) == 5756
    assert sum(row["reviewed_score_correction_count"] for row in subjects.values()) == 4
    result = {
        "base": args.base,
        "worktree": str(ROOT),
        "status": "pass",
        "checks": {
            "all_144_payloads_equal_corrected_baseline": True,
            "all_5760_identity_options_and_other_score_fields_unchanged": True,
            "other_5756_questions_answer_and_answers_unchanged": True,
            "only_four_reviewed_answer_pairs_changed": True,
            "all_four_answer_variants_match_independently_declared_complete_pairs": True,
            "all_unreviewed_fields_unchanged": True,
            "all_reading_A_to_Z_paragraphs_unchanged": True,
            "all_corrections_idempotent": True,
            "manifest_scope_matches_independently_declared_review_scope": True,
            "all_four_figure_files_match_reviewed_source_sha256_and_decode": True,
        },
        "answer_manifest_sha256": answer_manifest_hash,
        "historical_scope_report_sha256": historical_hash,
        "figure_resources": resources,
        "subjects": subjects,
        "limits": "Scope/invariant verification only; not a full semantic review or browser/audio acceptance.",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    assert hashlib.sha256(historical_path.read_bytes()).hexdigest() == historical_hash
    print(
        json.dumps(
            {
                "status": "pass",
                "tests": 144,
                "questions": 5760,
                "unchanged_answer_questions": 5756,
                "reviewed_answer_corrections": 4,
                "subjects": {
                    key: {
                        k: value[k]
                        for k in (
                            "changed_test_file_count",
                            "changed_question_count",
                            "changed_field_counts",
                            "restored_introduction_count",
                            "changed_group_count",
                            "restored_image_count",
                            "reviewed_score_correction_count",
                        )
                    }
                    for key, value in subjects.items()
                },
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
