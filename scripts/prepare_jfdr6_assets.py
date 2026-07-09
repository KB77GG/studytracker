#!/usr/bin/env python3
"""Prepare 9分达人雅思听力 source assets for the import pipeline.

- Copies source mp3 files into data/jfdr{book}/audio/ with canonical
  names jfdr{book}_test{N}_s{S}.mp3 (Test 6 files lack the "Test 6" prefix and
  some carry a leading space, so parsing is per-directory).
- Validates the result with ffprobe: sane durations and exactly 4 parts per test.
- Optionally renders the scanned PDF into per-page JPEGs for the visual
  extraction step (data/jfdr{book}/pages/, not tracked by git).

Usage:
    python scripts/prepare_jfdr6_assets.py            # audio only
    python scripts/prepare_jfdr6_assets.py --render-pdf
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_ROOT = Path(
    "/Users/zhouxin/Desktop/工作/资料/9分达人听力/《9分达人雅思听力真题还原及解析6》"
)
DEFAULT_PDF_NAME = "9分达人雅思听力真题还原及解析6（208页）.pdf"

PART_RE = re.compile(r"(?:part|p)\s*(\d)", re.IGNORECASE)
MIN_DURATION_S = 5 * 60
MAX_DURATION_S = 13 * 60


def probe_duration(path: Path) -> float:
    out = subprocess.run(
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
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


def _jfdr_root(book: int) -> Path:
    return PROJECT_ROOT / "data" / f"jfdr{book}"


def _count_pdf_pages(pdf: Path) -> int | None:
    try:
        out = subprocess.run(
            ["pdfinfo", str(pdf)],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    for line in out.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return None


def collect_audio(source_root: Path, book: int, tests: int) -> list[dict]:
    entries = []
    for test_no in range(1, tests + 1):
        test_dir = source_root / f"Test {test_no}"
        if not test_dir.is_dir():
            raise SystemExit(f"missing source dir: {test_dir}")
        mp3s = [p for p in test_dir.iterdir() if p.suffix.lower() == ".mp3"]
        parts: dict[int, Path] = {}
        for p in mp3s:
            match = PART_RE.search(p.stem.strip())
            if not match:
                raise SystemExit(f"cannot parse part number from: {p}")
            part_no = int(match.group(1))
            if part_no in parts:
                raise SystemExit(f"duplicate part {part_no} in {test_dir}")
            parts[part_no] = p
        if sorted(parts) != [1, 2, 3, 4]:
            raise SystemExit(f"Test {test_no}: expected parts 1-4, got {sorted(parts)}")
        for part_no, src in sorted(parts.items()):
            entries.append(
                {
                    "id": f"jfdr{book}_test{test_no}_s{part_no}",
                    "test": test_no,
                    "section": part_no,
                    "source": str(src),
                }
            )
    return entries


def copy_and_validate(entries: list[dict], audio_out: Path, manifest_out: Path) -> None:
    audio_out.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        dest = audio_out / f"{entry['id']}.mp3"
        if not dest.exists():
            shutil.copy2(entry["source"], dest)
        duration = probe_duration(dest)
        if not MIN_DURATION_S <= duration <= MAX_DURATION_S:
            raise SystemExit(
                f"{dest.name}: duration {duration:.1f}s outside sane range"
            )
        entry["dest"] = str(dest.relative_to(PROJECT_ROOT))
        entry["duration"] = round(duration, 2)
    manifest_out.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OK: {len(entries)} audio files -> {audio_out.relative_to(PROJECT_ROOT)}")
    print(f"manifest: {manifest_out.relative_to(PROJECT_ROOT)}")


def render_pdf(source_root: Path, pdf_name: str, pages_out: Path, dpi: int = 150) -> None:
    pdf = source_root / pdf_name
    if not pdf.exists():
        raise SystemExit(f"missing PDF: {pdf}")
    pages_out.mkdir(parents=True, exist_ok=True)
    existing = len(list(pages_out.glob("page-*.jpg")))
    expected = _count_pdf_pages(pdf)
    if existing and (expected is None or existing >= expected):
        print(f"pages already rendered ({existing}), skip")
        return
    subprocess.run(
        [
            "pdftoppm",
            "-jpeg",
            "-r",
            str(dpi),
            str(pdf),
            str(pages_out / "page"),
        ],
        check=True,
    )
    count = len(list(pages_out.glob("page-*.jpg")))
    print(f"OK: rendered {count} pages -> {pages_out.relative_to(PROJECT_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", type=int, default=6, help="9分达人听力 book number")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_ROOT,
                        help="source directory containing Test N folders and the PDF")
    parser.add_argument("--tests", type=int, default=6, help="number of tests to import")
    parser.add_argument("--pdf-name", default=DEFAULT_PDF_NAME, help="source PDF filename")
    parser.add_argument("--render-pdf", action="store_true", help="also render PDF pages")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    jfdr_root = _jfdr_root(args.book)
    entries = collect_audio(args.source, args.book, args.tests)
    copy_and_validate(
        entries,
        audio_out=jfdr_root / "audio",
        manifest_out=jfdr_root / "audio_manifest.json",
    )
    if args.render_pdf:
        render_pdf(args.source, args.pdf_name, jfdr_root / "pages", args.dpi)


if __name__ == "__main__":
    sys.exit(main())
