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
        text_chunks = [
            str(row.get("content"))
            for row in value
            if isinstance(row, dict)
            and row.get("type") == "text"
            and row.get("content")
        ]
        if text_chunks:
            return "\n".join(text_chunks)
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


def audio_location(value) -> dict:
    if not isinstance(value, list):
        return {}
    for row in value:
        if not isinstance(row, dict) or row.get("type") != "audio":
            continue
        location = row.get("location")
        if isinstance(location, dict) and (location.get("start_time") or location.get("end_time")):
            return location
    return {}


def is_usable_analysis(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    blocked_markers = (
        "\u5f88\u62b1\u6b49",
        "\u65e0\u6cd5\u76f4\u63a5",
        "\u65e0\u6cd5\u786e\u5b9a",
        "\u4fe1\u606f\u6709\u9650",
    )
    return not any(marker in text for marker in blocked_markers)


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


def default_start_time(item: dict):
    answer_sentence = item.get("answer_sentences") or {}
    return answer_sentence.get("start_time") or item.get("start_time")


def parse_location_sentence(value) -> list[int]:
    """Parse ai_central_sentences.location_sentence into 1-based content indices."""
    if not isinstance(value, str):
        return []
    normalized = value.replace("，", ",")  # tolerate Chinese comma
    indices = []
    for token in normalized.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            indices.append(int(token))
        except ValueError:
            continue
    return indices


def location_span_from_content(item: dict, content: list | None) -> dict:
    """Derive answer timing from ai_central_sentences.location_sentence.

    Cambridge IELTS 21 items ship without answer_sentences / start_time, but the
    AI analysis records which transcript sentences (1-based into the part's
    ``content`` array) hold the answer. Return a dict shaped like Cambridge
    IELTS 20's answer_sentences ({start_time, end_time, lyc_index:[min, max]},
    times in ms), or {} when parsing fails / indices go out of bounds.
    """
    if not content:
        return {}
    acs = item.get("ai_central_sentences")
    if not isinstance(acs, dict):
        return {}
    indices = parse_location_sentence(acs.get("location_sentence"))
    if not indices:
        return {}
    lo, hi = min(indices), max(indices)
    if lo < 1 or hi > len(content):
        return {}
    start_row = content[lo - 1] if isinstance(content[lo - 1], dict) else {}
    end_row = content[hi - 1] if isinstance(content[hi - 1], dict) else {}
    start_time = start_row.get("start_time")
    end_time = end_row.get("end_time")
    if not start_time and not end_time:
        return {}
    return {
        "start_time": start_time,
        "end_time": end_time,
        "lyc_index": [lo, hi],
    }


def analyze_location_question_ids(items: list[dict]) -> set:
    by_start = {}
    for item in items:
        start_time = default_start_time(item)
        if not start_time:
            continue
        by_start.setdefault(start_time, []).append(item)

    for cluster in by_start.values():
        if len(cluster) < 2:
            continue
        locations = [audio_location(item.get("analyze")) for item in cluster]
        starts = {
            location.get("start_time")
            for location in locations
            if location.get("start_time")
        }
        if len(starts) < 2:
            continue
        return {
            item.get("id")
            for item in items
            if audio_location(item.get("analyze")).get("start_time")
        }
    return set()


def build_question(
    item: dict,
    use_analyze_location: bool = False,
    content: list | None = None,
) -> dict:
    options = []
    for option in item.get("option") or []:
        options.append(
            {
                "title": str(option.get("title") or "").strip(),
                "content": str(option.get("content") or "").strip(),
            }
        )

    answer = str(item.get("display_answer") or "").strip()
    source_location = (
        audio_location(item.get("analyze"))
        if use_analyze_location
        else {}
    )
    answer_sentence = item.get("answer_sentences") or {}
    start_time = source_location.get("start_time") or answer_sentence.get("start_time") or item.get("start_time")
    end_time = source_location.get("end_time") or answer_sentence.get("end_time") or item.get("end_time")
    output_answer_sentence = dict(answer_sentence)
    if source_location:
        for key in ("start_time", "end_time", "lyc_index"):
            if key in source_location:
                output_answer_sentence[key] = source_location.get(key)
    if not start_time and not end_time:
        # 4th-level fallback: no explicit timing (e.g. Cambridge IELTS 21) —
        # locate the answer via ai_central_sentences.location_sentence.
        location_span = location_span_from_content(item, content)
        if location_span:
            start_time = location_span["start_time"]
            end_time = location_span["end_time"]
            output_answer_sentence.update(location_span)
    source_analysis = analysis_text(item.get("analyze"))
    if use_analyze_location and is_usable_analysis(source_analysis):
        analysis = source_analysis
    else:
        analysis = item.get("ai_analyze") or source_analysis
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
        "answer_sentences": output_answer_sentence,
    }


def build_group(group: dict, section_id: str, content: list | None = None) -> dict:
    img_url = group.get("img_url") or ""
    items = group.get("list") or []
    analyze_location_ids = analyze_location_question_ids(items)
    collect_option = group.get("collect_option") or {}
    # Cambridge IELTS 21 leaves the group-level title empty and only stores the
    # shared multiple-choice stem on collect_option.title — fall back to it so
    # the render's <h3> shows the question stem.
    title = (group.get("title") or "").strip() or (collect_option.get("title") or "")
    return {
        "group_id": group.get("group_id"),
        "type": group.get("type"),
        "title": title,
        "question_title": group.get("question_title") or "",
        "desc": group.get("desc") or "",
        "table": group.get("table"),
        "collect": group.get("collect") or "",
        "img_url": img_url,
        "img_local": localize_image(img_url, section_id),
        "collect_option": collect_option,
        "questions": [
            build_question(item, item.get("id") in analyze_location_ids, content)
            for item in items
        ],
    }


def build_section(exercise_id: str, part_id: int, audio: str, raw_parts: dict) -> dict:
    part = unwrap_part(raw_parts, part_id)
    content = part.get("content") or []
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
        "groups": [
            build_group(group, exercise_id, content)
            for group in part.get("question") or []
        ],
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
