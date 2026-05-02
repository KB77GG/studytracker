#!/usr/bin/env python3
"""Build Cambridge IELTS reading practice JSON from idictation reading raw data."""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "idictation_reading" / "raw.json"
OUTPUT_DIR = ROOT / "static" / "reading_tests"
IMAGE_DIR = OUTPUT_DIR / "images"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(p|div|li|tr|h[1-6])\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def as_list(value: Any) -> list:
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


def first_int(*values: Any) -> int:
    for value in values:
        if isinstance(value, int):
            return value
        match = re.search(r"\d+", str(value or ""))
        if match:
            return int(match.group())
    return 0


def analysis_text(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        chunks = []
        for row in value:
            if isinstance(row, dict):
                chunks.append(clean_text(row.get("content") or row.get("analysis") or row.get("text")))
            else:
                chunks.append(clean_text(row))
        return "\n".join(chunk for chunk in chunks if chunk)
    if isinstance(value, dict):
        return clean_text(value.get("content") or value.get("analysis") or value.get("text") or "")
    return ""


def option_key(value: Any, fallback_index: int) -> str:
    raw = clean_text(value)
    match = re.match(r"^([A-Z]+)(?:[.)、:]|\s|$)", raw, re.I)
    if match:
        return match.group(1).upper()
    return chr(ord("A") + fallback_index)


def option_text(value: dict[str, Any], fallback_key: str) -> str:
    text = clean_text(value.get("content") or value.get("text") or value.get("title") or "")
    text = re.sub(rf"^{re.escape(fallback_key)}[.)、:\s]+", "", text, flags=re.I).strip()
    return text


def truth_options(answer: str) -> list[dict[str, str]]:
    upper = answer.strip().upper()
    if upper in {"TRUE", "FALSE", "NOT GIVEN", "T", "F", "NG"}:
        return [
            {"key": "T", "text": "TRUE"},
            {"key": "F", "text": "FALSE"},
            {"key": "NG", "text": "NOT GIVEN"},
        ]
    if upper in {"YES", "NO", "NOT GIVEN", "Y", "N", "NG"}:
        return [
            {"key": "Y", "text": "YES"},
            {"key": "N", "text": "NO"},
            {"key": "NG", "text": "NOT GIVEN"},
        ]
    return []


def is_usable_image(url: str) -> bool:
    return bool(re.match(r"^https?://", url or ""))


def localize_image(url: str, passage_id: str) -> str:
    if not is_usable_image(url):
        return ""
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix or ".png"
    stem = Path(parsed.path).stem or "question"
    filename = f"{passage_id}_{stem}{suffix}"
    out_path = IMAGE_DIR / filename
    if not out_path.exists():
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(url, timeout=30, context=context) as resp:
            out_path.write_bytes(resp.read())
    return f"reading_tests/images/{filename}"


def unwrap_part(raw_parts: dict[str, Any], source: str, part_id: int) -> dict[str, Any]:
    row = raw_parts.get(source, {}).get(str(part_id)) or {}
    return row.get("values") or row.get("data") or row


def build_passage_content(part: dict[str, Any]) -> dict[str, Any]:
    content = part.get("content")
    if not isinstance(content, dict):
        return {"title": clean_text(part.get("title") or ""), "paragraphs": []}
    title = clean_text(content.get("title") or part.get("title") or "")
    paragraphs = []
    raw_paragraphs = content.get("paragraph")
    if isinstance(raw_paragraphs, list):
        for index, paragraph in enumerate(raw_paragraphs):
            label = ""
            if index < 26:
                label = chr(ord("A") + index)
            paragraphs.append({"label": label, "text": clean_text(paragraph)})
    else:
        for key in sorted([k for k in content if re.fullmatch(r"[A-Z]", str(k))]):
            text = clean_text(content.get(key))
            if text:
                paragraphs.append({"label": key, "text": text})
    return {
        "title": title,
        "summary": clean_text(content.get("summary")),
        "notes": clean_text(content.get("notes")),
        "paragraphs": paragraphs,
    }


def build_question(item: dict[str, Any], group_options: list[dict[str, str]]) -> dict[str, Any]:
    answer = clean_text(item.get("display_answer") or item.get("answer") or item.get("correct_answer"))
    options = []
    for index, raw in enumerate(item.get("option") or []):
        if not isinstance(raw, dict):
            raw = {"title": raw}
        key = option_key(raw.get("title") or raw.get("key") or raw.get("label"), index)
        text = option_text(raw, key)
        if text:
            options.append({"key": key, "text": text})
    if not options:
        options = truth_options(answer)
    input_mode = "choice" if options else ("select" if group_options else "text")
    return {
        "id": item.get("id"),
        "number": item.get("number"),
        "title": clean_text(item.get("title") or item.get("question") or item.get("stem")),
        "answer": answer,
        "answers": [part.strip() for part in re.split(r"\s*/\s*", answer) if part.strip()],
        "options": options,
        "input_mode": input_mode,
        "analysis": clean_text(item.get("ai_analyze")) or analysis_text(item.get("analyze")),
        "central_sentences": item.get("central_sentences") or item.get("ai_central_sentences") or [],
        "locating_words": item.get("locating_words") or item.get("key_locating_words") or [],
    }


def build_group_options(group: dict[str, Any]) -> list[dict[str, str]]:
    rows = ((group.get("collect_option") or {}).get("list") or [])
    options = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raw = {"title": raw}
        key = option_key(raw.get("title") or raw.get("key") or raw.get("label"), index)
        text = option_text(raw, key)
        if text:
            options.append({"key": key, "text": text})
    return options


def build_group(group: dict[str, Any], passage_id: str) -> dict[str, Any]:
    group_options = build_group_options(group)
    img_url = group.get("img_url") or ""
    return {
        "group_id": group.get("group_id"),
        "type": group.get("type"),
        "title": clean_text(group.get("title")),
        "question_title": clean_text(group.get("question_title")),
        "desc": clean_text(group.get("desc")),
        "table": group.get("table"),
        "collect": group.get("collect") or "",
        "img_url": img_url,
        "img_local": localize_image(img_url, passage_id),
        "collect_option": {
            "title": clean_text((group.get("collect_option") or {}).get("title")),
            "list": group_options,
        },
        "questions": [build_question(item, group_options) for item in group.get("list") or []],
    }


def test_id_for(book: int, test_no: int) -> str:
    return f"ielts{book}_test{test_no}_reading"


def build_tests(raw: dict[str, Any], source: str) -> dict[str, dict[str, Any]]:
    raw_parts = raw.get("parts") or {}
    tests: dict[str, dict[str, Any]] = {}
    for entry in raw.get("entries") or []:
        part_id = int(entry.get("part_id") or 0)
        part = unwrap_part(raw_parts, source, part_id)
        if not part:
            continue
        book = first_int(part.get("in_book"), entry.get("book"))
        test_no = first_int(part.get("test_name"), entry.get("test"))
        passage_no = first_int(part.get("title"), entry.get("passage"))
        if not book or not test_no or not passage_no:
            continue
        tid = test_id_for(book, test_no)
        tests.setdefault(
            tid,
            {
                "id": tid,
                "book": book,
                "test": test_no,
                "title": f"Cambridge IELTS {book} Test {test_no} Reading",
                "source": "idictation_reading",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "passages": [],
            },
        )
        passage_id = f"ielts{book}_test{test_no}_p{passage_no}"
        tests[tid]["passages"].append(
            {
                "id": passage_id,
                "part_id": part_id,
                "book": book,
                "test": test_no,
                "passage": passage_no,
                "title": clean_text(part.get("title") or f"Passage {passage_no}"),
                "question_name": clean_text(part.get("question_name")),
                "question_number": part.get("question_number"),
                "question_type": as_list(part.get("question_type")),
                "content": build_passage_content(part),
                "groups": [build_group(group, passage_id) for group in part.get("question") or []],
            }
        )
    for payload in tests.values():
        payload["passages"].sort(key=lambda row: row["passage"])
    return tests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--source", default="academic")
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    tests = build_tests(raw, args.source)
    catalog: dict[int, list[dict[str, Any]]] = {}
    for tid, payload in sorted(tests.items(), key=lambda item: (item[1]["book"], item[1]["test"])):
        out_path = args.output_dir / f"{tid}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        question_count = sum(len(group.get("questions") or []) for passage in payload["passages"] for group in passage.get("groups") or [])
        catalog.setdefault(payload["book"], []).append(
            {
                "id": tid,
                "book": payload["book"],
                "test": payload["test"],
                "passage_count": len(payload["passages"]),
                "question_count": question_count,
            }
        )
        print(f"Wrote {out_path} ({len(payload['passages'])} passages, {question_count} questions)")
    catalog_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "books": [
            {"book": book, "tests": sorted(rows, key=lambda row: row["test"])}
            for book, rows in sorted(catalog.items())
        ],
    }
    (args.output_dir / "catalog.json").write_text(json.dumps(catalog_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.output_dir / 'catalog.json'}")


if __name__ == "__main__":
    main()
