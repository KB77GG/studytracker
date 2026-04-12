#!/usr/bin/env python3
"""
音频-文本句级对齐脚本

用法:
    python scripts/align_audio.py --audio audio.mp3 --text text.txt --output output.json [--title "标题"] [--translation trans.txt]

输入:
    - audio: 整篇音频文件 (mp3/wav/m4a)
    - text:  整篇文本文件，每行一句（用换行分句）
    - translation: 可选，翻译文件，每行对应一句翻译

输出:
    - JSON 文件，包含每句的 start/end 时间戳

依赖:
    pip install openai-whisper

原理:
    1. 用 Whisper 对音频做带词级时间戳的转录
    2. 将 Whisper 的词级结果与你提供的文本做 fuzzy 对齐
    3. 输出每句的精确时间戳
"""

import argparse
import json
import re
import sys
from pathlib import Path


def split_sentences(text_path: str) -> list[str]:
    """读取文本文件，每行作为一个 segment。"""
    lines = Path(text_path).read_text(encoding="utf-8").strip().splitlines()
    return [line.strip() for line in lines if line.strip()]


def normalize(text: str) -> str:
    """标准化文本用于比较。"""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def align_with_whisper(audio_path: str, sentences: list[str]) -> list[dict]:
    """使用 Whisper 做强制对齐。"""
    try:
        import whisper
    except ImportError:
        print("错误: 请先安装 whisper: pip install openai-whisper")
        sys.exit(1)

    print("正在加载 Whisper 模型 (base)...")
    model = whisper.load_model("base")

    print("正在转录音频...")
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
    )

    # 收集所有词级时间戳
    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append({
                "word": w["word"].strip(),
                "start": w["start"],
                "end": w["end"],
            })

    if not words:
        print("警告: Whisper 未返回词级时间戳，回退到段级时间戳")
        return align_fallback_segment(result, sentences)

    # 将词按顺序分配给每个句子
    segments = []
    word_idx = 0

    for sent_idx, sentence in enumerate(sentences):
        sent_words = normalize(sentence).split()
        if not sent_words:
            continue

        # 寻找最佳匹配起始位置
        best_start_idx = word_idx
        best_score = -1

        # 在当前位置附近搜索
        search_range = min(20, len(words) - word_idx)
        for offset in range(search_range):
            check_idx = word_idx + offset
            if check_idx >= len(words):
                break
            score = 0
            for j, sw in enumerate(sent_words[:5]):  # 只比较前5个词
                if check_idx + j < len(words):
                    if normalize(words[check_idx + j]["word"]) == sw:
                        score += 1
            if score > best_score:
                best_score = score
                best_start_idx = check_idx

        # 从最佳起始位置匹配整个句子
        start_time = words[best_start_idx]["start"] if best_start_idx < len(words) else 0
        end_idx = min(best_start_idx + len(sent_words), len(words)) - 1
        end_time = words[end_idx]["end"] if end_idx < len(words) else start_time + 5

        segments.append({
            "id": sent_idx + 1,
            "start": round(start_time, 2),
            "end": round(end_time, 2),
            "text": sentence,
        })

        word_idx = end_idx + 1

    return segments


def align_fallback_segment(result: dict, sentences: list[str]) -> list[dict]:
    """回退方案: 用 Whisper 段级时间戳做粗略对齐。"""
    whisper_segs = result.get("segments", [])
    segments = []

    for i, sentence in enumerate(sentences):
        if i < len(whisper_segs):
            seg = whisper_segs[i]
            start = seg["start"]
            end = seg["end"]
        else:
            # 均匀分配剩余时间
            total_dur = whisper_segs[-1]["end"] if whisper_segs else 60
            avg = total_dur / len(sentences)
            start = i * avg
            end = (i + 1) * avg

        segments.append({
            "id": i + 1,
            "start": round(start, 2),
            "end": round(end, 2),
            "text": sentence,
        })

    return segments


def main():
    parser = argparse.ArgumentParser(description="音频-文本句级对齐工具")
    parser.add_argument("--audio", required=True, help="音频文件路径")
    parser.add_argument("--text", required=True, help="文本文件路径 (每行一句)")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument("--title", default="Listening Exercise", help="练习标题")
    parser.add_argument("--translation", help="翻译文件路径 (每行一句，可选)")
    parser.add_argument("--audio-url", help="音频在网页中的访问路径 (默认使用文件名)")

    args = parser.parse_args()

    # 读取句子
    sentences = split_sentences(args.text)
    print(f"读取到 {len(sentences)} 个句子")

    # 读取翻译
    translations = []
    if args.translation:
        translations = split_sentences(args.translation)
        if len(translations) != len(sentences):
            print(f"警告: 翻译行数 ({len(translations)}) 与文本行数 ({len(sentences)}) 不一致")

    # 对齐
    segments = align_with_whisper(args.audio, sentences)

    # 添加翻译
    if translations:
        for seg in segments:
            idx = seg["id"] - 1
            if idx < len(translations):
                seg["translation"] = translations[idx]

    # 构建输出
    audio_url = args.audio_url or Path(args.audio).name
    output = {
        "id": Path(args.audio).stem,
        "title": args.title,
        "audio": audio_url,
        "parts": [
            {
                "name": "Part 1",
                "segments": segments,
            }
        ],
    }

    # 写入
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成: {out_path}")
    print(f"共 {len(segments)} 个句子片段")

    # 显示前几个
    for seg in segments[:3]:
        print(f"  [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'][:50]}")
    if len(segments) > 3:
        print(f"  ... 共 {len(segments)} 句")


if __name__ == "__main__":
    main()
