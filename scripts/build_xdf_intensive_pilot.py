#!/usr/bin/env python3
"""Build one XDF-style intensive-listening pilot from an existing IELTS asset.

The public XDF transcript uses an edited dialogue-only timeline.  This script
maps its sentence structure back to the existing local source audio, removes
the non-dialogue gap, and writes a separate preview asset without replacing
the original exercise.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
XDF_API_URL = "https://ieltscat.xdf.cn/api/newquestion/getIntensive"
XDF_PAGE_URL = "https://ieltscat.xdf.cn/intensive/intensive/1817/2/1"
SPEAKER_RE = re.compile(r"^(?:MAN|WOMAN):\s*", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]+")
PART_LABEL_RE = re.compile(r"^PART\s+\d+$", re.IGNORECASE)
ORIGINAL_AUDIO_BACKUP = "ielts20_test1_s1_pre_45sentence_20260813.mp3"


def normalized_tokens(text: str) -> list[str]:
    normalized = SPEAKER_RE.sub("", str(text or "").strip())
    normalized = normalized.replace("’", "'").replace("‘", "'")
    return TOKEN_RE.findall(normalized.lower())


def _dialogue_segments(payload: dict) -> list[dict]:
    segments = []
    for part in payload.get("parts") or []:
        for segment in part.get("segments") or []:
            text = str(segment.get("text") or "").strip()
            if text and not PART_LABEL_RE.fullmatch(text):
                segments.append(segment)
    return segments


def _token_spans(rows: list[dict], text_key: str) -> tuple[list[str], list[dict]]:
    all_tokens: list[str] = []
    spans = []
    position = 0
    for row in rows:
        tokens = normalized_tokens(row.get(text_key) or "")
        start_position = position
        position += len(tokens)
        spans.append(
            {
                "row": row,
                "start_position": start_position,
                "end_position": position,
            }
        )
        all_tokens.extend(tokens)
    return all_tokens, spans


def fetch_xdf_payload(qid: int) -> dict:
    response = requests.post(
        XDF_API_URL,
        data={"qId": str(qid)},
        headers={"User-Agent": "StudyTracker intensive-listening pilot"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != 0 or not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"Unexpected XDF response: status={payload.get('status')}")
    return payload["data"]


def _infer_regions(xdf_spans: list[dict], local_spans: list[dict]) -> list[dict]:
    local_starts = {
        span["start_position"]: float(span["row"].get("original_start", span["row"]["start"]))
        for span in local_spans
    }
    anchors = []
    for row_index, span in enumerate(xdf_spans):
        local_time = local_starts.get(span["start_position"])
        if local_time is None:
            continue
        xdf_time = float(span["row"]["start"])
        anchors.append((row_index, local_time - xdf_time))

    if not anchors:
        raise ValueError("No shared sentence boundaries were found")

    break_rows = []
    for previous, current in zip(anchors, anchors[1:], strict=False):
        if abs(current[1] - previous[1]) > 5:
            break_rows.append(current[0])

    boundaries = [0, *sorted(set(break_rows)), len(xdf_spans)]
    regions = []
    for start_row, end_row in zip(boundaries, boundaries[1:], strict=False):
        offsets = [offset for row_index, offset in anchors if start_row <= row_index < end_row]
        if not offsets:
            raise ValueError(f"Timeline region {start_row}:{end_row} has no anchors")
        regions.append(
            {
                "start_row": start_row,
                "end_row": end_row,
                "offset": statistics.median(offsets),
            }
        )
    return regions


def _mapped_boundary(
    local_boundaries: dict[int, float],
    word_position: int,
    xdf_time: float,
    region_offset: float,
    *,
    force_local: bool = False,
) -> float:
    local_time = local_boundaries.get(word_position)
    if local_time is not None:
        local_offset = local_time - xdf_time
        if force_local or abs(local_offset - region_offset) <= 0.5:
            return local_time
    return xdf_time + region_offset


def build_pilot_payload(source_payload: dict, xdf_payload: dict, audio_name: str) -> dict:
    local_rows = _dialogue_segments(source_payload)
    xdf_rows = sorted(
        xdf_payload.get("sentence") or [],
        key=lambda row: int(row.get("sortNum") or 0),
    )
    local_tokens, local_spans = _token_spans(local_rows, "text")
    xdf_tokens, xdf_spans = _token_spans(xdf_rows, "entext")
    if local_tokens != xdf_tokens:
        raise ValueError(
            "The XDF and local transcripts differ after normalization: "
            f"xdf={len(xdf_tokens)}, local={len(local_tokens)}"
        )

    local_starts = {
        span["start_position"]: float(span["row"].get("original_start", span["row"]["start"]))
        for span in local_spans
    }
    local_ends = {
        span["end_position"]: float(span["row"].get("original_end", span["row"]["end"]))
        for span in local_spans
    }
    regions = _infer_regions(xdf_spans, local_spans)

    mapped_rows = []
    for region_index, region in enumerate(regions):
        for row_index in range(region["start_row"], region["end_row"]):
            span = xdf_spans[row_index]
            row = span["row"]
            xdf_start = float(row["start"])
            xdf_end = float(row["end"])
            original_start = _mapped_boundary(
                local_starts,
                span["start_position"],
                xdf_start,
                region["offset"],
            )
            original_end = _mapped_boundary(
                local_ends,
                span["end_position"],
                xdf_end,
                region["offset"],
                force_local=row_index == len(xdf_spans) - 1,
            )
            if original_end <= original_start:
                raise ValueError(f"Invalid mapped range at XDF sentence {row_index + 1}")
            mapped_rows.append(
                {
                    "row": row,
                    "region_index": region_index,
                    "original_start": original_start,
                    "original_end": original_end,
                }
            )

    clips = []
    output_cursor = 0.0
    for region_index, region in enumerate(regions):
        first = mapped_rows[region["start_row"]]
        last = mapped_rows[region["end_row"] - 1]
        clip_start = first["original_start"]
        clip_end = last["original_end"]
        clips.append(
            {
                "region_index": region_index,
                "original_start": clip_start,
                "original_end": clip_end,
                "output_start": output_cursor,
            }
        )
        output_cursor += clip_end - clip_start

    segments = []
    for item in mapped_rows:
        row = item["row"]
        clip = clips[item["region_index"]]
        output_start = clip["output_start"] + (item["original_start"] - clip["original_start"])
        output_end = clip["output_start"] + (item["original_end"] - clip["original_start"])
        segments.append(
            {
                "id": len(segments) + 1,
                "start": round(output_start, 2),
                "end": round(output_end, 2),
                "text": str(row.get("entext") or "").strip(),
                "translation": str(row.get("cntext") or "").strip(),
                "source_order": int(row.get("sortNum") or len(segments) + 1),
                "source_start_time": round(float(row["start"]) * 1000),
                "source_end_time": round(float(row["end"]) * 1000),
                "original_start": round(item["original_start"], 3),
                "original_end": round(item["original_end"], 3),
            }
        )

    xdf_internal_boundaries = {span["end_position"] for span in xdf_spans[:-1]}
    local_internal_boundaries = {span["end_position"] for span in local_spans[:-1]}
    removed_gaps = [
        round(current["original_start"] - previous["original_end"], 3)
        for previous, current in zip(clips, clips[1:], strict=False)
    ]
    source = source_payload.get("source") or {}
    source_mapping = source.get("mapping") or {}
    return {
        "id": "ielts20_test1_s1_xdf_pilot",
        "title": "Cambridge IELTS 20 Test 1 Section 1（45句纯对话试点）",
        "audio": audio_name,
        "source": {
            "provider": "xdf_ieltscat_pilot",
            "q_id": int(xdf_rows[0].get("qId") or 1817),
            "page_url": XDF_PAGE_URL,
            "api_url": XDF_API_URL,
            "original_audio": source_payload.get("audio"),
            "original_provider": source.get("original_provider") or source.get("provider"),
            "original_file_url": source.get("original_file_url") or source.get("file_url"),
            "generated_by": "scripts/build_xdf_intensive_pilot.py",
            "mapping": {
                "token_count": len(xdf_tokens),
                "xdf_segment_count": len(xdf_rows),
                "original_dialogue_segment_count": int(
                    source_mapping.get("original_dialogue_segment_count") or len(local_rows)
                ),
                "shared_internal_boundaries": int(
                    source_mapping.get("shared_internal_boundaries")
                    or len(xdf_internal_boundaries & local_internal_boundaries)
                ),
                "region_offsets_seconds": [round(region["offset"], 3) for region in regions],
                "removed_gaps_seconds": removed_gaps,
                "clips": [
                    {
                        "original_start": round(clip["original_start"], 3),
                        "original_end": round(clip["original_end"], 3),
                        "output_start": round(clip["output_start"], 3),
                    }
                    for clip in clips
                ],
            },
        },
        "parts": [{"name": "Section 1 · 45句试点", "segments": segments}],
    }


def build_dialogue_audio(source_audio: Path, output_audio: Path, clips: list[dict]):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to build the dialogue-only audio")

    filter_parts = []
    labels = []
    for index, clip in enumerate(clips):
        label = f"a{index}"
        labels.append(f"[{label}]")
        filter_parts.append(
            f"[0:a]atrim=start={clip['original_start']}:end={clip['original_end']},"
            f"asetpts=PTS-STARTPTS[{label}]"
        )
    filter_parts.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]")
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            str(source_audio),
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[out]",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(output_audio),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qid", type=int, default=1817)
    parser.add_argument(
        "--source-json",
        type=Path,
        default=ROOT / "static/listening/ielts20_test1_s1.json",
    )
    parser.add_argument(
        "--source-audio",
        type=Path,
        default=ROOT / "static/listening" / ORIGINAL_AUDIO_BACKUP,
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=ROOT / "static/listening/ielts20_test1_s1_xdf_pilot.json",
    )
    parser.add_argument(
        "--output-audio",
        type=Path,
        default=ROOT / "static/listening/ielts20_test1_s1_xdf_pilot.mp3",
    )
    parser.add_argument("--skip-audio", action="store_true")
    args = parser.parse_args()

    source_payload = json.loads(args.source_json.read_text(encoding="utf-8"))
    xdf_payload = fetch_xdf_payload(args.qid)
    pilot = build_pilot_payload(source_payload, xdf_payload, args.output_audio.name)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(pilot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not args.skip_audio:
        build_dialogue_audio(
            args.source_audio,
            args.output_audio,
            pilot["source"]["mapping"]["clips"],
        )

    mapping = pilot["source"]["mapping"]
    print(
        f"built {len(pilot['parts'][0]['segments'])} segments, "
        f"{mapping['token_count']} tokens, removed gaps "
        f"{mapping['removed_gaps_seconds']}s"
    )
    print(args.output_json)
    if not args.skip_audio:
        print(args.output_audio)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
