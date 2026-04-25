#!/usr/bin/env python3
"""Audit and optionally trim IELTS listening JSON/audio alignment issues.

The main failure this catches is a transcript tail with no corresponding audio:
the old aligner generated synthetic 2-second timestamps after Whisper ran out
of timed words, so students saw text that could not be played.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LISTENING_ROOT = PROJECT_ROOT / "static" / "listening"


@dataclass
class FlatSegment:
    part_index: int
    segment_index: int
    global_index: int
    segment: dict


def run_text(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()


def audio_duration(path: Path) -> float:
    return float(
        run_text(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nk=1:nw=1",
                str(path),
            ]
        )
    )


def final_speech_end(path: Path, duration: float, window: float = 120.0) -> float:
    """Return the start of final trailing silence, or duration if none exists."""
    start = max(0.0, duration - window)
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{window:.3f}",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-35dB:d=1",
            "-f",
            "null",
            "-",
        ],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    starts = [start + float(x) for x in re.findall(r"silence_start: ([0-9.]+)", proc.stderr)]
    ends = [start + float(x) for x in re.findall(r"silence_end: ([0-9.]+)", proc.stderr)]
    if starts and (not ends or starts[-1] > ends[-1]):
        return starts[-1]
    return duration


def flatten(payload: dict) -> list[FlatSegment]:
    rows: list[FlatSegment] = []
    global_index = 0
    for part_index, part in enumerate(payload.get("parts", [])):
        for segment_index, segment in enumerate(part.get("segments", [])):
            rows.append(FlatSegment(part_index, segment_index, global_index, segment))
            global_index += 1
    return rows


def words(text: str) -> list[str]:
    return re.findall(r"\b[\w'-]+\b", text or "")


def segment_stats(segment: dict) -> tuple[float, int, float, float]:
    start = float(segment.get("start") or 0.0)
    end = float(segment.get("end") or 0.0)
    duration = max(0.0, end - start)
    word_count = len(words(segment.get("text") or ""))
    wps = word_count / duration if duration else 999.0
    return duration, word_count, wps, end


def is_synthetic_tail_segment(segment: dict, duration: float, speech_end: float) -> bool:
    start = float(segment.get("start") or 0.0)
    end = float(segment.get("end") or 0.0)
    seg_dur, word_count, wps, _ = segment_stats(segment)
    exact_two_second = abs(seg_dur - 2.0) <= 0.06 and word_count >= 4
    starts_after_audio = start >= duration - 0.1
    short_beyond_audio = seg_dur <= 3.0 and end > duration + 0.5
    in_final_silence = start >= speech_end - 0.25 and word_count >= 4
    impossible_speed = word_count >= 8 and (wps >= 6.5 or (seg_dur <= 3.0 and word_count >= 12))
    return exact_two_second or starts_after_audio or short_beyond_audio or in_final_silence or impossible_speed


def find_tail_cut(rows: list[FlatSegment], duration: float, speech_end: float) -> int | None:
    if len(rows) < 4:
        return None

    candidate = len(rows)
    for idx in range(len(rows) - 1, -1, -1):
        if is_synthetic_tail_segment(rows[idx].segment, duration, speech_end):
            candidate = idx
            continue
        break

    bad_tail_len = len(rows) - candidate
    last_end = float(rows[-1].segment.get("end") or 0.0)
    if bad_tail_len < 3 and last_end <= duration + 0.5:
        candidate = None

    if candidate is None:
        search_start = max(0, len(rows) - 14)
        run_start = None
        run: list[int] = []
        for idx in range(search_start, len(rows)):
            seg_dur, word_count, wps, _ = segment_stats(rows[idx].segment)
            if abs(seg_dur - 2.0) <= 0.06:
                if run_start is None:
                    run_start = idx
                run.append(idx)
            else:
                if _looks_like_artifact_run(rows, run):
                    candidate = run_start
                run_start = None
                run = []
        if _looks_like_artifact_run(rows, run):
            candidate = run_start
        if candidate is None:
            return None

    # Extend the cut earlier to include the first impossible segment before a
    # synthetic 2-second run, e.g. 38 transcript words squeezed into 2.5 sec.
    while candidate > 0:
        prev = rows[candidate - 1].segment
        seg_dur, word_count, wps, _ = segment_stats(prev)
        prev_bad = word_count >= 8 and (wps >= 6.5 or (seg_dur <= 3.0 and word_count >= 12))
        if prev_bad:
            candidate -= 1
            continue
        break

    return candidate


def _looks_like_artifact_run(rows: list[FlatSegment], indices: list[int]) -> bool:
    if len(indices) < 3:
        return False
    for idx in indices:
        seg_dur, word_count, wps, _ = segment_stats(rows[idx].segment)
        if word_count >= 8 and (wps >= 6.5 or (seg_dur <= 3.0 and word_count >= 12)):
            return True
    return False


def trim_payload(payload: dict, cut_index: int) -> dict:
    next_payload = dict(payload)
    next_parts = []
    global_index = 0
    for part in payload.get("parts", []):
        next_part = dict(part)
        next_segments = []
        for segment in part.get("segments", []):
            if global_index < cut_index:
                next_segments.append(segment)
            global_index += 1
        if next_segments:
            next_part["segments"] = next_segments
            next_parts.append(next_part)
    next_payload["parts"] = next_parts
    return next_payload


def clip_last_segment_end(payload: dict, duration: float) -> bool:
    for part in reversed(payload.get("parts", [])):
        segments = part.get("segments") or []
        if not segments:
            continue
        last = segments[-1]
        start = float(last.get("start") or 0.0)
        end = float(last.get("end") or 0.0)
        if start < duration and end > duration:
            last["end"] = round(duration, 2)
            return True
        return False
    return False


def audit_file(path: Path, fix: bool = False) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = flatten(payload)
    audio_name = payload.get("audio") or f"{path.stem}.mp3"
    audio_path = LISTENING_ROOT / audio_name
    result = {
        "id": path.stem,
        "json": str(path.relative_to(PROJECT_ROOT)),
        "audio": audio_name,
        "segments": len(rows),
        "issues": [],
        "cut_index": None,
        "trimmed": 0,
        "clipped_last_end": None,
    }

    if not audio_path.exists():
        result["issues"].append("missing_audio")
        return result

    duration = audio_duration(audio_path)
    speech_end = final_speech_end(audio_path, duration)
    result["audio_duration"] = round(duration, 2)
    result["final_speech_end"] = round(speech_end, 2)

    if rows:
        last_end = float(rows[-1].segment.get("end") or 0.0)
        result["last_segment_end"] = round(last_end, 2)
        if last_end > duration + 0.5:
            result["issues"].append("last_segment_after_audio")

    for prev, cur in zip(rows, rows[1:]):
        if float(cur.segment.get("start") or 0.0) < float(prev.segment.get("start") or 0.0):
            result["issues"].append("non_monotonic_start")
            break

    cut_index = find_tail_cut(rows, duration, speech_end)
    simulated_payload = payload
    if cut_index is not None and cut_index < len(rows):
        result["issues"].append("synthetic_tail")
        result["cut_index"] = cut_index
        result["trimmed"] = len(rows) - cut_index
        first_bad = rows[cut_index].segment
        result["first_trimmed"] = {
            "index": cut_index + 1,
            "start": first_bad.get("start"),
            "end": first_bad.get("end"),
            "text": (first_bad.get("text") or "")[:120],
        }
        simulated_payload = trim_payload(payload, cut_index)

    simulated_rows = flatten(simulated_payload)
    if simulated_rows:
        last_after_trim = simulated_rows[-1].segment
        last_start = float(last_after_trim.get("start") or 0.0)
        last_end = float(last_after_trim.get("end") or 0.0)
        if last_start < duration and last_end > duration + 0.05:
            result["issues"].append("clip_last_segment_end")
            result["clipped_last_end"] = {
                "from": round(last_end, 2),
                "to": round(duration, 2),
            }

    if fix and (result["trimmed"] or result["clipped_last_end"]):
        next_payload = simulated_payload
        if result["clipped_last_end"]:
            clip_last_segment_end(next_payload, duration)
        path.write_text(json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if len(rows) <= 3:
        result["issues"].append("low_segment_count")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit IELTS listening JSON/audio alignment")
    parser.add_argument("--root", type=Path, default=LISTENING_ROOT)
    parser.add_argument("--fix-tail", action="store_true", help="trim detected unsupported tail segments")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "data" / "listening_alignment_audit.json")
    parser.add_argument("--only", help="comma-separated exercise ids")
    args = parser.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else None
    files = sorted(args.root.glob("*.json"))
    if only:
        files = [p for p in files if p.stem in only]

    results = [audit_file(path, fix=args.fix_tail) for path in files]
    report = {
        "checked": len(results),
        "fix_tail": args.fix_tail,
        "issue_count": sum(1 for row in results if row["issues"]),
        "trimmed_file_count": sum(1 for row in results if row.get("trimmed")),
        "trimmed_segment_count": sum(int(row.get("trimmed") or 0) for row in results),
        "results": [row for row in results if row["issues"]],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "checked": report["checked"],
                "issue_count": report["issue_count"],
                "trimmed_file_count": report["trimmed_file_count"],
                "trimmed_segment_count": report["trimmed_segment_count"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    for row in report["results"][:80]:
        print(
            f"{row['id']}: issues={','.join(row['issues'])} "
            f"segments={row['segments']} trimmed={row.get('trimmed') or 0} "
            f"cut={row.get('cut_index')}"
        )


if __name__ == "__main__":
    main()
