#!/usr/bin/env python3
"""Build static JSON assets for the listening jijing practice pages."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


TYPE_NAMES = {
    1: "单选题",
    2: "多选题",
    3: "表格/句子填空题",
    4: "匹配题",
    5: "摘要/笔记填空题",
    6: "简答题",
    7: "地图题",
    8: "句子填空题",
    9: "多选题",
    10: "拖拽匹配题",
}


def safe_slug(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "unknown"


def part_number(title: str) -> int:
    match = re.search(r"\d+", title or "")
    return int(match.group()) if match else 0


def answer_of(item: dict[str, Any]) -> str:
    if item.get("display_answer") not in (None, ""):
        return str(item["display_answer"]).strip()
    for block in item.get("analyze") or []:
        if isinstance(block, dict) and block.get("type") == "answer":
            text = str(block.get("content") or "").strip()
            return re.sub(r"^答案[:：]\s*", "", text).strip()
    return ""


def analysis_of(item: dict[str, Any]) -> str:
    if item.get("ai_analyze"):
        return str(item["ai_analyze"]).strip()
    for block in item.get("analyze") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text = str(block.get("content") or "").strip()
            if text:
                return text
    return ""


def audio_location_of(item: dict[str, Any]) -> dict[str, Any] | None:
    for block in item.get("analyze") or []:
        if isinstance(block, dict) and block.get("type") == "audio" and isinstance(block.get("location"), dict):
            location = block["location"]
            return {
                "start_time": location.get("start_time"),
                "end_time": location.get("end_time"),
            }
    return None


def normalize_option(option: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": option.get("id"),
        "title": option.get("title") or option.get("value") or "",
        "content": option.get("content") or option.get("label") or "",
    }


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "number": item.get("number"),
        "title": item.get("title") or "",
        "options": [normalize_option(o) for o in item.get("option") or [] if isinstance(o, dict)],
        "answer": answer_of(item),
        "analysis": analysis_of(item),
        "start_time": item.get("start_time"),
        "end_time": item.get("end_time"),
        "audio_location": audio_location_of(item),
        "img_url": item.get("img_url") or "",
        "is_multiple": item.get("is_multiple"),
    }


def normalize_group(group: dict[str, Any]) -> dict[str, Any]:
    type_id = group.get("type")
    try:
        type_id_int = int(type_id)
    except (TypeError, ValueError):
        type_id_int = 0

    collect_option = group.get("collect_option") if isinstance(group.get("collect_option"), dict) else {}
    return {
        "group_id": group.get("group_id"),
        "type": type_id_int,
        "type_name": TYPE_NAMES.get(type_id_int, f"题型 {type_id}"),
        "desc": group.get("desc") or "",
        "title": group.get("title") or "",
        "question_title": group.get("question_title") or "",
        "collect": group.get("collect") or "",
        "collect_options": {
            "title": collect_option.get("title") or "",
            "list": [
                normalize_option(option)
                for option in collect_option.get("list") or []
                if isinstance(option, dict)
            ],
        },
        "table": group.get("table"),
        "img_url": group.get("img_url") or "",
        "items": [normalize_item(item) for item in group.get("list") or [] if isinstance(item, dict)],
    }


def build(raw: dict[str, Any], manifest: list[dict[str, Any]], output_dir: Path) -> None:
    audio_by_paper = {str(item.get("paper_id")): item for item in manifest}
    parts_dir = output_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    catalog_books: dict[int, dict[str, Any]] = {}
    written_parts = 0

    for response in (raw.get("parts") or {}).values():
        if not isinstance(response, dict):
            continue
        values = response.get("values")
        if not isinstance(values, dict):
            continue
        paper_id = values.get("paper_id")
        audio = audio_by_paper.get(str(paper_id))
        if not paper_id or not audio:
            continue
        groups = [normalize_group(group) for group in values.get("question") or [] if isinstance(group, dict)]
        if not groups:
            continue

        in_book = values.get("in_book")
        test_name = values.get("test_name") or ""
        title = values.get("title") or ""
        part_num = part_number(title)
        part_id = f"jijing_{safe_slug(in_book)}_{safe_slug(test_name)}_part_{part_num}_{safe_slug(paper_id)}"

        question_numbers = []
        for group in groups:
            for item in group["items"]:
                if item.get("number") not in (None, ""):
                    question_numbers.append(int(item["number"]))

        part_payload = {
            "id": part_id,
            "paper_id": paper_id,
            "in_book": in_book,
            "test_name": test_name,
            "part_title": title,
            "part_number": part_num,
            "question_name": values.get("question_name") or "",
            "question_type": values.get("question_type") or "",
            "audio": {
                "url": audio.get("url") or values.get("file_url") or "",
                "filename": audio.get("filename") or "",
                "local_path": audio.get("local_path") or "",
            },
            "content": values.get("content") or [],
            "groups": groups,
        }
        (parts_dir / f"{part_id}.json").write_text(
            json.dumps(part_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written_parts += 1

        book_key = int(in_book) if str(in_book).isdigit() else 999999
        book = catalog_books.setdefault(
            book_key,
            {
                "in_book": in_book,
                "title": f"机经 {in_book}",
                "tests": {},
            },
        )
        tests = book["tests"]
        test = tests.setdefault(
            test_name,
            {
                "test_name": test_name,
                "parts": [],
            },
        )
        test["parts"].append(
            {
                "id": part_id,
                "paper_id": paper_id,
                "part_title": title,
                "part_number": part_num,
                "question_name": values.get("question_name") or "",
                "question_type": values.get("question_type") or "",
                "question_count": len(set(question_numbers)),
                "audio_path": audio.get("local_path") or "",
            }
        )

    books = []
    for _, book in sorted(catalog_books.items(), key=lambda pair: pair[0]):
        tests = []
        for _, test in sorted(book["tests"].items(), key=lambda pair: pair[0]):
            test["parts"].sort(key=lambda item: item["part_number"])
            tests.append(test)
        book["tests"] = tests
        books.append(book)

    catalog = {
        "source": "idictation_jijing",
        "title": "听力机经",
        "book_count": len(books),
        "part_count": written_parts,
        "books": books,
    }
    (output_dir / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_audio_link(static_dir: Path, audio_source: Path, copy_audio: bool) -> None:
    target = static_dir / "audio"
    if copy_audio:
        target.mkdir(parents=True, exist_ok=True)
        for source in audio_source.glob("*.mp3"):
            dest = target / source.name
            if not dest.exists() or dest.stat().st_size != source.stat().st_size:
                shutil.copy2(source, dest)
        return

    if target.exists() or target.is_symlink():
        if target.is_symlink() and Path(os.readlink(target)).resolve() == audio_source.resolve():
            return
        if target.is_dir() and not target.is_symlink():
            return
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(audio_source.resolve(), target_is_directory=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="/Users/zhouxin/Desktop/idictation_listening_jijing_raw.json")
    parser.add_argument("--manifest", default="data/idictation_listening_jijing/audio_manifest.json")
    parser.add_argument("--output-dir", default="static/listening_jijing")
    parser.add_argument("--audio-source", default="data/idictation_listening_jijing/audio")
    parser.add_argument("--copy-audio", action="store_true")
    args = parser.parse_args()

    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    build(raw, manifest, output_dir)
    ensure_audio_link(output_dir, Path(args.audio_source), copy_audio=args.copy_audio)
    print(output_dir / "catalog.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
