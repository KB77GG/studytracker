#!/usr/bin/env python3
"""
Normalize IELTS audio filenames into a stable mapping manifest.

This script does not rename the user's original files. It creates symlinks
under data/ielts_audio_normalized/ and writes a manifest JSON file that maps:
  - transcript coordinates: cam / text_test / section
  - display coordinates: cam / display_test / section
  - source path and normalized audio path

Usage:
    python scripts/normalize_ielts_audio.py
    python scripts/normalize_ielts_audio.py --source ~/Desktop/精听材料库/音频
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = Path("/Users/zhouxin/Desktop/精听材料库/音频")
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "ielts_audio_normalized"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "ielts_audio_manifest.json"

ROMAN = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
}

WORD_NUMS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
}


def cam_from_path(path: Path) -> int | None:
    text = str(path)
    match = re.search(r"剑桥?\s*(\d+)|剑\s*(\d+)|IELTS\s*(\d+)", text, re.I)
    if match:
        for group in match.groups():
            if group:
                return int(group)

    match = re.search(r"(?:^|[\\/])(?:[A-Za-z])?(\d+)\s*音频", text, re.I)
    if match:
        return int(match.group(1))

    return None


def direct_parse(path: Path) -> dict | None:
    stem = path.stem.strip()
    patterns = [
        re.compile(r"^C(?P<cam>\d+)T(?P<test>\d+)S(?P<section>\d+)$", re.I),
        re.compile(r"^C(?P<cam>\d+)-T(?P<test>\d+)-P(?P<section>\d+)$", re.I),
        re.compile(r"^T(?P<test>\d+)S(?P<section>\d+)$", re.I),
        re.compile(r"^Test(?P<test>\d+)-s(?P<section>\d+)$", re.I),
        re.compile(r"^Test(?P<test>\d+)_section(?P<section>\d+)$", re.I),
        re.compile(r"^IELTS\s*(?P<cam>\d+)\s*Test\s*(?P<test>\d+)_S(?P<section>\d+)$", re.I),
        re.compile(r"^IELTS(?P<cam>\d+)_Test(?P<test>\d+)_Section(?P<section>\d+)$", re.I),
        re.compile(r"^IELTS(?P<cam>\d+)_Test(?P<test>\d+)\.Section(?P<section>\d+)$", re.I),
        re.compile(r"^IELTS\s*(?P<cam>\d+)\s*Test\s*(?P<test>\d+)_(?P<section>\d+)$", re.I),
        re.compile(r"^IELTS(?P<cam>\d+)_test(?P<test>\d+)_audio(?P<section>\d+)$", re.I),
    ]
    for pattern in patterns:
        match = pattern.match(stem)
        if not match:
            continue
        groups = match.groupdict()
        cam = int(groups.get("cam") or cam_from_path(path) or 0)
        test = int(groups["test"])
        section = int(groups["section"])
        return {
            "cam": cam,
            "text_test": test,
            "display_test": test,
            "section": section,
        }

    match = re.match(r"^Test\s+([0-9]+|[IVX]+)\s+Section\s*([0-9]+)\s*$", stem, re.I)
    if match:
        raw_test = match.group(1)
        test = int(raw_test) if raw_test.isdigit() else ROMAN[raw_test.lower()]
        return {
            "cam": cam_from_path(path),
            "text_test": test,
            "display_test": test,
            "section": int(match.group(2)),
        }

    match = re.match(r"^Test\s+([0-9]+|[IVX]+)\s+Part\s*([0-9]+)\s*$", stem, re.I)
    if match:
        raw_test = match.group(1)
        test = int(raw_test) if raw_test.isdigit() else ROMAN[raw_test.lower()]
        return {
            "cam": cam_from_path(path),
            "text_test": test,
            "display_test": test,
            "section": int(match.group(2)),
        }

    match = re.match(r"^Test([0-9]+|[IVX]+)\s+Part([0-9]+)\s*$", stem, re.I)
    if match:
        raw_test = match.group(1)
        test = int(raw_test) if raw_test.isdigit() else ROMAN[raw_test.lower()]
        return {
            "cam": cam_from_path(path),
            "text_test": test,
            "display_test": test,
            "section": int(match.group(2)),
        }

    match = re.match(
        r"^\d+\s+Test\s+(One|Two|Three|Four)-Section\s+(One|Two|Three|Four)$",
        stem,
        re.I,
    )
    if match:
        return {
            "cam": cam_from_path(path),
            "text_test": WORD_NUMS[match.group(1).lower()],
            "display_test": WORD_NUMS[match.group(1).lower()],
            "section": WORD_NUMS[match.group(2).lower()],
        }

    return None


def special_parse(path: Path) -> dict | None:
    cam = cam_from_path(path)
    if cam == 12:
        parsed = direct_parse(path)
        if parsed:
            parsed["text_test"] = parsed["display_test"] - 4
            return parsed

    if cam == 13:
        match = re.match(r"^IELTS13-Tests1-4CD([12])Track_(\d+)$", path.stem, re.I)
        if match:
            cd = int(match.group(1))
            track = int(match.group(2))
            zero_based = (cd - 1) * 8 + (track - 1)
            return {
                "cam": 13,
                "text_test": zero_based // 4 + 1,
                "display_test": zero_based // 4 + 1,
                "section": zero_based % 4 + 1,
            }

    if cam == 10:
        parent = path.parent.name.lower()
        match = re.match(r"^(\d+)\s+音频轨道$", path.stem)
        if match and parent.startswith("cd "):
            cd = int(parent.split()[-1])
            track = int(match.group(1))
            zero_based = (cd - 1) * 8 + (track - 1)
            return {
                "cam": 10,
                "text_test": zero_based // 4 + 1,
                "display_test": zero_based // 4 + 1,
                "section": zero_based % 4 + 1,
            }

    return None


def parse_audio(path: Path) -> dict | None:
    return special_parse(path) or direct_parse(path)


def normalized_name(meta: dict, suffix: str) -> str:
    return (
        f"cam{meta['cam']:02d}_texttest{meta['text_test']}_"
        f"displaytest{meta['display_test']}_section{meta['section']}{suffix.lower()}"
    )


def ensure_symlink(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink() and dest.resolve() == src.resolve():
            return
        dest.unlink()
    dest.symlink_to(src)


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize IELTS audio filenames")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="source audio root")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="normalized output dir")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="manifest json path")
    args = parser.parse_args()

    source_root = Path(args.source).expanduser()
    output_root = Path(args.output).expanduser()
    manifest_path = Path(args.manifest).expanduser()

    audio_files = sorted(
        p for p in source_root.rglob("*") if p.is_file() and p.suffix.lower() in {".mp3", ".m4a", ".aiff"}
    )

    entries: list[dict] = []
    unresolved: list[str] = []
    seen: set[tuple[int, int, int]] = set()

    for audio in audio_files:
        meta = parse_audio(audio)
        if not meta or not meta.get("cam"):
            unresolved.append(str(audio))
            continue

        key = (meta["cam"], meta["display_test"], meta["section"])
        if key in seen:
            unresolved.append(str(audio))
            continue
        seen.add(key)

        normalized = output_root / normalized_name(meta, audio.suffix)
        ensure_symlink(audio, normalized)
        entries.append(
            {
                **meta,
                "source_path": str(audio),
                "normalized_path": str(normalized),
                "extension": audio.suffix.lower(),
            }
        )

    payload = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "entries": sorted(entries, key=lambda e: (e["cam"], e["display_test"], e["section"])),
        "unresolved": unresolved,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"normalized: {len(entries)}")
    print(f"unresolved: {len(unresolved)}")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
