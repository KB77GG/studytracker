#!/usr/bin/env python3
"""Release gate for IELTS Listening/Reading practice-library integrity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\$([^$\s]+)\$")


def _json_files(root: Path):
    excluded = {"catalog.json", "offline_tests.json"}
    return sorted(path for path in root.glob("*.json") if path.name not in excluded)


def _load_offline_tests(root: Path, problems: list[dict]) -> dict[str, dict]:
    manifest_path = root / "offline_tests.json"
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        problems.append({
            "severity": "P0",
            "file": str(manifest_path),
            "code": "offline_manifest_invalid",
            "detail": str(exc),
        })
        return {}

    entries: dict[str, dict] = {}
    for entry in payload.get("tests") or []:
        test_id = str(entry.get("id") or "").strip() if isinstance(entry, dict) else ""
        if not test_id or entry.get("status") != "offline" or test_id in entries:
            problems.append({
                "severity": "P0",
                "file": str(manifest_path),
                "code": "offline_manifest_entry_invalid",
                "detail": repr(entry),
            })
            continue
        entries[test_id] = entry

    catalog_path = root / "catalog.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        problems.append({
            "severity": "P0",
            "file": str(catalog_path),
            "code": "catalog_invalid_json",
            "detail": str(exc),
        })
        catalog = {}
    catalog_ids = {
        str(test.get("id") or "")
        for book in catalog.get("books") or []
        for test in book.get("tests") or []
        if isinstance(test, dict)
    }
    for test_id, entry in entries.items():
        source_path = root / f"{test_id}.json"
        if not source_path.is_file():
            problems.append({
                "severity": "P0",
                "file": str(source_path),
                "code": "offline_source_missing",
                "detail": test_id,
            })
            continue
        expected_hash = str(entry.get("source_sha256") or "").strip().lower()
        actual_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if not expected_hash or expected_hash != actual_hash:
            problems.append({
                "severity": "P0",
                "file": str(source_path),
                "code": "offline_source_hash_mismatch",
                "detail": f"expected={expected_hash or '<empty>'}, actual={actual_hash}",
            })
        if test_id in catalog_ids:
            problems.append({
                "severity": "P0",
                "file": str(catalog_path),
                "code": "offline_test_still_catalogued",
                "detail": test_id,
            })
    return entries


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _duration_seconds(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=15,
        )
        return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.SubprocessError, TypeError, ValueError):
        return 0.0


def scan_library(static_root: Path, audio_root: Path, *, verify_duration: bool = True) -> dict:
    problems = []
    counts = {
        "listening_tests": 0,
        "reading_tests": 0,
        "offline_reading_tests": 0,
        "questions": 0,
        "audio_files": 0,
        "images": 0,
    }
    suites = [
        ("listening", static_root / "listening_tests", "sections"),
        ("reading", static_root / "reading_tests", "passages"),
        ("reading", static_root / "reading_jijing", "passages"),
    ]
    reading_jijing_root = static_root / "reading_jijing"
    offline_reading_tests = _load_offline_tests(reading_jijing_root, problems)

    for kind, root, container_key in suites:
        for path in _json_files(root):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                problems.append({"severity": "P0", "file": str(path), "code": "invalid_json", "detail": str(exc)})
                continue
            if root == reading_jijing_root and path.stem in offline_reading_tests:
                actual_question_count = sum(
                    len(group.get("questions") or [])
                    for unit in payload.get(container_key) or []
                    for group in unit.get("groups") or []
                )
                expected_question_count = offline_reading_tests[path.stem].get("question_count")
                if expected_question_count != actual_question_count:
                    problems.append({
                        "severity": "P0",
                        "file": str(path),
                        "code": "offline_question_count_mismatch",
                        "detail": f"expected={expected_question_count}, actual={actual_question_count}",
                    })
                counts["offline_reading_tests"] += 1
                continue
            units = payload.get(container_key)
            if not isinstance(units, list) or not units:
                continue
            counts[f"{kind}_tests"] += 1
            numbers = []
            ids = []
            for unit in units:
                if kind == "listening":
                    audio_name = str(unit.get("audio") or "").strip()
                    audio_path = audio_root / Path(audio_name).name
                    if not audio_name or not audio_path.is_file() or audio_path.stat().st_size <= 0:
                        problems.append({"severity": "P0", "file": str(path), "code": "audio_missing", "detail": audio_name or "<empty>"})
                    else:
                        counts["audio_files"] += 1
                        if verify_duration and _duration_seconds(audio_path) <= 0:
                            problems.append({"severity": "P0", "file": str(path), "code": "audio_invalid_duration", "detail": audio_name})
                declared = unit.get("question_number")
                unit_numbers = []
                for group in unit.get("groups") or []:
                    questions = group.get("questions") or []
                    question_ids = {str(question.get("id")) for question in questions}
                    for value in _walk_strings({"collect": group.get("collect"), "table": group.get("table")}):
                        for reference in PLACEHOLDER_RE.findall(value):
                            if str(reference) not in question_ids:
                                problems.append({"severity": "P0", "file": str(path), "code": "orphan_placeholder", "detail": reference})
                    image = str(group.get("img_local") or "").strip().lstrip("/")
                    if image:
                        counts["images"] += 1
                        if not (static_root / image).is_file():
                            problems.append({"severity": "P0", "file": str(path), "code": "image_missing", "detail": image})
                    for question in questions:
                        number = question.get("number")
                        qid = question.get("id")
                        if number is None or qid is None:
                            problems.append({"severity": "P0", "file": str(path), "code": "question_identity_missing", "detail": repr({"id": qid, "number": number})})
                            continue
                        numbers.append(int(number))
                        unit_numbers.append(int(number))
                        ids.append(str(qid))
                        counts["questions"] += 1
                if isinstance(declared, list) and sorted(map(int, declared)) != sorted(unit_numbers):
                    problems.append({"severity": "P0", "file": str(path), "code": "declared_question_mismatch", "detail": f"declared={declared}, actual={unit_numbers}"})

            duplicate_numbers = sorted({number for number in numbers if numbers.count(number) > 1})
            duplicate_ids = sorted({qid for qid in ids if ids.count(qid) > 1})
            if duplicate_numbers:
                problems.append({"severity": "P0", "file": str(path), "code": "duplicate_question_number", "detail": duplicate_numbers})
            if duplicate_ids:
                problems.append({"severity": "P0", "file": str(path), "code": "duplicate_question_id", "detail": duplicate_ids})
            if numbers:
                missing = sorted(set(range(min(numbers), max(numbers) + 1)) - set(numbers))
                if missing:
                    problems.append({"severity": "P0", "file": str(path), "code": "question_number_gap", "detail": missing})
                if min(numbers) != 1 or max(numbers) != 40 or len(numbers) != 40:
                    problems.append({"severity": "P0", "file": str(path), "code": "not_full_40_question_test", "detail": f"count={len(numbers)}, range={min(numbers)}-{max(numbers)}"})

    return {"ok": not problems, "counts": counts, "problems": problems}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-root", type=Path, default=Path(__file__).resolve().parents[1] / "static")
    parser.add_argument("--audio-root", type=Path)
    parser.add_argument("--skip-duration", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    audio_root = args.audio_root or args.static_root / "listening"
    report = scan_library(args.static_root, audio_root, verify_duration=not args.skip_duration)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("IELTS practice library gate:", "PASS" if report["ok"] else "FAIL")
        print(json.dumps(report["counts"], ensure_ascii=False, sort_keys=True))
        for problem in report["problems"]:
            print(f"{problem['severity']} {problem['code']} {problem['file']}: {problem['detail']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
