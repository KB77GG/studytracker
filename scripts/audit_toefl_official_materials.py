#!/usr/bin/env python3
"""Audit ETS TOEFL Practice/OG materials for duplicate content.

The source files remain untouched. The audit distinguishes:

- duplicate_copy: the same file stored more than once;
- within_set_duplicate_asset: repeated media inside one practice set;
- shared_direction_asset: reusable direction audio shared by different sets;
- cross_set_content_duplicate: non-direction content shared by different sets.

It also extracts question-like text blocks from the official PDFs and reports
exact and near duplicate blocks across Practice Tests and the OG practice test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable


DEFAULT_SOURCE = Path.home() / "Desktop" / "新托福资料"
DEFAULT_OUTPUT = Path("data") / "toefl_official_audit"
NOTICE = "内部学习资料，禁止外传或用于商业用途"

MEDIA_EXTENSIONS = {".mp3", ".m4a", ".wav", ".ogg", ".mp4", ".mov"}
AUDITED_EXTENSIONS = MEDIA_EXTENSIONS | {".pdf", ".zip"}
QUESTION_START_RE = re.compile(
    r"(?m)^\s*(?P<number>\d+(?:\s*[–-]\s*\d+)?)\.\s+(?P<body>\S.*)$"
)
FILL_RANGE_RE = re.compile(
    r"Fill in the missing letters in the paragraph\.\s*"
    r"\(Questions?\s+(?P<number>\d+\s*[–-]\s*\d+)\)\s*"
    r"(?P<body>.+?)(?=\n\s*(?:Read an?|TOEFL iBT|$))",
    re.I | re.S,
)
SECTION_PATTERNS = {
    "reading": re.compile(r"(?:—\s*)?Reading(?:\s+Section)?", re.I),
    "listening": re.compile(r"(?:—\s*)?Listening(?:\s+Section)?", re.I),
    "writing": re.compile(r"(?:—\s*)?Writing(?:\s+Section)?", re.I),
    "speaking": re.compile(r"(?:—\s*)?Speaking(?:\s+Section)?", re.I),
}
BOILERPLATE_PATTERNS = (
    re.compile(r"TOEFL\s*iBT.*Practice Test", re.I),
    re.compile(r"Copyright ©? 2025 by ETS", re.I),
    re.compile(r"This ebook was issued to", re.I),
    re.compile(r"Unlawful distribution", re.I),
    re.compile(r"SdkBytes\(", re.I),
    re.compile(r"BAOXIN ZHANG", re.I),
    re.compile(r"THE OFFICIAL GUIDE TO THE TOEFL", re.I),
    re.compile(r"^\s*\d+\s*$"),
)


@dataclass(frozen=True)
class OfficialSource:
    source_id: str
    label: str
    kind: str
    pdf_path: Path
    media_paths: tuple[Path, ...] = ()
    text_start_pattern: str | None = None
    text_end_pattern: str | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_sources(root: Path) -> list[OfficialSource]:
    specs = [
        (
            "ets-practice-1",
            "ETS Student Practice Test 1",
            "student_practice",
            root / "toefl-ibt-full-length-practice-test-1.pdf",
            (
                root / "Student Practice Test 1 - Audio Files",
                root / "Student Practice Test 1 - Audio Files 2",
                root / "Student Practice Test 1 - Audio Files 2.zip",
                root / "student-practice-test-1-audio-files.zip",
            ),
            None,
            None,
        ),
        (
            "ets-practice-2",
            "ETS Student Practice Test 2",
            "student_practice",
            root / "测试2" / "toefl-ibt-full-length-practice-test-2.pdf",
            (
                root / "测试2" / "Student Practice Test 2 - Audio Files",
                root / "测试2" / "student-practice-test-2-audio-files.zip",
            ),
            None,
            None,
        ),
        (
            "ets-practice-3",
            "ETS Teacher Practice Test 3",
            "teacher_practice",
            root / "tmp_pdfs" / "ets_practice_test_3.pdf",
            (
                root / "test 5" / "teacher-Practice-Test-3-audio-files.zip",
                root / "test 5" / "teacher-Practice-Test-3-audio-files (1).zip",
            ),
            None,
            None,
        ),
        (
            "ets-practice-4",
            "ETS Teacher Practice Test 4",
            "teacher_practice",
            root / "test 6" / "toefl-ibt-teachers-resources-practice-test-4.pdf",
            (
                root / "test 6" / "Teacher Practice Test 4 Audio Files",
                root / "test 6" / "teacher-practice-test-4-audio-files.zip",
            ),
            None,
            None,
        ),
        (
            "ets-practice-5",
            "ETS Teacher Practice Test 5",
            "teacher_practice",
            root / "test 7" / "toefl-ibt-teachers-resources-practice-test-5.pdf",
            (
                root / "test 7" / "Teacher Practice Test 5 Audio Files",
                root / "test 7" / "teacher-practice-test-5-audio-files.zip",
            ),
            None,
            None,
        ),
        (
            "ets-og-chapter-6",
            "ETS Official Guide Chapter 6 Practice Test",
            "official_guide",
            root
            / "新版托福考试官方指南（OG）"
            / "The Official Guide to the TOEFL iBT Test_ Pocket Edition (Limited Digital Release).pdf",
            (
                root
                / "新版托福考试官方指南（OG）"
                / "Audio_Video Files"
                / "Chapter 6_Audio_Video",
            ),
            r"(?im)^\s*CHAPTER 6\s*$[\s\S]{0,800}?"
            r"^\s*TOEFL iBT®?\s*$[\s\S]{0,120}?^\s*Practice Test\s*$",
            r"(?im)^\s*Answers, Explanations, and Scripts\s*$",
        ),
    ]
    return [
        OfficialSource(
            source_id=source_id,
            label=label,
            kind=kind,
            pdf_path=pdf_path,
            media_paths=tuple(media_paths),
            text_start_pattern=text_start_pattern,
            text_end_pattern=text_end_pattern,
        )
        for (
            source_id,
            label,
            kind,
            pdf_path,
            media_paths,
            text_start_pattern,
            text_end_pattern,
        ) in specs
        if pdf_path.is_file()
    ]


def iter_source_files(source: OfficialSource) -> Iterable[Path]:
    yield source.pdf_path
    for media_path in source.media_paths:
        if media_path.is_file() and media_path.suffix.lower() in AUDITED_EXTENSIONS:
            yield media_path
        elif media_path.is_dir():
            for path in media_path.rglob("*"):
                if (
                    path.is_file()
                    and path.suffix.lower() in AUDITED_EXTENSIONS
                    and not path.name.startswith(".")
                    and "__MACOSX" not in path.parts
                ):
                    yield path


def extract_pdf_text(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise RuntimeError("pdftotext is required")
    result = subprocess.run(
        [pdftotext, "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Unable to read {path}")
    return result.stdout


def slice_source_text(source: OfficialSource, text: str) -> str:
    if source.text_start_pattern:
        start_match = re.search(source.text_start_pattern, text)
        if not start_match:
            raise RuntimeError(f"Start marker not found for {source.source_id}")
        text = text[start_match.start():]
    if source.text_end_pattern:
        end_match = re.search(source.text_end_pattern, text)
        if not end_match:
            raise RuntimeError(f"End marker not found for {source.source_id}")
        text = text[:end_match.start()]
    return text


def clean_page_text(page: str) -> str:
    lines = []
    skip_sdk = False
    for raw_line in page.splitlines():
        line = raw_line.strip()
        if "SdkBytes(" in line:
            skip_sdk = True
            continue
        if skip_sdk:
            if line.endswith(")") or re.fullmatch(r"[0-9a-f]+\)", line, re.I):
                skip_sdk = False
            continue
        if any(pattern.search(line) for pattern in BOILERPLATE_PATTERNS):
            continue
        lines.append(raw_line.rstrip())
    return "\n".join(lines).strip()


def normalize_content(value: str) -> str:
    value = value.replace("’", "'").replace("‘", "'").replace("–", "-")
    value = re.sub(r"\b(?:question|questions)\s+\d+(?:\s*-\s*\d+)?\b", " ", value, flags=re.I)
    value = re.sub(r"(?m)^\s*\d+(?:\s*-\s*\d+)?\.\s*", "", value)
    value = re.sub(r"(?m)^\s*\([A-D]\)\s*", "", value)
    value = re.sub(r"(?m)^\s*[A-D]\.\s*", "", value)
    value = re.sub(r"[^a-z0-9'_]+", " ", value.lower())
    return re.sub(r"\s+", " ", value).strip()


def _section_for_page(page: str, previous: str | None) -> str | None:
    header = "\n".join(page.splitlines()[:12])
    for section, pattern in SECTION_PATTERNS.items():
        if pattern.search(header):
            return section
    return previous


def _module_for_page(page: str, previous: str) -> str:
    match = re.search(r"\bModule\s+([12])\b", page, re.I)
    return f"m{match.group(1)}" if match else previous


def extract_question_blocks(source: OfficialSource, text: str) -> list[dict]:
    blocks: list[dict] = []
    section: str | None = None
    module = "main"
    for page_number, raw_page in enumerate(text.split("\f"), start=1):
        page = clean_page_text(raw_page)
        if not page:
            continue
        section = _section_for_page(page, section)
        module = _module_for_page(page, module)
        if not section:
            continue
        if re.search(r"Answer Key|Answers, Explanations|Self-Scoring", page, re.I):
            continue

        occupied: list[tuple[int, int]] = []
        for match in FILL_RANGE_RE.finditer(page):
            occupied.append(match.span())
            body = match.group(0)
            normalized = normalize_content(body)
            if len(normalized) >= 80:
                blocks.append({
                    "source_id": source.source_id,
                    "section": section,
                    "module": module,
                    "question_no": re.sub(r"\s+", "", match.group("number")),
                    "page": page_number,
                    "text": re.sub(r"\s+", " ", body).strip(),
                    "normalized": normalized,
                })

        matches = list(QUESTION_START_RE.finditer(page))
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(page)
            if any(span_start <= start < span_end for span_start, span_end in occupied):
                continue
            body = page[start:end].strip()
            normalized = normalize_content(body)
            if len(normalized) < 80:
                continue
            blocks.append({
                "source_id": source.source_id,
                "section": section,
                "module": module,
                "question_no": re.sub(r"\s+", "", match.group("number")),
                "page": page_number,
                "text": re.sub(r"\s+", " ", body).strip(),
                "normalized": normalized,
            })
    return blocks


def canonical_path(paths: list[Path]) -> Path:
    def rank(path: Path) -> tuple[int, int, str]:
        text = str(path)
        penalty = int(" (1)" in text) + int(" Files 2" in text) + int("__MACOSX" in text)
        return penalty, len(path.parts), text

    return min(paths, key=rank)


def classify_file_duplicate(rows: list[dict]) -> str:
    source_ids = {row["source_id"] for row in rows}
    names = [Path(row["path"]).name.lower() for row in rows]
    if len(source_ids) == 1:
        simplified = {re.sub(r"\s*\(1\)(?=\.)", "", name) for name in names}
        if len(simplified) == 1 or len({row["relative_name"] for row in rows}) == 1:
            return "duplicate_copy"
        return "within_set_duplicate_asset"
    if all("direction" in name or "instruction" in name for name in names):
        return "shared_direction_asset"
    return "cross_set_content_duplicate"


def file_inventory(sources: list[OfficialSource], root: Path) -> tuple[list[dict], list[dict]]:
    records = []
    for source in sources:
        for path in iter_source_files(source):
            records.append({
                "source_id": source.source_id,
                "path": str(path.relative_to(root)),
                "relative_name": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })

    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["sha256"]].append(record)

    duplicate_groups = []
    for sha256, rows in grouped.items():
        if len(rows) < 2:
            continue
        paths = [root / row["path"] for row in rows]
        canonical = canonical_path(paths)
        duplicate_groups.append({
            "sha256": sha256,
            "classification": classify_file_duplicate(rows),
            "copy_count": len(rows),
            "source_ids": sorted({row["source_id"] for row in rows}),
            "canonical_path": str(canonical.relative_to(root)),
            "paths": sorted(row["path"] for row in rows),
            "reclaimable_bytes": sum(row["size_bytes"] for row in rows) - canonical.stat().st_size,
        })
    duplicate_groups.sort(key=lambda item: (-item["reclaimable_bytes"], item["sha256"]))
    return records, duplicate_groups


def compare_question_blocks(blocks: list[dict], near_threshold: float) -> list[dict]:
    duplicate_rows = []
    by_hash: dict[str, list[dict]] = defaultdict(list)
    for block in blocks:
        digest = hashlib.sha256(block["normalized"].encode("utf-8")).hexdigest()
        block["content_sha256"] = digest
        by_hash[digest].append(block)

    exact_pairs: set[tuple[str, str]] = set()
    for digest, rows in by_hash.items():
        source_ids = {row["source_id"] for row in rows}
        if len(source_ids) < 2:
            continue
        for left_index, left in enumerate(rows):
            for right in rows[left_index + 1:]:
                if left["source_id"] == right["source_id"]:
                    continue
                pair_key = tuple(sorted((left["source_id"], right["source_id"])))
                exact_pairs.add(pair_key)
                duplicate_rows.append({
                    "match_type": "exact",
                    "similarity": 1.0,
                    "section": left["section"],
                    "left_source": left["source_id"],
                    "left_module": left["module"],
                    "left_question": left["question_no"],
                    "left_page": left["page"],
                    "right_source": right["source_id"],
                    "right_module": right["module"],
                    "right_question": right["question_no"],
                    "right_page": right["page"],
                    "content_sha256": digest,
                    "excerpt": left["text"][:220],
                })

    candidates = [
        block for block in blocks
        if len(block["normalized"]) >= 120
    ]
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1:]:
            if left["source_id"] == right["source_id"] or left["section"] != right["section"]:
                continue
            if left["content_sha256"] == right["content_sha256"]:
                continue
            length_ratio = min(len(left["normalized"]), len(right["normalized"])) / max(
                len(left["normalized"]), len(right["normalized"])
            )
            if length_ratio < 0.84:
                continue
            similarity = SequenceMatcher(
                None,
                left["normalized"],
                right["normalized"],
                autojunk=False,
            ).ratio()
            if similarity < near_threshold:
                continue
            duplicate_rows.append({
                "match_type": "near",
                "similarity": round(similarity, 4),
                "section": left["section"],
                "left_source": left["source_id"],
                "left_module": left["module"],
                "left_question": left["question_no"],
                "left_page": left["page"],
                "right_source": right["source_id"],
                "right_module": right["module"],
                "right_question": right["question_no"],
                "right_page": right["page"],
                "content_sha256": "",
                "excerpt": left["text"][:220],
            })
    duplicate_rows.sort(
        key=lambda item: (-item["similarity"], item["left_source"], item["right_source"])
    )
    return duplicate_rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: " | ".join(value) if isinstance(value, list) else value
                for key, value in row.items()
            })


def build_summary(
    sources: list[OfficialSource],
    file_records: list[dict],
    file_duplicates: list[dict],
    question_blocks: list[dict],
    question_duplicates: list[dict],
) -> str:
    class_counts: dict[str, int] = defaultdict(int)
    for group in file_duplicates:
        class_counts[group["classification"]] += 1
    exact_questions = sum(row["match_type"] == "exact" for row in question_duplicates)
    near_questions = sum(row["match_type"] == "near" for row in question_duplicates)
    risky_groups = [
        group for group in file_duplicates
        if group["classification"] == "cross_set_content_duplicate"
    ]

    lines = [
        "# TOEFL 官方 Practice / OG 重复审计",
        "",
        f"> {NOTICE}",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 官方来源：**{len(sources)}**",
        f"- 审计文件：**{len(file_records)}**",
        f"- 文件重复组：**{len(file_duplicates)}**",
        f"- 纯副本：**{class_counts['duplicate_copy']}**",
        f"- 同套内部重复媒体：**{class_counts['within_set_duplicate_asset']}**",
        f"- 跨套共享说明媒体：**{class_counts['shared_direction_asset']}**",
        f"- 跨套内容重复媒体：**{class_counts['cross_set_content_duplicate']}**",
        f"- 抽取题目块：**{len(question_blocks)}**",
        f"- 跨套完全相同题目块：**{exact_questions}**",
        f"- 跨套近似题目块：**{near_questions}**",
        "",
        "## 收录结论",
        "",
        "- Student Practice Test 1 的两个解压目录是完整镜像，只保留一个逻辑来源。",
        "- Teacher Practice Test 1、2、3 的 `(1).zip` 与无后缀 ZIP 是纯副本。",
        "- `Directions` 音频可跨套共享，不应被误判为重复试题。",
        "- 非说明类跨套媒体或题目块重复必须人工确认，确认前不能作为新套卷发布。",
        "- OG Chapter 6 是独立来源；与 Practice Test 1–5 的题目块对比结果见 CSV。",
        "",
        "## 官方来源",
        "",
        "| ID | 类型 | PDF | 题目块 |",
        "|---|---|---|---:|",
    ]
    block_counts: dict[str, int] = defaultdict(int)
    for block in question_blocks:
        block_counts[block["source_id"]] += 1
    for source in sources:
        lines.append(
            f"| {source.source_id} | {source.kind} | `{source.pdf_path.name}` | "
            f"{block_counts[source.source_id]} |"
        )

    lines.extend(["", "## 高风险跨套文件重复", ""])
    if not risky_groups:
        lines.append("未发现非说明类跨套媒体文件完全相同。")
    else:
        for group in risky_groups:
            lines.append(
                f"- `{group['sha256'][:12]}`: "
                + "；".join(group["paths"])
            )

    lines.extend(["", "## 题目级重复", ""])
    if not question_duplicates:
        lines.append("未发现达到阈值的跨套题目块重复。")
    else:
        for row in question_duplicates[:30]:
            lines.append(
                f"- {row['match_type']} {row['similarity']:.2%}: "
                f"{row['left_source']} {row['section']} {row['left_module']}/Q{row['left_question']} "
                f"↔ {row['right_source']} {row['right_module']}/Q{row['right_question']}"
            )
    lines.extend([
        "",
        "## 导入门禁",
        "",
        "1. `duplicate_copy` 不建立第二套逻辑题库。",
        "2. `shared_direction_asset` 只做媒体复用，不影响套题唯一性。",
        "3. `cross_set_content_duplicate` 或题目级 exact/near 命中时，默认状态为 `review_required`。",
        "4. 发布 ID 使用 `source_id + subject + module + question_no`，禁止只按 Practice Test 编号或裸题号。",
        "",
    ])
    return "\n".join(lines)


def run(source_root: Path, output_dir: Path, near_threshold: float = 0.94) -> dict:
    sources = discover_sources(source_root)
    file_records, file_duplicates = file_inventory(sources, source_root)
    question_blocks = []
    for source in sources:
        text = slice_source_text(source, extract_pdf_text(source.pdf_path))
        question_blocks.extend(extract_question_blocks(source, text))
    question_duplicates = compare_question_blocks(question_blocks, near_threshold)

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_root": str(source_root),
        "notice": NOTICE,
        "sources": [
            {
                "source_id": source.source_id,
                "label": source.label,
                "kind": source.kind,
                "pdf_path": str(source.pdf_path.relative_to(source_root)),
                "pdf_sha256": sha256_file(source.pdf_path),
                "question_block_count": sum(
                    block["source_id"] == source.source_id for block in question_blocks
                ),
            }
            for source in sources
        ],
        "file_records": file_records,
        "file_duplicate_groups": file_duplicates,
        "question_blocks": question_blocks,
        "question_duplicate_matches": question_duplicates,
    }
    (output_dir / "inventory.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(
        output_dir / "file_duplicates.csv",
        file_duplicates,
        [
            "sha256",
            "classification",
            "copy_count",
            "source_ids",
            "canonical_path",
            "paths",
            "reclaimable_bytes",
        ],
    )
    write_csv(
        output_dir / "question_duplicates.csv",
        question_duplicates,
        [
            "match_type",
            "similarity",
            "section",
            "left_source",
            "left_module",
            "left_question",
            "left_page",
            "right_source",
            "right_module",
            "right_question",
            "right_page",
            "content_sha256",
            "excerpt",
        ],
    )
    (output_dir / "summary.md").write_text(
        build_summary(
            sources,
            file_records,
            file_duplicates,
            question_blocks,
            question_duplicates,
        ),
        encoding="utf-8",
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--near-threshold", type=float, default=0.94)
    args = parser.parse_args()
    payload = run(args.source.expanduser().resolve(), args.output, args.near_threshold)
    print(
        json.dumps(
            {
                "sources": len(payload["sources"]),
                "files": len(payload["file_records"]),
                "file_duplicate_groups": len(payload["file_duplicate_groups"]),
                "question_blocks": len(payload["question_blocks"]),
                "question_duplicate_matches": len(payload["question_duplicate_matches"]),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
