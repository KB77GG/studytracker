#!/usr/bin/env python3
"""
从 engnovate.com 抓取剑桥雅思听力音频原文，
按 Cam/Test/Part 拆分保存为独立的 txt 文件。

数据源: https://engnovate.com/ielts-listening-tests/cambridge-ielts-{N}-academic-listening-test-{T}/
HTML 结构稳定: 每个 test 页面含 4 个 <div id="ielts-listening-transcript-{1..4}">，
各自包裹一个 Part 的完整对白。

用法:
    # 抓取剑20 全部 4 个 Test
    python scripts/fetch_ielts_transcripts.py --cam 20 --out data/ielts_transcripts

    # 抓取剑15-20 全部
    python scripts/fetch_ielts_transcripts.py --cam 15-20 --out data/ielts_transcripts

    # 只抓指定 test
    python scripts/fetch_ielts_transcripts.py --cam 20 --tests 1,2 --out data/ielts_transcripts

输出目录结构:
    out/
      cam20/
        test1/
          section1.txt   (Part 1 对白)
          section2.txt   (Part 2 对白)
          section3.txt   (Part 3 对白)
          section4.txt   (Part 4 对白)
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch(url: str, timeout: int = 25) -> str | None:
    """用 curl 抓取 URL，返回 HTML。失败返回 None。"""
    try:
        result = subprocess.run(
            [
                "curl", "-sSL",
                "-A", UA,
                "-H", "Accept: text/html,application/xhtml+xml",
                "--max-time", str(timeout),
                "-w", "\n__HTTP_CODE__%{http_code}",
                url,
            ],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        body = result.stdout
        m = re.search(r"__HTTP_CODE__(\d+)\s*$", body)
        code = int(m.group(1)) if m else 0
        if m:
            body = body[: m.start()]
        if code == 200 and body:
            return body
        print(f"  HTTP {code}: {url}", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"  超时: {url}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  请求失败: {e}", file=sys.stderr)
        return None


def html_entities_decode(text: str) -> str:
    """把常见 HTML 实体解码成字符。"""
    for k, v in [
        ("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
        ("&#8217;", "'"), ("&#8216;", "'"),
        ("&#8220;", '"'), ("&#8221;", '"'),
        ("&rsquo;", "'"), ("&lsquo;", "'"),
        ("&ldquo;", '"'), ("&rdquo;", '"'),
        ("&mdash;", "—"), ("&ndash;", "–"),
        ("&#8211;", "–"), ("&#8212;", "—"),
        ("&#163;", "£"), ("&#8364;", "€"), ("&#36;", "$"),
        ("&pound;", "£"), ("&euro;", "€"),
        ("&#39;", "'"), ("&quot;", '"'), ("&apos;", "'"),
    ]:
        text = text.replace(k, v)
    # 数字实体兜底
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))) if 32 <= int(m.group(1)) < 0x10000 else " ", text)
    # 剩余未知实体
    text = re.sub(r"&[a-z]+;", " ", text)
    return text


def extract_transcript_divs(html: str) -> dict[int, str]:
    """
    从页面 HTML 中提取 4 个 transcript div 的内容。
    返回 {part_num: text}。
    """
    results = {}
    # 匹配 <div id="ielts-listening-transcript-N" class="...">...</div>
    # 由于 div 可能嵌套，这里用贪婪匹配到下一个 transcript div 或特定收尾标记
    for part in range(1, 5):
        pattern = (
            rf'<div\s+id\s*=\s*"ielts-listening-transcript-{part}"[^>]*>'
            r'(.*?)'
            rf'(?=<div\s+id\s*=\s*"ielts-listening-transcript-{part + 1}"|'
            r'<div\s+class="[^"]*ielts-listening-question-section|'
            r'<!--\s*/transcripts\s*-->)'
        )
        m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if not m:
            # 兜底: 贪婪到 </div></div> 后多处
            pattern2 = (
                rf'<div\s+id\s*=\s*"ielts-listening-transcript-{part}"[^>]*>'
                r'(.*?)</div>\s*(?:</div>)?'
            )
            m = re.search(pattern2, html, re.DOTALL | re.IGNORECASE)
        if m:
            inner = m.group(1)
            results[part] = html_to_plaintext(inner)
    return results


def html_to_plaintext(html: str) -> str:
    """把 HTML 片段转成干净的纯文本。"""
    # 去掉 script/style
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # block 元素变换行
    html = re.sub(r"<(br|p|div|li|h[1-6])\b[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</(p|div|li|h[1-6])\s*>", "\n", html, flags=re.IGNORECASE)
    # 其余标签去掉
    text = re.sub(r"<[^>]+>", " ", html)
    text = html_entities_decode(text)

    # 按行清洗
    out = []
    for line in text.splitlines():
        s = re.sub(r"[ \t]+", " ", line).strip()
        if not s:
            continue
        out.append(s)
    return "\n".join(out)


def process_test(cam: int, test: int, out_dir: Path) -> tuple[bool, dict]:
    """抓取并处理单个 test。返回 (成功, {part: word_count})。"""
    url = f"https://engnovate.com/ielts-listening-tests/cambridge-ielts-{cam}-academic-listening-test-{test}/"
    print(f"  Cam{cam} Test{test}: ", end="", flush=True)

    html = fetch(url)
    if not html:
        print(f"❌ 抓取失败  {url}")
        return False, {}

    parts = extract_transcript_divs(html)
    if len(parts) < 4:
        print(f"❌ 只找到 {len(parts)}/4 个 transcript")
        return False, {}

    test_dir = out_dir / f"cam{cam:02d}" / f"test{test}"
    test_dir.mkdir(parents=True, exist_ok=True)

    word_counts = {}
    for n in range(1, 5):
        content = parts.get(n, "").strip()
        (test_dir / f"section{n}.txt").write_text(content + "\n", encoding="utf-8")
        word_counts[n] = len(content.split())

    info = " ".join(f"S{n}:{w}w" for n, w in word_counts.items())
    print(f"✓ [{info}]")
    return True, word_counts


def parse_cam_range(s: str) -> list[int]:
    if "-" in s:
        lo, hi = s.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(s)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cam", required=True, help="Cambridge 编号, 如 20 或 15-20")
    p.add_argument("--tests", default="1,2,3,4", help="Test 编号逗号分隔")
    p.add_argument("--out", default="data/ielts_transcripts", help="输出目录")
    p.add_argument("--delay", type=float, default=1.5, help="请求间延迟秒数")
    args = p.parse_args()

    cams = parse_cam_range(args.cam)
    tests = [int(t.strip()) for t in args.tests.split(",")]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(cams) * len(tests)
    ok = 0
    print(f"准备抓取 {total} 个 Test (Cam {cams}, Test {tests}), 间隔 {args.delay}s")
    print(f"输出目录: {out_dir.resolve()}")
    print()

    for cam in cams:
        print(f"=== Cambridge IELTS {cam} ===")
        for test in tests:
            success, _ = process_test(cam, test, out_dir)
            if success:
                ok += 1
            time.sleep(args.delay)
        print()

    print(f"完成: {ok}/{total} 成功")


if __name__ == "__main__":
    main()
