#!/usr/bin/env python3
"""Render idictation listening jijing raw export as a reading-friendly Markdown file."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any


TYPE_NAMES = {
    1: "单选题",
    2: "多选题",
    3: "表格/句子填空题",
    4: "匹配题",
    5: "摘要/笔记填空题",
    6: "简答题",
    7: "地图题",
    8: "句子填空题",
    9: "多选题",
    10: "拖拽匹配题",
}


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def unwrap(response: dict[str, Any]) -> Any:
    return response.get("values", response)


def question_type_name(type_id: Any) -> str:
    try:
        return TYPE_NAMES.get(int(type_id), f"题型 {type_id}")
    except (TypeError, ValueError):
        return f"题型 {type_id}"


def answer_of(item: dict[str, Any]) -> str:
    if item.get("display_answer") not in (None, ""):
        return clean_text(item["display_answer"])
    for block in item.get("analyze") or []:
        if isinstance(block, dict) and block.get("type") == "answer":
            text = clean_text(block.get("content", ""))
            return re.sub(r"^答案[:：]\s*", "", text).strip()
    return ""


def option_lines(options: Any) -> list[str]:
    lines: list[str] = []
    for option in options or []:
        if not isinstance(option, dict):
            continue
        label = clean_text(option.get("title") or option.get("value") or "")
        content = clean_text(option.get("content") or option.get("label") or "")
        if label and content:
            lines.append(f"   - {label}. {content}")
        elif label:
            lines.append(f"   - {label}")
        elif content:
            lines.append(f"   - {content}")
    return lines


def collect_option_lines(collect_option: Any, skip_title: str = "") -> list[str]:
    if not isinstance(collect_option, dict):
        return []

    options = collect_option.get("list")
    if not options:
        return []

    lines: list[str] = []
    title = clean_text(collect_option.get("title"))
    if title and title != skip_title:
        lines.append(title)
        lines.append("")

    for option in options:
        if not isinstance(option, dict):
            continue
        label = clean_text(option.get("title"))
        content = clean_text(option.get("content"))
        if label and content:
            lines.append(f"- {label}. {content}")
        elif label:
            lines.append(f"- {label}")
        elif content:
            lines.append(f"- {content}")

    if lines:
        lines.append("")
    return lines


def render_collect(text: str, items: list[dict[str, Any]]) -> str:
    by_id = {str(item.get("id")): item for item in items if isinstance(item, dict)}

    def replace(match: re.Match[str]) -> str:
        item = by_id.get(match.group(1), {})
        number = item.get("number") or "?"
        return f"____ (Q{number})"

    text = re.sub(r"\$([^$\s]+)\$", replace, text or "")
    return clean_text(text)


def render_question_group(group: dict[str, Any], include_answers: bool) -> list[str]:
    lines: list[str] = []
    type_id = group.get("type")
    type_name = question_type_name(type_id)
    desc = clean_text(group.get("desc"))
    question_title = clean_text(group.get("question_title"))
    title = clean_text(group.get("title"))
    items = [item for item in group.get("list") or [] if isinstance(item, dict)]
    collect = render_collect(group.get("collect") or "", items)

    heading_parts = [type_name]
    if desc:
        heading_parts.append(desc.replace("\n", " / "))
    lines.append(f"##### {' - '.join(heading_parts)}")

    if question_title:
        lines.append(question_title)
        lines.append("")
    if title:
        lines.append(title)
        lines.append("")
    if collect:
        for paragraph in collect.split("\n"):
            paragraph = paragraph.strip()
            if paragraph:
                lines.append(paragraph)
        lines.append("")

    lines.extend(collect_option_lines(group.get("collect_option"), skip_title=question_title or title))

    if group.get("img_url") and str(group.get("img_url")).startswith("http") and "aliyuncs.com" in str(group.get("img_url")):
        img_url = str(group["img_url"])
        if not img_url.rstrip("/").endswith("aliyuncs.com"):
            lines.append(f"图片：{img_url}")
            lines.append("")

    for item in items:
        number = item.get("number") or ""
        item_title = clean_text(item.get("title"))
        if item_title:
            lines.append(f"**Q{number}. {item_title}**")
        else:
            lines.append(f"**Q{number}.** ____")

        lines.extend(option_lines(item.get("option")))

        if include_answers:
            answer = answer_of(item)
            if answer:
                lines.append(f"答案：{answer}")

        lines.append("")

    return lines


def normalize_part(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_id": values.get("paper_id"),
        "in_book": values.get("in_book"),
        "test_name": values.get("test_name") or "",
        "title": values.get("title") or "",
        "file_url": values.get("file_url") or "",
        "question_name": values.get("question_name") or "",
        "question_type": values.get("question_type") or "",
        "question": values.get("question") or [],
    }


def sort_key(part: dict[str, Any]) -> tuple[int, str, int]:
    in_book = part.get("in_book")
    try:
        book_num = int(in_book)
    except (TypeError, ValueError):
        book_num = 999999
    test_name = str(part.get("test_name") or "")
    title = str(part.get("title") or "")
    part_match = re.search(r"\d+", title)
    part_num = int(part_match.group()) if part_match else 999
    return book_num, test_name, part_num


def render(raw: dict[str, Any], include_answers: bool) -> str:
    parts: list[dict[str, Any]] = []
    for response in (raw.get("parts") or {}).values():
        values = unwrap(response) if isinstance(response, dict) else {}
        if isinstance(values, dict):
            parts.append(normalize_part(values))
    parts.sort(key=sort_key)

    lines = ["# 爱听写听力机经题目", ""]
    current_book: Any = None
    current_test: Any = None

    for part in parts:
        if part["in_book"] != current_book:
            current_book = part["in_book"]
            current_test = None
            lines.extend([f"## 机经 {current_book}", ""])
        test_label = part["test_name"]
        if test_label != current_test:
            current_test = test_label
            lines.extend([f"### {test_label}", ""])

        lines.extend([f"#### {part['title']}"])
        if part["question_name"]:
            lines.append(f"题号范围：{part['question_name']}")
        if part["question_type"]:
            lines.append(f"题型：{part['question_type']}")
        if part["file_url"]:
            lines.append(f"音频：{part['file_url']}")
        lines.append("")

        for group in part["question"]:
            if isinstance(group, dict):
                lines.extend(render_question_group(group, include_answers))

        lines.append("---")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="/Users/zhouxin/Desktop/idictation_listening_jijing_raw.json")
    parser.add_argument("--output", default="data/idictation_listening_jijing/listening_jijing_questions.md")
    parser.add_argument("--with-answers", action="store_true")
    args = parser.parse_args()

    raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(raw, include_answers=args.with_answers), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
