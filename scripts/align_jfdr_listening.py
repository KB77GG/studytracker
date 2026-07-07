#!/usr/bin/env python3
"""Force-align 9分达人听力6 transcripts to audio (local Mac only, never prod).

Reads canonical merged transcripts from data/jfdr6/merged/test{N}_part{S}.json
and audio from data/jfdr6/audio/jfdr6_test{N}_s{S}.mp3, producing
data/jfdr6/aligned/jfdr6_test{N}_s{S}.json with one timestamped segment per
transcript sentence (strict 1:1, same order/idx).

Key difference from batch_align_ielts.py: sentences are already final
(extracted + reviewed from the book), so we must NOT re-split them —
split_sentences()/smart_split_into_sentences() are intentionally bypassed
to keep transcript idx <-> segment idx identity for answer_sentences mapping.

Usage:
    .venv/bin/python scripts/align_jfdr_listening.py                 # all 24
    .venv/bin/python scripts/align_jfdr_listening.py --only jfdr6_test1_s1
    .venv/bin/python scripts/align_jfdr_listening.py --model small --resume
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from batch_align_ielts import (  # noqa: E402
    align_with_model,
    get_audio_duration,
    strip_speaker_label,
)
from lcs_align import align_sentences as lcs_align_sentences  # noqa: E402

MERGED_DIR = PROJECT_ROOT / "data" / "jfdr6" / "merged"
AUDIO_DIR = PROJECT_ROOT / "data" / "jfdr6" / "audio"
ALIGNED_DIR = PROJECT_ROOT / "data" / "jfdr6" / "aligned"
CACHE_DIR = PROJECT_ROOT / "data" / "jfdr6" / "whisper_cache"


class CachingWhisper:
    """word-timestamps 转写结果落盘缓存。

    whisper 转写是整条流水线唯一的重机器环节（每个音频数分钟），而对齐
    逻辑本身是纯计算。缓存后可以先 --prewarm 预热全部音频，之后 merged
    文本迭代/重跑对齐都是秒级。
    """

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, audio_path: str) -> Path:
        return CACHE_DIR / f"{Path(audio_path).stem}.{self.model_name}.json"

    def words(self, audio_path: str) -> list[dict]:
        """Flattened [{word,start,end}] from the cached transcription."""
        result = self.transcribe(str(audio_path), word_timestamps=True,
                                 language="en", verbose=False)
        return [w for seg in result["segments"] for w in seg.get("words", [])]

    def transcribe(self, audio_path: str, **kwargs):
        cache = self._cache_path(audio_path)
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        if self._model is None:
            import whisper

            print(f"loading whisper model: {self.model_name}")
            self._model = whisper.load_model(self.model_name)
        result = self._model.transcribe(audio_path, **kwargs)
        slim = {
            "segments": [
                {
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "words": [
                        {"word": w["word"], "start": w["start"], "end": w["end"]}
                        for w in seg.get("words", [])
                    ],
                }
                for seg in result["segments"]
            ]
        }
        cache.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
        return slim


def iter_exercises() -> list[dict]:
    items = []
    for path in sorted(MERGED_DIR.glob("test*_part*.json")):
        merged = json.loads(path.read_text(encoding="utf-8"))
        test_no = int(merged["test"])
        part_no = int(merged["part"])
        exercise_id = f"jfdr6_test{test_no}_s{part_no}"
        items.append(
            {
                "id": exercise_id,
                "merged_path": path,
                "merged": merged,
                "audio": AUDIO_DIR / f"{exercise_id}.mp3",
            }
        )
    return items


def validate_segments(segments: list[dict], sentence_count: int, duration: float) -> list[str]:
    problems = []
    if len(segments) != sentence_count:
        problems.append(f"segment count {len(segments)} != sentence count {sentence_count}")
    prev_start = -1.0
    for seg in segments:
        if seg["start"] < prev_start - 0.01:
            problems.append(f"non-monotonic start at segment {seg['id']} ({seg['start']} < {prev_start})")
        prev_start = seg["start"]
        if seg["end"] < seg["start"]:
            problems.append(f"end < start at segment {seg['id']}")
        if duration and seg["end"] > duration + 0.1:
            problems.append(f"end beyond audio duration at segment {seg['id']}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="small",
                        help="whisper model; 'small' is the minimum that reliably "
                             "reaches the end of IELTS recordings")
    parser.add_argument("--only", help="comma separated exercise ids, e.g. jfdr6_test1_s1")
    parser.add_argument("--resume", action="store_true", help="skip existing aligned outputs")
    parser.add_argument("--prewarm", action="store_true",
                        help="only transcribe all audio into whisper_cache (no merged needed)")
    parser.add_argument("--method", choices=["greedy", "lcs"], default="lcs",
                        help="lcs (global monotonic, robust to sparse ASR) or greedy "
                             "(batch_align_ielts anchor-window)")
    args = parser.parse_args()

    model = CachingWhisper(args.model)

    if args.prewarm:
        for audio in sorted(AUDIO_DIR.glob("jfdr6_*.mp3")):
            print(f"prewarm {audio.name}")
            model.transcribe(str(audio), word_timestamps=True, language="en", verbose=False)
        print("prewarm done")
        return

    exercises = iter_exercises()
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        exercises = [e for e in exercises if e["id"] in wanted]
        if not exercises:
            raise SystemExit(f"--only matched nothing: {wanted}")
    if not exercises:
        raise SystemExit(f"no merged transcripts found under {MERGED_DIR}")

    ALIGNED_DIR.mkdir(parents=True, exist_ok=True)

    report = {"processed": [], "skipped": [], "failed": [], "warnings": {}}
    for entry in exercises:
        out_path = ALIGNED_DIR / f"{entry['id']}.json"
        if args.resume and out_path.exists():
            report["skipped"].append(entry["id"])
            continue
        if not entry["audio"].exists():
            report["failed"].append({"id": entry["id"], "reason": "missing audio"})
            continue

        transcript = entry["merged"].get("transcript") or []
        display_sentences = []
        align_sentences = []
        for row in transcript:
            speaker = (row.get("speaker") or "").strip()
            en = (row.get("en") or "").strip()
            display = f"{speaker}: {en}" if speaker else en
            display_sentences.append(display)
            align_sentences.append(strip_speaker_label(display))

        duration = get_audio_duration(entry["audio"])
        print(f"aligning {entry['id']} ({len(align_sentences)} sentences, {args.method})")
        try:
            if args.method == "lcs":
                words = model.words(entry["audio"])
                segments = lcs_align_sentences(align_sentences, words, duration)
            else:
                segments = align_with_model(model, entry["audio"], align_sentences)
        except Exception as exc:  # noqa: BLE001
            report["failed"].append({"id": entry["id"], "reason": repr(exc)})
            print(f"  failed: {exc}")
            continue

        for seg, display in zip(segments, display_sentences):
            seg["text"] = display

        problems = validate_segments(segments, len(align_sentences), duration)
        if problems:
            report["warnings"][entry["id"]] = problems
            for p in problems:
                print(f"  [warn] {p}")

        out_path.write_text(
            json.dumps(
                {
                    "id": entry["id"],
                    "audio": entry["audio"].name,
                    "audio_duration": round(duration, 2),
                    "model": args.model,
                    "segments": segments,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        report["processed"].append(entry["id"])

    report_path = PROJECT_ROOT / "data" / "jfdr6" / "align_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}, ensure_ascii=False))
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
