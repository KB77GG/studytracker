#!/usr/bin/env python3
"""Build all 16 Cambridge IELTS 20 intensive-listening assets in XDF style."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

try:
    from scripts.build_xdf_intensive_pilot import (
        ORIGINAL_AUDIO_BACKUP,
        ROOT,
        build_dialogue_audio,
        build_pilot_payload,
        fetch_xdf_payload,
    )
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root.
    from build_xdf_intensive_pilot import (  # type: ignore[no-redef]
        ORIGINAL_AUDIO_BACKUP,
        ROOT,
        build_dialogue_audio,
        build_pilot_payload,
        fetch_xdf_payload,
    )


@dataclass(frozen=True)
class SectionSpec:
    test: int
    section: int
    qid: int

    @property
    def asset_id(self) -> str:
        return f"ielts20_test{self.test}_s{self.section}"


SECTIONS = (
    SectionSpec(1, 1, 1817),
    SectionSpec(1, 2, 1819),
    SectionSpec(1, 3, 1820),
    SectionSpec(1, 4, 1821),
    SectionSpec(2, 1, 1834),
    SectionSpec(2, 2, 1823),
    SectionSpec(2, 3, 1824),
    SectionSpec(2, 4, 1825),
    SectionSpec(3, 1, 1826),
    SectionSpec(3, 2, 1827),
    SectionSpec(3, 3, 1828),
    SectionSpec(3, 4, 1829),
    SectionSpec(4, 1, 1830),
    SectionSpec(4, 2, 1831),
    SectionSpec(4, 3, 1832),
    SectionSpec(4, 4, 1833),
)

# Each source MP3 was compared with the corresponding public XDF audio at
# 2 kHz.  These offsets are the correlation peaks for the continuous dialogue
# regions and avoid inheriting noisy sentence boundaries from the old data.
REGION_OFFSETS_SECONDS: dict[int, tuple[float, ...]] = {
    1817: (40.645, 87.412),
    1819: (72.475, 109.742),
    1820: (57.208, 104.742),
    1821: (73.686,),
    1823: (55.342, 102.442),
    1824: (48.909, 100.742),
    1825: (90.520,),
    1826: (53.099, 103.800),
    1827: (75.341, 122.242),
    1828: (69.375, 105.376),
    1829: (74.921,),
    1830: (51.506, 86.707),
    1831: (51.475, 102.875),
    1832: (47.075, 114.742),
    1833: (87.786,),
    1834: (41.970, 87.870),
}


def _source_audio_name(spec: SectionSpec) -> str:
    if spec == SECTIONS[0]:
        return ORIGINAL_AUDIO_BACKUP
    return f"{spec.asset_id}.mp3"


def build_all(source_dir: Path, output_dir: Path, *, skip_audio: bool = False) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_cache_dir = output_dir / "xdf_source"
    source_cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for spec in SECTIONS:
        source_json = source_dir / f"{spec.asset_id}.json"
        source_audio_name = _source_audio_name(spec)
        source_audio = source_dir / source_audio_name
        output_audio_name = f"{spec.asset_id}_xdf_20260813.mp3"
        output_json = output_dir / f"{spec.asset_id}.json"
        output_audio = output_dir / output_audio_name

        source_payload = json.loads(source_json.read_text(encoding="utf-8"))
        source_cache = source_cache_dir / f"{spec.qid}.json"
        if source_cache.exists():
            xdf_payload = json.loads(source_cache.read_text(encoding="utf-8"))
        else:
            xdf_payload = fetch_xdf_payload(spec.qid)
            source_cache.write_text(
                json.dumps(xdf_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        built = build_pilot_payload(
            source_payload,
            xdf_payload,
            output_audio_name,
            asset_id=spec.asset_id,
            title=f"Cambridge IELTS 20 Test {spec.test} Section {spec.section}",
            part_name=f"Section {spec.section} · {len(xdf_payload.get('sentence') or [])}句",
            provider="xdf_ieltscat_mapped",
            generated_by="scripts/build_xdf_ielts20.py",
            qid=spec.qid,
            source_audio_file=source_audio_name,
            region_offsets=REGION_OFFSETS_SECONDS[spec.qid],
        )
        output_json.write_text(
            json.dumps(built, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if not skip_audio:
            build_dialogue_audio(
                source_audio,
                output_audio,
                built["source"]["mapping"]["clips"],
            )

        segments = built["parts"][0]["segments"]
        manifest.append(
            {
                "asset_id": spec.asset_id,
                "qid": spec.qid,
                "segments": len(segments),
                "tokens": built["source"]["mapping"]["token_count"],
                "duration": segments[-1]["end"],
                "audio": output_audio_name,
                "removed_gaps_seconds": built["source"]["mapping"]["removed_gaps_seconds"],
            }
        )
        print(
            f"{spec.asset_id}: {len(segments)} sentences, "
            f"{built['source']['mapping']['token_count']} tokens, "
            f"{segments[-1]['end']:.2f}s"
        )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(manifest_path)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=ROOT / "static/listening",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / ".tmp/ielts20_xdf_20260813",
    )
    parser.add_argument("--skip-audio", action="store_true")
    args = parser.parse_args()
    build_all(args.source_dir, args.output_dir, skip_audio=args.skip_audio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
