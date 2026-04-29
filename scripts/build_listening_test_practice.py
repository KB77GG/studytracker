#!/usr/bin/env python3
"""Build a full Cambridge IELTS listening test practice JSON from idictation raw data."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "idictation_xyy_listening" / "raw.json"
REPORT_PATH = ROOT / "data" / "idictation_xyy_listening" / "import_report.json"
OUTPUT_DIR = ROOT / "static" / "listening_tests"
IMAGE_DIR = OUTPUT_DIR / "images"


SECTION_RE = re.compile(r"^ielts(?P<book>\d+)_test(?P<test>\d+)_s(?P<section>\d+)$")


def ms_to_seconds(value) -> float:
    try:
        return round(float(value or 0) / 1000, 3)
    except (TypeError, ValueError):
        return 0.0


def as_list(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [text]
    return []


def analysis_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks = []
        for row in value:
            if isinstance(row, dict) and row.get("content"):
                chunks.append(str(row.get("content")))
            elif isinstance(row, str):
                chunks.append(row)
        return "\n".join(chunks)
    if isinstance(value, dict):
        return str(value.get("content") or value.get("analysis") or "")
    return ""


def is_usable_image(url: str) -> bool:
    return bool(re.match(r"^https?://", url or "")) and not re.search(r"aliyuncs\.com/?$", url or "")


def localize_image(url: str, section_id: str) -> str:
    if not is_usable_image(url):
        return ""
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix or ".png"
    stem = Path(parsed.path).stem or "question"
    filename = f"{section_id}_{stem}{suffix}"
    out_path = IMAGE_DIR / filename
    if not out_path.exists():
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(url, timeout=20, context=context) as resp:
            out_path.write_bytes(resp.read())
    return f"listening_tests/images/{filename}"


def unwrap_part(raw_parts: dict, part_id: int) -> dict:
    row = raw_parts.get(str(part_id)) or {}
    return row.get("values") or row.get("data") or row


def build_question(item: dict) -> dict:
    options = []
    for option in item.get("option") or []:
        options.append(
            {
                "title": str(option.get("title") or "").strip(),
                "content": str(option.get("content") or "").strip(),
            }
        )

    answer = str(item.get("display_answer") or "").strip()
    answer_sentence = item.get("answer_sentences") or {}
    start_time = answer_sentence.get("start_time") or item.get("start_time")
    end_time = answer_sentence.get("end_time") or item.get("end_time")
    analysis = item.get("ai_analyze") or analysis_text(item.get("analyze"))
    return {
        "id": item.get("id"),
        "number": item.get("number"),
        "title": str(item.get("title") or "").strip(),
        "answer": answer,
        "answers": [part.strip() for part in re.split(r"\s*/\s*", answer) if part.strip()],
        "options": options,
        "start": ms_to_seconds(start_time),
        "end": ms_to_seconds(end_time),
        "analysis": analysis,
        "answer_sentences": answer_sentence,
    }


def build_group(group: dict, section_id: str) -> dict:
    img_url = group.get("img_url") or ""
    return {
        "group_id": group.get("group_id"),
        "type": group.get("type"),
        "title": group.get("title") or "",
        "question_title": group.get("question_title") or "",
        "desc": group.get("desc") or "",
        "table": group.get("table"),
        "collect": group.get("collect") or "",
        "img_url": img_url,
        "img_local": localize_image(img_url, section_id),
        "collect_option": group.get("collect_option") or {},
        "questions": [build_question(item) for item in group.get("list") or []],
    }


def build_section(exercise_id: str, part_id: int, audio: str, raw_parts: dict) -> dict:
    part = unwrap_part(raw_parts, part_id)
    match = SECTION_RE.match(exercise_id)
    section_no = int(match.group("section")) if match else 0
    return {
        "id": exercise_id,
        "part_id": part_id,
        "section": section_no,
        "title": f"Section {section_no}",
        "audio": audio,
        "source_title": part.get("title") or "",
        "question_name": part.get("question_name") or "",
        "question_type": as_list(part.get("question_type")),
        "groups": [build_group(group, exercise_id) for group in part.get("question") or []],
        "transcript": [
            {
                "order": row.get("order"),
                "start": ms_to_seconds(row.get("start_time")),
                "end": ms_to_seconds(row.get("end_time")),
                "en": row.get("en_text") or "",
                "cn": row.get("cn_text") or "",
            }
            for row in part.get("content") or []
        ],
    }


def build_test(test_id: str) -> dict:
    raw = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    sections = []

    for row in report:
        exercise_id = row.get("exercise_id") or ""
        if not exercise_id.startswith(f"{test_id}_s"):
            continue
        sections.append(
            build_section(
                exercise_id=exercise_id,
                part_id=int(row["part_id"]),
                audio=row.get("audio") or f"{exercise_id}.mp3",
                raw_parts=raw.get("parts") or {},
            )
        )

    sections.sort(key=lambda section: section["section"])
    if not sections:
        raise SystemExit(f"No sections found for {test_id}")

    match = re.match(r"^ielts(?P<book>\d+)_test(?P<test>\d+)$", test_id)
    if match:
        title = f"Cambridge IELTS {match.group('book')} Test {match.group('test')} Listening"
    else:
        title = test_id

    return {
        "id": test_id,
        "title": title,
        "source": "idictation_xyy",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
    }


def discover_test_ids() -> list[str]:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    ids = set()
    for row in report:
        exercise_id = row.get("exercise_id") or ""
        match = re.match(r"^(ielts\d+_test\d+)_s[1-4]$", exercise_id)
        if match:
            ids.add(match.group(1))

    def sort_key(test_id: str) -> tuple[int, int]:
        match = re.match(r"^ielts(?P<book>\d+)_test(?P<test>\d+)$", test_id)
        if not match:
            return (999, 999)
        return (int(match.group("book")), int(match.group("test")))

    return sorted(ids, key=sort_key)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("test_id", nargs="?", default="ielts11_test1")
    parser.add_argument("--all", action="store_true", help="build every Cambridge IELTS test found in import_report.json")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    test_ids = discover_test_ids() if args.all else [args.test_id]
    for test_id in test_ids:
        payload = build_test(test_id)
        out_path = args.output_dir / f"{test_id}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        question_count = sum(
            len(group.get("questions") or [])
            for section in payload["sections"]
            for group in section.get("groups") or []
        )
        print(f"Wrote {out_path} ({len(payload['sections'])} sections, {question_count} questions)")


if __name__ == "__main__":
    main()
