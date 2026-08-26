#!/usr/bin/env python3
"""Re-align listening transcript segments to MP3 word timestamps.

The command writes proposed JSON files and an audit report to separate output
directories. It never overwrites source JSON files.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import whisper

TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")
SPEAKER_RE = re.compile(r"^(?:[A-Z][A-Z\s.'&/-]{0,40}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s*:\s*")
TOKEN_ALIASES = {
    "part": "section",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


@dataclass(frozen=True)
class Word:
    token: str
    start: float
    end: float


def normalize_tokens(text: str, *, strip_speaker: bool = False) -> list[str]:
    value = str(text or "").replace("’", "'").replace("‘", "'")
    if strip_speaker:
        value = SPEAKER_RE.sub("", value.strip())
    tokens = TOKEN_RE.findall(value.lower())
    return [TOKEN_ALIASES.get(token, token) for token in tokens]


def transcribe_words(model, audio_path: Path, cache_path: Path) -> list[Word]:
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return [Word(**row) for row in payload]

    result = model.transcribe(
        str(audio_path),
        language="en",
        word_timestamps=True,
        fp16=False,
        temperature=0,
        condition_on_previous_text=True,
    )
    words: list[Word] = []
    for segment in result.get("segments") or []:
        for item in segment.get("words") or []:
            tokens = normalize_tokens(item.get("word") or "")
            for token in tokens:
                words.append(
                    Word(
                        token=token,
                        start=float(item.get("start") or 0.0),
                        end=float(item.get("end") or 0.0),
                    )
                )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps([word.__dict__ for word in words], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return words


def flatten_segments(payload: dict) -> list[dict]:
    return [
        segment for part in payload.get("parts") or [] for segment in part.get("segments") or []
    ]


def align_payload(payload: dict, words: list[Word]) -> tuple[dict, list[dict]]:
    segments = flatten_segments(payload)
    reference_tokens: list[str] = []
    token_segments: list[int] = []
    segment_token_ranges: list[tuple[int, int]] = []
    for segment_index, segment in enumerate(segments):
        tokens = normalize_tokens(segment.get("text") or "", strip_speaker=True)
        start = len(reference_tokens)
        reference_tokens.extend(tokens)
        token_segments.extend([segment_index] * len(tokens))
        segment_token_ranges.append((start, len(reference_tokens)))

    matcher = difflib.SequenceMatcher(
        None,
        reference_tokens,
        [word.token for word in words],
        autojunk=False,
    )
    mapping: dict[int, int] = {}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):
            mapping[block.a + offset] = block.b + offset

    report: list[dict] = []
    proposals: list[tuple[float, float] | None] = []
    for index, segment in enumerate(segments):
        token_start, token_end = segment_token_ranges[index]
        token_count = token_end - token_start
        matches = [mapping[pos] for pos in range(token_start, token_end) if pos in mapping]
        coverage = len(matches) / token_count if token_count else 0.0
        minimum_matches = 1 if token_count <= 2 else 2
        accepted = len(matches) >= minimum_matches and coverage >= 0.34
        proposal = None
        speech_span = None
        if accepted:
            first_ref = min(pos for pos in range(token_start, token_end) if pos in mapping)
            last_ref = max(pos for pos in range(token_start, token_end) if pos in mapping)
            first_word = words[mapping[first_ref]]
            last_word = words[mapping[last_ref]]
            missing_leading = first_ref - token_start
            missing_trailing = token_end - 1 - last_ref
            speech_start = max(0.0, first_word.start - min(0.9, 0.28 * missing_leading))
            speech_end = last_word.end + min(0.9, 0.28 * missing_trailing)
            speech_span = speech_end - speech_start
            maximum_span = max(2.0, token_count * 1.2)
            if speech_span <= maximum_span:
                proposal = (max(0.0, speech_start - 0.1), speech_end + 0.1)
            else:
                accepted = False
        proposals.append(proposal)
        report.append(
            {
                "id": segment.get("id"),
                "text": segment.get("text"),
                "old_start": segment.get("start"),
                "old_end": segment.get("end"),
                "token_count": token_count,
                "matched_tokens": len(matches),
                "coverage": round(coverage, 3),
                "speech_span": round(speech_span, 3) if speech_span is not None else None,
                "accepted": accepted,
            }
        )

    # Keep a small safety gap between adjacent proposed clips so one sentence
    # cannot leak into the next when the browser pauses a frame late.
    for index in range(len(proposals) - 1):
        current = proposals[index]
        following = proposals[index + 1]
        if current is None or following is None:
            continue
        current_start, current_end = current
        next_start, next_end = following
        if current_end >= next_start:
            cut = max(current_start + 0.05, min(next_end - 0.05, (current_end + next_start) / 2))
            proposals[index] = (current_start, cut - 0.015)
            proposals[index + 1] = (cut + 0.015, next_end)

    for segment, proposal, row in zip(segments, proposals, report, strict=True):
        if proposal is None:
            row["new_start"] = segment.get("start")
            row["new_end"] = segment.get("end")
            continue
        start, end = proposal
        start = round(start, 2)
        end = round(end, 2)
        if end <= start:
            row["accepted"] = False
            row["new_start"] = segment.get("start")
            row["new_end"] = segment.get("end")
            continue
        segment["start"] = start
        segment["end"] = end
        row["new_start"] = start
        row["new_end"] = end

    # A low-confidence segment keeps its original range, which can overlap a
    # confidently aligned neighbour. Split such overlaps at their midpoint
    # and retain a 30 ms decoder-safety gap.
    for current, following in zip(segments, segments[1:], strict=False):
        if current["end"] <= following["start"]:
            continue
        # Trim only a local boundary overlap. Fully inverted clips need an
        # explicit correction; midpoint trimming would create invalid ranges.
        if current["start"] > following["start"] or current["end"] > following["end"]:
            continue
        cut = (current["end"] + following["start"]) / 2
        current["end"] = round(cut - 0.015, 2)
        following["start"] = round(cut + 0.015, 2)

    return payload, report


def structural_issues(payload: dict) -> dict:
    segments = flatten_segments(payload)
    return {
        "bad_ranges": [
            segment.get("id")
            for segment in segments
            if not isinstance(segment.get("start"), (int, float))
            or not isinstance(segment.get("end"), (int, float))
            or segment.get("start", 0) < 0
            or segment.get("end", 0) <= segment.get("start", 0)
        ],
        "nonmonotonic": [
            [left.get("id"), right.get("id")]
            for left, right in zip(segments, segments[1:], strict=False)
            if right.get("start", 0) < left.get("start", 0)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--ids-file", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", default="base")
    args = parser.parse_args()

    exercise_ids = [line.strip() for line in args.ids_file.read_text().splitlines() if line.strip()]
    model = whisper.load_model(args.model)
    results = []
    for index, exercise_id in enumerate(exercise_ids, start=1):
        print(f"[{index}/{len(exercise_ids)}] transcribe {exercise_id}", flush=True)
        json_path = args.root / f"{exercise_id}.json"
        audio_path = args.root / f"{exercise_id}.mp3"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        before_issues = structural_issues(payload)
        words = transcribe_words(model, audio_path, args.cache_dir / f"{exercise_id}.json")
        aligned, rows = align_payload(payload, words)
        after_issues = structural_issues(aligned)
        output_path = args.output_dir / json_path.name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(aligned, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        results.append(
            {
                "id": exercise_id,
                "before_issues": before_issues,
                "after_issues": after_issues,
                "segments": len(rows),
                "accepted": sum(row["accepted"] for row in rows),
                "low_confidence": [row for row in rows if not row["accepted"]],
                "rows": rows,
            }
        )

    report = {
        "model": args.model,
        "checked": len(results),
        "remaining_issue_files": sum(
            bool(row["after_issues"]["bad_ranges"] or row["after_issues"]["nonmonotonic"])
            for row in results
        ),
        "results": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"checked": report["checked"], "remaining_issue_files": report["remaining_issue_files"]}
        )
    )


if __name__ == "__main__":
    main()
