#!/usr/bin/env python3
"""Extract reusable answer-key rows from dated TOEFL answer PDFs.

The source PDFs use section-level numbering and restart numbering for "加试".
This script preserves that namespace instead of flattening question numbers too
early. It does not update application data.

Example:
    python scripts/extract_toefl_answer_keys.py \
      --root ~/Desktop/新托福资料 \
      --latest 3 \
      --output-dir data/toefl_answer_keys/latest_complete
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.0"
ANSWER_PDF_PATTERN = re.compile(r"参考答案|答案", re.I)
PARTIAL_PATTERN = re.compile(r"缺|仅|待补|后续|部分", re.I)
READING_PATTERN = re.compile(r"阅读|reading", re.I)
LISTENING_PATTERN = re.compile(r"听力|listening", re.I)
WRITING_PATTERN = re.compile(r"写作|writing", re.I)
SPEAKING_PATTERN = re.compile(r"口语|speaking", re.I)
FULL_PAPER_PATTERN = re.compile(r"真题|practice[\s_-]*test|full[\s_-]*length", re.I)
SECTION_HEADING_PATTERN = re.compile(r"^(阅读|听力|写作|口语)(?:\s|$)", re.I)
DATE_PATTERN = re.compile(
    r"(?<!\d)(?:(?P<year>20\d{2})\s*[./年-]\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*[./月-]\s*"
    r"(?P<day>3[01]|[12]\d|0?[1-9])(?:\s*日)?(?!\d)"
)
ANSWER_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?P<number>\d{1,3})\s*"
    r"(?P<answer>[A-Za-z][A-Za-z'’-]*)"
)
CHOICES = {"A", "B", "C", "D"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx"}
EXPECTED_COUNTS = {
    ("reading", "main"): 35,
    ("reading", "extra"): 15,
    ("listening", "main"): 32,
    ("listening", "extra"): 15,
}


@dataclass(frozen=True)
class Candidate:
    exam_key: str
    exam_date: str
    variant: str
    answer_pdf: Path
    source_dir: Path
    sha256: str
    companion_sections: tuple[str, ...]
    companion_files: tuple[str, ...]
    partial_markers: tuple[str, ...]
    complete: bool
    rejection_reasons: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_date(value: str, default_year: int = 2026) -> str | None:
    matches = list(DATE_PATTERN.finditer(value))
    if not matches:
        return None
    match = matches[-1]
    year = int(match.group("year") or default_year)
    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def extract_path_date(path: Path, root: Path, default_year: int) -> str | None:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    for part in reversed(parts):
        exam_date = extract_date(part, default_year)
        if exam_date:
            return exam_date
    return None


def _chinese_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    values = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    return values.get(value)


def extract_variant(value: str) -> str:
    normalized = value.replace("Ａ", "A").replace("Ｂ", "B").replace("Ｃ", "C")
    match = re.search(r"(?<![A-Za-z])([ABC])\s*卷", normalized, re.I)
    if match:
        return match.group(1).upper()
    match = re.search(r"套\s*([一二三四五六七八九十\d]+)", normalized, re.I)
    if match:
        number = _chinese_number(match.group(1))
        if number:
            return f"S{number}"
    return "default"


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _iter_source_files(source_dir: Path) -> Iterable[Path]:
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") or part == "__MACOSX" for part in path.parts):
            continue
        yield path


def assess_candidate(
    answer_pdf: Path,
    root: Path,
    default_year: int,
    required_sections: set[str],
) -> Candidate | None:
    exam_date = extract_path_date(answer_pdf, root, default_year)
    if not exam_date:
        return None

    source_dir = answer_pdf.parent
    variant = extract_variant(source_dir.name)
    suffix = "" if variant == "default" else f"-{variant}"
    exam_key = f"{exam_date}{suffix}"

    source_files = list(_iter_source_files(source_dir))
    companion_sections: set[str] = set()
    companion_files: list[str] = []
    partial_markers: list[str] = []
    searchable_paths = [source_dir.name]

    for path in source_files:
        relative = _relative(path, source_dir)
        searchable_paths.append(relative)
        if PARTIAL_PATTERN.search(relative):
            partial_markers.append(relative)
        if path.suffix.lower() not in DOCUMENT_EXTENSIONS:
            continue
        name = path.name
        sections: set[str] = set()
        if READING_PATTERN.search(name):
            sections.add("reading")
        if LISTENING_PATTERN.search(name):
            sections.add("listening")
        has_explicit_section = any(
            pattern.search(name)
            for pattern in (
                READING_PATTERN,
                LISTENING_PATTERN,
                WRITING_PATTERN,
                SPEAKING_PATTERN,
            )
        )
        if (
            FULL_PAPER_PATTERN.search(name)
            and not ANSWER_PDF_PATTERN.search(name)
            and not re.search(r"原文|transcript", name, re.I)
            and not has_explicit_section
        ):
            sections.update({"reading", "listening"})
        if sections:
            companion_sections.update(sections)
            companion_files.append(relative)

    if PARTIAL_PATTERN.search(source_dir.name):
        partial_markers.append(source_dir.name)

    rejection_reasons = []
    missing = sorted(required_sections - companion_sections)
    if missing:
        rejection_reasons.append(f"missing companion sections: {','.join(missing)}")
    if partial_markers:
        rejection_reasons.append("partial/incomplete marker present")

    return Candidate(
        exam_key=exam_key,
        exam_date=exam_date,
        variant=variant,
        answer_pdf=answer_pdf,
        source_dir=source_dir,
        sha256=sha256_file(answer_pdf),
        companion_sections=tuple(sorted(companion_sections)),
        companion_files=tuple(sorted(set(companion_files))),
        partial_markers=tuple(sorted(set(partial_markers))),
        complete=not rejection_reasons,
        rejection_reasons=tuple(rejection_reasons),
    )


def discover_candidates(
    root: Path,
    default_year: int = 2026,
    required_sections: set[str] | None = None,
) -> list[Candidate]:
    required_sections = required_sections or {"reading", "listening"}
    raw_candidates = []
    for path in root.rglob("*.pdf"):
        if any(part.startswith(".") or part == "__MACOSX" for part in path.parts):
            continue
        if not ANSWER_PDF_PATTERN.search(path.name):
            continue
        candidate = assess_candidate(path, root, default_year, required_sections)
        if candidate:
            raw_candidates.append(candidate)

    # The source tree contains copied dated folders. Prefer the shortest direct
    # path for the same exam and exact answer PDF.
    deduplicated: dict[tuple[str, str], Candidate] = {}
    for candidate in raw_candidates:
        key = (candidate.exam_key, candidate.sha256)
        current = deduplicated.get(key)
        candidate_depth = len(candidate.answer_pdf.relative_to(root).parts)
        current_depth = (
            len(current.answer_pdf.relative_to(root).parts) if current else 10**9
        )
        if current is None or candidate_depth < current_depth:
            deduplicated[key] = candidate

    # If one exam folder has multiple answer PDFs, prefer a dedicated answer
    # file over a section-specific "阅读+答案" style file.
    by_exam: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in deduplicated.values():
        by_exam[candidate.exam_key].append(candidate)

    selected_per_exam = []
    for candidates in by_exam.values():
        candidates.sort(
            key=lambda item: (
                bool(
                    READING_PATTERN.search(item.answer_pdf.name)
                    or LISTENING_PATTERN.search(item.answer_pdf.name)
                    or re.search(r"写作|口语|writing|speaking", item.answer_pdf.name, re.I)
                ),
                len(item.answer_pdf.name),
                str(item.answer_pdf).lower(),
            )
        )
        selected_per_exam.append(candidates[0])

    return sorted(
        selected_per_exam,
        key=lambda item: (item.exam_date, item.exam_key),
        reverse=True,
    )


def extract_pdf_text(path: Path) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        raise RuntimeError("pdftotext is required; install Poppler first")
    proc = subprocess.run(
        [pdftotext, "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "pdftotext failed")
    text = unicodedata.normalize("NFKC", proc.stdout).replace("\u00a0", " ")
    if not re.sub(r"\s+", "", text):
        raise RuntimeError("answer PDF has no extractable text layer; OCR required")
    return text


def split_answer_blocks(text: str) -> dict[tuple[str, str], str]:
    blocks: dict[tuple[str, str], list[str]] = defaultdict(list)
    current_section: str | None = None
    current_block = "main"
    section_map = {
        "阅读": "reading",
        "听力": "listening",
        "写作": "writing",
        "口语": "speaking",
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = SECTION_HEADING_PATTERN.match(line)
        if heading:
            current_section = section_map[heading.group(1)]
            current_block = "main"
            continue
        if line.startswith("加试") and current_section in {"reading", "listening"}:
            current_block = "extra"
            remainder = line[len("加试") :].strip()
            if remainder:
                blocks[(current_section, current_block)].append(remainder)
            continue
        if current_section in {"reading", "listening"}:
            blocks[(current_section, current_block)].append(line)

    return {key: " ".join(lines) for key, lines in blocks.items()}


def parse_block_tokens(block_text: str) -> tuple[list[tuple[int, str]], list[str]]:
    answers: list[tuple[int, str]] = []
    warnings: list[str] = []
    seen: set[int] = set()
    for match in ANSWER_TOKEN_PATTERN.finditer(block_text):
        number = int(match.group("number"))
        answer = match.group("answer").strip().rstrip(".,;:").lower()
        if number in seen:
            warnings.append(f"duplicate source question number {number}")
            continue
        seen.add(number)
        answers.append((number, answer))

    answers.sort(key=lambda item: item[0])
    if answers:
        expected = set(range(1, answers[-1][0] + 1))
        missing = sorted(expected - {number for number, _ in answers})
        if missing:
            warnings.append(
                "missing source question numbers: " + ",".join(map(str, missing))
            )
    return answers, warnings


def _reading_choice_numbers(tokens: list[tuple[int, str]]) -> set[int]:
    """Return a trailing contiguous A-D run, avoiding short fill-word ambiguity."""
    choice_numbers: list[int] = []
    expected_number: int | None = None
    for number, answer in reversed(tokens):
        if answer.upper() not in CHOICES:
            break
        if expected_number is not None and number != expected_number:
            break
        choice_numbers.append(number)
        expected_number = number - 1
    return set(choice_numbers) if len(choice_numbers) >= 3 else set()


def parse_answer_text(
    text: str,
    exam_key: str,
    source_pdf: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    block_texts = split_answer_blocks(text)
    parsed_blocks: dict[tuple[str, str], list[tuple[int, str]]] = {}
    warnings: list[str] = []

    for section in ("reading", "listening"):
        for block in ("main", "extra"):
            key = (section, block)
            tokens, token_warnings = parse_block_tokens(block_texts.get(key, ""))
            parsed_blocks[key] = tokens
            for warning in token_warnings:
                warnings.append(f"{section}.{block}: {warning}")
            expected_count = EXPECTED_COUNTS[key]
            if len(tokens) != expected_count:
                warnings.append(
                    f"{section}.{block}: expected {expected_count} answers, "
                    f"found {len(tokens)}"
                )

    rows: list[dict[str, Any]] = []
    for section in ("reading", "listening"):
        main_max = max(
            (number for number, _ in parsed_blocks[(section, "main")]),
            default=0,
        )
        for block in ("main", "extra"):
            tokens = parsed_blocks[(section, block)]
            reading_choices = (
                _reading_choice_numbers(tokens) if section == "reading" else set()
            )
            choice_index = 0
            for number, answer in tokens:
                is_choice = (
                    answer.upper() in CHOICES
                    if section == "listening"
                    else number in reading_choices
                )
                if is_choice:
                    choice_index += 1
                section_question_no = number if block == "main" else main_max + number
                rows.append(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "exam_key": exam_key,
                        "section": section,
                        "block": block,
                        "is_extra": block == "extra",
                        "source_question_no": number,
                        "section_question_no": section_question_no,
                        "choice_question_no": choice_index if is_choice else None,
                        "answer_type": "choice" if is_choice else "text",
                        "correct_answer": answer.upper() if is_choice else answer,
                        "canonical_key": (
                            f"{exam_key}:{section}:{block}:q{number}"
                        ),
                        "source_pdf": source_pdf,
                        "source_page": 1,
                        "confidence": "high",
                    }
                )
    return rows, warnings


def build_choice_map(exams: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for exam in exams:
        exam_map: dict[str, dict[str, dict[str, str]]] = {
            "reading": {"main": {}, "extra": {}},
            "listening": {"main": {}, "extra": {}},
        }
        for row in exam["answers"]:
            if row["answer_type"] != "choice":
                continue
            exam_map[row["section"]][row["block"]][
                str(row["source_question_no"])
            ] = row["correct_answer"]
        result[exam["exam_key"]] = exam_map
    return result


def candidate_to_dict(candidate: Candidate, root: Path) -> dict[str, Any]:
    data = asdict(candidate)
    data["answer_pdf"] = _relative(candidate.answer_pdf, root)
    data["source_dir"] = _relative(candidate.source_dir, root)
    return data


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# TOEFL 答案提取报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 扫描目录：`{payload['source_root']}`",
        f"- 选中套题：{len(payload['exams'])}",
        "- 筛选规则：日期倒序；必须有阅读、听力题面；拒绝路径中带“缺/仅/待补/后续/部分”的套题。",
        "",
        "## 选中样本",
        "",
        "| 套题 | 答案 PDF | 全部答案 | 选项答案 | 校验 |",
        "|---|---|---:|---:|---|",
    ]
    for exam in payload["exams"]:
        choice_count = sum(
            1 for row in exam["answers"] if row["answer_type"] == "choice"
        )
        validation = "通过" if not exam["warnings"] else "需复核"
        lines.append(
            f"| {exam['exam_key']} | `{exam['source_answer_pdf']}` | "
            f"{len(exam['answers'])} | {choice_count} | {validation} |"
        )

    lines.extend(
        [
            "",
            "## 最近未选样本",
            "",
            "| 套题 | 答案 PDF | 原因 |",
            "|---|---|---|",
        ]
    )
    selected_keys = {exam["exam_key"] for exam in payload["exams"]}
    skipped = [
        row
        for row in payload["selection_audit"]
        if row["exam_key"] not in selected_keys
    ][:12]
    for row in skipped:
        reason = "；".join(row["rejection_reasons"]) or "超过 latest 数量"
        lines.append(
            f"| {row['exam_key']} | `{row['answer_pdf']}` | {reason} |"
        )
    if not skipped:
        lines.append("| - | - | - |")

    lines.extend(
        [
            "",
            "## 回填约束",
            "",
            "- 唯一键使用 `exam_key + section + block + source_question_no`。",
            "- `block=extra` 的题号会从 1 重启，不能只用题号关联。",
            "- `section_question_no` 是科目内累计编号，仅作为辅助定位。",
            "- `choice_question_no` 是当前块内仅统计选择题的序号，不等于原题号。",
            "- 业务库回填前必须提供 section/task 到目标 `section_id` 的显式映射。",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(payload: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "answer_keys.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "choice_map.json").write_text(
        json.dumps(build_choice_map(payload["exams"]), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(render_report(payload), encoding="utf-8")

    fields = [
        "schema_version",
        "exam_key",
        "exam_date",
        "variant",
        "source_dir",
        "section",
        "block",
        "is_extra",
        "source_question_no",
        "section_question_no",
        "choice_question_no",
        "answer_type",
        "correct_answer",
        "canonical_key",
        "source_pdf",
        "source_page",
        "source_sha256",
        "confidence",
    ]
    with (output_dir / "answer_keys.csv").open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for exam in payload["exams"]:
            for answer in exam["answers"]:
                writer.writerow(
                    {
                        **answer,
                        "exam_date": exam["exam_date"],
                        "variant": exam["variant"],
                        "source_dir": exam["source_dir"],
                        "source_sha256": exam["source_sha256"],
                    }
                )

    backfill_fields = [
        "schema_version",
        "canonical_key",
        "exam_key",
        "source_section",
        "source_block",
        "source_question_no",
        "correct_answer",
        "source_pdf",
        "source_sha256",
        "target_paper_id",
        "target_section_id",
        "target_question_id",
        "target_sequence",
        "match_method",
        "match_status",
        "reviewer_note",
    ]
    with (output_dir / "backfill_template.csv").open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=backfill_fields)
        writer.writeheader()
        for exam in payload["exams"]:
            for answer in exam["answers"]:
                if answer["answer_type"] != "choice":
                    continue
                writer.writerow(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "canonical_key": answer["canonical_key"],
                        "exam_key": exam["exam_key"],
                        "source_section": answer["section"],
                        "source_block": answer["block"],
                        "source_question_no": answer["source_question_no"],
                        "correct_answer": answer["correct_answer"],
                        "source_pdf": answer["source_pdf"],
                        "source_sha256": exam["source_sha256"],
                        "target_paper_id": "",
                        "target_section_id": "",
                        "target_question_id": "",
                        "target_sequence": "",
                        "match_method": "",
                        "match_status": "unmatched",
                        "reviewer_note": "",
                    }
                )


def build_payload(
    root: Path,
    latest: int,
    default_year: int,
    required_sections: set[str],
) -> dict[str, Any]:
    candidates = discover_candidates(root, default_year, required_sections)
    complete_candidates = [candidate for candidate in candidates if candidate.complete]
    selected = complete_candidates[:latest]

    exams = []
    for candidate in selected:
        relative_pdf = _relative(candidate.answer_pdf, root)
        text = extract_pdf_text(candidate.answer_pdf)
        answers, warnings = parse_answer_text(
            text,
            candidate.exam_key,
            relative_pdf,
        )
        exams.append(
            {
                "exam_key": candidate.exam_key,
                "exam_date": candidate.exam_date,
                "variant": candidate.variant,
                "source_dir": _relative(candidate.source_dir, root),
                "source_answer_pdf": relative_pdf,
                "source_sha256": candidate.sha256,
                "companion_sections": list(candidate.companion_sections),
                "companion_files": list(candidate.companion_files),
                "warnings": warnings,
                "answers": answers,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_root": str(root),
        "selection_policy": {
            "latest": latest,
            "default_year": default_year,
            "required_companion_sections": sorted(required_sections),
            "reject_partial_markers": PARTIAL_PATTERN.pattern,
            "answer_pdf_pattern": ANSWER_PDF_PATTERN.pattern,
        },
        "exams": exams,
        "selection_audit": [
            candidate_to_dict(candidate, root) for candidate in candidates
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.home() / "Desktop" / "新托福资料",
        help="Root directory containing dated TOEFL material folders",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data") / "toefl_answer_keys" / "latest_complete",
    )
    parser.add_argument("--latest", type=int, default=3)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument(
        "--require-sections",
        default="reading,listening",
        help="Comma-separated companion sections required for auto-selection",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any selected answer key has validation warnings",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"source root does not exist: {root}")
    if args.latest < 1:
        raise SystemExit("--latest must be at least 1")
    required_sections = {
        item.strip().lower()
        for item in args.require_sections.split(",")
        if item.strip()
    }
    unknown_sections = required_sections - {"reading", "listening"}
    if unknown_sections:
        raise SystemExit(
            "unsupported required sections: " + ",".join(sorted(unknown_sections))
        )

    payload = build_payload(root, args.latest, args.year, required_sections)
    write_outputs(payload, args.output_dir)

    warning_count = sum(len(exam["warnings"]) for exam in payload["exams"])
    print(
        f"selected {len(payload['exams'])} exams; "
        f"wrote outputs to {args.output_dir}; warnings={warning_count}"
    )
    if args.strict and warning_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
