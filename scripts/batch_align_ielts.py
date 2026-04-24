#!/usr/bin/env python3
"""
Batch align normalized IELTS audio with transcript text files.

Usage:
    python scripts/batch_align_ielts.py --manifest data/ielts_audio_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEXT_ROOT = PROJECT_ROOT / "data" / "ielts_transcripts"
LISTENING_ROOT = PROJECT_ROOT / "static" / "listening"


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def strip_speaker_label(text: str) -> str:
    return re.sub(
        r"^(?:[A-Z][A-Z\s.'&/-]{0,40}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\s*:\s*",
        "",
        (text or "").strip(),
    )


def split_sentences(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    sentences = []
    for line in lines:
        cleaned = strip_speaker_label(line)
        if cleaned:
            sentences.append(cleaned)
    return sentences


def align_with_model(model, audio_path: Path, sentences: list[str]) -> list[dict]:
    result = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language="en",
        verbose=False,
    )

    words: list[dict] = []
    for seg in result["segments"]:
        for word in seg.get("words", []):
            words.append(
                {
                    "word": word["word"].strip(),
                    "start": word["start"],
                    "end": word["end"],
                }
            )

    segments: list[dict] = []
    word_idx = 0

    if not words:
        for idx, sentence in enumerate(sentences):
            seg = result["segments"][idx] if idx < len(result["segments"]) else None
            start = seg["start"] if seg else float(idx * 5)
            end = seg["end"] if seg else start + 5.0
            segments.append(
                {"id": idx + 1, "start": round(start, 2), "end": round(end, 2), "text": sentence}
            )
        return segments

    for idx, sentence in enumerate(sentences):
        sent_words = normalize_text(sentence).split()
        if not sent_words:
            continue

        # 第一句：全局搜（音频常有 IELTS 标准片头 ~25-40s 不在文本里），
        # 后续句子：本地小窗口搜，避免相似句干扰。
        if idx == 0:
            search_range = max(0, len(words) - word_idx)
            anchor_len = min(6, len(sent_words))
        else:
            search_range = min(20, len(words) - word_idx)
            anchor_len = min(5, len(sent_words))

        scored = []  # [(check_idx, score)]
        for offset in range(search_range):
            check_idx = word_idx + offset
            score = 0
            for j, sent_word in enumerate(sent_words[:anchor_len]):
                if check_idx + j < len(words) and normalize_text(words[check_idx + j]["word"]) == sent_word:
                    score += 1
            scored.append((check_idx, score))

        if not scored:
            best_start_idx = word_idx
            best_score = -1
        else:
            max_score = max(s for _, s in scored)
            if idx == 0:
                # IELTS Section 1 常有 "example" 节选先放 ~第一句到第三句，再播完整录音。
                # 取得分最高（或差 1 分）的所有候选，选最后一个 → 跳过 example，命中真正录音。
                high = [ci for ci, s in scored if s >= max_score - 1 and s >= 2]
                best_start_idx = high[-1] if high else scored[0][0]
                best_score = max_score
            else:
                # 后续句子：取首个最佳匹配，避免漂到后面相似句
                best_start_idx = next(ci for ci, s in scored if s == max_score)
                best_score = max_score

        # 第一句：要求至少匹配 2 个 anchor 词；否则放弃强行对齐，保守留 t=0 fallback
        if idx == 0 and best_score < 2:
            print(f"  [warn] first-sentence anchor weak (score={best_score}); using t=0 fallback")

        # 词数耗尽：用上一句结尾续写，避免落到 t=0
        if best_start_idx >= len(words):
            prev_end = segments[-1]["end"] if segments else (words[-1]["end"] if words else 0)
            start_time = prev_end
            end_time = prev_end + 2.0
            end_idx = len(words)  # keep word_idx pinned to end
        else:
            start_time = words[best_start_idx]["start"]
            end_idx = min(best_start_idx + len(sent_words), len(words)) - 1
            end_time = words[end_idx]["end"] if end_idx < len(words) else start_time + 5
        segments.append(
            {
                "id": idx + 1,
                "start": round(start_time, 2),
                "end": round(end_time, 2),
                "text": sentence,
            }
        )
        word_idx = end_idx + 1

    return segments


def ensure_mp3(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    if src.suffix.lower() == ".mp3":
        shutil.copy2(src, dest)
        return
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(dest),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch align IELTS listening materials")
    parser.add_argument("--manifest", default="data/ielts_audio_manifest.json")
    parser.add_argument("--model", default="base")
    parser.add_argument("--books", help="comma separated book numbers, e.g. 4,5,6")
    parser.add_argument("--limit", type=int, help="max entries to process")
    parser.add_argument("--resume", action="store_true", help="skip outputs that already exist")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    entries = manifest["entries"]
    book_filter = None
    if args.books:
        book_filter = {int(x.strip()) for x in args.books.split(",") if x.strip()}
        entries = [e for e in entries if e["cam"] in book_filter]
    if args.limit:
        entries = entries[: args.limit]

    try:
        import whisper
    except ImportError as exc:
        raise SystemExit("openai-whisper not installed") from exc

    print(f"loading whisper model: {args.model}")
    model = whisper.load_model(args.model)
    LISTENING_ROOT.mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0
    failed: list[dict] = []

    for entry in entries:
        cam = entry["cam"]
        text_test = entry["text_test"]
        display_test = entry["display_test"]
        section = entry["section"]
        normalized_audio = Path(entry["normalized_path"])
        text_path = TEXT_ROOT / f"cam{cam:02d}" / f"test{text_test}" / f"section{section}.txt"
        exercise_id = f"ielts{cam}_test{display_test}_s{section}"
        json_path = LISTENING_ROOT / f"{exercise_id}.json"
        audio_out = LISTENING_ROOT / f"{exercise_id}.mp3"

        if args.resume and json_path.exists() and audio_out.exists():
            skipped += 1
            print(f"skip {exercise_id}")
            continue

        if not text_path.exists():
            failed.append({"exercise_id": exercise_id, "reason": f"missing text {text_path}"})
            print(f"missing text: {exercise_id}")
            continue

        print(f"processing {exercise_id}")
        try:
            sentences = split_sentences(text_path)
            segments = align_with_model(model, normalized_audio, sentences)
            ensure_mp3(normalized_audio, audio_out)
            payload = {
                "id": exercise_id,
                "title": f"Cambridge IELTS {cam} Test {display_test} Section {section}",
                "audio": audio_out.name,
                "parts": [{"name": f"Section {section}", "segments": segments}],
            }
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            processed += 1
        except Exception as exc:  # noqa: BLE001
            failed.append({"exercise_id": exercise_id, "reason": repr(exc)})
            print(f"failed {exercise_id}: {exc}")

    report = {
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
    }
    report_path = PROJECT_ROOT / "data" / "ielts_batch_align_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
