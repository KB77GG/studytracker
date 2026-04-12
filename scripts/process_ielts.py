#!/usr/bin/env python3
"""
剑桥雅思听力音频批量处理脚本

用法:
    # 处理单个音频文件
    python scripts/process_ielts.py --audio "path/to/IELTS 12 Test 5_S1.mp3"

    # 批量处理整个目录
    python scripts/process_ielts.py --dir "path/to/剑12听力音频/"

    # 指定 Whisper 模型 (tiny/base/small/medium/large)
    python scripts/process_ielts.py --dir "path/to/audio/" --model small

处理流程:
    1. 用 Whisper 转录音频，获取句级时间戳
    2. 生成 JSON 数据文件到 static/listening/
    3. 复制音频文件到 static/listening/

依赖:
    pip install openai-whisper
"""

import argparse
import json
import re
import shutil
import ssl
import sys
from pathlib import Path

# 绕过 SSL 证书验证（用于下载 Whisper 模型）
ssl._create_default_https_context = ssl._create_unverified_context

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "static" / "listening"


def parse_filename(filename: str) -> dict | None:
    """从文件名提取信息，如 'IELTS 12 Test 5_S1.mp3'"""
    m = re.match(
        r"IELTS\s*(\d+)\s*Test\s*(\d+)[_\s]*S(\d+)",
        filename,
        re.IGNORECASE,
    )
    if m:
        return {
            "book": int(m.group(1)),
            "test": int(m.group(2)),
            "section": int(m.group(3)),
        }
    return None


def transcribe_audio(audio_path: str, model_name: str = "base") -> list[dict]:
    """使用 Whisper 转录音频，返回句级 segments。"""
    try:
        import whisper
    except ImportError:
        print("错误: 请先安装 whisper:")
        print("  pip install openai-whisper")
        sys.exit(1)

    print(f"  加载 Whisper 模型 ({model_name})...")
    model = whisper.load_model(model_name)

    print(f"  正在转录...")
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language="en",
        verbose=False,
    )

    segments = []
    for i, seg in enumerate(result.get("segments", [])):
        text = seg["text"].strip()
        if not text:
            continue
        segments.append({
            "id": len(segments) + 1,
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": text,
        })

    return segments


def merge_short_segments(segments: list[dict], min_duration: float = 1.5) -> list[dict]:
    """合并过短的 segment 到前一个。"""
    if not segments:
        return segments

    merged = [segments[0]]
    for seg in segments[1:]:
        dur = seg["end"] - seg["start"]
        if dur < min_duration and merged:
            # 合并到上一个
            merged[-1]["end"] = seg["end"]
            merged[-1]["text"] += " " + seg["text"]
        else:
            merged.append(seg)

    # 重新编号
    for i, seg in enumerate(merged):
        seg["id"] = i + 1

    return merged


def process_single(audio_path: Path, model_name: str = "base") -> Path:
    """处理单个音频文件，生成 JSON 并复制音频。"""
    info = parse_filename(audio_path.name)

    if info:
        exercise_id = f"ielts{info['book']}_test{info['test']}_s{info['section']}"
        title = f"Cambridge IELTS {info['book']} Test {info['test']} Section {info['section']}"
    else:
        exercise_id = re.sub(r"[^\w]", "_", audio_path.stem).lower()
        title = audio_path.stem

    print(f"\n处理: {audio_path.name}")
    print(f"  ID: {exercise_id}")

    # 转录
    segments = transcribe_audio(str(audio_path), model_name)
    segments = merge_short_segments(segments)
    print(f"  识别到 {len(segments)} 个句子")

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 复制音频
    audio_dest = OUTPUT_DIR / f"{exercise_id}.mp3"
    if not audio_dest.exists() or audio_dest.stat().st_size != audio_path.stat().st_size:
        shutil.copy2(audio_path, audio_dest)
        print(f"  音频已复制到: {audio_dest.relative_to(PROJECT_ROOT)}")

    # 生成 JSON
    data = {
        "id": exercise_id,
        "title": title,
        "audio": f"{exercise_id}.mp3",
        "parts": [
            {
                "name": f"Section {info['section']}" if info else "Full",
                "segments": segments,
            }
        ],
    }

    json_path = OUTPUT_DIR / f"{exercise_id}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  JSON 已生成: {json_path.relative_to(PROJECT_ROOT)}")

    # 显示前几句
    for seg in segments[:3]:
        print(f"    [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'][:60]}")
    if len(segments) > 3:
        print(f"    ... 共 {len(segments)} 句")

    return json_path


def process_directory(dir_path: Path, model_name: str = "base"):
    """批量处理目录下的所有 MP3 文件。"""
    mp3_files = sorted(dir_path.glob("*.mp3"))
    if not mp3_files:
        print(f"目录中没有 MP3 文件: {dir_path}")
        return

    print(f"找到 {len(mp3_files)} 个 MP3 文件:")
    for f in mp3_files:
        print(f"  - {f.name}")

    for f in mp3_files:
        try:
            process_single(f, model_name)
        except Exception as e:
            print(f"  处理失败: {e}")

    print(f"\n全部完成！访问 /listening 查看练习列表。")


def main():
    parser = argparse.ArgumentParser(description="剑桥雅思听力音频处理工具")
    parser.add_argument("--audio", help="单个音频文件路径")
    parser.add_argument("--dir", help="音频文件目录（批量处理）")
    parser.add_argument(
        "--model",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper 模型大小 (默认: base, 推荐 small 获得更好效果)",
    )

    args = parser.parse_args()

    if not args.audio and not args.dir:
        parser.print_help()
        print("\n示例:")
        print('  python scripts/process_ielts.py --audio "Downloads/IELTS 12 Test 5_S1.mp3"')
        print('  python scripts/process_ielts.py --dir "Downloads/剑12听力音频/" --model small')
        return

    if args.audio:
        p = Path(args.audio).expanduser()
        if not p.exists():
            print(f"文件不存在: {p}")
            sys.exit(1)
        process_single(p, args.model)
    elif args.dir:
        p = Path(args.dir).expanduser()
        if not p.is_dir():
            print(f"目录不存在: {p}")
            sys.exit(1)
        process_directory(p, args.model)

    print(f"\n数据目录: {OUTPUT_DIR.relative_to(PROJECT_ROOT)}/")
    print("启动服务后访问 /listening 即可使用。")


if __name__ == "__main__":
    main()
