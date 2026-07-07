#!/usr/bin/env python3
"""Prepare 9分达人雅思听力6 source assets for the import pipeline.

- Copies the 24 source mp3 files into data/jfdr6/audio/ with canonical
  names jfdr6_test{N}_s{S}.mp3 (Test 6 files lack the "Test 6" prefix and
  some carry a leading space, so parsing is per-directory).
- Validates the result with ffprobe: exactly 24 files, sane durations.
- Optionally renders the scanned PDF into per-page JPEGs for the visual
  extraction step (data/jfdr6/pages/, not tracked by git).

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
SOURCE_ROOT = Path(
    "/Users/zhouxin/Desktop/工作/资料/9分达人听力/《9分达人雅思听力真题还原及解析6》"
)
PDF_NAME = "9分达人雅思听力真题还原及解析6（208页）.pdf"
AUDIO_OUT = PROJECT_ROOT / "data" / "jfdr6" / "audio"
PAGES_OUT = PROJECT_ROOT / "data" / "jfdr6" / "pages"
MANIFEST_OUT = PROJECT_ROOT / "data" / "jfdr6" / "audio_manifest.json"

PART_RE = re.compile(r"part\s*(\d)", re.IGNORECASE)
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


def collect_audio() -> list[dict]:
    entries = []
    for test_no in range(1, 7):
        test_dir = SOURCE_ROOT / f"Test {test_no}"
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
                    "id": f"jfdr6_test{test_no}_s{part_no}",
                    "test": test_no,
                    "section": part_no,
                    "source": str(src),
                }
            )
    return entries


def copy_and_validate(entries: list[dict]) -> None:
    AUDIO_OUT.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        dest = AUDIO_OUT / f"{entry['id']}.mp3"
        if not dest.exists():
            shutil.copy2(entry["source"], dest)
        duration = probe_duration(dest)
        if not MIN_DURATION_S <= duration <= MAX_DURATION_S:
            raise SystemExit(
                f"{dest.name}: duration {duration:.1f}s outside sane range"
            )
        entry["dest"] = str(dest.relative_to(PROJECT_ROOT))
        entry["duration"] = round(duration, 2)
    MANIFEST_OUT.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"OK: {len(entries)} audio files -> {AUDIO_OUT.relative_to(PROJECT_ROOT)}")
    print(f"manifest: {MANIFEST_OUT.relative_to(PROJECT_ROOT)}")


def render_pdf(dpi: int = 150) -> None:
    pdf = SOURCE_ROOT / PDF_NAME
    if not pdf.exists():
        raise SystemExit(f"missing PDF: {pdf}")
    PAGES_OUT.mkdir(parents=True, exist_ok=True)
    existing = len(list(PAGES_OUT.glob("page-*.jpg")))
    if existing >= 208:
        print(f"pages already rendered ({existing}), skip")
        return
    subprocess.run(
        [
            "pdftoppm",
            "-jpeg",
            "-r",
            str(dpi),
            str(pdf),
            str(PAGES_OUT / "page"),
        ],
        check=True,
    )
    count = len(list(PAGES_OUT.glob("page-*.jpg")))
    print(f"OK: rendered {count} pages -> {PAGES_OUT.relative_to(PROJECT_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-pdf", action="store_true", help="also render PDF pages")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    entries = collect_audio()
    copy_and_validate(entries)
    if args.render_pdf:
        render_pdf(args.dpi)


if __name__ == "__main__":
    sys.exit(main())
