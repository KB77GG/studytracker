#!/usr/bin/env python3
"""Build Cambridge IELTS writing practice JSON from idictation catalog raw data.

Reads data/idictation_xyy_listening/raw.json's ``catalog.values.books[]`` (剑4-21
共 72 套 Test), each test node carries a ``writing`` dict with ``xiaozuowen``
(Task 1) and ``dazuowen`` (Task 2). Produces one
``static/writing_tests/ielts{book}_test{test}_writing.json`` per test plus a
``catalog.json`` index, downloading Task 1 chart images into
``static/writing_tests/images/``.

Idempotent: re-running overwrites JSON deterministically and skips images that
already exist.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "idictation_xyy_listening" / "raw.json"
OUTPUT_DIR = ROOT / "static" / "writing_tests"
IMAGE_DIR = OUTPUT_DIR / "images"

TASK_MIN_WORDS = {1: 150, 2: 250}


def clean_text(value: Any) -> str:
    """Strip HTML to readable plain text (mirrors build_reading_test_practice)."""
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


def first_int(*values: Any) -> int:
    for value in values:
        if isinstance(value, int):
            return value
        match = re.search(r"\d+", str(value or ""))
        if match:
            return int(match.group())
    return 0


def is_usable_image(url: str) -> bool:
    return bool(re.match(r"^https?://", url or ""))


def localize_image(url: str, test_id: str, insecure: bool) -> str | None:
    """Download image into IMAGE_DIR; return ``images/<file>`` relative path."""
    if not is_usable_image(url):
        return None
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix or ".png"
    stem = Path(parsed.path).stem or "task1"
    filename = f"{test_id}_task1_{stem}{suffix}"
    out_path = IMAGE_DIR / filename
    if not out_path.exists():
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        context = ssl._create_unverified_context() if insecure else None
        with urllib.request.urlopen(url, timeout=30, context=context) as resp:
            out_path.write_bytes(resp.read())
        print(f"  downloaded {filename}")
    return f"images/{filename}"


def build_task(node: dict[str, Any], task_no: int, test_id: str, insecure: bool) -> dict[str, Any]:
    image = None
    if task_no == 1:
        image = localize_image(node.get("img_url") or "", test_id, insecure)
    return {
        "task": task_no,
        "paper_id": node.get("paper_id"),
        "kind": node.get("kind") or ("xiaozuowen" if task_no == 1 else "dazuowen"),
        "kind_name": node.get("kind_name") or ("小作文" if task_no == 1 else "大作文"),
        "prompt": clean_text(node.get("content")),
        "image": image,
        "min_words": TASK_MIN_WORDS[task_no],
    }


def build_test(book: int, test_no: int, writing: dict[str, Any], insecure: bool) -> dict[str, Any] | None:
    xiaozuowen = writing.get("xiaozuowen")
    dazuowen = writing.get("dazuowen")
    if not isinstance(xiaozuowen, dict) or not isinstance(dazuowen, dict):
        return None
    test_id = f"ielts{book}_test{test_no}_writing"
    tasks = [
        build_task(xiaozuowen, 1, test_id, insecure),
        build_task(dazuowen, 2, test_id, insecure),
    ]
    return {
        "id": test_id,
        "book": book,
        "test": test_no,
        "title": f"Cambridge IELTS {book} Test {test_no} Writing",
        "source": "idictation_xyy",
        "generated_at": datetime.now(UTC).isoformat(),
        "tasks": tasks,
    }


def iter_writing_tests(raw: dict[str, Any]):
    books = ((raw.get("catalog") or {}).get("values") or {}).get("books") or []
    for book_node in books:
        book = first_int(book_node.get("book_id"), book_node.get("name"))
        for child in book_node.get("children") or []:
            test_no = first_int(child.get("name"), child.get("test_id"))
            writing = child.get("writing")
            if not book or not test_no or not isinstance(writing, dict):
                continue
            yield book, test_no, writing


def main() -> None:
    global IMAGE_DIR
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument(
        "--insecure",
        action="store_true",
        default=True,
        help="use an unverified SSL context when downloading images (default on)",
    )
    parser.add_argument("--secure", dest="insecure", action="store_false")
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR = args.output_dir / "images"

    catalog: dict[int, list[dict[str, Any]]] = {}
    written = 0
    for book, test_no, writing in iter_writing_tests(raw):
        payload = build_test(book, test_no, writing, args.insecure)
        if payload is None:
            print(f"skip ielts{book}_test{test_no}: writing tasks incomplete")
            continue
        out_path = args.output_dir / f"{payload['id']}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        has_image = bool(payload["tasks"][0].get("image"))
        catalog.setdefault(book, []).append(
            {
                "id": payload["id"],
                "book": book,
                "test": test_no,
                "task_count": len(payload["tasks"]),
                "has_image": has_image,
            }
        )
        written += 1
        print(f"Wrote {out_path} (2 tasks, task1 image: {has_image})")

    catalog_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "books": [
            {"book": book, "tests": sorted(rows, key=lambda row: row["test"])}
            for book, rows in sorted(catalog.items())
        ],
    }
    (args.output_dir / "catalog.json").write_text(
        json.dumps(catalog_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {args.output_dir / 'catalog.json'} ({written} tests)")


if __name__ == "__main__":
    main()
