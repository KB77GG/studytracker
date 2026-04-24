#!/usr/bin/env python3
"""
从老烤鸭 laokaoya.com 抓取剑桥雅思听力原文（主要用于剑 4-9，补足 engnovate 缺的部分）。

老烤鸭结构:
- 每个 tag 页 (如 tag/剑桥雅思4听力原文与答案) 列出该剑的 16 个 Section 的文章链接
- 每篇文章包含: 中文介绍 + 英文对话原文 + 链接到其他 Section

用法:
    python scripts/fetch_laokaoya_transcripts.py --cam 4 --out data/ielts_transcripts
    python scripts/fetch_laokaoya_transcripts.py --cam 4-9 --out data/ielts_transcripts

输出:
    out/cam04/test1/section1.txt  (纯英文对话)
"""

import argparse
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path


UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def fetch(url: str, timeout: int = 25) -> str | None:
    try:
        result = subprocess.run(
            ["curl", "-sSL", "-A", UA, "--max-time", str(timeout),
             "-w", "\n__HTTP_CODE__%{http_code}", url],
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
    except Exception as e:
        print(f"  请求失败: {e}", file=sys.stderr)
        return None


def tag_url(cam: int) -> str:
    """剑桥雅思N听力原文与答案 的 tag 页 URL。"""
    tag_text = f"剑桥雅思{cam}听力原文与答案"
    return f"https://www.laokaoya.com/tag/{urllib.parse.quote(tag_text)}"


# 标题示例:
#   "剑4 test 1 Section 1雅思听力原文 notes on social programme"
#   "剑桥雅思4 test 4 Section 4听力原文与答案 Sharks in Australia"
#   "剑桥雅思9 Test1 Section 1听力原文" (可能连写)
TITLE_RE = re.compile(
    r"剑(?:桥雅思)?\s*(\d+)\s*(?:[Tt]est|TEST)\s*(\d+)\s*(?:[Ss]ection|SECTION)\s*(\d+)",
    re.UNICODE,
)


def parse_tag_page(html: str, cam: int) -> dict[tuple[int, int], str]:
    """
    从 tag 页解析出 {(test, section): article_url} 映射。
    """
    mapping = {}
    for m in re.finditer(
        r'<a[^>]+href="(https?://www\.laokaoya\.com/\d+\.html)"[^>]*>([^<]+)</a>',
        html,
    ):
        url = m.group(1)
        title = re.sub(r"\s+", " ", m.group(2)).strip()
        if "听力原文" not in title:
            continue
        mt = TITLE_RE.search(title)
        if not mt:
            continue
        c, t, s = int(mt.group(1)), int(mt.group(2)), int(mt.group(3))
        if c != cam:
            continue
        if not (1 <= t <= 4 and 1 <= s <= 4):
            continue
        # 保留第一次出现（若有重复）
        mapping.setdefault((t, s), url)
    return mapping


def html_to_lines(html: str) -> list[str]:
    """HTML → 按行清洗的文本列表。"""
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.I)
    html = re.sub(r"<(br|p|div|li|h[1-6])\b[^>]*>", "\n", html, flags=re.I)
    html = re.sub(r"</(p|div|li|h[1-6])\s*>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = text.replace("&nbsp;", " ")
    for k, v in [
        ("&#8217;", "'"), ("&#8216;", "'"),
        ("&#8220;", '"'), ("&#8221;", '"'),
        ("&rsquo;", "'"), ("&lsquo;", "'"),
        ("&ldquo;", '"'), ("&rdquo;", '"'),
        ("&amp;", "&"), ("&mdash;", "—"),
        ("&#8211;", "–"), ("&#8212;", "—"),
        ("&pound;", "£"), ("&#163;", "£"),
    ]:
        text = text.replace(k, v)
    text = re.sub(r"&#\d+;|&[a-z]+;", " ", text)
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    return [l for l in lines if l]


CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def is_english_line(line: str, min_len: int = 20) -> bool:
    """判断一行是否为英文正文：长度够且没有中文字符。"""
    if len(line) < min_len:
        return False
    if CHINESE_RE.search(line):
        return False
    # 必须以字母或引号开头（排除纯标点/数字行）
    return bool(re.match(r'^[A-Za-z"\'(\[]', line))


def extract_dialogue(lines: list[str]) -> list[str]:
    """
    从老烤鸭文章行列表中截取英文正文主体（对话或独白均适用）。

    规则:
    - 起点: 第一个"较长的纯英文行"（避免命中导航栏里零星的英文短句）
    - 终点: 遇到中文行（文章结束，进入"答案解析/相关文章/评论"等区）
    - 中间允许少量短行/空行（对话停顿），但一旦出现中文即立刻停
    """
    # 找起点：第一个长度>=40 的纯英文行（足够明确是正文段）
    start = None
    for i, l in enumerate(lines):
        if is_english_line(l, min_len=40):
            start = i
            break
    # 若未找到长英文行，降级条件（适合某些独白被分成短句的情况）
    if start is None:
        for i, l in enumerate(lines):
            if is_english_line(l, min_len=20):
                start = i
                break
    if start is None:
        return []

    out = []
    for l in lines[start:]:
        # 碰到中文行（>=2 个中文字符）立刻停止
        if len(CHINESE_RE.findall(l)) >= 2:
            break
        # 显式结束关键词
        if re.search(r"(?i)(Laokaoya|laokaoya\.com)", l) and len(l) < 60:
            continue  # 单行水印跳过即可，不终止
        # 清洗行内污染
        l2 = re.sub(r"This article is from Laokaoya website\.?\s*", "", l, flags=re.I)
        l2 = re.sub(r"\bQ\d+\b", "", l2)
        l2 = re.sub(r"\s{2,}", " ", l2).strip()
        if not l2:
            continue
        # 至少有 3 个英文单词才保留（剔除剩余的短噪声）
        if len(re.findall(r"[A-Za-z]+", l2)) < 3 and len(l2) < 40:
            continue
        out.append(l2)
    return out


def process_cam(cam: int, out_dir: Path, delay: float) -> int:
    """处理单个 Cambridge 编号，返回成功的 Section 数。"""
    print(f"=== 剑雅 {cam} ===")
    tag_html = fetch(tag_url(cam))
    if not tag_html:
        print(f"  ❌ 无法抓取 tag 页")
        return 0

    mapping = parse_tag_page(tag_html, cam)
    print(f"  tag 页识别到 {len(mapping)}/16 个 Section 链接")
    if len(mapping) < 16:
        missing = [(t, s) for t in range(1, 5) for s in range(1, 5) if (t, s) not in mapping]
        print(f"  缺失: {missing}")

    ok_count = 0
    for (test, sec), url in sorted(mapping.items()):
        print(f"  Cam{cam} T{test} S{sec}: ", end="", flush=True)
        art_html = fetch(url)
        if not art_html:
            print("❌ 抓取失败")
            continue
        lines = html_to_lines(art_html)
        dialogue = extract_dialogue(lines)
        if not dialogue:
            print("❌ 未找到对话")
            continue
        content = "\n".join(dialogue)

        test_dir = out_dir / f"cam{cam:02d}" / f"test{test}"
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / f"section{sec}.txt").write_text(content + "\n", encoding="utf-8")
        print(f"✓ {len(dialogue)}行 {len(content.split())}词")
        ok_count += 1
        time.sleep(delay)

    print(f"  小计: {ok_count}/16")
    print()
    return ok_count


def parse_cam_range(s: str) -> list[int]:
    if "-" in s:
        lo, hi = s.split("-")
        return list(range(int(lo), int(hi) + 1))
    return [int(s)]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cam", required=True, help="Cambridge 编号, 如 4 或 4-9")
    p.add_argument("--out", default="data/ielts_transcripts", help="输出目录")
    p.add_argument("--delay", type=float, default=1.5, help="文章间延迟秒数")
    args = p.parse_args()

    cams = parse_cam_range(args.cam)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"准备抓取 剑雅 {cams}, 间隔 {args.delay}s")
    print(f"输出目录: {out_dir.resolve()}\n")

    total_ok = 0
    for cam in cams:
        total_ok += process_cam(cam, out_dir, args.delay)
        time.sleep(args.delay)

    expected = len(cams) * 16
    print(f"完成: {total_ok}/{expected} 个 Section")


if __name__ == "__main__":
    main()
