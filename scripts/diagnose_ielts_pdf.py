#!/usr/bin/env python3
"""
剑雅听力 PDF 切分诊断脚本

只分析，不切分。扫描整份 PDF，按 Test/Section 循环推断每个 Section 的页码范围，
输出一份诊断报告，帮助判断这个 PDF 是否适合做自动切分。

用法:
    python scripts/diagnose_ielts_pdf.py <pdf_path> [--out diagnosis.txt]

依赖:
    pip install pypdf
"""

import argparse
import re
import sys
from pathlib import Path


def extract_pages(pdf_path: str) -> list[str]:
    """提取每页文本，无文本或出错则返回空字符串。"""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append(text)
    return pages


def roman_to_int(s: str) -> int | None:
    """简单罗马数字转阿拉伯，失败返回 None。"""
    s = s.upper()
    mp = {"I": 1, "V": 5, "X": 10}
    if not s or any(c not in mp for c in s):
        return None
    total = 0
    prev = 0
    for c in reversed(s):
        v = mp[c]
        if v < prev:
            total -= v
        else:
            total += v
        prev = v
    return total if total > 0 else None


def parse_test_num(raw: str) -> int | None:
    """TEST 后面的数字可能是阿拉伯也可能是罗马数字。"""
    raw = raw.strip()
    if raw.isdigit():
        return int(raw)
    return roman_to_int(raw)


# 匹配 TEST 标题: 行首或独立出现的 "TEST N" / "Test N" / "TEST I"
TEST_RE = re.compile(r"(?im)(?:^|\n)\s*TEST\s*([0-9]+|[IVXivx]+)\b")
# 匹配 SECTION 标题
SEC_RE = re.compile(r"(?im)(?:^|\n)\s*SECTION\s*([0-9])\b")


def scan_events(pages: list[str]) -> list[dict]:
    """扫描所有页，返回按页码排序的事件列表。"""
    events = []
    for i, text in enumerate(pages):
        page_num = i + 1
        # Test 事件
        for m in TEST_RE.finditer(text):
            n = parse_test_num(m.group(1))
            if n is not None:
                events.append({"page": page_num, "type": "TEST", "value": n, "pos": m.start()})
        # Section 事件
        for m in SEC_RE.finditer(text):
            try:
                n = int(m.group(1))
            except ValueError:
                continue
            if 1 <= n <= 4:
                events.append({"page": page_num, "type": "SEC", "value": n, "pos": m.start()})

    events.sort(key=lambda e: (e["page"], e["pos"]))
    # 同一页同一类型同值去重（pypdf 有时一页返回重复）
    dedup = []
    seen = set()
    for e in events:
        key = (e["page"], e["type"], e["value"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(e)
    return dedup


def infer_sections(events: list[dict], total_pages: int) -> list[dict]:
    """
    根据事件序列推断每个 Section 的页码范围。

    规则:
    - 遇到 SEC 事件就开始一个新 Section（页 = 事件页）
    - 当前 Section 的结束页 = 下一个 SEC/TEST 事件的前一页（或总页数）
    - 同时维护当前 Test 编号与 Book 编号（当 Test 从高值回到 1 时 Book +1）
    """
    sections = []
    current_book = 1
    current_test = None
    prev_test_val = None

    # 先把 TEST 事件按页聚合一下: 在每个 SEC 前/当页找最近的 TEST
    sec_events = [e for e in events if e["type"] == "SEC"]

    for i, sec in enumerate(sec_events):
        # 找不大于 sec.page 且离 sec.page 最近的 TEST 事件
        nearest_test = None
        for te in events:
            if te["type"] != "TEST":
                continue
            if te["page"] > sec["page"]:
                break
            if te["page"] == sec["page"] and te["pos"] > sec["pos"]:
                continue
            nearest_test = te

        if nearest_test is not None:
            t_val = nearest_test["value"]
            if prev_test_val is not None and t_val < prev_test_val:
                current_book += 1
            current_test = t_val
            prev_test_val = t_val

        # 结束页
        end_page = total_pages
        if i + 1 < len(sec_events):
            end_page = sec_events[i + 1]["page"] - 1
        # 但如果下一个 Section 开始在同一页，则 end = 同页
        if end_page < sec["page"]:
            end_page = sec["page"]

        sections.append({
            "book_seq": current_book,
            "test": current_test,
            "section": sec["value"],
            "start_page": sec["page"],
            "end_page": end_page,
        })

    return sections


def page_has_text(pages: list[str], page_num: int, threshold: int = 50) -> bool:
    if not (1 <= page_num <= len(pages)):
        return False
    return len(pages[page_num - 1].strip()) >= threshold


def summarize(sections: list[dict], pages: list[str]) -> str:
    lines = []
    total = len(sections)
    anomalies = []

    # 统计
    book_counts = {}
    for s in sections:
        book_counts[s["book_seq"]] = book_counts.get(s["book_seq"], 0) + 1

    lines.append("=" * 70)
    lines.append(f"识别到 Section 总数: {total}")
    lines.append(f"推断书本数 (按 Test 循环): {len(book_counts)}")
    lines.append(f"剑雅 4-20 应有: 17 本 × 4 Test × 4 Section = 272 个 Section")
    lines.append(f"覆盖率: {total}/272 = {total/272*100:.1f}%")
    lines.append("")

    lines.append("每本推断的 Section 数 (应为 16):")
    for b, c in sorted(book_counts.items()):
        flag = " ✓" if c == 16 else f"  ⚠ (缺 {16 - c})"
        lines.append(f"  第 {b} 本: {c} 个 Section{flag}")
    lines.append("")

    # 异常检测
    for s in sections:
        span = s["end_page"] - s["start_page"] + 1
        # 正常一个 Section 1-5 页
        if span > 8:
            anomalies.append(f"  跨度过大 ({span}页): 书{s['book_seq']} Test{s['test']} Sec{s['section']} p{s['start_page']}-{s['end_page']}")
        # 起始页没文本
        if not page_has_text(pages, s["start_page"]):
            anomalies.append(f"  起始页无文本: 书{s['book_seq']} Test{s['test']} Sec{s['section']} p{s['start_page']}")

    lines.append(f"检测到异常 Section: {len(anomalies)}")
    for a in anomalies[:40]:
        lines.append(a)
    if len(anomalies) > 40:
        lines.append(f"  ... 还有 {len(anomalies) - 40} 条")
    lines.append("")

    # 扫描图片/空白区间
    empty_ranges = []
    empty_pages = [i + 1 for i, t in enumerate(pages) if len(t.strip()) < 50]
    if empty_pages:
        s_ = empty_pages[0]
        e_ = empty_pages[0]
        for p in empty_pages[1:]:
            if p == e_ + 1:
                e_ = p
            else:
                empty_ranges.append((s_, e_))
                s_ = e_ = p
        empty_ranges.append((s_, e_))

    lines.append(f"无文本页区间 (疑似扫描图片): {len(empty_pages)} 页")
    for s_, e_ in empty_ranges:
        lines.append(f"  p{s_}-{e_} ({e_ - s_ + 1} 页)")
    lines.append("")

    lines.append("全部 Section 列表:")
    lines.append(f"  {'书':>3} {'Test':>4} {'Sec':>3}  {'页范围':>10}  {'跨度':>4}  起始页文本?")
    for s in sections:
        span = s["end_page"] - s["start_page"] + 1
        has_txt = "✓" if page_has_text(pages, s["start_page"]) else "✗"
        lines.append(
            f"  {s['book_seq']:>3} {str(s['test']):>4} {s['section']:>3}  "
            f"p{s['start_page']}-{s['end_page']:<5}  {span:>4}  {has_txt}"
        )

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pdf", help="PDF 文件路径")
    p.add_argument("--out", default="diagnosis.txt", help="输出报告文件 (默认 diagnosis.txt)")
    args = p.parse_args()

    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"错误: 找不到文件 {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"正在提取文本: {pdf_path}")
    pages = extract_pages(pdf_path)
    print(f"共 {len(pages)} 页")

    print("正在扫描 Test/Section 事件...")
    events = scan_events(pages)
    print(f"找到 {len(events)} 个事件")

    print("正在推断 Section 边界...")
    sections = infer_sections(events, len(pages))
    print(f"推断出 {len(sections)} 个 Section")

    report = summarize(sections, pages)
    out_path = Path(args.out)
    out_path.write_text(report, encoding="utf-8")
    print(f"\n诊断报告已写入: {out_path.resolve()}")
    print(f"(前 30 行预览如下)")
    print("-" * 70)
    for line in report.splitlines()[:30]:
        print(line)


if __name__ == "__main__":
    main()
