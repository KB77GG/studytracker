#!/usr/bin/env python3
"""Audit and losslessly remux listening MP3 files with missing seek headers."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

SEEK_MARKERS = (b"Xing", b"Info")


@dataclass(frozen=True)
class ProbeResult:
    path: str
    declared_duration: float
    packet_duration: float
    duration_drift: float
    id3_bytes: int
    has_seek_index: bool


def _run(*args: str) -> str:
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _declared_duration(path: Path) -> float:
    output = _run(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        str(path),
    )
    return float(output)


def _packet_duration(path: Path) -> float:
    output = _run(
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_packets",
        "-show_entries",
        "packet=pts_time,duration_time",
        "-of",
        "json",
        str(path),
    )
    packets = json.loads(output).get("packets") or []
    timed_packets = [
        packet
        for packet in packets
        if packet.get("pts_time") is not None and packet.get("duration_time") is not None
    ]
    if not timed_packets:
        raise ValueError(f"no audio packets: {path}")
    last = timed_packets[-1]
    return float(last["pts_time"]) + float(last["duration_time"])


def _id3_size_and_seek_index(path: Path) -> tuple[int, bool]:
    with path.open("rb") as stream:
        header = stream.read(10)
        id3_bytes = 0
        if header[:3] == b"ID3" and len(header) == 10:
            id3_bytes = 10 + sum(
                (header[6 + index] & 0x7F) << (7 * (3 - index)) for index in range(4)
            )
        stream.seek(id3_bytes)
        first_frames = stream.read(512)
    return id3_bytes, any(marker in first_frames for marker in SEEK_MARKERS)


def probe(path: Path) -> ProbeResult:
    declared = _declared_duration(path)
    packets = _packet_duration(path)
    id3_bytes, indexed = _id3_size_and_seek_index(path)
    return ProbeResult(
        path=str(path),
        declared_duration=round(declared, 6),
        packet_duration=round(packets, 6),
        duration_drift=round(packets - declared, 6),
        id3_bytes=id3_bytes,
        has_seek_index=indexed,
    )


def remux(source: Path, destination: Path) -> ProbeResult:
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map_metadata",
            "-1",
            "-c:a",
            "copy",
            "-write_xing",
            "1",
            str(destination),
        ],
        check=True,
    )
    result = probe(destination)
    if not result.has_seek_index:
        raise ValueError(f"seek index was not created: {destination}")
    if abs(result.duration_drift) > 0.05:
        raise ValueError(
            f"declared/packet duration still differs by {result.duration_drift}s: " f"{destination}"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repair-missing-index", action="store_true")
    args = parser.parse_args()

    source_paths = sorted(args.root.glob("*.mp3"))
    before = [probe(path) for path in source_paths]
    targets = [result for result in before if not result.has_seek_index]
    repaired: list[dict] = []

    if args.repair_missing_index:
        if args.output_dir is None:
            parser.error("--output-dir is required with --repair-missing-index")
        for index, target in enumerate(targets, start=1):
            source = Path(target.path)
            destination = args.output_dir / source.name
            after = remux(source, destination)
            if abs(after.packet_duration - target.packet_duration) > 0.05:
                raise ValueError(
                    f"packet duration changed for {source.name}: "
                    f"{target.packet_duration} -> {after.packet_duration}"
                )
            repaired.append({"before": asdict(target), "after": asdict(after)})
            print(f"[{index}/{len(targets)}] {source.name}")

    manifest = {
        "root": str(args.root),
        "checked": len(before),
        "missing_seek_index": len(targets),
        "duration_drift_over_0_25": sum(result.duration_drift > 0.25 for result in before),
        "targets": [asdict(result) for result in targets],
        "repaired": repaired,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in ("checked", "missing_seek_index", "duration_drift_over_0_25")
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
