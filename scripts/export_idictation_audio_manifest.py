#!/usr/bin/env python3
"""Export or download audio files referenced by an idictation listening raw dump."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import ssl
import subprocess
import urllib.request
from pathlib import Path
from typing import Any


def safe_slug(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def unwrap(response: dict[str, Any]) -> dict[str, Any]:
    values = response.get("values")
    return values if isinstance(values, dict) else {}


def part_num(title: str) -> str:
    match = re.search(r"\d+", title or "")
    return match.group() if match else "0"


def build_manifest(raw: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    for response in (raw.get("parts") or {}).values():
        if not isinstance(response, dict):
            continue
        values = unwrap(response)
        url = values.get("file_url")
        if not url or url in seen:
            continue
        seen.add(url)

        in_book = values.get("in_book")
        test_name = values.get("test_name") or ""
        title = values.get("title") or ""
        paper_id = values.get("paper_id")
        filename = (
            f"jijing_{safe_slug(in_book)}_"
            f"{safe_slug(test_name)}_"
            f"part_{safe_slug(part_num(title))}_"
            f"{safe_slug(paper_id)}.mp3"
        )

        entries.append(
            {
                "in_book": in_book,
                "test_name": test_name,
                "part_title": title,
                "paper_id": paper_id,
                "question_name": values.get("question_name") or "",
                "question_type": values.get("question_type") or "",
                "url": url,
                "filename": filename,
                "local_path": f"audio/{filename}",
            }
        )

    return sorted(
        entries,
        key=lambda x: (
            int(x["in_book"]) if str(x["in_book"]).isdigit() else 999999,
            str(x["test_name"]),
            int(part_num(x["part_title"])),
        ),
    )


def download(
    entries: list[dict[str, Any]],
    audio_dir: Path,
    insecure: bool = False,
    timeout: int = 180,
    retries: int = 3,
    use_curl: bool = False,
) -> None:
    audio_dir.mkdir(parents=True, exist_ok=True)
    context = ssl._create_unverified_context() if insecure else None
    total = len(entries)
    for index, entry in enumerate(entries, 1):
        target = audio_dir / entry["filename"]
        if target.exists() and target.stat().st_size > 0:
            print(f"[{index}/{total}] skip {target.name}")
            continue

        temp_target = target.with_suffix(target.suffix + ".part")
        try:
            temp_target.unlink(missing_ok=True)
        except TypeError:
            if temp_target.exists():
                temp_target.unlink()

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            print(f"[{index}/{total}] download {target.name} attempt {attempt}/{retries}")
            try:
                if use_curl:
                    command = [
                        "curl",
                        "-L",
                        "--fail",
                        "--connect-timeout",
                        "20",
                        "--max-time",
                        str(timeout),
                        "--output",
                        str(temp_target),
                        entry["url"],
                    ]
                    if insecure:
                        command.insert(1, "-k")
                    subprocess.run(command, check=True)
                else:
                    with urllib.request.urlopen(entry["url"], timeout=timeout, context=context) as response:
                        with temp_target.open("wb") as output:
                            shutil.copyfileobj(response, output)
                temp_target.replace(target)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                try:
                    temp_target.unlink(missing_ok=True)
                except TypeError:
                    if temp_target.exists():
                        temp_target.unlink()
                if attempt == retries:
                    raise
                print(f"  retry after error: {exc}")

        if last_error is not None:
            raise last_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="/Users/zhouxin/Desktop/idictation_listening_jijing_raw.json")
    parser.add_argument("--output", default="data/idictation_listening_jijing/audio_manifest.json")
    parser.add_argument("--urls-output", default="data/idictation_listening_jijing/audio_urls.txt")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--audio-dir", default="data/idictation_listening_jijing/audio")
    parser.add_argument("--insecure", action="store_true", help="Skip TLS certificate verification for audio downloads.")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--use-curl", action="store_true", help="Use the system curl command for downloads.")
    args = parser.parse_args()

    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    entries = build_manifest(raw)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    urls_output = Path(args.urls_output)
    urls_output.parent.mkdir(parents=True, exist_ok=True)
    urls_output.write_text("\n".join(entry["url"] for entry in entries) + "\n", encoding="utf-8")

    if args.download:
        download(
            entries,
            Path(args.audio_dir),
            insecure=args.insecure,
            timeout=args.timeout,
            retries=args.retries,
            use_curl=args.use_curl,
        )

    print(f"{len(entries)} audio urls")
    print(output)
    print(urls_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
