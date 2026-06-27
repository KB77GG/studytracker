#!/usr/bin/env python3
"""Map TOEFL reference answers to the consolidated practice documents.

This script is read-only with respect to the source materials. It builds:

* exam_crosswalk.csv: one row per consolidated date/volume.
* question_answer_crosswalk.csv/json: one row per parsed source answer.
* report.md: coverage summary and alignment risks.

The stable source namespace is:

    practice_id + subject + module + source_question_no

Question numbers restart in Module 2, so a bare date + question number is not
safe for imports.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree


DEFAULT_ROOT = Path.home() / "Desktop" / "新托福资料"
DEFAULT_HUB_NAME = "新托福分科刷题材料"
ANSWER_PATTERN = re.compile(r"参考答案|答案", re.I)
PARTIAL_PATTERN = re.compile(r"缺|仅|待补|后续|部分", re.I)
DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})-(\d{2})-(\d{2})(?!\d)")
PATH_DATE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:20\d{2})\s*[./年-]\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*[./月-]\s*"
    r"(?P<day>3[01]|[12]\d|0?[1-9])(?:\s*日)?(?!\d)"
)
QUESTION_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?P<number>\d{1,3})\s*"
    r"(?P<answer>[A-Za-z][A-Za-z'’-]*)"
)
NUMBERED_LINE_PATTERN = re.compile(r"^\s*(\d{1,2})\s*[.)、]?\s*(.+?)\s*$")
LISTENING_QUESTION_PATTERN = re.compile(
    r"Listening\s*\|?\s*Question\s+(\d+)\s+of\s+(\d+)",
    re.I,
)
WRITING_QUESTION_PATTERN = re.compile(
    r"Writing\s*(?:\||I)?\s*Question\s*(\d+)\s*of\s*(\d+)",
    re.I,
)
EXPECTED = {
    ("reading", "m1"): 35,
    ("reading", "m2"): 15,
    ("listening", "m1"): 32,
    ("listening", "m2"): 15,
    ("writing", "m1"): 10,
}
CHOICES = {"A", "B", "C", "D"}


@dataclass
class PracticeSection:
    title: str
    folder: str
    sources: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    @property
    def date(self) -> str:
        match = DATE_PATTERN.search(self.title)
        return match.group(0) if match else ""

    @property
    def practice_id(self) -> str:
        suffix = self.title.removeprefix(self.date).strip()
        suffix = (
            suffix.replace("卷", "")
            .replace("套一", "S1")
            .replace("套二", "S2")
            .replace("国内线下", "offline-cn")
            .replace("线下", "offline")
            .strip()
        )
        slug = re.sub(r"[^A-Za-z0-9]+", "-", suffix).strip("-").lower()
        return self.date if not slug else f"{self.date}-{slug}"


@dataclass
class ParsedAnswer:
    subject: str
    module: str
    source_question_no: int
    answer_type: str
    correct_answer: str
    answer_form: str


@dataclass
class ParseResult:
    format: str
    answers: list[ParsedAnswer]
    warnings: list[str]


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_markdown_sections(path: Path) -> list[PracticeSection]:
    text = path.read_text(encoding="utf-8")
    sections: list[PracticeSection] = []
    for chunk in re.split(r"(?m)^## ", text)[1:]:
        lines = chunk.splitlines()
        title = lines[0].strip()
        if not DATE_PATTERN.match(title):
            continue
        folder = ""
        sources: list[str] = []
        for line in lines[1:]:
            if line.startswith("文件夹："):
                folder = line.split("：", 1)[1].strip()
            elif line.startswith("### 来源："):
                sources.append(line.split("：", 1)[1].strip())
        sections.append(
            PracticeSection(
                title=title,
                folder=folder,
                sources=sources,
                lines=lines[1:],
            )
        )
    return sections


def extract_pdf_text(path: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            proc.stderr.decode("utf-8", errors="replace").strip()
            or "pdftotext failed"
        )
    return proc.stdout.decode("utf-8", errors="replace").replace("\f", "\n")


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        parts = [
            node.text or ""
            for node in paragraph.iter(f"{namespace}t")
        ]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_document_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        text = extract_pdf_text(path)
    elif path.suffix.lower() == ".docx":
        text = extract_docx_text(path)
    else:
        raise RuntimeError(f"unsupported answer format: {path.suffix}")
    return unicodedata.normalize("NFKC", text).replace("\u00a0", " ")


def between(text: str, start_pattern: str, end_pattern: str | None) -> str:
    start = re.search(start_pattern, text, re.I)
    if not start:
        return ""
    if end_pattern is None:
        return text[start.end() :]
    end = re.search(end_pattern, text[start.end() :], re.I)
    if not end:
        return text[start.end() :]
    return text[start.end() : start.end() + end.start()]


def parse_tokens(text: str) -> tuple[list[tuple[int, str]], list[str]]:
    values: list[tuple[int, str]] = []
    warnings: list[str] = []
    seen: set[int] = set()
    for match in QUESTION_TOKEN_PATTERN.finditer(text):
        number = int(match.group("number"))
        answer = match.group("answer").strip("`'’.,;: ").lower()
        if number in seen:
            continue
        seen.add(number)
        values.append((number, answer))
    values.sort()
    if values:
        missing = sorted(set(range(1, values[-1][0] + 1)) - seen)
        if missing:
            warnings.append("missing question numbers: " + ",".join(map(str, missing)))
    return values, warnings


def parse_numbered_sentences(text: str) -> list[tuple[int, str]]:
    values: dict[int, str] = {}
    for line in text.splitlines():
        match = NUMBERED_LINE_PATTERN.match(line)
        if not match:
            continue
        number = int(match.group(1))
        if not 1 <= number <= 10:
            continue
        sentence = re.sub(r"\s+", " ", match.group(2)).strip()
        if sentence:
            values.setdefault(number, sentence)
    if values:
        return sorted(values.items())

    # DOCX bullet lists often lose their numbering during XML extraction.
    lines = [
        re.sub(r"^[\s•·▪◦-]+", "", line).strip()
        for line in text.splitlines()
        if line.strip()
    ]
    candidates = [
        line
        for line in lines
        if len(line.split()) >= 3
        and not re.fullmatch(r"写作|口语|Writing|Speaking", line, re.I)
    ]
    return list(enumerate(candidates[:10], start=1))


def _rows_from_tokens(
    subject: str,
    module: str,
    tokens: list[tuple[int, str]],
    source_format: str,
) -> list[ParsedAnswer]:
    rows: list[ParsedAnswer] = []
    reading_choice_start = 21 if module == "m1" else 11
    for number, answer in tokens:
        upper = answer.upper()
        is_choice = upper in CHOICES and (
            subject == "listening"
            or (subject == "reading" and number >= reading_choice_start)
        )
        if is_choice:
            answer_type = "mc"
            correct_answer = upper
            answer_form = "option_key"
        else:
            answer_type = "fill"
            correct_answer = answer
            answer_form = (
                "word_or_missing_letters"
                if source_format == "english_modules"
                else "word"
            )
        rows.append(
            ParsedAnswer(
                subject=subject,
                module=module,
                source_question_no=number,
                answer_type=answer_type,
                correct_answer=correct_answer,
                answer_form=answer_form,
            )
        )
    return rows


def parse_english_modules(text: str) -> ParseResult:
    block_patterns = {
        ("reading", "m1"): (
            r"Reading\s*,?\s*Module\s*1\s*:",
            r"(?m)^\s*Module\s*2\s*:",
        ),
        ("reading", "m2"): (
            r"(?m)^\s*Module\s*2\s*:",
            r"Listening\s+module\s*1",
        ),
        ("listening", "m1"): (
            r"Listening\s+module\s*1",
            r"Listening\s+module\s*2",
        ),
        ("listening", "m2"): (
            r"Listening\s+module\s*2",
            r"(?m)^\s*Writing\b",
        ),
    }
    answers: list[ParsedAnswer] = []
    warnings: list[str] = []
    for key, (start, end) in block_patterns.items():
        tokens, block_warnings = parse_tokens(between(text, start, end))
        answers.extend(_rows_from_tokens(*key, tokens, "english_modules"))
        warnings.extend(f"{key[0]}.{key[1]}: {item}" for item in block_warnings)
        expected = EXPECTED[key]
        if len(tokens) != expected:
            warnings.append(
                f"{key[0]}.{key[1]}: expected {expected}, found {len(tokens)}"
            )

    writing_text = between(
        text,
        r"Build\s+a\s+sentence\s*\.",
        r"(?m)^\s*Speaking\b",
    )
    writing = parse_numbered_sentences(writing_text)
    answers.extend(
        ParsedAnswer(
            subject="writing",
            module="m1",
            source_question_no=number,
            answer_type="order",
            correct_answer=sentence,
            answer_form="sentence",
        )
        for number, sentence in writing
    )
    if len(writing) != EXPECTED[("writing", "m1")]:
        warnings.append(f"writing.m1: expected 10, found {len(writing)}")
    return ParseResult("english_modules", answers, warnings)


def split_chinese_subjects(text: str) -> dict[str, str]:
    matches = list(
        re.finditer(r"(?m)^\s*(阅读|听力|写作(?:\s*[AB])?|口语)\s*$", text)
    )
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        if heading.startswith("阅读"):
            result.setdefault("reading", body)
        elif heading.startswith("听力"):
            result.setdefault("listening", body)
        elif heading.startswith("写作"):
            result.setdefault("writing", body)
        elif heading == "口语":
            result.setdefault("speaking", body)
    return result


def split_main_extra(text: str) -> tuple[str, str]:
    match = re.search(r"(?m)^\s*(?:加试|第二部[份分])\s*$", text)
    if not match:
        return text, ""
    return text[: match.start()], text[match.end() :]


def parse_chinese_sections(text: str) -> ParseResult:
    subjects = split_chinese_subjects(text)
    answers: list[ParsedAnswer] = []
    warnings: list[str] = []
    for subject in ("reading", "listening"):
        main, extra = split_main_extra(subjects.get(subject, ""))
        for module, block in (("m1", main), ("m2", extra)):
            tokens, block_warnings = parse_tokens(block)
            answers.extend(_rows_from_tokens(subject, module, tokens, "chinese_sections"))
            warnings.extend(
                f"{subject}.{module}: {item}" for item in block_warnings
            )
            expected = EXPECTED[(subject, module)]
            if len(tokens) != expected:
                warnings.append(
                    f"{subject}.{module}: expected {expected}, found {len(tokens)}"
                )

    writing = parse_numbered_sentences(subjects.get("writing", ""))
    answers.extend(
        ParsedAnswer(
            subject="writing",
            module="m1",
            source_question_no=number,
            answer_type="order",
            correct_answer=sentence,
            answer_form="sentence",
        )
        for number, sentence in writing
    )
    if subjects.get("writing") and len(writing) != EXPECTED[("writing", "m1")]:
        warnings.append(f"writing.m1: expected 10, found {len(writing)}")
    return ParseResult("chinese_sections", answers, warnings)


def parse_answer_document(path: Path) -> ParseResult:
    text = extract_document_text(path)
    if re.search(r"Reading\s*,?\s*Module\s*1", text, re.I):
        return parse_english_modules(text)
    if re.search(r"(?m)^\s*(?:阅读|听力)\s*$", text):
        return parse_chinese_sections(text)
    return ParseResult("unsupported", [], ["unrecognized answer layout"])


def _path_component_date(value: str, default_year: int = 2026) -> str | None:
    matches = list(PATH_DATE_PATTERN.finditer(value))
    if not matches:
        return None
    match = matches[-1]
    try:
        return (
            f"{default_year:04d}-{int(match.group('month')):02d}-"
            f"{int(match.group('day')):02d}"
        )
    except ValueError:
        return None


def candidate_answer_files(
    section: PracticeSection,
    root: Path,
) -> list[Path]:
    folder = root / section.folder
    if not folder.exists():
        return []
    candidates: list[Path] = []
    for path in folder.rglob("*"):
        if (
            not path.is_file()
            or path.suffix.lower() not in {".pdf", ".docx"}
            or not ANSWER_PATTERN.search(path.name)
        ):
            continue
        relative_parts = path.relative_to(folder).parts[:-1]
        nested_dates = {
            found
            for part in relative_parts
            if (found := _path_component_date(part))
        }
        if nested_dates and section.date not in nested_dates:
            continue
        candidates.append(path)
    return sorted(candidates, key=lambda path: (len(path.parts), str(path).lower()))


def primary_answer_file(candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda path: (
            bool(re.search(r"阅读|听力|写作|口语|speaking|listening|reading|writing", path.name, re.I)),
            len(path.name),
            str(path).lower(),
        ),
    )


def listening_coverage(section: PracticeSection) -> set[tuple[str, int]]:
    result: set[tuple[str, int]] = set()
    for line in section.lines:
        match = LISTENING_QUESTION_PATTERN.search(line)
        if not match:
            continue
        number, total = map(int, match.groups())
        module = "m1" if total > 20 else "m2"
        result.add((module, number))
    return result


def writing_coverage(section: PracticeSection) -> set[tuple[str, int]]:
    result: set[tuple[str, int]] = set()
    for line in section.lines:
        match = WRITING_QUESTION_PATTERN.search(line)
        if match:
            result.add(("m1", int(match.group(1))))
    return result


def reading_record_coverage(path: Path) -> set[tuple[str, int, str]]:
    items = json.loads(path.read_text(encoding="utf-8"))
    result: set[tuple[str, int, str]] = set()
    module_index = 1
    previous_number: int | None = None
    for item in items:
        number = item.get("number")
        if not isinstance(number, int) or number < 1:
            continue
        if previous_number is not None and number < previous_number and number <= 11:
            module_index += 1
        if module_index > 2:
            break
        module = f"m{module_index}"
        if item.get("kind") == "complete_words":
            number_end = item.get("number_end") or number
            for value in range(number, int(number_end) + 1):
                result.add((module, value, "fill"))
        elif item.get("kind") == "question":
            result.add((module, number, "mc"))
        previous_number = item.get("number_end") or number
    return result


def reading_coverage(
    manifest: list[dict[str, Any]],
    title: str,
) -> tuple[set[tuple[str, int, str]], list[str]]:
    result: set[tuple[str, int, str]] = set()
    sources: list[str] = []
    for record in manifest:
        if record.get("date") != title:
            continue
        output = Path(record["output"])
        sources.append(record.get("relative_source") or str(output))
        if output.exists():
            result.update(reading_record_coverage(output))
    return result, sources


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_crosswalk(root: Path, hub: Path) -> dict[str, Any]:
    output_dir = hub / "整理输出"
    listening_sections = {
        section.title: section
        for section in parse_markdown_sections(output_dir / "托福真题整理_听力.md")
    }
    reading_sections = {
        section.title: section
        for section in parse_markdown_sections(output_dir / "托福真题整理_阅读.md")
    }
    writing_sections = {
        section.title: section
        for section in parse_markdown_sections(output_dir / "托福真题整理_写作.md")
    }
    manifest = json.loads(
        (root / "tmp/pdfs/reading_structured/manifest.json").read_text(
            encoding="utf-8"
        )
    )

    titles = list(listening_sections)
    exam_rows: list[dict[str, Any]] = []
    question_rows: list[dict[str, Any]] = []

    for title in titles:
        section = listening_sections[title]
        candidates = candidate_answer_files(section, root)
        answer_file = primary_answer_file(candidates)
        parse_result = (
            parse_answer_document(answer_file)
            if answer_file
            else ParseResult("none", [], ["no answer file"])
        )
        source_path = _relative(answer_file, root) if answer_file else ""
        source_sha256 = sha256_file(answer_file) if answer_file else ""
        listen_targets = listening_coverage(section)
        write_targets = writing_coverage(writing_sections[title])
        read_targets, read_sources = reading_coverage(manifest, title)

        counts: dict[tuple[str, str], int] = defaultdict(int)
        matched: dict[tuple[str, str], int] = defaultdict(int)
        for answer in parse_result.answers:
            counts[(answer.subject, answer.answer_type)] += 1
            if answer.subject == "reading":
                exists = (
                    answer.module,
                    answer.source_question_no,
                    answer.answer_type,
                ) in read_targets
            elif answer.subject == "listening":
                exists = (
                    answer.module,
                    answer.source_question_no,
                ) in listen_targets
            else:
                exists = (
                    answer.module,
                    answer.source_question_no,
                ) in write_targets
            if exists:
                matched[(answer.subject, answer.answer_type)] += 1

            question_rows.append(
                {
                    "practice_id": section.practice_id,
                    "practice_title": title,
                    "subject": answer.subject,
                    "module": answer.module,
                    "source_question_no": answer.source_question_no,
                    "answer_type": answer.answer_type,
                    "correct_answer": answer.correct_answer,
                    "answer_form": answer.answer_form,
                    "canonical_key": (
                        f"{section.practice_id}:{answer.subject}:"
                        f"{answer.module}:q{answer.source_question_no}"
                    ),
                    "answer_source": source_path,
                    "answer_source_sha256": source_sha256,
                    "practice_target_exists": exists,
                    "match_status": "mapped" if exists else "answer_without_target",
                }
            )

        incomplete_marker = bool(
            PARTIAL_PATTERN.search(section.folder)
            or any(PARTIAL_PATTERN.search(source) for source in section.sources)
        )
        if not answer_file:
            status = "no_answer_file"
        elif parse_result.format == "unsupported":
            status = "unsupported_answer_layout"
        elif incomplete_marker:
            status = "mapped_partial_material"
        elif parse_result.warnings:
            status = "mapped_with_warnings"
        else:
            status = "mapped"

        exam_rows.append(
            {
                "practice_id": section.practice_id,
                "practice_title": title,
                "folder": section.folder,
                "reading_sources": " | ".join(read_sources or reading_sections[title].sources),
                "listening_sources": " | ".join(section.sources),
                "writing_sources": " | ".join(writing_sections[title].sources),
                "answer_candidates": " | ".join(_relative(path, root) for path in candidates),
                "primary_answer_file": _relative(answer_file, root) if answer_file else "",
                "answer_format": parse_result.format,
                "status": status,
                "partial_material": incomplete_marker,
                "reading_fill_answers": counts[("reading", "fill")],
                "reading_fill_matched": matched[("reading", "fill")],
                "reading_mc_answers": counts[("reading", "mc")],
                "reading_mc_matched": matched[("reading", "mc")],
                "listening_mc_answers": counts[("listening", "mc")],
                "listening_mc_matched": matched[("listening", "mc")],
                "writing_order_answers": counts[("writing", "order")],
                "writing_order_matched": matched[("writing", "order")],
                "warnings": " | ".join(parse_result.warnings),
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_root": str(root),
        "practice_hub": str(hub),
        "exams": exam_rows,
        "answers": question_rows,
    }


def render_report(payload: dict[str, Any]) -> str:
    exams = payload["exams"]
    answers = payload["answers"]
    status_counts: dict[str, int] = defaultdict(int)
    for row in exams:
        status_counts[row["status"]] += 1

    mapped_answers = sum(row["practice_target_exists"] for row in answers)
    choice_answers = [
        row for row in answers if row["answer_type"] == "mc"
    ]
    mapped_choices = sum(row["practice_target_exists"] for row in choice_answers)

    lines = [
        "# TOEFL 参考答案 - 刷题文档对应报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 汇编套题：{len(exams)}",
        f"- 解析答案条目：{len(answers)}",
        f"- 已找到汇编题号目标：{mapped_answers}/{len(answers)}",
        f"- MC 选项已找到汇编题号目标：{mapped_choices}/{len(choice_answers)}",
        "",
        "## 状态汇总",
        "",
        "| 状态 | 套题数 |",
        "|---|---:|",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## 套题对应",
            "",
            "| 套题 | 答案文件 | 格式 | 阅读 MC | 听力 MC | 写作排序 | 状态 |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in exams:
        lines.append(
            f"| {row['practice_title']} | "
            f"`{row['primary_answer_file'] or '-'}` | "
            f"{row['answer_format']} | "
            f"{row['reading_mc_matched']}/{row['reading_mc_answers']} | "
            f"{row['listening_mc_matched']}/{row['listening_mc_answers']} | "
            f"{row['writing_order_matched']}/{row['writing_order_answers']} | "
            f"{row['status']} |"
        )

    lines.extend(
        [
            "",
            "## 关键约束",
            "",
            "- 主卷对应 `m1`，加试/第二部分对应 `m2`；两者题号都会重启。",
            "- 早期官方答案中的阅读填词常是缺失字母片段，不是完整单词；不能直接用于完整词判分。",
            "- `practice_target_exists=true` 只证明汇编中存在该题号，不证明 OCR 题干和四个选项完整。",
            "- 同一天可能有普通卷、线下卷或多个题组，日期本身不是唯一键。",
            "- 导入时必须保留 `answer_source_sha256` 和 `canonical_key`，禁止按裸题号批量更新。",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "crosswalk.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        render_report(payload),
        encoding="utf-8",
    )
    write_csv(
        output_dir / "exam_crosswalk.csv",
        [
            "practice_id",
            "practice_title",
            "folder",
            "reading_sources",
            "listening_sources",
            "writing_sources",
            "answer_candidates",
            "primary_answer_file",
            "answer_format",
            "status",
            "partial_material",
            "reading_fill_answers",
            "reading_fill_matched",
            "reading_mc_answers",
            "reading_mc_matched",
            "listening_mc_answers",
            "listening_mc_matched",
            "writing_order_answers",
            "writing_order_matched",
            "warnings",
        ],
        payload["exams"],
    )
    write_csv(
        output_dir / "question_answer_crosswalk.csv",
        [
            "practice_id",
            "practice_title",
            "subject",
            "module",
            "source_question_no",
            "answer_type",
            "correct_answer",
            "answer_form",
            "canonical_key",
            "answer_source",
            "answer_source_sha256",
            "practice_target_exists",
            "match_status",
        ],
        payload["answers"],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/toefl_answer_keys/practice_crosswalk"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    hub = root / DEFAULT_HUB_NAME
    payload = build_crosswalk(root, hub)
    write_outputs(payload, args.output_dir)
    print(
        f"mapped {len(payload['exams'])} practice sets and "
        f"{len(payload['answers'])} answer rows to {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
