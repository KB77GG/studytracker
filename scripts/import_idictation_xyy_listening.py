#!/usr/bin/env python3
"""Import idictation xyy IELTS listening parts into local listening assets.

The script fetches the Cambridge IELTS listening catalog, downloads each part
audio file, and writes JSON in the format used by /listening/<exercise_id>.

Authentication is supplied at runtime via --cookie or IDICTATION_COOKIE.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import random
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


BASE_URL = "https://www.idictation.cn"
SECRET = "idictation_2024"
DEFAULT_BOOKS = "4-20"


def parse_books(value: str) -> set[int]:
    books: set[int] = set()
    for chunk in (value or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            books.update(range(int(start), int(end) + 1))
        else:
            books.add(int(chunk))
    return books


def signed_body(path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {k: v for k, v in (data or {}).items() if v is not None}
    body["api_key"] = urllib.parse.quote(path, safe="")
    body["timestamp"] = int(time.time())
    body["nonce"] = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(10))

    canonical_parts: list[str] = []
    for key in sorted(body):
        value = body[key]
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        canonical_parts.append(f"{key}={value}")
    canonical = "&".join(canonical_parts)
    body["sign"] = hmac.new(SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return body


def post_json(
    path: str,
    data: dict[str, Any] | None,
    cookie: str,
    timeout: int,
    insecure: bool = False,
) -> dict[str, Any]:
    payload = json.dumps(signed_body(path, data), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Cookie": cookie,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/main/book",
            "User-Agent": "Mozilla/5.0",
        },
    )
    context = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        raw = response.read().decode("utf-8")
    decoded = json.loads(raw)
    if decoded.get("status"):
        raise RuntimeError(f"{path} failed: {decoded.get('message') or decoded.get('status')}")
    return decoded


def values_of(response: dict[str, Any]) -> Any:
    return response.get("values") if isinstance(response, dict) else None


def collect_catalog_parts(catalog_values: dict[str, Any], allowed_books: set[int]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for book in catalog_values.get("books") or []:
        book_id = book.get("book_id")
        if book_id not in allowed_books:
            continue
        for test in book.get("children") or []:
            test_name = str(test.get("name") or "")
            match = re.search(r"\d+", test_name)
            if not match:
                continue
            test_number = int(match.group())
            listening = test.get("listening") if isinstance(test.get("listening"), dict) else test
            for part in listening.get("children") or []:
                title = str(part.get("title") or part.get("name") or "")
                part_match = re.search(r"\d+", title)
                if not part_match:
                    continue
                section = int(part_match.group())
                part_id = part.get("id")
                if not part_id:
                    continue
                entries.append(
                    {
                        "book": int(book_id),
                        "test": test_number,
                        "section": section,
                        "part_id": int(part_id),
                        "title": title,
                    }
                )
    return sorted(entries, key=lambda item: (item["book"], item["test"], item["section"]))


def exercise_id(entry: dict[str, Any]) -> str:
    return f"ielts{entry['book']}_test{entry['test']}_s{entry['section']}"


def normalize_segment(item: dict[str, Any], index: int) -> dict[str, Any]:
    start_ms = item.get("start_time") or 0
    end_ms = item.get("end_time") or 0
    return {
        "id": index + 1,
        "start": round(float(start_ms) / 1000.0, 2),
        "end": round(float(end_ms) / 1000.0, 2),
        "text": str(item.get("en_text") or "").strip(),
        "translation": str(item.get("cn_text") or "").strip(),
        "source_order": item.get("order", index),
        "source_start_time": start_ms,
        "source_end_time": end_ms,
    }


def build_player_payload(entry: dict[str, Any], part_values: dict[str, Any], audio_name: str) -> dict[str, Any]:
    section = entry["section"]
    segments = [
        normalize_segment(item, index)
        for index, item in enumerate(part_values.get("content") or [])
        if isinstance(item, dict) and (item.get("en_text") or "").strip()
    ]
    ex_id = exercise_id(entry)
    return {
        "id": ex_id,
        "title": f"Cambridge IELTS {entry['book']} Test {entry['test']} Section {section}",
        "audio": audio_name,
        "source": {
            "provider": "idictation_xyy",
            "paper_id": part_values.get("paper_id") or entry["part_id"],
            "file_url": part_values.get("file_url") or "",
            "jianya_name": part_values.get("jianya_name") or "",
            "test_name": part_values.get("test_name") or "",
            "title": part_values.get("title") or "",
        },
        "parts": [
            {
                "name": f"Section {section}",
                "segments": segments,
            }
        ],
    }


def download_file(url: str, target: Path, timeout: int, retries: int, insecure: bool) -> None:
    if target.exists() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    context = ssl._create_unverified_context() if insecure else None
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            temp.unlink(missing_ok=True)
            started_at = time.monotonic()
            with urllib.request.urlopen(url, timeout=timeout, context=context) as response:
                with temp.open("wb") as output:
                    while True:
                        if time.monotonic() - started_at > timeout:
                            raise TimeoutError(f"download exceeded {timeout}s")
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        output.write(chunk)
            temp.replace(target)
            return
        except Exception as exc:
            last_error = exc
            temp.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"download failed {url}: {last_error}")


def read_raw(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"catalog": None, "parts": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import idictation xyy IELTS listening assets.")
    parser.add_argument("--cookie", default=os.environ.get("IDICTATION_COOKIE", ""), help="Login cookie; defaults to IDICTATION_COOKIE.")
    parser.add_argument("--books", default=DEFAULT_BOOKS, help="Book range/list, e.g. 4-20 or 11,12.")
    parser.add_argument("--raw", default="data/idictation_xyy_listening/raw.json")
    parser.add_argument("--output-dir", default="static/listening")
    parser.add_argument("--only", default="", help="Comma-separated exercise ids to import, e.g. ielts11_test1_s1.")
    parser.add_argument("--no-fetch", action="store_true", help="Use existing --raw without calling idictation APIs.")
    parser.add_argument("--no-download", action="store_true", help="Write JSON only; do not download audio.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing JSON files.")
    parser.add_argument("--redownload", action="store_true", help="Force redownload even when audio already exists.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--insecure", action="store_true", help="Skip TLS verification for audio downloads.")
    args = parser.parse_args()

    raw_path = Path(args.raw)
    raw = read_raw(raw_path)
    allowed_books = parse_books(args.books)

    if not args.no_fetch:
        if not args.cookie:
            raise SystemExit("Missing cookie. Pass --cookie or set IDICTATION_COOKIE.")
        catalog = post_json(
            "/api/study/zhenti/v1/combined/jianya/list",
            {},
            args.cookie,
            args.timeout,
            args.insecure,
        )
        raw["catalog"] = catalog
        catalog_values = values_of(catalog)
        if not isinstance(catalog_values, dict):
            raise SystemExit("Catalog response missing values.")
        entries = collect_catalog_parts(catalog_values, allowed_books)
    else:
        catalog_values = values_of(raw.get("catalog") or {})
        if not isinstance(catalog_values, dict):
            raise SystemExit("Raw catalog missing. Run without --no-fetch first.")
        entries = collect_catalog_parts(catalog_values, allowed_books)

    only = {item.strip() for item in args.only.split(",") if item.strip()}
    if only:
        entries = [entry for entry in entries if exercise_id(entry) in only]

    output_dir = Path(args.output_dir)
    raw.setdefault("parts", {})
    imported: list[dict[str, Any]] = []

    total = len(entries)
    for index, entry in enumerate(entries, 1):
        ex_id = exercise_id(entry)
        json_path = output_dir / f"{ex_id}.json"
        audio_name = f"{ex_id}.mp3"
        audio_path = output_dir / audio_name
        print(f"[{index}/{total}] {ex_id} part_id={entry['part_id']}")

        part_key = str(entry["part_id"])
        if not args.no_fetch and (args.overwrite or part_key not in raw["parts"]):
            raw["parts"][part_key] = post_json(
                f"/api/study/zhenti/v1/xyy/part/show/{entry['part_id']}",
                {},
                args.cookie,
                args.timeout,
                args.insecure,
            )
            time.sleep(args.sleep)

        part_response = raw["parts"].get(part_key)
        part_values = values_of(part_response or {})
        if not isinstance(part_values, dict):
            print(f"  skip: missing part values")
            continue

        file_url = part_values.get("file_url") or ""
        if file_url and not args.no_download:
            if args.redownload and audio_path.exists():
                audio_path.unlink()
            download_file(file_url, audio_path, args.timeout, args.retries, args.insecure)

        payload = build_player_payload(entry, part_values, audio_name)
        if args.overwrite or not json_path.exists():
            write_json(json_path, payload)
        imported.append(
            {
                "exercise_id": ex_id,
                "part_id": entry["part_id"],
                "segments": len(payload["parts"][0]["segments"]),
                "audio": audio_name,
                "source_url": file_url,
            }
        )

    write_json(raw_path, raw)
    write_json(Path("data/idictation_xyy_listening/import_report.json"), imported)
    print(f"imported {len(imported)} exercises")
    print(f"raw: {raw_path}")
    print("report: data/idictation_xyy_listening/import_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
